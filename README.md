# Clo

Clo is the network orchestrator for the TOS13 network period (WP1 Encode). She gets to
know the companies in the network, finds them data they can use, and brings it to them by
email and SMS — as Cloé's AI assistant, after Cloé approves.

- **Plan:** `sprint.md` (one sprint per Claude Code session) · **Status:** `docs/STATE.md`
- **Voice:** `tone.md` · **Facts already researched:** `docs/CONTEXT.md`
- **Rules for Claude Code sessions:** `CLAUDE.md`

## Setup

```
uv sync --all-extras
cp .env.example .env          # fill in what you have; CLO_SEND stays 0 until launch
git config core.hooksPath .githooks   # after Sprint 0
uv run clo doctor
```

Status: planning done (2026-10-08); Sprint 0 not started.
