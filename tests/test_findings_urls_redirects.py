from imr_proxy.findings.redirects import analyze as ar
from imr_proxy.findings.urls import analyze as au
from imr_proxy.models.flow import FlowRecord, RequestRecord, ResponseRecord
def test_sensitive_url_param():
    f=FlowRecord(id="1",session_id="s",request=RequestRecord(method="GET",url="https://example.com/?token=abc",host="example.com"))
    assert any(x.id=="URL-SENSITIVE-PARAM" for x in au(f))
def test_https_downgrade_redirect():
    f=FlowRecord(id="1",session_id="s",request=RequestRecord(method="GET",url="https://example.com",scheme="https",host="example.com"),response=ResponseRecord(status_code=302,headers={"Location":"http://example.com"}))
    assert any(x.id=="REDIRECT-HTTPS-DOWNGRADE" for x in ar(f))
