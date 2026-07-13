from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from imr_proxy.storage.repositories import FlowSearch


def build_api(flow_repo, session_repo, user_repo=None):
    router = APIRouter(prefix="/api")

    @router.get("/sessions")
    def sessions():
        return session_repo.list()

    @router.get("/flows")
    def flows(
        q: str | None = None,
        host: str | None = None,
        method: str | None = None,
        status: int | None = None,
        status_class: str | None = None,
        severity: str | None = None,
        event_type: str | None = None,
        state: str | None = None,
        tls: str | None = None,
        has_findings: bool | None = None,
        session_id: str | None = None,
        min_duration: float | None = Query(default=None, ge=0),
        max_duration: float | None = Query(default=None, ge=0),
        since: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int = Query(default=250, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        order: str = Query(default="desc", pattern="^(asc|desc)$"),
        meta: bool = False,
    ):
        search = FlowSearch(
            q=q,
            host=host,
            method=method,
            status=status,
            status_class=status_class,
            severity=severity,
            event_type=event_type,
            state=state,
            tls=tls,
            has_findings=has_findings,
            session_id=session_id,
            min_duration=min_duration,
            max_duration=max_duration,
            since=since,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
            offset=offset,
            order=order,
        )
        items, total = flow_repo.search(search)
        if not meta:
            return items
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @router.get("/flows/options")
    def flow_options():
        return flow_repo.filter_options()

    @router.get("/traffic/stats")
    def traffic_stats():
        return flow_repo.stats()

    @router.get("/flows/{flow_id}")
    def flow_detail(flow_id: str):
        flow = flow_repo.get(flow_id)
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")
        return flow.model_dump(mode="json")

    @router.get("/users")
    def users(request: Request):
        if not user_repo:
            raise HTTPException(status_code=404, detail="User repository unavailable")
        current = getattr(request.state, "user", None)
        if not current or not current.get("is_admin"):
            raise HTTPException(status_code=403, detail="Administrator required")
        return user_repo.list_users()

    return router
