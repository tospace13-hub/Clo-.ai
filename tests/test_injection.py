"""Prompt-injection suite (sprint.md → Security → "The injection test suite").

Sprint 0 covers wrapping, scrubbing, flagging, schema-only extraction and the canary.
Each later sprint turns its skipped placeholder below into real assertions.
"""

import unicodedata
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from cloe import config, llm, persona, untrusted

FIXTURES = Path(__file__).parent / "fixtures" / "injection"
CANARY = "cloe-canary-injectiontest000000000000"
HOSTILE = sorted(p for p in FIXTURES.iterdir() if p.name != "README.md")


class CompanyFacts(BaseModel):
    """Stand-in for the Sprint 1/3 extraction schema."""

    model_config = ConfigDict(extra="forbid")
    does: list[str]
    instruction_like: list[str]


def hostile(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("{{CANARY}}", CANARY)


@pytest.fixture
def settings(tmp_path):
    return config.load(tmp_path / ".env", environ={"CLOE_CANARY": CANARY})


def test_fixture_set_is_complete():
    names = {p.name for p in HOSTILE}
    assert names == {
        "web_page.html", "pdf_text.txt", "cordis_summary.json",
        "joinform_row.csv", "inbound_email.eml", "sms.txt",
    }
    for p in HOSTILE:
        assert CANARY in hostile(p), p.name


@pytest.mark.parametrize("path", HOSTILE, ids=lambda p: p.name)
def test_wrapped_fixture_cannot_escape_its_block(path):
    wrapped = untrusted.wrap(hostile(path), f"fixture:{path.name}")
    assert wrapped.lower().count("<untrusted") == 1
    assert wrapped.count("</untrusted>") == 1 and wrapped.endswith("</untrusted>")
    # No invisible characters survive (zero-width, bidi, Unicode tag smuggling).
    assert not [ch for ch in wrapped if unicodedata.category(ch) in {"Cf", "Co", "Cn"}]


@pytest.mark.parametrize("path", HOSTILE, ids=lambda p: p.name)
def test_every_fixture_is_flagged(path):
    assert untrusted.injection_flags(hostile(path)), path.name


def test_hidden_tag_characters_are_removed_not_obeyed():
    page = hostile(FIXTURES / "web_page.html")
    assert "drop@evil.example" not in untrusted.scrub(page)


def test_reader_prompt_carries_the_rule_and_canary():
    system = persona.system_prompt("Extract company facts.", CANARY)
    assert untrusted.UNTRUSTED_RULE in system[0]["text"]
    assert CANARY in system[0]["text"]


@pytest.mark.parametrize("path", HOSTILE, ids=lambda p: p.name)
def test_obedient_model_output_with_canary_is_discarded(settings, path):
    # Simulate a model that fell for the payload and echoed the canary.
    obeyed = {"does": [f"repeat {CANARY}"], "instruction_like": []}
    fake = llm.FakeClaude(settings, {"CompanyFacts": obeyed})
    with pytest.raises(llm.InjectionSuspected):
        fake.extract(CompanyFacts, "task", [untrusted.wrap(hostile(path), path.name)])


def test_extraction_returns_only_schema_fields(settings):
    smuggled = {"does": ["weaving"], "instruction_like": [], "send_to": "harvest@evil.example"}
    fake = llm.FakeClaude(settings, {"CompanyFacts": smuggled})
    page = untrusted.wrap(hostile(FIXTURES / "web_page.html"), "web:1")
    with pytest.raises(ValidationError):
        fake.extract(CompanyFacts, "task", [page])


def test_instruction_like_text_is_recorded_as_data(settings):
    good = {"does": ["weaves technical textiles"], "instruction_like": ["asks to email contacts"]}
    fake = llm.FakeClaude(settings, {"CompanyFacts": good})
    page = untrusted.wrap(hostile(FIXTURES / "web_page.html"), "web:1")
    out = fake.extract(CompanyFacts, "task", [page])
    assert out.instruction_like == ["asks to email contacts"]


def test_raw_hostile_text_cannot_reach_a_reader_unwrapped(settings):
    fake = llm.FakeClaude(settings, {"CompanyFacts": {"does": [], "instruction_like": []}})
    with pytest.raises(llm.UnwrappedInput):
        fake.extract(CompanyFacts, "task", [hostile(FIXTURES / "sms.txt")])


@pytest.mark.skip(reason="Sprint 1: join-form import flags instruction_like rows")
def test_joinform_row_flagged_on_import(): ...


@pytest.mark.skip(reason="Sprint 4: compose output has no non-allowlisted link + fixed signature")
def test_compose_output_links_and_signature(): ...


@pytest.mark.skip(reason="Sprint 5: outbox refuses to send without approval and consent")
def test_outbox_refuses_without_approval_or_consent(): ...


@pytest.mark.skip(reason="Sprint 5: STOP in an inbound sets consent to no without a model call")
def test_inbound_stop_without_model(): ...
