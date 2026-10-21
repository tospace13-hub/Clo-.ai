"""The source catalogue (sources/registers.py): which sources apply to a company, and the
parsers on the hand-written register responses in tests/fixtures/site/."""

import json
from pathlib import Path

import pytest

from cloe.sources import registers as R

SITE = Path(__file__).parent / "fixtures" / "site"
SUBJECT = R.Subject("Voorbeeld Weverij B.V.", kvk="12345678", domain="example.nl",
                    city="Tilburg")
KEYS = {"kvk": "test-kvk-key", "overheidio": "test-ovio-key"}
FIXTURE_FILES = {
    "kvk_zoeken": "kvk_zoeken.json", "kvk_basisprofiel": "kvk_basisprofiel.json",
    "openkvk": "openkvk.json", "opencorporates": "opencorporates.json",
    "wikidata": "wikidata.json", "wikipedia_nl": "wikipedia.json",
    "bekendmakingen": "bekendmakingen.xml", "google_news": "google_news.xml",
    "google_news_en": "google_news_en.xml", "bing_news": "bing_news.xml",
    "gdelt": "gdelt.json", "wayback": "wayback.json", "openalex": "openalex.json",
    "crossref": "crossref.json", "zenodo": "zenodo.json",
}


def parsed(key: str) -> R.Parsed:
    return R.parse(R.BY_KEY[key], (SITE / FIXTURE_FILES[key]).read_bytes())


def test_catalogue_is_consistent():
    keys = [r.key for r in R.CATALOGUE]
    assert len(keys) == len(set(keys)) and len(keys) >= 45
    for reg in R.CATALOGUE:
        assert reg.group in R.GROUPS and reg.access in R.ACCESS
        assert reg.keyed in ("kvk", "name", "domain", "local")
        assert reg.kind in R.MENTION_KINDS
        assert reg.parser is None or reg.parser in R.PARSERS
        if reg.keyed == "local":
            assert reg.access == "loaded" and not reg.url
        else:
            assert reg.url.startswith("https://")
        if reg.access == "key":
            assert reg.api_key in R.KEY_ENV
        if reg.keyed == "kvk" and reg.access != "person":  # a person types it on the page
            assert "{kvk}" in reg.url
        if reg.keyed == "domain":
            assert "{domain}" in reg.url
    # every group is used, and the KvK number is the first way in
    assert {r.group for r in R.CATALOGUE} == set(R.GROUPS)
    assert R.CATALOGUE[0].key == "site_colofon" and R.CATALOGUE[1].keyed == "name"
    assert sum(r.keyed == "kvk" for r in R.CATALOGUE) >= 5


def test_search_name_drops_the_legal_form():
    assert R.search_name("Voorbeeld Weverij B.V.") == "Voorbeeld Weverij"
    assert R.search_name("Garenfabriek Twente N.V.") == "Garenfabriek Twente"
    assert R.search_name("Indigo Denim Works Holding B.V.") == "Indigo Denim Works"
    assert R.search_name("Atelier Bram") == "Atelier Bram"
    assert R.search_name("Stichting Kringloop Textiel") == "Stichting Kringloop Textiel"
    assert R.search_name("") == ""


def test_queries_need_the_kvk_number_and_the_api_keys():
    qs, skipped = R.queries(R.Subject("Voorbeeld Weverij B.V.", domain="example.nl"))
    assert {q.register.key for q in qs} >= {"google_news", "gdelt", "openalex", "wayback"}
    assert not any(q.register.keyed == "kvk" for q in qs)
    assert "wikidata: needs the kvk" in skipped and "kvk_zoeken: no CLOE_KVK_API_KEY" in skipped

    qs, skipped = R.queries(SUBJECT, KEYS)
    by_key = {q.register.key: q for q in qs}
    assert {"kvk_zoeken", "kvk_basisprofiel", "openkvk", "wikidata", "opencorporates"} <= set(by_key)
    assert by_key["kvk_basisprofiel"].headers == {"apikey": "test-kvk-key"}
    assert by_key["openkvk"].headers == {"ovio-api-key": "test-ovio-key"}
    assert by_key["google_news"].headers == {}
    assert skipped == []
    assert all(q.register.parser for q in qs)
    # nothing without a name
    assert R.queries(R.Subject(" B.V. ", kvk="12345678"))[0] == [
        q for q in R.queries(R.Subject(" B.V. ", kvk="12345678"))[0] if q.register.keyed == "kvk"]


