import asyncio, logging, threading, uuid
from pathlib import Path
from imr_proxy.models.config import AppConfig
from imr_proxy.models.session import SessionRecord
from imr_proxy.proxy.addons import ImrProxyAddon
from imr_proxy.proxy.certificates import ca_paths, init_ca
from imr_proxy.storage.database import connect, init_db
from imr_proxy.storage.repositories import FlowRepository, SessionRepository
from imr_proxy.terminal.live import LivePrinter
from imr_proxy.version import get_version
log=logging.getLogger(__name__)

def _mitmproxy_options_kwargs(config: AppConfig, ca_dir: Path|None)->dict[str, object]:
    """Build constructor kwargs for mitmproxy Options.

    mitmproxy 11+ type-checks option values at construction time.
    The ``confdir`` option must be a string when supplied; passing
    ``None`` raises ``TypeError``. In TLS passthrough/default mode we do
    not need a custom CA directory, so the option must be omitted entirely.
    """
    kwargs: dict[str, object]={"listen_host": config.host, "listen_port": config.port}
    if ca_dir is not None:
        kwargs["confdir"]=str(ca_dir)
    return kwargs

def ensure_ca_for_interception(config: AppConfig)->Path|None:
    if not config.intercept_https or config.cert_mode=="passthrough": return None
    ca_dir=(config.ca_dir or Path.home()/".imr-proxy"/"ca").expanduser()
    if not ca_paths(ca_dir).mitmproxy_combined.exists():
        log.warning("Local CA not found; generating one. Install exported public CA manually.")
        init_ca(ca_dir)
    return ca_dir
async def _run_mitmproxy(config, flow_repo, session_id, terminal):
    try:
        from mitmproxy.options import Options
        from mitmproxy.tools.dump import DumpMaster
    except Exception as exc:
        raise RuntimeError("mitmproxy is required. Install with `python -m pip install -e .`.") from exc
    mode=[f"upstream:{config.upstream_proxy}"] if config.upstream_proxy else ["regular"]
    ca_dir=ensure_ca_for_interception(config)
    option_kwargs=_mitmproxy_options_kwargs(config, ca_dir)
    opts=Options(**option_kwargs)
    update={"mode":mode,"http2":True,"ssl_insecure":False}
    if config.effective_tls_passthrough(): update["ignore_hosts"]=[".*"]
    if config.proxy_auth: update["proxyauth"]=config.proxy_auth
    opts.update(**update)
    master=DumpMaster(opts, with_termlog=False, with_dumper=False)
    master.addons.add(ImrProxyAddon(config, flow_repo, session_id, terminal))
    log.info("Proxy listening on %s:%s", config.host, config.port)
    log.info("Use %s:%s as the browser/system HTTP(S) proxy; open the Web UI at http://%s:%s", config.host, config.port, config.web_host, config.web_port)
    try: await master.run()
    finally: master.shutdown()
def run_proxy(config: AppConfig)->None:
    conn=connect(config.storage); init_db(conn)
    session=SessionRecord(id=uuid.uuid4().hex, name=config.session_name, version=get_version(), config_snapshot=config.model_dump(mode="json"))
    SessionRepository(conn).create(session)
    terminal=LivePrinter(config.no_color, config.jsonl) if config.terminal else None
    asyncio.run(_run_mitmproxy(config, FlowRepository(conn), session.id, terminal))
def run_proxy_in_thread(config: AppConfig)->threading.Thread:
    t=threading.Thread(target=run_proxy,args=(config,),daemon=True); t.start(); return t
