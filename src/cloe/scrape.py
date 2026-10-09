"""`cloe scrape funding` and `cloe scrape url`: pages → sources → library cards.

The fetcher is either the guarded `fetch.Fetcher` (live, MacBook) or `fetch.FixtureFetcher`
(saved pages). The reader is whatever `claude` is passed: the API, or FakeClaude with the
offline stand-in. One failed fetch or card never stops the run; it is counted.
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
from cloe.sources.funding import FUNDING_URL, ProjectRef, parse_funding_page

DEFAULT_MAX_PROJECTS = 3
DEFAULT_MAX_DOCS = 5
RESULT_TO_DOC_TYPE = {"deliverable": "deliverable", "publication": "publication",
                      "report": "report", "other": "other"}


@dataclass
class Report:
    listed: int = 0
    processed: int = 0
    projects_new: int = 0
    on_cordis: int = 0
    cordis_pages: int = 0
    flagged_projects: int = 0
    documents: Counter = field(default_factory=Counter)
    by_type: Counter = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        docs = ", ".join(f"{n} {s}" for s, n in sorted(self.documents.items())) or "none"
        types = ", ".join(f"{n} {t}" for t, n in self.by_type.most_common()) or "none"
        out = [
            (f"projects listed {self.listed}, processed {self.processed} "
             f"({self.projects_new} new), on CORDIS {self.on_cordis}/{self.processed}, "
             f"CORDIS pages read {self.cordis_pages}"),
            f"documents: {docs}",
            f"document types: {types}",
        ]
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
        report.errors.append(f"not fetched: {url} ({exc})")
        return None


def _source(conn: sqlite3.Connection, got: fetch.Fetched, raw_dir: Path | None) -> int:
    kind = source_kind(got.final_url, got.content_type)
    if raw_dir is not None:
        sid, _ = records.upsert_source(conn, kind, got.url, raw=got.content, raw_dir=raw_dir)
    else:
        sid, _ = records.upsert_source(conn, kind, got.url, digest=got.sha256)
    return sid


def upsert_project(conn: sqlite3.Connection, ref: ProjectRef,
                   cp: cordis.CordisProject | None = None) -> tuple[int, bool]:
    """One row per CORDIS id, else per acronym (or title). CORDIS facts win over the
    funding page for title and dates; Dutch partners are merged."""
    cid = (cp.cordis_id if cp else None) or ref.cordis_id
    acronym = (cp.acronym if cp and cp.acronym else None) or ref.acronym
    row = None
    if cid:
        row = conn.execute("SELECT * FROM project WHERE cordis_id = ?", (cid,)).fetchone()
    if row is None and acronym:
        row = conn.execute("SELECT * FROM project WHERE acronym = ? COLLATE NOCASE AND "
                           "(cordis_id IS NULL OR cordis_id = ?)", (acronym, cid)).fetchone()
    if row is None and not acronym and ref.title:
        row = conn.execute("SELECT * FROM project WHERE title = ? AND acronym IS NULL",
                           (ref.title,)).fetchone()
    cordis_title = cp.title if cp and cp.title and cp.title != cordis.FLAGGED_TITLE else ""
    values = {
        "acronym": acronym,
        "title": cordis_title or ref.title or acronym or "(untitled)",
        "programme": (cp.programme if cp else None) or ref.programme,
        "cordis_id": cid,
        "url": cordis.project_url(cid) if cid else (ref.urls[0] if ref.urls else None),
        "start_date": (cp.start_date if cp else None) or
        (str(ref.start_year) if ref.start_year else None),
        "end_date": (cp.end_date if cp else None) or
        (str(ref.end_year) if ref.end_year else None),
    }
    partners = list(dict.fromkeys([*ref.partners_nl, *(cp.partners_nl if cp else [])]))
    if row is None:
        cur = conn.execute(
            "INSERT INTO project(acronym, title, programme, cordis_id, url, start_date, "
            "end_date, partners_nl_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (*values.values(), json.dumps(partners, ensure_ascii=False)))
        return cur.lastrowid, True
    known = json.loads(row["partners_nl_json"] or "[]")
    merged = list(dict.fromkeys([*known, *partners]))
    if not cordis_title and row["title"]:
        values["title"] = row["title"]  # the funding page does not overwrite CORDIS
    conn.execute(
        "UPDATE project SET acronym = coalesce(?, acronym), title = ?, "
        "programme = coalesce(?, programme), cordis_id = coalesce(?, cordis_id), "
        "url = coalesce(?, url), start_date = coalesce(?, start_date), "
        "end_date = coalesce(?, end_date), partners_nl_json = ? WHERE id = ?",
        (*values.values(), json.dumps(merged, ensure_ascii=False), row["id"]))
    return row["id"], False


def project_text(cp: cordis.CordisProject) -> str:
    """The project page as the reader sees it: parsed fields only, no page furniture."""
    head = " · ".join(x for x in (cp.acronym, cp.programme,
                                  "–".join(d for d in (cp.start_date, cp.end_date) if d)) if x)
    parts = [f"# {cp.title}", head, "## Objective", cp.objective]
    if cp.partners_nl:
        parts.append("Dutch participants: " + "; ".join(cp.partners_nl))
    if cp.coordinator:
        parts.append(f"Coordinator: {cp.coordinator}")
    return "\n\n".join(p for p in parts if p)


def _card(conn, claude, canary, report, *, got, raw_dir, project_id, doc_type, title_hint,
          text=None) -> None:
    sid = _source(conn, got, raw_dir)
    try:
        body = text if text is not None else fetch.to_text(got)
    except fetch.FetchError as exc:
        report.errors.append(f"no text from {got.url} ({exc})")
        report.documents["error"] += 1
        return
    added = library.add_document(conn, claude, canary, source_id=sid, text=body,
                                 project_id=project_id, doc_type=doc_type,
                                 title_hint=title_hint)
    report.documents[added.status] += 1
    if added.status in ("new", "updated", "flagged"):
        report.by_type[doc_type] += 1
    if added.status in ("error", "skipped"):
        report.errors.append(f"no card for {got.url} ({added.detail})")


def scrape_project(conn, fetcher, claude, canary, ref: ProjectRef, report: Report, *,
                   raw_dir: Path | None, max_docs: int) -> int:
    cp, page = None, None
    if ref.cordis_id:
        page = _get(fetcher, cordis.project_url(ref.cordis_id), report)
        if page is not None:
            try:
                cp = cordis.parse_project(page.content, page.final_url, page.content_type)
                report.cordis_pages += 1
            except (ValueError, TypeError) as exc:
                report.errors.append(f"unreadable CORDIS page {page.url} ({exc})")
    pid, created = upsert_project(conn, ref, cp)
    report.projects_new += created
    report.on_cordis += bool(ref.cordis_id or (cp and cp.cordis_id))
    report.flagged_projects += bool(ref.flags or (cp and cp.flags))
    links: list[cordis.ResultLink] = []
    if cp is not None and page is not None:
        text = project_text(cp) if cp.objective else None
        _card(conn, claude, canary, report, got=page, raw_dir=raw_dir, project_id=pid,
              doc_type="project_page", title_hint=cp.title, text=text)
        results = _get(fetcher, cp.results_url, report) if cp.results_url else None
        if results is not None:
            links = cordis.parse_results(results.content, results.final_url)
    elif not ref.cordis_id:
        site = next((u for u in ref.urls if not cordis.cordis_id_of(u)), None)
        got = _get(fetcher, site, report) if site else None
        if got is not None:
            _card(conn, claude, canary, report, got=got, raw_dir=raw_dir, project_id=pid,
                  doc_type="project_site", title_hint=ref.title)
            if got.content_type == "text/html":
                links = [lk for lk in cordis.parse_results(got.content, got.final_url)
                         if lk.kind != "other"]
    for link in links[:max_docs]:
        got = _get(fetcher, link.url, report)
        if got is not None:
            _card(conn, claude, canary, report, got=got, raw_dir=raw_dir, project_id=pid,
                  doc_type=RESULT_TO_DOC_TYPE[link.kind], title_hint=link.title)
    return pid


def scrape_funding(conn: sqlite3.Connection, fetcher, claude, canary: str, *,
                   raw_dir: Path | None, max_projects: int = DEFAULT_MAX_PROJECTS,
                   max_docs: int = DEFAULT_MAX_DOCS, start_url: str = FUNDING_URL) -> Report:
    report = Report()
    page = _get(fetcher, start_url, report)
    if page is None:
        return report
    _source(conn, page, raw_dir)
    refs = parse_funding_page(page.text(), page.final_url)
    report.listed = len(refs)
    for ref in refs[:max_projects]:
        scrape_project(conn, fetcher, claude, canary, ref, report, raw_dir=raw_dir,
                       max_docs=max_docs)
        report.processed += 1
        conn.commit()
    db.event(conn, "scrape", "scrape_funding", ref=start_url[:200], detail={
        "listed": report.listed, "processed": report.processed,
        "on_cordis": report.on_cordis, "documents": dict(report.documents),
        "errors": len(report.errors)})
    return report


def scrape_url(conn: sqlite3.Connection, fetcher, claude, canary: str, url: str, *,
               raw_dir: Path | None) -> tuple[library.Added | None, list[str]]:
    """One page or PDF the team hands Cloé, into the library (no project)."""
    report = Report()
    got = _get(fetcher, url, report)
    if got is None:
        return None, report.errors
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
