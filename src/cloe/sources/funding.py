"""The m-dpp.nl EU-projects page → `ProjectRef`s.

Nobody in a cloud session has seen the real page (CONTEXT §G), so the parser makes no
assumption about its layout. It reads project rows from any table with a header row
(Dutch or English headers) and project entries from repeated blocks (cards, list items,
headed sections). A block counts as a project only if it links to CORDIS, or if it shows an
acronym together with a programme or a year range. Work order 001 saves the real page so a
later session can check this against it.

Everything on the page is untrusted: text is scrubbed, and instruction-like cells are
flagged and kept out of titles and partner lists.
"""

from __future__ import annotations

import re

from bs4 import Tag
from pydantic import BaseModel, Field

from cloe.records import INSTRUCTION_LIKE, clean
from cloe.sources import cordis
from cloe.sources.cordis import programme_of
from cloe.sources.fetch import absolute_link, soup_of
from cloe.untrusted import injection_flags

FUNDING_URL = "https://m-dpp.nl/nl_funding_network.html"
FLAGGED_TITLE = "[flagged text]"

YEARS = re.compile(r"\b((?:19|20)\d{2})\s*(?:[-–—/]|tot|to|t/m)\s*((?:19|20)\d{2})\b")
YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]*(?:[-+][A-Z0-9]+)*[A-Z0-9]\b")
NOT_ACRONYMS = frozenset({
    "EU", "H2020", "HEU", "FP7", "LIFE", "COSME", "ERC", "MSCA", "EIT", "NWO", "SIA", "RVO",
    "NL", "BV", "NV", "VOF", "SA", "GMBH", "SME", "SMES", "CORDIS", "PDF", "DPP", "ESPR",
    "EPR", "UPV", "LCA", "HTML", "URL", "KVK", "AMFI", "HVA", "WP", "II", "III",
})
GRANT = re.compile(r"(?:cordis|grant(?:\s+agreement)?(?:\s+id)?|GA)\D{0,15}(\d{6,9})\b", re.IGNORECASE)
PARTNERS_LABEL = re.compile(
    r"(?:nederlandse\s+partners?|dutch\s+partners?|nl[\s-]partners?|partners?|deelnemers)"
    r"\s*[:：]\s*(.+)", re.IGNORECASE)
SPLIT_PARTNERS = re.compile(r"\s*(?:[;,·|/]|\ben\b|\band\b)\s*")

HEADER_KEYS = {
    "acronym": ("acroniem", "acronym", "afkorting", "kortenaam", "short name"),
    "title": ("titel", "title", "naam", "name", "projecttitel", "project title"),
    "programme": ("programma", "programme", "program", "funding", "financiering", "regeling",
                  "call", "fonds", "fund"),
    "years": ("looptijd", "periode", "period", "jaar", "jaren", "years", "year", "duration",
              "start"),
    "partners": ("partner", "deelnemer", "participant", "consortium"),
    "link": ("link", "website", "url", "cordis", "meer info", "more info"),
}


class ProjectRef(BaseModel):
    acronym: str | None = None
    title: str = ""
    urls: list[str] = Field(default_factory=list)
    programme: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    partners_nl: list[str] = Field(default_factory=list)
    cordis_id: str | None = None
    flags: list[str] = Field(default_factory=list)

    @property
    def key(self) -> str:
        return self.cordis_id or f"{self.acronym or ''}|{self.title.lower()}"

    @property
    def label(self) -> str:
        return self.acronym or self.title or "(untitled)"


# -- field readers ----------------------------------------------------------------------


def years_of(text: str) -> tuple[int | None, int | None]:
    m = YEARS.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = YEAR.search(text)
    return (int(m.group(1)), None) if m else (None, None)


def acronym_of(text: str) -> str | None:
    for m in ACRONYM.finditer(text):
        token = m.group(0)
        if len(token) >= 3 and token.upper() not in NOT_ACRONYMS and not token.isdigit():
            return token
    return None


def partners_of(text: str) -> list[str]:
    out = []
    for name in SPLIT_PARTNERS.split(text):
        name = clean(name, 200).strip(" .")
        if len(name) >= 2 and not injection_flags(name) and name not in out:
            out.append(name)
    return out


def _cordis_id(urls: list[str], text: str) -> str | None:
    for url in urls:
        cid = cordis.cordis_id_of(url)
        if cid:
            return cid
    m = GRANT.search(text)
    return m.group(1) if m else None


def _links(tag: Tag, base_url: str) -> list[str]:
    urls = (absolute_link(a.get("href"), base_url) for a in tag.find_all("a"))
    return list(dict.fromkeys(u for u in urls if u))


def _text(tag: Tag) -> str:
    return clean(tag.get_text(" "), 2000)


def _finish(ref: ProjectRef, raw_texts: list[str]) -> ProjectRef:
    if any(injection_flags(t) for t in raw_texts if t):
        ref.flags.append(INSTRUCTION_LIKE)
        if injection_flags(ref.title):
            ref.title = FLAGGED_TITLE
        if ref.acronym and injection_flags(ref.acronym):
            ref.acronym = None
    return ref


# -- tables -----------------------------------------------------------------------------


