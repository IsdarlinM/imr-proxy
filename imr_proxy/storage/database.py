from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_BUSY_TIMEOUT_MS = 30_000
_INIT_RETRIES = 8


def connect(path: Path) -> sqlite3.Connection:
    """Open a configured SQLite connection.

    Every thread/request must use its own connection.  ``check_same_thread`` is
    disabled only because FastAPI may create and close a connection in
    different worker contexts; the connection must never be shared concurrently.
    WAL is enabled by the schema bootstrap and the per-connection pragmas keep
    readers lightweight while the proxy writes traffic.
    """

    p = path.expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        p,
        timeout=_BUSY_TIMEOUT_MS / 1000,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-16384")
    return conn


@contextmanager
def connection(path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a short-lived connection and always close/rollback safely."""

    conn = connect(path)
    try:
        yield conn
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def _is_locked(exc: sqlite3.OperationalError) -> bool:
    return "locked" in str(exc).lower() or "busy" in str(exc).lower()


def _ensure_flow_columns(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the initial 0.1.8 schema.

    SQLite does not support ``ADD COLUMN IF NOT EXISTS`` on all versions we
    support, so inspect the table first. This keeps upgrades compatible with
    databases created by earlier builds.
    """

    existing = {row["name"] for row in conn.execute("PRAGMA table_info(flows)").fetchall()}
    additions = {
        "updated_at": "TEXT",
        "event_type": "TEXT NOT NULL DEFAULT 'http'",
        "state": "TEXT NOT NULL DEFAULT 'complete'",
        "error_message": "TEXT",
        "intercepted_tls": "INTEGER NOT NULL DEFAULT 0",
        "finding_count": "INTEGER NOT NULL DEFAULT 0",
        "client_address": "TEXT",
        "server_address": "TEXT",
        "scheme": "TEXT",
        "port": "INTEGER",
        "http_version": "TEXT",
        "user_agent": "TEXT",
        "content_type": "TEXT",
        "request_size": "INTEGER NOT NULL DEFAULT 0",
        "response_size": "INTEGER NOT NULL DEFAULT 0",
        "tags_json": "TEXT NOT NULL DEFAULT '[]'",
    }
    for name, definition in additions.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE flows ADD COLUMN {name} {definition}")
    conn.execute("UPDATE flows SET updated_at=COALESCE(updated_at, started_at)")
    conn.execute("UPDATE flows SET event_type=COALESCE(NULLIF(event_type,''), 'http')")
    conn.execute(
        "UPDATE flows SET state=COALESCE(NULLIF(state,''), "
        "CASE WHEN status_code IS NULL THEN 'pending' ELSE 'complete' END)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flows_event_state ON flows(event_type, state)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flows_severity ON flows(highest_severity)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flows_updated_at ON flows(updated_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flows_client_address ON flows(client_address)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flows_user_agent ON flows(user_agent)")

    rows = conn.execute(
        """
        SELECT id, data FROM flows
        WHERE client_address IS NULL OR server_address IS NULL OR http_version IS NULL
           OR user_agent IS NULL OR content_type IS NULL
        """
    ).fetchall()
    for row in rows:
        try:
            payload = json.loads(row["data"])
            request = payload.get("request") or {}
            response = payload.get("response") or {}
            request_headers = request.get("headers") or {}
            response_headers = response.get("headers") or {}
            user_agent = next(
                (str(value) for key, value in request_headers.items() if str(key).lower() == "user-agent"),
                None,
            )
            content_type = next(
                (str(value) for key, value in response_headers.items() if str(key).lower() == "content-type"),
                None,
            )
            conn.execute(
                """
                UPDATE flows SET
                    client_address=COALESCE(client_address, ?),
                    server_address=COALESCE(server_address, ?),
                    scheme=COALESCE(scheme, ?),
                    port=COALESCE(port, ?),
                    http_version=COALESCE(http_version, ?),
                    user_agent=COALESCE(user_agent, ?),
                    content_type=COALESCE(content_type, ?),
                    request_size=CASE WHEN request_size=0 THEN ? ELSE request_size END,
                    response_size=CASE WHEN response_size=0 THEN ? ELSE response_size END,
                    tags_json=CASE WHEN tags_json='[]' THEN ? ELSE tags_json END
                WHERE id=?
                """,
                (
                    payload.get("client_address") or "",
                    payload.get("server_address") or "",
                    request.get("scheme") or "",
                    request.get("port"),
                    response.get("http_version") or request.get("http_version") or "",
                    user_agent or "",
                    content_type or "",
                    int(request.get("body_size") or 0),
                    int(response.get("body_size") or 0),
                    json.dumps(payload.get("tags") or []),
                    row["id"],
                ),
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            continue

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS traffic_revision (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            revision INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO traffic_revision(id, revision, updated_at) VALUES (1, 0, CURRENT_TIMESTAMP)"
    )


def init_db(conn: sqlite3.Connection) -> None:
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    from imr_proxy.web.auth import UserRepository

    last_error: sqlite3.OperationalError | None = None
    for attempt in range(_INIT_RETRIES):
        try:
            conn.executescript(schema)
            _ensure_flow_columns(conn)
            UserRepository(conn).ensure_default_admin()
            conn.commit()
            return
        except sqlite3.OperationalError as exc:
            if not _is_locked(exc):
                raise
            if conn.in_transaction:
                conn.rollback()
            last_error = exc
            time.sleep(0.05 * (2**attempt))
    if last_error is not None:
        raise last_error
