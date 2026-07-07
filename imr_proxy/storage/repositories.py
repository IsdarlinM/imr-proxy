import json, sqlite3
from typing import Any
from imr_proxy.models.flow import FlowRecord
from imr_proxy.models.session import SessionRecord
def _dump(data: Any)->str:
    try:
        import orjson; return orjson.dumps(data, option=orjson.OPT_NAIVE_UTC).decode()
    except Exception: return json.dumps(data, default=str, ensure_ascii=False)
class SessionRepository:
    def __init__(self, conn: sqlite3.Connection): self.conn=conn
    def create(self, s: SessionRecord)->None:
        self.conn.execute("INSERT OR REPLACE INTO sessions(id,name,version,created_at,config_snapshot) VALUES (?,?,?,?,?)",(s.id,s.name,s.version,s.created_at.isoformat(),_dump(s.config_snapshot))); self.conn.commit()
    def latest_id(self)->str|None:
        r=self.conn.execute("SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1").fetchone(); return r["id"] if r else None
    def list(self)->list[dict[str,Any]]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()]
class FlowRepository:
    def __init__(self, conn: sqlite3.Connection): self.conn=conn
    def save(self, f: FlowRecord)->None:
        self.conn.execute("INSERT OR REPLACE INTO flows(id,session_id,started_at,method,url,host,status_code,duration_ms,highest_severity,data) VALUES (?,?,?,?,?,?,?,?,?,?)",(f.id,f.session_id,f.started_at.isoformat(),f.request.method,f.request.url,f.request.host,f.response.status_code if f.response else None,f.duration_ms,f.highest_severity(),_dump(f.model_dump(mode='json'))))
        self.conn.execute("DELETE FROM findings WHERE flow_id=?",(f.id,))
        for x in f.findings:
            self.conn.execute("INSERT INTO findings(flow_id,session_id,finding_id,severity,confidence,title,data) VALUES (?,?,?,?,?,?,?)",(f.id,f.session_id,x.id,x.severity,x.confidence,x.title,_dump(x.model_dump(mode='json'))))
        self.conn.commit()
    def list_by_session(self, session_id: str, limit: int|None=None)->list[FlowRecord]:
        sql="SELECT data FROM flows WHERE session_id=? ORDER BY started_at ASC"; params=(session_id,)
        if limit: sql+=" LIMIT ?"; params=(session_id, limit)
        return [FlowRecord.model_validate(json.loads(r["data"])) for r in self.conn.execute(sql,params).fetchall()]
    def get(self, flow_id: str)->FlowRecord|None:
        r=self.conn.execute("SELECT data FROM flows WHERE id=?",(flow_id,)).fetchone(); return FlowRecord.model_validate(json.loads(r["data"])) if r else None
    def recent(self, limit: int=100)->list[dict[str,Any]]:
        return [dict(r) for r in self.conn.execute("SELECT id,session_id,started_at,method,url,host,status_code,duration_ms,highest_severity FROM flows ORDER BY started_at DESC LIMIT ?",(limit,)).fetchall()]
