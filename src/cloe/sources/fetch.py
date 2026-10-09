"""Cloé's only door to the web (sprint.md → Security → principle 7).

- http(s) only, no credentials in URLs.
- Every host is DNS-resolved and *every* address must be public (no private, loopback,
  link-local, metadata, shared or reserved ranges) before connecting — on the first hop and
  after each of at most 3 redirects. The connection goes to the vetted address, so a second
  DNS answer cannot swap it for an internal one.
- `robots.txt` is honoured per site (cached), 1 s between requests to one host, 15 s
  timeout, 2 MB cap (PDF 20 MB), content types text/html, text/plain, application/pdf,
  application/json. No JavaScript.
- Raw bytes are stored under `data/raw/<sha256>` and never executed or opened as code.

It connects directly (the address check needs that), so it does not use HTTP proxies: the
live scrape runs on the MacBook, not in a cloud session.
"""

from __future__ import annotations

import http.client
import io
import ipaddress
import json
import re
import socket
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup, NavigableString, Tag

from cloe import records

ALLOWED_TYPES = ("text/html", "text/plain", "application/pdf", "application/json")
TYPE_ALIASES = {"application/xhtml+xml": "text/html", "application/x-pdf": "application/pdf"}
OCTET_STREAM = ("application/octet-stream", "binary/octet-stream")  # accepted only if %PDF-
MAX_BYTES = 2_000_000
MAX_PDF_BYTES = 20_000_000
MAX_PDF_PAGES = 60
MAX_REDIRECTS = 3
TIMEOUT_S = 15
DOMAIN_DELAY_S = 1.0
USER_AGENT = "CloeBot/0.1 (TOS13 research library; +https://space13.to)"
ROBOTS_AGENT = "CloeBot"
REDIRECTS = (301, 302, 303, 307, 308)

Resolver = Callable[[str, int], list[str]]


class FetchError(Exception):
    """Nothing usable came back. `status` is the HTTP status when there was one."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class Blocked(FetchError):
    """A guard refused: scheme, address, robots.txt, content type or size."""


@dataclass(frozen=True)
class Fetched:
    url: str
    final_url: str
    content_type: str
    content: bytes
    sha256: str
    raw_path: str | None
    charset: str | None = None

    def text(self) -> str:
        return self.content.decode(self.charset or "utf-8", errors="replace")


def address_allowed(ip: str) -> bool:
    """True only for globally routable unicast addresses."""
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


def system_resolver(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError(f"cannot resolve {host}: {exc.strerror}") from None
    return list(dict.fromkeys(info[4][0] for info in infos))


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, ip: str, timeout: float):
        super().__init__(host, port, timeout=timeout)
        self._ip = ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, ip: str, timeout: float, context: ssl.SSLContext):
        super().__init__(host, port, timeout=timeout, context=context)
        self._ip = ip

    def connect(self) -> None:
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _split(url: str) -> tuple[str, str, int, str]:
    """(scheme, host, port, path?query) or Blocked."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise Blocked(f"only http(s) URLs are fetched, not {scheme or 'no scheme'!r}")
    if parts.username or parts.password:
        raise Blocked("URLs with credentials are not fetched")
    try:
        host = (parts.hostname or "").encode("idna").decode("ascii").lower()
        port = parts.port or (443 if scheme == "https" else 80)
    except (UnicodeError, ValueError):
        raise Blocked("malformed host or port") from None
    if not host:
        raise Blocked("URL has no host")
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    return scheme, host, port, path


def _media_type(header: str | None) -> tuple[str, str | None]:
    if not header:
        return "", None
    main, _, params = header.partition(";")
    m = re.search(r"charset\s*=\s*\"?([A-Za-z0-9._-]+)", params)
    media = main.strip().lower()
    return TYPE_ALIASES.get(media, media), (m.group(1) if m else None)


