from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from imr_proxy.proxy.certificates import load_ca_info
from imr_proxy.storage.database import connect, init_db
from imr_proxy.storage.repositories import FlowRepository, SessionRepository
from imr_proxy.version import get_version

from .api import build_api


def _render_template(templates: Jinja2Templates, request: Request, name: str, context: dict):
    """Render a template using the Starlette/FastAPI-compatible call style.

    Newer Starlette versions expect ``TemplateResponse(request, name, context)``.
    Passing the old positional order (``name, context``) makes Starlette treat the
    context dictionary as the template name, which raises ``TypeError: unhashable
    type: 'dict'`` inside Jinja2's template cache.
    """
    return templates.TemplateResponse(request, name, context)


def create_app(config):
    conn = connect(config.storage)
    init_db(conn)
    flows = FlowRepository(conn)
    sessions = SessionRepository(conn)

    app = FastAPI(title="imr-proxy", version=get_version())
    base_dir = Path(__file__).parent
    templates = Jinja2Templates(directory=str(base_dir / "templates"))
    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")
    app.include_router(build_api(flows, sessions))

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        return _render_template(
            templates,
            request,
            "dashboard.html",
            {"version": get_version(), "flows": flows.recent(100), "config": config},
        )

    @app.get("/flows/{flow_id}", response_class=HTMLResponse)
    def flow_detail(request: Request, flow_id: str):
        return _render_template(
            templates,
            request,
            "flow_detail.html",
            {"version": get_version(), "flow": flows.get(flow_id)},
        )

    @app.get("/certificates", response_class=HTMLResponse)
    def certificates(request: Request):
        info = None
        err = None
        try:
            if config.ca_dir:
                info = load_ca_info(config.ca_dir)
        except Exception as exc:
            err = str(exc)
        return _render_template(
            templates,
            request,
            "certificates.html",
            {"version": get_version(), "info": info, "error": err},
        )

    @app.get("/settings", response_class=HTMLResponse)
    def settings(request: Request):
        return _render_template(
            templates,
            request,
            "settings.html",
            {"version": get_version(), "config": config},
        )

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return Response(status_code=204)

    return app


def run_web(config):
    import uvicorn

    # Disable uvicorn ANSI colors to avoid raw escape sequences on Windows CMD/PowerShell.
    uvicorn.run(
        create_app(config),
        host=config.web_host,
        port=config.web_port,
        log_level="info" if not config.quiet else "error",
        use_colors=False,
    )
