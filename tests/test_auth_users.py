from typer.testing import CliRunner

from imr_proxy.cli import app
from imr_proxy.storage.database import connect, init_db
from imr_proxy.web.auth import UserRepository, hash_password, verify_password


def test_password_hashing_round_trip():
    hashed = hash_password("admin")
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password("admin", hashed)
    assert not verify_password("wrong", hashed)


def test_default_admin_created_and_user_lifecycle(tmp_path):
    conn = connect(tmp_path / "users.sqlite3")
    init_db(conn)
    repo = UserRepository(conn)
    assert repo.authenticate("admin", "admin")

    repo.create_user("Analyst01", "ChangeMe123!", is_admin=False, created_by="test")
    assert repo.authenticate("analyst01", "ChangeMe123!")
    repo.set_password("analyst01", "NewPass123!")
    assert not repo.authenticate("analyst01", "ChangeMe123!")
    assert repo.authenticate("analyst01", "NewPass123!")
    repo.set_active("analyst01", False)
    assert repo.authenticate("analyst01", "NewPass123!") is None


def test_cli_user_commands(tmp_path):
    runner = CliRunner()
    storage = str(tmp_path / "cli-users.sqlite3")
    result = runner.invoke(app, ["users", "list", "--storage", storage])
    assert result.exit_code == 0, result.output
    assert "admin" in result.output

    result = runner.invoke(app, ["users", "create", "analyst02", "--password", "ChangeMe123!", "--storage", storage])
    assert result.exit_code == 0, result.output
    assert "Created user" in result.output

    result = runner.invoke(app, ["users", "passwd", "analyst02", "--password", "OtherPass123!", "--storage", storage])
    assert result.exit_code == 0, result.output
    assert "Password updated" in result.output

    result = runner.invoke(app, ["users", "disable", "analyst02", "--storage", storage])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["users", "enable", "analyst02", "--storage", storage])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["users", "delete", "analyst02", "--yes", "--storage", storage])
    assert result.exit_code == 0, result.output


def test_default_admin_init_is_idempotent_for_repeated_startup(tmp_path):
    db = tmp_path / "startup-users.sqlite3"
    conn1 = connect(db)
    init_db(conn1)
    conn2 = connect(db)
    init_db(conn2)
    repo = UserRepository(conn2)
    users = repo.list_users()
    assert [u["username"] for u in users].count("admin") == 1
    assert repo.authenticate("admin", "admin")


def test_default_admin_init_is_safe_under_parallel_startup(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    db = tmp_path / "parallel-startup-users.sqlite3"

    def init_once():
        conn = connect(db)
        init_db(conn)
        return UserRepository(conn).authenticate("admin", "admin") is not None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: init_once(), range(16)))

    assert all(results)
    conn = connect(db)
    init_db(conn)
    users = UserRepository(conn).list_users()
    assert [u["username"] for u in users].count("admin") == 1
