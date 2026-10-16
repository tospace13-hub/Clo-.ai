"""Where Cloé looks for what is written about a Dutch company: the source catalogue.

A Dutch company is identified by its KvK number (Kamer van Koophandel, 8 digits). TELL's
export has no KvK column, so the number comes from `company.kvk`, `cloe research --kvk`,
the company's own website (Dutch law makes them print it) or the KVK API's name search.
Every source is a `Register`: what it is keyed by (kvk / name / domain / local), how it is
reached (open, with an API key, by a person, or already loaded), its format, a URL
template and what it gives. Sources with a documented machine-readable format have a
parser that turns the response into `Mention`s (an article, a register entry, a paper, an
archived page) and identity fields (name, legal form, SBI codes, founding year).

No host in this file is reachable from a cloud session (docs/CONTEXT.md §G): every parser
was written from the format's documentation and is tested on hand-written fixtures in
`tests/fixtures/site/`. The MacBook runs them live; a parser that meets a response it
does not understand returns nothing and the run reports it. Responses are data: parsed,
never executed, and wrapped before any model reads them.
"""

from __future__ import annotations

import email.utils
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urlsplit

from defusedxml import ElementTree

from cloe.untrusted import scrub

MENTION_KINDS = ("news", "press_release", "publication", "procurement", "register", "patent",
                 "certification", "event", "project", "dataset", "archive", "other")
GROUPS = {
    "identity": "Identity — who they are (KvK number first)",
    "official": "Official publications and courts",
    "funding": "Funding, research projects and public procurement",
    "ip_cert": "Patents, trademarks and certifications",
    "news": "News and trade press",
    "academic": "Academic output",
    "people": "People (business roles only)",
    "library_access": "Databases the HvA library gives access to (a person, logged in)",
}
ACCESS = {
    "open": "open",
    "key": "API key",
    "person": "a person in a browser",
    "loaded": "already in Cloé's database",
}
KEY_ENV = {"kvk": "CLOE_KVK_API_KEY", "overheidio": "CLOE_OVERHEIDIO_API_KEY"}
# Domains for `site:` searches in the API engine's web research (news and trade press
# without a usable site search, or with one that needs a browser).
PRESS_DOMAINS = (
    "textilia.nl", "fashionunited.nl", "modint.nl", "innovationintextiles.com",
    "ecotextile.com", "knittingindustry.com", "fibre2fashion.com", "just-style.com",
    "tubantia.nl", "bd.nl", "nos.nl", "nu.nl", "fd.nl", "nrc.nl", "volkskrant.nl",
    "rtl.nl", "bnr.nl", "emerce.nl", "mt.nl", "duurzaam-ondernemen.nl", "change.inc",
    "fashionforgood.com", "circle-economy.com", "dutchcirculartextilevalley.nl",
)
SOCIAL_DOMAINS = ("linkedin.com", "facebook.com", "instagram.com", "x.com", "twitter.com",
                  "tiktok.com")
