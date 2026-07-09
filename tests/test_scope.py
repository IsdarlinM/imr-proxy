from imr_proxy.proxy.scope import ScopeMatcher
def test_scope_domain():
    m=ScopeMatcher(["example.com"], [])
    assert m.in_scope("https://app.example.com/a")
    assert not m.in_scope("https://evil.test/a")
def test_exclude_path():
    assert not ScopeMatcher(["example.com"], ["/logout*"]).in_scope("https://example.com/logout")
