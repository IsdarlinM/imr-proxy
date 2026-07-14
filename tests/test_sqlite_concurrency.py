from __future__ import annotations

import hashlib
import threading
import time

from fastapi.testclient import TestClient

from imr_proxy.models.config import AppConfig
from imr_proxy.models.flow import FlowRecord, RequestRecord, ResponseRecord
from imr_proxy.models.session import SessionRecord
from imr_proxy.storage.database import connect, init_db
from imr_proxy.storage.repositories import FlowRepository, SessionRepository
from imr_proxy.version import get_version
from imr_proxy.web.auth import SESSION_COOKIE
from imr_proxy.web.server import create_app


def _config(tmp_path) -> AppConfig:
    return AppConfig(storage=tmp_path / "concurrency.sqlite3", ca_dir=tmp_path / "ca")


def _login(client: TestClient) -> str:
    response = client.post(
        "/login",
        data={"username": "admin", "password": "admin", "next": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    token = client.cookies.get(SESSION_COOKIE)
    assert token
    return token


def _session_last_seen(storage, token: str) -> str:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = connect(storage)
    try:
        return conn.execute(
            "SELECT last_seen_at FROM web_sessions WHERE token_hash=?",
            (token_hash,),
        ).fetchone()["last_seen_at"]
    finally:
        conn.close()


def test_authenticated_api_hot_path_is_read_only(tmp_path):
    config = _config(tmp_path)
    client = TestClient(create_app(config))
    token = _login(client)
    before = _session_last_seen(config.storage, token)

    for _ in range(10):
        assert client.get("/api/flows?meta=true").status_code == 200
        assert client.get("/api/traffic/stats").status_code == 200

    after = _session_last_seen(config.storage, token)
    assert after == before


def test_api_reads_succeed_while_proxy_writer_holds_reserved_lock(tmp_path):
    config = _config(tmp_path)
    client = TestClient(create_app(config))
    _login(client)

    writer = connect(config.storage)
    try:
        # In WAL mode an IMMEDIATE transaction reserves the single writer slot,
        # but authenticated dashboard/API reads must still succeed because they
        # no longer write last_seen_at during every request.
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("UPDATE traffic_revision SET revision=revision+1 WHERE id=1")

        assert client.get("/api/flows?limit=250&meta=true").status_code == 200
        assert client.get("/api/traffic/stats").status_code == 200
        assert client.get("/").status_code == 200
    finally:
        writer.rollback()
        writer.close()


def test_concurrent_flow_capture_and_dashboard_reads_do_not_return_500(tmp_path):
    config = _config(tmp_path)
    client = TestClient(create_app(config))
    _login(client)

    seed = connect(config.storage)
    init_db(seed)
    SessionRepository(seed).create(
        SessionRecord(
            id="stress-session",
            name="stress",
            version=get_version(),
            config_snapshot={},
        )
    )
    seed.close()

    errors: list[BaseException] = []

    def writer() -> None:
        conn = connect(config.storage)
        repo = FlowRepository(conn)
        try:
            for index in range(150):
                repo.save(
                    FlowRecord(
                        id=f"stress-{index}",
                        session_id="stress-session",
                        event_type="http",
                        state="complete",
                        request=RequestRecord(
                            method="GET",
                            url=f"https://example.test/{index}",
                            host="example.test",
                        ),
                        response=ResponseRecord(status_code=200),
                    )
                )
        except BaseException as exc:  # pragma: no cover - assertion reports it
            errors.append(exc)
        finally:
            conn.close()

    thread = threading.Thread(target=writer, daemon=True)
    thread.start()
    statuses: list[int] = []
    while thread.is_alive():
        statuses.append(client.get("/api/flows?limit=250&meta=true").status_code)
        statuses.append(client.get("/api/traffic/stats").status_code)
        time.sleep(0.002)
    thread.join(timeout=5)

    assert not errors
    assert statuses
    assert set(statuses) == {200}
    final = client.get("/api/traffic/stats")
    assert final.status_code == 200
    assert final.json()["total"] == 150
