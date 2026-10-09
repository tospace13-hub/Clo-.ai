"""The fetcher's guards (sprint.md → Security → principle 7), against a local http.server.

The server listens on 127.0.0.1, which the fetcher refuses by design; tests name it
`site.test` and exempt only that name, so every other host keeps the address check."""

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from pdfgen import make_pdf

from cloe.sources import fetch

PAGE = b"""<!doctype html><html><head><title>Knit Lab</title><style>p{}</style></head>
<body><nav><a href="/menu">Menu</a></nav><script>alert(1)</script>
<h1>Knit Lab</h1><p>We test <a href="/report.pdf">the passport report</a> and
<a href="mailto:x@example.org">mail us</a>.</p>
<div style="display: none">hidden <span>nested hidden</span></div>
<ul><li>wool</li><li>cotton</li></ul></body></html>"""


class Server:
    def __init__(self):
        self.routes: dict[str, tuple[int, dict[str, str], bytes]] = {}
        self.hits: list[str] = []
        routes, hits = self.routes, self.hits

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                status, headers, body = routes.get(self.path, (404, {}, b"not found"))
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                if "Content-Length" not in headers and not headers.get("X-No-Length"):
                    self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def url(self, path, host="site.test"):
        return f"http://{host}:{self.port}{path}"


@pytest.fixture(scope="module")
def server():
    s = Server()
    yield s
    s.httpd.shutdown()


@pytest.fixture
def routes(server):
    server.routes.clear()
    server.hits.clear()
    server.routes["/robots.txt"] = (200, {"Content-Type": "text/plain"},
                                    b"User-agent: *\nDisallow: /private\n")
    return server.routes


LOCAL = {"site.test": ["127.0.0.1"], "localhost": ["127.0.0.1"],
         "internal.test": ["10.0.0.5"], "mixed.test": ["93.184.216.34", "192.168.1.1"],
         "metadata.test": ["169.254.169.254"]}


def fetcher(tmp_path=None, **kw):
    return fetch.Fetcher(tmp_path, delay=0, resolver=lambda host, port: LOCAL.get(host, [host]),
                         exempt_hosts=frozenset({"site.test"}), **kw)


def html(body=PAGE):
    return (200, {"Content-Type": "text/html; charset=utf-8"}, body)


def test_fetches_and_stores_raw(server, routes, tmp_path):
    routes["/page"] = html()
    got = fetcher(tmp_path).fetch(server.url("/page"))
    assert (got.content_type, got.charset, got.content) == ("text/html", "utf-8", PAGE)
    assert got.raw_path == str(tmp_path / got.sha256)
    assert oct(os.stat(got.raw_path).st_mode & 0o777) == "0o600"


@pytest.mark.parametrize("address", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "[::1]",
                                     "100.64.0.1", "0.0.0.0"])
def test_private_addresses_rejected(address):
    with pytest.raises(fetch.Blocked):
        fetch.Fetcher(delay=0).fetch(f"http://{address}/")


@pytest.mark.parametrize("host", ["internal.test", "mixed.test", "metadata.test"])
def test_hosts_resolving_to_private_addresses_rejected(host):
    with pytest.raises(fetch.Blocked, match="non-public"):
        fetcher().fetch(f"http://{host}/")


@pytest.mark.parametrize("target", ["http://localhost:{port}/page", "http://127.0.0.1/",
                                    "http://metadata.test/latest/meta-data/",
                                    "file:///etc/passwd"])
def test_redirect_to_private_address_rejected(server, routes, target):
    routes["/page"] = html()
    routes["/go"] = (302, {"Location": target.format(port=server.port)}, b"")
    with pytest.raises(fetch.Blocked):
        fetcher().fetch(server.url("/go"))


def test_redirects_followed_up_to_three(server, routes):
    routes["/page"] = html()
    for i in range(4):
        routes[f"/r{i}"] = (301, {"Location": f"/r{i + 1}" if i < 3 else "/page"}, b"")
    got = fetcher().fetch(server.url("/r1"))
    assert got.final_url == server.url("/page") and got.url == server.url("/r1")
    with pytest.raises(fetch.Blocked, match="redirects"):
        fetcher().fetch(server.url("/r0"))


def test_oversized_body_rejected(server, routes):
    big = b"x" * (fetch.MAX_BYTES + 1)
    routes["/big"] = (200, {"Content-Type": "text/plain"}, big)
    with pytest.raises(fetch.Blocked, match="cap"):  # by Content-Length
        fetcher().fetch(server.url("/big"))
    routes["/sneaky"] = (200, {"Content-Type": "text/plain", "X-No-Length": "1",
                               "Connection": "close"}, big)
    with pytest.raises(fetch.Blocked, match="larger"):  # counted while reading
        fetcher().fetch(server.url("/sneaky"))


