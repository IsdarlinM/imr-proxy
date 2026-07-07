PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL, created_at TEXT NOT NULL, config_snapshot TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS flows (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, started_at TEXT NOT NULL, method TEXT NOT NULL, url TEXT NOT NULL, host TEXT, status_code INTEGER, duration_ms REAL, highest_severity TEXT, data TEXT NOT NULL, FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS idx_flows_session ON flows(session_id);
CREATE TABLE IF NOT EXISTS findings (id INTEGER PRIMARY KEY AUTOINCREMENT, flow_id TEXT NOT NULL, session_id TEXT NOT NULL, finding_id TEXT NOT NULL, severity TEXT NOT NULL, confidence TEXT NOT NULL, title TEXT NOT NULL, data TEXT NOT NULL);