def test_urls_are_encoded():
    url = R.url_for(R.BY_KEY["google_news"], R.Subject('Atelier "Bram" & Co'))
    assert "%22Atelier%20%5C%22Bram%5C%22%20%26%20Co%22" in url or "%22Atelier" in url
    assert " " not in url and '"' not in url
    sparql = R.url_for(R.BY_KEY["wikidata"], SUBJECT)
    assert "{" not in sparql and "}" not in sparql and "%2212345678%22" in sparql
    assert R.url_for(R.BY_KEY["mdpp_projects"], SUBJECT) is None


def test_fixture_index_covers_every_parsed_register():
    index = json.loads((SITE / "index.json").read_text())
    qs, _ = R.queries(SUBJECT, KEYS)
    missing = [q.register.key for q in qs if q.url not in index]
    assert missing == []
    assert set(FIXTURE_FILES) == {q.register.key for q in qs}


@pytest.mark.parametrize("key", sorted(FIXTURE_FILES))
def test_every_fixture_parses_without_error(key):
    p = parsed(key)
    assert p.error is None
    for m in p.mentions:
        assert m.url.startswith("https://") and m.kind in R.MENTION_KINDS
        assert m.register == key and len(m.title) <= 300


def test_rss_reads_items_and_drops_non_http_links():
    ms = parsed("google_news").mentions
    assert [m.date for m in ms] == ["2026-09-12", "2025-11-03"]
    assert ms[0].outlet == "Textilia" and ms[0].kind == "news"
    assert ms[0].url == "https://www.textilia.nl/nieuws/voorbeeld-weverij-productpaspoort"
    assert "<" not in ms[0].one_line and "productpaspoort" in ms[0].one_line
    assert not any("passwd" in m.url for m in ms)
    assert parsed("google_news_en").mentions == []
    assert parsed("bing_news").mentions[0].outlet == "Tubantia"  # from <News:Source>


def test_gdelt_and_wayback():
    ms = parsed("gdelt").mentions
    assert ms[1].url.startswith("https://www.innovationintextiles.com/")
    assert ms[1].date == "2026-09-15" and ms[1].outlet == "innovationintextiles.com"
    assert ms[1].one_line == "English United Kingdom"
    ws = parsed("wayback").mentions
    assert [m.date for m in ws] == ["2001-04-12", "2010-08-15", "2025-03-01"]
    assert ws[0].url == "https://web.archive.org/web/20010412093015/http://example.nl:80/"
    assert ws[0].kind == "archive"


def test_sru_reads_the_official_publications():
    ms = parsed("bekendmakingen").mentions
    assert ms[0].url == "https://zoek.officielebekendmakingen.nl/stcrt-2024-18723.html"
    assert ms[0].outlet == "Staatscourant" and ms[0].date == "2024-06-14"
    assert ms[0].one_line.startswith("Staatscourant: Mededeling ex art. 2:314 BW")
    assert ms[1].url == "https://zoek.officielebekendmakingen.nl/gmb-2025-301122.html"
    assert ms[1].outlet == "Gemeenteblad" and "omgevingsvergunning" in ms[1].title


