from __future__ import annotations

from io import StringIO

from fastapi.testclient import TestClient
from rich.console import Console

from imr_proxy.models.config import AppConfig
from imr_proxy.models.flow import FlowRecord, RequestRecord, ResponseRecord
from imr_proxy.models.session import SessionRecord
from imr_proxy.storage.database import connect, init_db
from imr_proxy.storage.repositories import FlowRepository, FlowSearch, SessionRepository
from imr_proxy.terminal.live import LivePrinter
from imr_proxy.web.server import create_app


def _flow() -> FlowRecord:
    return FlowRecord(
        id="http:compact",
        session_id="compact-session",
        event_type="http",
        state="complete",
        client_address="127.0.0.1:54321",
        server_address="140.82.121.4:443",
        duration_ms=42.5,
        intercepted_tls=True,
        request=RequestRecord(
            method="GET",
            url="https://github.com/openai/imr-proxy",
            scheme="https",
            host="github.com",
            port=443,
            http_version="HTTP/2",
            headers={"User-Agent": "curl/8.7.1", "Accept": "*/*"},
            body_size=12,
        ),
        response=ResponseRecord(
            status_code=200,
            reason="OK",
            http_version="HTTP/2",
            headers={"Content-Type": "text/html; charset=utf-8"},
            body_size=2048,
        ),
        tags=["http", "complete"],
    )


def test_compact_summary_fields_and_search(tmp_path):
    conn = connect(tmp_path / "db.sqlite3")
    init_db(conn)
    SessionRepository(conn).create(
        SessionRecord(id="compact-session", name="compact", version="0.1.82", config_snapshot={})
    )
    repo = FlowRepository(conn)
    repo.save(_flow())

    items, total = repo.search(FlowSearch(q="curl/8.7.1"))
    assert total == 1
    summary = items[0]
    assert summary["client_address"] == "127.0.0.1:54321"
    assert summary["server_address"] == "140.82.121.4:443"
    assert summary["user_agent"] == "curl/8.7.1"
    assert summary["http_version"] == "HTTP/2"
    assert summary["content_type"].startswith("text/html")
    assert summary["request_size"] == 12
    assert summary["response_size"] == 2048
    assert summary["tags"] == ["http", "complete"]
    conn.close()


def test_compact_summary_available_through_authenticated_api(tmp_path):
    storage = tmp_path / "db.sqlite3"
    conn = connect(storage)
    init_db(conn)
    SessionRepository(conn).create(
        SessionRecord(id="compact-session", name="compact", version="0.1.82", config_snapshot={})
    )
    FlowRepository(conn).save(_flow())
    conn.close()

    client = TestClient(create_app(AppConfig(storage=storage, ca_dir=tmp_path / "ca")))
    assert client.post(
        "/login",
        data={"username": "admin", "password": "admin", "next": "/"},
        follow_redirects=False,
    ).status_code == 303
    payload = client.get("/api/flows", params={"meta": "true", "q": "127.0.0.1:54321"}).json()
    assert payload["total"] == 1
    assert payload["items"][0]["user_agent"] == "curl/8.7.1"
    assert client.get("/api/flows/http%3Acompact").status_code == 200


def test_terminal_compact_log_includes_connection_details():
    output = StringIO()
    printer = LivePrinter(no_color=True)
    printer.console = Console(file=output, force_terminal=False, width=500)
    printer.emit(_flow())
    rendered = output.getvalue()
    assert "src=127.0.0.1:54321" in rendered
    assert "dst=140.82.121.4:443" in rendered
    assert 'ua="curl/8.7.1"' in rendered
    assert "proto=HTTP/2" in rendered
    assert "res=2.0KB" in rendered

    narrow = StringIO()
    printer.console = Console(file=narrow, force_terminal=False, width=100)
    printer.emit(_flow())
    assert narrow.getvalue().count("\n") == 1
