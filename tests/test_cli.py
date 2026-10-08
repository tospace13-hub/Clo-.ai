import pytest

from cloe import cli, db


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    for key in ("CLOE_DB", "CLOE_SEND", "CLOE_CANARY", "CLOE_APPROVERS", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text(f"CLOE_DB={tmp_path / 'data' / 'cloe.db'}\nCLOE_SEND=0\n")
    return path


def test_version(capsys, env_file):
    assert cli.main(["--env", str(env_file), "version"]) == 0
    assert capsys.readouterr().out.startswith("cloe ")


def test_init_is_idempotent_and_logged(capsys, env_file, tmp_path):
    assert cli.main(["--env", str(env_file), "init"]) == 0
    assert cli.main(["--env", str(env_file), "init"]) == 0
    out = capsys.readouterr().out
    assert "1 migration(s) applied" in out and "0 migration(s) applied" in out
    conn = db.connect(tmp_path / "data" / "cloe.db")
    assert conn.execute("SELECT count(*) FROM event WHERE action='init'").fetchone()[0] == 2


def test_doctor_ok_and_warns_dry_run(capsys, env_file):
    cli.main(["--env", str(env_file), "init"])
    capsys.readouterr()
    assert cli.main(["--env", str(env_file), "doctor"]) == 0
    out = capsys.readouterr().out
    assert "OK   canary present" in out
    assert "OK   tone.md version" in out
    assert "WARN CLOE_SEND=0: dry run" in out
    assert "FAIL" not in out
    assert "@" not in out  # approvers are counted, never printed


def test_doctor_before_init_does_not_create_db(capsys, env_file, tmp_path):
    assert cli.main(["--env", str(env_file), "doctor"]) == 0
    assert "run `cloe init`" in capsys.readouterr().out
    assert not (tmp_path / "data" / "cloe.db").exists()


def test_bad_settings_exit_2(env_file, monkeypatch):
    monkeypatch.setenv("CLOE_EFFORT", "turbo")
    assert cli.main(["--env", str(env_file), "version"]) == 2
