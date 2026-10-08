"""The Sprint 1 commands, end to end through `cli.main` (Definition of Done flow)."""

import json
from pathlib import Path

import pytest

from cloe import cli, cmd_network, db, llm, people
from cloe.sources import sheets

FIXTURES = Path(__file__).parent / "fixtures"
JOINFORM = str(FIXTURES / "joinform.csv")
TELL = str(FIXTURES / "tell.xlsx")


@pytest.fixture
def env(tmp_path, monkeypatch):
    for key in ("CLOE_DB", "CLOE_CANARY", "ANTHROPIC_API_KEY", "CLOE_JOINFORM_SHEET_ID",
                "GOOGLE_SERVICE_ACCOUNT_FILE"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text(f"CLOE_DB={tmp_path / 'data' / 'cloe.db'}\nCLOE_SEND=0\n")
    return path


def run(env, *argv):
    return cli.main(["--env", str(env), *argv])


def connect(tmp_path):
    return db.connect(tmp_path / "data" / "cloe.db")


@pytest.fixture
def loaded(env, capsys):
    pytest.importorskip("openpyxl")
    assert run(env, "ingest", "joinform", JOINFORM) == 0
    assert run(env, "ingest", "tell", TELL) == 0
    capsys.readouterr()
    return env


def test_definition_of_done_flow(loaded, capsys, tmp_path):
    assert run(loaded, "profile", "example.nl") == 0
    out, err = capsys.readouterr()
    before, flagged = out.split("## Flagged text", 1)
    assert "Ignore previous" not in before and "Ignore previous" in flagged
    assert (tmp_path / "data" / "profiles" / "example.nl.md").exists()
    assert "saved to" in err

    assert run(loaded, "export", "injected@example.nl") == 0
    exported = json.loads(capsys.readouterr().out)
    assert exported["person"]["email"] == "injected@example.nl"
    assert len(exported["submissions"]) == 1 and exported["submissions"][0]["raw"]["question"]

    assert run(loaded, "forget", "injected@example.nl") == 0
    assert "forgotten: person 1" in capsys.readouterr().out
    assert run(loaded, "export", "injected@example.nl") == 1
    assert "not found" in capsys.readouterr().err
    assert not (tmp_path / "data" / "profiles" / "example.nl.md").exists()

    # a re-import does not bring them back, and the flagged need went with them
    assert run(loaded, "ingest", "joinform", JOINFORM) == 0
    assert "1 forgotten" in capsys.readouterr().out
    conn = connect(tmp_path)
    assert people.get_person(conn, "injected@example.nl") is None
    assert conn.execute("SELECT count(*) FROM need WHERE status='flagged'").fetchone()[0] == 0
    actions = [r[0] for r in conn.execute("SELECT action FROM event ORDER BY id")]
    assert actions.count("forget") == 1 and "export" in actions
    assert "@" not in "".join(r[0] for r in conn.execute("SELECT detail || ref FROM event"))


def test_forget_unknown_email_suppresses_future_imports(env, capsys, tmp_path):
    assert run(env, "forget", "bram@atelier.example") == 0
    assert "suppression list" in capsys.readouterr().out
    assert run(env, "ingest", "joinform", JOINFORM) == 0
    assert people.get_person(connect(tmp_path), "bram@atelier.example") is None


def test_consent_set(loaded, capsys, tmp_path):
    assert run(loaded, "consent", "set", "info@example.nl", "email", "cloe_updates", "yes",
               "--evidence", "said yes on the phone, 2026-10-08") == 0
    assert "OK   email/cloe_updates = yes" in capsys.readouterr().out
    conn = connect(tmp_path)
    pid = people.get_person(conn, "info@example.nl")["id"]
    assert people.current_consent(conn, pid, "email", "cloe_updates") == "yes"
    row = conn.execute("SELECT source, evidence FROM consent WHERE person_id = ?", (pid,)).fetchone()
    assert tuple(row) == ("manual", "said yes on the phone, 2026-10-08")

    assert run(loaded, "consent", "set", "info@example.nl", "sms", "followup", "yes",
               "--evidence", "x") == 0
    assert "no phone number" in capsys.readouterr().out
    assert run(loaded, "consent", "set", "nobody@example.org", "email", "followup", "yes",
               "--evidence", "x") == 1
    assert run(loaded, "consent", "set", "info@example.nl", "email", "followup", "yes",
               "--evidence", "  ") == 1
    with pytest.raises(SystemExit):
        run(loaded, "consent", "set", "info@example.nl", "fax", "followup", "yes",
            "--evidence", "x")


def test_companies_list_filters(loaded, capsys):
    assert run(loaded, "companies", "list") == 0
    assert capsys.readouterr().out.rstrip().endswith("10 companies")
    assert run(loaded, "companies", "list", "--city", "TILBURG") == 0
    assert capsys.readouterr().out.rstrip().endswith("3 companies")
    assert run(loaded, "companies", "list", "--tier", "yarn", "--needs") == 0
    out = capsys.readouterr().out
    assert "example.nl" in out and out.rstrip().endswith("1 company")


def test_profile_ambiguous_and_missing(loaded, capsys):
    assert run(loaded, "profile", "Weverij") == 0  # one match by name
    capsys.readouterr()
    assert run(loaded, "profile", "e") == 1
    assert "companies match" in capsys.readouterr().out
    assert run(loaded, "profile", "nothing-like-this") == 1


def test_ingest_joinform_classifies_with_the_engine(env, capsys, tmp_path, monkeypatch):
    def fake_engine(settings, conn, no_llm):
        return llm.FakeClaude(settings, {"NeedClassification": {
            "kind": "research", "instruction_like": False}}, conn)

    monkeypatch.setattr(cmd_network, "make_claude", fake_engine)
    assert run(env, "ingest", "joinform", JOINFORM) == 0
    out = capsys.readouterr().out
    assert "needs classified 3" in out and "WARN" not in out
    conn = connect(tmp_path)
    unclassified = "SELECT count(*) FROM need WHERE kind IS NULL AND status = 'open'"
    assert conn.execute(unclassified).fetchone()[0] == 0


def test_ingest_joinform_needs_a_source(env, capsys):
    assert run(env, "ingest", "joinform") == 1
    assert "CLOE_JOINFORM_SHEET_ID" in capsys.readouterr().err


def test_ingest_joinform_from_the_sheet(env, capsys, tmp_path, monkeypatch):
    from test_joinform import SHEET_ID, FakeSession, fixture_tabs

    key = tmp_path / "sa.json"
    key.write_text("{}")
    with env.open("a") as f:
        f.write(f"CLOE_JOINFORM_SHEET_ID={SHEET_ID}\nGOOGLE_SERVICE_ACCOUNT_FILE={key}\n")
    sess = FakeSession({"Responses": fixture_tabs()["Responses"]})
    monkeypatch.setattr(sheets, "session", lambda path: sess)
    assert run(env, "ingest", "joinform") == 0
    out = capsys.readouterr().out
    assert "from Google Sheet" in out and "5 new" in out
    assert run(env, "doctor") == 0
    assert "OK   join form: Google Sheet" in capsys.readouterr().out


def test_sheet_errors_fail_cleanly(env, capsys, monkeypatch):
    with env.open("a") as f:
        f.write("CLOE_JOINFORM_SHEET_ID=x\nGOOGLE_SERVICE_ACCOUNT_FILE=/nonexistent.json\n")
    assert run(env, "ingest", "joinform") == 1
    assert "service account key" in capsys.readouterr().err


def test_ingest_tell_needs_file_or_db(env, capsys):
    assert run(env, "ingest", "tell") == 1
    assert run(env, "ingest", "tell", "--db") == 1
    assert "TELL_DB_URL" in capsys.readouterr().err


def test_doctor_warns_when_sheet_not_configured(env, capsys):
    assert run(env, "doctor") == 0
    assert "WARN join form sheet not configured" in capsys.readouterr().out
