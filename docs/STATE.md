# STATE — read this first every session, update it every round

A **round** is one Claude Code session on one sprint. Every round: (1) add a "Round log"
line when you start, (2) update "In progress" after every finished step, (3) move the
round-log line to `finished` or `stopped` when you stop. The pre-commit hook (Sprint 0)
refuses any commit that doesn't touch this file. When the team praises the work, add it
to "Laurels" with the habits that earned it.

**Next sprint:** 4 (Matching and composing). Branch: `main` (Sprint 3 merged 2026-10-21).
Work order 001 (MacBook, narrowed) still asks for three real CORDIS results pages; see open question 13.

## Round log (newest first)

- 2026-10-21 · Max plan engine · finished — no API costs: without a key every AI job
  becomes a work order for Claude Code under the Claude plan (`CLOE_ENGINE`), join-form
  needs included; 335 tests.
- 2026-10-21 · merge sprint 3 · finished — `claude/relaxed-edison-nggs72` (Sprint 3,
  company research) merged with `main`; its migration renumbered 6 → 9; 331 tests.
- 2026-10-21 · MacBook hand-off · finished — the computer that runs Cloé doesn't see the cloud
  chats: `docs/MACBOOK.md` (runbook), `.claude/skills/cloe-workorder/`, a CLAUDE.md entry.
- 2026-10-20 · orchestrate regions + proposals · finished — the three ACT regions set up
  (seed file + `load`, region-aware suggestions), AI proposals for tensions and
  interventions (API, stand-in, work order; the team accepts); 254 tests.
- 2026-10-20 · orchestrate · finished — `cloe orchestrate`, built on PONT's "Orkestreren als
  ontwerpcompetentie" (De Koning & Renger, 2025): board, check against the model,
  suggestions from the network, collective memory; 248 tests.
- 2026-10-20 · contact language · finished — each person's contact language is captured
  (default English, Dutch offered; explicit beats inferred); 240 tests.
- 2026-10-16 · sprint 3 · finished — company research: KvK-first source catalogue (50
  sources, 12 parsers), site crawl, findings schema with URL validation, API + work-order
  engines, "In the news and in registers" in the profile; 305 tests.
- 2026-10-13 · sprint 2 follow-up · finished — the funding page's real data comes from the
  M-DPP repo (github.com/MDPP-ops/MDPP_Website): 2,530 Dutch projects imported, cards
  most-textile-first; 228 tests.
- 2026-10-09 · sprint 2 · finished — research library: guarded fetcher, funding + CORDIS
  parsers (hand-written fixtures: hosts blocked), cards + FTS5 search, work-order engine;
  226 tests. Work order 001 open for the MacBook.
- 2026-10-09 · sprint 1 follow-up · finished — the team's answers to open questions 8, 11,
  12: rejoiners, people from one company kept individually, colleague links; 157 tests.
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

(none — Sprint 4 not started.)

## Done

