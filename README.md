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
```

Plan: `sprint.md` (one sprint per Claude Code session) · Status: `docs/STATE.md` ·
Voice: `tone.md` · Researched facts: `docs/CONTEXT.md` · Session rules: `CLAUDE.md`.
