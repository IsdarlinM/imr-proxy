from __future__ import annotations

import time
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import urlsplit

from imr_proxy.findings.engine import analyze_flow
from imr_proxy.models.flow import FlowRecord, RequestRecord, ResponseRecord
from imr_proxy.proxy.capture import decode_body, headers_to_dict
from imr_proxy.proxy.redaction import redact_cookies, redact_headers, redact_text, redact_url
from imr_proxy.proxy.scope import ScopeMatcher
from imr_proxy.proxy.tls import extract_tls_metadata


def _cookies_to_dict(obj: Any) -> dict[str, str]:
    try:
        return {str(key): str(value) for key, value in obj.items()}
    except Exception:
        return {}


def _parse_response_cookies(set_cookies: list[str]) -> dict[str, str]:
    output: dict[str, str] = {}
    for raw in set_cookies:
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
            for key, morsel in cookie.items():
                output[key] = morsel.value
        except Exception:
            pass
    return output


def _timestamp(value: Any) -> datetime:
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return datetime.now(timezone.utc)


def _address(connection: Any) -> str | None:
    if connection is None:
        return None
    for attribute in ("peername", "address", "sockname"):
        value = getattr(connection, attribute, None)
        if value:
            if isinstance(value, (list, tuple)):
                return ":".join(str(part) for part in value)
            return str(value)
    return None


