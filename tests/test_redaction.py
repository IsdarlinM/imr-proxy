from imr_proxy.proxy.redaction import redact_headers, redact_text, redact_url
def test_redact_headers():
    h=redact_headers({"Authorization":"Bearer abcdefghijklmnop","Accept":"application/json"})
    assert h["Authorization"]!="Bearer abcdefghijklmnop" and h["Accept"]=="application/json"
def test_redact_url():
    assert "secretvalue" not in redact_url("https://e.test/a?access_token=secretvalue")
def test_strict_redacts_email():
    assert "a@example.com" not in (redact_text("email a@example.com","strict") or "")
