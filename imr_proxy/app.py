import logging
import sys
import threading

from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt

from imr_proxy.constants import BANNER, LOCALHOSTS
from imr_proxy.version import get_version
from imr_proxy.web.server import run_web

log = logging.getLogger(__name__)


class BindValidationError(ValueError):
    """Raised when imr-proxy would bind to a remote-facing interface unsafely."""


def print_banner(config):
    if not config.quiet:
        Console(no_color=config.no_color).print(f"[cyan]{BANNER.format(version=get_version())}[/cyan]")


def validate_bind(config):
    if config.host not in LOCALHOSTS and not config.allow_remote:
        raise BindValidationError(
            f"Refusing proxy bind to {config.host!r}. Use --allow-remote only when you intentionally "
            "want imr-proxy reachable from other devices. Example: "
            f"imr-proxy start --host {config.host} --port {config.port} --allow-remote"
        )
    if config.web_host not in LOCALHOSTS and not config.allow_remote:
        raise BindValidationError(
            f"Refusing Web UI bind to {config.web_host!r}. Use --allow-remote only when you intentionally "
            "want the console reachable from other devices. Example: "
            f"imr-proxy start --web-host {config.web_host} --web-port {config.web_port} --allow-remote"
        )


def security_warnings(config):
    c = Console(no_color=config.no_color)
    if config.allow_remote:
        c.print(
            "[bold yellow]Warning:[/bold yellow] Remote binding is enabled. "
            "Restrict access with firewall rules and strong web-console credentials."
        )
    if config.intercept_https and config.cert_mode != "passthrough":
        c.print(
            "[bold yellow]Warning:[/bold yellow] HTTPS interception is enabled for authorized "
            "local testing only. Install CA manually."
        )
    if config.redaction_level == "off":
        c.print("[bold red]Warning:[/bold red] Redaction is OFF.")


def maybe_first_run_prompt(config):
    if not sys.stdin.isatty() or config.config is not None:
        return config
    if Confirm.ask("Use current imr-proxy startup settings?", default=True):
        return config
    host = Prompt.ask("Proxy listen IP", default=config.host)
    port = IntPrompt.ask("Proxy listen port", default=config.port)
    intercept = Confirm.ask("Enable HTTPS interception?", default=config.intercept_https)
    terminal = Confirm.ask("Enable terminal output?", default=config.terminal)
    red = Prompt.ask("Redaction level", choices=["strict", "balanced", "off"], default=config.redaction_level)
    return config.model_copy(
        update={
            "host": host,
            "port": port,
            "intercept_https": intercept,
            "tls_passthrough": not intercept,
            "cert_mode": "local-ca" if intercept else "passthrough",
            "terminal": terminal,
            "redaction_level": red,
        }
    )


def start_web_thread(config):
    if not config.web:
        return None
    t = threading.Thread(target=run_web, args=(config,), daemon=True)
    t.start()
    log.info("Web UI listening on http://%s:%s", config.web_host, config.web_port)
    return t
