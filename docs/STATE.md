# STATE — read this first every session, update it every round

A **round** is one Claude Code session on one sprint. Every round: (1) add a "Round log"
line when you start, (2) update "In progress" after every finished step, (3) move the
round-log line to `finished` or `stopped` when you stop. The pre-commit hook (Sprint 0)
refuses any commit that doesn't touch this file. When the team praises the work, add it
to "Laurels" with the habits that earned it.

**Next sprint:** 2 (Research library: EU projects → research material). Branch: `main`.

## Round log (newest first)

- 2026-10-08 · sprint 1 · finished — join form (Google Sheet or export) + TELL + profiles,
  consent / forget / export / companies list; 151 tests green (3 skipped: Sprints 4/5).
- 2026-10-08 · sprint 0 · finished — Foundation: config, db, untrusted, llm + FakeClaude,
  persona, cli, pre-commit hook, 79 tests green (4 skipped placeholders for Sprints 1/4/5).
- 2026-10-08 · laurels · finished — added the "Laurels" section below.
- 2026-10-08 · hosts · finished — `space13.to` added to the hosts to unblock (CONTEXT §G).
- 2026-10-08 · rename · finished — the AI is **Cloé** (was "Clo"), the person is **Chloe**;
  package/CLI `cloe`, env `CLOE_*`; tone.md 1.1 puts "(AI)" beside every sign-off.
- 2026-10-08 · planning · finished — sprint.md, CLAUDE.md, tone.md, CONTEXT.md written;
  deps added; first commit + push.

## Laurels (what the team says is working — keep doing it)

When the team praises the work, record it here: date, what they said, and the specific
habits that earned it, so later rounds repeat them. Newest first.

- **2026-10-08 · "Give yourself a Laurel, you're doing a great job"** (TOS13 team, after
  the planning and rename rounds). What earned it:
  - **Researched before building.** Read the TELL code, the space13.to source (AI and
    privacy statements, join form) and the Slack posting protocol, then grounded the plan
    in TOS13's own published commitments instead of inventing rules.
  - **Planned for compaction.** CONTEXT pack so nothing is re-researched, one sprint
    section per session, STATE.md checkpoint after every step, Definition of Done as
    runnable commands.
  - **Security as code, not prompts.** Readers of untrusted text have no tools, writers see
    only extracted facts, sending is gated Python with a named approver; LinkedIn is a
    person-in-the-loop work order, never a scraper.
  - **Careful with names and people.** The rename kept the AI (Cloé) and the person (Chloe)
    impossible to confuse ("(AI)" in every sign-off) and flagged what isn't confirmed.
  - **Followed the team's Slack protocol to the letter** (#ai-log line for every shared
    change, short topic-channel update with Link and Next, replies in the existing thread).
  - **Reported honestly.** Said plainly what was blocked (hosts) and what still needs a
    human (calibration, approvers), rather than papering over it.

## In progress

(none — Sprint 1 finished; Sprint 2 not started)

## Done

- 2026-10-08 (sprint 1): Definition of Done (run with `CLOE_DB` in a scratch folder so the
  fixtures stay out of `data/cloe.db`) — `uv run pytest -q` → `151 passed, 3 skipped`;
  ruff → `All checks passed!`; `cloe ingest joinform tests/fixtures/joinform.csv` → 5 rows,
  4 companies, 5 people, 25 consent rows, 22 facts, 4 needs (1 flagged; 3 unclassified: no
  API key); `cloe ingest tell tests/fixtures/tell.xlsx` → 6 new, 4 matched, 7 contacts
  without consent, 33 facts (1 flagged keyword); `cloe profile example.nl` → the injection
  text appears only under "Flagged text" (indented code block); `cloe forget
  injected@example.nl` → person 1, consents 5, sources 1, facts 2, needs 1, profiles 1;
  `cloe export injected@example.nl` → `FAIL not found`, exit 1. Modules: `records.py`,
  `people.py`, `sources/sheets.py`, `sources/joinform.py`, `sources/tell.py`, `profile.py`,
  `cmd_network.py`. Tests: `test_records`, `test_joinform` (incl. the Sheets path with a
  fake session), `test_tell`, `test_profile` (golden `tests/fixtures/profile_example.nl.md`;
  regenerate with `CLOE_UPDATE_GOLDEN=1`), `test_cmd_network` (the DoD flow end to end);
  the Sprint 1 injection placeholder is now a real test.
  **Real data:** no real join-form rows or TELL export were used — fixtures only. At the
  team's request the join form is read straight from the "TOS13 join form responses" Google
  Sheet; its header row (only the header) was checked on 2026-10-08: tab `Responses` is
  identical to CONTEXT §C (24 columns, same order); a second tab `Unsubscribe` has
  `submitted_at, email, responses_updated` (now in CONTEXT §C). No column differences.
