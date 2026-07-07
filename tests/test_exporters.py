import json

from imr_proxy.models.flow import FlowRecord, RequestRecord, ResponseRecord
from imr_proxy.reporting.exporters import export_flows
from imr_proxy.version import get_version


def test_export_json(tmp_path):
    f = FlowRecord(
        id="1",
        session_id="s",
        request=RequestRecord(method="GET", url="https://example.com", host="example.com"),
        response=ResponseRecord(status_code=200),
    )
    data = json.loads(export_flows([f], "json", tmp_path / "out.json").read_text())
    assert data["version"] == get_version() and data["flows"][0]["id"] == "1"


def test_export_har(tmp_path):
    f = FlowRecord(
        id="1",
        session_id="s",
        request=RequestRecord(method="GET", url="https://example.com", host="example.com"),
        response=ResponseRecord(status_code=200),
    )
    data = json.loads(export_flows([f], "har", tmp_path / "out.har").read_text())
    assert data["log"]["entries"][0]["request"]["url"] == "https://example.com"
