"""`cloe orchestrate …` — orchestrating a challenge (opgave) after PONT's "Orkestreren als
ontwerpcompetentie" (see `orchestrate.py`). Nothing here contacts anyone."""

from __future__ import annotations

import argparse
import sys

from cloe import config, orchestrate, records
from cloe.cmd_network import open_db


def _err(msg: str) -> int:
    print(f"FAIL {msg}", file=sys.stderr)
    return 1


def _run(settings: config.Settings, fn) -> int:
    conn = open_db(settings)
    try:
        return fn(conn)
    except orchestrate.OrchestrateError as exc:
        return _err(str(exc))
    finally:
        conn.close()


def cmd_new(args, settings):
    def go(conn):
        orchestrate.new_opgave(conn, args.slug, args.title, frame=args.frame or "",
                               region=args.region or "")
        print(f"OK   challenge {orchestrate.slugify(args.slug)}: next, add actors "
              f"(`cloe orchestrate suggest {orchestrate.slugify(args.slug)}` finds some)")
        return 0
    return _run(settings, go)


def cmd_list(args, settings):
    def go(conn):
        rows = conn.execute(
            "SELECT o.*, (SELECT count(*) FROM orch_actor a WHERE a.opgave_id = o.id) AS actors,"
            " (SELECT count(*) FROM orch_intervention i WHERE i.opgave_id = o.id AND "
            "i.status != 'dropped') AS interventions FROM opgave o ORDER BY o.updated_at DESC"
        ).fetchall()
        for r in rows:
            print(f"{r['slug']:<28} {r['status']:<7} {r['actors']:>3} actors "
                  f"{r['interventions']:>3} interventions  {r['title']}")
        print(f"{len(rows)} challenge{'s' if len(rows) != 1 else ''}")
        return 0
    return _run(settings, go)


def cmd_show(args, settings):
    def go(conn):
        print(orchestrate.board(conn, args.slug), end="")
        return 0
    return _run(settings, go)


def cmd_check(args, settings):
    def go(conn):
        findings = orchestrate.check(conn, args.slug)
        for f in findings:
            print(f"{f.level.upper():<4} [{f.component}] {f.text}")
        return 1 if any(f.level == "warn" for f in findings) and args.strict else 0
    return _run(settings, go)


def cmd_actor(args, settings):
    def go(conn):
        company_id = project_id = None
        name = args.name
        kind = args.kind
        if args.company:
            matches = records.lookup_company(conn, args.company)
            if len(matches) != 1:
                return _err(f"--company {args.company!r} matches {len(matches)} companies; "
                            "name one by id or domain")
            company_id, name, kind = matches[0]["id"], name or matches[0]["name"], kind or "company"
        if args.project:
            p = conn.execute("SELECT * FROM project WHERE ext_id = ? OR acronym = ? COLLATE "
                             "NOCASE OR cordis_id = ?", (args.project,) * 3).fetchall()
            if len(p) != 1:
                return _err(f"--project {args.project!r} matches {len(p)} projects")
            project_id = p[0]["id"]
            name, kind = name or p[0]["acronym"] or p[0]["title"], kind or "project"
        if not name:
            return _err("give the actor a name, or --company / --project")
        aid, created = orchestrate.set_actor(
            conn, args.slug, name, kind=kind, level=args.level,
            has_mandate=True if args.mandate else (False if args.no_mandate else None),
            interest=args.interest, timeline=args.timeline, involve_when=args.when,
            staging=args.staging, status=args.status, company_id=company_id,
            project_id=project_id)
        print(f"OK   actor #{aid} {name} {'added' if created else 'updated'}")
        return 0
    return _run(settings, go)


def cmd_signal(args, settings):
    def go(conn):
        if args.status:
            orchestrate.set_signal_status(conn, int(args.kind_or_id), args.status)
            print(f"OK   signal #{args.kind_or_id} {args.status}")
            return 0
        if not args.text:
            return _err("give the signal's text")
        sid = orchestrate.add_signal(conn, args.slug, args.kind_or_id, args.text,
                                     level=args.level, actor=args.actor)
        print(f"OK   signal #{sid}")
        return 0
    return _run(settings, go)


