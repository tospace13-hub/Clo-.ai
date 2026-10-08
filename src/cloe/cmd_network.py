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


# -- profiles and the network ----------------------------------------------------------


def cmd_profile(args: argparse.Namespace, settings: config.Settings) -> int:
    from cloe import profile, records

    conn = open_db(settings)
    matches = records.lookup_company(conn, args.company)
    if not matches:
        conn.close()
        return _err(f"no company matches {args.company!r} (try `cloe companies list`)")
    if len(matches) > 1:
        print(f"WARN {len(matches)} companies match; name one by id or domain:")
        for c in matches:
            print(f"     #{c['id']}  {c['name']}  {c['domain'] or '-'}  {c['city'] or '-'}")
        conn.close()
        return 1
    company = matches[0]
    print(profile.render(conn, company["id"]), end="")
    if not args.no_write:
        path = profile.write(conn, company["id"], data_dir(settings) / "profiles")
        print(f"\n(saved to {path})", file=sys.stderr)
    conn.close()
    return 0


def cmd_companies_list(args: argparse.Namespace, settings: config.Settings) -> int:
    conn = open_db(settings)
    where, params = [], []
    if args.tier:
        where.append("c.tier LIKE ?")
        params.append(f"%{args.tier}%")
    if args.city:
        where.append("c.city = ? COLLATE NOCASE")
        params.append(args.city)
    if args.needs:
        kind_sql = "" if args.needs == "any" else " AND n.kind = ?"
        where.append(f"EXISTS (SELECT 1 FROM need n WHERE n.company_id = c.id "
                     f"AND n.status != 'flagged'{kind_sql})")
        if args.needs != "any":
            params.append(args.needs)
    sql = (
        "SELECT c.id, c.name, c.domain, c.city, c.tier, "
        "(SELECT count(*) FROM person p WHERE p.company_id = c.id) AS people, "
        "(SELECT count(*) FROM need n WHERE n.company_id = c.id AND n.status != 'flagged') "
        "AS needs FROM company c"
        + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY c.name"
    )
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    for r in rows:
        print(f"#{r['id']:<5} {r['name'][:34]:<34} {(r['domain'] or '-')[:26]:<26} "
              f"{(r['city'] or '-')[:14]:<14} people {r['people']:<3} needs {r['needs']:<3} "
              f"{(r['tier'] or '-')[:40]}")
    print(f"{len(rows)} compan{'y' if len(rows) == 1 else 'ies'}")
    return 0


# -- people and privacy -----------------------------------------------------------------


def cmd_consent_set(args: argparse.Namespace, settings: config.Settings) -> int:
    from cloe import people

    email = people.normalise_email(args.email)
    if not email:
        return _err("not a valid email address")
    if not args.evidence.strip():
        return _err("--evidence is required: say how and when they agreed")
    conn = open_db(settings)
    person = people.get_person(conn, email)
    if person is None:
        reason = "was forgotten" if people.is_forgotten(conn, email) else "is not known"
        conn.close()
        return _err(f"this person {reason}; ingest them first")
    people.set_consent(conn, person["id"], args.channel, args.purpose, args.status,
                       source="manual", evidence=args.evidence)
    conn.commit()
    db.event(conn, "cli", "consent_set", ref=f"person:{person['id']}",
             detail={"channel": args.channel, "purpose": args.purpose, "status": args.status})
    print(f"OK   {args.channel}/{args.purpose} = {args.status} for person #{person['id']}")
    if args.channel == "sms" and args.status == "yes" and not person["phone"]:
        print("WARN no phone number on record: SMS still cannot be sent")
    conn.close()
    return 0


def cmd_forget(args: argparse.Namespace, settings: config.Settings) -> int:
    from cloe import people

    conn = open_db(settings)
    try:
        counts = people.forget(conn, args.email, profiles_dir=data_dir(settings) / "profiles")
    except ValueError as exc:
        conn.close()
        return _err(str(exc))
    conn.close()
    if counts["person"] == 0 and counts["sources"] == 0:
        print("OK   not found; added to the suppression list so no import brings them in")
    else:
        print("OK   forgotten: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    return 0


def cmd_export(args: argparse.Namespace, settings: config.Settings) -> int:
    import json

    from cloe import people

    conn = open_db(settings)
    data = people.export(conn, args.email)
    if data is not None:
        db.event(conn, "cli", "export", ref=f"person:{data['person']['id']}")
    conn.close()
    if data is None:
        return _err("not found")
    text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    if args.out:
        out = Path(args.out)
        out.write_text(text + "\n", encoding="utf-8")
        out.chmod(0o600)
        print(f"OK   written to {out}")
    else:
        print(text)
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

    p = sub.add_parser("profile", help="print and save a company profile")
    p.add_argument("company", help="id, domain, website or name")
    p.add_argument("--no-write", action="store_true", help="print only")
    p.set_defaults(func=cmd_profile)

    companies = sub.add_parser("companies", help="list companies").add_subparsers(
        dest="action", required=True
    )
    p = companies.add_parser("list", help="list companies, optionally filtered")
    p.add_argument("--tier", help="tier contains this text")
    p.add_argument("--city")
    p.add_argument("--needs", nargs="?", const="any", metavar="KIND",
                   help="only companies with open needs (of this kind)")
    p.set_defaults(func=cmd_companies_list)

    from cloe import people

    consent = sub.add_parser("consent", help="the consent ledger").add_subparsers(
        dest="action", required=True
    )
    p = consent.add_parser("set", help="record consent Chloe obtained")
    p.add_argument("email")
    p.add_argument("channel", choices=people.CHANNELS)
    p.add_argument("purpose", choices=people.PURPOSES)
    p.add_argument("status", choices=("yes", "no"))
    p.add_argument("--evidence", required=True, help="how and when they agreed")
    p.set_defaults(func=cmd_consent_set)

    p = sub.add_parser("forget", help="erase a person and keep them out of future imports")
    p.add_argument("email")
    p.set_defaults(func=cmd_forget)

    p = sub.add_parser("export", help="everything Cloé holds about a person, as JSON")
    p.add_argument("email")
    p.add_argument("--out", help="write to this file instead of printing")
    p.set_defaults(func=cmd_export)
