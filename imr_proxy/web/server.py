from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from imr_proxy.proxy.certificates import load_ca_info
from imr_proxy.storage.database import connect, init_db
from imr_proxy.storage.repositories import FlowRepository, SessionRepository
from imr_proxy.version import get_version
from .api import build_api
def create_app(config):
    conn=connect(config.storage); init_db(conn); flows=FlowRepository(conn); sessions=SessionRepository(conn)
    app=FastAPI(title="imr-proxy", version=get_version())
    templates=Jinja2Templates(directory=str(Path(__file__).parent/"templates"))
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent/"static")), name="static")
    app.include_router(build_api(flows, sessions))
    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request): return templates.TemplateResponse("dashboard.html", {"request":request,"version":get_version(),"flows":flows.recent(100)})
    @app.get("/flows/{flow_id}", response_class=HTMLResponse)
    def flow_detail(request: Request, flow_id: str): return templates.TemplateResponse("flow_detail.html", {"request":request,"version":get_version(),"flow":flows.get(flow_id)})
    @app.get("/certificates", response_class=HTMLResponse)
    def certificates(request: Request):
        info=err=None
        try:
            if config.ca_dir: info=load_ca_info(config.ca_dir)
        except Exception as exc: err=str(exc)
        return templates.TemplateResponse("certificates.html", {"request":request,"version":get_version(),"info":info,"error":err})
    @app.get("/settings", response_class=HTMLResponse)
    def settings(request: Request): return templates.TemplateResponse("settings.html", {"request":request,"version":get_version(),"config":config})
    return app
def run_web(config):
    import uvicorn
    uvicorn.run(create_app(config), host=config.web_host, port=config.web_port, log_level="info" if not config.quiet else "error")
