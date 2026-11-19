"""Settings in the macOS Keychain (keychain.py, `cloe secrets`), with an in-memory stand-in:
tests never touch a real Keychain."""

import os

import pytest

from cloe import cli, config, keychain
from cloe.sources import sheets


class FakeKeyring:
    def __init__(self, fail_on_set=False):
        self.items: dict[tuple[str, str], str] = {}
        self.fail_on_set = fail_on_set

    def get_password(self, service, name):
        return self.items.get((service, name))

    def set_password(self, service, name, value):
        if self.fail_on_set:
            raise RuntimeError("locked")
        self.items[(service, name)] = value

    def delete_password(self, service, name):
        del self.items[(service, name)]


@pytest.fixture
def kc(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(keychain, "_backend", fake)
    monkeypatch.setattr(keychain, "PLATFORM", "darwin")
    monkeypatch.delenv("CLOE_KEYCHAIN", raising=False)
    for name in config.SETTING_NAMES:
        monkeypatch.delenv(name, raising=False)
    return fake


@pytest.fixture
def env(tmp_path):
    path = tmp_path / ".env"
    path.write_text("CLOE_DB=data/x.db\nANTHROPIC_API_KEY=from-the-file\n"
                    "SMTP_PASSWORD=pw-in-file  # a comment\nCLOE_CANARY=cloe-canary-file\n")
    path.chmod(0o600)
    return path


def test_order_is_environment_then_keychain_then_env_file(kc, env, monkeypatch):
    assert config.load(env).anthropic_api_key == "from-the-file"
    kc.items[("cloe", "ANTHROPIC_API_KEY")] = "from-the-keychain"
    s = config.load(env)
    assert s.anthropic_api_key == "from-the-keychain"
    assert s.keychain_names == ("ANTHROPIC_API_KEY",)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-the-environment")
    s = config.load(env)
    assert s.anthropic_api_key == "from-the-environment" and s.keychain_names == ()
    # an explicit environ (tests, callers) never reads the Keychain
    assert config.load(env, environ={}).anthropic_api_key == "from-the-file"


def test_not_used_off_macos_or_when_turned_off(kc, env, monkeypatch):
    kc.items[("cloe", "ANTHROPIC_API_KEY")] = "from-the-keychain"
    monkeypatch.setattr(keychain, "PLATFORM", "linux")
    assert not keychain.enabled() and "macOS only" in keychain.why_not()
    assert config.load(env).anthropic_api_key == "from-the-file"
    monkeypatch.setattr(keychain, "PLATFORM", "darwin")
    monkeypatch.setenv("CLOE_KEYCHAIN", "0")
    assert config.load(env).anthropic_api_key == "from-the-file"


def test_a_new_canary_goes_to_the_keychain(kc, tmp_path):
    path = tmp_path / ".env"
    path.write_text("CLOE_DB=data/x.db\n")
    s = config.load(path)
    assert kc.items[("cloe", "CLOE_CANARY")] == s.canary
    assert "CLOE_CANARY" not in path.read_text()
    assert config.load(path).canary == s.canary  # read back, not regenerated


def run(env, *argv):
    return cli.main(["--env", str(env), *argv])


def test_move_puts_secrets_in_the_keychain_and_blanks_them(kc, env, capsys):
    assert run(env, "secrets", "move") == 0
    assert "ANTHROPIC_API_KEY, CLOE_CANARY, SMTP_PASSWORD" in capsys.readouterr().out
    assert kc.items[("cloe", "SMTP_PASSWORD")] == "pw-in-file"
    text = env.read_text()
    assert "from-the-file" not in text and "pw-in-file" not in text
    assert "CLOE_DB=data/x.db" in text  # not a secret: stays
    assert oct(os.stat(env).st_mode & 0o777) == "0o600"
    s = config.load(env)
    assert (s.anthropic_api_key, s.smtp_password) == ("from-the-file", "pw-in-file")
    assert run(env, "secrets", "move") == 0
    assert "nothing to move" in capsys.readouterr().out
    assert run(env, "secrets", "move", "--all") == 0
    assert kc.items[("cloe", "CLOE_DB")] == "data/x.db"


def test_move_keeps_what_the_keychain_refused(kc, env, capsys, monkeypatch):
    monkeypatch.setattr(keychain, "_backend", FakeKeyring(fail_on_set=True))
    assert run(env, "secrets", "move") == 1
    assert "it stays in .env" in capsys.readouterr().err
    assert "from-the-file" in env.read_text()


def test_set_list_delete(kc, env, capsys, monkeypatch, tmp_path):
    monkeypatch.setattr("getpass.getpass", lambda prompt: "typed-secret")
    assert run(env, "secrets", "set", "CLOE_KVK_API_KEY") == 0
    assert kc.items[("cloe", "CLOE_KVK_API_KEY")] == "typed-secret"
    key = tmp_path / "sa.json"
    key.write_text('{"type": "service_account"}')
    assert run(env, "secrets", "set", "GOOGLE_SERVICE_ACCOUNT_JSON", "--file", str(key)) == 0
    assert run(env, "secrets", "set", "NOT_A_SETTING") == 1
    capsys.readouterr()
    assert run(env, "secrets", "list") == 0
    out = capsys.readouterr().out
    assert "typed-secret" not in out and "from-the-file" not in out  # never values
    assert "CLOE_KVK_API_KEY" in out and "Keychain (secret)" in out
    assert "ANTHROPIC_API_KEY" in out and ".env (plain text) (secret)" in out
    assert run(env, "secrets", "delete", "CLOE_KVK_API_KEY") == 0
    assert ("cloe", "CLOE_KVK_API_KEY") not in kc.items
    assert run(env, "doctor") in (0, 1)
    out = capsys.readouterr().out
    assert "OK   macOS Keychain: 1 settings there" in out
    assert "secrets in .env in plain text: ANTHROPIC_API_KEY, CLOE_CANARY, SMTP_PASSWORD" in out


def test_commands_refuse_without_a_keychain(env, capsys):
    assert run(env, "secrets", "move") == 1
    assert "can't be used here" in capsys.readouterr().err


def test_service_account_key_from_the_keychain():
    pytest.importorskip("google.oauth2")
    with pytest.raises(sheets.SheetsError, match="cannot read the service account key"):
        sheets.session("", "not json")
    with pytest.raises(sheets.SheetsError, match="neither"):
        sheets.session("", "")
