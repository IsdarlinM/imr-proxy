import json, logging
from pathlib import Path
from typing import Annotated, Optional
import typer
from rich.console import Console
from imr_proxy.app import maybe_first_run_prompt, print_banner, security_warnings, start_web_thread, validate_bind
from imr_proxy.config import build_config, default_ca_dir, default_config_path, write_default_config
from imr_proxy.logging import setup_logging
from imr_proxy.proxy.certificates import export_ca, init_ca, load_ca_info, rotate_ca, sign_host_certificate
from imr_proxy.proxy.engine import run_proxy
from imr_proxy.reporting.exporters import export_flows
from imr_proxy.storage.database import connect, init_db
from imr_proxy.storage.repositories import FlowRepository, SessionRepository
from imr_proxy.terminal.tables import sessions_table
from imr_proxy.version import get_version
app=typer.Typer(invoke_without_command=True, no_args_is_help=True, help="imr-proxy defensive HTTP/HTTPS inspection proxy")
ca_app=typer.Typer(help="Local CA lifecycle commands"); config_app=typer.Typer(help="Configuration commands"); sessions_app=typer.Typer(help="Session commands"); rules_app=typer.Typer(help="Rule testing commands")
app.add_typer(ca_app,name="ca"); app.add_typer(config_app,name="config"); app.add_typer(sessions_app,name="sessions"); app.add_typer(rules_app,name="rules")
console=Console()
@app.callback()
def callback(version: Annotated[bool, typer.Option("--version", help="Show version and exit.")]=False):
    if version: typer.echo(get_version()); raise typer.Exit()
def _read_patterns(values, file):
    items=list(values or [])
    if file: items += [x.strip() for x in file.read_text(encoding="utf-8").splitlines() if x.strip() and not x.strip().startswith("#")]
    return items
@app.command()
def start(host: Annotated[Optional[str], typer.Option("--host")]=None, port: Annotated[Optional[int], typer.Option("--port")]=None, web: Annotated[Optional[bool], typer.Option("--web/--no-web")]=None, web_host: Annotated[Optional[str], typer.Option("--web-host")]=None, web_port: Annotated[Optional[int], typer.Option("--web-port")]=None, terminal: Annotated[bool, typer.Option("--terminal")]=False, quiet: Annotated[bool, typer.Option("--quiet")]=False, verbose: Annotated[bool, typer.Option("--verbose")]=False, allow_remote: Annotated[bool, typer.Option("--allow-remote")]=False, scope: Annotated[Optional[list[str]], typer.Option("--scope")]=None, scope_file: Annotated[Optional[Path], typer.Option("--scope-file")]=None, exclude: Annotated[Optional[list[str]], typer.Option("--exclude")]=None, exclude_file: Annotated[Optional[Path], typer.Option("--exclude-file")]=None, upstream_proxy: Annotated[Optional[str], typer.Option("--upstream-proxy")]=None, proxy_auth: Annotated[Optional[str], typer.Option("--proxy-auth")]=None, intercept_https: Annotated[bool, typer.Option("--intercept-https")]=False, tls_passthrough: Annotated[bool, typer.Option("--tls-passthrough")]=False, ca_dir: Annotated[Optional[Path], typer.Option("--ca-dir")]=None, cert_mode: Annotated[Optional[str], typer.Option("--cert-mode")]=None, storage: Annotated[Optional[Path], typer.Option("--storage")]=None, session_name: Annotated[Optional[str], typer.Option("--session-name")]=None, max_body_size: Annotated[Optional[int], typer.Option("--max-body-size")]=None, capture_bodies: Annotated[Optional[bool], typer.Option("--capture-bodies/--no-capture-bodies")]=None, redaction_level: Annotated[Optional[str], typer.Option("--redaction-level")]=None, export_json: Annotated[Optional[Path], typer.Option("--export-json")]=None, export_har: Annotated[Optional[Path], typer.Option("--export-har")]=None, export_html: Annotated[Optional[Path], typer.Option("--export-html")]=None, config: Annotated[Optional[Path], typer.Option("--config")]=None, no_color: Annotated[bool, typer.Option("--no-color")]=False, jsonl: Annotated[bool, typer.Option("--jsonl")]=False):
    overrides={"host":host,"port":port,"web":web,"web_host":web_host,"web_port":web_port,"terminal":terminal or None,"quiet":quiet or None,"verbose":verbose or None,"allow_remote":allow_remote or None,"scope":_read_patterns(scope,scope_file) if (scope or scope_file) else None,"exclude":_read_patterns(exclude,exclude_file) if (exclude or exclude_file) else None,"upstream_proxy":upstream_proxy,"proxy_auth":proxy_auth,"intercept_https":intercept_https or None,"tls_passthrough":tls_passthrough or (False if intercept_https else None),"ca_dir":ca_dir,"cert_mode":cert_mode or ("local-ca" if intercept_https else None),"storage":storage,"session_name":session_name,"max_body_size":max_body_size,"capture_bodies":capture_bodies,"redaction_level":redaction_level,"no_color":no_color or None,"jsonl":jsonl or None,"config":config}
    cfg=build_config(config, overrides); setup_logging(cfg.verbose,cfg.quiet,cfg.no_color); cfg=maybe_first_run_prompt(cfg); validate_bind(cfg); print_banner(cfg); security_warnings(cfg); start_web_thread(cfg)
    if export_json or export_har or export_html: logging.getLogger(__name__).info("Use sessions export after capture.")
    try: run_proxy(cfg)
    except KeyboardInterrupt: console.print("\n[cyan]imr-proxy stopped.[/cyan]")