_LEGAL_FORM = re.compile(
    r"[\s,]*\b(b\.?\s?v\.?|n\.?\s?v\.?|v\.?\s?o\.?\s?f\.?|c\.?\s?v\.?|holding|groep|group|"
    r"international|b\.?v\.?i\.?o\.?|eenmanszaak|stichting)\b\.?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Register:
    key: str
    name: str
    group: str
    keyed: str      # kvk | name | domain | local
    access: str     # open | key | person | loaded
    format: str     # json | xml | rss | html | search | local
    gives: str
    url: str = ""   # template with {kvk} {q} {qq} {domain}; empty for local sources
    parser: str | None = None   # a key of PARSERS
    kind: str = "other"         # Mention.kind for its hits
    api_key: str | None = None  # KEY_ENV key for `access == "key"`
    note: str = ""


@dataclass
class Mention:
    url: str
    title: str
    date: str | None = None     # YYYY-MM-DD, YYYY-MM or YYYY
    outlet: str = ""
    kind: str = "other"
    one_line: str = ""
    register: str = ""


@dataclass
class Parsed:
    mentions: list[Mention] = field(default_factory=list)
    identity: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class Subject:
    """What is known about the company before the run; it decides which sources apply."""

    name: str
    kvk: str | None = None
    domain: str | None = None
    city: str | None = None


@dataclass(frozen=True)
class Query:
    register: Register
    url: str
    headers: dict[str, str] = field(default_factory=dict)


def R(key, name, group, keyed, access, fmt, gives, url="", **kw) -> Register:
    return Register(key, name, group, keyed, access, fmt, gives, url, **kw)


SPARQL = (
    'SELECT ?item ?itemLabel ?article ?inception ?website WHERE {{ ?item wdt:P3220 "{kvk}" . '
    "OPTIONAL {{ ?article schema:about ?item ; schema:isPartOf <https://nl.wikipedia.org/> }} "
    "OPTIONAL {{ ?item wdt:P571 ?inception }} OPTIONAL {{ ?item wdt:P856 ?website }} "
    'SERVICE wikibase:label {{ bd:serviceParam wikibase:language "nl,en". }} }}'
)
SRU = ("https://zoek.officielebekendmakingen.nl/sru/Search?version=2.0&operation=searchRetrieve"
       "&x-connection=officielepublicaties&maximumRecords=25&query=cql.textAndIndexes%3D{qq}")

CATALOGUE: tuple[Register, ...] = (
    # -- identity ---------------------------------------------------------------------
    R("site_colofon", "The company's own website", "identity", "domain", "open", "html",
      "KvK number, BTW-id, address and trade names: Dutch law (Handelsregisterwet art. 27) "
      "makes a company print its KvK number on its site; crawled by `sources/web.py`",
      "https://{domain}/"),
    R("kvk_zoeken", "KVK API — Zoeken (name → KvK number)", "identity", "name", "key", "json",
      "KvK numbers, names and places matching the name; the way in when TELL has no number",
      "https://api.kvk.nl/api/v2/zoeken?naam={q}&resultatenPerPagina=10", parser="kvk_zoeken",
      kind="register", api_key="kvk", note="free key from developers.kvk.nl"),
    R("kvk_basisprofiel", "KVK API — Basisprofiel", "identity", "kvk", "key", "json",
      "official name, trade names, legal form, SBI activities, employees, registration date, "
      "main branch address", "https://api.kvk.nl/api/v1/basisprofielen/{kvk}",
      parser="kvk_profile", kind="register", api_key="kvk", note="metered per call"),
    R("openkvk", "OpenKVK (overheid.io)", "identity", "kvk", "key", "json",
      "Handelsregister mirror: name, address, SBI, legal form, status",
      "https://api.overheid.io/v3/openkvk/{kvk}", parser="kvk_profile", kind="register",
      api_key="overheidio", note="free tier; endpoint version unverified from a cloud session"),
    R("opencorporates", "OpenCorporates", "identity", "kvk", "open", "json",
      "status, incorporation date, previous names, industry codes; the web page lists "
      "register events", "https://api.opencorporates.com/v0.4/companies/nl/{kvk}",
      parser="opencorporates", kind="register",
      note="the API without a key is rate-limited; the page https://opencorporates.com/"
           "companies/nl/<kvk> is open"),
    R("wikidata", "Wikidata (property P3220 = KvK number)", "identity", "kvk", "open", "json",
      "the Wikipedia article, founding date, website and other identifiers",
      "https://query.wikidata.org/sparql?format=json&query=" + quote(SPARQL, safe="{}"),
      parser="wikidata", kind="other"),
    R("wikipedia_nl", "Wikipedia (nl)", "identity", "name", "open", "json",
      "articles that mention the company (also try en.wikipedia.org)",
      "https://nl.wikipedia.org/w/api.php?action=query&list=search&srsearch={qq}&format=json"
      "&srlimit=5", parser="mediawiki", kind="other"),
    # -- official ---------------------------------------------------------------------
    R("bekendmakingen", "Officiële bekendmakingen (SRU)", "official", "name", "open", "xml",
      "Staatscourant: faillissement, surseance, fusie, splitsing, ontbinding, liquidatie; "
      "Gemeenteblad/Provinciaal blad: vergunningen at their address; Kamerstukken",
      SRU, parser="sru", kind="register"),
    R("insolventieregister", "Centraal Insolventieregister", "official", "kvk", "person",
      "search", "current and past insolvency of the company (search by KvK number)",
      "https://insolventies.rechtspraak.nl/", note="also published in the Staatscourant"),
    R("rechtspraak", "Rechtspraak.nl — uitspraken", "official", "name", "open", "search",
      "court decisions naming the company (companies are not anonymised)",
      "https://uitspraken.rechtspraak.nl/resultaat?zoekterm={qq}",
      note="the open-data API has no full-text search; use the site or web search"),
    # -- funding, projects, procurement ------------------------------------------------
    R("mdpp_projects", "M-DPP research-funding network (loaded)", "funding", "local", "loaded",
      "local", "the 2,530 EU/NWO projects with a Dutch partner already in Cloé's database: "
      "projects naming this company among the Dutch organisations", kind="project"),
    R("library", "Cloé's research library (loaded)", "funding", "local", "loaded", "local",
      "documents already carded that mention the company", kind="other"),
    R("rvo_projecten", "RVO projectendatabase", "funding", "name", "open", "search",
      "Dutch subsidies granted (MIT, DEI+, TSE, EFRO, Interreg…) with amounts",
      "https://projecten.rvo.nl/projecten?search={q}", kind="project",
      note="search parameter unverified from a cloud session"),
    R("cordis", "CORDIS", "funding", "name", "open", "search",
      "EU research projects beyond the M-DPP textile subset",
      "https://cordis.europa.eu/search?q={qq}&p=1&num=10&srt=Relevance:decreasing",
      kind="project"),
    R("kohesio", "Kohesio (EU cohesion: EFRO, ESF, Interreg)", "funding", "name", "open",
      "search", "regional EU-funded projects with the company as beneficiary",
      "https://kohesio.ec.europa.eu/en/projects?keywords={q}&country=Netherlands",
      kind="project"),
    R("eu_fts", "EU Financial Transparency System", "funding", "name", "person", "search",
      "direct EU grants and contracts by beneficiary name",
      "https://ec.europa.eu/budget/financial-transparency-system/", kind="project"),
    R("ted", "TED — Tenders Electronic Daily", "funding", "name", "open", "search",
      "EU contract awards naming the company as winner (workwear, linen, uniforms)",
      "https://ted.europa.eu/en/search/result?FT={qq}", kind="procurement",
      note="API: https://api.ted.europa.eu/v3/notices/search"),
    R("tenderned", "TenderNed", "funding", "name", "open", "search",
      "Dutch public procurement notices and awards",
      "https://www.tenderned.nl/aankondigingen/overzicht?zoekterm={q}", kind="procurement"),
    R("keep_eu", "keep.eu (Interreg projects)", "funding", "name", "open", "search",
      "cross-border Interreg projects and partners", "https://keep.eu/projects/?keywords={q}",
      kind="project"),
    # -- patents, trademarks, certifications ---------------------------------------------
    R("espacenet", "Espacenet (EPO)", "ip_cert", "name", "open", "search",
      "patents with the company as applicant; EPO OPS has an API (free key)",
      "https://worldwide.espacenet.com/patent/search?q=pa%3D{qq}", kind="patent"),
    R("google_patents", "Google Patents", "ip_cert", "name", "open", "search",
      "patents by assignee, full text", "https://patents.google.com/?assignee={q}",
      kind="patent"),
    R("nl_octrooiregister", "Nederlands octrooiregister (RVO)", "ip_cert", "name", "open",
      "search", "Dutch national patents by applicant", "https://register.octrooicentrum.nl/",
      kind="patent"),
    R("tmview", "TMview (BOIP + EUIPO trademarks)", "ip_cert", "name", "open", "search",
      "registered brand names: the trade names to search news for",
      "https://www.tmdn.org/tmview/", kind="register"),
    R("gots", "GOTS certified suppliers database", "ip_cert", "name", "open", "search",
      "GOTS certification, scope and products",
      "https://global-standard.org/find-suppliers-shops-and-inputs/certified-suppliers/database",
      kind="certification"),
    R("textile_exchange", "Textile Exchange certified companies (GRS, RCS, OCS, RWS)",
      "ip_cert", "name", "open", "search", "recycled/organic content certification",
      "https://textileexchange.org/find-certified-company/", kind="certification"),
    R("oeko_tex", "OEKO-TEX buying guide", "ip_cert", "name", "open", "search",
      "STANDARD 100, MADE IN GREEN, STeP certificates",
      "https://www.oeko-tex.com/en/buying-guide?q={q}", kind="certification"),
    R("fairwear", "Fair Wear Foundation member brands", "ip_cert", "name", "open", "search",
      "membership and brand performance checks", "https://www.fairwear.org/brands/",
      kind="certification"),
    R("bcorp", "B Corp directory", "ip_cert", "name", "open", "search",
      "B Corp certification and impact score",
      "https://www.bcorporation.net/en-us/find-a-b-corp/?search={q}", kind="certification"),
    R("sbti", "Science Based Targets — companies taking action", "ip_cert", "name", "open",
      "search", "climate targets (CSV export on the page)",
      "https://sciencebasedtargets.org/companies-taking-action", kind="certification"),
    R("upv_textiel", "UPV Textiel (extended producer responsibility register)", "ip_cert",
      "name", "person", "search", "whether they are a registered textile producer/importer",
      "https://www.upvtextiel.nl/", kind="register",
      note="check on the MacBook whether the producer list is public"),
    R("anbi", "ANBI register (Belastingdienst)", "ip_cert", "name", "person", "search",
      "for stichtingen: ANBI status and the published annual reports",
      "https://www.belastingdienst.nl/wps/wcm/connect/nl/aftrek-en-kortingen/content/"
      "anbi-status-controleren", kind="register"),
    # -- news -------------------------------------------------------------------------
    R("google_news", "Google News RSS (nl)", "news", "name", "open", "rss",
      "articles in Dutch media naming the company, with dates and outlets",
      "https://news.google.com/rss/search?q={qq}&hl=nl&gl=NL&ceid=NL:nl", parser="rss",
      kind="news", note="links are Google redirects; the fetcher follows them"),
    R("google_news_en", "Google News RSS (en)", "news", "name", "open", "rss",
      "articles in English-language trade press",
      "https://news.google.com/rss/search?q={qq}&hl=en&gl=NL&ceid=NL:en", parser="rss",
      kind="news"),
    R("bing_news", "Bing News RSS", "news", "name", "open", "rss", "a second news index",
      "https://www.bing.com/news/search?q={qq}&format=rss", parser="rss", kind="news"),
    R("gdelt", "GDELT DOC 2.0", "news", "name", "open", "json",
      "global news monitoring, last 24 months, with language and country",
      "https://api.gdeltproject.org/api/v2/doc/doc?query={qq}&mode=artlist&format=json"
      "&maxrecords=50&timespan=24m", parser="gdelt", kind="news"),
    R("textilia", "Textilia", "news", "name", "open", "search", "Dutch textile trade press",
      "https://www.textilia.nl/?s={q}", kind="news"),
    R("fashionunited", "FashionUnited (nl)", "news", "name", "open", "search",
      "fashion industry news", "https://fashionunited.nl/zoeken?q={q}", kind="news"),
    R("modint", "Modint", "news", "name", "open", "search", "the trade association's news",
      "https://www.modint.nl/?s={q}", kind="news"),
    R("innovation_in_textiles", "Innovation in Textiles", "news", "name", "open", "search",
      "technical textiles news (en)", "https://www.innovationintextiles.com/?s={q}",
      kind="news"),
    R("ecotextile", "Ecotextile News", "news", "name", "open", "search",
      "sustainability in textiles (en, partly paywalled)",
      "https://www.ecotextile.com/search.html?searchword={q}", kind="news"),
    R("knitting_industry", "Knitting Industry", "news", "name", "open", "search",
      "knitting technology news (en)", "https://www.knittingindustry.com/?s={q}", kind="news"),
    R("youtube", "YouTube", "news", "name", "person", "search",
      "company videos, fair presentations, interviews",
      "https://www.youtube.com/results?search_query={qq}", kind="event"),
    R("wayback", "Wayback Machine (CDX)", "news", "domain", "open", "json",
      "when their site first appeared and one archived copy per year: old products, "
      "old names", "https://web.archive.org/cdx/search/cdx?url={domain}&output=json"
      "&fl=timestamp,original&filter=statuscode:200&collapse=timestamp:4&limit=50",
      parser="wayback", kind="archive"),
    # -- academic ---------------------------------------------------------------------
    R("openalex", "OpenAlex", "academic", "name", "open", "json",
      "papers with the company in an author affiliation",
      "https://api.openalex.org/works?filter=raw_affiliation_strings.search:{q}&per-page=25"
      "&sort=publication_date:desc", parser="openalex", kind="publication"),
    R("crossref", "Crossref", "academic", "name", "open", "json",
      "papers by affiliation (a second index)",
      "https://api.crossref.org/works?query.affiliation={q}&rows=20&sort=published&order=desc",
      parser="crossref", kind="publication"),
    R("zenodo", "Zenodo", "academic", "name", "open", "json",
      "open-access deliverables and datasets that mention the company",
      "https://zenodo.org/api/records?q={qq}&size=20&sort=mostrecent", parser="zenodo",
      kind="publication"),
    # -- people -----------------------------------------------------------------------
    R("site_team", "The company's own team page", "people", "domain", "open", "html",
      "names and business roles the company publishes itself (crawled)", "https://{domain}/"),
    R("linkedin", "LinkedIn (a person, in their own browser)", "people", "name", "person",
      "search", "company page, people with their business role, what they post about",
      "https://www.linkedin.com/search/results/companies/?keywords={q}",
      note="never scraped: see the LinkedIn rules in the work order"),
    # -- HvA library ------------------------------------------------------------------
    R("nexis_uni", "Nexis Uni (LexisNexis)", "library_access", "name", "person", "search",
      "full-text archive of Dutch and international newspapers: the complete press record",
      "https://www.lexisnexis.com/en-us/professional/academic/nexis-uni.page"),
    R("company_info", "Company.info", "library_access", "name", "person", "search",
      "KvK data with annual-accounts figures, group structure and news",
      "https://companyinfo.nl/"),
)
BY_KEY = {r.key: r for r in CATALOGUE}


# -- queries ----------------------------------------------------------------------------


def search_name(name: str) -> str:
    """The name as people write it in articles: without the legal form."""
    out = scrub(name or "", 200)
    for _ in range(2):
        out = _LEGAL_FORM.sub("", out).strip(" ,.-")
    return " ".join(out.split())


def url_for(register: Register, subject: Subject) -> str | None:
    """The register's URL for this company, or None when the key it needs is unknown."""
    if register.keyed == "local" or not register.url:
        return None
    if register.keyed == "kvk" and not subject.kvk:
        return None
    if register.keyed == "domain" and not subject.domain:
        return None
    q = search_name(subject.name)
    if register.keyed == "name" and not q:
        return None
    values = {"kvk": subject.kvk or "", "domain": subject.domain or "",
              "q": quote(q, safe=""), "qq": quote(f'"{q}"', safe="")}
    # Braces survive the templates only inside the SPARQL query; encode them for the wire.
    return register.url.format_map(values).replace("{", "%7B").replace("}", "%7D")


def queries(subject: Subject, keys: dict[str, str] | None = None, *,
            parsed_only: bool = True) -> tuple[list[Query], list[str]]:
    """The fetchable queries for a company, and why the others were skipped. `keys` maps
    KEY_ENV names ("kvk", "overheidio") to API keys; keyed registers without one are
    skipped. With `parsed_only`, only registers Cloé can read by code are returned."""
    keys = keys or {}
    out, skipped = [], []
    for reg in CATALOGUE:
        if parsed_only and reg.parser is None:
            continue
        if reg.access not in ("open", "key"):
            continue
        url = url_for(reg, subject)
        if url is None:
            skipped.append(f"{reg.key}: needs the {reg.keyed}")
            continue
        headers: dict[str, str] = {}
        if reg.access == "key":
            key = keys.get(reg.api_key or "")
            if not key:
                skipped.append(f"{reg.key}: no {KEY_ENV[reg.api_key]}")
                continue
            headers = {"apikey": key} if reg.api_key == "kvk" else {"ovio-api-key": key}
        out.append(Query(reg, url, headers))
    return out, skipped


def describe(subject: Subject) -> list[str]:
    """Markdown lines listing every source for this company, URLs filled in, by group."""
    lines: list[str] = []
    for group, title in GROUPS.items():
        lines += ["", f"### {title}", ""]
        for reg in CATALOGUE:
            if reg.group != group:
                continue
            url = url_for(reg, subject)
            how = ACCESS[reg.access] + (f" ({KEY_ENV[reg.api_key]})" if reg.api_key else "")
            read = "Cloé reads it" if reg.parser or reg.keyed == "local" else "to read"
            where = f"<{url}>" if url else (
                "already in the database" if reg.keyed == "local"
                else f"needs the {reg.keyed} first ({reg.url.split('{')[0]}…)")
            note = f" _{reg.note}._" if reg.note else ""
            lines.append(f"- **{reg.name}** — {reg.gives}. {how}; {read}: {where}{note}")
    return lines


# -- parsers ----------------------------------------------------------------------------


def _local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1].lower()


