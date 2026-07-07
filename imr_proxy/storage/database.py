import sqlite3
from pathlib import Path
def connect(path: Path)->sqlite3.Connection:
    p=path.expanduser().resolve(); p.parent.mkdir(parents=True, exist_ok=True)
    conn=sqlite3.connect(p, check_same_thread=False); conn.row_factory=sqlite3.Row; conn.execute("PRAGMA foreign_keys=ON"); return conn
def init_db(conn: sqlite3.Connection)->None:
    conn.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")); conn.commit()
