from types import SimpleNamespace

from imr_proxy.models.config import AppConfig
from imr_proxy.proxy.addons import ImrProxyAddon


class Headers(dict):
    def items(self, multi=False):
        return super().items()

    def get_all(self, name):
        value = self.get(name)
        return [] if value is None else [value]


class FakeRepository:
    def __init__(self):
        self.records = {}
        self.history = []

    def save(self, flow):
        self.records[flow.id] = flow
        self.history.append(flow.model_copy(deep=True))


def make_flow(*, flow_id="abc", method="GET", url="http://example.test/path?q=ok", response=True):
    request = SimpleNamespace(
        method=method,
        pretty_url=url,
        url=url,
        scheme="https" if url.startswith("https") else "http",
        host="github.com" if "github.com" in url else "example.test",
        port=443 if url.startswith("https") else 80,
        path="/path",
        http_version="HTTP/1.1",
        headers=Headers({"User-Agent": "pytest"}),
        cookies={},
        raw_content=b"",
        timestamp_start=1_700_000_000,
    )
    reply = None
    if response:
        reply = SimpleNamespace(
            status_code=200,
            reason="OK",
            http_version="HTTP/1.1",
            headers=Headers({"Content-Type": "text/plain"}),
            cookies={},
            raw_content=b"hello",
        )
    return SimpleNamespace(
        id=flow_id,
        request=request,
        response=reply,
        error=None,
        client_conn=SimpleNamespace(peername=("127.0.0.1", 51000)),
        server_conn=SimpleNamespace(address=(request.host, request.port), tls_version=None, cipher=None, cert=None),
        websocket=None,
    )


def test_request_is_visible_before_response_and_upserted_on_completion(tmp_path):
    repo = FakeRepository()
    addon = ImrProxyAddon(AppConfig(storage=tmp_path / "db.sqlite3"), repo, "session")
    flow = make_flow(response=False)

    addon.requestheaders(flow)
    pending = repo.records["http:abc"]
    assert pending.state == "pending"
    assert pending.response is None

    flow.response = make_flow().response
    addon.response(flow)
    completed = repo.records["http:abc"]
    assert completed.state == "complete"
    assert completed.response.status_code == 200
    assert len(repo.records) == 1


def test_failed_http_request_is_persisted(tmp_path):
    repo = FakeRepository()
    addon = ImrProxyAddon(AppConfig(storage=tmp_path / "db.sqlite3"), repo, "session")
    flow = make_flow(response=False)
    flow.error = SimpleNamespace(msg="connection reset by peer")

    addon.request(flow)
    addon.error(flow)

    record = repo.records["http:abc"]
    assert record.state == "error"
    assert "connection reset" in record.error_message


def test_connect_tunnel_is_visible_for_tls_passthrough(tmp_path):
    repo = FakeRepository()
    addon = ImrProxyAddon(AppConfig(storage=tmp_path / "db.sqlite3"), repo, "session")
    flow = make_flow(method="CONNECT", url="https://github.com:443/", response=False)

    addon.http_connect(flow)
    assert repo.records["connect:abc"].state == "pending"
    assert repo.records["connect:abc"].request.host == "github.com"

    addon.http_connected(flow)
    record = repo.records["connect:abc"]
    assert record.state == "connected"
    assert record.response.status_code == 200
    assert record.event_type == "connect"


def test_websocket_lifecycle_uses_stable_record(tmp_path):
    repo = FakeRepository()
    addon = ImrProxyAddon(AppConfig(storage=tmp_path / "db.sqlite3"), repo, "session")
    flow = make_flow(url="https://example.test/path", response=True)
    flow.websocket = SimpleNamespace(messages=[], close_code=None, close_reason=None)

    addon.websocket_start(flow)
    assert repo.records["websocket:abc"].state == "active"

    flow.websocket.messages.append(SimpleNamespace(content=b"hello", from_client=True))
    addon.websocket_message(flow)
    assert repo.records["websocket:abc"].metadata["message_count"] == 1

    flow.websocket.close_code = 1000
    flow.websocket.close_reason = "normal"
    addon.websocket_end(flow)
    assert repo.records["websocket:abc"].state == "closed"
    assert repo.records["websocket:abc"].metadata["close_code"] == 1000


def test_server_connection_lifecycle_is_visible(tmp_path):
    repo = FakeRepository()
    addon = ImrProxyAddon(AppConfig(storage=tmp_path / "db.sqlite3"), repo, "session")
    server = SimpleNamespace(
        id="server-1",
        address=("github.com", 443),
        peername=("140.82.121.4", 443),
        timestamp_start=1_700_000_000,
        tls=True,
        transport_protocol="tcp",
        alpn=b"h2",
        error=None,
    )
    data = SimpleNamespace(server=server, client=SimpleNamespace(peername=("127.0.0.1", 51000)))

    addon.server_connect(data)
    assert repo.records["connection:server-1"].state == "pending"
    addon.server_connected(data)
    assert repo.records["connection:server-1"].state == "connected"
    assert repo.records["connection:server-1"].request.host == "github.com"
    addon.server_disconnected(data)
    assert repo.records["connection:server-1"].state == "disconnected"
