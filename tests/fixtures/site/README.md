# Company research fixtures

`cloe research example.nl --fixture tests/fixtures/site` runs on this folder with no web
access: `index.json` serves every URL the run would fetch, the company's own pages as
well as the register queries from `sources/registers.py`.

**Everything here is hand-written and fictional.** No host in the source catalogue is
reachable from a cloud session (docs/CONTEXT.md §G), so each register response was written
from the format's public documentation, not copied from a live response. When the MacBook
runs `cloe research` live, save the real responses here (same file names) and tell the
next session which parsers needed a fix.

- `home.html`, `over-ons.html`, `producten.html`, `nieuws.html`, `team.html`: the site of
  *Voorbeeld Weverij B.V.* (Tilburg, KvK 12345678). The homepage links to the metadata
  address `169.254.169.254` and to LinkedIn (neither is followed); `over-ons.html` carries an
  instruction-like HTML comment and a visible instruction-like paragraph.
- `article_*.html`: three press articles the news registers point to.
- `kvk_zoeken.json`, `kvk_basisprofiel.json`: KVK API v2 Zoeken and v1 Basisprofiel shapes.
- `openkvk.json`: overheid.io OpenKVK (field names as documented; endpoint version unverified).
- `opencorporates.json`: OpenCorporates API v0.4 company record.
- `wikidata.json`: SPARQL JSON results for P3220 = KvK number.
- `wikipedia.json`: MediaWiki `list=search` result.
- `bekendmakingen.xml`: SRU 2.0 response from zoek.officielebekendmakingen.nl with two
  `gzd` records (a Staatscourant merger notice, a Gemeenteblad permit).
- `google_news.xml`, `google_news_en.xml`, `bing_news.xml`: RSS 2.0 feeds. Live Google
  News links are redirects through news.google.com; here they point at the articles.
  One item carries a `file:` link that must be dropped.
- `gdelt.json`: GDELT DOC 2.0 `artlist` JSON.
- `wayback.json`: Wayback CDX JSON (first row is the header).
- `openalex.json`, `crossref.json`, `zenodo.json`: works APIs; OpenAlex and Crossref name
  the same DOI, so the run must keep one mention.
