from fastapi import APIRouter, HTTPException
def build_api(flow_repo, session_repo):
    r=APIRouter(prefix="/api")
    @r.get("/sessions")
    def sessions(): return session_repo.list()
    @r.get("/flows")
    def flows(limit:int=100): return flow_repo.recent(limit)
    @r.get("/flows/{flow_id}")
    def flow_detail(flow_id: str):
        f=flow_repo.get(flow_id)
        if not f: raise HTTPException(status_code=404, detail="Flow not found")
        return f.model_dump(mode="json")
    return r
