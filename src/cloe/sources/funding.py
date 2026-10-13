"""M-DPP's Dutch textile research-funding network → projects.

m-dpp.nl/nl_funding_network.html is a D3 network drawn in the browser; its HTML holds no
project list. The data are three JSON datasets in the site's public repository,
github.com/MDPP-ops/MDPP_Website (Jekyll on GitHub Pages):

- `cordis_textile_projects.json`, built by its `fetch_cordis_bulk.py` from the official
  CORDIS open-data archives (H2020 + Horizon Europe), filtered for textile and fashion
  keywords. One record per project: id, acronym, title, programme, funding scheme, dates,
  EU grant, objective (cut at 1,200 characters), topics, and every participating
  organisation with its country, role and activity type.
- `erasmus_textile_projects.json`: the same for Erasmus+ project lists.
- `nwo_fashion_textile_filtered.json`: NWO/SIA projects (Dutch by definition).

The page shows the EU projects with at least one Dutch member, plus the NWO projects.
Cloé reads the same files from a checkout of that repository and keeps the same projects.
For NWO she uses the repo's filtered textile file; the page loads the unfiltered one.

The datasets are third-party text (abstracts, organisation names): scrubbed, capped,
instruction-like text flagged and kept out of titles. And no people: NWO lists researchers
by name, and Cloé keeps only their organisations.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from cloe.records import INSTRUCTION_LIKE, clean
from cloe.sources.cordis import ResultLink, cordis_id_of, iso_date
from cloe.untrusted import injection_flags

REPO_URL = "https://github.com/MDPP-ops/MDPP_Website"
PAGE_URL = "https://m-dpp.nl/nl_funding_network.html"
DATASETS = (
    ("cordis", "cordis_textile_projects.json"),
    ("erasmus", "erasmus_textile_projects.json"),
    ("nwo", "nwo_fashion_textile_filtered.json"),
)
SOURCE_LABELS = {"cordis": "CORDIS", "erasmus": "Erasmus+", "nwo": "NWO/SIA"}
MAX_DATASET_BYTES = 100_000_000
NL_CODES = frozenset({"NL"})
FLAGGED_TITLE = "[flagged text]"
# Words that make a project textile-specific (the datasets' own keyword match is broad:
# "value chain", "coating", "supply chain"). Used to choose which projects to card first.
CORE_TERMS = ("textile", "textiel", "fabric", "fibre", "fiber", "garment", "apparel",
              "clothing", "kleding", "fashion", "yarn", "knit", "breien",
              "weav", "denim", "wool", "cotton", "polyester", "nonwoven", "leather",
              "footwear")


class Organisation(BaseModel):
    name: str
    type: str = ""   # CORDIS activity type (PRC, HES, REC, PUB, OTH) or Erasmus+ orgType
    role: str = ""


class ProjectRef(BaseModel):
    ext_id: str | None = None        # "cordis:101060375", "erasmus:…", "nwo:…"
    source: str = ""                 # cordis | erasmus | nwo
    acronym: str | None = None
    title: str = ""
    urls: list[str] = Field(default_factory=list)  # project page first, then its website
    programme: str | None = None
    funding_scheme: str | None = None
    start_date: str | None = None    # ISO date, or a year
    end_date: str | None = None
    ec_grant: float | None = None
    abstract: str = ""
    keywords: list[str] = Field(default_factory=list)
    nl_orgs: list[Organisation] = Field(default_factory=list)
    cordis_id: str | None = None
    publications: list[ResultLink] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    @property
    def partners_nl(self) -> list[str]:
        return [o.name for o in self.nl_orgs]

    @property
    def label(self) -> str:
        return self.acronym or self.title or "(untitled)"

    def core_score(self) -> int:
        """How textile-specific the project reads: title counts most, then keywords."""
        title, keys, text = (self.title.lower(), " ".join(self.keywords).lower(),
                             self.abstract.lower())
        return sum(3 * (t in title) + 2 * (t in keys) + (t in text) for t in CORE_TERMS)


def has_dutch_member(record: dict) -> bool:
    if str(record.get("_pi_country") or "").upper() in NL_CODES:
        return True
    return any(str(m.get("country") or "").upper() in NL_CODES
               for m in record.get("project_members") or [] if isinstance(m, dict))


def _orgs(record: dict, source: str) -> list[Organisation]:
    found: dict[str, Organisation] = {}
    for m in record.get("project_members") or []:
        if not isinstance(m, dict):
            continue
        if source != "nwo" and str(m.get("country") or "").upper() not in NL_CODES:
            continue
        # NWO members are people: keep their organisation (top level), never their name.
        name = clean(str(m.get("organisation") or "").split("||")[0], 200)
        if not name or injection_flags(name):
            continue
        kind = clean(m.get("activityType") or m.get("orgType") or "", 80)
        role = clean(m.get("role") or "", 60) if source != "nwo" else ""
        found.setdefault(name.lower(), Organisation(name=name, type=kind, role=role))
    return list(found.values())


def _grant(record: dict, source: str) -> float | None:
    value = record.get("award_amount") if source == "nwo" else \
        record.get("ec_grant_num", record.get("ec_grant"))
    try:
        number = float(str(value).replace(" ", "").replace(",", ".")) if value not in (
            None, "") else None
    except ValueError:
        return None
    return number if number and number > 0 else None


def _publications(record: dict) -> list[ResultLink]:
    links = []
    for product in record.get("products") or []:
        if not isinstance(product, dict):
            continue
        url = str(product.get("url_open_access") or "").strip()
        if url.startswith("10."):
            url = "https://doi.org/" + url
        if not url.startswith(("https://", "http://")):
            continue
        title = clean(product.get("title") or url, 300)
        links.append(ResultLink(title=FLAGGED_TITLE if injection_flags(title) else title,
                                url=url, kind="publication"))
    return links


def to_ref(record: dict, source: str) -> ProjectRef:
    pid = clean(record.get("project_id") or "", 80)
    title = clean(record.get("title_en") or record.get("title") or "", 500)
    abstract = clean(record.get("objective") or record.get("summary_en") or
                     record.get("summary_nl") or "", 5000)
    acronym = clean(record.get("acronym") or "", 40) or None
    page = str(record.get("project_page_url") or "").strip()
    if not page and source == "nwo" and pid:
        page = f"https://www.nwo.nl/projecten/{pid}"
    website = str(record.get("project_website") or "").strip()
    urls = [u for u in (page, website) if u.startswith(("https://", "http://"))]
    keywords = [k for k in (clean(k, 80) for k in
                            str(record.get("topics") or "").replace(";", ",").split(","))
                if k][:20]
    ref = ProjectRef(
        ext_id=f"{source}:{pid}" if pid else None,
        source=source,
        acronym=acronym,
        title=title or acronym or "",
        urls=urls,
        programme=clean(record.get("programme") or "", 80) or
        ("NWO/SIA" if source == "nwo" else None),
        funding_scheme=clean(record.get("funding_scheme") or record.get("key_action") or "",
                             120) or None,
        start_date=iso_date(str(record.get("start_date") or "")) or
        (clean(record.get("call_year") or "", 4) or None),
        end_date=iso_date(str(record.get("end_date") or "")),
        ec_grant=_grant(record, source),
        abstract=abstract,
        keywords=keywords,
        nl_orgs=_orgs(record, source),
        cordis_id=(pid if source == "cordis" and pid.isdigit() else None) or
        cordis_id_of(page),
        publications=_publications(record),
    )
    if any(injection_flags(t) for t in (title, abstract, acronym or "", *keywords)):
        ref.flags.append(INSTRUCTION_LIKE)
        if injection_flags(ref.title):
            ref.title = FLAGGED_TITLE
        if ref.acronym and injection_flags(ref.acronym):
            ref.acronym = None
        ref.keywords = [k for k in ref.keywords if not injection_flags(k)]
    return ref


def read_dataset(path: Path) -> list[dict]:
    """The records of one dataset file: `{"projects": [...]}` or a bare list."""
    if path.stat().st_size > MAX_DATASET_BYTES:
        raise ValueError(f"{path.name} is larger than {MAX_DATASET_BYTES} bytes")
    try:
        data = json.loads(path.read_bytes())
    except json.JSONDecodeError:
        raise ValueError(f"{path.name} is not valid JSON") from None
    projects = data.get("projects") if isinstance(data, dict) else data
    if not isinstance(projects, list):
        raise TypeError(f"{path.name} has no project list")
    return [p for p in projects if isinstance(p, dict)]


def load(directory: Path) -> tuple[list[ProjectRef], dict[str, tuple[int, int]]]:
    """Every project the page shows: (refs, {source: (records, kept)}). Missing files
    are skipped; at least one must exist."""
    refs: list[ProjectRef] = []
    counts: dict[str, tuple[int, int]] = {}
    for source, name in DATASETS:
        path = Path(directory) / name
        if not path.is_file():
            continue
        records = read_dataset(path)
        kept = [r for r in records if source == "nwo" or has_dutch_member(r)]
        refs += [to_ref(r, source) for r in kept]
        counts[source] = (len(records), len(kept))
    if not counts:
        raise ValueError(f"no M-DPP datasets in {directory} (clone {REPO_URL})")
    unique: dict[str, ProjectRef] = {}
    for ref in refs:
        unique.setdefault(ref.ext_id or f"{ref.source}|{ref.title}", ref)
    return list(unique.values()), counts


def priority(refs: list[ProjectRef]) -> list[ProjectRef]:
    """Which projects to card first: the most textile-specific, then the newest."""
    return sorted(refs, key=lambda r: (r.core_score(), r.start_date or ""), reverse=True)
