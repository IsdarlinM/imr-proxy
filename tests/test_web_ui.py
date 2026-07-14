from pathlib import Path

from fastapi.testclient import TestClient

from imr_proxy.models.config import AppConfig
from imr_proxy.web.auth import SESSION_COOKIE
from imr_proxy.web.server import create_app
from imr_proxy.version import get_version


def _client(tmp_path):
    cfg = AppConfig(storage=tmp_path / "imr-proxy.sqlite3", ca_dir=tmp_path / "ca")
    return TestClient(create_app(cfg))


def _login(client: TestClient, username="admin", password="admin"):
    response = client.post("/login", data={"username": username, "password": password, "next": "/"}, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert SESSION_COOKIE in response.cookies
    return response


def test_web_ui_requires_login_and_default_admin_can_login(tmp_path):
    client = _client(tmp_path)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")

    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert "Console Login" in login_page.text
    assert get_version() in login_page.text

    _login(client)
    dashboard = client.get("/")
    assert dashboard.status_code == 200, dashboard.text
    assert "IMR-PROXY" in dashboard.text
    assert "Traffic Dashboard" in dashboard.text
    assert "Default credentials" in dashboard.text


def test_web_ui_routes_render_after_login(tmp_path):
    client = _client(tmp_path)
    _login(client)

    for path in ["/", "/settings", "/certificates", "/users"]:
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert "IMR-PROXY" in response.text
        assert get_version() in response.text


def test_web_api_routes_are_authenticated(tmp_path):
    client = _client(tmp_path)
    assert client.get("/api/sessions").status_code == 401
    _login(client)

    assert client.get("/api/sessions").json() == []
    assert client.get("/api/flows").json() == []
    assert client.get("/api/flows/not-found").status_code == 404
    assert client.get("/favicon.ico").status_code == 204


def test_dashboard_shows_custom_linux_ports_after_login(tmp_path):
    cfg = AppConfig(
        storage=tmp_path / "imr-proxy.sqlite3",
        ca_dir=tmp_path / "ca",
        host="127.0.0.1",
        port=18113,
        web_host="127.0.0.1",
        web_port=18114,
    )
    client = TestClient(create_app(cfg))
    _login(client)
    response = client.get("/")
    assert response.status_code == 200
    assert "127.0.0.1:18113" in response.text
    assert "127.0.0.1:18114" in response.text


def test_web_user_creation_and_login(tmp_path):
    client = _client(tmp_path)
    _login(client)
    users_page = client.get("/users")
    assert users_page.status_code == 200
    marker = 'name="csrf_token" value="'
    csrf = users_page.text.split(marker, 1)[1].split('"', 1)[0]

    created = client.post(
        "/users/create",
        data={"csrf_token": csrf, "username": "analyst01", "password": "ChangeMe123!"},
    )
    assert created.status_code == 200, created.text
    assert "analyst01" in created.text

    client.get("/logout")
    response = client.post("/login", data={"username": "analyst01", "password": "ChangeMe123!", "next": "/"}, follow_redirects=False)
    assert response.status_code == 303
    dashboard = client.get("/")
    assert dashboard.status_code == 200


def test_invalid_login_is_rejected(tmp_path):
    client = _client(tmp_path)
    response = client.post("/login", data={"username": "admin", "password": "wrong", "next": "/"})
    assert response.status_code == 200
    assert "Invalid username or password" in response.text


def test_mobile_assets_and_responsive_markup(tmp_path):
    client = _client(tmp_path)

    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert "viewport-fit=cover" in login_page.text
    assert "style.css?v=0.1.82-console-r1" in login_page.text

    _login(client)
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert 'id="traffic-log"' in dashboard.text
    assert 'id="flow-drawer"' in dashboard.text
    assert 'class="traffic-log-row"' in Path("imr_proxy/web/templates/dashboard.html").read_text()
    assert 'id="filter-status"' in dashboard.text
    assert 'id="traffic-filters"' in dashboard.text
    assert 'id="filter-event-type"' in dashboard.text
    assert 'id="filter-tls"' in dashboard.text
    assert 'id="toggle-live"' in dashboard.text
    assert "app.js?v=0.1.82-console-r1" in dashboard.text

    stylesheet = client.get("/static/style.css")
    assert stylesheet.status_code == 200
    assert "@media screen and (max-width: 1100px)" in stylesheet.text
    assert "@media screen and (max-width: 700px)" in stylesheet.text
    assert ".traffic-log-row" in stylesheet.text
    assert ".flow-drawer" in stylesheet.text
    assert "overflow-wrap: anywhere" in stylesheet.text

    javascript = client.get("/static/app.js")
    assert javascript.status_code == 200
    assert 'openFlowDrawer' in javascript.text
    assert 'renderLogRows' in javascript.text
    assert 'aria-current' in javascript.text
    assert '/api/flows?' in javascript.text
    assert 'new WebSocket' in javascript.text
    assert '/ws/traffic' in javascript.text
    assert 'fallbackPollingIntervalMs' in javascript.text
    assert 'replaceChildren' in javascript.text
