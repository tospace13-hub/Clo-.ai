"""SQLite store: schema as numbered migrations, a connection helper, and the audit log.

`PRAGMA user_version` records how many migrations have run, so `migrate()` is idempotent.
Never edit a migration that has shipped; append a new one.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MIGRATIONS: list[str] = [
    # 1 — the Sprint 0 schema (sprint.md → Architecture → Data model).
    """
    CREATE TABLE company (
        id          INTEGER PRIMARY KEY,
        name        TEXT NOT NULL,
        domain      TEXT UNIQUE,
        website     TEXT,
        city        TEXT,
        postcode    TEXT,
        kvk         TEXT,
        tier        TEXT,
        category    TEXT,
        employees   TEXT,
        year_start  INTEGER,
        tell_id     TEXT,
        lang        TEXT,
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    );
    CREATE TABLE person (
        id          INTEGER PRIMARY KEY,
        company_id  INTEGER REFERENCES company(id) ON DELETE SET NULL,
        name        TEXT,
        email       TEXT UNIQUE COLLATE NOCASE,
        phone       TEXT,
        role        TEXT,
        lang        TEXT,
        created_at  TEXT NOT NULL
    );
    CREATE INDEX person_company ON person(company_id);
    CREATE TABLE consent (
        id          INTEGER PRIMARY KEY,
        person_id   INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
        channel     TEXT NOT NULL CHECK (channel IN ('email', 'sms')),
        purpose     TEXT NOT NULL CHECK (purpose IN ('followup', 'newsletter', 'cloe_updates')),
        status      TEXT NOT NULL CHECK (status IN ('yes', 'no', 'unknown')),
        source      TEXT,
        evidence    TEXT,
        at          TEXT NOT NULL
    );
    CREATE INDEX consent_lookup ON consent(person_id, channel, purpose, at);
    CREATE TABLE source (
        id          INTEGER PRIMARY KEY,
        url         TEXT,
        kind        TEXT NOT NULL CHECK (kind IN ('joinform', 'tell', 'web', 'pdf', 'cordis',
                                                  'workorder', 'inbound', 'manual')),
        fetched_at  TEXT NOT NULL,
        sha256      TEXT,
        raw_path    TEXT
    );
    CREATE INDEX source_sha ON source(sha256);
    CREATE TABLE fact (
        id          INTEGER PRIMARY KEY,
        company_id  INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
        kind        TEXT NOT NULL CHECK (kind IN ('does', 'makes', 'needs', 'has_data', 'project',
                                                  'event', 'contact', 'other')),
        text        TEXT NOT NULL,
        confidence  REAL NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
        source_id   INTEGER REFERENCES source(id) ON DELETE SET NULL,
        observed_at TEXT NOT NULL,
        expires_at  TEXT,
        flags       TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX fact_company ON fact(company_id, kind);
    CREATE TABLE project (
        id               INTEGER PRIMARY KEY,
        acronym          TEXT,
        title            TEXT NOT NULL,
        programme        TEXT,
        cordis_id        TEXT UNIQUE,
        url              TEXT,
        start_date       TEXT,
        end_date         TEXT,
        partners_nl_json TEXT NOT NULL DEFAULT '[]'
    );
    CREATE TABLE document (
        id           INTEGER PRIMARY KEY,
        source_id    INTEGER REFERENCES source(id) ON DELETE SET NULL,
        project_id   INTEGER REFERENCES project(id) ON DELETE SET NULL,
        title        TEXT NOT NULL,
        summary      TEXT,
        tags_json    TEXT NOT NULL DEFAULT '[]',
        lang         TEXT,
        published_at TEXT,
        body_path    TEXT
    );
    CREATE VIRTUAL TABLE document_fts USING fts5(
        title, summary, tags, body, tokenize = 'unicode61 remove_diacritics 2'
    );
    CREATE TABLE need (
        id          INTEGER PRIMARY KEY,
        company_id  INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
        text        TEXT NOT NULL,
        kind        TEXT,
        status      TEXT NOT NULL DEFAULT 'open',
        source_id   INTEGER REFERENCES source(id) ON DELETE SET NULL
    );
    CREATE TABLE match (
        id               INTEGER PRIMARY KEY,
        company_id       INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
        document_id      INTEGER REFERENCES document(id) ON DELETE CASCADE,
        other_company_id INTEGER REFERENCES company(id) ON DELETE CASCADE,
        score            REAL NOT NULL,
        rationale        TEXT NOT NULL,
        status           TEXT NOT NULL DEFAULT 'proposed'
                         CHECK (status IN ('proposed', 'approved', 'rejected', 'used')),
        created_at       TEXT NOT NULL
    );
    CREATE TABLE message (
        id              INTEGER PRIMARY KEY,
        person_id       INTEGER REFERENCES person(id) ON DELETE SET NULL,
        channel         TEXT NOT NULL CHECK (channel IN ('email', 'sms')),
        direction       TEXT NOT NULL CHECK (direction IN ('out', 'in')),
        thread_id       TEXT,
        subject         TEXT,
        body            TEXT NOT NULL,
        lang            TEXT,
        status          TEXT NOT NULL CHECK (status IN ('draft', 'blocked', 'approved', 'sent',
                                                        'failed', 'received')),
        tone_version    TEXT,
        tone_score      REAL,
        approved_by     TEXT,
        approved_at     TEXT,
        sent_at         TEXT,
        provider_id     TEXT,
        content_sha256  TEXT,
        match_ids_json  TEXT NOT NULL DEFAULT '[]',
        flags           TEXT NOT NULL DEFAULT '',
        created_at      TEXT NOT NULL
    );
    CREATE INDEX message_person ON message(person_id, direction, sent_at);
    CREATE TABLE work_order (
        id          INTEGER PRIMARY KEY,
        kind        TEXT NOT NULL,
        status      TEXT NOT NULL DEFAULT 'open',
        path        TEXT NOT NULL,
        result_path TEXT,
        created_at  TEXT NOT NULL,
        ingested_at TEXT
    );
    CREATE TABLE event (
        id      INTEGER PRIMARY KEY,
        at      TEXT NOT NULL,
        actor   TEXT NOT NULL,
        action  TEXT NOT NULL,
        ref     TEXT NOT NULL DEFAULT '',
        detail  TEXT NOT NULL DEFAULT '{}'
    );
    CREATE INDEX event_action ON event(action, at);
    """,
    # 2 — Sprint 1: TELL's company class for the profile header; the name+city identity key
    # (records.identity_key) so matching is an index lookup; the suppression list that keeps
    # `cloe forget` from being undone by the next import (sha256 of the email only).
    """
    ALTER TABLE company ADD COLUMN company_class TEXT;
    ALTER TABLE company ADD COLUMN identity_key TEXT;
    CREATE INDEX company_identity ON company(identity_key);
    CREATE TABLE forgotten (
        email_sha256 TEXT PRIMARY KEY,
        at           TEXT NOT NULL
    );
    """,
]

# Events carry ids and hashes, never bodies (sprint.md → Security → principle 11).
MAX_EVENT_VALUE_CHARS = 200


def now() -> str:
    """UTC timestamp, ISO 8601, second precision."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def connect(path: Path | str) -> sqlite3.Connection:
    """Open the database (creating its folder), with foreign keys on and Row results."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations. Returns how many ran (0 when already current)."""
    current = schema_version(conn)
    pending = MIGRATIONS[current:]
    for number, sql in enumerate(pending, start=current + 1):
        try:
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
        except sqlite3.Error:
            if conn.in_transaction:
                conn.rollback()
            raise
    return len(pending)


def event(
    conn: sqlite3.Connection,
    actor: str,
    action: str,
    ref: str = "",
    detail: dict[str, Any] | None = None,
) -> int:
    """Append to the audit log. `detail` holds ids, hashes, counts and short codes only."""
    detail = detail or {}
    for key, value in detail.items():
        if isinstance(value, str) and len(value) > MAX_EVENT_VALUE_CHARS:
            raise ValueError(f"event detail {key!r} is too long; log an id or hash, not text")
    cur = conn.execute(
        "INSERT INTO event(at, actor, action, ref, detail) VALUES (?, ?, ?, ?, ?)",
        (now(), actor, action, ref, json.dumps(detail, sort_keys=True, ensure_ascii=False)),
    )
    conn.commit()
    return cur.lastrowid
