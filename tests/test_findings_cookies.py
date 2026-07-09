from imr_proxy.findings.cookies import analyze
from imr_proxy.models.flow import FlowRecord, RequestRecord, ResponseRecord
def test_cookie_missing_attrs():
    f=FlowRecord(id="1",session_id="s",request=RequestRecord(method="GET",url="https://example.com",scheme="https",host="example.com"),response=ResponseRecord(status_code=200,set_cookies=["sessionid=abc123; Path=/"]))
    ids={x.id for x in analyze(f)}
    assert "COOKIE-MISSING-SECURE" in ids and "COOKIE-MISSING-HTTPONLY" in ids