class ImrProxyAddon:
    """Persist HTTP lifecycle and CONNECT/WebSocket visibility.

    Earlier builds only wrote a flow from the ``response`` hook. That omitted
    requests still in progress, failed requests, and CONNECT tunnels used by
    TLS passthrough. The portal now receives stable upserts for every lifecycle
    stage, so a request first appears as pending and is updated when complete.
    """

    def __init__(self, config, flow_repo, session_id: str, terminal=None):
        self.config = config
        self.flow_repo = flow_repo
        self.session_id = session_id
        self.terminal = terminal
        self.scope = ScopeMatcher(config.scope, config.exclude)
        self._started: dict[str, float] = {}

    @staticmethod
    def _flow_id(flow: Any, event_type: str = "http") -> str:
        return f"{event_type}:{flow.id}"

    def _request_record(self, flow: Any, *, include_body: bool) -> RequestRecord:
        request = flow.request
        original_url = getattr(request, "pretty_url", None) or getattr(request, "url", None) or ""
        safe_url = redact_url(original_url, self.config.redaction_level) or ""
        parsed = urlsplit(safe_url)
        raw = getattr(request, "raw_content", None) or b""
        body, size, is_binary = decode_body(raw, self.config.max_body_size, self.config.capture_bodies and include_body)
        return RequestRecord(
            method=str(getattr(request, "method", "REQUEST")),
            url=safe_url,
            scheme=str(getattr(request, "scheme", "") or parsed.scheme),
            host=str(getattr(request, "host", "") or parsed.hostname or ""),
            port=getattr(request, "port", None),
            path=str(getattr(request, "path", "") or parsed.path or "/"),
            query=parsed.query,
            http_version=str(getattr(request, "http_version", "") or ""),
            headers=redact_headers(headers_to_dict(getattr(request, "headers", {})), self.config.redaction_level),
            cookies=redact_cookies(_cookies_to_dict(getattr(request, "cookies", {})), self.config.redaction_level),
            body_text=redact_text(body, self.config.redaction_level),
            body_size=size,
            is_binary=is_binary,
        )

    def _response_record(self, flow: Any) -> ResponseRecord | None:
        response = getattr(flow, "response", None)
        if response is None:
            return None
        raw = getattr(response, "raw_content", None) or b""
        body, size, is_binary = decode_body(raw, self.config.max_body_size, self.config.capture_bodies)
        headers = redact_headers(headers_to_dict(getattr(response, "headers", {})), self.config.redaction_level)
        try:
            raw_set_cookies = list(response.headers.get_all("set-cookie"))
        except Exception:
            raw_set_cookies = [headers.get("set-cookie", "")] if headers.get("set-cookie") else []
        safe_set_cookies = [redact_text(value, self.config.redaction_level) or "" for value in raw_set_cookies]
        return ResponseRecord(
            status_code=getattr(response, "status_code", None),
            reason=str(getattr(response, "reason", "") or ""),
            http_version=str(getattr(response, "http_version", "") or ""),
            headers=headers,
            cookies=redact_cookies(_parse_response_cookies(safe_set_cookies), self.config.redaction_level),
            set_cookies=safe_set_cookies,
            body_text=redact_text(body, self.config.redaction_level),
            body_size=size,
            is_binary=is_binary,
        )

    def _in_scope(self, flow: Any) -> bool:
        request = getattr(flow, "request", None)
        if request is None:
            return False
        url = getattr(request, "pretty_url", None) or getattr(request, "url", None) or ""
        return self.scope.in_scope(url, getattr(request, "host", None), getattr(request, "path", None))

    def _save_http(
        self,
        flow: Any,
        *,
        state: str,
        include_body: bool,
        error_message: str | None = None,
        event_type: str = "http",
        synthetic_status: int | None = None,
        emit_terminal: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> FlowRecord | None:
        if not self._in_scope(flow):
            return None

        request = self._request_record(flow, include_body=include_body)
        response = self._response_record(flow)
        if response is None and synthetic_status is not None:
            response = ResponseRecord(status_code=synthetic_status, reason="CONNECT established")

        started_perf = self._started.get(flow.id)
        duration = (time.perf_counter() - started_perf) * 1000 if started_perf is not None else None
        request_timestamp = getattr(getattr(flow, "request", None), "timestamp_start", None)
        started_at = _timestamp(request_timestamp)
        location = None
        if getattr(flow, "response", None) is not None:
            try:
                location = flow.response.headers.get("location")
            except Exception:
                location = None

        record = FlowRecord(
            id=self._flow_id(flow, event_type),
            session_id=self.session_id,
            started_at=started_at,
            updated_at=datetime.now(timezone.utc),
            duration_ms=duration,
            event_type=event_type,
            state=state,
            error_message=redact_text(error_message, self.config.redaction_level),
            client_address=_address(getattr(flow, "client_conn", None)),
            server_address=_address(getattr(flow, "server_conn", None)),
            request=request,
            response=response,
            redirect_to=redact_url(location, self.config.redaction_level) if location else None,
            intercepted_tls=(
                not self.config.effective_tls_passthrough()
                and request.scheme.lower() in {"https", "wss"}
                and event_type != "connect"
            ),
            tls_metadata=extract_tls_metadata(flow),
            metadata=dict(metadata or {}),
        )
        if state == "complete" and event_type == "http" and response is not None:
            analyze_flow(record)
        else:
            record.tags = sorted({event_type, state})
        self.flow_repo.save(record)
        if emit_terminal and self.terminal:
            self.terminal.emit(record)
        return record

    # HTTP lifecycle -----------------------------------------------------
    def requestheaders(self, flow: Any) -> None:
        self._started.setdefault(flow.id, time.perf_counter())
        self._save_http(flow, state="pending", include_body=False)

    def request(self, flow: Any) -> None:
        self._started.setdefault(flow.id, time.perf_counter())
        self._save_http(flow, state="pending", include_body=True)

    def response(self, flow: Any) -> None:
        self._save_http(flow, state="complete", include_body=True, emit_terminal=True)
        self._started.pop(flow.id, None)

    def error(self, flow: Any) -> None:
        error = getattr(getattr(flow, "error", None), "msg", None) or str(getattr(flow, "error", "HTTP flow failed"))
        self._save_http(flow, state="error", include_body=True, error_message=error, emit_terminal=True)
        self._started.pop(flow.id, None)

    # CONNECT visibility ------------------------------------------------
    def http_connect(self, flow: Any) -> None:
        self._started.setdefault(flow.id, time.perf_counter())
        self._save_http(flow, state="pending", include_body=False, event_type="connect", emit_terminal=True)

    def http_connected(self, flow: Any) -> None:
        self._save_http(
            flow,
            state="connected",
            include_body=False,
            event_type="connect",
            synthetic_status=200,
            emit_terminal=True,
        )
        self._started.pop(flow.id, None)

    def http_connect_error(self, flow: Any) -> None:
        error = getattr(getattr(flow, "error", None), "msg", None) or "CONNECT tunnel failed"
        self._save_http(
            flow,
            state="error",
            include_body=False,
            error_message=error,
            event_type="connect",
            emit_terminal=True,
        )
        self._started.pop(flow.id, None)


    # Server connection visibility --------------------------------------
    @staticmethod
    def _server_connection_id(data: Any) -> str:
        server = getattr(data, "server", None)
        identifier = getattr(server, "id", None)
        if identifier:
            return f"connection:{identifier}"
        address = _address(server) or "unknown"
        return f"connection:{address}"

    def _save_server_connection(self, data: Any, *, state: str, error_message: str | None = None) -> FlowRecord | None:
        server = getattr(data, "server", None)
        client = getattr(data, "client", None)
        address = getattr(server, "address", None)
        host = ""
        port = None
        if isinstance(address, (tuple, list)) and address:
            host = str(address[0])
            if len(address) > 1:
                try:
                    port = int(address[1])
                except (TypeError, ValueError):
                    port = None
        elif address:
            host = str(address)
        if not host:
            return None
        scheme = "tls" if bool(getattr(server, "tls", False)) or port == 443 else "tcp"
        url = f"{scheme}://{host}{f':{port}' if port else ''}"
        if not self.scope.in_scope(url, host, "/"):
            return None
        record = FlowRecord(
            id=self._server_connection_id(data),
            session_id=self.session_id,
            started_at=_timestamp(getattr(server, "timestamp_start", None)),
            updated_at=datetime.now(timezone.utc),
            event_type="connection",
            state=state,
            error_message=redact_text(error_message, self.config.redaction_level),
            client_address=_address(client),
            server_address=_address(server),
            request=RequestRecord(
                method="TCP",
                url=redact_url(url, self.config.redaction_level) or url,
                scheme=scheme,
                host=host,
                port=port,
                path="/",
            ),
            intercepted_tls=False,
            metadata={
                "transport_protocol": str(getattr(server, "transport_protocol", "") or ""),
                "tls": bool(getattr(server, "tls", False)),
                "alpn": str(getattr(server, "alpn", "") or ""),
            },
            tags=["connection", state],
        )
        self.flow_repo.save(record)
        if self.terminal:
            self.terminal.emit(record)
        return record

    def server_connect(self, data: Any) -> None:
        self._save_server_connection(data, state="pending")

    def server_connected(self, data: Any) -> None:
        self._save_server_connection(data, state="connected")

    def server_connect_error(self, data: Any) -> None:
        server = getattr(data, "server", None)
        error = getattr(server, "error", None) or "Server connection failed"
        self._save_server_connection(data, state="error", error_message=str(error))

    def server_disconnected(self, data: Any) -> None:
        self._save_server_connection(data, state="disconnected")

    # WebSocket connection visibility ----------------------------------
    def websocket_start(self, flow: Any) -> None:
        self._save_http(
            flow,
            state="active",
            include_body=True,
            event_type="websocket",
            emit_terminal=True,
            metadata={"message_count": 0},
        )

    def websocket_message(self, flow: Any) -> None:
        websocket = getattr(flow, "websocket", None)
        messages = getattr(websocket, "messages", []) or []
        last = messages[-1] if messages else None
        content = getattr(last, "content", b"") if last is not None else b""
        self._save_http(
            flow,
            state="active",
            include_body=True,
            event_type="websocket",
            metadata={
                "message_count": len(messages),
                "last_message_size": len(content or b""),
                "last_from_client": bool(getattr(last, "from_client", False)) if last is not None else None,
            },
        )

    def websocket_end(self, flow: Any) -> None:
        websocket = getattr(flow, "websocket", None)
        messages = getattr(websocket, "messages", []) or []
        self._save_http(
            flow,
            state="closed",
            include_body=True,
            event_type="websocket",
            emit_terminal=True,
            metadata={
                "message_count": len(messages),
                "close_code": getattr(websocket, "close_code", None),
                "close_reason": redact_text(getattr(websocket, "close_reason", None), self.config.redaction_level),
            },
        )
