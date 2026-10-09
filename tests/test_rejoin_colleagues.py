"""Team decisions of 2026-10-09: rejoiners, people kept individually, colleague links."""

from pathlib import Path

import pytest

from cloe import db, people, profile
from cloe.sources import joinform, tell

FIXTURES = Path(__file__).parent / "fixtures"
LATER = "2999-01-01T00:00:00Z"  # a submission made after any forget in these tests


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.migrate(c)
    return c


def tabs(*extra_rows):
    t = joinform.read_file(FIXTURES / "joinform.csv")
    t["Responses"] += [list(r) for r in extra_rows]
    return t


def row(**values):
    return list((dict.fromkeys(joinform.COLUMNS, "") | values).values())


def ingest(conn, tmp_path, t=None):
    return joinform.ingest(conn, t or tabs(), raw_dir=tmp_path / "raw")


def one(conn, sql, *args):
    return conn.execute(sql, args).fetchone()[0]


def test_people_from_one_company_kept_individually(conn, tmp_path):
    report = ingest(conn, tmp_path)
    company = conn.execute("SELECT * FROM company WHERE domain = 'example.nl'").fetchone()
    # the later submission (injected, "example.nl") did not overwrite the first one's details
    assert (company["name"], company["website"]) == ("Voorbeeld Weverij B.V.",
                                                    "https://www.example.nl/")
    # each person's answers stay facts of their own submission
    dpp = dict(conn.execute("SELECT text, source_id FROM fact WHERE kind = 'has_data' "
                            "AND company_id = ?", (company["id"],)).fetchall())
    assert len(dpp) == 2 and len(set(dpp.values())) == 2
    assert report.colleague_links == 1


def test_colleague_link_pending_until_both_say_yes(conn, tmp_path):
    ingest(conn, tmp_path)
    link = conn.execute("SELECT * FROM colleague_link").fetchone()
    anna = people.get_person(conn, "anna@example.nl")["id"]
    injected = people.get_person(conn, "injected@example.nl")["id"]
    assert (link["newcomer_id"], link["existing_id"]) == (injected, anna)
    assert (link["status"], link["newcomer_ok"], link["existing_ok"]) == (
        "detected", "unknown", "unknown")
    assert ingest(conn, tmp_path).colleague_links == 0  # idempotent
    # TELL contacts at the same company are not "registered": no link to info@
    recs, _ = tell.read_export(FIXTURES / "tell.xlsx")
    tell.ingest(conn, recs, origin="tell.xlsx", digest="0" * 64)
    third = row(submitted_at="2026-10-01T10:00:00Z", email="third@example.nl",
                trade_name="Voorbeeld Weverij", website="example.nl", city="Tilburg",
                consent_privacy="Yes")
    ingest(conn, tmp_path, tabs(third))
    pid = people.get_person(conn, "third@example.nl")["id"]
    linked = {r[0] for r in conn.execute(
        "SELECT existing_id FROM colleague_link WHERE newcomer_id = ?", (pid,))}
    assert linked == {anna, injected}


def test_export_shows_links_without_naming_the_colleague(conn, tmp_path):
    ingest(conn, tmp_path)
    links = people.export(conn, "injected@example.nl")["colleague_links"]
    assert [(lk["role"], lk["my_answer"], lk["status"]) for lk in links] == [
        ("newcomer", "unknown", "detected")]
    assert "anna" not in str(links).lower()


def test_rejoin_after_forget(conn, tmp_path, monkeypatch):
    ingest(conn, tmp_path)
    counts = people.forget(conn, "injected@example.nl")
    assert counts["colleague_links"] == 1
    assert one(conn, "SELECT count(*) FROM colleague_link") == 0

    # their old row is still in the sheet: it stays out
    report = ingest(conn, tmp_path)
    assert (report.forgotten, report.rejoined) == (1, 0)
    assert people.get_person(conn, "injected@example.nl") is None

    # an undated new row cannot be told apart from an old one: it stays out too
    undated = row(submitted_at="soon", email="injected@example.nl", trade_name="Voorbeeld",
                  website="example.nl", consent_privacy="Yes")
    assert ingest(conn, tmp_path, tabs(undated)).forgotten == 2

    # a submission made after the forget is a rejoin
    again = row(submitted_at=LATER, name="Injected Again", email="Injected@example.nl",
                role="Buyer", trade_name="Voorbeeld Weverij", website="example.nl",
                city="Tilburg", question="Looking for wool sorting partners",
                consent_privacy="Yes", consent_newsletter="Yes")
    report = ingest(conn, tmp_path, tabs(again))
    assert (report.rejoined, report.forgotten, report.colleague_links) == (1, 1, 1)
    person = people.get_person(conn, "injected@example.nl")
    assert (person["name"], person["flags"]) == ("Injected Again", "rejoined")
    assert people.current_consent(conn, person["id"], "email", "newsletter") == "yes"
    assert one(conn, "SELECT count(*) FROM event WHERE action = 'rejoin'") == 1
    # only the new submission came back, not the old flagged question
    assert one(conn, "SELECT count(*) FROM need WHERE status = 'flagged'") == 0
    assert len(people.export(conn, "injected@example.nl")["submissions"]) == 1

    report = ingest(conn, tmp_path, tabs(again))  # idempotent
    assert (report.rejoined, report.new, report.colleague_links) == (0, 0, 0)

    text = profile.render(conn, person["company_id"])
    assert "rejoined after being forgotten" in text


def test_rejoined_person_can_be_matched_by_tell_again(conn, tmp_path):
    ingest(conn, tmp_path)
    people.forget(conn, "lotte@vezel.example")
    recs, _ = tell.read_export(FIXTURES / "tell.xlsx")
    assert tell.ingest(conn, recs, origin="t", digest="1" * 64).emails_forgotten == 1
    again = row(submitted_at=LATER, email="lotte@vezel.example", trade_name="Vezel Lab",
                website="https://vezel.example", consent_privacy="Yes")
    ingest(conn, tmp_path, tabs(again))
    assert tell.ingest(conn, recs, origin="t", digest="2" * 64).emails_forgotten == 0


def test_forgetting_again_moves_the_date(conn, monkeypatch):
    monkeypatch.setattr(db, "now", lambda: "2026-10-01T00:00:00+00:00")
    people.forget(conn, "x@example.org")
    monkeypatch.setattr(db, "now", lambda: "2026-11-01T00:00:00+00:00")
    people.forget(conn, "x@example.org")
    assert people.forgotten_at(conn, "x@example.org") == "2026-11-01T00:00:00+00:00"
