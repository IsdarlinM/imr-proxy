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