def cmd_intervention(args, settings):
    def go(conn):
        iid = orchestrate.add_intervention(
            conn, args.slug, args.title, args.quadrant, kind=args.kind, value=args.value or "",
            planned_for=args.when or "", status=args.status,
            actors=[a.strip() for a in (args.actors or "").split(",") if a.strip()],
            follows=args.follows, signal=args.signal)
        q = orchestrate.QUADRANTS[args.quadrant]
        print(f"OK   intervention #{iid} in {q['label']} ({q['pont']})")
        return 0
    return _run(settings, go)


def cmd_status(args, settings):
    def go(conn):
        orchestrate.set_intervention_status(conn, args.id, args.status)
        print(f"OK   intervention #{args.id} {args.status}")
        if args.status == "done":
            print("     record what was learned: cloe orchestrate lesson <challenge> \"…\" "
                  f"--intervention {args.id}")
        return 0
    return _run(settings, go)


def cmd_lesson(args, settings):
    def go(conn):
        lid = orchestrate.add_lesson(conn, args.slug, args.text, kind=args.kind,
                                     intervention=args.intervention)
        print(f"OK   lesson #{lid} kept in the collective memory")
        return 0
    return _run(settings, go)


def cmd_lessons(args, settings):
    def go(conn):
        rows = orchestrate.search_lessons(conn, args.query, args.k)
        for r in rows:
            print(f"#{r['id']}  [{r['kind']}] {r['text']}  ({r['slug']})")
        print(f"{len(rows)} lesson{'s' if len(rows) != 1 else ''}")
        return 0 if rows else 1
    return _run(settings, go)


def cmd_suggest(args, settings):
    def go(conn):
        found = orchestrate.suggest(conn, args.slug, args.k)
        for c in found:
            ref = f" --company {c.company_id}" if c.company_id else (
                f" --project {c.project_id}" if c.project_id else "")
            print(f"- {c.name} ({c.kind}): {c.reason}")
            print(f"    cloe orchestrate actor {orchestrate.slugify(args.slug)} "
                  f"\"{c.name}\" --kind {c.kind}{ref}")
        print(f"{len(found)} candidate{'s' if len(found) != 1 else ''}")
        return 0
    return _run(settings, go)


def cmd_load(args, settings):
    from pathlib import Path

    def go(conn):
        path = Path(args.file)
        if not path.is_file() or path.stat().st_size > 1_000_000:
            return _err(f"{path}: not a seed file (missing, or larger than 1 MB)")
        counts = orchestrate.load_seed(conn, path.read_bytes())
        print(f"OK   loaded {path.name}: +{counts['challenges']} challenges, "
              f"+{counts['actors']} actors, +{counts['signals']} signals (existing ones kept "
              "as the team left them)")
        return 0
    return _run(settings, go)


def cmd_propose(args, settings):
    from cloe import llm, workorders

    def go(conn):
        if (args.engine or settings.engine) == "workorder":
            path = workorders.write_proposal_order(conn, workorders.WORKORDER_DIR, args.slug)
            print(f"OK   work order written: {path}")
            print(f"     its inputs are in {workorders.private_path(path).name} (not in git)")
            return 0
        if settings.fake_llm:
            reader = llm.FakeClaude(settings, {"OrchestrationProposal":
                                               orchestrate.standin_proposal(conn, args.slug)},
                                    conn)
            engine = "standin"
        elif settings.anthropic_api_key:
            reader, engine = llm.Claude(settings, conn), "api"
        else:
            return _err("no ANTHROPIC_API_KEY: use --engine workorder (the MacBook proposes), "
                        "or CLOE_FAKE=1 for a dry run with the stand-in")
        counts = orchestrate.propose(conn, args.slug, reader, settings.canary, engine=engine)
        print(f"OK   proposed {counts['signals']} signals and {counts['interventions']} "
              f"interventions ({counts['dropped']} dropped by the checks, "
              f"{counts['duplicates']} already known)"
              + (" — CLOE_FAKE=1: stand-in, not Cloé's judgement" if engine == "standin"
                 else ""))
        print(f"     review: cloe orchestrate proposals {orchestrate.slugify(args.slug)}")
        return 0
    return _run(settings, go)


