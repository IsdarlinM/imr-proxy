from __future__ import annotations

import json
import re
from typing import Any

from rich.console import Console
from rich.text import Text


def _header_value(headers: dict[str, Any], name: str) -> str | None:
    wanted = name.lower()
    for key, value in (headers or {}).items():
        if str(key).lower() == wanted:
            return str(value)
    return None


def _one_line(value: Any, fallback: str = "-") -> str:
    if value is None or value == "":
        return fallback
    return re.sub(r"\s+", " ", str(value)).strip() or fallback


def _size(value: int | float | None) -> str:
    numeric = float(value or 0)
    units = ("B", "KB", "MB", "GB")
    unit = units[0]
    for candidate in units:
        unit = candidate
        if numeric < 1024 or candidate == units[-1]:
            break
        numeric /= 1024
    if unit == "B":
        return f"{int(numeric)}B"
    return f"{numeric:.1f}{unit}"


class LivePrinter:
    """Render one compact, information-dense line per completed event."""

    def __init__(self, no_color: bool = False, jsonl: bool = False):
        self.console = Console(no_color=no_color)
        self.jsonl = jsonl

    def emit(self, flow) -> None:
        if self.jsonl:
            self.console.print_json(json.dumps(flow.model_dump(mode="json")))
            return

        response = flow.response
        request = flow.request
        status = str(response.status_code) if response and response.status_code is not None else "-"
        response_size = response.body_size if response else 0
        duration = f"{flow.duration_ms:.1f}ms" if flow.duration_ms is not None else "-"
        severity = flow.highest_severity()
        source = _one_line(flow.client_address)
        destination = _one_line(flow.server_address)
        if destination == "-":
            destination = request.host or "-"
            if request.port:
                destination = f"{destination}:{request.port}"
        protocol = (
            (response.http_version if response else None)
            or request.http_version
            or flow.metadata.get("alpn")
            or flow.metadata.get("transport_protocol")
            or request.scheme
            or "-"
        )
        user_agent = _header_value(request.headers, "user-agent") or "-"
        content_type = _header_value(response.headers, "content-type") if response else None
        redirect = f" redirect={_one_line(flow.redirect_to)}" if flow.redirect_to else ""
        error = f" error={_one_line(flow.error_message)}" if flow.error_message else ""
        tags = ",".join(flow.tags[:4]) if flow.tags else "-"

        severity_style = {
            "critical": "bold white on red",
            "high": "bold red",
            "medium": "yellow",
            "low": "cyan",
            "info": "dim",
        }.get(severity, "dim")
        event_style = {
            "error": "bold red",
            "pending": "yellow",
            "connected": "green",
            "complete": "green",
            "active": "cyan",
        }.get(flow.state, "cyan")

        line = Text(no_wrap=True, overflow="ellipsis")
        line.append(flow.updated_at.strftime("%H:%M:%S.%f")[:-3], style="dim")
        line.append(" ")
        line.append(f"{flow.event_type.upper()}/{flow.state.upper():<12}", style=event_style)
        line.append(" ")
        line.append(f"{request.method:<7}", style="bold")
        line.append(f" {status:>3} ")
        line.append(_one_line(request.url), style="bright_white")
        line.append(f" src={source}", style="dim")
        line.append(f" dst={destination}", style="dim")
        line.append(f" proto={_one_line(protocol)}", style="dim")
        line.append(f" ua=\"{_one_line(user_agent)}\"", style="dim")
        line.append(f" req={_size(request.body_size)} res={_size(response_size)} dur={duration}", style="dim")
        if content_type:
            line.append(f" type={_one_line(content_type)}", style="dim")
        line.append(f" findings={len(flow.findings)} tags={tags} ", style="dim")
        line.append(severity, style=severity_style)
        line.append(redirect + error, style="red" if error else "dim")
        line.truncate(max(20, self.console.width - 1), overflow="ellipsis")
        self.console.print(line, soft_wrap=False)
