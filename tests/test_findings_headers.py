from imr_proxy.findings.headers import analyze
from imr_proxy.models.flow import FlowRecord, RequestRecord, ResponseRecord
def test_missing_headers_findings():
    f=FlowRecord(id="1",session_id="s",request=RequestRecord(method="GET",url="https://example.com",scheme="https",host="example.com"),response=ResponseRecord(status_code=200,headers={"content-type":"text/html"}))
    ids={x.id for x in analyze(f)}
    assert "HDR-MISSING-HSTS" in ids and "HDR-MISSING-CSP" in ids
