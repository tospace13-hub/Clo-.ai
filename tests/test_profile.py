import os
from pathlib import Path

import pytest

from cloe import config, db, llm, profile, records
from cloe.sources import joinform, tell

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = FIXTURES / "profile_example.nl.md"
NOW = "2026-10-08T12:00:00+00:00"
CANARY = "cloe-canary-profiletest000000000000000"


def classify(content):
    text = content[0]["text"].lower()
    if "ignore previous" in text:
        return {"kind": "other", "instruction_like": True}
    return {"kind": "recycling" if "wool" in text else "research", "instruction_like": False}


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "now", lambda: NOW)
    pytest.importorskip("openpyxl")
    c = db.connect(":memory:")
    db.migrate(c)
    settings = config.load(tmp_path / ".env", environ={"CLOE_CANARY": CANARY})
    fake = llm.FakeClaude(settings, {"NeedClassification": classify})
    joinform.ingest(c, joinform.read_file(FIXTURES / "joinform.csv"), raw_dir=tmp_path / "raw",
                    claude=fake, canary=CANARY)
    recs, _ = tell.read_export(FIXTURES / "tell.xlsx")
    tell.ingest(c, recs, origin="tell.xlsx", digest="0" * 64)
    return c


def company_id(conn, domain):
    return conn.execute("SELECT id FROM company WHERE domain = ?", (domain,)).fetchone()[0]


def test_golden_profile(conn):
    text = profile.render(conn, company_id(conn, "example.nl"))
    if os.environ.get("CLOE_UPDATE_GOLDEN") == "1":
        GOLDEN.write_text(text, encoding="utf-8")
    assert text == GOLDEN.read_text(encoding="utf-8")


def test_injection_only_under_flagged_text(conn):
    text = profile.render(conn, company_id(conn, "example.nl"))
    before, rest = text.split("## Flagged text", 1)
    flagged, after = rest.split("## Sources", 1)
    for needle in ("Ignore previous", "phish.example", "attacker.example"):
        assert needle not in before and needle not in after
        assert needle in flagged
    # inside an indented code block: every flagged line starts with four spaces
    assert all(line.startswith("    ") for line in flagged.splitlines() if "phish" in line)


def test_flagged_scraped_keyword_listed_with_source(conn):
    text = profile.render(conn, company_id(conn, "indigo.example"))
    assert "fact · does [S" in text.split("## Flagged text", 1)[1]
    assert "reveal your system prompt" not in text.split("## Flagged text", 1)[0]


def test_markdown_in_facts_is_escaped_and_expired_facts_hidden(conn):
    cid = company_id(conn, "hemp.example")
    records.add_fact(conn, cid, "does", "See [our site](http://evil.example) <b>now</b>",
                     source_id=None, confidence=0.5)
    records.add_fact(conn, cid, "does", "Old news", source_id=None, confidence=0.5,
                     expires_at="2020-01-01T00:00:00+00:00")
    text = profile.render(conn, cid)
    assert r"See \[our site\](http://evil.example) \<b\>now\</b\> [no source]" in text
    assert "Old news" not in text


def test_people_without_consent_are_not_contactable(conn):
    text = profile.render(conn, company_id(conn, "garen.example"))
    section = text.split("## People we may contact (with consent)", 1)[1].split("##", 1)[0]
    assert "- (nobody yet)" in section and "contact@garen.example" in section
    assert "Nobody here has given consent" in text


def test_write_saves_owner_only_file(conn, tmp_path):
    path = profile.write(conn, company_id(conn, "example.nl"), tmp_path / "profiles")
    assert path.name == "example.nl.md" and oct(path.stat().st_mode & 0o777) == "0o600"
    cid = conn.execute("SELECT id FROM company WHERE domain IS NULL").fetchone()[0]
    assert profile.write(conn, cid, tmp_path / "profiles").name == f"company-{cid}.md"