def _texts(elem, *names: str) -> list[str]:
    wanted = set(names)
    return [" ".join(e.text.split()) for e in elem.iter()
            if _local(e.tag) in wanted and e.text and e.text.strip()]


def _first(elem, *names: str) -> str:
    """The first text under `elem` for the first of `names` that has one."""
    for name in names:
        if found := _texts(elem, name):
            return found[0]
    return ""


def iso_date(value: object) -> str | None:
    """YYYY-MM-DD / YYYY-MM / YYYY from ISO, compact (20251016T120000Z), RFC 2822 and
    Dutch d-m-Y dates; None when unreadable."""
    s = str(value or "").strip()
    if not s:
        return None
    if m := re.match(r"^((?:19|20)\d{2})-?(\d{2})-?(\d{2})(?:[T\s]|$)", s):
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if m := re.match(r"^((?:19|20)\d{2})(?:-(\d{2}))?$", s):
        return m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")
    if m := re.match(r"^(\d{1,2})-(\d{1,2})-((?:19|20)\d{2})$", s):
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    try:
        dt = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        return None
    return dt.date().isoformat() if dt else None


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def _short(value: object, n: int) -> str:
    return " ".join(scrub(str(value or ""), n * 4).split())[:n]


def _url(value: object) -> str:
    s = _short(value, 2000)
    return s if s.startswith(("http://", "https://")) else ""


