"""CORDIS project and results pages → project facts and links to research material.

Nobody in a cloud session has seen a live CORDIS page (CONTEXT §G), and the public pages
offer no per-project JSON format that could be confirmed (the CORDIS data API needs an EU
Login). So the parser reads HTML by labels and headings rather than by CSS classes:
"Start date" / "End date" / "Funded under" next to their values (dt/dd, th/td, or
"Label: value"), the section under an "Objective" heading, the "Participants" section's
entries that mention the Netherlands, and the page title's "Title | ACRONYM | Project | …"
pattern. A JSON record in the CORDIS open-data shape (`id`, `acronym`, `title`,
`objective`, `startDate`, `endDate`, `frameworkProgramme`) is read too. Work order 001
saves real pages so a later session can check this.

All of it is untrusted text: scrubbed, and instruction-like titles are flagged.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Literal

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field

from cloe.records import INSTRUCTION_LIKE, clean
from cloe.sources.fetch import absolute_link, soup_of
from cloe.untrusted import injection_flags

BASE = "https://cordis.europa.eu"
CORDIS_ID = re.compile(r"cordis\.europa\.eu/project/id/(\d{5,9})\b", re.IGNORECASE)
HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
NETHERLANDS = re.compile(r"\b(?:the\s+)?netherlands\b|\bnederland\b|\(NL\)|\bNL\b", re.IGNORECASE)
FLAGGED_TITLE = "[flagged text]"

PROGRAMMES = (
    (r"horizon\s*europe|\bHEU\b|\bHORIZON\b(?!\s*2020)", "Horizon Europe"),
    (r"horizon\s*2020|\bH2020\b", "Horizon 2020"),
    (r"\bFP7\b|seventh framework", "FP7"),
    (r"interreg[\w\s-]{0,30}?(?=[,.;·|()]|\d|$)", None),  # the Interreg strand as written
    (r"\bLIFE\b", "LIFE"),
    (r"\bCOSME\b", "COSME"),
    (r"erasmus\s*\+", "Erasmus+"),
    (r"digital\s+europe", "Digital Europe"),
    (r"\bEIT\b[\w\s-]{0,20}", None),
    (r"\bERC\b", "ERC"),
    (r"\bMSCA\b|marie\s+sk", "MSCA"),
)

ResultKind = Literal["deliverable", "publication", "report", "other"]


class CordisProject(BaseModel):
    cordis_id: str
    acronym: str | None = None
    title: str = ""
    objective: str = ""
    programme: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    partners_nl: list[str] = Field(default_factory=list)
    coordinator: str | None = None
    results_url: str | None = None
    flags: list[str] = Field(default_factory=list)


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


def programme_of(text: str) -> str | None:
    """A funding programme named in `text`, in canonical spelling."""
    for pattern, canonical in PROGRAMMES:
        m = re.search(pattern, text or "", re.IGNORECASE)
        if m:
            return canonical or " ".join(m.group(0).split()).strip(" -")
    return None


def iso_date(text: str | None) -> str | None:
    """'1 September 2023', '2023-09-01', '01/09/2023' → '2023-09-01'."""
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


def labelled(soup: BeautifulSoup, *labels: str) -> str:
    """The value next to a label: dt→dd, th/td→td, label element→next sibling, or a
    'Label: value' line."""
    want = {label.lower() for label in labels}
    for tag in soup.find_all(["dt", "th", "td", "span", "div", "strong", "b", "label", "p"]):
        if _text(tag).rstrip(":").strip().lower() not in want:
            continue
        if tag.name == "dt":
            value = tag.find_next_sibling("dd")
        elif tag.name in ("th", "td"):
            value = tag.find_next_sibling("td")
        else:
            value = tag.find_next_sibling()
        if value is not None and _text(value):
            return _text(value)
    lines = soup.get_text("\n")
    for label in labels:
        m = re.search(rf"^\s*{re.escape(label)}\s*:\s*(\S.*)$", lines, re.IGNORECASE | re.MULTILINE)
        if m:
            return clean(m.group(1), 500)
    return ""


def section(soup: BeautifulSoup, pattern: str) -> list[Tag]:
    """Elements after the first heading matching `pattern`, up to the next heading of the
    same or a higher level."""
    for h in soup.find_all(HEADINGS):
        if re.search(pattern, _text(h), re.IGNORECASE):
            level, parts = int(h.name[1]), []
            for sib in h.find_next_siblings():
                if sib.name in HEADINGS and int(sib.name[1]) <= level:
                    break
                parts.append(sib)
            return parts
    return []


def _entries(parts: list[Tag]) -> list[Tag]:
    found: list[Tag] = []
    for part in parts:
        rows = part.find_all(["li", "tr"]) if part.name not in ("li", "tr") else [part]
        found += [r for r in rows if r.find("td") or r.name == "li"] or [part]
    return found


def _entry_name(entry: Tag) -> str:
    first = entry.find(["strong", "b", "a", "td", "h3", "h4"])
    if first is not None and _text(first):
        return _text(first)
    return re.split(r"\s+[—–-]\s+|,\s*", _text(entry), maxsplit=1)[0]


def _participants(soup: BeautifulSoup) -> tuple[list[str], str | None]:
    dutch: list[str] = []
    coordinator = None
    for entry in _entries(section(soup, r"participant|partner|consorti|coordinat")):
        text = _text(entry)
        name = clean(_entry_name(entry), 200)
        if not name or injection_flags(name):
            continue
        if NETHERLANDS.search(text) and name not in dutch:
            dutch.append(name)
        if coordinator is None and re.search(r"\bcoordinat", text, re.IGNORECASE):
            coordinator = name
    return dutch, coordinator


def _from_json(data: object, cordis_id: str) -> CordisProject:
    record = data[0] if isinstance(data, list) and data else data
    if not isinstance(record, dict):
        raise TypeError("CORDIS JSON is not a project record")

    def get(*keys: str) -> str:
        for key in keys:
            if record.get(key):
                return clean(record[key], 5000)
        return ""

    return CordisProject(
        cordis_id=get("id") or cordis_id,
        acronym=get("acronym") or None,
        title=get("title"),
        objective=get("objective"),
        programme=programme_of(get("frameworkProgramme", "programme")) or
        (get("frameworkProgramme", "programme") or None),
        start_date=iso_date(get("startDate")),
        end_date=iso_date(get("endDate")),
        results_url=results_url(get("id") or cordis_id),
    )


def parse_project(content: str | bytes, url: str, content_type: str = "text/html"
                  ) -> CordisProject:
    cid = cordis_id_of(url) or ""
    if content_type == "application/json":
        project = _from_json(json.loads(content), cid)
    else:
        soup = soup_of(content)
        for tag in soup.find_all(["script", "style", "noscript", "nav", "footer"]):
            tag.decompose()
        segments = [s.strip() for s in (soup.title.get_text() if soup.title else "").split("|")]
        lowered = [s.lower() for s in segments]
        from_title = {}
        if "project" in lowered and lowered.index("project") >= 2:
            i = lowered.index("project")
            from_title = {"title": segments[0], "acronym": segments[i - 1],
                          "programme": segments[i + 2] if len(segments) > i + 2 else ""}
        og = soup.find("meta", attrs={"property": "og:title"})
        title = (clean(og.get("content", ""), 500) if og else "") or \
            _text(soup.find("h1")) or clean(from_title.get("title", ""), 500)
        acronym = labelled(soup, "Acronym", "Project acronym") or from_title.get("acronym")
        objective = clean(" ".join(p.get_text(" ") for p in
                                   section(soup, r"^(objective|summary|doelstelling)")), 5000)
        funded = labelled(soup, "Funded under", "Programme", "Programme(s)", "Programma")
        programme = programme_of(funded) or programme_of(from_title.get("programme", "")) \
            or (clean(funded, 120) or None)
        dutch, coordinator = _participants(soup)
        cid = cid or labelled(soup, "Grant agreement ID", "Grant agreement").strip()
        results = next((absolute_link(a.get("href"), url) for a in soup.find_all("a")
                        if re.search(r"/project/id/\d+/results", a.get("href") or "")), None)
        project = CordisProject(
            cordis_id=cid, acronym=clean(acronym, 40) or None, title=title,
            objective=objective, programme=programme,
            start_date=iso_date(labelled(soup, "Start date", "Startdatum")),
            end_date=iso_date(labelled(soup, "End date", "Einddatum")),
            partners_nl=dutch, coordinator=coordinator,
            results_url=results or (results_url(cid) if cid else None),
        )
    if injection_flags(project.title) or injection_flags(project.objective):
        project.flags.append(INSTRUCTION_LIKE)
        if injection_flags(project.title):
            project.title = FLAGGED_TITLE
    if project.acronym and injection_flags(project.acronym):
        project.acronym = None
    return project


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