def _header_map(cells: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for i, cell in enumerate(cells):
        low = cell.lower()
        for field, keys in HEADER_KEYS.items():
            if field not in found and any(k in low for k in keys):
                found[field] = i
                break
        else:
            if low.strip() == "project" and "title" not in found:
                found["title"] = i
    return found


def _from_table(table: Tag, base_url: str) -> list[ProjectRef]:
    rows = table.find_all("tr")
    if len(rows) < 2:
        return []
    header = [_text(c) for c in rows[0].find_all(["th", "td"])]
    cols = _header_map(header)
    if not ({"acronym", "title"} & cols.keys()):
        return [ref for row in rows if (ref := _from_block(row, base_url))]
    refs = []
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        def cell(field: str, cells=cells) -> str:
            i = cols.get(field)
            return _text(cells[i]) if i is not None and i < len(cells) else ""

        urls = _links(row, base_url)
        row_text = _text(row)
        title = cell("title")
        acronym = cell("acronym") or acronym_of(title) or None
        start, end = years_of(cell("years") or row_text)
        ref = ProjectRef(
            acronym=acronym if acronym and len(acronym) <= 40 else acronym_of(acronym or ""),
            title=title or (acronym or ""),
            urls=urls,
            programme=programme_of(cell("programme")) or (clean(cell("programme"), 80) or None),
            start_year=start,
            end_year=end,
            partners_nl=partners_of(cell("partners")),
            cordis_id=_cordis_id(urls, row_text),
        )
        if ref.title or ref.acronym:
            refs.append(_finish(ref, [title, acronym or "", cell("partners")]))
    return refs


# -- blocks (cards, list items, sections) -----------------------------------------------


HEADINGS = ("h2", "h3", "h4", "h5", "h6")


def _from_block(tag: Tag | list[Tag], base_url: str, heading: str = "") -> ProjectRef | None:
    parts = tag if isinstance(tag, list) else [tag]
    text = clean(" ".join(p.get_text(" ") for p in parts), 2000)
    urls = list(dict.fromkeys(u for p in parts for u in _links(p, base_url)))
    cid = _cordis_id(urls, text)
    explicit = bool(heading)
    heading = heading or text[:200]
    acronym = acronym_of(heading) or acronym_of(text)
    programme = programme_of(text)
    start, end = years_of(text)
    if not cid and not (acronym and (programme or start)):
        return None
    title = heading
    if acronym and title.startswith(acronym):
        title = title[len(acronym):].lstrip(" :–—-|·").strip()
    if (not title or not explicit) and acronym and acronym in text:  # "ACRONYM – Title (…)"
        rest = text[text.index(acronym) + len(acronym):].lstrip(" :–—-|·")
        title = re.split(r"\s*\(|\.\s", rest, maxsplit=1)[0].strip()
    partners_text = ""
    for part in parts:  # the label's value ends with its element, or at the next field
        m = PARTNERS_LABEL.search(clean(part.get_text(" "), 2000))
        if m:
            partners_text = m.group(1)
            break
    for stop in (" · ", " | ", ". "):
        partners_text = partners_text.split(stop, 1)[0]
    ref = ProjectRef(acronym=acronym, title=clean(title, 300) or (acronym or ""), urls=urls,
                     programme=programme, start_year=start, end_year=end,
                     partners_nl=partners_of(partners_text), cordis_id=cid)
    return _finish(ref, [heading, partners_text])


def _section(heading: Tag) -> list[Tag] | None:
    """The heading and its following siblings up to the next heading of the same or a
    higher level. None when the section holds sub-headings, tables or lists: then it is a
    container, and its parts are read on their own."""
    level = int(heading.name[1])
    parts = [heading]
    for sib in heading.find_next_siblings():
        if sib.name in HEADINGS and int(sib.name[1]) <= level:
            break
        if sib.name in HEADINGS or sib.name in ("table", "ul", "ol") or \
                sib.find(["table", "ul", "ol", *HEADINGS]):
            return None
        parts.append(sib)
    return parts


def _blocks(soup: Tag, base_url: str) -> list[ProjectRef]:
    refs = []
    for h in soup.find_all(HEADINGS):
        if h.find_parent(["table", "li"]):
            continue
        parts = _section(h)
        if parts and (ref := _from_block(parts, base_url, heading=_text(h))):
            refs.append(ref)
    for li in soup.find_all("li"):
        if li.find_parent("table") or li.find("li"):
            continue
        head = li.find(["strong", "b", "a", *HEADINGS])
        if ref := _from_block(li, base_url, heading=_text(head) if head else ""):
            refs.append(ref)
    return refs


def parse_funding_page(html: str | bytes, base_url: str = FUNDING_URL) -> list[ProjectRef]:
    soup = soup_of(html)
    for tag in soup.find_all(["script", "style", "noscript", "nav", "template", "footer"]):
        tag.decompose()
    refs: list[ProjectRef] = []
    for table in soup.find_all("table"):
        refs += _from_table(table, base_url)
    refs += _blocks(soup, base_url)
    unique: dict[str, ProjectRef] = {}
    for ref in refs:
        unique.setdefault(ref.key, ref)
    return list(unique.values())
