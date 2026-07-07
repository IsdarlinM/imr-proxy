from imr_proxy.config import build_config, write_default_config
def test_config_loading(tmp_path):
    p=tmp_path/"config.yaml"; write_default_config(p)
    cfg=build_config(p, {"port":9999})
    assert cfg.host=="127.0.0.1" and cfg.port==9999 and cfg.redaction_level=="balanced"
