"""`cloe orchestrate`, after PONT's "Orkestreren als ontwerpcompetentie": the board, the check
against the model, suggestions from the network, and the collective memory."""

from pathlib import Path

import pytest

from cloe import cli, config, db, library, llm, people, scrape
from cloe import orchestrate as orch
from cloe.sources import funding, joinform, tell

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.migrate(c)
    return c


@pytest.fixture
def network(conn, tmp_path):
    """The Sprint 1 and 2 fixtures: join form, TELL, M-DPP sample with every project carded."""
    joinform.ingest(conn, joinform.read_file(FIXTURES / "joinform.csv"), raw_dir=tmp_path / "r")
    recs, _ = tell.read_export(FIXTURES / "tell.xlsx")
    tell.ingest(conn, recs, origin="tell.xlsx", digest="0" * 64)
    settings = config.load(tmp_path / ".env", environ={"CLOE_CANARY": "cloe-canary-orch"})
    reader = llm.FakeClaude(settings, {"DocumentCard": library.standin_card}, conn)
    refs, sources = funding.load(FIXTURES / "funding")
    scrape.scrape_funding(conn, refs, sources, None, reader, settings.canary, raw_dir=None,
                          max_projects=10, max_docs=0)
    return conn


def finding_texts(conn, slug, level="warn"):
    return [f.text for f in orch.check(conn, slug) if f.level == level]


def test_challenge_and_actors(conn):
    oid = orch.new_opgave(conn, "DPP Knitwear!", "DPP readiness for knitters", frame="frame")
    assert conn.execute("SELECT slug FROM opgave WHERE id = ?", (oid,)).fetchone()[0] == \
        "dpp-knitwear"
    with pytest.raises(orch.OrchestrateError, match="exists"):
        orch.new_opgave(conn, "dpp-knitwear", "again")
    aid, created = orch.set_actor(conn, "dpp-knitwear", "Provincie Overijssel",
                                  kind="government", level="macro", has_mandate=True)
    assert created
    before = conn.execute("SELECT status_at FROM orch_actor WHERE id = ?", (aid,)).fetchone()[0]
    again, created = orch.set_actor(conn, "dpp-knitwear", "Provincie Overijssel",
                                    status="involved", staging="opens the regional agenda")
    row = conn.execute("SELECT * FROM orch_actor WHERE id = ?", (aid,)).fetchone()
    assert (again, created, row["status"], row["kind"], row["has_mandate"]) == (
        aid, False, "involved", "government", 1)
    assert row["status_at"] >= before
    for bad in ({"kind": "alien"}, {"level": "cosmic"}, {"status": "maybe"}, {"colour": "x"}):
        with pytest.raises(orch.OrchestrateError):
            orch.set_actor(conn, "dpp-knitwear", "X", **bad)
    with pytest.raises(orch.OrchestrateError, match="no challenge"):
        orch.set_actor(conn, "nope", "X")


def test_empty_board_says_where_to_start(conn):
    orch.new_opgave(conn, "c", "A challenge")
    warns = finding_texts(conn, "c")
    assert any("No actors yet" in w for w in warns)
    assert any("No signals yet" in w for w in warns)
    assert any("No interventions yet" in w for w in warns)