def _json(content: bytes) -> Any:
    try:
        return json.loads(content.decode("utf-8", errors="replace"))
    except ValueError as exc:
        raise ValueError(f"not JSON: {str(exc)[:60]}") from None


def _pick(d: Any, *keys: str, default: Any = None) -> Any:
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] not in (None, "", []):
            return d[k]
    return default


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_rss(reg: Register, content: bytes) -> Parsed:
    root = ElementTree.fromstring(content)
    out = Parsed()
    for item in root.iter():
        if _local(item.tag) not in ("item", "entry"):
            continue
        link = _first(item, "link")
        if not link:
            link = next((e.get("href", "") for e in item if _local(e.tag) == "link"), "")
        url = _url(link)
        if not url:
            continue
        source = next((e for e in item if _local(e.tag) == "source"), None)
        outlet = _short(source.text if source is not None and source.text else "", 100) \
            or _host(source.get("url", "") if source is not None else "") or _host(url)
        out.mentions.append(Mention(
            url=url, title=_short(_first(item, "title"), 300),
            date=iso_date(_first(item, "pubdate", "published", "updated", "date")),
            outlet=outlet, kind=reg.kind,
            one_line=_short(re.sub(r"<[^>]+>", " ", _first(item, "description", "summary")),
                            240), register=reg.key))
    return out


