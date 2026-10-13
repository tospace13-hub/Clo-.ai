"""`cloe scrape funding` and `cloe scrape url`: datasets and pages → projects and cards.

`scrape funding` imports every project of M-DPP's research-funding network
(`sources/funding.py`), with no model calls. It then cards the most textile-specific ones:
the abstract becomes a `project_page` document, followed by up to M deliverables and
publications. For CORDIS projects those come from the project's results page; for NWO
projects, from its open-access publications.

The fetcher is the guarded `fetch.Fetcher` (live, on the MacBook) or `fetch.FixtureFetcher`
(saved pages). The reader is the API, or FakeClaude with the offline stand-in. Without a
reader, projects are imported and nothing is carded. One failed fetch or card never stops
the run; it is counted.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from cloe import db, library, records
from cloe.sources import cordis, fetch
from cloe.sources.funding import SOURCE_LABELS, ProjectRef, priority

DEFAULT_MAX_PROJECTS = 3
DEFAULT_MAX_DOCS = 5
RESULT_TO_DOC_TYPE = {"deliverable": "deliverable", "publication": "publication",
                      "report": "report", "other": "other"}


@dataclass
class Report:
    sources: dict[str, tuple[int, int]] = field(default_factory=dict)
    imported: int = 0
    projects_new: int = 0
    flagged_projects: int = 0
    carded: int = 0
    documents: Counter = field(default_factory=Counter)
    by_type: Counter = field(default_factory=Counter)
    not_saved: int = 0
    errors: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        src = ", ".join(f"{kept} {SOURCE_LABELS.get(s, s)} (of {total})"
                        for s, (total, kept) in self.sources.items())
        docs = ", ".join(f"{n} {s}" for s, n in sorted(self.documents.items())) or "none"
        types = ", ".join(f"{n} {t}" for t, n in self.by_type.most_common()) or "none"
        out = [
            f"projects imported {self.imported} ({self.projects_new} new): {src}",
            f"projects carded {self.carded} (the most textile-specific first)",
            f"documents: {docs}",
            f"document types: {types}",
        ]
        if self.not_saved:
            out.append(f"pages the fixture has no copy of: {self.not_saved}")
        if self.flagged_projects:
            out.append(f"projects with flagged text: {self.flagged_projects}")
        out += [f"WARN {e}" for e in self.errors]
        return out


def source_kind(url: str, content_type: str) -> str:
    if content_type == "application/pdf":
        return "pdf"
    if (urlsplit(url).hostname or "").endswith("cordis.europa.eu"):
        return "cordis"
    return "web"


def _get(fetcher, url: str, report: Report) -> fetch.Fetched | None:
    try:
        return fetcher.fetch(url)
    except fetch.FetchError as exc:
        if str(exc).startswith("not in the fixture index"):
            report.not_saved += 1
        else:
            report.errors.append(f"not fetched: {url} ({exc})")
        return None


def _source(conn: sqlite3.Connection, got: fetch.Fetched, raw_dir: Path | None) -> int:
    kind = source_kind(got.final_url, got.content_type)
    if raw_dir is not None:
        sid, _ = records.upsert_source(conn, kind, got.url, raw=got.content, raw_dir=raw_dir)
    else:
        sid, _ = records.upsert_source(conn, kind, got.url, digest=got.sha256)
    return sid


def upsert_project(conn: sqlite3.Connection, ref: ProjectRef) -> tuple[int, bool]:
    """One row per `ext_id`, else per CORDIS id, acronym or title. The dataset is the
    authority for a project's facts; Dutch partners are merged."""
    row = None
    if ref.ext_id:
        row = conn.execute("SELECT * FROM project WHERE ext_id = ?", (ref.ext_id,)).fetchone()
    if row is None and ref.cordis_id:
        row = conn.execute("SELECT * FROM project WHERE cordis_id = ?",
                           (ref.cordis_id,)).fetchone()
    if row is None and ref.acronym:
        row = conn.execute("SELECT * FROM project WHERE acronym = ? COLLATE NOCASE AND "
                           "ext_id IS NULL AND cordis_id IS NULL", (ref.acronym,)).fetchone()
    url = ref.urls[0] if ref.urls else (cordis.project_url(ref.cordis_id) if ref.cordis_id
                                        else None)
    orgs = [o.model_dump() for o in ref.nl_orgs]
    values = (ref.acronym, ref.title or ref.acronym or "(untitled)", ref.programme,
              ref.cordis_id, url, ref.start_date, ref.end_date, ref.ext_id, ref.funding_scheme,
              ref.ec_grant, json.dumps(ref.keywords, ensure_ascii=False),
              json.dumps(orgs, ensure_ascii=False))
    if row is None:
        cur = conn.execute(
            "INSERT INTO project(acronym, title, programme, cordis_id, url, start_date, "
            "end_date, ext_id, funding_scheme, ec_grant, keywords_json, nl_orgs_json, "
            "partners_nl_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*values, json.dumps(ref.partners_nl, ensure_ascii=False)))
        return cur.lastrowid, True
    merged = list(dict.fromkeys([*json.loads(row["partners_nl_json"] or "[]"),
                                 *ref.partners_nl]))
    conn.execute(
        "UPDATE project SET acronym = coalesce(?, acronym), title = ?, "
        "programme = coalesce(?, programme), cordis_id = coalesce(?, cordis_id), "
        "url = coalesce(?, url), start_date = coalesce(?, start_date), "
        "end_date = coalesce(?, end_date), ext_id = coalesce(?, ext_id), "
        "funding_scheme = coalesce(?, funding_scheme), ec_grant = coalesce(?, ec_grant), "
        "keywords_json = ?, nl_orgs_json = ?, partners_nl_json = ? WHERE id = ?",
        (*values, json.dumps(merged, ensure_ascii=False), row["id"]))
    return row["id"], False


def project_text(ref: ProjectRef) -> str:
    """A project as the reader sees it: the dataset's fields, nothing else."""
    years = "–".join(d for d in (ref.start_date, ref.end_date) if d)
    head = " · ".join(x for x in (ref.acronym, ref.programme, ref.funding_scheme, years) if x)
    parts = [f"# {ref.title}", head, "## Objective", ref.abstract]
    if ref.keywords:
        parts.append("Keywords: " + ", ".join(ref.keywords))
    if ref.nl_orgs:
        parts.append("Dutch partners: " + "; ".join(
            f"{o.name} ({', '.join(x for x in (o.type, o.role) if x)})" if o.type or o.role
            else o.name for o in ref.nl_orgs))
    return "\n\n".join(p for p in parts if p)


def _card_text(conn, claude, canary, report, *, sid, text, project_id, doc_type,
               title_hint) -> None:
    added = library.add_document(conn, claude, canary, source_id=sid, text=text,
                                 project_id=project_id, doc_type=doc_type,
                                 title_hint=title_hint)
    report.documents[added.status] += 1
    if added.status in ("new", "updated", "flagged"):
        report.by_type[doc_type] += 1
    if added.status in ("error", "skipped"):
        report.errors.append(f"no card for source {sid} ({added.detail})")


def _card(conn, claude, canary, report, *, got, raw_dir, project_id, doc_type,
          title_hint) -> None:
    sid = _source(conn, got, raw_dir)
    try:
        body = fetch.to_text(got)
    except fetch.FetchError as exc:
        report.errors.append(f"no text from {got.url} ({exc})")
        report.documents["error"] += 1
        return
    _card_text(conn, claude, canary, report, sid=sid, text=body, project_id=project_id,
               doc_type=doc_type, title_hint=title_hint)


def scrape_project(conn, fetcher, claude, canary, ref: ProjectRef, project_id: int,
                   report: Report, *, raw_dir: Path | None, max_docs: int) -> None:
    """Card one project: its abstract, then its research material."""
    record = ref.model_dump_json().encode("utf-8")
    kind = "cordis" if ref.source == "cordis" else "web"
    url = ref.urls[0] if ref.urls else f"mdpp:{ref.ext_id}"
    if raw_dir is not None:
        sid, _ = records.upsert_source(conn, kind, url, raw=record, raw_dir=raw_dir)
    else:
        sid, _ = records.upsert_source(conn, kind, url, digest=records.sha256(record))
    _card_text(conn, claude, canary, report, sid=sid, text=project_text(ref),
               project_id=project_id, doc_type="project_page", title_hint=ref.title)
    if max_docs <= 0:
        return
    links: list[cordis.ResultLink] = []
    if ref.cordis_id:
        results = _get(fetcher, cordis.results_url(ref.cordis_id), report)
        if results is not None:
            links = cordis.parse_results(results.content, results.final_url)
    links += ref.publications
    if len(ref.urls) > 1:  # the project's own website (Erasmus+ records name one)
        site = _get(fetcher, ref.urls[1], report)
        if site is not None:
            _card(conn, claude, canary, report, got=site, raw_dir=raw_dir,
                  project_id=project_id, doc_type="project_site", title_hint=ref.title)
    for link in links[:max_docs]:
        got = _get(fetcher, link.url, report)
        if got is not None:
            _card(conn, claude, canary, report, got=got, raw_dir=raw_dir,
                  project_id=project_id, doc_type=RESULT_TO_DOC_TYPE[link.kind],
                  title_hint=link.title)


def import_projects(conn: sqlite3.Connection, refs: list[ProjectRef],
                    report: Report) -> dict[int, int]:
    """Every project into `project` (no model calls). Returns {id(ref): project id}."""
    ids: dict[int, int] = {}
    for ref in refs:
        pid, created = upsert_project(conn, ref)
        ids[id(ref)] = pid
        report.imported += 1
        report.projects_new += created
        report.flagged_projects += bool(ref.flags)
    conn.commit()
    return ids


def to_card(conn: sqlite3.Connection, refs: list[ProjectRef], ids: dict[int, int],
            n: int) -> list[ProjectRef]:
    """The next `n` projects without a card, the most textile-specific first. Each run
    with `--max-projects N` cards the next N."""
    chosen: list[ProjectRef] = []
    for ref in priority(refs):
        if len(chosen) >= n:
            break
        carded = conn.execute("SELECT 1 FROM document WHERE project_id = ? AND "
                              "doc_type = 'project_page'", (ids[id(ref)],)).fetchone()
        if carded is None:
            chosen.append(ref)
    return chosen


def scrape_funding(conn: sqlite3.Connection, refs: list[ProjectRef],
                   sources: dict[str, tuple[int, int]], fetcher, claude, canary: str, *,
                   raw_dir: Path | None, max_projects: int = DEFAULT_MAX_PROJECTS,
                   max_docs: int = DEFAULT_MAX_DOCS, origin: str = "") -> Report:
    report = Report(sources=sources)
    ids = import_projects(conn, refs, report)
    if claude is not None:
        for ref in to_card(conn, refs, ids, max_projects):
            scrape_project(conn, fetcher, claude, canary, ref, ids[id(ref)], report,
                           raw_dir=raw_dir, max_docs=max_docs)
            report.carded += 1
            conn.commit()
    db.event(conn, "scrape", "scrape_funding", ref=origin[:200], detail={
        "imported": report.imported, "new": report.projects_new, "carded": report.carded,
        "documents": dict(report.documents), "errors": len(report.errors)})
    return report


def scrape_url(conn: sqlite3.Connection, fetcher, claude, canary: str, url: str, *,
               raw_dir: Path | None) -> tuple[library.Added | None, list[str]]:
    """One page or PDF the team hands Cloé, into the library (no project)."""
    report = Report()
    got = _get(fetcher, url, report)
    if got is None:
        return None, report.errors or [f"not fetched: {url} (not in the fixture index)"]
    doc_type = "document" if got.content_type == "application/pdf" else "page"
    title = fetch.html_title(got.content) if got.content_type == "text/html" else ""
    _card(conn, claude, canary, report, got=got, raw_dir=raw_dir, project_id=None,
          doc_type=doc_type, title_hint=title)
    sid = conn.execute("SELECT id FROM source WHERE url = ? AND kind = ?",
                       (got.url, source_kind(got.final_url, got.content_type))).fetchone()
    doc = conn.execute("SELECT id FROM document WHERE source_id = ?",
                       (sid["id"],)).fetchone() if sid else None
    status = next(iter(report.documents), "error")
    db.event(conn, "scrape", "scrape_url", ref=f"document:{doc['id'] if doc else '-'}",
             detail={"status": status})
    return library.Added(doc["id"] if doc else None, status), report.errors
