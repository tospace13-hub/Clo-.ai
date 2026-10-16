"""`cloe research <company>`: the dynamic profile (Sprint 3). Two engines, one contract:
`--engine api` does the research here (site crawl, registers, news, one reader call, one
web research call); `--engine workorder` writes `docs/workorders/NNN-research-<domain>.md`
for the MacBook, whose result `cloe workorder ingest NNN` merges the same way.
`--list-sources` prints the source catalogue with this company's URLs filled in."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from cloe import config, llm, records, research, workorders
from cloe.cmd_network import data_dir, open_db
from cloe.sources import fetch, registers, web

NO_READER = ("no ANTHROPIC_API_KEY: use --engine workorder (the MacBook does the research), "
             "or CLOE_FAKE=1 for a dry run with the keyword stand-in")


def _err(msg: str) -> int:
    print(f"FAIL {msg}")
    return 1


def make_researcher(settings: config.Settings, conn):
    """The reader for `cloe research`: the keyword stand-in under CLOE_FAKE=1, the API when
    a key is set, else None."""
    if settings.fake_llm:
        return llm.FakeClaude(settings, {"ResearchFindings": research.standin_findings,
                                         "research": llm.ResearchResult(text="")}, conn)
    if settings.anthropic_api_key:
        return llm.Claude(settings, conn)
    return None


def print_report(label: str, r: research.Report, *, verbose: bool = False) -> None:
    found = f" (found by {r.kvk_found_by})" if r.kvk_found_by not in (None, "known") else ""
    print(f"OK   {label}: KvK {r.kvk or 'unknown'}{found}")
    print(f"     pages: {r.pages} read, {r.pages_failed} not fetched · registers: {r.registers} "
          f"read, {r.registers_failed} failed, {len(r.registers_skipped)} skipped · "
          f"articles read: {r.articles}")
    print(f"     mentions: {r.mentions_new} new, {r.mentions_seen} seen · facts: {r.facts} new, "
          f"{r.facts_renewed} renewed · people {r.people} · needs {r.needs} · data {r.data}")
    print(f"     dropped (unlisted source): {len(r.dropped)} · flagged: {r.flagged} · "
          f"library matches proposed: {r.matches} · tokens: {r.usage}")
    for line in r.dropped:
        print(f"WARN {line}")
    for line in r.registers_skipped:
        print(f"     skipped {line}")
    if verbose:
        for line in r.errors:
            print(f"WARN {line}")
    elif r.errors:
        print(f"     {len(r.errors)} pages or registers not fetched (--verbose lists them)")


def _company(conn, query: str):
    matches = records.lookup_company(conn, query)
    if not matches:
        _err(f"no company matches {query!r} (try `cloe companies list`)")
        return None
    if len(matches) > 1:
        print(f"WARN {len(matches)} companies match; name one by id or domain:")
        for c in matches:
            print(f"     #{c['id']}  {c['name']}  {c['domain'] or '-'}  {c['city'] or '-'}")
        return None
    return matches[0]


def cmd_research(args: argparse.Namespace, settings: config.Settings) -> int:
    conn = open_db(settings)
    try:
        company = _company(conn, args.company)
        if company is None:
            return 1
        cid = company["id"]
        if args.kvk:
            kvk = re.sub(r"\D", "", args.kvk)
            if len(kvk) != 8:
                return _err("--kvk must be the 8-digit KvK number")
            research.apply_identity(conn, cid, {"kvk": kvk}, source_id=None,
                                    report=research.Report(), overwrite=True)
            conn.commit()
        subject = research.subject_of(conn, cid)
        if args.list_sources:
            print(f"# Sources for {subject.name} (KvK {subject.kvk or 'unknown'}, "
                  f"{subject.domain or 'no website'})")
            print("\n".join(registers.describe(subject)))
            return 0
        if args.engine == research.ENGINE_WORKORDER:
            existing = workorders.open_research_order(conn, cid)
            if existing and not args.refresh:
                print(f"OK   an open research work order exists: {existing} "
                      "(--refresh writes another)")
                return 0
            path = workorders.write_research_order(conn, workorders.WORKORDER_DIR, cid,
                                                   query=args.company)
            conn.commit()
            print(f"OK   work order written: {path}")
            print(f"     the MacBook writes {workorders.result_path(path).name}; then "
                  f"`cloe workorder ingest {path.name[:3]}`")
            return 0
        when = research.recently_researched(conn, cid)
        if when and not args.refresh:
            print(f"OK   {subject.name} was researched on {when}; --refresh runs it again")
            return 0
        claude = make_researcher(settings, conn)
        if claude is None:
            return _err(NO_READER)
        raw_dir = data_dir(settings) / "raw"
        fetcher = (fetch.FixtureFetcher(Path(args.fixture), raw_dir) if args.fixture
                   else fetch.Fetcher(raw_dir))
        try:
            report = research.research_company(
                conn, settings, claude, fetcher, cid, raw_dir=raw_dir, max_pages=args.max_pages,
                max_mentions=args.max_mentions,
                web_research=not args.fixture and not args.no_web)
        except llm.LLMError as exc:
            return _err(f"research stopped: {exc}")
        conn.commit()
        print_report(f"research {subject.name} ({subject.domain or 'no website'})", report,
                     verbose=args.verbose)
        return 0
    finally:
        conn.close()


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("research", help="research a company: its site, the registers, the news")
    p.add_argument("company", help="domain, name or id")
    p.add_argument("--engine", choices=(research.ENGINE_API, research.ENGINE_WORKORDER),
                   default=research.ENGINE_API)
    p.add_argument("--refresh", action="store_true",
                   help=f"run again although it ran in the last {research.REFRESH_DAYS} days")
    p.add_argument("--kvk", help="the company's KvK number (8 digits), if TELL did not have it")
    p.add_argument("--fixture", help="a folder with index.json instead of the web "
                                     "(tests/fixtures/site); implies --no-web")
    p.add_argument("--max-pages", type=int, default=web.DEFAULT_MAX_PAGES,
                   help="pages of the company's own site")
    p.add_argument("--max-mentions", type=int, default=research.DEFAULT_MAX_MENTIONS,
                   help="articles to read, newest first")
    p.add_argument("--no-web", action="store_true", help="skip the web research call")
    p.add_argument("--list-sources", action="store_true",
                   help="print the source catalogue for this company and stop")
    p.add_argument("--verbose", action="store_true", help="list every page not fetched")
    p.set_defaults(func=cmd_research)
