PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    config_snapshot TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS flows (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    updated_at TEXT,
    method TEXT NOT NULL,
    url TEXT NOT NULL,
    host TEXT,
    status_code INTEGER,
    duration_ms REAL,
    highest_severity TEXT,
    event_type TEXT NOT NULL DEFAULT 'http',
    state TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    intercepted_tls INTEGER NOT NULL DEFAULT 0,
    finding_count INTEGER NOT NULL DEFAULT 0,
    data TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_flows_session ON flows(session_id);
CREATE INDEX IF NOT EXISTS idx_flows_started_at ON flows(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_flows_host ON flows(host);
CREATE INDEX IF NOT EXISTS idx_flows_method ON flows(method);
CREATE INDEX IF NOT EXISTS idx_flows_status ON flows(status_code);
CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence TEXT NOT NULL,
    title TEXT NOT NULL,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT,
    created_by TEXT
);
CREATE TABLE IF NOT EXISTS web_sessions (
    token_hash TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    csrf_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen_at TEXT,
    user_agent TEXT,
    ip_address TEXT,
    FOREIGN KEY(username) REFERENCES users(username) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_web_sessions_username ON web_sessions(username);
CREATE INDEX IF NOT EXISTS idx_web_sessions_expires ON web_sessions(expires_at);