@ca_app.command("init")
def ca_init(ca_dir: Annotated[Path, typer.Option("--ca-dir")]=default_ca_dir(), force: Annotated[bool, typer.Option("--force")]=False):
    p=init_ca(ca_dir, force=force); console.print(f"[green]Created local CA:[/green] {p.ca_dir}")
@ca_app.command("export")
def ca_export(ca_dir: Annotated[Path, typer.Option("--ca-dir")]=default_ca_dir(), fmt: Annotated[str, typer.Option("--format")]="pem", output: Annotated[Path, typer.Option("--output")]=Path("imr-proxy-ca.pem")):
    console.print(f"[green]Exported public CA certificate:[/green] {export_ca(ca_dir,output,fmt)}")
@ca_app.command("rotate")
def ca_rotate(ca_dir: Annotated[Path, typer.Option("--ca-dir")]=default_ca_dir()):
    p=rotate_ca(ca_dir); console.print(f"[yellow]Rotated CA.[/yellow] New CA directory: {p.ca_dir}")
@ca_app.command("info")
def ca_info(ca_dir: Annotated[Path, typer.Option("--ca-dir")]=default_ca_dir()): console.print_json(json.dumps(load_ca_info(ca_dir)))
@ca_app.command("leaf")
def ca_leaf(hostname: str, ca_dir: Annotated[Path, typer.Option("--ca-dir")]=default_ca_dir(), output_dir: Annotated[Optional[Path], typer.Option("--output-dir")]=None):
    cert,key=sign_host_certificate(ca_dir,hostname,output_dir); console.print(f"Certificate: {cert}\nKey: {key}")
@config_app.command("init")
def config_init(path: Annotated[Optional[Path], typer.Option("--path")]=None, force: Annotated[bool, typer.Option("--force")]=False): console.print(f"[green]Wrote config:[/green] {write_default_config(path,force)}")
@config_app.command("show")
def config_show(path: Annotated[Optional[Path], typer.Option("--config")]=None):
    cfg=build_config(path); console.print_json(cfg.model_dump_json(indent=2)); console.print(f"Default config path: {default_config_path()}")
def _repos(storage: Optional[Path]):
    cfg=build_config(overrides={"storage":storage} if storage else None); conn=connect(cfg.storage); init_db(conn); return SessionRepository(conn), FlowRepository(conn)
@sessions_app.command("list")
def sessions_list(storage: Annotated[Optional[Path], typer.Option("--storage")]=None):
    s,_=_repos(storage); console.print(sessions_table(s.list()))
@sessions_app.command("export")
def sessions_export(session: Annotated[str, typer.Option("--session")]="latest", fmt: Annotated[str, typer.Option("--format")]="json", output: Annotated[Path, typer.Option("--output")]=Path("imr-proxy-export.json"), storage: Annotated[Optional[Path], typer.Option("--storage")]=None):
    s,f=_repos(storage); sid=s.latest_id() if session=="latest" else session
    if not sid: raise typer.BadParameter("No session found")
    console.print(f"[green]Exported:[/green] {export_flows(f.list_by_session(sid),fmt,output)}")
@app.command()
def report(session: Annotated[str, typer.Option("--session")]="latest", fmt: Annotated[str, typer.Option("--format")]="html", output: Annotated[Path, typer.Option("--output")]=Path("imr-proxy-report.html"), storage: Annotated[Optional[Path], typer.Option("--storage")]=None):
    s,f=_repos(storage); sid=s.latest_id() if session=="latest" else session
    if not sid: raise typer.BadParameter("No session found")
    console.print(f"[green]Report written:[/green] {export_flows(f.list_by_session(sid),fmt,output)}")
@app.command()
def replay(flow_id: str, allow_unsafe: Annotated[bool, typer.Option("--allow-unsafe")]=False, storage: Annotated[Optional[Path], typer.Option("--storage")]=None):
    _,fr=_repos(storage); flow=fr.get(flow_id)
    if not flow: raise typer.BadParameter("Flow not found")
    from imr_proxy.proxy.replay import replay_flow
    r=replay_flow(flow,allow_unsafe=allow_unsafe); console.print(f"{r.status_code} {r.reason_phrase} {len(r.content)} bytes")
@rules_app.command("test")
def rules_test(url: str, scope: Annotated[Optional[list[str]], typer.Option("--scope")]=None, exclude: Annotated[Optional[list[str]], typer.Option("--exclude")]=None):
    from imr_proxy.proxy.scope import ScopeMatcher
    console.print_json(json.dumps({"url":url,"in_scope":ScopeMatcher(scope or [], exclude or []).in_scope(url)}))
def main(): app()