def test_check_follows_the_model(conn):
    orch.new_opgave(conn, "c", "Sorting in Twente")
    orch.set_actor(conn, "c", "Sorter", kind="company", level="micro", status="involved")
    orch.set_actor(conn, "c", "Lab", kind="knowledge", level="micro", status="involved",
                   staging="tests fibre purity")
    orch.set_actor(conn, "c", "Gemeente", kind="government", level="micro")
    tension = orch.add_signal(conn, "c", "tension", "Sorters and recyclers distrust each "
                              "other's quality data", level="micro", actor="Sorter")
    pilot = orch.add_intervention(conn, "c", "Joint purity test", "use_space", kind="pilot",
                                  actors=["Lab"], status="planned")
    warns = finding_texts(conn, "c")
    assert any("Nobody with a formal mandate is involved" in w for w in warns)
    assert any("upper half of the model" in w for w in warns)
    assert any("Decide when to involve Gemeente" in w for w in warns)
    assert any("Say how Sorter can add value" in w for w in warns)
    assert any("Sorter: involved, but in no planned or done intervention" in w for w in warns)
    assert any(f"Open tension #{tension}" in w for w in warns)
    assert any("Only the micro level is in view" in w for w in warns)
    assert any("Only short-term steps" in w for w in warns)

    # fill in what the model asks for
    orch.set_actor(conn, "c", "Gemeente", status="involved", has_mandate=True, level="meso",
                   staging="links the pilot to the regional agenda")
    orch.set_actor(conn, "c", "Sorter", staging="shares sorting data")
    talk = orch.add_intervention(conn, "c", "Make the distrust discussable", "use_space",
                                 kind="workshop", actors=["Sorter", "Lab"], signal=tension,
                                 status="planned")
    orch.add_intervention(conn, "c", "Present the pilot at the regional board",
                          "timing_mandate", kind="meeting", actors=["Gemeente"],
                          follows=pilot, status="planned")
    orch.add_intervention(conn, "c", "Purity data in the regional circular agenda",
                          "make_space", actors=["Gemeente", "Sorter"], follows=talk)
    assert finding_texts(conn, "c") == []
    oks = finding_texts(conn, "c", "ok")
    assert any("Involved with a mandate: Gemeente" in t for t in oks)
    assert any("Levels in view: micro, meso" in t for t in oks)

    # done without a lesson → memory; done addresses the linked tension
    orch.set_intervention_status(conn, talk, "done")
    status = conn.execute("SELECT status FROM orch_signal WHERE id = ?", (tension,)).fetchone()
    assert status[0] == "addressed"
    expected = f"Done without a lesson: #{talk}. Record what worked and what didn't."
    assert finding_texts(conn, "c") == [expected]
    orch.add_lesson(conn, "c", "A shared purity sample made the data comparable",
                    kind="success", intervention=talk)
    assert finding_texts(conn, "c") == []


def test_interventions_validate_their_references(conn):
    orch.new_opgave(conn, "a", "A")
    orch.new_opgave(conn, "b", "B")
    other = orch.add_signal(conn, "b", "pattern", "elsewhere")
    with pytest.raises(orch.OrchestrateError, match="quadrant"):
        orch.add_intervention(conn, "a", "x", "middle")
    with pytest.raises(orch.OrchestrateError, match="no actor"):
        orch.add_intervention(conn, "a", "x", "use_space", actors=["Ghost"])
    with pytest.raises(orch.OrchestrateError, match="no signal"):
        orch.add_intervention(conn, "a", "x", "use_space", signal=other)
    with pytest.raises(orch.OrchestrateError, match="no intervention"):
        orch.set_intervention_status(conn, 999, "done")


def test_collective_memory_spans_challenges(conn):
    orch.new_opgave(conn, "brabant", "Sorting chain Brabant")
    orch.add_lesson(conn, "brabant", "Bring the province in after the first pilot, not before",
                    kind="insight")
    orch.add_lesson(conn, "brabant", "A workshop without sorting data stalled", kind="failure")
    orch.new_opgave(conn, "twente", "Sorting chain Twente", frame="pilot with the province")
    hits = orch.search_lessons(conn, "province pilot")
    assert [h["slug"] for h in hits] == ["brabant"] and "province" in hits[0]["text"]
    infos = finding_texts(conn, "twente", "info")
    assert any(i.startswith("Earlier lesson (brabant, insight)") for i in infos)
    assert orch.search_lessons(conn, "") == []


def test_suggest_from_the_network(network):
    orch.new_opgave(network, "dpp", "DPP readiness for small knitwear makers",
                    frame="digital product passport data for yarn and wool")
    found = orch.suggest(network, "dpp", k=3)
    kinds = [c.kind for c in found]
    assert kinds.index("company") < kinds.index("project")  # the network's companies first
    names = [c.name for c in found]
    assert "Voorbeeld Weverij B.V." in names and "KNITPASS" in names
    knit = next(c for c in found if c.name == "KNITPASS")
    assert knit.project_id and "research project" in knit.reason
    assert all("Ignore previous" not in c.reason for c in found)  # flagged text never used
    # actors already on the board are not suggested again
    orch.set_actor(network, "dpp", "KNITPASS", kind="project", project_id=knit.project_id)
    assert "KNITPASS" not in [c.name for c in orch.suggest(network, "dpp", k=3)]
    nwo = {"name": "ArtEZ University of the Arts", "type": ""}
    assert orch.org_kind(nwo) == "knowledge" and orch.org_kind({"type": "PRC"}) == "company"


