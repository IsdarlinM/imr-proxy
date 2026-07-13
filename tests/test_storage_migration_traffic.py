import sqlite3

from imr_proxy.storage.database import connect, init_db


def test_existing_legacy_flow_table_is_migrated(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    raw = sqlite3.connect(path)
    raw.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL, created_at TEXT NOT NULL, config_snapshot TEXT NOT NULL)")
    raw.execute("CREATE TABLE flows (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, started_at TEXT NOT NULL, method TEXT NOT NULL, url TEXT NOT NULL, host TEXT, status_code INTEGER, duration_ms REAL, highest_severity TEXT, data TEXT NOT NULL)")
    raw.commit()
    raw.close()

    conn = connect(path)
    init_db(conn)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(flows)").fetchall()}
    assert {"updated_at", "event_type", "state", "error_message", "intercepted_tls", "finding_count"}.issubset(columns)
    conn.close()
