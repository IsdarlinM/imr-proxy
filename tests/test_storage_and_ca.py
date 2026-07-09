from imr_proxy.models.flow import FlowRecord, RequestRecord, ResponseRecord
from imr_proxy.models.session import SessionRecord
from imr_proxy.proxy.certificates import export_ca, init_ca, load_ca_info, sign_host_certificate
from imr_proxy.storage.database import connect, init_db
from imr_proxy.storage.repositories import FlowRepository, SessionRepository
from imr_proxy.version import get_version


def test_storage_session_and_flow_round_trip(tmp_path):
    conn = connect(tmp_path / "imr-proxy.sqlite3")
    init_db(conn)
    sessions = SessionRepository(conn)
    flows = FlowRepository(conn)
    session = SessionRecord(id="s1", name="test", version=get_version(), config_snapshot={"host": "127.0.0.1"})
    sessions.create(session)
    flow = FlowRecord(
        id="f1",
        session_id="s1",
        request=RequestRecord(method="GET", url="https://example.com/a", host="example.com"),
        response=ResponseRecord(status_code=200),
    )
    flows.save(flow)

    assert sessions.latest_id() == "s1"
    assert flows.get("f1").request.url == "https://example.com/a"
    assert flows.recent(10)[0]["id"] == "f1"
    assert flows.list_by_session("s1")[0].id == "f1"


def test_ca_lifecycle(tmp_path):
    ca_dir = tmp_path / "ca"
    init_ca(ca_dir)
    info = load_ca_info(ca_dir)
    assert "imr-proxy" in info["subject"]

    exported = export_ca(ca_dir, tmp_path / "public-ca.pem")
    assert exported.exists()
    assert "BEGIN CERTIFICATE" in exported.read_text(encoding="utf-8")

    cert, key = sign_host_certificate(ca_dir, "example.com", tmp_path / "leaf")
    assert cert.exists()
    assert key.exists()
