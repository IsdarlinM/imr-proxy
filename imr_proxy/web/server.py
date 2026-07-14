from __future__ import annotations

import html
import logging
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from imr_proxy.proxy.certificates import load_ca_info
from imr_proxy.storage.database import connection, init_db
from imr_proxy.storage.repositories import FlowRepository
from imr_proxy.version import get_version

from .api import build_api
from .auth import AuthError, SESSION_COOKIE, UserRepository
from .websocket import register_traffic_websocket

logger = logging.getLogger(__name__)

PUBLIC_PATH_PREFIXES = ("/static/",)
PUBLIC_EXACT_PATHS = {"/login", "/favicon.ico"}


def _wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return request.url.path.startswith("/api/") or "application/json" in accept.lower()


def _client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


async def _read_form(request: Request) -> dict[str, str]:
    """Parse x-www-form-urlencoded bodies without adding python-multipart."""

    body = await request.body()
    parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _render_template(
    templates: Jinja2Templates,
    request: Request,
    name: str,
    context: dict[str, Any] | None = None,
):
    data = dict(context or {})
    data.setdefault("version", get_version())
    data.setdefault("user", getattr(request.state, "user", None))
    data.setdefault("csrf_token", getattr(request.state, "csrf_token", ""))
    return templates.TemplateResponse(request, name, data)


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def _database_busy_response(request: Request) -> Response:
    """Return a controlled temporary failure instead of an ASGI traceback."""

    headers = {"Retry-After": "1"}
    if _wants_json(request):
        return JSONResponse(
            {"detail": "Traffic storage is temporarily busy. Retry shortly."},
            status_code=503,
            headers=headers,
        )
    return HTMLResponse(
        "<h1>Storage temporarily busy</h1><p>Please retry in a moment.</p>",
        status_code=503,
        headers=headers,
    )


