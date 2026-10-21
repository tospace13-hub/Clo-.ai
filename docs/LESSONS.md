# LESSONS — one entry per lesson, newest first

Format: `## YYYY-MM-DD — one-line summary` then 2–5 lines: what happened, what we do now,
why it matters. Record corrections and confirmed approaches alike. Don't repeat what git
history or STATE.md already says. Update an existing entry rather than adding a duplicate;
delete entries that turn out to be wrong.

## 2026-10-16 — Write the source list as data before writing any scraper

Asked to "dig the internet for every article" about a company, the useful first step was a
catalogue, not a crawler: one `Register` per source with what keys it (KvK number, name,
domain), how it is reached (open, API key, a person, already loaded), its format, and what
it gives. The KvK number turned out to be the key to the official half of the list, and
TELL's export doesn't carry it, so "find the KvK number" became step one of the pipeline.
The catalogue also renders straight into the work order and `--list-sources`, so the team
can review the sources without reading code.

## 2026-10-16 — A test double sees only what the model sees

`FakeClaude` callables get the request content, never the system prompt, so a stand-in
reader cannot map source ids to URLs from the task text. Readers now cite the block id
("S3") or the URL, and `validate_findings` resolves ids in code. That also makes the real
reader robust when a model cites an id instead of the URL.

## 2026-10-13 — Before building on stand-ins, ask who made the source

The m-dpp.nl funding page was blocked, so Sprint 2 built a label-based HTML parser on
hand-written pages. The page turned out to be the team's own site, with a public repo
(`MDPP-ops/MDPP_Website`). It is a D3 network over JSON datasets, so no HTML parser could
ever have worked. When a source is blocked, first ask whether the team owns it or has its
data or repo. A site's IP can hint (185.199.108–111.x = GitHub Pages). Hand-written
fixtures are the last resort, not the first.

## 2026-10-13 — Run text heuristics over real data before trusting them

`injection_flags` had "act as" as a fake-system-prompt signal. On 2,530 real project
abstracts it flagged 16, all ordinary prose ("will act as a hub"), and flagged items drop
out of search. Run each heuristic over a real corpus, and add the false positives found
as regression tests.

## 2026-10-08 — Date consent by when the person acted; re-imports act only on changes

A re-import that dates consent "now" (e.g. an unparseable `submitted_at`) can silently undo
a later "no" Chloe recorded. Rule: a new row is dated by its own timestamp; a row seen
before only acts on cells that changed since the last import (dated when observed);
one-off events (unsubscribes) are applied once. The latest ledger row by `at` wins.

## 2026-10-08 — Don't grep other repos' working copies for facts CONTEXT already has

Searching the local TELL clone (it has a `db/mysql/.env`) was refused by the session's
permission classifier as credential exploration. CONTEXT §D already lists TELL's tables
and export columns; where something is missing (TELL's `query_org`), write it down as an
open question for the TELL team instead of digging.

## 2026-10-08 — Shell heredocs here turn `\uXXXX` escapes into real characters

Writing Python tests through a bash heredoc put literal zero-width characters into the
source, and ruff (PLE2502/PLE2515) refused them. Build invisible characters with `chr()`
in tests, and write hostile fixtures from a Python script. The pre-commit hook also caught
an example address in a test: split such strings (`"someone@" + "gmail.com"`).

## 2026-10-08 — Several source hosts are blocked from cloud sessions

`m-dpp.nl`, `news.byborre.com`, `www.byborre.com`, `thenextcartel.com` are denied by the
environment's network policy (and, since 2026-10-09, `cordis.europa.eu`, `ec.europa.eu`,
`zenodo.org`, `data.europa.eu`). Also, Cloé's fetcher connects directly (needed for its
address check), so it can't use the cloud proxy even for allowed hosts. Fetch them on the MacBook (work order) or ask an environment
owner to allow the domains. Don't burn turns retrying; test scrapers against committed
fixtures.
