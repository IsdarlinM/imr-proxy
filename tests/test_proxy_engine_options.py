from pathlib import Path

from imr_proxy.models.config import AppConfig
from imr_proxy.proxy.engine import _mitmproxy_options_kwargs


def test_mitmproxy_options_omit_confdir_when_ca_dir_is_none():
    cfg = AppConfig(host="127.0.0.1", port=7413)

    kwargs = _mitmproxy_options_kwargs(cfg, None)

    assert kwargs["listen_host"] == "127.0.0.1"
    assert kwargs["listen_port"] == 7413
    assert "confdir" not in kwargs


def test_mitmproxy_options_include_confdir_only_as_string_when_ca_dir_exists():
    cfg = AppConfig(host="127.0.0.1", port=7413)
    ca_dir = Path("/tmp/imr-proxy-ca")

    kwargs = _mitmproxy_options_kwargs(cfg, ca_dir)

    assert kwargs["confdir"] == str(ca_dir)
    assert isinstance(kwargs["confdir"], str)

import sys
import types

import asyncio

from imr_proxy.proxy.engine import _run_mitmproxy


def test_run_mitmproxy_uses_fake_mitmproxy_and_finishes(monkeypatch, tmp_path):
    calls = {"options": None, "update": None, "run": False, "shutdown": False, "addons": []}

    class FakeOptions:
        def __init__(self, **kwargs):
            calls["options"] = kwargs
        def update(self, **kwargs):
            calls["update"] = kwargs

    class FakeAddonManager:
        def add(self, addon):
            calls["addons"].append(addon)

    class FakeDumpMaster:
        def __init__(self, opts, with_termlog=False, with_dumper=False):
            self.opts = opts
            self.addons = FakeAddonManager()
        async def run(self):
            calls["run"] = True
        def shutdown(self):
            calls["shutdown"] = True

    monkeypatch.setitem(sys.modules, "mitmproxy", types.ModuleType("mitmproxy"))
    options_mod = types.ModuleType("mitmproxy.options")
    options_mod.Options = FakeOptions
    tools_mod = types.ModuleType("mitmproxy.tools")
    dump_mod = types.ModuleType("mitmproxy.tools.dump")
    dump_mod.DumpMaster = FakeDumpMaster
    monkeypatch.setitem(sys.modules, "mitmproxy.options", options_mod)
    monkeypatch.setitem(sys.modules, "mitmproxy.tools", tools_mod)
    monkeypatch.setitem(sys.modules, "mitmproxy.tools.dump", dump_mod)

    cfg = AppConfig(storage=tmp_path / "db.sqlite3", ca_dir=tmp_path / "ca", intercept_https=False, cert_mode="passthrough")

    class FakeRepo:
        def save(self, flow):
            pass

    asyncio.run(_run_mitmproxy(cfg, FakeRepo(), "session-id", None))

    assert calls["options"] == {"listen_host": "127.0.0.1", "listen_port": 7413}
    assert calls["update"]["mode"] == ["regular"]
    assert calls["update"]["http2"] is True
    assert calls["update"]["ignore_hosts"] == [".*"]
    assert len(calls["addons"]) == 1
    assert calls["run"] is True
    assert calls["shutdown"] is True