def parse_gdelt(reg: Register, content: bytes) -> Parsed:
    data = _json(content)
    out = Parsed()
    for a in _list(_pick(data, "articles", default=[])):
        url = _url(_pick(a, "url"))
        if not url:
            continue
        out.mentions.append(Mention(
            url=url, title=_short(_pick(a, "title"), 300), date=iso_date(_pick(a, "seendate")),
            outlet=_short(_pick(a, "domain", default=_host(url)), 100), kind=reg.kind,
            one_line=_short(" ".join(x for x in (_pick(a, "language"),
                                                 _pick(a, "sourcecountry")) if x), 60),
            register=reg.key))
    return out


def parse_wikidata(reg: Register, content: bytes) -> Parsed:
    data = _json(content)
    out = Parsed()
    for b in _list(_pick(_pick(data, "results", default={}), "bindings", default=[])):
        if _binding(b, "item") and "wikidata" not in out.identity:
            out.identity["wikidata"] = _binding(b, "item")
            out.identity["name"] = _binding(b, "itemLabel")
            if year := iso_date(_binding(b, "inception")):
                out.identity["founded"] = int(year[:4])
            if site := _url(_binding(b, "website")):
                out.identity["website"] = site
        if article := _url(_binding(b, "article")):
            out.mentions.append(Mention(url=article, kind=reg.kind, register=reg.key,
                                        title=f"Wikipedia: {_binding(b, 'itemLabel')}",
                                        outlet=_host(article)))
    return out