def cmd_proposals(args, settings):
    def go(conn):
        rows = orchestrate.proposals(conn, args.slug, args.status)
        for r in rows:
            item = r["item"]
            if r["kind"] == "signal":
                head = f"[{item['kind']} · {item['level']}] {item['text']}"
                extra = [f"actors: {', '.join(item['actors'])}" if item["actors"] else "",
                         f"evidence: {', '.join(item['evidence'])}" if item["evidence"] else ""]
            else:
                q = orchestrate.QUADRANTS[item["quadrant"]]
                head = f"[{q['label']} · {item['kind']}] {item['title']}"
                extra = [f"value: {item['value']}" if item["value"] else "",
                         f"with: {', '.join(item['actors'])}" if item["actors"] else "",
                         f"addresses: {item['addresses']}" if item["addresses"] else "",
                         f"when: {item['when']}" if item["when"] else "",
                         f"why: {item['why']}" if item["why"] else ""]
            print(f"#{r['id']} {r['kind']} ({r['engine']}): {head}")
            for line in filter(None, [*extra, item.get("warning", "")]):
                print(f"     {line}")
        print(f"{len(rows)} {args.status} proposal{'s' if len(rows) != 1 else ''}")
        if rows and args.status == "proposed":
            print("     cloe orchestrate accept <id> … / cloe orchestrate reject <id> …")
        return 0
    return _run(settings, go)


def _decide(args, settings, accept: bool):
    def go(conn):
        for pid in args.ids:
            ref = orchestrate.decide(conn, pid, accept)
            print(f"OK   proposal #{pid} " + (f"accepted: {ref}" if accept else "rejected"))
        return 0
    return _run(settings, go)


def cmd_accept(args, settings):
    return _decide(args, settings, True)


def cmd_reject(args, settings):
    return _decide(args, settings, False)


