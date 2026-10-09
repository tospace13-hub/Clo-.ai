"""`cloe scrape funding|url`, `cloe library search|show|stats`, `cloe workorder ingest` — the
Sprint 2 commands."""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from cloe import config, library, llm, scrape, workorders
from cloe.cmd_network import data_dir, open_db
from cloe.sources import fetch


def _err(msg: str) -> int:
    print(f"FAIL {msg}", file=sys.stderr)
    return 1


def make_reader(settings: config.Settings, conn):
    """The engine that makes library cards: the keyword stand-in under CLOE_FAKE=1, the API
    when a key is set, else None."""
    if settings.fake_llm:
        return llm.FakeClaude(settings, {"DocumentCard": library.standin_card}, conn)
    if settings.anthropic_api_key:
        return llm.Claude(settings, conn)
    return None


NO_READER = ("no ANTHROPIC_API_KEY: use --engine workorder (the MacBook makes the cards), "
             "or CLOE_FAKE=1 for a dry run with the keyword stand-in")


def _fetcher(args: argparse.Namespace, raw_dir: Path):
    if args.fixture:
        return fetch.FixtureFetcher(Path(args.fixture), raw_dir)
    return fetch.Fetcher(raw_dir)


def cmd_scrape_funding(args: argparse.Namespace, settings: config.Settings) -> int:
    if args.max_projects < 1 or args.max_docs_per_project < 0:
        return _err("--max-projects must be ≥ 1 and --max-docs-per-project ≥ 0")
    conn = open_db(settings)
    try:
        if args.engine == "workorder":
            path = workorders.write_funding_batch(
                conn, workorders.WORKORDER_DIR, max_projects=args.max_projects,
                max_docs=args.max_docs_per_project)
            print(f"OK   work order written: {path}")
            print("     run it on the MacBook, then: uv run cloe workorder ingest "
                  f"{path.name[:3]}")
            return 0
        reader = make_reader(settings, conn)
        if reader is None:
            return _err(NO_READER)
        raw_dir = data_dir(settings) / "raw"
        try:
            fetcher = _fetcher(args, raw_dir)
        except fetch.FetchError as exc:
            return _err(str(exc))
        report = scrape.scrape_funding(conn, fetcher, reader, settings.canary, raw_dir=raw_dir,
                                       max_projects=args.max_projects,
                                       max_docs=args.max_docs_per_project)
    finally:
        conn.close()
    if not report.listed:
        for e in report.errors:
            print(f"WARN {e}")
        return _err("no projects found on the funding page")
    origin = f"fixture {args.fixture}" if args.fixture else "the web"
    print(f"OK   funding page from {origin}" + (" (CLOE_FAKE=1: keyword stand-in cards)"
                                               if settings.fake_llm else ""))
    for line in report.lines():
        print(f"     {line}" if not line.startswith("WARN") else line)
    return 0


def cmd_scrape_url(args: argparse.Namespace, settings: config.Settings) -> int:
    conn = open_db(settings)
    try:
        reader = make_reader(settings, conn)
        if reader is None:
            return _err(NO_READER)
        raw_dir = data_dir(settings) / "raw"
        try:
            fetcher = _fetcher(args, raw_dir)
        except fetch.FetchError as exc:
            return _err(str(exc))
        added, errors = scrape.scrape_url(conn, fetcher, reader, settings.canary, args.url,
                                          raw_dir=raw_dir)
    finally:
        conn.close()
    for e in errors:
        print(f"WARN {e}")
    if added is None or added.document_id is None:
        return _err(f"{args.url}: nothing added")
    print(f"OK   document #{added.document_id} ({added.status})")
    return 0


def cmd_library_search(args: argparse.Namespace, settings: config.Settings) -> int:
    conn = open_db(settings)
    hits = library.search(conn, args.query, args.k, tier=args.tier, topic=args.topic,
                          include_flagged=args.include_flagged)
    conn.close()
    for h in hits:
        flag = "  [flagged]" if h.flags else ""
        project = f" · {h.project}" if h.project else ""
        print(f"#{h.id}  {h.title}  ({h.doc_type}{project}){flag}")
        if h.one_line:
            print(textwrap.indent(textwrap.fill(h.one_line, 92), "     "))
        if h.url:
            print(f"     {h.url}")
    print(f"{len(hits)} card{'s' if len(hits) != 1 else ''}")
    return 0 if hits else 1