def _binding(b: Any, name: str) -> str:
    return _short(_pick(_pick(b, name, default={}), "value"), 500)


def parse_mediawiki(reg: Register, content: bytes) -> Parsed:
    data = _json(content)
    out = Parsed()
    for hit in _list(_pick(_pick(data, "query", default={}), "search", default=[])):
        title = _short(_pick(hit, "title"), 300)
        if not title:
            continue
        out.mentions.append(Mention(
            url="https://nl.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="_()"),
            title=title, date=iso_date(_pick(hit, "timestamp")), outlet="nl.wikipedia.org",
            kind=reg.kind, one_line=_short(re.sub(r"<[^>]+>", "", str(_pick(hit, "snippet",
                                                                           default=""))), 240),
            register=reg.key))
    return out


def parse_sru(reg: Register, content: bytes) -> Parsed:
    root = ElementTree.fromstring(content)
    out = Parsed()
    for rec in root.iter():
        if _local(rec.tag) != "record":
            continue
        ident = _first(rec, "identifier")
        url = _url(_first(rec, "url")) or _url(ident)
        if not url and re.fullmatch(r"[a-z]+-\d{4}-\d+", ident):
            url = f"https://zoek.officielebekendmakingen.nl/{ident}.html"
        if not url:
            continue
        kind_text = _first(rec, "publicatienaam", "documenttype", "type")
        abstract = _first(rec, "abstract", "description")
        out.mentions.append(Mention(
            url=url, title=_short(_first(rec, "title"), 300),
            date=iso_date(_first(rec, "available", "issued", "date", "modified")),
            outlet=_short(_first(rec, "publisher", "creator"), 100) or "Officiële bekendmakingen",
            kind=reg.kind, one_line=_short(": ".join(x for x in (kind_text, abstract) if x), 240),
            register=reg.key))
    return out


