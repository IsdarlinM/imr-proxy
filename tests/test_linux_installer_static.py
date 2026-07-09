from pathlib import Path


def test_linux_installer_creates_user_launcher_and_fails_on_missing_command():
    script = Path("scripts/install_linux.sh").read_text(encoding="utf-8")
    assert "LAUNCHER_PATH" in script
    assert "~/.local/bin" in script or "$HOME/.local/bin" in script
    assert "Installation finished but command was not created" in script
    assert "export PATH=" in script
