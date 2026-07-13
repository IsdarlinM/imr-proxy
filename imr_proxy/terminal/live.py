import json

from rich.console import Console


class LivePrinter:
    def __init__(self, no_color: bool = False, jsonl: bool = False):
        self.console = Console(no_color=no_color)
        self.jsonl = jsonl

    def emit(self, flow):
        if self.jsonl:
            self.console.print_json(json.dumps(flow.model_dump(mode="json")))
            return

        status = flow.response.status_code if flow.response else "-"
        size = flow.response.body_size if flow.response else 0
        duration = f"{flow.duration_ms:.1f}ms" if flow.duration_ms is not None else "-"
        severity = flow.highest_severity()
        style = {
            "critical": "bold white on red",
            "high": "bold red",
            "medium": "yellow",
            "low": "cyan",
            "info": "dim",
        }.get(severity, "dim")
        redirect = " ↪" if flow.redirect_to else ""
        event = flow.event_type.upper()
        state = flow.state.upper()
        error = f" error={flow.error_message}" if flow.error_message else ""
        self.console.print(
            f"[{flow.started_at.strftime('%H:%M:%S')}] "
            f"[bold]{event}/{state}[/bold] [bold]{flow.request.method}[/bold] "
            f"{flow.request.url} -> {status} {size}B {duration}{redirect} "
            f"findings={len(flow.findings)} [{style}]{severity}[/{style}]{error}"
        )
