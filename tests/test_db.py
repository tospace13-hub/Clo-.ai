import json
import sqlite3

import pytest

from cloe import db

TABLES = {
    "company", "person", "consent", "source", "fact", "project", "document", "document_fts",
    "need", "match", "message", "work_order", "event",
}


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "sub" / "cloe.db")
    yield c
    c.close()


def test_migrate_twice_is_idempotent(conn):
    assert db.migrate(conn) == len(db.MIGRATIONS)
    assert db.migrate(conn) == 0
    assert db.schema_version(conn) == len(db.MIGRATIONS)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert TABLES <= names


def test_foreign_keys_and_checks_enforced(conn):
    db.migrate(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO consent(person_id, channel, purpose, status, at) "
            "VALUES (999, 'email', 'followup', 'yes', ?)", (db.now(),)
        )
    t = db.now()
    conn.execute("INSERT INTO person(name, created_at) VALUES ('A', ?)", (t,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO consent(person_id, channel, purpose, status, at) "
            "VALUES (1, 'pigeon', 'followup', 'yes', ?)", (t,)
        )


def test_fts5_search(conn):
    db.migrate(conn)
    conn.execute(
        "INSERT INTO document_fts(rowid, title, summary, tags, body) VALUES (1, ?, ?, ?, ?)",
        ("Recycled polyester", "Fibre-to-fibre recycling pilot", "recycling", "Gerecycleerd"),
    )
    hits = conn.execute(
        "SELECT rowid FROM document_fts WHERE document_fts MATCH 'recycling'"
    ).fetchall()
    assert [h[0] for h in hits] == [1]


def test_event_logs_ids_not_bodies(conn):
    db.migrate(conn)
    eid = db.event(conn, "cli", "init", ref="db", detail={"migrations": 1})
    row = conn.execute("SELECT * FROM event WHERE id = ?", (eid,)).fetchone()
    assert row["actor"] == "cli" and json.loads(row["detail"]) == {"migrations": 1}
    with pytest.raises(ValueError):
        db.event(conn, "cli", "oops", detail={"body": "x" * 500})


def test_failed_migration_rolls_back(conn, monkeypatch):
    monkeypatch.setattr(db, "MIGRATIONS", ["CREATE TABLE ok(x); CREATE TABLE ok(x);"])
    with pytest.raises(sqlite3.OperationalError):
        db.migrate(conn)
    assert db.schema_version(conn) == 0
    assert not conn.in_transaction
    assert conn.execute("SELECT count(*) FROM sqlite_master WHERE name='ok'").fetchone()[0] == 0
