from fastapi import APIRouter, HTTPException, Request


def build_api(flow_repo, session_repo, user_repo=None):
    r = APIRouter(prefix="/api")

    @r.get("/sessions")
    def sessions():
        return session_repo.list()

    @r.get("/flows")
    def flows(limit: int = 100):
        return flow_repo.recent(limit)

    @r.get("/flows/{flow_id}")
    def flow_detail(flow_id: str):
        f = flow_repo.get(flow_id)
        if not f:
            raise HTTPException(status_code=404, detail="Flow not found")
        return f.model_dump(mode="json")

    @r.get("/users")
    def users(request: Request):
        if not user_repo:
            raise HTTPException(status_code=404, detail="User repository unavailable")
        current = getattr(request.state, "user", None)
        if not current or not current.get("is_admin"):
            raise HTTPException(status_code=403, detail="Administrator required")
        return user_repo.list_users()

    return r