def parse_opencorporates(reg: Register, content: bytes) -> Parsed:
    data = _json(content)
    company = _pick(_pick(data, "results", default={}), "company", default={})
    out = Parsed()
    if not isinstance(company, dict) or not company:
        return out
    ident = out.identity
    ident["name"] = _short(_pick(company, "name"), 200)
    ident["status"] = _short(_pick(company, "current_status"), 60)
    ident["legal_form"] = _short(_pick(company, "company_type"), 60)
    if year := iso_date(_pick(company, "incorporation_date")):
        ident["founded"] = int(year[:4])
    ident["previous_names"] = [_short(_pick(p, "company_name"), 200)
                               for p in _list(_pick(company, "previous_names", default=[]))
                               if _pick(p, "company_name")]
    ident["sbi"] = [{"code": _short(_pick(c, "code"), 12),
                     "text": _short(_pick(c, "description"), 120)}
                    for c in (_pick(x, "industry_code", default=x)
                              for x in _list(_pick(company, "industry_codes", default=[])))
                    if _pick(c, "code")]
    page = _url(_pick(company, "opencorporates_url"))
    if page:
        out.mentions.append(Mention(
            url=page, title=f"OpenCorporates: {ident['name']}", kind=reg.kind,
            date=iso_date(_pick(company, "updated_at")), outlet="opencorporates.com",
            one_line=_short(" · ".join(x for x in (ident["status"], ident["legal_form"],
                                                   _pick(company, "registered_address_in_full"))
                                       if x), 240), register=reg.key))
    return out


def parse_kvk_zoeken(reg: Register, content: bytes) -> Parsed:
    data = _json(content)
    out = Parsed()
    seen: list[dict[str, str]] = []
    for r in _list(_pick(data, "resultaten", default=[])):
        kvk = re.sub(r"\D", "", str(_pick(r, "kvkNummer", default="")))
        if len(kvk) != 8:
            continue
        adres = _pick(_pick(r, "adres", default={}), "binnenlandsAdres", default={})
        entry = {"kvk": kvk, "name": _short(_pick(r, "naam"), 200),
                 "city": _short(_pick(r, "plaats") or _pick(adres, "plaats"), 100),
                 "type": _short(_pick(r, "type"), 40)}
        if entry["kvk"] not in {s["kvk"] for s in seen}:
            seen.append(entry)
    out.identity["kvk_candidates"] = seen
    return out


def parse_kvk_profile(reg: Register, content: bytes) -> Parsed:
    """KVK Basisprofiel and OpenKVK share the fields, under different names."""
    data = _json(content)
    out = Parsed()
    if not isinstance(data, dict):
        return out
    ident = out.identity
    kvk = re.sub(r"\D", "", str(_pick(data, "kvkNummer", "dossiernummer", "kvk", default="")))
    if len(kvk) == 8:
        ident["kvk"] = kvk
    ident["name"] = _short(_pick(data, "naam", "handelsnaam", "statutaireNaam", "name"), 200)
    names = [_short(_pick(h, "naam", default=h), 200)
             for h in _list(_pick(data, "handelsnamen", "handelsnaam_lijst", default=[]))]
    ident["trade_names"] = [n for n in names if n and n != ident["name"]]
    ident["legal_form"] = _short(_pick(data, "rechtsvorm", "rechtsvormOmschrijving"), 60)
    sbi = []
    for s in _list(_pick(data, "sbiActiviteiten", "sbi", default=[])):
        code = _short(_pick(s, "sbiCode", "code", default=s if isinstance(s, str) else ""), 12)
        if code:
            sbi.append({"code": code, "text": _short(_pick(s, "sbiOmschrijving", "omschrijving"),
                                                     120),
                        "main": str(_pick(s, "indHoofdactiviteit", default="")).lower() == "ja"})
    ident["sbi"] = sbi
    start = _pick(data, "formeleRegistratiedatum", "datum_inschrijving", "oprichtingsdatum")
    if not start:
        start = _pick(_pick(data, "materieleRegistratie", default={}), "datumAanvang")
    if year := iso_date(start):
        ident["founded"] = int(year[:4])
    if staff := _pick(data, "totaalWerkzamePersonen", "werkzame_personen"):
        ident["employees"] = _short(staff, 20)
    branch = _pick(_pick(data, "_embedded", default={}), "hoofdvestiging", default={})
    for adr in _list(_pick(branch, "adressen", default=[])) or [data]:
        if city := _pick(adr, "plaats"):
            ident["city"] = _short(city, 100)
            break
    status = _pick(data, "actief", "status")
    if isinstance(status, bool):
        ident["status"] = "active" if status else "inactive"
    elif status:
        ident["status"] = _short(status, 40)
    return out


