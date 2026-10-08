# STATE — read this first every session, update it every round

A **round** is one Claude Code session on one sprint. Every round: (1) add a "Round log"
line when you start, (2) update "In progress" after every finished step, (3) move the
round-log line to `finished` or `stopped` when you stop. The pre-commit hook (Sprint 0)
refuses any commit that doesn't touch this file.

**Next sprint:** 0 (Foundation). Branch: `main`.

## Round log (newest first)

- 2026-10-08 · planning · finished — sprint.md, CLAUDE.md, tone.md, CONTEXT.md written;
  deps added; first commit + push.

## In progress

(none — Sprint 0 not started)

## Done

- 2026-10-08 (planning): `uv init --lib`; deps `anthropic`, `pydantic`, `beautifulsoup4`;
  extras `tell` (pymysql, openpyxl), `pdf` (pypdf); dev `pytest`, `ruff`. `.gitignore`,
  `.env.example`, `pyproject` script entry `clo = clo.cli:main`. Wrote `sprint.md`,
  `CLAUDE.md`, `tone.md` (v1.0, calibration pending), `docs/CONTEXT.md`, `docs/LESSONS.md`.
  Verified SDK 1.12.1 surface: `beta.messages.parse(output_format=…, fallbacks=…)`,
  `tool_runner`, `beta_tool` all present.

## Decisions

- Language: Python 3.12 + uv. Store: SQLite (stdlib) with FTS5 for the library.
- Clo's runtime model: `claude-opus-5-5` for every call (`CLO_MODEL`; `CLO_MODEL_BULK`
  defaults to the same). Sprints are executed by Opus 5.5 sessions; planning was done by
  a Fable 5.1 session.
- Voice: Clo writes on Cloé's behalf, is open about being her AI assistant, and nothing is
  sent without Cloé's approval. `tone.md` is the single source of truth; code loads it
  verbatim.
- Every LLM job has two engines: API (`--engine api`) or a work order executed by a
  Claude Code session on the MacBook (`--engine workorder`). Same schemas, same outputs.
- Security is code, not prompts: readers have no tools, writers see only extracted facts,
  sending is gated Python with a named approver. Full list in `sprint.md` → "Security".
- LinkedIn is never scraped. It is a work order a person performs in their own browser,
  recording business-role facts only.

## Open questions for Cloé / the team

1. Cloé's surname, role, and 5–10 real messages she has sent (for `tone.md` §9).
2. Who approves messages when Cloé is away? (second approver in `CLO_APPROVERS`)
3. Read-only TELL DB credentials, or rely on the public xlsx export? (default: export)
4. Phone number + SMS-consent field on the join form? Until then SMS is limited to people
   who gave a number and consent elsewhere.
5. SMS provider (Twilio vs MessageBird) and the sending mailbox for email
   (hello@space13.to via Google Workspace SMTP?).
6. Who owns the AI-statement and privacy-statement updates on space13.to? (Sprint 7 drafts
   them.)
7. Unblock `m-dpp.nl`, `news.byborre.com`, `byborre.com` in the cloud environment's
   network settings, or run work order 001 on the MacBook before Sprint 2.