def create_app(config):
    # Bootstrap/migrate once, then close the connection. Web requests use a
    # dedicated short-lived connection instead of sharing one connection across
    # FastAPI worker threads.
    with connection(config.storage) as conn:
        init_db(conn)
        UserRepository(conn).purge_expired_sessions()

    app = FastAPI(title="imr-proxy", version=get_version())
    base_dir = Path(__file__).parent
    templates = Jinja2Templates(directory=str(base_dir / "templates"))
    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")
    app.include_router(build_api(config.storage))
    register_traffic_websocket(app, config.storage)

    @app.middleware("http")
    async def require_console_login(request: Request, call_next):
        path = request.url.path
        if path in PUBLIC_EXACT_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
            return await call_next(request)
        try:
            with connection(config.storage) as conn:
                # Authentication is intentionally read-only. Updating
                # last_seen_at on every API request previously contended with
                # proxy flow writes and caused sqlite3 "database is locked".
                session = UserRepository(conn).get_session_user(
                    request.cookies.get(SESSION_COOKIE),
                    touch=False,
                )
        except sqlite3.OperationalError as exc:
            logger.warning("SQLite busy while validating web session: %s", exc)
            return _database_busy_response(request)
        if not session:
            if _wants_json(request):
                return JSONResponse({"detail": "Authentication required"}, status_code=401)
            return _redirect(f"/login?next={html.escape(str(request.url.path))}")
        request.state.user = session
        request.state.csrf_token = session["csrf_token"]
        try:
            return await call_next(request)
        except sqlite3.OperationalError as exc:
            logger.warning("SQLite busy while serving %s: %s", request.url.path, exc)
            return _database_busy_response(request)

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, next: str = "/"):
        request.state.user = None
        return _render_template(templates, request, "login.html", {"next": next, "error": None})

    @app.post("/login")
    async def login_submit(request: Request):
        form = await _read_form(request)
        username = form.get("username", "")
        password = form.get("password", "")
        next_path = form.get("next", "/") or "/"
        if not next_path.startswith("/") or next_path.startswith("//"):
            next_path = "/"
        try:
            with connection(config.storage) as conn:
                users = UserRepository(conn)
                user = users.authenticate(username, password)
                if not user:
                    request.state.user = None
                    return _render_template(
                        templates,
                        request,
                        "login.html",
                        {"next": next_path, "error": "Invalid username or password."},
                    )
                token, _csrf = users.create_session(
                    user["username"],
                    user_agent=request.headers.get("user-agent"),
                    ip_address=_client_ip(request),
                )
        except AuthError as exc:
            request.state.user = None
            return _render_template(
                templates,
                request,
                "login.html",
                {"next": next_path, "error": str(exc)},
            )
        response = _redirect(next_path)
        response.set_cookie(
            SESSION_COOKIE,
            token,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=12 * 60 * 60,
        )
        return response

    @app.get("/logout")
    def logout(request: Request):
        with connection(config.storage) as conn:
            UserRepository(conn).delete_session(request.cookies.get(SESSION_COOKIE))
        response = _redirect("/login")
        response.delete_cookie(SESSION_COOKIE)
        return response

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        with connection(config.storage) as conn:
            flows = FlowRepository(conn)
            recent_flows = flows.recent(250)
            traffic_stats = flows.stats()
        stats = {
            "total_flows": traffic_stats["total"],
            "high_risk": traffic_stats["high_risk"],
            "pending": traffic_stats["pending"],
            "errors": traffic_stats["errors"],
            "connects": traffic_stats["connects"],
            "proxied_host": f"{config.host}:{config.port}",
            "web_host": f"{config.web_host}:{config.web_port}",
        }
        return _render_template(
            templates,
            request,
            "dashboard.html",
            {"flows": recent_flows, "config": config, "stats": stats},
        )

    @app.get("/flows/{flow_id}", response_class=HTMLResponse)
    def flow_detail(request: Request, flow_id: str):
        with connection(config.storage) as conn:
            flow = FlowRepository(conn).get(flow_id)
        return _render_template(templates, request, "flow_detail.html", {"flow": flow})

    @app.get("/certificates", response_class=HTMLResponse)
    def certificates(request: Request):
        info = None
        err = None
        try:
            if config.ca_dir:
                info = load_ca_info(config.ca_dir)
        except Exception as exc:
            err = str(exc)
        return _render_template(templates, request, "certificates.html", {"info": info, "error": err})

    @app.get("/settings", response_class=HTMLResponse)
    def settings(request: Request):
        return _render_template(templates, request, "settings.html", {"config": config})

    @app.get("/users", response_class=HTMLResponse)
    def users_page(request: Request):
        if not request.state.user["is_admin"]:
            return Response("Forbidden", status_code=403)
        with connection(config.storage) as conn:
            user_list = UserRepository(conn).list_users()
        return _render_template(
            templates,
            request,
            "users.html",
            {"users": user_list, "message": None, "error": None},
        )

    @app.post("/users/create")
    async def users_create(request: Request):
        if not request.state.user["is_admin"]:
            return Response("Forbidden", status_code=403)
        form = await _read_form(request)
        if form.get("csrf_token") != request.state.csrf_token:
            return Response("Invalid CSRF token", status_code=400)
        try:
            with connection(config.storage) as conn:
                users = UserRepository(conn)
                users.create_user(
                    form.get("username", ""),
                    form.get("password", ""),
                    is_admin=form.get("is_admin") == "on",
                    must_change_password=form.get("must_change_password") == "on",
                    created_by=request.state.user["username"],
                )
                user_list = users.list_users()
            message = f"User {form.get('username','').strip().lower()} created."
            error = None
        except AuthError as exc:
            with connection(config.storage) as conn:
                user_list = UserRepository(conn).list_users()
            message = None
            error = str(exc)
        return _render_template(
            templates,
            request,
            "users.html",
            {"users": user_list, "message": message, "error": error},
        )

    @app.post("/users/password")
    async def users_password(request: Request):
        if not request.state.user["is_admin"]:
            return Response("Forbidden", status_code=403)
        form = await _read_form(request)
        if form.get("csrf_token") != request.state.csrf_token:
            return Response("Invalid CSRF token", status_code=400)
        try:
            with connection(config.storage) as conn:
                users = UserRepository(conn)
                users.set_password(
                    form.get("username", ""),
                    form.get("password", ""),
                    must_change_password=form.get("must_change_password") == "on",
                )
                user_list = users.list_users()
            message = f"Password updated for {form.get('username','').strip().lower()}."
            error = None
        except AuthError as exc:
            with connection(config.storage) as conn:
                user_list = UserRepository(conn).list_users()
            message = None
            error = str(exc)
        return _render_template(
            templates,
            request,
            "users.html",
            {"users": user_list, "message": message, "error": error},
        )

    @app.post("/users/toggle")
    async def users_toggle(request: Request):
        if not request.state.user["is_admin"]:
            return Response("Forbidden", status_code=403)
        form = await _read_form(request)
        if form.get("csrf_token") != request.state.csrf_token:
            return Response("Invalid CSRF token", status_code=400)
        try:
            with connection(config.storage) as conn:
                users = UserRepository(conn)
                users.set_active(form.get("username", ""), form.get("active") == "1")
                user_list = users.list_users()
            message = f"User {form.get('username','')} updated."
            error = None
        except AuthError as exc:
            with connection(config.storage) as conn:
                user_list = UserRepository(conn).list_users()
            message = None
            error = str(exc)
        return _render_template(
            templates,
            request,
            "users.html",
            {"users": user_list, "message": message, "error": error},
        )

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return Response(status_code=204)

    return app


def run_web(config):
    import uvicorn

    uvicorn.run(
        create_app(config),
        host=config.web_host,
        port=config.web_port,
        log_level="info" if not config.quiet else "error",
        use_colors=False,
    )