def test_robots_disallow_honoured(server, routes):
    routes["/private/report"] = html()
    routes["/page"] = html()
    f = fetcher()
    with pytest.raises(fetch.Blocked, match="robots"):
        f.fetch(server.url("/private/report"))
    f.fetch(server.url("/page"))
    assert server.hits.count("/robots.txt") == 1  # cached per site
    assert "/private/report" not in server.hits


def test_robots_missing_allows_and_server_error_disallows(server, routes):
    routes["/page"] = html()
    del routes["/robots.txt"]  # 404
    fetcher().fetch(server.url("/page"))
    routes["/robots.txt"] = (500, {}, b"")
    with pytest.raises(fetch.Blocked, match="robots"):
        fetcher().fetch(server.url("/page"))


def test_robots_redirect_to_private_address_disallows(server, routes):
    routes["/robots.txt"] = (302, {"Location": "http://internal.test/robots.txt"}, b"")
    routes["/page"] = html()
    with pytest.raises(fetch.Blocked, match="robots"):
        fetcher().fetch(server.url("/page"))


def test_content_types(server, routes):
    routes["/img"] = (200, {"Content-Type": "image/png"}, b"\x89PNG")
    routes["/js"] = (200, {"Content-Type": "application/javascript"}, b"alert(1)")
    routes["/bin"] = (200, {"Content-Type": "application/octet-stream"}, b"MZ\x90\x00")
    routes["/pdf"] = (200, {"Content-Type": "application/octet-stream"}, make_pdf(["hello"]))
    for path in ("/img", "/js", "/bin"):
        with pytest.raises(fetch.Blocked):
            fetcher().fetch(server.url(path))
    assert fetcher().fetch(server.url("/pdf")).content_type == "application/pdf"


@pytest.mark.parametrize("url", ["ftp://site.test/x", "http://user:pw@site.test/x",
                                 "javascript:alert(1)", "http:///nohost"])
def test_bad_urls_rejected(url):
    with pytest.raises(fetch.Blocked):
        fetcher().fetch(url)


def test_http_errors(server, routes):
    routes["/gone"] = (410, {}, b"")
    with pytest.raises(fetch.FetchError) as exc:
        fetcher().fetch(server.url("/gone"))
    assert exc.value.status == 410 and not isinstance(exc.value, fetch.Blocked)


def test_one_second_between_requests_to_a_host(server, routes):
    routes["/page"] = html()
    now, slept = [100.0], []
    f = fetch.Fetcher(resolver=lambda h, p: LOCAL.get(h, [h]), exempt_hosts=frozenset({"site.test"}),
                      sleep=lambda s: (slept.append(s), now.__setitem__(0, now[0] + s)),
                      clock=lambda: now[0])
    f.fetch(server.url("/page"))  # robots.txt, then the page: one wait
    f.fetch(server.url("/page"))
    assert slept == [pytest.approx(1.0), pytest.approx(1.0)]


def test_html_to_text():
    text = fetch.html_to_text(PAGE, "https://knit.example/about/")
    assert "# Knit Lab" in text
    assert "[the passport report](https://knit.example/report.pdf)" in text
    assert "mail us" in text and "mailto" not in text and "x@example.org" not in text
    for gone in ("Menu", "alert", "p{}", "hidden"):
        assert gone not in text
    assert "- wool" in text and "- cotton" in text
    assert fetch.html_title(PAGE) == "Knit Lab"


def test_pdf_to_text_caps_pages():
    pdf = make_pdf([f"page {i} about knitwear" for i in range(1, 6)])
    text, pages = fetch.pdf_to_text(pdf, max_pages=3)
    assert pages == 5 and "page 3" in text and "page 4" not in text
    with pytest.raises(fetch.FetchError, match="unreadable"):
        fetch.pdf_to_text(b"%PDF-1.4 garbage")


def test_fixture_fetcher(tmp_path):
    (tmp_path / "a.html").write_bytes(PAGE)
    (tmp_path / "index.json").write_text(
        '{"https://knit.example/": {"file": "a.html", "content_type": "text/html"},'
        ' "https://evil.example/": {"file": "../secret", "content_type": "text/html"},'
        ' "https://img.example/": {"file": "a.html", "content_type": "image/png"}}')
    f = fetch.FixtureFetcher(tmp_path, raw_dir=tmp_path / "raw")
    got = f.fetch("https://knit.example")
    assert got.content == PAGE and (tmp_path / "raw" / got.sha256).exists()
    assert "# Knit Lab" in fetch.to_text(got)
    with pytest.raises(fetch.FetchError, match="not in the fixture"):
        f.fetch("https://other.example/")
    for url in ("https://evil.example/", "https://img.example/"):
        with pytest.raises(fetch.Blocked):
            f.fetch(url)