class Fetcher:
    """Guarded GET with robots.txt, per-host delay and raw storage.

    `resolver` and `exempt_hosts` exist for tests (a local server must be reachable while
    every other host keeps the address check); the CLI never sets them."""

    def __init__(
        self,
        raw_dir: Path | None = None,
        *,
        delay: float = DOMAIN_DELAY_S,
        timeout: float = TIMEOUT_S,
        resolver: Resolver = system_resolver,
        exempt_hosts: frozenset[str] = frozenset(),
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.raw_dir = raw_dir
        self.delay = delay
        self.timeout = timeout
        self.resolver = resolver
        self.exempt_hosts = exempt_hosts
        self.sleep = sleep
        self.clock = clock
        self.context = ssl.create_default_context()
        self._last: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}

    # -- public -----------------------------------------------------------------------

    def fetch(self, url: str) -> Fetched:
        current = url
        for _hop in range(MAX_REDIRECTS + 1):
            _scheme, host, port, _path = _split(current)
            self._vet(host, port)  # a clear refusal before robots.txt is even asked
            if not self.robots_allowed(current):
                raise Blocked(f"robots.txt disallows {current}")
            result = self._get(current)
            if isinstance(result, str):  # a redirect
                current = result
                continue
            return self._store(url, current, *result)
        raise Blocked(f"more than {MAX_REDIRECTS} redirects")

    def robots_allowed(self, url: str) -> bool:
        scheme, host, port, _ = _split(url)
        origin = f"{scheme}://{host}:{port}"
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(f"{scheme}://{host}:{port}/robots.txt")
        return self._robots[origin].can_fetch(ROBOTS_AGENT, url)

    # -- internals --------------------------------------------------------------------

    def _load_robots(self, robots_url: str) -> RobotFileParser:
        parser = RobotFileParser()
        current = robots_url
        try:
            for _hop in range(MAX_REDIRECTS + 1):
                result = self._get(current, robots=True)
                if isinstance(result, str):
                    current = result
                    continue
                _media, content, charset = result
                parser.parse(content.decode(charset or "utf-8", errors="replace").splitlines())
                return parser
            parser.disallow_all = True
        except Blocked:
            parser.disallow_all = True
        except FetchError as exc:
            # RFC 9309: 4xx means "no rules" (allow); anything else means "assume disallow".
            if exc.status is not None and 400 <= exc.status < 500:
                parser.allow_all = True
            else:
                parser.disallow_all = True
        return parser

    def _vet(self, host: str, port: int) -> str:
        addresses = self.resolver(host, port)
        if not addresses:
            raise FetchError(f"{host} has no address")
        if host not in self.exempt_hosts:
            bad = [a for a in addresses if not address_allowed(a)]
            if bad:
                raise Blocked(f"{host} resolves to a non-public address")
        return addresses[0]

    def _wait(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            remaining = self.delay - (self.clock() - last)
            if remaining > 0:
                self.sleep(remaining)
        self._last[host] = self.clock()

    def _get(self, url: str, *, robots: bool = False) -> str | tuple[str, bytes, str | None]:
        """One request. Returns the next URL on a redirect, else (type, bytes, charset)."""
        scheme, host, port, path = _split(url)
        ip = self._vet(host, port)
        self._wait(host)
        if scheme == "https":
            conn: http.client.HTTPConnection = _PinnedHTTPS(host, port, ip, self.timeout,
                                                            self.context)
        else:
            conn = _PinnedHTTP(host, port, ip, self.timeout)
        try:
            conn.request("GET", path, headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/pdf,application/json,text/plain;q=0.9",
                "Accept-Encoding": "identity",
            })
            resp = conn.getresponse()
            if resp.status in REDIRECTS:
                location = resp.getheader("Location")
                if not location:
                    raise FetchError(f"redirect without Location from {host}", resp.status)
                return urljoin(url, location.strip())
            if resp.status != 200:
                raise FetchError(f"HTTP {resp.status} from {host}", resp.status)
            media, charset = _media_type(resp.getheader("Content-Type"))
            cap = MAX_PDF_BYTES if media in ("application/pdf", *OCTET_STREAM) else MAX_BYTES
            if not robots and media not in ALLOWED_TYPES and media not in OCTET_STREAM:
                raise Blocked(f"content type {media or 'missing'!r} is not fetched")
            length = resp.getheader("Content-Length")
            if length and length.isdigit() and int(length) > cap:
                raise Blocked(f"{host} sent {int(length)} bytes; the cap is {cap}")
            content = self._read(resp, cap)
        except (OSError, http.client.HTTPException) as exc:
            raise FetchError(f"{host}: {type(exc).__name__}") from None
        finally:
            conn.close()
        if media in OCTET_STREAM:
            if not content.startswith(b"%PDF-"):
                raise Blocked(f"content type {media!r} is fetched only for PDFs")
            media = "application/pdf"
        return media, content, charset

    def _read(self, resp: http.client.HTTPResponse, cap: int) -> bytes:
        deadline = self.clock() + self.timeout
        chunks: list[bytes] = []
        total = 0
        while chunk := resp.read(65_536):
            total += len(chunk)
            if total > cap:
                raise Blocked(f"body larger than {cap} bytes")
            if self.clock() > deadline:
                raise FetchError("body took longer than the timeout")
            chunks.append(chunk)
        return b"".join(chunks)

    def _store(self, url: str, final_url: str, media: str, content: bytes,
               charset: str | None) -> Fetched:
        digest, raw_path = records.sha256(content), None
        if self.raw_dir is not None:
            digest, raw_path = records.write_raw(self.raw_dir, content)
        return Fetched(url, final_url, media, content, digest, raw_path, charset)


