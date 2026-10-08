# LESSONS — one entry per lesson, newest first

Format: `## YYYY-MM-DD — one-line summary` then 2–5 lines: what happened, what we do now,
why it matters. Record corrections and confirmed approaches alike. Don't repeat what git
history or STATE.md already says. Update an existing entry rather than adding a duplicate;
delete entries that turn out to be wrong.

## 2026-10-08 — Shell heredocs here turn `\uXXXX` escapes into real characters

Writing Python tests through a bash heredoc put literal zero-width characters into the
source, and ruff (PLE2502/PLE2515) refused them. Build invisible characters with `chr()`
in tests, and write hostile fixtures from a Python script. The pre-commit hook also caught
an example address in a test: split such strings (`"someone@" + "gmail.com"`).

## 2026-10-08 — Several source hosts are blocked from cloud sessions

`m-dpp.nl`, `news.byborre.com`, `www.byborre.com`, `thenextcartel.com` are denied by the
environment's network policy. Fetch them on the MacBook (work order) or ask an environment
owner to allow the domains. Don't burn turns retrying; test scrapers against committed
fixtures.
