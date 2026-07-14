from imr_proxy.version import get_version


def test_version():
    assert get_version() == "0.1.83"
