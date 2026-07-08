from fastapi.testclient import TestClient

from imr_proxy.models.config import AppConfig
from imr_proxy.web.server import create_app
from imr_proxy.version import get_version


def test_web_ui_routes_render_without_500(tmp_path):
    cfg = AppConfig(storage=tmp_path / "imr-proxy.sqlite3", ca_dir=tmp_path / "ca")
    client = TestClient(create_app(cfg))

    for path in ["/", "/settings", "/certificates"]:
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert "IMR-PROXY" in response.text
        assert get_version() in response.text


def test_web_api_routes_work_on_empty_database(tmp_path):
    cfg = AppConfig(storage=tmp_path / "imr-proxy.sqlite3", ca_dir=tmp_path / "ca")
    client = TestClient(create_app(cfg))

    assert client.get("/api/sessions").json() == []
    assert client.get("/api/flows").json() == []
    assert client.get("/api/flows/not-found").status_code == 404
    assert client.get("/favicon.ico").status_code == 204


def test_dashboard_shows_custom_linux_ports(tmp_path):
    cfg = AppConfig(
        storage=tmp_path / "imr-proxy.sqlite3",
        ca_dir=tmp_path / "ca",
        host="127.0.0.1",
        port=18113,
        web_host="127.0.0.1",
        web_port=18114,
    )
    client = TestClient(create_app(cfg))
    response = client.get("/")
    assert response.status_code == 200
    assert "127.0.0.1:18113" in response.text
    assert "127.0.0.1:18114" in response.text
