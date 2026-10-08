# STATE — read this first every session, update it every round

A **round** is one Claude Code session on one sprint. Every round: (1) add a "Round log"
line when you start, (2) update "In progress" after every finished step, (3) move the
round-log line to `finished` or `stopped` when you stop. The pre-commit hook (Sprint 0)
refuses any commit that doesn't touch this file. When the team praises the work, add it
to "Laurels" with the habits that earned it.

**Next sprint:** 1 (Know the network: join form + TELL + profiles). Branch: `main`.

## Round log (newest first)

- 2026-10-08 · sprint 1 · started — join form + TELL + profiles.
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

Sprint 1. Done so far: `records.py` (identity rules, company/source/fact/need writes),
`people.py` (person, consent ledger, forget, export), migration 2 (`company.company_class`,
`company.identity_key`, `forgotten`), settings `CLOE_JOINFORM_SHEET_ID` +
`GOOGLE_SERVICE_ACCOUNT_FILE`, optional extra `sheets` (google-auth). Team asked that the
join form be read straight from the "TOS13 join form responses" Google Sheet: header row
checked on 2026-10-08, it matches CONTEXT §C exactly (24 columns, tab `Responses`); a
second tab `Unsubscribe` has `submitted_at, email, responses_updated`.
Step 2 done: `sources/sheets.py` (Sheets API, read-only service account, formatted values
only) and `sources/joinform.py` (sheet or CSV/XLSX; header detection; quarantine of
instruction-like name/header cells; consent seed; unsubscribe tab; needs classified via
`extract`, unclassified without a key); `cloe ingest joinform [file]`; fixture
`tests/fixtures/joinform.csv`; injection placeholder for Sprint 1 is now a real test.
Step 3 done: `sources/tell.py` (dashboard xlsx export; `--db` read-only via
`TELL_DB_URL` + required `TELL_DB_CA_CERT`; fills blanks only; keywords chunked ≤ 20 per
fact, flagged `scraped`; contacts as people without consent); `cloe ingest tell`;
fixture `tests/fixtures/tell.xlsx` (+ `make_tell_xlsx.py` to regenerate).
Steps 4–5 done: `profile.py` (render + write, golden `tests/fixtures/profile_example.nl.md`),
`cmd_network.py`: `cloe profile`, `cloe companies list [--tier --city --needs [KIND]]`,
`cloe consent set`, `cloe forget`, `cloe export`. Consent dating fixed after self-review:
a seen row only acts on changed consent cells (dated when observed); unsubscribes are
applied once (kept as join-form sources); code-flagged needs are never sent to a model.
Next: step 6, DoD run, README, STATE hand-off, final commit, push, Slack.

## Done

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
