"""`cloe draft <format>` and `cloe drafts …`: emails in Cloé's voice that Chloe reads,
approves and sends herself (Sprint 4, Monday scope). Nothing is sent from here."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cloe import compose, config, llm, records, workorders
from cloe.cmd_network import data_dir, open_db


def _err(msg: str) -> int:
    print(f"FAIL {msg}", file=sys.stderr)
    return 1


def cmd_draft(args: argparse.Namespace, settings: config.Settings) -> int:
    try:
        brief = compose.load_brief(Path(args.brief)) if args.brief else None
    except (OSError, ValueError) as exc:
        return _err(str(exc))
    conn = open_db(settings)
    try:
        company_ids = None
        if args.company:
            company_ids = []
            for query in args.company:
                found = records.lookup_company(conn, query)
                if len(found) != 1:
                    return _err(f"--company {query!r} matches {len(found)} companies")
                company_ids.append(found[0]["id"])
        try:
            chosen, skipped = compose.targets(conn, settings, args.format,
                                              company_ids=company_ids, email=args.person,
                                              brief=brief, limit=args.limit, lang=args.lang)
        except ValueError as exc:
            return _err(str(exc))
        for s in skipped:
            print(f"SKIP {s.email}: {s.reason}")
        if not chosen:
            print("OK   nobody to write to (see SKIP lines)")
            return 0
        engine = args.engine or settings.engine
        if engine == "workorder":
            path = workorders.write_draft_order(conn, workorders.WORKORDER_DIR, args.format,
                                                chosen, brief)
            print(f"OK   work order written for {len(chosen)} people: {path}")
            print("     ask Claude Code on the MacBook to run it, then: uv run cloe workorder "
                  f"ingest {path.name[:3]}")
            return 0
        if settings.fake_llm:
            reader = llm.FakeClaude(settings, {"Draft": _standins(chosen, brief)}, conn)
            engine = "standin"
        elif settings.anthropic_api_key:
            reader = llm.Claude(settings, conn)
        else:
            return _err("no ANTHROPIC_API_KEY: use --engine workorder (Claude Code on the "
                        "MacBook writes the drafts), or CLOE_FAKE=1 for a dry run")
        out = compose.compose(conn, reader, settings.canary, settings, chosen, brief,
                              engine=engine)
    finally:
        conn.close()
    print(f"OK   {len(out['drafts'])} drafts ready, {len(out['blocked'])} blocked by the "
          "tone.md checks" + (" — CLOE_FAKE=1: stand-in text, not for sending"
                              if engine == "standin" else ""))
    for e in out["errors"]:
        print(f"WARN {e}")
    print("     next: uv run cloe drafts review")
    return 0


def _standins(chosen, brief):
    return [compose.standin(t, brief) for t in chosen]


def cmd_list(args, settings):
    conn = open_db(settings)
    sql = ("SELECT m.id, m.format, m.status, m.lang, m.subject, p.email FROM message m JOIN "
           "person p ON p.id = m.person_id WHERE m.direction = 'out'")
    rows = conn.execute(sql + (" AND m.status = ?" if args.status else "") + " ORDER BY m.id",
                        (args.status,) if args.status else ()).fetchall()
    conn.close()
    for r in rows:
        print(f"#{r['id']:<4} {r['status']:<8} {r['format'] or '-':<10} {r['lang']}  "
              f"{r['email']:<32} {r['subject']}")
    print(f"{len(rows)} message{'s' if len(rows) != 1 else ''}")
    return 0


def _one(args, settings, fn):
    conn = open_db(settings)
    try:
        return fn(conn)
    except ValueError as exc:
        return _err(str(exc))
    finally:
        conn.close()


def cmd_show(args, settings):
    def go(conn):
        print(compose.render(compose.get(conn, args.id)), end="")
        return 0
    return _one(args, settings, go)


def cmd_review(args, settings):
    def go(conn):
        path, n = compose.review_file(conn, data_dir(settings) / "drafts")
        print(f"OK   {n} open drafts in {path} (keep it on this computer: it holds personal "
              "data)")
        return 0
    return _one(args, settings, go)


def cmd_approve(args, settings):
    def go(conn):
        by = compose.approve(conn, settings, args.id, args.by)
        print(f"OK   #{args.id} approved by {by}. Send it yourself, then: uv run cloe drafts "
              f"sent {args.id} --via email")
        return 0
    return _one(args, settings, go)


def cmd_sent(args, settings):
    def go(conn):
        compose.mark_sent(conn, args.id, args.via)
        print(f"OK   #{args.id} recorded as sent by {args.via}")
        return 0
    return _one(args, settings, go)


def cmd_reject(args, settings):
    def go(conn):
        compose.reject(conn, args.id)
        print(f"OK   #{args.id} rejected")
        return 0
    return _one(args, settings, go)


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("draft", help="write emails in Cloé's voice for Chloe to send")
    p.add_argument("format", choices=tuple(compose.FORMATS))
    p.add_argument("--company", action="append", help="only this company (repeatable)")
    p.add_argument("--person", help="only this email address")
    p.add_argument("--brief", help="the event brief for invite (see docs/events/TEMPLATE.json)")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--engine", choices=config.ENGINES, help="api: write here; workorder: "
                   "Claude Code on the MacBook writes them (default: CLOE_ENGINE)")
    p.add_argument("--lang", choices=("en", "nl"), help="override the person's language "
                   "(testing only)")
    p.set_defaults(func=cmd_draft)

    d = sub.add_parser("drafts", help="read, approve and record the drafts").add_subparsers(
        dest="action", required=True)
    p = d.add_parser("list", help="all messages")
    p.add_argument("--status", choices=("draft", "blocked", "approved", "sent"))
    p.set_defaults(func=cmd_list)
    p = d.add_parser("show", help="one draft, ready to copy")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_show)
    d.add_parser("review", help="every open draft in one file for Chloe").set_defaults(
        func=cmd_review)
    p = d.add_parser("approve", help="Chloe approves a draft")
    p.add_argument("id", type=int)
    p.add_argument("--by", help="the approver (an address in CLOE_APPROVERS)")
    p.set_defaults(func=cmd_approve)
    p = d.add_parser("sent", help="record that Chloe sent it herself")
    p.add_argument("id", type=int)
    p.add_argument("--via", required=True, choices=("email", "whatsapp"))
    p.set_defaults(func=cmd_sent)
    p = d.add_parser("reject", help="turn a draft down")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_reject)
