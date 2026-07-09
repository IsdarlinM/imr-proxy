import json
from rich.console import Console
class LivePrinter:
    def __init__(self, no_color: bool=False, jsonl: bool=False): self.console=Console(no_color=no_color); self.jsonl=jsonl
    def emit(self, flow):
        if self.jsonl: self.console.print_json(json.dumps(flow.model_dump(mode="json"))); return
        status=flow.response.status_code if flow.response else "-"
        size=flow.response.body_size if flow.response else 0
        dur=f"{flow.duration_ms:.1f}ms" if flow.duration_ms is not None else "-"
        sev=flow.highest_severity(); redir=" ↪" if flow.redirect_to else ""
        self.console.print(f"[{flow.started_at.strftime('%H:%M:%S')}] [bold]{flow.request.method}[/bold] {flow.request.url} -> {status} {size}B {dur}{redir} findings={len(flow.findings)} [{sev}]{sev}[/{sev}]")
