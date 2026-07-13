import sqlite3
import time
from pathlib import Path


_BUSY_TIMEOUT_MS = 30_000
_INIT_RETRIES = 8


def connect(path: Path) -> sqlite3.Connection:
    p = path.expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, timeout=_BUSY_TIMEOUT_MS / 1000, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _is_locked(exc: sqlite3.OperationalError) -> bool:
    return "locked" in str(exc).lower() or "busy" in str(exc).lower()



def _ensure_flow_columns(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the initial 0.1.8 schema.

    SQLite does not support ``ADD COLUMN IF NOT EXISTS`` on all versions we
    support, so inspect the table first. This keeps upgrades compatible with
    databases created by earlier 0.1.8 builds.
    """
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(flows)").fetchall()}
    additions = {
        "updated_at": "TEXT",
        "event_type": "TEXT NOT NULL DEFAULT 'http'",
        "state": "TEXT NOT NULL DEFAULT 'complete'",
        "error_message": "TEXT",
        "intercepted_tls": "INTEGER NOT NULL DEFAULT 0",
        "finding_count": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, definition in additions.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE flows ADD COLUMN {name} {definition}")
    conn.execute("UPDATE flows SET updated_at=COALESCE(updated_at, started_at)")
    conn.execute("UPDATE flows SET event_type=COALESCE(NULLIF(event_type,''), 'http')")
    conn.execute("UPDATE flows SET state=COALESCE(NULLIF(state,''), CASE WHEN status_code IS NULL THEN 'pending' ELSE 'complete' END)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flows_event_state ON flows(event_type, state)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flows_severity ON flows(highest_severity)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flows_updated_at ON flows(updated_at DESC)")


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
            last_error = exc
            time.sleep(0.05 * (2**attempt))
    if last_error is not None:
        raise last_error
