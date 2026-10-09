# Cloé

Cloé is the network orchestrator for the TOS13 network period (WP1 Encode). She gets to
know the companies in the network, finds them data they can use, and brings it to them by
email and SMS — signed "Cloé (AI)", after Chloe approves. Cloé is the AI, named after and
modelled on Chloe, who brought the WoTO companies together.

```
uv sync --all-extras
cp .env.example .env                  # fill in what you have; CLOE_SEND stays 0 until launch
git config core.hooksPath .githooks   # pre-commit: STATE.md staged, ruff, pytest
uv run cloe init                      # create / migrate data/cloe.db
uv run cloe doctor                    # OK / WARN / FAIL per check
uv run cloe version

uv run cloe ingest joinform           # the "TOS13 join form responses" Google Sheet
uv run cloe ingest joinform export.csv  # …or a CSV/XLSX export of it
uv run cloe ingest tell companies.xlsx  # TELL dashboard export (or --db, read-only)
uv run cloe companies list --needs
uv run cloe profile example.nl        # prints, and saves data/profiles/example.nl.md
uv run cloe consent set someone@example.org email followup yes --evidence "how and when"
uv run cloe export someone@example.org   # everything held about one person (JSON)
uv run cloe forget someone@example.org   # erase them; future imports skip them

uv run cloe scrape funding --max-projects 3    # m-dpp.nl EU projects → CORDIS → documents (MacBook)
uv run cloe scrape funding --engine workorder  # …or write a work order for Claude Code instead
uv run cloe workorder ingest 002               # read that work order's result
uv run cloe scrape url https://…               # one page or PDF into the library
uv run cloe library search "digital product passport knitwear" --tier yarn
uv run cloe library show 2 · uv run cloe library stats
```

The research library fetches only through a guarded fetcher (public addresses only, robots.txt,
1 s per site, size and type caps). Live scrapes run on the MacBook: cloud sessions can't
reach m-dpp.nl or CORDIS. `--fixture tests/fixtures/funding` runs on saved pages instead,
and `CLOE_FAKE=1` makes cards with a keyword stand-in rather than the model (dry runs only).

Reading the Google Sheet needs a Google Cloud service account: share the sheet with its
address as **Viewer**, put the JSON key outside the repo (or under `secrets/`, ignored),
and set `CLOE_JOINFORM_SHEET_ID` and `GOOGLE_SERVICE_ACCOUNT_FILE` in `.env`
(`uv sync --extra sheets`).

Plan: `sprint.md` (one sprint per Claude Code session) · Status: `docs/STATE.md` ·
Voice: `tone.md` · Researched facts: `docs/CONTEXT.md` · Session rules: `CLAUDE.md`.
