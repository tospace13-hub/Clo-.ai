"""TELL (tell.newtexeco.nl) → companies, facts and contact people without consent.

Reads the dashboard's xlsx export (columns: docs/CONTEXT.md §D) or, with `--db`, the TELL
MySQL database read-only. Read only: Cloé never writes to TELL.

TELL is the second source, after the companies themselves: it only fills empty company
fields and never changes a person who is already known. Keywords are scraped text, stored
flagged `scraped`. Email contacts become people with **no consent**: Cloé may not write to
them until Chloe records consent (`cloe consent set`).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from cloe import db, people, records

EXPORT_COLUMNS = (
    "Company", "City", "Region", "Website", "Employees", "Surface (m2)", "Founded",
    "Legal form", "Status", "Product category", "Supply chain tier", "Company class",
    "Email contacts", "Keywords",
)
NAME_FIELDS = ("name", "website", "city", "employees", "year_start", "tier", "category",
               "company_class")
KEYWORDS_PER_FACT = 20
MAX_FILE_BYTES = 50 * 1024 * 1024
CONFIDENCE = 0.6  # a 2021 KvK-based dataset
KEYWORD_CONFIDENCE = 0.4  # scraped from the company's website

# Columns named like the export. Written from the table list in CONTEXT §D: check it
# against TELL's own `query_org` before first use (open question in STATE.md).
DB_QUERY = """
SELECT o.id AS tell_id, o.trade_name AS `Company`, o.city AS `City`, o.website AS `Website`,
       o.employees AS `Employees`, o.year_start AS `Founded`,
       t.category AS `Product category`, t.tier AS `Supply chain tier`,
       cc.company_class AS `Company class`, s.`Website emails` AS `Email contacts`,
       ts.tags_new AS `Keywords`
