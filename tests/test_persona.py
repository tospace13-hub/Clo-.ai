from cloe import persona, untrusted

CANARY = "cloe-canary-persona000000000000000000"


def test_tone_md_is_included_verbatim():
    tone = persona.load_tone()
    blocks = persona.system_prompt("Summarise.", CANARY)
    assert tone in blocks[0]["text"]


def test_task_block_is_last_and_uncached():
    blocks = persona.system_prompt("TASK-XYZ", CANARY)
    assert len(blocks) == 2
    assert blocks[-1]["text"].endswith("TASK-XYZ")
    assert "cache_control" not in blocks[-1]
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "TASK-XYZ" not in blocks[0]["text"]


def test_stable_part_has_identity_rule_and_canary():
    stable = persona.system_prompt("t", CANARY)[0]["text"]
    assert stable.startswith(persona.IDENTITY)
    assert untrusted.UNTRUSTED_RULE in stable
    assert CANARY in stable


def test_stable_part_is_identical_across_tasks():
    a = persona.system_prompt("task a", CANARY)[0]
    b = persona.system_prompt("task b", CANARY)[0]
    assert a == b  # same bytes → the prompt cache hits


def test_identity_keeps_ai_and_person_apart():
    assert "You are Cloé" in persona.IDENTITY
    assert "never write as if you were Chloe" in persona.IDENTITY


def test_tone_version_parsed():
    assert persona.tone_version(persona.load_tone()) == "1.1"


def test_canary_required():
    import pytest

    with pytest.raises(ValueError):
        persona.system_prompt("t", "")
