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
