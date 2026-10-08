# STATE — read this first every session, update it every round

A **round** is one Claude Code session on one sprint. Every round: (1) add a "Round log"
line when you start, (2) update "In progress" after every finished step, (3) move the
round-log line to `finished` or `stopped` when you stop. The pre-commit hook (Sprint 0)
refuses any commit that doesn't touch this file. When the team praises the work, add it
to "Laurels" with the habits that earned it.

**Next sprint:** 0 (Foundation). Branch: `main`.

## Round log (newest first)

- 2026-10-08 · sprint 0 · started — Foundation.
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

Sprint 0 (Foundation). Steps 1–4 done (hook; config; db; `untrusted.py`: scrub drops Cc/Cf/Co/Cs/Cn incl. tag-char smuggling, wrap neutralises tag escapes, injection_flags heuristics, contains_canary survives obfuscation). Next: step 5 llm.py.

## Done

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