def test_identity_from_the_kvk_registers():
    cands = parsed("kvk_zoeken").identity["kvk_candidates"]
    assert [c["kvk"] for c in cands] == ["12345678", "87654321"]
    assert cands[0] == {"kvk": "12345678", "name": "Voorbeeld Weverij B.V.", "city": "Tilburg",
                        "type": "hoofdvestiging"}
    basis = parsed("kvk_basisprofiel").identity
    assert basis["kvk"] == "12345678" and basis["founded"] == 1998
    assert basis["trade_names"] == ["Voorbeeld Jacquard"] and basis["employees"] == "32"
    assert basis["sbi"][0] == {"code": "1320", "text": "Weven van textiel", "main": True}
    assert basis["city"] == "Tilburg"
    openkvk = parsed("openkvk").identity
    assert openkvk["legal_form"] == "Besloten Vennootschap" and openkvk["status"] == "active"
    assert openkvk["sbi"] == [{"code": "1320", "text": "Weven van textiel", "main": False}]
    oc = parsed("opencorporates")
    assert oc.identity["previous_names"] == ["Weverij Van Dijk B.V."]
    assert oc.identity["sbi"] == [{"code": "13.20", "text": "Weaving of textiles"}]
    assert oc.mentions[0].url == "https://opencorporates.com/companies/nl/12345678"
    assert "Active · Besloten Vennootschap · Weverstraat 12" in oc.mentions[0].one_line
    wd = parsed("wikidata")
    assert wd.identity == {"wikidata": "http://www.wikidata.org/entity/Q99999999",
                           "name": "Voorbeeld Weverij", "founded": 1998,
                           "website": "https://example.nl/"}
    assert wd.mentions[0].url == "https://nl.wikipedia.org/wiki/Voorbeeld_Weverij"
    wp = parsed("wikipedia_nl").mentions
    assert wp[1].url == "https://nl.wikipedia.org/wiki/Textielindustrie_in_Tilburg"
    assert "<span" not in wp[0].one_line and "jacquardweverij" in wp[0].one_line


def test_academic_registers():
    oa, cr, zn = parsed("openalex").mentions, parsed("crossref").mentions, parsed("zenodo").mentions
    assert oa[0].url == cr[0].url == "https://doi.org/10.1000/voorbeeld.2025.01"
    assert oa[0].date == cr[0].date == "2025-10-02"
    assert oa[0].outlet == cr[0].outlet == "Journal of Circular Textiles"
    assert zn[0].url == "https://zenodo.org/records/9990007" and zn[0].one_line == "Report"


@pytest.mark.parametrize("value, expected", [
    ("Thu, 16 Oct 2025 10:00:00 GMT", "2025-10-16"), ("20251016T120000Z", "2025-10-16"),
    ("2025-10-16T10:00:00+02:00", "2025-10-16"), ("16-10-2025", "2025-10-16"),
    ("2025-10", "2025-10"), ("2025", "2025"), (20251016, "2025-10-16"), ("soon", None),
    ("12 september 2026", "2026-09-12"), ("3 nov. 2025", "2025-11-03"), ("1 mrt 2024", "2024-03-01"),
    ("", None), (None, None),
])
def test_iso_date(value, expected):
    assert R.iso_date(value) == expected


@pytest.mark.parametrize("key, body", [
    ("gdelt", b"<html>Service unavailable</html>"), ("google_news", b'{"not": "xml"}'),
    ("openalex", b"[]"), ("wikidata", b"null"), ("bekendmakingen", b""),
    ("google_news", (b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 '
                     b'"&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]><rss><channel>'
                     b'<item><title>&lol2;</title><link>https://a.example/</link></item>'
                     b'</channel></rss>')),
])
def test_unreadable_responses_are_reported_not_raised(key, body):
    p = R.parse(R.BY_KEY[key], body)
    assert p.mentions == [] and p.identity == {}
    assert p.error is None or p.error.startswith(key)
    if p.error is None:  # an empty list / null is "nothing found", not an error
        assert body in (b"[]", b"null")


def test_parse_without_parser_and_unknown_kinds():
    assert R.parse(R.BY_KEY["textilia"], b"").error == "textilia has no parser"
    weird = R.Register("weird", "Weird", "news", "name", "open", "rss", "x",
                       "https://w.example/?q={q}", parser="rss", kind="weird")
    body = (b'<rss><channel><item><title>t</title><link>https://w.example/a</link></item>'
            b'</channel></rss>')
    assert [m.kind for m in R.parse(weird, body).mentions] == ["other"]


def test_describe_lists_every_source_with_its_url():
    text = "\n".join(R.describe(SUBJECT))
    for reg in R.CATALOGUE:
        assert reg.name in text
    assert "<https://api.kvk.nl/api/v1/basisprofielen/12345678>" in text
    assert "already in the database" in text and "CLOE_KVK_API_KEY" in text
    no_kvk = "\n".join(R.describe(R.Subject("Atelier Bram")))
    assert "needs the kvk first" in no_kvk and "needs the domain first" in no_kvk