FROM organizations o
LEFT JOIN tags t ON t.id = o.id
LEFT JOIN company_class cc ON cc.id = o.id
LEFT JOIN tags_scraped ts ON ts.id = o.id
LEFT JOIN scraping17092026 s ON s.website = o.website
"""


@dataclass
class Report:
    rows: int = 0
    skipped: int = 0
    companies_created: int = 0
    companies_matched: int = 0
    people_created: int = 0
    emails_invalid: int = 0
    emails_forgotten: int = 0
    facts: int = 0
    flagged_facts: int = 0
    unknown_columns: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = [
            (f"rows {self.rows} ({self.skipped} without a company name): companies "
             f"+{self.companies_created} new, {self.companies_matched} matched to known ones"),
            (f"contact people +{self.people_created} (no consent; Chloe adds it with "
             f"`cloe consent set`) · emails skipped: {self.emails_invalid} invalid, "
             f"{self.emails_forgotten} forgotten"),
            (f"facts +{self.facts} · flagged as instruction-like (whole database): "
             f"{self.flagged_facts}"),
        ]
        if self.unknown_columns:
            out.append("columns not in CONTEXT §D (ignored): " + ", ".join(self.unknown_columns))
        return out


# -- reading ----------------------------------------------------------------------------


def _key(header: object) -> str:
    return " ".join(str(header or "").split()).lower()


_KNOWN = {_key(c): c for c in EXPORT_COLUMNS}


def _text(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def to_records(rows: list[list[Any]]) -> tuple[list[dict[str, str]], list[str]]:
    rows = [r for r in rows if any(_text(c) for c in r)]
    if not rows:
        return [], []
    head = [_key(c) for c in rows[0]]
    if "company" not in head:
        raise ValueError("not a TELL export: no 'Company' column in the first row")
    unknown = [str(rows[0][i]) for i, h in enumerate(head) if h and h not in _KNOWN]
    out = []
    for row in rows[1:]:
        rec = dict.fromkeys(EXPORT_COLUMNS, "")
        for i, h in enumerate(head):
            if h in _KNOWN and i < len(row):
                rec[_KNOWN[h]] = _text(row[i])
        out.append(rec)
    return out, unknown


def read_export(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"{path.name} is larger than {MAX_FILE_BYTES // 2**20} MB")
    try:
        import openpyxl
    except ImportError as exc:
        raise ValueError("reading the TELL export needs: uv sync --extra tell") from exc
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return to_records([list(r) for r in wb.worksheets[0].iter_rows(values_only=True)])
    finally:
        wb.close()


def connect_db(url: str, ca_cert: str):
    """Read-only connection from `TELL_DB_URL` (`mysql+pymysql://user:pass@host:port/db`)."""
    import pymysql
    import pymysql.cursors

    parts = urlsplit(url)
    if not parts.scheme.startswith("mysql") or not parts.hostname:
        raise ValueError("TELL_DB_URL must look like mysql+pymysql://user:pass@host:port/db")
    if not ca_cert:
        raise ValueError("TELL_DB_CA_CERT is required: the TELL database only accepts SSL")
    conn = pymysql.connect(
        host=parts.hostname, port=parts.port or 25060, user=unquote(parts.username or ""),
        password=unquote(parts.password or ""), database=parts.path.lstrip("/"),
        ssl={"ca": ca_cert}, connect_timeout=15, read_timeout=120,
        cursorclass=pymysql.cursors.DictCursor, charset="utf8mb4",
    )
    with conn.cursor() as cur:
        cur.execute("SET SESSION TRANSACTION READ ONLY")
    return conn


def read_db(mysql) -> list[dict[str, str]]:
    with mysql.cursor() as cur:
        cur.execute(DB_QUERY)
        rows = cur.fetchall()
    return [{**dict.fromkeys(EXPORT_COLUMNS, ""), **{k: _text(v) for k, v in r.items()}}
            for r in rows]


def load_db(url: str, ca_cert: str) -> list[dict[str, str]]:
    """Connect, read, close. Database errors become ValueError naming only the error type
    (their messages can carry the host)."""
    try:
        import pymysql
    except ImportError as exc:
        raise ValueError("TELL database access needs: uv sync --extra tell") from exc
    try:
        mysql = connect_db(url, ca_cert)
        try:
            return read_db(mysql)
        finally:
            mysql.close()
    except pymysql.MySQLError as exc:
        raise ValueError(f"database error {type(exc).__name__}") from None


# -- writing ----------------------------------------------------------------------------


def _keywords(value: str) -> list[str]:
    seen: dict[str, None] = {}
    for kw in re.split(r"[;,\n]", value):
        kw = " ".join(kw.split())
        if kw:
            seen.setdefault(kw, None)
    return list(seen)


def _row(conn, rec: dict[str, str], sid: int, report: Report) -> None:
    values = {
        "name": rec["Company"], "website": rec["Website"], "city": rec["City"],
        "employees": rec["Employees"], "year_start": rec["Founded"],
        "tier": rec["Supply chain tier"], "category": rec["Product category"],
        "company_class": rec["Company class"],
    }
    moved = records.quarantine(values, NAME_FIELDS, "TELL")
    if not values["name"]:
        report.skipped += 1
        return
    ident = records.identity_key(values["name"], values["city"])
    values["tell_id"] = rec.get("tell_id") or f"export:{ident}"
    cid, created = records.upsert_company(conn, values)
    report.companies_created += created
    report.companies_matched += not created

    facts = [
        ("does", f"Product category: {values['category']}" if values["category"] else "",
         CONFIDENCE, ()),
        ("does", f"Supply-chain tier: {values['tier']}" if values["tier"] else "", CONFIDENCE, ()),
        ("does", f"Company class: {values['company_class']}" if values["company_class"] else "",
         CONFIDENCE, ()),
    ]
    kws = _keywords(rec["Keywords"])
    for i in range(0, len(kws), KEYWORDS_PER_FACT):
        chunk = ", ".join(kws[i:i + KEYWORDS_PER_FACT])
        facts.append(("does", f"Keywords (TELL, scraped): {chunk}", KEYWORD_CONFIDENCE,
                      (records.SCRAPED,)))
    facts += [("other", text, 0.1, (records.INSTRUCTION_LIKE,)) for text in moved]
    for kind, text, confidence, flags in facts:
        if text and records.add_fact(conn, cid, kind, text, source_id=sid,
                                     confidence=confidence, flags=flags):
            report.facts += 1

    for raw in re.split(r"[;,\s]+", rec["Email contacts"]):
        if not raw:
            continue
        email = people.normalise_email(raw)
        if not email:
            report.emails_invalid += 1
        elif people.is_forgotten(conn, email) and people.get_person(conn, email) is None:
            report.emails_forgotten += 1
        else:
            _, created = people.upsert_person(conn, email, company_id=cid)
            report.people_created += created


def ingest(
    conn: sqlite3.Connection, recs: list[dict[str, str]], *, origin: str, digest: str,
    unknown_columns: list[str] | None = None,
) -> Report:
    """`origin` names the export file or the database; `digest` fingerprints the content.
    No raw copy is kept: the export holds the whole network's contact data."""
    report = Report(unknown_columns=list(unknown_columns or []))
    sid, _ = records.upsert_source(conn, "tell", f"tell:{origin}#{digest[:16]}", digest=digest)
    for rec in recs:
        report.rows += 1
        _row(conn, rec, sid, report)
    conn.commit()
    report.flagged_facts = conn.execute(
        "SELECT count(*) FROM fact WHERE ',' || flags || ',' LIKE '%,instruction_like,%'"
    ).fetchone()[0]
    db.event(conn, "tell", "ingest", ref=f"source:{sid}", detail={
        "rows": report.rows, "created": report.companies_created,
        "matched": report.companies_matched, "people": report.people_created,
        "facts": report.facts,
    })
    return report