- 2026-10-08 (sprint 0): Definition of Done —
  `uv run pytest -q` → `79 passed, 4 skipped`; `uv run ruff check src tests` → `All checks
  passed!`; `uv run cloe doctor` → 11 OK, 3 WARN (no API key, no real approver,
  `CLOE_SEND=0: dry run`), exit 0. Modules: `config.py`, `db.py`, `untrusted.py`,
  `llm.py`, `persona.py`, `cli.py`. Tests: `test_config`, `test_db`, `test_untrusted`,
  `test_llm_fake` (FakeClaude + the real class against a stub client — request shape, no
  network), `test_persona`, `test_cli`, `test_hygiene`, `test_injection` (6 hostile
  fixtures in `tests/fixtures/injection/`). `.githooks/pre-commit` active.
- 2026-10-08 (planning): `uv init --lib`; deps `anthropic`, `pydantic`, `beautifulsoup4`;
  extras `tell` (pymysql, openpyxl), `pdf` (pypdf); dev `pytest`, `ruff`. `.gitignore`,
  `.env.example`, `pyproject` script entry `cloe = cloe.cli:main`. Wrote `sprint.md`,
  `CLAUDE.md`, `tone.md` (v1.0, calibration pending), `docs/CONTEXT.md`, `docs/LESSONS.md`.
  Verified SDK 1.12.1 surface: `beta.messages.parse(output_format=…, fallbacks=…)`,
  `tool_runner`, `beta_tool` all present.

## Decisions

- Language: Python 3.12 + uv. Store: SQLite (stdlib) with FTS5 for the library.
- Cloé's runtime model: `claude-opus-5-5` for every call (`CLOE_MODEL`; `CLOE_MODEL_BULK`
  defaults to the same). Sprints are executed by Opus 5.5 sessions; planning was done by
  a Fable 5.1 session.
- Naming: the AI is **Cloé** (product "Cloé.ai"; the GitHub repo shows as `Clo-.ai`
  because GitHub replaces é). The person she is modelled on is **Chloe** (spelling to be
  confirmed — open question 1). Code identifiers are ASCII: package and CLI `cloe`,
  env vars `CLOE_*`, skill `cloe-workorder`.
- Voice: Cloé writes on Chloe's behalf, always signs "Cloé (AI)", and nothing is
  sent without Chloe's approval. `tone.md` is the single source of truth; code loads it
  verbatim.
- Every LLM job has two engines: API (`--engine api`) or a work order executed by a
  Claude Code session on the MacBook (`--engine workorder`). Same schemas, same outputs.
- Security is code, not prompts: readers have no tools, writers see only extracted facts,
  sending is gated Python with a named approver. Full list in `sprint.md` → "Security".
- LinkedIn is never scraped. It is a work order a person performs in their own browser,
  recording business-role facts only.