class FixtureFetcher:
    """Serves saved pages from a folder instead of the web (work order 001's output).

    The folder holds `index.json`: `{"<url>": {"file": "<name>", "content_type": "…"}}`.
    Same interface as `Fetcher`; unknown URLs are a FetchError, never a live request."""

    def __init__(self, directory: Path, raw_dir: Path | None = None):
        self.directory = Path(directory)
        self.raw_dir = raw_dir
        index = self.directory / "index.json"
        if not index.is_file():
            raise FetchError(f"{index} is missing (see docs/workorders/001-*.md)")
        self.index: dict[str, dict[str, str]] = json.loads(index.read_text(encoding="utf-8"))

    def robots_allowed(self, url: str) -> bool:
        return True

    def fetch(self, url: str) -> Fetched:
        candidates = (url, url.rstrip("/"), url.rstrip("/") + "/")
        entry = next((self.index[u] for u in candidates if u in self.index), None)
        if entry is None:
            raise FetchError(f"not in the fixture index: {url}")
        path = (self.directory / entry["file"]).resolve()
        if self.directory.resolve() not in path.parents:
            raise Blocked("fixture file outside the fixture folder")
        media, charset = _media_type(entry.get("content_type", "text/html"))
        if media not in ALLOWED_TYPES:
            raise Blocked(f"content type {media!r} is not fetched")
        content = path.read_bytes()
        cap = MAX_PDF_BYTES if media == "application/pdf" else MAX_BYTES
        if len(content) > cap:
            raise Blocked(f"fixture larger than {cap} bytes")
        digest, raw_path = records.sha256(content), None
        if self.raw_dir is not None:
            digest, raw_path = records.write_raw(self.raw_dir, content)
        final = entry.get("final_url", url)
        return Fetched(url, final, media, content, digest, raw_path, charset)


# -- text extraction ------------------------------------------------------------------

DROP_TAGS = ("script", "style", "noscript", "nav", "template", "iframe", "svg", "form",
             "button", "select", "canvas", "object", "embed")
BLOCK_TAGS = ("p", "div", "section", "article", "main", "header", "footer", "aside", "ul",
              "ol", "table", "tr", "dl", "dt", "dd", "blockquote", "pre", "figure",
              "figcaption", "address", "hr")


def absolute_link(href: str | None, base_url: str | None) -> str | None:
    """An absolute http(s) URL, or None (mailto:, javascript:, fragments, junk)."""
    if not href:
        return None
    url = urljoin(base_url or "", href.strip())
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return url.split("#", 1)[0]


def _hidden(tag: Tag) -> bool:
    style = (tag.get("style") or "").replace(" ", "").lower()
    return (tag.has_attr("hidden") or tag.get("aria-hidden") == "true"
            or "display:none" in style or "visibility:hidden" in style)


def soup_of(html: str | bytes) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def html_to_text(html: str | bytes, base_url: str | None = None) -> str:
    """Readable text: no nav/scripts/styles/hidden elements; headings as `#`, links as
    `[text](url)` (absolute http(s) only), list items as `- `. Untrusted: wrap it."""
    soup = soup_of(html)
    for tag in soup.find_all(DROP_TAGS):
        tag.decompose()
    for tag in soup.find_all(_hidden):
        tag.decompose()
    for a in soup.find_all("a"):
        label = " ".join(a.get_text(" ").split())
        url = absolute_link(a.get("href"), base_url)
        a.replace_with(NavigableString(f"[{label}]({url})" if url and label else label))
    for br in soup.find_all("br"):
        br.replace_with(NavigableString("\n"))
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            text = " ".join(h.get_text(" ").split())
            h.replace_with(NavigableString(f"\n\n{'#' * level} {text}\n\n" if text else ""))
    for li in soup.find_all("li"):
        li.insert(0, NavigableString("\n- "))
        li.append(NavigableString("\n"))
    for cell in soup.find_all(["td", "th"]):
        cell.append(NavigableString(" | "))
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert(0, NavigableString("\n"))
        tag.append(NavigableString("\n"))
    root = soup.body or soup
    lines = [" ".join(line.split()) for line in root.get_text().splitlines()]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def html_title(html: str | bytes) -> str:
    soup = soup_of(html)
    meta = soup.find("meta", attrs={"property": "og:title"})
    if meta and meta.get("content"):
        return " ".join(str(meta["content"]).split())
    if soup.title and soup.title.string:
        return " ".join(soup.title.string.split())
    h1 = soup.find("h1")
    return " ".join(h1.get_text(" ").split()) if h1 else ""


def pdf_to_text(content: bytes, max_pages: int = MAX_PDF_PAGES) -> tuple[str, int]:
    """Text of the first `max_pages` pages and the total page count (extra `pdf`)."""
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError:
        raise FetchError("reading PDFs needs the 'pdf' extra: uv sync --extra pdf") from None
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted and not reader.decrypt(""):
            raise FetchError("PDF is password-protected")
        pages = len(reader.pages)
        texts = [reader.pages[i].extract_text() or "" for i in range(min(pages, max_pages))]
    except (PyPdfError, ValueError, KeyError, TypeError, OSError) as exc:
        raise FetchError(f"unreadable PDF ({type(exc).__name__})") from None
    text = "\n\n".join(t.strip() for t in texts if t.strip())
    return text, pages


def to_text(fetched: Fetched) -> str:
    """Plain text of a fetched page, PDF, JSON or text file."""
    if fetched.content_type == "application/pdf":
        return pdf_to_text(fetched.content)[0]
    if fetched.content_type == "text/html":
        return html_to_text(fetched.text(), fetched.final_url)
    return fetched.text()
