"""Contact language (team, 2026-10-20): default to English, offer Dutch; capture what people
tell us; an explicit choice beats a guess; Dutch is je unless they use u."""

from pathlib import Path

import pytest

from cloe import cli, db, language, people
from cloe.sources import joinform

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.migrate(c)
    return c


def person(conn, email="a@example.nl"):
    return people.upsert_person(conn, email, name="A")[0]


@pytest.mark.parametrize(("text", "lang"), [
    ("Wij zoeken een partner voor het sorteren van wol voor onze garenlijn.", "nl"),
    ("We are looking for a partner who can sort wool for our yarn line.", "en"),
    ("Hoi", None),
    ("", None),
    ("Textile recycling DPP", None),
])
def test_detect(text, lang):
    assert language.detect(text) == lang


def test_formality_and_choices():
    assert language.formality("Kunt u mij helpen met uw vraag?") == "u"
    assert language.formality("Kun je me helpen?") is None
    for value, code in (("Nederlands", "nl"), ("Dutch", "nl"), ("NL", "nl"),
                        ("English", "en"), ("Engels", "en"), ("Klingon", None), ("", None)):
        assert language.parse_choice(value) == code


def test_default_is_english_with_dutch_offered(conn):
    now = language.contact_language(conn, person(conn))
    assert (now.lang, now.formality, now.source, now.offer_dutch) == ("en", None, "default", True)
    assert now.describe() == "English, default: nothing captured yet; Cloé offers Dutch"


def test_explicit_beats_inferred_and_newest_explicit_wins(conn):
    pid = person(conn)
    assert language.set_language(conn, pid, "en", source="joinform_text", evidence="answers",
                                 at="2026-10-01T00:00:00+00:00")
    assert language.contact_language(conn, pid).offer_dutch  # a guess still offers Dutch
    assert language.set_language(conn, pid, "nl", source="manual", evidence="asked on the phone",
                                 at="2026-10-02T00:00:00+00:00")
    # a later guess never replaces an explicit choice
    assert not language.set_language(conn, pid, "en", source="joinform_text", evidence="x",
                                     at="2026-10-09T00:00:00+00:00")
    # an older explicit answer doesn't either; a newer one does
    assert not language.set_language(conn, pid, "en", source="joinform", evidence="form",
                                     at="2026-09-01T00:00:00+00:00")
    assert language.set_language(conn, pid, "en", source="inbound", evidence="replied in English",
                                 at="2026-10-15T00:00:00+00:00")
    now = language.contact_language(conn, pid)
    assert (now.lang, now.source, now.offer_dutch) == ("en", "inbound", False)
    events = conn.execute("SELECT detail FROM event WHERE action = 'language_set'").fetchall()
    assert len(events) == 3 and all("@" not in e[0] for e in events)


def test_repeats_change_nothing_and_formality(conn):
    pid = person(conn)
    assert language.set_language(conn, pid, "nl", source="manual", evidence="x", form="u")
    assert not language.set_language(conn, pid, "nl", source="manual", evidence="again")
    now = language.contact_language(conn, pid)
    assert (now.lang, now.formality, now.offer_dutch) == ("nl", "u", False)
    assert now.describe() == "Dutch (u), set by the team"
    language.set_language(conn, pid, "en", source="manual", evidence="y")
    assert language.contact_language(conn, pid).formality is None  # English has no je/u
    with pytest.raises(ValueError):
        language.set_language(conn, pid, "de", source="manual", evidence="z")
    with pytest.raises(ValueError):
        language.set_language(conn, pid, "nl", source="gossip", evidence="z")


def row(**values):
    cols = (*joinform.COLUMNS, *joinform.OPTIONAL_COLUMNS)
    return [list(cols), list((dict.fromkeys(cols, "") | values).values())]


def ingest(conn, tmp_path, *rows):
    header = rows[0][0]
    body = [r[1] for r in rows]
    return joinform.ingest(conn, {"Responses": [header, *body]}, raw_dir=tmp_path / "raw")


def test_join_form_capture(conn, tmp_path):
    base = {"trade_name": "Weverij", "website": "weverij.example", "consent_privacy": "Yes"}
    report = ingest(conn, tmp_path,
                    row(submitted_at="2026-10-01T10:00:00Z", email="nl@example.nl", **base,
                        question="Kunt u ons helpen met het vinden van een partner voor wol?"),
                    row(submitted_at="2026-10-01T11:00:00Z", email="en@example.nl", **base,
                        question="We are looking for a partner for our wool and the yarn."),
                    row(submitted_at="2026-10-01T12:00:00Z", email="short@example.nl", **base,
                        question="DPP"),
                    row(submitted_at="2026-10-01T13:00:00Z", email="chose@example.nl", **base,
                        question="We are looking for a partner for our wool and the yarn.",
                        preferred_language="Nederlands"))
    assert report.languages == 3 and "contact languages captured 3" in "\n".join(report.lines())

    def now(email):
        return language.contact_language(conn, people.get_person(conn, email)["id"])

    assert (now("nl@example.nl").lang, now("nl@example.nl").formality) == ("nl", "u")
    assert (now("en@example.nl").lang, now("en@example.nl").offer_dutch) == ("en", True)
    assert now("short@example.nl").source == "default"
    chose = now("chose@example.nl")
    assert (chose.lang, chose.source, chose.offer_dutch) == ("nl", "joinform", False)
    assert chose.evidence == "join form, submitted 2026-10-01T13:00:00Z"
    # importing the same rows again changes nothing
    assert ingest(conn, tmp_path, row(submitted_at="2026-10-01T10:00:00Z",
                                      email="nl@example.nl", **base,
                                      question="Kunt u ons helpen met het vinden van een "
                                      "partner voor wol?")).languages == 0
    # the person's export carries their language
    exported = people.export(conn, "chose@example.nl")["person"]
    assert (exported["lang"], exported["lang_source"]) == ("nl", "joinform")


def test_fixture_without_the_column_still_reads(conn, tmp_path):
    report = joinform.ingest(conn, joinform.read_file(FIXTURES / "joinform.csv"),
                             raw_dir=tmp_path / "raw")
    assert report.unknown_columns == [] and report.rows == 5


@pytest.fixture
def env(tmp_path, monkeypatch):
    for key in ("CLOE_DB", "CLOE_CANARY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text(f"CLOE_DB={tmp_path / 'data' / 'cloe.db'}\n")
    return path


def test_language_set_command(env, capsys, tmp_path):
    run = lambda *a: cli.main(["--env", str(env), *a])
    assert run("ingest", "joinform", str(FIXTURES / "joinform.csv")) == 0
    capsys.readouterr()
    assert run("language", "set", "anna@example.nl", "nl", "--evidence",
               "asked for Dutch on the phone, 2026-10-20") == 0
    assert "is written to in Dutch (je), set by the team" in capsys.readouterr().out
    assert run("language", "set", "anna@example.nl", "en", "--formality", "u",
               "--evidence", "x") == 1
    assert run("language", "set", "anna@example.nl", "nl", "--evidence", " ") == 1
    assert run("language", "set", "nobody@example.org", "nl", "--evidence", "x") == 1
    assert run("profile", "example.nl", "--no-write") == 0
    assert "language: Dutch (je), set by the team" in capsys.readouterr().out