- **Schema (migration 1, `db.py`; append new migrations, never edit shipped ones):**
  `company(id, name, domain UNIQUE, website, city, postcode, kvk, tier, category, employees
  TEXT, year_start, tell_id, lang, created_at, updated_at)` ·
  `person(id, company_id, name, email UNIQUE NOCASE, phone, role, lang, created_at)` ·
  `consent(id, person_id, channel[email|sms], purpose[followup|newsletter|cloe_updates],
  status[yes|no|unknown], source, evidence, at)` ·
  `source(id, url, kind[joinform|tell|web|pdf|cordis|workorder|inbound|manual], fetched_at,
  sha256, raw_path)` ·
  `fact(id, company_id, kind[does|makes|needs|has_data|project|event|contact|other], text,
  confidence 0..1, source_id, observed_at, expires_at, flags)` ·
  `project(id, acronym, title, programme, cordis_id UNIQUE, url, start_date, end_date,
  partners_nl_json)` ·
  `document(id, source_id, project_id, title, summary, tags_json, lang, published_at,
  body_path)` + FTS5 `document_fts(title, summary, tags, body)` (rowid = document.id;
  `unicode61 remove_diacritics 2`) ·
  `need(id, company_id, text, kind, status, source_id)` ·
  `match(id, company_id, document_id, other_company_id, score, rationale,
  status[proposed|approved|rejected|used], created_at)` ·
  `message(id, person_id, channel[email|sms], direction[out|in], thread_id, subject, body,
  lang, status[draft|blocked|approved|sent|failed|received], tone_version, tone_score,
  approved_by, approved_at, sent_at, provider_id, content_sha256, match_ids_json, flags,
  created_at)` ·
  `work_order(id, kind, status, path, result_path, created_at, ingested_at)` ·
  `event(id, at, actor, action, ref, detail JSON)`.
  Foreign keys on; timestamps are UTC ISO strings from `db.now()`; version in
  `PRAGMA user_version`. Differences from the sprint.md sketch: `start_date/end_date`
  (not start/end), purpose `cloe_updates` (not clo_updates).
- **Interfaces later sprints build on:**
  `config.load(env_path=None, environ=None) -> Settings` (env overrides `.env`;
  `CLOE_SEND` is live only when exactly `1`; canary in `CLOE_CANARY`, generated once).
  `db.connect(path)`, `db.migrate(conn)`, `db.event(conn, actor, action, ref, detail)` —
  detail string values > 200 chars are refused (ids and hashes, not bodies).
  `untrusted.scrub/wrap/injection_flags/contains_canary(text, canary)`, `UNTRUSTED_RULE`.
  The canary is passed explicitly from `Settings.canary` (no module-global `CANARY`).
  `llm.Claude(settings, conn=None)` / `llm.FakeClaude(settings, outputs, conn=None)`:
  `.extract(schema, system, blocks)` — each block must be exactly one `untrusted.wrap()`
  result, else `UnwrappedInput`; `.draft(system, prompt)`; `.research(system, prompt,
  allowed_domains=…|blocked_domains=…)` → `ResearchResult(text, sources, continues)`
  (untrusted). Errors: `Refused`, `Truncated`, `InjectionSuspected` (all `LLMError`).
  `bulk=True` uses `CLOE_MODEL_BULK`. FakeClaude outputs are keyed by schema class name,
  `"draft"`, `"research"`; a list is consumed in order; callables get the request content.
  `persona.system_prompt(task_block, canary)` → [stable cached block, task block];
  `persona.tone_version(text)`.
  CLI: add a module name to `cli.COMMAND_MODULES`; it defines `register(subparsers)` and
  sets `func=handler`, `handler(args, settings) -> int`.
- **Migration 2 (Sprint 1):** `company.company_class` (TELL), `company.identity_key`
  (indexed, `records.identity_key(name, city)`), table `forgotten(email_sha256 PK, at)` —
  the suppression list that keeps `cloe forget` from being undone by an import.
- **Identity resolution (`records.py`):** company by normalised domain = the website's host
  (lowercase; no scheme, `www.`, port, path or query; unicode → punycode; shared hosts like
  facebook.com, linktr.ee, gmail.com are not a domain), else by `identity_key` = name +
  city with accents, punctuation and legal-form words (B.V., N.V., v.o.f., …) removed. A
  name+city match is taken only when the two records don't carry *different* domains.
  People by lowercased email; invalid emails skipped; forgotten emails never imported.
  Join form overwrites company/person fields on a new row (the company told us; the newest
  row wins) and only fills blanks on a seen row; TELL only fills blanks and never changes a
  known person. TELL rows without an id get `tell_id = "export:<identity_key>"`.
- **Consent ledger:** rows dated by when the person acted; latest `at` wins (ties: newest
  row). New join-form row: `followup` from `consent_privacy`, `newsletter` from
  `consent_newsletter` (empty = no), `sms/*` = unknown, all dated `submitted_at`. A row
  seen before only acts on consent cells that changed since its last import (dated now).
  `Unsubscribe` tab: "no" for **every** email purpose, applied once per row (kept as a
  join-form source). TELL contacts get no consent rows (= unknown). `cloe consent set`
  writes `source=manual` with required evidence.
