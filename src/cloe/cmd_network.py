"""`cloe ingest …`, `cloe profile`, `cloe consent set`, `cloe forget`, `cloe export`,
`cloe companies list` — the Sprint 1 commands."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from cloe import config, db, llm


def open_db(settings: config.Settings) -> sqlite3.Connection:
    conn = db.connect(settings.db)
    db.migrate(conn)
    return conn


def data_dir(settings: config.Settings) -> Path:
    return Path(settings.db).parent


def make_claude(settings: config.Settings, conn: sqlite3.Connection, no_llm: bool):
    """The API engine when a key is set; None means 'leave model work for later'."""
    if no_llm or not settings.anthropic_api_key:
        return None
    return llm.Claude(settings, conn)


def _err(msg: str) -> int:
    print(f"FAIL {msg}", file=sys.stderr)
    return 1


# -- ingest -----------------------------------------------------------------------------


def cmd_ingest_joinform(args: argparse.Namespace, settings: config.Settings) -> int:
    from cloe.sources import joinform, sheets

    try:
        if args.file:
            tabs = joinform.read_file(Path(args.file))
            origin = Path(args.file).name
        elif settings.joinform_sheet_id:
            sess = sheets.session(settings.google_service_account_file)
            tabs = joinform.read_sheet(sess, settings.joinform_sheet_id)
            origin = "Google Sheet (CLOE_JOINFORM_SHEET_ID)"
        else:
            return _err("give a CSV/XLSX export, or set CLOE_JOINFORM_SHEET_ID and "
                        "GOOGLE_SERVICE_ACCOUNT_FILE to read the sheet")
    except (OSError, ValueError, sheets.SheetsError) as exc:
        return _err(f"join form: {exc}")
    conn = open_db(settings)
    claude = make_claude(settings, conn, args.no_llm)
    report = joinform.ingest(conn, tabs, raw_dir=data_dir(settings) / "raw", claude=claude,
                             canary=settings.canary)
    conn.close()
    print(f"OK   join form from {origin}")
    for line in report.lines():
        print(f"     {line}")
    if report.unclassified and claude is None:
        print("WARN needs left unclassified: no ANTHROPIC_API_KEY (or --no-llm); "
              "re-run the ingest with a key to classify them")
    return 0


def cmd_ingest_tell(args: argparse.Namespace, settings: config.Settings) -> int:
    import json

    from cloe import records
    from cloe.sources import tell

    unknown: list[str] = []
    try:
        if args.db:
            if not settings.tell_db_url:
                return _err("--db needs TELL_DB_URL (and TELL_DB_CA_CERT) in .env")
            recs = tell.load_db(settings.tell_db_url, settings.tell_db_ca_cert)
            origin = "db"
            digest = records.sha256(json.dumps(recs, sort_keys=True))
        elif args.file:
            path = Path(args.file)
            recs, unknown = tell.read_export(path)
            origin, digest = path.name, records.sha256(path.read_bytes())
        else:
            return _err("give the TELL dashboard export (.xlsx), or --db")
    except (OSError, ValueError) as exc:
        return _err(f"TELL: {exc}")
    conn = open_db(settings)
    report = tell.ingest(conn, recs, origin=origin, digest=digest, unknown_columns=unknown)
    conn.close()
    print(f"OK   TELL from {origin}")
    for line in report.lines():
        print(f"     {line}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    ingest = sub.add_parser("ingest", help="import outside data").add_subparsers(
        dest="source", required=True
    )
    p = ingest.add_parser(
        "joinform", help="join form: the Google Sheet, or a CSV/XLSX export of it"
    )
    p.add_argument("file", nargs="?", help="CSV/XLSX export; omit to read the Google Sheet")
    p.add_argument("--no-llm", action="store_true", help="don't classify needs now")
    p.set_defaults(func=cmd_ingest_joinform)
    p = ingest.add_parser("tell", help="TELL: the dashboard's xlsx export, or --db (read-only)")
    p.add_argument("file", nargs="?", help="companies.xlsx from the TELL dashboard export")
    p.add_argument("--db", action="store_true", help="read TELL_DB_URL instead of a file")
    p.set_defaults(func=cmd_ingest_tell)