def parse_openalex(reg: Register, content: bytes) -> Parsed:
    data = _json(content)
    out = Parsed()
    for w in _list(_pick(data, "results", default=[])):
        loc = _pick(w, "primary_location", default={})
        url = _url(_pick(w, "doi")) or _url(_pick(loc, "landing_page_url")) or _url(_pick(w, "id"))
        if not url:
            continue
        out.mentions.append(Mention(
            url=url, title=_short(_pick(w, "display_name", "title"), 300),
            date=iso_date(_pick(w, "publication_date", "publication_year")),
            outlet=_short(_pick(_pick(loc, "source", default={}), "display_name"), 100)
            or "openalex.org", kind=reg.kind, register=reg.key))
    return out


def parse_crossref(reg: Register, content: bytes) -> Parsed:
    data = _json(content)
    out = Parsed()
    for it in _list(_pick(_pick(data, "message", default={}), "items", default=[])):
        url = _url(_pick(it, "URL")) or (f"https://doi.org/{it['DOI']}" if _pick(it, "DOI")
                                         else "")
        if not url:
            continue
        parts = _list(_pick(_pick(it, "issued", default={}), "date-parts", default=[[]]))
        first = _list(parts[0]) if parts else []
        date = "-".join(f"{int(p):02d}" if i else str(p) for i, p in enumerate(first[:3])
                        if isinstance(p, int)) or None
        out.mentions.append(Mention(
            url=url, title=_short(" ".join(_list(_pick(it, "title", default=[]))[:1]), 300),
            date=iso_date(date), kind=reg.kind,
            outlet=_short(" ".join(_list(_pick(it, "container-title", default=[]))[:1])
                          or _pick(it, "publisher", default=""), 100) or "crossref.org",
            register=reg.key))
    return out


def parse_wayback(reg: Register, content: bytes) -> Parsed:
    data = _json(content)
    out = Parsed()
    rows = [r for r in _list(data) if isinstance(r, list) and len(r) >= 2]
    for ts, original in (r[:2] for r in rows[1:] if rows and rows[0][:1] == ["timestamp"]):
        ts, original = str(ts), str(original)
        if not re.fullmatch(r"\d{14}", ts) or not _url(original):
            continue
        out.mentions.append(Mention(
            url=f"https://web.archive.org/web/{ts}/{_url(original)}",
            title=f"Archived copy of {_host(original)} ({ts[:4]})", date=iso_date(ts[:8]),
            outlet="web.archive.org", kind=reg.kind, register=reg.key))
    return out


def parse_zenodo(reg: Register, content: bytes) -> Parsed:
    data = _json(content)
    out = Parsed()
    for hit in _list(_pick(_pick(data, "hits", default={}), "hits", default=[])):
        meta = _pick(hit, "metadata", default={})
        links = _pick(hit, "links", default={})
        url = _url(_pick(links, "self_html", "doi")) or (
            f"https://zenodo.org/records/{hit['id']}" if _pick(hit, "id") else "")
        if not url:
            continue
        out.mentions.append(Mention(
            url=url, title=_short(_pick(meta, "title"), 300),
            date=iso_date(_pick(meta, "publication_date")), outlet="zenodo.org",
            kind=reg.kind, one_line=_short(_pick(_pick(meta, "resource_type", default={}),
                                                 "title", "type"), 60), register=reg.key))
    return out


PARSERS = {
    "rss": parse_rss, "gdelt": parse_gdelt, "wikidata": parse_wikidata,
    "mediawiki": parse_mediawiki, "sru": parse_sru, "opencorporates": parse_opencorporates,
    "kvk_zoeken": parse_kvk_zoeken, "kvk_profile": parse_kvk_profile, "openalex": parse_openalex,
    "crossref": parse_crossref, "wayback": parse_wayback, "zenodo": parse_zenodo,
}


def parse(register: Register, content: bytes) -> Parsed:
    """Run the register's parser; a response it cannot read gives an empty `Parsed` with
    `error` set. Titles and lines are scrubbed and capped; URLs must be http(s)."""
    fn = PARSERS.get(register.parser or "")
    if fn is None:
        return Parsed(error=f"{register.key} has no parser")
    try:
        parsed = fn(register, content)
    except (ValueError, ElementTree.ParseError, TypeError, KeyError, AttributeError) as exc:
        return Parsed(error=f"{register.key}: unreadable response ({type(exc).__name__})")
    for m in parsed.mentions:
        m.kind = m.kind if m.kind in MENTION_KINDS else "other"
    parsed.mentions = [m for m in parsed.mentions if m.url][:200]
    return parsed