- **Facts and needs:** text scrubbed and single-lined (facts ≤ 500 chars, needs ≤ 1000),
  de-duplicated per company + kind + text. Flags (comma list): `instruction_like` (code
  heuristics or the model), `scraped` (TELL keywords: wrap before any model reads them).
  Confidence: join form 0.9, TELL 0.6, TELL keywords 0.4, quarantined cells 0.1.
  Instruction-like name/header cells (name, trade name, city, …) are blanked and kept as a
  flagged fact of kind `other`. `need.status` is `open` or `flagged`; `need.kind` stays
  NULL until classified, from the closed enum `materials production recycling data
  regulation research funding partners market knowledge technology other`
  (`joinform.NeedClassification`, via `Claude.extract`, `bulk=True`). Code-flagged needs
  are never sent to a model. Writers (Sprint 4) must skip flagged facts/needs.
- **Files:** raw join-form rows at `data/raw/<sha256>` (0600; TELL exports are not
  copied — they hold the whole network's contacts, the source row keeps the sha256);
  profiles at `data/profiles/<domain>.md` or `company-<id>.md` (0600). `forget` deletes
  the person, consents, their join-form sources + raw copies + the facts/needs taken from
  them, their messages, companies left with nothing (and no `tell_id`), and cached
  profiles; events keep only `person:<id>` refs.
- **Sprint 1 interfaces:** `records.upsert_company(conn, values, overwrite=False) ->
  (id, created)`, `records.lookup_company(conn, query)`, `records.upsert_source(conn,
  kind, url, raw=…, raw_dir=… | digest=…)`, `records.add_fact(…, flags=…)`,
  `records.add_need(…)`, `records.quarantine(values, keys, label)`;
  `people.upsert_person`, `people.set_consent(…, at=…)`, `people.current_consent`,
  `people.consents`, `people.forget`, `people.export`; `joinform.ingest(conn, tabs,
  raw_dir, claude, canary) -> Report` (tabs from `read_file` or `read_sheet`);
  `tell.ingest(conn, recs, origin, digest)`; `profile.render(conn, company_id)`,
  `profile.write(conn, company_id, dir)`. Settings `CLOE_JOINFORM_SHEET_ID`,
  `GOOGLE_SERVICE_ACCOUNT_FILE`; extra `sheets` (google-auth). Sheets are read with
  `FORMATTED_VALUE` only (never formulas).

## Open questions for Chloe / the team

1. Chloe's name as she writes it (Chloe / Chloé / Cloé), surname, role, OK to have the AI
   carry her name, and 5–10 real messages she has sent (for `tone.md` §9).
2. Who approves messages when Chloe is away? (second approver in `CLOE_APPROVERS`)
3. Read-only TELL DB credentials, or rely on the public xlsx export? (default: export)
4. Phone number + SMS-consent field on the join form? Until then SMS is limited to people
   who gave a number and consent elsewhere.
5. SMS provider (Twilio vs MessageBird) and the sending mailbox for email
   (hello@space13.to via Google Workspace SMTP?).
6. Who owns the AI-statement and privacy-statement updates on space13.to? (Sprint 7 drafts
   them.)
7. Unblock `m-dpp.nl`, `news.byborre.com`, `byborre.com`, `space13.to` in the cloud environment's
   network settings, or run work order 001 on the MacBook before Sprint 2.
8. Join-form sheet access: who creates the Google Cloud service account, shares "TOS13 join
   form responses" with it as Viewer, and keeps the key on the MacBook? The sheet is owned
   by a personal Google account; consider moving it to the TOS13 Workspace. The sheet id
   stays in `.env` (`CLOE_JOINFORM_SHEET_ID`), not in the repo.
9. Cloé treats an unsubscribe as "no" for *every* email purpose (follow-up, newsletter,
   Cloé updates), not only the newsletter. Chloe to confirm.
10. `cloe ingest tell --db`: the SQL (`tell.DB_QUERY`) was written from the table list in
    CONTEXT §D; TELL's own `query_org` could not be read this session. TELL team to check
    the joins before first use; the xlsx export remains the default.
11. Someone who was forgotten and later submits the join form again is still skipped (there
    is no "un-forget"). Decide the policy (e.g. a newer submission lifts the suppression).
12. When several people from one company submit, the newest row's company fields win
    (e.g. `website`). OK, or should the team's edits in TELL win?
