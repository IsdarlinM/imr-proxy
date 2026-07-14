from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from imr_proxy.realtime import traffic_events
from imr_proxy.storage.database import connect
from imr_proxy.storage.repositories import FlowRepository

from .auth import SESSION_COOKIE, UserRepository

logger = logging.getLogger(__name__)

_DB_FALLBACK_CHECK_SECONDS = 2.0
_HEARTBEAT_SECONDS = 15.0
_AUTH_RECHECK_SECONDS = 30.0


def _origin_allowed(websocket: WebSocket) -> bool:
    """Reject cross-site browser WebSocket handshakes.

    Browser clients send an Origin header. Non-browser local clients may omit it,
    which remains useful for diagnostics and automated tests.
    """

    origin = websocket.headers.get("origin")
    if not origin:
        return True
    parsed = urlsplit(origin)
    request_host = (websocket.headers.get("host") or "").lower()
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == request_host


async def _close(websocket: WebSocket, code: int, reason: str) -> None:
    with suppress(RuntimeError, WebSocketDisconnect):
        await websocket.close(code=code, reason=reason)


async def _cancel(task: asyncio.Task[object]) -> None:
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def _event_payload(kind: str, revision: int, stats: dict[str, int] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": kind,
        "revision": revision,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if stats is not None:
        payload["stats"] = stats
    return payload


def register_traffic_websocket(app: FastAPI, storage: Path) -> None:
    """Register the authenticated real-time traffic notification stream.

    Committed flows are pushed through an in-process thread-safe event bus. A
    low-frequency SQLite revision check catches writes made by another process.
    The browser then reloads its currently filtered JSON view, so WebSocket and
    HTTP filtering always use the same query implementation.
    """

    @app.websocket("/ws/traffic")
    async def traffic_websocket(websocket: WebSocket) -> None:
        if not _origin_allowed(websocket):
            await _close(websocket, 4403, "Origin not allowed")
            return

        conn = connect(storage)
        users = UserRepository(conn)
        token = websocket.cookies.get(SESSION_COOKIE)
        subscription = None
        try:
            user = users.get_session_user(token, touch=False)
            if not user:
                await _close(websocket, 4401, "Authentication required")
                return

            flows = FlowRepository(conn)
            subscription = traffic_events.subscribe()
            revision = flows.revision()
            await websocket.accept()
            await websocket.send_json(_event_payload("ready", revision))

            last_heartbeat = monotonic()
            last_auth_check = monotonic()
            last_db_check = monotonic()

            while True:
                receive_task = asyncio.create_task(websocket.receive_text())
                revision_task = asyncio.create_task(subscription.queue.get())
                timeout = min(
                    max(0.05, _HEARTBEAT_SECONDS - (monotonic() - last_heartbeat)),
                    max(0.05, _DB_FALLBACK_CHECK_SECONDS - (monotonic() - last_db_check)),
                    max(0.05, _AUTH_RECHECK_SECONDS - (monotonic() - last_auth_check)),
                )
                done, pending = await asyncio.wait(
                    {receive_task, revision_task},
                    timeout=timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    await _cancel(task)

                if receive_task in done:
                    message = receive_task.result()
                    if message.strip().lower() == "ping":
                        await websocket.send_json(_event_payload("pong", revision))

                if revision_task in done:
                    published_revision = revision_task.result()
                    if published_revision != revision:
                        revision = published_revision
                        await websocket.send_json(
                            _event_payload("traffic_changed", revision, flows.stats())
                        )
                        last_heartbeat = monotonic()

                now = monotonic()
                if now - last_db_check >= _DB_FALLBACK_CHECK_SECONDS:
                    current_revision = flows.revision()
                    last_db_check = now
                    if current_revision != revision:
                        revision = current_revision
                        await websocket.send_json(
                            _event_payload("traffic_changed", revision, flows.stats())
                        )
                        last_heartbeat = now

                if now - last_auth_check >= _AUTH_RECHECK_SECONDS:
                    if not users.get_session_user(token, touch=False):
                        await _close(websocket, 4401, "Session expired")
                        return
                    last_auth_check = now

                if now - last_heartbeat >= _HEARTBEAT_SECONDS:
                    await websocket.send_json(_event_payload("heartbeat", revision))
                    last_heartbeat = now
        except WebSocketDisconnect:
            return
        except Exception:
            logger.exception("Traffic WebSocket failed")
            await _close(websocket, 1011, "Internal WebSocket error")
        finally:
            if subscription is not None:
                traffic_events.unsubscribe(subscription)
            conn.close()
