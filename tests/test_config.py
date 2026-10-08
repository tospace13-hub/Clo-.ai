from datetime import time

import pytest

from cloe import config


def test_parse_env_quotes_comments_export():
    text = """
# comment
export A=1
B = two words   # trailing comment
C="Cloé (AI) · TOS13 <hello@space13.to>"
D='x # not a comment'
E=
F=   # empty with a comment
bad line
"""
    env = config.parse_env(text)
    assert env == {
        "A": "1",
        "B": "two words",
        "C": "Cloé (AI) · TOS13 <hello@space13.to>",
        "D": "x # not a comment",
        "E": "",
        "F": "",
    }


def test_example_env_parses_to_every_field(tmp_path):
    example = (config.Path(__file__).parents[1] / ".env.example").read_text(encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(example, encoding="utf-8")
    s = config.load(env_file, environ={})
    assert s.model == "claude-opus-5-5"
    assert s.model_bulk == s.model
    assert s.effort == "high"
    assert s.send is False
    assert s.quiet_hours == (time(20, 0), time(8, 0))
    assert s.max_msgs_per_person_per_14d == 1
    assert "space13.to" in s.allowed_link_domains
    assert s.mail_from.startswith("Cloé (AI)")
    assert str(s.db) == "data/cloe.db"


def test_environment_overrides_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("CLOE_SEND=0\nCLOE_APPROVERS=A@Example.org, b@example.org\n")
    s = config.load(env_file, environ={"CLOE_SEND": "1"})
    assert s.send is True
    assert s.approvers == ("a@example.org", "b@example.org")


@pytest.mark.parametrize("value", ["yes", "true", "2", ""])
def test_send_only_on_exact_one(tmp_path, value):
    s = config.load(tmp_path / ".env", environ={"CLOE_SEND": value})
    assert s.send is False


def test_bad_effort_rejected(tmp_path):
    with pytest.raises(ValueError):
        config.load(tmp_path / ".env", environ={"CLOE_EFFORT": "turbo"})


def test_canary_generated_once_and_persisted(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("CLOE_SEND=0")  # no trailing newline on purpose
    first = config.load(env_file, environ={})
    assert first.canary.startswith("cloe-canary-")
    assert f"CLOE_CANARY={first.canary}\n" in env_file.read_text()
    assert "CLOE_SEND=0\n" in env_file.read_text()
    second = config.load(env_file, environ={})
    assert second.canary == first.canary


def test_new_env_file_is_private(tmp_path):
    env_file = tmp_path / "sub" / ".env"
    config.load(env_file, environ={})
    assert env_file.stat().st_mode & 0o077 == 0


def test_secrets_not_in_repr(tmp_path):
    s = config.load(tmp_path / ".env", environ={"ANTHROPIC_API_KEY": "secret-value-123"})
    assert "secret-value-123" not in repr(s)
    assert s.canary not in repr(s)
