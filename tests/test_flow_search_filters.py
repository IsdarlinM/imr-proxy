from fastapi.testclient import TestClient

from imr_proxy.models.config import AppConfig
from imr_proxy.models.finding import Finding
from imr_proxy.models.flow import FlowRecord, RequestRecord, ResponseRecord
from imr_proxy.models.session import SessionRecord
from imr_proxy.storage.database import connect, init_db
from imr_proxy.storage.repositories import FlowRepository, FlowSearch, SessionRepository
from imr_proxy.web.server import create_app


def seed(path):
    conn = connect(path)
    init_db(conn)
    SessionRepository(conn).create(SessionRecord(id="s1", name="test", version="0.1.8", config_snapshot={}))
    repo = FlowRepository(conn)
    repo.save(FlowRecord(
        id="connect:g",
        session_id="s1",
        event_type="connect",
        state="connected",
        request=RequestRecord(method="CONNECT", url="https://github.com:443/", scheme="https", host="github.com", port=443),
        response=ResponseRecord(status_code=200),
        duration_ms=14.2,
    ))
    repo.save(FlowRecord(
        id="http:e",
        session_id="s1",
        event_type="http",
        state="complete",
        intercepted_tls=True,
        request=RequestRecord(method="GET", url="https://example.test/api", scheme="https", host="example.test", port=443),
        response=ResponseRecord(status_code=500),
        duration_ms=250.0,
        findings=[Finding(id="TEST", title="Test finding", severity="high", confidence="high")],
    ))
    return conn, repo


def test_repository_advanced_filters(tmp_path):
    conn, repo = seed(tmp_path / "db.sqlite3")
    items, total = repo.search(FlowSearch(host="github", event_type="connect"))
    assert total == 1
    assert items[0]["id"] == "connect:g"

    items, total = repo.search(FlowSearch(status_class="5xx", severity="high", has_findings=True, min_duration=200))
    assert total == 1
    assert items[0]["id"] == "http:e"

    items, total = repo.search(FlowSearch(tls="intercepted"))
    assert total == 1
    assert items[0]["id"] == "http:e"
    conn.close()


def test_filtered_api_and_options(tmp_path):
    storage = tmp_path / "db.sqlite3"
    conn, _repo = seed(storage)
    conn.close()
    client = TestClient(create_app(AppConfig(storage=storage, ca_dir=tmp_path / "ca")))
    login = client.post("/login", data={"username": "admin", "password": "admin", "next": "/"}, follow_redirects=False)
    assert login.status_code == 303

    response = client.get("/api/flows", params={"meta": "true", "host": "github", "event_type": "connect"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == "connect:g"

    legacy = client.get("/api/flows", params={"host": "github"})
    assert isinstance(legacy.json(), list)
    assert len(legacy.json()) == 1

    options = client.get("/api/flows/options").json()
    assert "github.com" in options["hosts"]
    assert "CONNECT" in options["methods"]

    stats = client.get("/api/traffic/stats").json()
    assert stats["total"] == 2
    assert stats["connects"] == 1
    assert stats["high_risk"] == 1