def test_board_and_forget(network):
    orch.new_opgave(network, "dpp", "DPP | knitwear", region="Oost-Nederland")
    anna = people.get_person(network, "anna@example.nl")["id"]
    orch.set_actor(network, "dpp", "Anna", kind="company", person_id=anna, status="involved")
    text = orch.board(network, "dpp")
    for heading in ("## Actors: who, when, how", "## Signals", "### Timing & mandate",
                    "### Strategic orchestration", "### Using space with stakeholders",
                    "### Making space with stakeholders", "## Lessons",
                    "## Check against the orchestration model"):
        assert heading in text
    assert "DPP \\| knitwear" in text  # markdown is escaped
    people.forget(network, "anna@example.nl")
    row = network.execute("SELECT person_id FROM orch_actor WHERE name = 'Anna'").fetchone()
    assert row["person_id"] is None


@pytest.fixture
def env(tmp_path, monkeypatch):
    for key in ("CLOE_DB", "CLOE_CANARY", "ANTHROPIC_API_KEY", "CLOE_FAKE"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text(f"CLOE_DB={tmp_path / 'data' / 'cloe.db'}\nCLOE_FAKE=1\n")
    return path


def test_cli_flow(env, capsys):
    def run(*argv):
        return cli.main(["--env", str(env), *argv])

    assert run("ingest", "joinform", str(FIXTURES / "joinform.csv")) == 0
    assert run("scrape", "funding", "--fixture", str(FIXTURES / "funding"),
               "--max-projects", "8", "--max-docs-per-project", "0") == 0
    capsys.readouterr()
    assert run("orchestrate", "new", "dpp", "--title", "DPP readiness for knitwear",
               "--frame", "passport data for wool yarn", "--region", "Twente") == 0
    assert run("orchestrate", "suggest", "dpp") == 0
    out = capsys.readouterr().out
    assert "cloe orchestrate actor dpp" in out and "candidates" in out
    assert run("orchestrate", "actor", "dpp", "--company", "example.nl", "--level", "micro",
               "--status", "involved", "--staging", "brings a wool yarn line") == 0
    assert run("orchestrate", "actor", "dpp", "--project", "KNITPASS", "--status",
               "involved", "--staging", "brings the data model") == 0
    assert run("orchestrate", "actor", "dpp", "Provincie Overijssel", "--kind", "government",
               "--level", "macro", "--mandate", "--when", "after the studio") == 0
    assert run("orchestrate", "signal", "dpp", "tension", "Knitters fear the passport "
               "exposes their suppliers", "--level", "micro") == 0
    assert run("orchestrate", "intervention", "dpp", "Passport studio", "--quadrant",
               "use_space", "--kind", "workshop", "--actors",
               "Voorbeeld Weverij B.V.,KNITPASS", "--signal", "1", "--status", "planned") == 0
    assert run("orchestrate", "status", "1", "done") == 0
    assert run("orchestrate", "lesson", "dpp", "One shared passport made the fear concrete "
               "and smaller", "--kind", "success", "--intervention", "1") == 0
    capsys.readouterr()
    assert run("orchestrate", "lessons", "passport fear") == 0
    assert "One shared passport" in capsys.readouterr().out
    assert run("orchestrate", "check", "dpp", "--strict") == 1  # a mandate is still missing
    assert "Nobody with a formal mandate" in capsys.readouterr().out
    assert run("orchestrate", "show", "dpp") == 0
    out = capsys.readouterr().out
    assert "| Voorbeeld Weverij B.V. | company | micro |" in out
    assert "#1 [done · workshop] Passport studio" in out and "[success]" in out
    assert run("orchestrate", "list") == 0
    assert "dpp" in capsys.readouterr().out
    assert run("orchestrate", "show", "nothing") == 1
    assert run("orchestrate", "actor", "dpp", "--company", "nothing-like-this") == 1