- 2026-10-21 (Max plan engine): the team does not want API costs ("Anthropic keys use real
  money, not my Max account"). `config.ENGINES`, `Settings.engine`: `CLOE_ENGINE` (api |
  workorder), and when empty, api with a key or `CLOE_FAKE=1`, else workorder. `--engine`
  on `scrape funding`, `research`, `orchestrate propose` and (new) `ingest joinform` now
  defaults to it, so without a key nothing calls the API: the job becomes a work order.
  New work order kind `classify-needs` (`workorders.write_needs_order` /
  `ingest_needs_order` / `open_needs_order`, `NeedsOrderResult`): `NEED_TASK` verbatim,
  the questions wrapped in a git-ignored `.private.md` (0600), flagged needs never
  included; the result fills only needs still open and blank (repeats, unknown ids and
  needs it wasn't given are skipped; `instruction_like` flags). `cloe workorder ingest`
  takes it; `ingest joinform` writes one when needs are left and none is open. `doctor`
  prints the engine. `tests/conftest.py` now gives every test its own work-order folder.
  MACBOOK.md (`.env` table: key empty; check the shell has no `ANTHROPIC_API_KEY`, or
  Claude Code bills it), the `cloe-workorder` skill and sprint.md Sprints 4–5 updated.
  `uv run pytest -q` → `335 passed, 3 skipped`; ruff clean.

- 2026-10-21 (merge sprint 3): merged `claude/relaxed-edison-nggs72` (forked from 412e171)
  with `main` (contact language, orchestrate, MacBook hand-off). Conflicts, all
  resolved by keeping both sides: `db.MIGRATIONS` (Sprint 3's migration appended as **9**;
  `migrate()` counts list positions, so no other code changes), `cli.COMMAND_MODULES`
  (+ `cloe.cmd_research`), `workorders.py` (orchestrate-proposal and research orders side
  by side), `cmd_library.cmd_workorder_ingest` (three kinds: funding-batch,
  orchestrate-proposal, research), CONTEXT (PONT stays §H; research sources are now **§I**),
  STATE (Sprint 3's open questions 17–20 are now 24–27). `docs/MACBOOK.md` step 2d and the
  `cloe-workorder` skill now cover `cloe research` and research work orders.
  `uv run pytest -q` → `331 passed, 3 skipped` (254 + Sprint 3's 77); ruff clean. Sprint
  3's Definition of Done re-run on a scratch DB (`CLOE_FAKE=1`): schema 9, `cloe research
  example.nl --engine api --fixture tests/fixtures/site` gives the same counts as on its
  branch (KvK found by site, 14 mentions new, 10 facts, flagged 1); `orchestrate load` and
  `suggest` still work on the same DB. Caveat: a database created on the Sprint 3 branch
  (schema 6 with `mention`) cannot migrate to this `main`; none is known to exist (no live
  run was made), and `data/cloe.db` on the MacBook is at 8 or lower, which migrates cleanly.

- 2026-10-21 (MacBook hand-off): `docs/MACBOOK.md` covers what the machine does, the
  one-time setup with the `.env` table, the real-data order (join form, TELL, M-DPP
  library), the ACT boards, work orders, day-to-day consent and language, reporting, and
  what blocks it. `.claude/skills/cloe-workorder/SKILL.md` tells Claude Code there how to
  run a work order. `CLAUDE.md` gained an "On the team's MacBook" section, and the README
  points to MACBOOK.md.
- 2026-10-20 (orchestrate part 2): the team targets **Brabant, Oost-Nederland and
  Amsterdam** (ACT × PONT) and wants AI help with **tensions and interventions**.
  Migration 8 adds `company.region` (TELL `Region`, stored and quarantined like other
  cells) and `orch_proposal`. `orchestrate.REGIONS` holds provinces plus main cities,
  with aliases Twente → Oost-Nederland and MRA → Amsterdam. A regional challenge's
  `suggest` offers every company in the region, matches and join-form registrants first.
  `load_seed` / `cloe orchestrate load <file>` add only what's missing.
  `docs/orchestrate/act-regions.json` holds act-brabant, act-oost-nederland and
  act-amsterdam: region character and the shared reframe, 5 national actors (EZ, IenW,
  OCW, ACT, PONT) and 6 signals each.
  Proposals: `OrchestrationProposal` (≤ 5 signals, tensions first, and ≤ 5 interventions,
  each with quadrant, kind, value, actors, addresses, when and why; closed enums),
  `PROPOSE_TASK` (PONT's model), `context()` (board + network facts, needs and project
  cards, no flagged text), `propose()` (`Claude.extract` over two untrusted blocks),
  `store_proposal()` (strips links, drops instruction-like items, skips duplicates of the
  board or earlier proposals, carries a warning when the reader saw instruction-like
  input), `standin_proposal()` (CLOE_FAKE=1) and `decide()` (accept adds unknown actors as
  not_yet/other and links the addressed signal). Work order `NNN-orchestrate-proposal.md`
  holds instructions and schema only; the board goes to a git-ignored `.private.md`
  (0600), because the repository is public. CLI: `cloe orchestrate
  propose [--engine workorder] | proposals [--status] | accept <ids> | reject <ids> |
  load`. `uv run pytest -q` → `254 passed, 3 skipped`; ruff clean.
- 2026-10-20 (orchestrate): the team asked for a tool that orchestrates following PONT's
  "Orkestreren als ontwerpcompetentie" (the PDF's host is blocked; the team uploaded it).
  The model is summarised in CONTEXT §H. Migration 7 adds tables `opgave`, `orch_actor`,
  `orch_signal`, `orch_intervention` (+ `orch_intervention_actor`), `orch_lesson` and FTS5
  `orch_lesson_fts`. `orchestrate.py` provides `new_opgave`, `set_actor`, `add_signal`,
  `add_intervention`, `set_intervention_status` (done marks its tension addressed),
  `add_lesson`, `search_lessons`, `check` (findings per component), `suggest` (network
  companies by facts and needs, then research projects from the library, then their Dutch
  partners) and `board` (markdown). `cmd_orchestrate.py` provides `cloe orchestrate
  new|list|show|check [--strict]|actor|signal|intervention|status|lesson|lessons|suggest`.
  Tried end to end on the fixtures ("DPP readiness for small knitwear makers": suggestions
  led by Voorbeeld Weverij, Vezel Lab and KNITPASS). `uv run pytest -q` → `248 passed, 3
  skipped`; ruff clean. New `tests/test_orchestrate.py` (8). README, sprint.md Sprint 6
  (the functions become chat-agent tools).
- 2026-10-20 (contact language): the team shared their Dutch invitation (sent by email and
  WhatsApp, "Hoi [naam]") and asked Cloé to capture each person's preferred contact
  language: **default to English, but offer Dutch**. Migration 6 adds `person.lang_source,
  lang_evidence, lang_at, formality`; `person.lang` existed but was unused until now.
  `cloe/language.py`: `detect(text)`, `formality(text)`, `parse_choice(value)`,
  `set_language(…)`, `contact_language(…) -> ContactLanguage(lang, formality, source,
  evidence, offer_dutch)`. The join form captures it: the optional `preferred_language`
  column (read when the sheet gains it), else the language of the person's own answers
  (question, role, other tier). `cloe language set <email> nl|en [--formality je|u]
  --evidence …` records it by hand. The profile shows a language line per contactable
  person, and the export includes the fields. The library's stand-in now uses the same
  detector. sprint.md Sprints 4 and 5 now say how compose and the inbox use it.
  `uv run pytest -q` → `240 passed, 3 skipped`; ruff clean; golden profile regenerated
  (only the language lines changed). New `tests/test_language.py` (12).
- 2026-10-16 (sprint 3): `cloe research <company>` — the team's ask (2026-10-16): "a scraper
  that looks at a company and digs the internet for every article that mentions them,
  including public databases; start with the KvK number". **Sources first:** CONTEXT §I and
  `sources/registers.py` (`CATALOGUE`: 50 sources in 8 groups — identity, official
  publications, funding/procurement, IP & certification, news, academic, people, HvA
  library; 12 parsers for the documented machine-readable ones: KVK API Zoeken/Basisprofiel,
  OpenKVK, OpenCorporates, Wikidata SPARQL, MediaWiki, SRU (officielebekendmakingen), RSS
  (Google/Bing News), GDELT, OpenAlex, Crossref, Wayback CDX, Zenodo). The KvK number keys
  the official half; TELL's export has no KvK column, so Cloé reads it from the company's
  own site (`web.find_kvk`; Dutch law makes them print it), `--kvk`, or KVK's name search.
  `sources/web.py` crawls the site (own host only; the metadata address a hostile page links
  to is never followed). `research.py`: `ResearchFindings` (identity, facts, people,
  needs, data, news, mentions, instruction_like_found, open_questions), `validate_findings`
  (every URL must be one Cloé fetched or the web tools cited; others dropped and counted;
  "S3" ids resolved), the API engine (crawl → loaded sources → registers → newest articles
  → one reader call → one web research call whose text goes through the same reader →
  merge → `match(status=proposed)` seeds), expiry 180 d (event) / 365 d (does…), repeats
  renewed, contradictions kept with dates. `workorders.write_research_order` /
  `ingest_research` (`ResearchOrderResult`: `visited[]` + findings; facts may only cite
  visited URLs). Migration 6 on its branch, 9 on `main`: `mention` (one row per
  company+URL: title, date, outlet, kind, register), `company.researched_at/legal_form/sbi_json`. Profile: KvK, legal form,
  SBI, "Last researched", "## In the news and in registers" (newest first, flagged ones
  under "Flagged text"). Fetcher: optional `headers` (API keys), XML types. Settings
  `CLOE_KVK_API_KEY`, `CLOE_OVERHEIDIO_API_KEY`. Dep `defusedxml`.
  **Definition of Done** (`CLOE_FAKE=1`, scratch DB with the TELL fixture): `uv run pytest -q`
  → `305 passed, 3 skipped`; ruff → `All checks passed!`; `cloe research example.nl --engine
  api --fixture tests/fixtures/site` → `KvK 12345678 (found by site)` · `pages: 5 read, 3 not
  fetched · registers: 12 read, 0 failed, 3 skipped · articles read: 3` · `mentions: 14 new,
  4 seen · facts: 10 new, 0 renewed · people 2 · needs 2 · data 3` · `dropped (unlisted
  source): 0 · flagged: 1`; run again → `was researched on 2026-10-16; --refresh runs it
  again`; `cloe research example.nl --engine workorder` → `docs/workorders/002-research-
  example.nl.md` (deleted after the run — fictional company; the golden copy is
  `tests/fixtures/workorders/research-order.md`); `cloe workorder ingest 002 --result
  tests/fixtures/workorders/research-result.json` → `pages: 4 read` · `dropped (unlisted
  source): 3 · flagged: 3` with a WARN per unlisted source; `cloe profile example.nl` →
  header `KvK 12345678 · Legal form Besloten Vennootschap · SBI 13.20 · Last researched
  2026-10-16`, 14 mentions newest first, the injected fact and need only under "Flagged
  text". Tests: `test_registers` (24), `test_web` (12), `test_research` (12),
  `test_workorder_research` (4), `test_cmd_research` (3); fixtures `tests/fixtures/site/`
  (README explains every file is a hand-written stand-in) and `tests/fixtures/workorders/`.
  **Hand-off:** per-company token cost of an API run: **not measured** (no key in the
  cloud). No live run anywhere yet: every source host is blocked from cloud sessions
  (CONTEXT §I lists the 2026-10-16 probe); the parsers were written from documentation and
  the first MacBook run must save the real responses over the fixtures (open question 26).
  Differences from sprint.md: people found on the web become `contact` facts (name — role,
  URL, date), not `person` rows (a person row is someone who gave an email); the work-order
  result sits next to the order (Sprint 2 convention) rather than `data/workorders/`; the
  web research text is parsed by a second schema call (readers have no free-text channel);
  a `mention` table was added for "every article".

- 2026-10-13 (sprint 2 follow-up): the team pointed to the source of m-dpp.nl,
  `github.com/MDPP-ops/MDPP_Website` (public; cloned read-only at 836204b). The real page
  is a D3 network over three JSON datasets (CONTEXT §E). The HTML parser built on
  stand-ins could never have worked on it: the page's HTML has no project list.
  `sources/funding.py` now reads the datasets (`load(dir) -> (refs, counts)`, the page's
  filter: EU projects with a Dutch member, plus NWO's filtered file). `scrape funding
  --mdpp <checkout>` imports every project (no model calls) and cards the next N without
  a card, most textile-specific first. Migration 5 (`project.ext_id` unique,
  `funding_scheme`, `ec_grant`, `keywords_json`, `nl_orgs_json`). The CORDIS project-page
  parser was removed (the dataset has those fields); `parse_results` stays for
  deliverables. The work-order engine writes an input file of the chosen projects.
  Fixtures are real sample records from the repo plus the fictional KNITPASS chain for
  the results-page path. `untrusted`'s "act as" heuristic was narrowed: it flagged 16
  real abstracts ("will act as a hub").
  **Definition of Done** (`CLOE_FAKE=1`, scratch DB): `uv run pytest -q` → `228 passed,
  3 skipped`; ruff clean; `cloe scrape funding --fixture tests/fixtures/funding
  --max-projects 3` → `projects imported 8 (8 new): 5 CORDIS (of 6), 1 Erasmus+ (of 2),
  2 NWO/SIA (of 2)` · `projects carded 3` · `documents: 3 new` · `pages the fixture has no
  copy of: 3`; `library search "digital product passport knitwear"` → 3 cards (AUTOLOOP,
  CISUTAC, PESCO-UP); `library stats` → `projects 8 (on CORDIS 5/8, with documents 3)`.
  **Real data:** `cloe scrape funding --mdpp <MDPP_Website checkout> --max-projects 10
  --max-docs-per-project 0` → `projects imported 2530 (2530 new): 1983 CORDIS (of 8429),
  423 Erasmus+ (of 6631), 124 NWO/SIA (of 124)` in 4 s, 10 cards (the stand-in), 0 flagged.
  **Hand-off, now with real numbers:**
  - *Page structure:* D3 network (d3 7.9.0) over `cordis_textile_projects.json`,
    `erasmus_textile_projects.json` and `nwo_textile_raw.json`, filtered in the browser to
    projects with a Dutch member, plus programme, year and keyword toggles. Cloé uses NWO's
    filtered file (124 projects); the page loads the unfiltered one (4,090, including
    non-textile projects).
  - *Projects listed:* 2,530 with a Dutch partner (1,983 CORDIS: 1,102 H2020, 881 Horizon
    Europe; 423 Erasmus+; 124 NWO/SIA). Only 785 mention a textile term and 117 are
    strongly textile-specific. 1,765 distinct Dutch organisations.
  - *CORDIS resolution:* 1,983/1,983 CORDIS projects carry their grant id (100%; no page
    lookup needed); 1,983/2,530 overall.
  - *Document types:* the datasets give one abstract per project (median 1,200 characters,
    M-DPP's cut). Further material: 241 open-access publication links (26 NWO projects),
    26 Erasmus+ project websites. CORDIS deliverables are only on results pages, which are
    still unseen (work order 001).
- 2026-10-09 (sprint 2): Definition of Done, run with `CLOE_DB` in a scratch folder and
  `CLOE_FAKE=1`: `uv run pytest -q` → `226 passed, 3 skipped`; ruff → `All checks passed!`;
  `cloe scrape funding --fixture tests/fixtures/funding --max-projects 3` → `projects listed
  5, processed 3 (3 new), on CORDIS 2/3, CORDIS pages read 2` · `documents: 6 new` ·
  `document types: 2 project_page, 2 deliverable, 1 publication, 1 project_site`;
  `cloe library search "digital product passport knitwear"` → 3 cards (KNITPASS project
  page, D2.1 deliverable, Zenodo field study); `cloe library stats` → `projects 3 (on CORDIS
  2/3, with documents 3)`, `documents 6 (flagged 0)`. Modules: `sources/fetch.py`,
  `sources/funding.py`, `sources/cordis.py`, `library.py`, `scrape.py`, `workorders.py`,
  `cmd_library.py`. Tests: `test_fetch` (29, local http.server), `test_funding` (18),
  `test_library` (14), `test_cmd_library` (6), PDF-payload tests in `test_injection`.
  **Hand-off (sprint.md asks for these):**
  - *Real page structure:* **not seen.** m-dpp.nl, cordis.europa.eu, ec.europa.eu,
    zenodo.org and data.europa.eu are all blocked from cloud sessions (proxy 403, 2026-10-09),
    and `tests/fixtures/funding/` did not exist. Following sprint.md's fallback, the
    parsers were built on hand-written stand-ins (`tests/fixtures/funding/README.md`) and
    `docs/workorders/001-fetch-funding-page.md` asks the MacBook to save the real pages
    into `tests/fixtures/funding_real/`.
  - *How many projects it lists:* unknown until work order 001 runs (the stand-in lists 5).
  - *CORDIS resolution rate:* 2/3 on the stand-in (the third project has only its own
    site). The real rate comes from step 6 of work order 001.
  - *Document types:* on the stand-in, deliverables and project pages, then a
    publication and a project site. The real mix is unknown.
  - No live scrape was run, from this session or any other.

- 2026-10-09 (sprint 1 follow-up): migration 3 (`person.flags`, `colleague_link`);
  rejoin detection; join form fills company blanks only; colleague links; profile names
  the person behind each join-form source and lists colleague links; `forget` counts links
  and moves the forget date on a repeat. `uv run pytest -q` → `157 passed, 3 skipped`;
  ruff clean. New `tests/test_rejoin_colleagues.py`; golden profile regenerated. Sprint 4
  and 5 sections of `sprint.md` now carry the `welcome` / `colleague_ask` /
  `colleague_intro` formats and the inbox rules for them.
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

- **No API costs (team, 2026-10-21):** the MacBook runs without `ANTHROPIC_API_KEY`; every
  model job is a work order that a person starts in Claude Code under the team's Claude
  plan. New model jobs (Sprints 4–5) get a work-order twin from the start. Unattended,
  scheduled model work would need an API key, or a check of the plan's terms first.
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
  **Each person is kept individually** (team, 2026-10-09): the join form only fills empty
  company fields (the first registrant's details stand), each submission's answers stay
  facts with that submission as source (the profile names whose submission it is), and a
  person's own new row updates their own name/role. TELL only fills blanks and never
  changes a known person. TELL rows without an id get `tell_id = "export:<identity_key>"`.
- **Colleague links (migration 3, team 2026-10-09):** when a new person registers through
  the join form at a company where others already registered (people with join-form
  consent rows — TELL contacts don't count), a `colleague_link(newcomer_id, existing_id,
  status=detected)` is recorded per earlier registrant. Cloé (Sprint 4/5) tells the
  newcomer someone from their company is registered and asks both whether they may be
  connected; neither ask names the other; names are shared only when both `*_ok = yes`
  (`connected`); any no → `declined`. `export` shows a person's links without naming the
  colleague; `forget` removes them (cascade).
- **Rejoining (team, 2026-10-09):** a forgotten email whose join-form row is dated after
  the forget (`forgotten.at`) is a rejoin: imported again, person flag `rejoined`, event
  `rejoin`. Rows dated before the forget, or undated, stay out. TELL skips a forgotten
  email unless the person has rejoined. Forgetting again moves `forgotten.at`. The
  Sprint 4 `welcome` says it looks like they're rejoining and shows what we know about
  their company; Sprint 5 clears the flag once that welcome is sent.
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
  `people.forgotten_at`, `people.add_flag(conn, pid, flag)`,
  `people.link_colleagues(conn, company_id, newcomer_id)`, `people.upsert_person`, `people.set_consent(…, at=…)`, `people.current_consent`,
  `people.consents`, `people.forget`, `people.export`; `joinform.ingest(conn, tabs,
  raw_dir, claude, canary) -> Report` (tabs from `read_file` or `read_sheet`);
  `tell.ingest(conn, recs, origin, digest)`; `profile.render(conn, company_id)`,
  `profile.write(conn, company_id, dir)`. Settings `CLOE_JOINFORM_SHEET_ID`,
  `GOOGLE_SERVICE_ACCOUNT_FILE`; extra `sheets` (google-auth). Sheets are read with
  `FORMATTED_VALUE` only (never formulas).

- **Fetcher (Sprint 2, `sources/fetch.py`):** the only way Cloé reads the web. http(s)
  only; every DNS answer must be public (`ipaddress.is_global`, IPv4-mapped unwrapped) before
  connecting and after each of ≤ 3 redirects; the socket goes to the vetted address (no
  rebinding); robots.txt per origin (RFC 9309: 4xx = allow, 5xx / blocked = disallow),
  user agent `CloeBot/0.1`; 1 s per host; 15 s timeouts and body deadline; 2 MB, PDF 20 MB,
  60 PDF pages; types html / plain / pdf / json, octet-stream only when it starts with
  `%PDF-`; `Accept-Encoding: identity`; raw bytes in `data/raw/<sha256>` (0600). No HTTP
  proxy support, by design (the address check needs a direct connection). Live scrapes run
  on the MacBook.
- **Library (migration 4):** one document per source. `card_json` holds the full
  `DocumentCard`; `tags_json` = topic labels + free tags; FTS5 `document_fts` (rowid =
  document.id) indexes title, one_line + summary + data_offered, tags, and body (≤ 200k
  characters). The reader sees ≤ 60k characters. A card is remade only when the source's
  sha256 changes. Card prose never carries links, emails or phone numbers (the source URL
  is the only link). Documents flagged `instruction_like` stay out of search unless
  `--include-flagged`, and Sprint 4 writers must skip them. `doc_type` is one of
  `project_page deliverable publication report project_site page document other`.
- **Taxonomy and tiers:** `library.TAXONOMY`, 25 topics (dpp, espr, epr, recycling,
  sorting, repair, reuse, fibres, biobased, dyeing_printing, knitting, weaving, finishing,
  nonwovens, traceability, lca, business_models, digital_twins, small_batch, textile_waste,
  circular_design, data_standards, policy, smart_textiles, workwear).
  `library.TIERS`: fibre, yarn_textile, finishing, garment, brand, retail,
  collection_sorting, recycling, repair, services. `tier_slugs(label)` maps a TELL tier
  label onto them; Sprint 4 matching should use it.
- **Funding network (follow-up, migration 5):** the source is M-DPP's datasets, read
  from a checkout of `github.com/MDPP-ops/MDPP_Website` (`--mdpp`, or `CLOE_MDPP_DIR`; no
  web fetch, and the files are 20–28 MB). The page's filter is applied (EU projects with a
  Dutch member, plus NWO's filtered file). A project is keyed by `ext_id` (`cordis:<id>`,
  `erasmus:<id>`, `nwo:<id>`), then CORDIS id, then acronym. The dataset is the authority
  for a project's facts. `nl_orgs_json` holds the Dutch organisations with CORDIS
  activity type (PRC/HES/REC/PUB/OTH) or Erasmus+ orgType, and role; `partners_nl_json`
  holds their names. No people: NWO researchers' names and ORCIDs are dropped and only
  their organisation's top level is kept. A natural person registered as a CORDIS
  participant (a sole trader) appears as CORDIS lists them. Cards: each run cards the
  next `--max-projects` projects without a `project_page` document, ordered by
  `ProjectRef.core_score()` (textile terms in title ×3, keywords ×2, abstract ×1), then
  newest. The card's text is `scrape.project_text` (title, programme, dates, abstract,
  keywords, Dutch partners). Material: CORDIS results page (fetched) → deliverables and
  publications; NWO open-access publications (DOIs); Erasmus+ project website.
- **Contact language (migration 6, team 2026-10-20):** default **English**, Dutch
  **offered**. Two strengths: *explicit* (`joinform` language answer, `manual` via `cloe
  language set` with evidence, `inbound` reply from Sprint 5), where the newest wins; and
  *inferred* (`joinform_text`, the language of their own answers, ≥ 3 stopword hits and a
  2:1 margin), which is used only while nothing explicit exists and never replaces an
  explicit choice. `offer_dutch` is true while the language is English and not explicit,
  so an English message carries one line offering Dutch (Sprint 4); a Dutch reply
  switches them (Sprint 5). Dutch is je unless their Dutch uses u/uw. Languages are `en`
  and `nl` only (tone.md covers those two). Every change logs `language_set` (ids and
  codes only).
- **Orchestrate (migration 7, team 2026-10-20):** follows PONT's orchestration model
  (CONTEXT §H). A challenge (`opgave`, by slug) holds actors (kind company / knowledge /
  government / network / funder / project / citizen / other; level micro / meso / macro;
  `has_mandate`; interest, timeline, `involve_when` for stakeholder timing, `staging` for
  stakeholder staging; status not_yet / involved / resting / left; optional link to a
  company, project or person); signals (pattern / tension / opportunity / blockage, with a
  level); interventions in the four quadrants (`timing_mandate`, `strategic` = with
  mandate; `use_space`, `make_space` = with stakeholders; short and long term), with kind,
  value, actors, `follows` (catalyst chain) and the signal they address; and lessons
  (success / failure / insight, FTS-searchable across challenges). `check` encodes the
  paper:
  - nobody with a mandate involved, or no intervention in the upper half;
  - a crucial voice missing (company, knowledge or government);
  - no timing or no staging for an actor;
  - an involved actor held without a role;
  - an open tension with no intervention;
  - one system level only;
  - only short-term or only long-term steps;
  - an intervention done without a lesson;
  - earlier lessons from other challenges that apply (info).

  It is code only, no model calls. Team input is trusted. Network text used by `suggest`
  skips flagged facts and needs. Nothing contacts anyone.
- **Orchestrate proposals (team, 2026-10-20):** an LLM job with two engines (API;
  work order `orchestrate-proposal`) plus the CLOE_FAKE stand-in. The reader sees the
  board and the network context as untrusted blocks, has no tools, and returns the schema.
  Code checks every item. Proposals never reach the board without `accept`, and nothing
  contacts anyone. Boards are internal strategy: work-order inputs about a board stay out
  of git.
- **`untrusted.injection_flags` (follow-up):** "act as" counts only when followed by an
  AI/admin role ("act as an AI", "act as admin"). On its own it flagged 16 real CORDIS and
  Erasmus+ abstracts.
- **CLOE_FAKE=1** (`Settings.fake_llm`): library cards come from `library.standin_card`, a
  keyword stand-in run through FakeClaude. It is for dry runs and the DoD only; the doctor
  warns. Under it, the join form leaves needs unclassified.
- **Work orders (basic):** `docs/workorders/NNN-<kind>.md`, numbered after the highest
  existing number. The result sits next to it as `NNN-<kind>.result.json` (git-ignored).
  Each has a `work_order` row (`funding-batch`: open → ingested). Results are untrusted:
  Pydantic `FundingBatchResult` (extra=forbid), card checks as for the API engine, and
  documents without a valid http(s) URL are skipped.
- **Sprint 2 interfaces:** `fetch.Fetcher(raw_dir).fetch(url) -> Fetched`,
  `fetch.FixtureFetcher(dir, raw_dir)`, `fetch.to_text / html_to_text / pdf_to_text`;
`library.add_document(conn, claude, canary, source_id=, text=,
  project_id=, doc_type=, title_hint=)`, `library.store`, `library.check_card`,
  `library.search(conn, query, k, tier=, topic=, include_flagged=)`, `library.get`,
  `library.stats`, `library.tier_slugs`; `scrape.scrape_funding(conn, refs, sources,
  fetcher, claude, canary, …)`, `scrape.import_projects`, `scrape.to_card`,
  `scrape.project_text`, `scrape.scrape_url`, `scrape.upsert_project(conn, ref)`;
  `funding.load(dir)`, `funding.priority`, `funding.ProjectRef` (ext_id, source, nl_orgs,
  abstract, keywords, publications, …); `cordis.parse_results / results_url /
  cordis_id_of / iso_date`; `workorders.write_funding_batch(conn, dir, refs, max_docs=)`
  (+ `NNN-funding-batch.input.json`), `workorders.ingest_funding_batch` (documents name
  their project by `project_ext_id`); `records.write_raw` (was `_write_raw`). Removed
  in the follow-up: `funding.parse_funding_page`, `cordis.parse_project`.

- **Company research (Sprint 3):** the KvK number is the company key for public databases;
  sources are data (`registers.Register`: keyed by kvk/name/domain/local, access open/key/
  person/loaded, format, URL template, parser, note) and `cloe research <c> --list-sources`
  prints them. Readers see wrapped page text and cite a URL or a block id; code validates
  every URL against what was actually fetched or cited. A person's work-order result is
  validated the same way against the pages they say they visited. People from the web are
  `contact` facts, never `person` rows. Facts expire (event 180 d, others 365 d); a fact
  seen again is renewed, a contradicting one is added with its date. `--refresh` is needed
  within 30 days of the last run; the work-order engine refuses while an order is open.
  Mentions (articles, register entries, papers, archived pages) are rows, one per
  company+URL, flagged like facts. Only facts cite sources; needs, data and open questions
  cite the run (`cloe://research/<engine>/<date>/company-<id>`).
- **Sprint 3 interfaces:** `registers.CATALOGUE / BY_KEY / Subject / queries(subject, keys)
  / url_for / describe / parse / search_name / iso_date / PRESS_DOMAINS / SOCIAL_DOMAINS`;
  `web.crawl_site(fetcher, domain, max_pages=, start_url=) -> Crawl(pages, errors,
  offsite_links, kvk)`, `web.find_kvk`; `research.ResearchFindings`, `validate_findings
  (findings, allowed, aliases)`, `research_company(conn, settings, claude, fetcher, cid,
  raw_dir=, max_pages=, max_mentions=, web_research=, kvk=) -> Report`, `merge_findings`,
  `apply_identity`, `add_mention`, `loaded_mentions`, `seed_matches`, `recently_researched`,
  `standin_findings` (FakeClaude key `ResearchFindings`; `research` → empty
  `ResearchResult`); `workorders.write_research_order(conn, dir, cid, query=)`,
  `ingest_research(conn, number, result, strict_number=)`, `ResearchOrderResult`,
  `open_research_order`; `fetch.Fetcher.fetch(url, headers=None)`; migration 6.

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
   form responses" (in the TOS13 workspace) with it as Viewer, and keeps the key on the
   MacBook? The sheet id stays in `.env` (`CLOE_JOINFORM_SHEET_ID`), not in the repo.
9. Cloé treats an unsubscribe as "no" for *every* email purpose (follow-up, newsletter,
   Cloé updates), not only the newsletter. Chloe to confirm.
10. `cloe ingest tell --db`: the SQL (`tell.DB_QUERY`) was written from the table list in
    CONTEXT §D; TELL's own `query_org` could not be read this session. TELL team to check
    the joins before first use; the xlsx export remains the default.
11. ~~Rejoining after a forget~~ — decided 2026-10-09: welcome them back (see Decisions).
12. ~~Several people from one company~~ — decided 2026-10-09: each person kept
    individually, with colleague links (see Decisions).
13. **Work order 001** (MacBook, narrowed 2026-10-13): save three real CORDIS results
    pages (CISUTAC, PESCO-UP, TCBL) and one deliverable into
    `tests/fixtures/funding_real/`. Then the next session checks `cordis.parse_results`
    against them. The funding page itself is no longer needed (M-DPP repo).
14. Chloe / the team: review the closed topic list (`library.TAXONOMY`, 25 topics) and the
    tiers (`library.TIERS`). The tier mapping is based on the 7 TELL "Supply chain tier"
    labels seen in the fixtures; TELL's full list should be checked against it.
15. ~~CORDIS JSON~~: resolved 2026-10-13. M-DPP already uses the CORDIS open-data bulk
    files; Cloé reads M-DPP's result.
16. How many projects to card, and with which engine? About 785 mention a textile term
    (117 strongly). Carding them all with the API is ~785 calls; the work-order engine
    does it under Claude Max. Default per run: 3.
17. **Join form language question** (team): add "Preferred language for our messages:
    English / Nederlands" to the space13.to join form (`tos13website`: `join.html`, plus
    `Code.gs` `COLUMNS` with `preferred_language` appended at the end). Code.gs writes the
    header only on an empty sheet, so add the header cell to the live sheet by hand. Cloé
    already reads the column. Until then the language is inferred or defaults to English.
18. **Chloe:** the wording of the one-line Dutch offer (a tone.md §6 fixed text). Also
    update tone.md §3 to "default English, offer Dutch": it says "website and form in
    English → English", which now matches, but doesn't mention the offer. Needs your
    sign-off.
19. **WhatsApp:** the team shares invitations by email and WhatsApp. Cloé's channels are
    email and SMS (WhatsApp Business is in the backlog; it needs template approval).
    Decide before Sprint 5.
20. Chloe: should the 2026-10-20 TOS13 invitation (Dutch, je-form, signed by Borre) be
    one of tone.md §9's calibration examples? §9 asks for messages Chloe wrote, so it's
    your call. The text is not in the repo.
21. ~~Orchestrate: which challenges, and AI help?~~ Decided 2026-10-20: Brabant,
    Oost-Nederland and Amsterdam; AI proposes tensions and interventions, and the team
    accepts.
22. **The repository is public.** CONTEXT §H and `docs/orchestrate/act-regions.json`
    quote the ACT × PONT proposal (an internal draft, March 2026): the region characters,
    "een orkestrerende kracht die beweging organiseert waar regie ontbreekt" (an
    orchestrating force that creates movement where no one has the lead), and national
    signals such as fragmented funding and policy that doesn't fit the market. Is that
    fine to publish, or should the seed file move out of the repo (e.g. to Drive)? Boards
    themselves live only in the MacBook's database.
23. ~~Sprint 3 is on a separate branch~~ — merged into `main` 2026-10-21 at the team's
    request; its migration is now number 9. Questions 24–27 came with it (they were 17–20
    on its branch).
24. **TELL and the KvK number** (TELL team): is `organizations.id` the KvK number? If so,
    `tell.DB_QUERY` should carry it into `company.kvk`. The xlsx export has no KvK column
    — can TELL add one? Until then Cloé reads it from the company's site or KVK's search.
25. **API keys** for the keyed registers: who registers at developers.kvk.nl (Zoeken free,
    Basisprofiel metered per call) and overheid.io (free tier)? They go in the MacBook's
    `.env` as `CLOE_KVK_API_KEY` / `CLOE_OVERHEIDIO_API_KEY`; without them those three
    registers are skipped and reported.
26. **First live run (MacBook):** `cloe research <a real company> --engine api --verbose`
    with an API key, then save the real register responses over `tests/fixtures/site/*`
    and tell the next session which of the 12 parsers broke — all were written from
    documentation. URL parameters marked unverified: OpenKVK endpoint version,
    projecten.rvo.nl, TenderNed, FashionUnited, Ecotextile. Also measure the token cost.
27. **HvA library:** may the team use Nexis Uni (full-text Dutch press) and Company.info in
    research work orders? The order asks for them when available.