def cmd_library_show(args: argparse.Namespace, settings: config.Settings) -> int:
    conn = open_db(settings)
    doc = library.get(conn, args.id)
    conn.close()
    if doc is None:
        return _err(f"no document #{args.id}")
    card = doc["card"]
    print(f"# {doc['title']}")
    print(f"type {doc['doc_type']} · lang {doc['lang']} · published "
          f"{doc['published_at'] or '-'} · added {doc['added_at']}")
    if doc["acronym"]:
        print(f"project {doc['acronym']} — {doc['project_title']}"
              + (f" (CORDIS {doc['cordis_id']})" if doc["cordis_id"] else ""))
    print(f"source {doc['url']} ({doc['source_kind']}, fetched {doc['fetched_at']})")
    if doc["flags"]:
        print(f"FLAGS {doc['flags']}: writers skip this document")
    print()
    print(textwrap.fill(doc["one_line"] or "", 92))
    print()
    print(textwrap.fill(doc["summary"] or "", 92))
    for label, key in (("topics", "topics"), ("tags", "tags"), ("data offered", "data_offered"),
                       ("tiers", "relevant_tiers"), ("needs", "relevant_for_needs")):
        if card.get(key):
            print(f"{label}: {'; '.join(card[key])}")
    if args.body:
        print("\n--- text as read (untrusted) ---")
        print(doc["body"][:4000])
    return 0


def cmd_library_stats(args: argparse.Namespace, settings: config.Settings) -> int:
    conn = open_db(settings)
    s = library.stats(conn)
    conn.close()
    if args.json:
        print(json.dumps(s, indent=2))
        return 0
    rate = (f"{s['projects_on_cordis']}/{s['projects']}" if s["projects"] else "0/0")
    print(f"projects {s['projects']} (on CORDIS {rate}, with documents "
          f"{s['projects_with_documents']})")
    print(f"documents {s['documents']} (flagged {s['flagged']})")
    for title, key in (("by type", "by_type"), ("by language", "by_lang"),
                       ("top topics", "top_topics")):
        if s[key]:
            print(f"{title}: " + ", ".join(f"{k} {v}" for k, v in s[key].items()))
    return 0


def cmd_workorder_ingest(args: argparse.Namespace, settings: config.Settings) -> int:
    order = workorders.find(workorders.WORKORDER_DIR, args.number)
    if order is None:
        return _err(f"no work order {args.number} in {workorders.WORKORDER_DIR}")
    if "funding-batch" not in order.name:
        return _err(f"{order.name}: only funding-batch work orders can be ingested so far")
    result = Path(args.result) if args.result else workorders.result_path(order)
    if not result.is_file():
        return _err(f"no result at {result}")
    conn = open_db(settings)
    try:
        counts = workorders.ingest_funding_batch(conn, args.number, result,
                                                 raw_dir=data_dir(settings) / "raw")
    except ValueError as exc:
        return _err(f"{result.name}: {exc}")
    finally:
        conn.close()
    print(f"OK   work order {args.number}: {counts['projects']} projects, "
          f"{counts['documents']} documents ({counts['flagged']} flagged, "
          f"{counts['skipped']} skipped)")
    for e in counts["errors"]:
        print(f"WARN {e}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    scrape_p = sub.add_parser("scrape", help="fill the research library").add_subparsers(
        dest="what", required=True)
    p = scrape_p.add_parser("funding", help="EU projects from m-dpp.nl → CORDIS → documents")
    p.add_argument("--fixture", help="folder of saved pages with index.json (no web access)")
    p.add_argument("--max-projects", type=int, default=scrape.DEFAULT_MAX_PROJECTS)
    p.add_argument("--max-docs-per-project", type=int, default=scrape.DEFAULT_MAX_DOCS)
    p.add_argument("--engine", choices=("api", "workorder"), default="api",
                   help="api: fetch and card here; workorder: write a work order instead")
    p.set_defaults(func=cmd_scrape_funding)
    p = scrape_p.add_parser("url", help="one page or PDF into the library")
    p.add_argument("url")
    p.add_argument("--fixture", help="folder of saved pages with index.json (no web access)")
    p.set_defaults(func=cmd_scrape_url)

    lib = sub.add_parser("library", help="the research library").add_subparsers(
        dest="what", required=True)
    p = lib.add_parser("search", help="find cards")
    p.add_argument("query")
    p.add_argument("-k", type=int, default=10, help="how many cards (default 10)")
    p.add_argument("--tier", help="a tier slug, word or TELL tier label")
    p.add_argument("--topic", help="a topic slug or label")
    p.add_argument("--include-flagged", action="store_true")
    p.set_defaults(func=cmd_library_search)
    p = lib.add_parser("show", help="one card")
    p.add_argument("id", type=int)
    p.add_argument("--body", action="store_true", help="also print the text as read")
    p.set_defaults(func=cmd_library_show)
    p = lib.add_parser("stats", help="what the library holds")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_library_stats)

    wo = sub.add_parser("workorder", help="work orders (basic)").add_subparsers(
        dest="what", required=True)
    p = wo.add_parser("ingest", help="read a work order's result into Cloé")
    p.add_argument("number")
    p.add_argument("--result", help="result JSON (default: NNN-….result.json next to it)")
    p.set_defaults(func=cmd_workorder_ingest)
