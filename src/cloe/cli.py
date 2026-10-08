"""`cloe` command line. Later sprints add commands by listing their module in
`COMMAND_MODULES`; each such module defines `register(subparsers)` and sets
`func=handler` on its parsers (`handler(args, settings) -> int`)."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import sqlite3
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from cloe import config, db, persona

COMMAND_MODULES: tuple[str, ...] = ("cloe.cmd_network",)

OPTIONAL_EXTRAS = {
    "openpyxl": "tell", "pymysql": "tell", "pypdf": "pdf", "google.auth": "sheets",
}
PLACEHOLDER_DOMAINS = ("example.org", "example.com", "example.net")


def _version() -> str:
    try:
        return version("cloe")
    except PackageNotFoundError:
        return "0+unknown"


def cmd_version(args: argparse.Namespace, settings: config.Settings) -> int:
    print(f"cloe {_version()}")
    return 0


def cmd_init(args: argparse.Namespace, settings: config.Settings) -> int:
    conn = db.connect(settings.db)
    ran = db.migrate(conn)
    current = db.schema_version(conn)
    db.event(conn, "cli", "init", ref="db", detail={"migrations_run": ran, "schema": current})
    conn.close()
    print(f"OK   database {settings.db} at schema {current} ({ran} migration(s) applied)")
    return 0


class _Report:
    def __init__(self) -> None:
        self.failed = False

    def ok(self, msg: str) -> None:
        print(f"OK   {msg}")

    def warn(self, msg: str) -> None:
        print(f"WARN {msg}")

    def fail(self, msg: str) -> None:
        self.failed = True
        print(f"FAIL {msg}")


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:  # a dotted name whose parent package is missing
        return False


def _hooks_path() -> str:
    try:
        out = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip()


def cmd_doctor(args: argparse.Namespace, settings: config.Settings) -> int:
    r = _Report()
    py = sys.version_info
    (r.ok if py >= (3, 12) else r.fail)(f"python {py.major}.{py.minor}.{py.micro}")

    if settings.env_path.exists():
        r.ok(f"settings file {settings.env_path}")
    else:
        r.warn(f"no {settings.env_path}; using the environment only (cp .env.example .env)")
    r.ok(f"model {settings.model} · bulk {settings.model_bulk} · effort {settings.effort}")
    if settings.canary:
        r.ok("canary present")
    else:
        r.fail("no canary")

    if settings.anthropic_api_key:
        r.ok("ANTHROPIC_API_KEY set (API engine available)")
    else:
        r.warn("ANTHROPIC_API_KEY not set: only the work-order engine can run LLM jobs")

    if settings.joinform_sheet_id and settings.google_service_account_file:
        if Path(settings.google_service_account_file).is_file():
            r.ok("join form: Google Sheet + service account key configured")
        else:
            r.fail("GOOGLE_SERVICE_ACCOUNT_FILE does not point to a file")
    else:
        r.warn("join form sheet not configured (CLOE_JOINFORM_SHEET_ID, "
               "GOOGLE_SERVICE_ACCOUNT_FILE): only file exports can be ingested")

    real = [a for a in settings.approvers if not a.endswith(PLACEHOLDER_DOMAINS)]
    if real:
        r.ok(f"approvers: {len(real)} configured")
    else:
        r.warn("CLOE_APPROVERS has no real address: nothing can be approved or sent")

    try:
        persona_tone = persona.load_tone()
        r.ok(f"tone.md version {persona.tone_version(persona_tone)}")
    except (OSError, ValueError) as exc:
        r.fail(f"tone.md: {exc}")

    if not Path(settings.db).exists():
        r.warn(f"database {settings.db} not created yet: run `cloe init`")
    else:
        try:
            conn = db.connect(settings.db)
            have, want = db.schema_version(conn), len(db.MIGRATIONS)
            conn.close()
            if have == want:
                r.ok(f"database {settings.db} at schema {have}")
            else:
                r.warn(f"database at schema {have}, code expects {want}: run `cloe init`")
        except sqlite3.Error as exc:
            r.fail(f"database {settings.db}: {exc}")

    try:
        probe = sqlite3.connect(":memory:")
        probe.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        probe.close()
        r.ok(f"sqlite {sqlite3.sqlite_version} with FTS5")
    except sqlite3.Error:
        r.fail("this sqlite has no FTS5 (the research library needs it)")

    for module, extra in OPTIONAL_EXTRAS.items():
        if _installed(module):
            r.ok(f"optional {module} ({extra} extra)")
        else:
            r.warn(f"optional {module} missing: uv sync --extra {extra}")

    if _hooks_path() == ".githooks":
        r.ok("git hooks: .githooks (STATE.md + ruff + pytest on commit)")
    else:
        r.warn("git hooks not enabled: git config core.hooksPath .githooks")

    if settings.send:
        r.warn("CLOE_SEND=1: LIVE — approved messages will really be sent")
    else:
        r.warn("CLOE_SEND=0: dry run — nothing is sent, sends are only logged")

    return 1 if r.failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cloe", description="Cloé — network orchestrator for the TOS13 network period."
    )
    parser.add_argument("--env", default=str(config.DEFAULT_ENV_PATH), help="path to .env")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print the version").set_defaults(func=cmd_version)
    sub.add_parser("init", help="create or migrate the database").set_defaults(func=cmd_init)
    sub.add_parser("doctor", help="check settings, database, extras").set_defaults(
        func=cmd_doctor
    )
    for name in COMMAND_MODULES:
        importlib.import_module(name).register(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = config.load(args.env)
    except ValueError as exc:
        print(f"FAIL settings: {exc}", file=sys.stderr)
        return 2
    return args.func(args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
