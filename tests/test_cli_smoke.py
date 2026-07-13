from typer.testing import CliRunner

from imr_proxy.cli import app
from imr_proxy.version import get_version

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert get_version() in result.output


def test_cli_rules_test():
    result = runner.invoke(app, ["rules", "test", "https://app.example.com/a", "--scope", "example.com"])
    assert result.exit_code == 0
    assert '"in_scope": true' in result.output


def test_start_rejects_remote_bind_without_traceback():
    result = runner.invoke(app, ["start", "--host", "0.0.0.0", "--port", "8585"])
    assert result.exit_code == 2
    assert "Configuration error" in result.output
    assert "--allow-remote" in result.output
    assert "Traceback" not in result.output


def test_start_rejects_remote_web_bind_without_traceback():
    result = runner.invoke(app, ["start", "--web-host", "0.0.0.0", "--web-port", "8586"])
    assert result.exit_code == 2
    assert "Configuration error" in result.output
    assert "--allow-remote" in result.output
    assert "Traceback" not in result.output
