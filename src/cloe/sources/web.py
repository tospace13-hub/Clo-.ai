"""Crawl a company's own website: the pages that say who they are and what they do.

`crawl_site(fetcher, domain, max_pages=8)`: the homepage, then the links whose path or
text uses the words companies use for those pages (about / over ons, team, products,
services, sustainability, news, vacancies, annual report, contact, colofon). Only the
site's own host (with or without `www.`) is followed. Everything else — other sites,
`mailto:`, the metadata address a hostile page may link to — is left alone, and the
fetcher's own address check guards every request anyway. Text comes from `fetch.to_text`
and is untrusted: `research.py` wraps it before a model reads it.

`find_kvk(text)` reads the KvK number a Dutch company must print on its site.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from cloe.sources import fetch

DEFAULT_MAX_PAGES = 8
# In the order Cloé wants them: who they are, what they do, what they say, who to ask.
LINK_WORDS = (
    "about", "over ons", "over", "wie zijn wij", "about us", "organisatie", "bedrijf",
    "team", "mensen", "people", "products", "producten", "collectie", "collection",
    "services", "diensten", "sustainability", "duurzaam", "duurzaamheid", "mvo", "csr",
    "impact", "circulair", "circular", "news", "nieuws", "blog", "pers", "press", "actueel",
    "vacatures", "jobs", "werken bij", "careers", "jaarverslag", "annual report",
    "contact", "colofon", "impressum",
)
SKIP_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip", ".mp4", ".mp3",
                   ".css", ".js", ".ico", ".woff", ".woff2", ".xml", ".json")
_KVK = re.compile(
    r"(?:kvk|k\.v\.k\.|kamer van koophandel|handelsregister|chamber of commerce|coc)"
    r"[^0-9\n]{0,30}?(\d[\d .]{6,12}\d)",
    re.IGNORECASE,
)
_WORD_PATTERNS = [(i, re.compile(rf"\b{re.escape(w)}\b")) for i, w in enumerate(LINK_WORDS)]


@dataclass
class Page:
    url: str
    final_url: str
    title: str
    text: str
    content_type: str
    content: bytes
    sha256: str
    raw_path: str | None


@dataclass
class Crawl:
    pages: list[Page] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    offsite_links: int = 0
    kvk: str | None = None


def site_host(domain_or_url: str) -> str:
    """The bare host: no scheme, `www.` or path."""
    s = domain_or_url.strip().lower()
    host = urlsplit(s if "://" in s else f"https://{s}").hostname or ""
    return host.removeprefix("www.")


def same_site(url: str, host: str) -> bool:
    return site_host(url) == host and urlsplit(url).scheme in ("http", "https")


def find_kvk(text: str) -> str | None:
    """The 8-digit KvK number named most often in `text`, else None."""
    counts = Counter(
        digits for m in _KVK.finditer(text)
        if len(digits := re.sub(r"\D", "", m.group(1))) == 8
    )
    return counts.most_common(1)[0][0] if counts else None


def _rank(path: str, text: str) -> int | None:
    haystack = re.sub(r"[^a-z0-9]+", " ", f"{path} {text}".lower())
    return next((i for i, p in _WORD_PATTERNS if p.search(haystack)), None)


def ranked_links(page: Page, host: str) -> tuple[list[tuple[int, str]], int]:
    """(rank, url) for the page's own-site links worth reading, and how many pointed
    elsewhere. Links with a query string or a media extension are left out."""
    if page.content_type != "text/html":
        return [], 0
    soup = fetch.soup_of(page.content)
    found: dict[str, int] = {}
    offsite = 0
    for a in soup.find_all("a"):
        url = fetch.absolute_link(a.get("href"), page.final_url)
        if url is None:
            continue
        if not same_site(url, host):
            offsite += 1
            continue
        parts = urlsplit(url)
        if parts.query or parts.path.lower().endswith(SKIP_EXTENSIONS):
            continue
        clean = url.rstrip("/") or url
        rank = _rank(parts.path, " ".join(a.get_text(" ").split()))
        if rank is not None and rank < found.get(clean, len(LINK_WORDS)):
            found[clean] = rank
    return sorted(((r, u) for u, r in found.items()), key=lambda x: (x[0], x[1])), offsite


def _page(got: fetch.Fetched) -> Page:
    title = fetch.html_title(got.content) if got.content_type == "text/html" else ""
    return Page(got.url, got.final_url, title, fetch.to_text(got), got.content_type,
                got.content, got.sha256, got.raw_path)


def crawl_site(fetcher, domain: str, *, max_pages: int = DEFAULT_MAX_PAGES,
               start_url: str | None = None) -> Crawl:
    """Read up to `max_pages` pages of the company's own site. The first page is
    `start_url` or `https://<domain>/` (then `http://` when https fails outright)."""
    host = site_host(domain)
    crawl = Crawl()
    if not host:
        crawl.errors.append(f"no host in {domain!r}")
        return crawl
    starts = [start_url] if start_url else [f"https://{host}/", f"http://{host}/"]
    seen: set[str] = set()
    queue: list[tuple[int, str]] = []

    def visit(url: str) -> bool:
        seen.add(_key(url))
        try:
            got = fetcher.fetch(url)
        except fetch.FetchError as exc:
            crawl.errors.append(f"{url}: {exc}")
            return False
        page = _page(got)
        crawl.pages.append(page)
        links, offsite = ranked_links(page, host)
        crawl.offsite_links += offsite
        queue.extend(links)
        return True

    if not any(visit(url) for url in starts):
        return crawl
    while queue and len(crawl.pages) < max_pages:
        queue.sort()
        _rank, url = queue.pop(0)
        if _key(url) not in seen:
            visit(url)
    crawl.kvk = find_kvk("\n".join(p.text for p in crawl.pages))
    return crawl


def _key(url: str) -> str:
    """One visit per page, whatever the scheme or `www.`."""
    key = url.rstrip("/").removeprefix("https://").removeprefix("http://")
    return key.removeprefix("www.")
