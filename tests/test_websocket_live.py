from __future__ import annotations

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from imr_proxy.models.config import AppConfig
from imr_proxy.models.flow import FlowRecord, RequestRecord, ResponseRecord
from imr_proxy.models.session import SessionRecord
from imr_proxy.storage.database import connect, init_db
from imr_proxy.storage.repositories import FlowRepository, SessionRepository
from imr_proxy.version import get_version
from imr_proxy.web.server import create_app


def _config(tmp_path):
    return AppConfig(storage=tmp_path / "imr-proxy.sqlite3", ca_dir=tmp_path / "ca")


def _login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"username": "admin", "password": "admin", "next": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _save_flow(config: AppConfig, *, state: str, status_code: int | None) -> int:
    conn = connect(config.storage)
    try:
        init_db(conn)
        sessions = SessionRepository(conn)
        if sessions.latest_id() is None:
            sessions.create(
                SessionRecord(
                    id="live-session",
                    name="live-test",
                    version=get_version(),
                    config_snapshot={},
                )
            )
        repo = FlowRepository(conn)
        repo.save(
            FlowRecord(
                id="live-flow",
                session_id="live-session",
                event_type="http",
                state=state,
                request=RequestRecord(
                    method="GET",
                    url="https://github.com/openai",
                    host="github.com",
                ),
                response=ResponseRecord(status_code=status_code) if status_code else None,
            )
        )
        return repo.revision()
    finally:
        conn.close()


def test_websocket_requires_authenticated_session(tmp_path):
    client = TestClient(create_app(_config(tmp_path)))
    try:
        with client.websocket_connect("/ws/traffic") as websocket:
            websocket.receive_json()
    except WebSocketDisconnect as exc:
        assert exc.code == 4401
    else:
        raise AssertionError("Unauthenticated WebSocket was accepted")


def test_websocket_rejects_cross_origin_browser_handshake(tmp_path):
    client = TestClient(create_app(_config(tmp_path)))
    _login(client)
    try:
        with client.websocket_connect(
            "/ws/traffic",
            headers={"origin": "https://evil.example"},
        ) as websocket:
            websocket.receive_json()
    except WebSocketDisconnect as exc:
        assert exc.code == 4403
    else:
        raise AssertionError("Cross-origin WebSocket was accepted")


def test_websocket_notifies_new_and_updated_flows_without_page_refresh(tmp_path):
    config = _config(tmp_path)
    client = TestClient(create_app(config))
    _login(client)

    with client.websocket_connect("/ws/traffic") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "ready"

        first_revision = _save_flow(config, state="pending", status_code=None)
        created = websocket.receive_json()
        assert created["type"] == "traffic_changed"
        assert created["revision"] == first_revision
        assert created["stats"]["total"] == 1
        assert created["stats"]["pending"] == 1

        second_revision = _save_flow(config, state="complete", status_code=200)
        updated = websocket.receive_json()
        assert updated["type"] == "traffic_changed"
        assert updated["revision"] == second_revision
        assert second_revision > first_revision
        assert updated["stats"]["total"] == 1
        assert updated["stats"]["pending"] == 0

    response = client.get("/api/flows?meta=true&host=github.com")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["status_code"] == 200