def register(sub: argparse._SubParsersAction) -> None:
    orch = sub.add_parser("orchestrate", help="orchestrate a challenge (PONT: orkestreren)"
                          ).add_subparsers(dest="action", required=True)
    p = orch.add_parser("new", help="start a challenge (opgave)")
    p.add_argument("slug")
    p.add_argument("--title", required=True)
    p.add_argument("--frame", help="how the challenge is framed")
    p.add_argument("--region")
    p.set_defaults(func=cmd_new)
    orch.add_parser("list", help="all challenges").set_defaults(func=cmd_list)
    p = orch.add_parser("show", help="the board: actors, signals, interventions, lessons, "
                        "check")
    p.add_argument("slug")
    p.set_defaults(func=cmd_show)
    p = orch.add_parser("check", help="read the board against the orchestration model")
    p.add_argument("slug")
    p.add_argument("--strict", action="store_true", help="exit 1 when anything is missing")
    p.set_defaults(func=cmd_check)

    p = orch.add_parser("actor", help="add or update an actor: who, when, how")
    p.add_argument("slug")
    p.add_argument("name", nargs="?", default="")
    p.add_argument("--kind", choices=orchestrate.ACTOR_KINDS)
    p.add_argument("--company", help="link a company in the network (id, domain or name)")
    p.add_argument("--project", help="link a research project (ext_id, acronym, CORDIS id)")
    p.add_argument("--level", choices=orchestrate.LEVELS)
    mandate = p.add_mutually_exclusive_group()
    mandate.add_argument("--mandate", action="store_true", help="has a formal mandate")
    mandate.add_argument("--no-mandate", action="store_true")
    p.add_argument("--interest", help="what they care about")
    p.add_argument("--timeline", help="their own rhythm and deadlines")
    p.add_argument("--when", help="when to involve them (stakeholder timing)")
    p.add_argument("--staging", help="how their input adds value (stakeholder staging)")
    p.add_argument("--status", choices=orchestrate.ACTOR_STATUSES)
    p.set_defaults(func=cmd_actor)

    p = orch.add_parser("signal", help="record a pattern, tension, opportunity or blockage "
                        "(or --status for an existing one)")
    p.add_argument("slug")
    p.add_argument("kind_or_id", help=f"one of {', '.join(orchestrate.SIGNAL_KINDS)}, or a "
                   "signal id with --status")
    p.add_argument("text", nargs="?", default="")
    p.add_argument("--level", choices=orchestrate.LEVELS, default="meso")
    p.add_argument("--actor")
    p.add_argument("--status", choices=("open", "addressed", "dropped"))
    p.set_defaults(func=cmd_signal)

    p = orch.add_parser("intervention", help="place an intervention in the model")
    p.add_argument("slug")
    p.add_argument("title")
    p.add_argument("--quadrant", required=True, choices=tuple(orchestrate.QUADRANTS),
                   help="timing_mandate · strategic · use_space · make_space")
    p.add_argument("--kind", choices=orchestrate.INTERVENTION_KINDS, default="other")
    p.add_argument("--value", help="the value it should bring")
    p.add_argument("--when")
    p.add_argument("--status", choices=orchestrate.INTERVENTION_STATUSES, default="idea")
    p.add_argument("--actors", help="comma-separated actor names")
    p.add_argument("--follows", type=int, help="the intervention this one builds on")
    p.add_argument("--signal", type=int, help="the signal (tension) it addresses")
    p.set_defaults(func=cmd_intervention)

    p = orch.add_parser("status", help="set an intervention's status")
    p.add_argument("id", type=int)
    p.add_argument("status", choices=orchestrate.INTERVENTION_STATUSES)
    p.set_defaults(func=cmd_status)

    p = orch.add_parser("lesson", help="keep a lesson in the collective memory")
    p.add_argument("slug")
    p.add_argument("text")
    p.add_argument("--kind", choices=orchestrate.LESSON_KINDS, default="insight")
    p.add_argument("--intervention", type=int)
    p.set_defaults(func=cmd_lesson)

    p = orch.add_parser("lessons", help="search lessons across all challenges")
    p.add_argument("query")
    p.add_argument("-k", type=int, default=10)
    p.set_defaults(func=cmd_lessons)

    p = orch.add_parser("propose", help="AI: propose tensions and interventions (the "
                        "team accepts or rejects them)")
    p.add_argument("slug")
    p.add_argument("--engine", choices=("api", "workorder"),
                   help="api: propose here; workorder: write a work order (default: CLOE_ENGINE)")
    p.set_defaults(func=cmd_propose)
    p = orch.add_parser("proposals", help="proposals waiting for the team")
    p.add_argument("slug")
    p.add_argument("--status", choices=("proposed", "accepted", "rejected"),
                   default="proposed")
    p.set_defaults(func=cmd_proposals)
    for name, func, help_text in (("accept", cmd_accept, "put proposals on the board"),
                                  ("reject", cmd_reject, "turn proposals down")):
        p = orch.add_parser(name, help=help_text)
        p.add_argument("ids", type=int, nargs="+")
        p.set_defaults(func=func)

    p = orch.add_parser("load", help="set up challenges from a seed file (adds only what "
                        "is missing)")
    p.add_argument("file")
    p.set_defaults(func=cmd_load)

    p = orch.add_parser("suggest", help="candidate actors from Cloé's network")
    p.add_argument("slug")
    p.add_argument("-k", type=int, default=8)
    p.set_defaults(func=cmd_suggest)
