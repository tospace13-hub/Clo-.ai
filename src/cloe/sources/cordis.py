"""CORDIS: project ids and URLs, and results pages → links to research material.

Project facts (title, dates, objective, Dutch participants) come from the CORDIS open-data
records in M-DPP's dataset (`sources/funding.py`), so Cloé doesn't read CORDIS project
pages. What the dataset lacks is the research material: deliverables and publications are
listed only on a project's results page (`/project/id/<id>/results`). `parse_results`
reads those links by what they point to (PDFs, EC document downloads, Zenodo records,
DOIs) and labels them by the heading above them. No live results page has been seen from
a cloud session (cordis.europa.eu is blocked; work order 001 asks the MacBook for some).

Link texts are untrusted: scrubbed, and instruction-like ones replaced.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

from bs4 import Tag
from pydantic import BaseModel

from cloe.records import clean
from cloe.sources.fetch import absolute_link, soup_of
from cloe.untrusted import injection_flags

BASE = "https://cordis.europa.eu"
CORDIS_ID = re.compile(r"cordis\.europa\.eu/project/id/(\d{5,9})\b", re.IGNORECASE)
HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
FLAGGED_TITLE = "[flagged text]"

ResultKind = Literal["deliverable", "publication", "report", "other"]


class ResultLink(BaseModel):
    title: str
    url: str
    kind: ResultKind


def cordis_id_of(url: str) -> str | None:
    m = CORDIS_ID.search(url or "")
    return m.group(1) if m else None


def project_url(cordis_id: str) -> str:
    return f"{BASE}/project/id/{cordis_id}"


def results_url(cordis_id: str) -> str:
    return f"{project_url(cordis_id)}/results"


def iso_date(text: str | None) -> str | None:
    """'1 September 2023', '2023-09-01', '2016-09-01T00:00:00', '01/09/2023' →
    '2023-09-01'."""
    if not text:
        return None
    text = " ".join(text.split())
    m = re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4}",
                  text)
    if not m:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(m.group(0), fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            continue
    return None


def _text(tag: Tag | None) -> str:
    return clean(tag.get_text(" "), 2000) if tag is not None else ""


MATERIAL = re.compile(r"\.pdf(?:$|\?)|downloadpublic|/docs/results/|zenodo\.org/records?/|"
                      r"doi\.org/10\.", re.IGNORECASE)


def _kind(heading: str, title: str) -> ResultKind:
    h, t = heading.lower(), title.lower()
    if "deliverable" in h or re.match(r"d\s?\d+(\.\d+)*\b", t):
        return "deliverable"
    if "publication" in h or "article" in h or "paper" in t:
        return "publication"
    if "report" in h or "report" in t:
        return "report"
    return "other"


def parse_results(content: str | bytes, url: str) -> list[ResultLink]:
    """Links to research material on a results page: PDFs, EC document downloads, Zenodo
    records and DOIs. Navigation and other CORDIS pages are skipped."""
    soup = soup_of(content)
    for tag in soup.find_all(["script", "style", "noscript", "nav", "footer"]):
        tag.decompose()
    links: dict[str, ResultLink] = {}
    for a in soup.find_all("a"):
        target = absolute_link(a.get("href"), url)
        if not target or not MATERIAL.search(target) or target in links:
            continue
        heading = a.find_previous(HEADINGS)
        title = _text(a) or target
        if injection_flags(title):
            title = FLAGGED_TITLE
        links[target] = ResultLink(title=clean(title, 300), url=target,
                                   kind=_kind(_text(heading), title))
    return list(links.values())
