"""People, the consent ledger, and the two privacy commands (`forget`, `export`).

Consent is a ledger: rows are dated by when the person acted (the form's `submitted_at`,
the unsubscribe time, or now for `cloe consent set`) and the latest row wins, so
re-importing an old row can never undo a later "no". No row means "unknown".
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cloe import db, records

CHANNELS = ("email", "sms")
PURPOSES = ("followup", "newsletter", "cloe_updates")
STATUSES = ("yes", "no", "unknown")

_EMAIL = re.compile(r"[^@\s<>()\[\],;:\"']+@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}")


def normalise_email(value: object) -> str | None:
    e = records.clean(value, 320).lower().removeprefix("mailto:")
    return e if _EMAIL.fullmatch(e) else None


def email_sha256(email: str) -> str:
    return records.sha256(email.strip().lower())


def parse_time(value: object) -> str | None:
    """An ISO 8601 timestamp (as the join form writes it) → UTC, `db.now()` format."""
    text = records.clean(value, 64)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace(" ", "T", 1))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).replace(microsecond=0).isoformat()


def is_forgotten(conn: sqlite3.Connection, email: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM forgotten WHERE email_sha256 = ?", (email_sha256(email),)
    ).fetchone()
    return row is not None


def get_person(conn: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM person WHERE email = ?", (email,)).fetchone()


def upsert_person(
    conn: sqlite3.Connection,
    email: str,
    *,
    name: str | None = None,
    role: str | None = None,
    company_id: int | None = None,
    overwrite: bool = False,
) -> tuple[int, bool]:
    """`email` must already be normalised and not forgotten. `overwrite=True` (join form:
    the person told us) replaces name/role/company; otherwise only empty fields are filled.
    Returns (person_id, created)."""
    vals = {"name": records.clean(name, 200) or None, "role": records.clean(role, 200) or None,
            "company_id": company_id}
    row = get_person(conn, email)
    if row is None:
        cur = conn.execute(
            "INSERT INTO person(company_id, name, email, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (vals["company_id"], vals["name"], email, vals["role"], db.now()),
        )
        return cur.lastrowid, True
    updates = {
        k: v for k, v in vals.items()
        if v is not None and (overwrite or row[k] is None) and row[k] != v
    }
    if updates:
        sets = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE person SET {sets} WHERE id = ?", (*updates.values(), row["id"]))
    return row["id"], False


def current_consent(conn: sqlite3.Connection, person_id: int, channel: str, purpose: str) -> str:
    row = conn.execute(
        "SELECT status FROM consent WHERE person_id = ? AND channel = ? AND purpose = ? "
        "ORDER BY at DESC, id DESC LIMIT 1",
        (person_id, channel, purpose),
    ).fetchone()
    return row["status"] if row else "unknown"


def set_consent(
    conn: sqlite3.Connection,
    person_id: int,
    channel: str,
    purpose: str,
    status: str,
    *,
    source: str,
    evidence: str,
    at: str | None = None,
) -> bool:
    """Append a ledger row dated `at` (default now). Skipped when the latest row with the
    same date already says the same. Returns True when a row was written."""
    if channel not in CHANNELS or purpose not in PURPOSES or status not in STATUSES:
        raise ValueError(f"bad consent {channel}/{purpose}/{status}")
    at = at or db.now()
    same_time = conn.execute(
        "SELECT status FROM consent WHERE person_id = ? AND channel = ? AND purpose = ? "
        "AND at = ? ORDER BY id DESC LIMIT 1",
        (person_id, channel, purpose, at),
    ).fetchone()
    if same_time and same_time["status"] == status:
        return False
    conn.execute(
        "INSERT INTO consent(person_id, channel, purpose, status, source, evidence, at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (person_id, channel, purpose, status, source, records.clean(evidence, 300), at),
    )
    return True


def consents(conn: sqlite3.Connection, person_id: int) -> dict[str, str]:
    """{"email/followup": "yes", …} for every channel and purpose."""
    return {
        f"{c}/{p}": current_consent(conn, person_id, c, p) for c in CHANNELS for p in PURPOSES
    }


# -- privacy ----------------------------------------------------------------------------


def _person_sources(conn: sqlite3.Connection, email: str) -> list[sqlite3.Row]:
    """Join-form sources submitted by this person (their url ends in the email's hash)."""
    return conn.execute(
        "SELECT * FROM source WHERE kind = 'joinform' AND url LIKE ? ORDER BY id",
        (f"%:{email_sha256(email)}",),
    ).fetchall()


def _ids(rows: list[sqlite3.Row]) -> tuple[str, list[int]]:
    ids = [r["id"] for r in rows]
    return ",".join("?" * len(ids)), ids


def forget(
    conn: sqlite3.Connection, email: str, *, profiles_dir: Path | None = None
) -> dict[str, int]:
    """Erase a person: their row and consents, their join-form submissions (source rows,
    raw copies, and the facts and needs taken from them), their messages, companies left
    with nothing but what they told us, and cached profiles that showed them. The email's
    hash goes on the suppression list so no import brings them back."""
    norm = normalise_email(email)
    if not norm:
        raise ValueError("not a valid email address")
    counts = dict.fromkeys(
        ("person", "consents", "sources", "facts", "needs", "messages", "companies",
         "profiles"), 0,
    )
    person = get_person(conn, norm)
    sources = _person_sources(conn, norm)
    companies: set[int] = set()
    marks, src_ids = _ids(sources)
    with conn:
        if src_ids:
            for table in ("fact", "need"):
                rows = conn.execute(
                    f"SELECT DISTINCT company_id FROM {table} WHERE source_id IN ({marks})",
                    src_ids,
                ).fetchall()
                companies.update(r["company_id"] for r in rows)
                cur = conn.execute(f"DELETE FROM {table} WHERE source_id IN ({marks})", src_ids)
                counts["facts" if table == "fact" else "needs"] = cur.rowcount
            conn.execute(f"DELETE FROM source WHERE id IN ({marks})", src_ids)
            counts["sources"] = len(src_ids)
            for s in sources:
                records.remove_raw(conn, s["raw_path"])
        if person is not None:
            if person["company_id"]:
                companies.add(person["company_id"])
            counts["consents"] = conn.execute(
                "SELECT count(*) FROM consent WHERE person_id = ?", (person["id"],)
            ).fetchone()[0]
            counts["messages"] = conn.execute(
                "DELETE FROM message WHERE person_id = ?", (person["id"],)
            ).rowcount
            conn.execute("DELETE FROM person WHERE id = ?", (person["id"],))
            counts["person"] = 1
        for cid in sorted(companies):
            company = conn.execute("SELECT * FROM company WHERE id = ?", (cid,)).fetchone()
            if company is None:
                continue
            if profiles_dir is not None:
                path = profiles_dir / records.profile_filename(company)
                if path.exists():
                    path.unlink()
                    counts["profiles"] += 1
            if company["tell_id"] is None and not _company_has_records(conn, cid):
                conn.execute("DELETE FROM company WHERE id = ?", (cid,))
                counts["companies"] += 1
        conn.execute(
            "INSERT OR IGNORE INTO forgotten(email_sha256, at) VALUES (?, ?)",
            (email_sha256(norm), db.now()),
        )
    ref = f"person:{person['id']}" if person is not None else ""
    db.event(conn, "cli", "forget", ref=ref, detail=counts)
    return counts


def _company_has_records(conn: sqlite3.Connection, cid: int) -> bool:
    for sql in (
        "SELECT 1 FROM person WHERE company_id = ?",
        "SELECT 1 FROM fact WHERE company_id = ?",
        "SELECT 1 FROM need WHERE company_id = ?",
        "SELECT 1 FROM match WHERE company_id = ? OR other_company_id = ?",
    ):
        args = (cid, cid) if sql.count("?") == 2 else (cid,)
        if conn.execute(sql, args).fetchone():
            return True
    return False


def _raw_text(path: str | None) -> Any:
    if not path or not Path(path).exists():
        return None
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    try:
        return json.loads(text)
    except ValueError:
        return text


def export(conn: sqlite3.Connection, email: str) -> dict[str, Any] | None:
    """Everything Cloé holds about one person, as plain JSON-able data. None if unknown."""
    norm = normalise_email(email)
    person = get_person(conn, norm) if norm else None
    if person is None:
        return None
    pid = person["id"]
    sources = _person_sources(conn, norm)
    marks, src_ids = _ids(sources)

    def rows(sql: str, args: tuple | list) -> list[dict[str, Any]]:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]

    company = conn.execute(
        "SELECT id, name, domain, website, city FROM company WHERE id = ?", (person["company_id"],)
    ).fetchone()
    by_source = bool(src_ids)
    return {
        "exported_at": db.now(),
        "person": dict(person),
        "company": dict(company) if company else None,
        "consent_now": consents(conn, pid),
        "consent_ledger": rows("SELECT * FROM consent WHERE person_id = ? ORDER BY at, id", (pid,)),
        "submissions": [{**dict(s), "raw": _raw_text(s["raw_path"])} for s in sources],
        "facts_from_submissions": rows(
            f"SELECT * FROM fact WHERE source_id IN ({marks}) ORDER BY id", src_ids
        ) if by_source else [],
        "needs_from_submissions": rows(
            f"SELECT * FROM need WHERE source_id IN ({marks}) ORDER BY id", src_ids
        ) if by_source else [],
        "messages": rows("SELECT * FROM message WHERE person_id = ? ORDER BY id", (pid,)),
        "events": rows("SELECT * FROM event WHERE ref = ? ORDER BY id", (f"person:{pid}",)),
    }
