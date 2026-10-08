"""Network records: companies, sources, facts and needs, and the identity rules.

Identity resolution (every importer goes through `upsert_company`):
- **Domain first.** The website's host: lowercase, no scheme, `www.`, port, path or query;
  unicode hosts as punycode. Shared hosts (facebook.com, linktr.ee, gmail.com, …) are not
  a company's domain.
- **Then name + city** (`identity_key`): accents, punctuation and legal-form words (B.V.,
  N.V., v.o.f., …) removed. A name+city match is taken only when the two records do not
  carry different domains: two different domains are two companies.
- People are keyed by lowercased email (`people.py`); forgotten emails are never imported.

Everything here that came from outside is scrubbed and checked with
`untrusted.injection_flags`; hits are kept as data, flagged `instruction_like`, and never
shown as prose.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import unicodedata
from pathlib import Path

from cloe import db
from cloe.untrusted import injection_flags, scrub

INSTRUCTION_LIKE = "instruction_like"
SCRAPED = "scraped"  # third-party scraped text (TELL keywords): wrap before any model reads it

COMPANY_FIELDS = (
    "name", "website", "city", "postcode", "kvk", "tier", "category", "employees",
    "year_start", "tell_id", "company_class",
)

SHARED_HOSTS = frozenset({
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "youtube.com",
    "tiktok.com", "pinterest.com", "google.com", "sites.google.com", "linktr.ee",
    "etsy.com", "gmail.com", "hotmail.com", "outlook.com", "live.nl", "kvk.nl",
})
LEGAL_FORMS = frozenset({
    "bv", "nv", "vof", "cv", "bvba", "eenmanszaak", "ltd", "gmbh", "inc", "llc", "sa", "srl",
})

_DOMAIN = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}")
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://")


def sha256(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def clean(text: object, max_chars: int = 500) -> str:
    """Scrubbed single-line text: what we store from untrusted cells."""
    return " ".join(scrub(str(text or ""), max_chars).split())


# -- identity ---------------------------------------------------------------------------


def normalise_domain(website: str | None) -> str | None:
    """`https://www.Example.nl/en/` → `example.nl`. None when unusable or a shared host."""
    w = clean(website, 300).lower()
    if not w or " " in w:
        return None
    w = _SCHEME.sub("", w)
    w = re.split(r"[/?#]", w, maxsplit=1)[0].rsplit("@", 1)[-1].split(":", 1)[0].strip(".")
    w = w.removeprefix("www.")
    try:
        w = w.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    if not _DOMAIN.fullmatch(w) or w in SHARED_HOSTS:
        return None
    return w


def _ascii_tokens(text: str | None) -> list[str]:
    t = unicodedata.normalize("NFKD", clean(text, 300)).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", t.lower().replace(".", "").replace("'", ""))


def name_key(name: str | None) -> str:
    tokens = _ascii_tokens(name)
    kept = [t for t in tokens if t not in LEGAL_FORMS]
    return " ".join(kept or tokens)


def identity_key(name: str | None, city: str | None) -> str | None:
    key = name_key(name)
    return f"{key}|{' '.join(_ascii_tokens(city))}" if key else None


def find_company(conn: sqlite3.Connection, domain: str | None, ident: str | None) -> int | None:
    if domain:
        row = conn.execute("SELECT id FROM company WHERE domain = ?", (domain,)).fetchone()
        if row:
            return row["id"]
    if ident:
        for row in conn.execute(
            "SELECT id, domain FROM company WHERE identity_key = ? ORDER BY id", (ident,)
        ):
            if not domain or not row["domain"]:
                return row["id"]
    return None


def _year(value: object) -> int | None:
    m = re.search(r"\b(1[89]\d\d|20\d\d)\b", str(value or ""))
    return int(m.group(1)) if m else None


def upsert_company(
    conn: sqlite3.Connection, values: dict[str, object], *, overwrite: bool = False
) -> tuple[int, bool]:
    """Find-or-create by the identity rules. `overwrite=False` only fills empty fields
    (TELL); `True` lets the new values win (the company told us itself: join form).
    Returns (company_id, created)."""
    vals: dict[str, object] = {}
    for key in COMPANY_FIELDS:
        raw = values.get(key)
        value = _year(raw) if key == "year_start" else clean(raw, 300)
        if value not in (None, ""):
            vals[key] = value
    domain = normalise_domain(str(vals.get("website", "")))
    vals["name"] = vals.get("name") or domain or ""
    if not vals["name"]:
        raise ValueError("a company needs a name or a usable website")
    ident = identity_key(str(vals["name"]), str(vals.get("city", "")))
    cid = find_company(conn, domain, ident)
    ts = db.now()
    if cid is None:
        cols = {**vals, "domain": domain, "identity_key": ident, "created_at": ts,
                "updated_at": ts}
        cur = conn.execute(
            f"INSERT INTO company({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            tuple(cols.values()),
        )
        return cur.lastrowid, True
    row = conn.execute("SELECT * FROM company WHERE id = ?", (cid,)).fetchone()
    updates = {k: v for k, v in vals.items() if overwrite or row[k] in (None, "")}
    if domain and not row["domain"]:
        updates["domain"] = domain
    name, city = updates.get("name", row["name"]), updates.get("city", row["city"])
    updates["identity_key"] = identity_key(str(name), str(city or ""))
    updates = {k: v for k, v in updates.items() if row[k] != v}
    if updates:
        sets = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE company SET {sets}, updated_at = ? WHERE id = ?",
            (*updates.values(), ts, cid),
        )
    return cid, False


def lookup_company(conn: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    """Companies matching an id (`12` / `#12`), a domain or website, or a name."""
    q = query.strip()
    if re.fullmatch(r"#?\d+", q):
        return conn.execute("SELECT * FROM company WHERE id = ?", (int(q.lstrip("#")),)).fetchall()
    domain = normalise_domain(q)
    if domain:
        rows = conn.execute("SELECT * FROM company WHERE domain = ?", (domain,)).fetchall()
        if rows:
            return rows
    key = name_key(q)
    if key:
        rows = conn.execute(
            "SELECT * FROM company WHERE identity_key LIKE ? ORDER BY name", (f"{key}|%",)
        ).fetchall()
        if rows:
            return rows
    pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    return conn.execute(
        "SELECT * FROM company WHERE name LIKE ? ESCAPE '\\' ORDER BY name", (pattern,)
    ).fetchall()


def profile_filename(company: sqlite3.Row) -> str:
    """`<domain>.md`, or `company-<id>.md` without a domain. Domains are [a-z0-9.-] only."""
    return f"{company['domain']}.md" if company["domain"] else f"company-{company['id']}.md"


# -- sources ----------------------------------------------------------------------------


def _write_raw(raw_dir: Path, data: bytes) -> tuple[str, str]:
    digest = sha256(data)
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / digest
    if not path.exists():
        path.write_bytes(data)
        path.chmod(0o600)  # join-form rows hold personal data
    return digest, str(path)


def remove_raw(conn: sqlite3.Connection, raw_path: str | None) -> bool:
    """Delete a raw file unless another source row still points at it."""
    if not raw_path:
        return False
    still = conn.execute("SELECT 1 FROM source WHERE raw_path = ?", (raw_path,)).fetchone()
    if still:
        return False
    Path(raw_path).unlink(missing_ok=True)
    return True


def stored_raw(conn: sqlite3.Connection, kind: str, url: str) -> bytes | None:
    """The raw copy kept for a source, if any (to compare a row with its last import)."""
    row = conn.execute(
        "SELECT raw_path FROM source WHERE kind = ? AND url = ?", (kind, url)
    ).fetchone()
    if row is None or not row["raw_path"] or not Path(row["raw_path"]).is_file():
        return None
    return Path(row["raw_path"]).read_bytes()


def upsert_source(
    conn: sqlite3.Connection,
    kind: str,
    url: str,
    *,
    raw: bytes | None = None,
    raw_dir: Path | None = None,
    digest: str | None = None,
) -> tuple[int, bool]:
    """One source per (kind, url). `raw` is stored under `raw_dir/<sha256>`, never executed.
    When the same url comes back with different content the raw copy is replaced.
    Returns (source_id, created)."""
    raw_path = None
    if raw is not None:
        if raw_dir is None:
            raise ValueError("raw_dir is required to store raw content")
        digest, raw_path = _write_raw(raw_dir, raw)
    row = conn.execute(
        "SELECT id, sha256, raw_path FROM source WHERE kind = ? AND url = ?", (kind, url)
    ).fetchone()
    if row is None:
        cur = conn.execute(
            "INSERT INTO source(url, kind, fetched_at, sha256, raw_path) VALUES (?, ?, ?, ?, ?)",
            (url, kind, db.now(), digest, raw_path),
        )
        return cur.lastrowid, True
    if digest and digest != row["sha256"]:
        conn.execute(
            "UPDATE source SET sha256 = ?, raw_path = ?, fetched_at = ? WHERE id = ?",
            (digest, raw_path, db.now(), row["id"]),
        )
        remove_raw(conn, row["raw_path"])
    return row["id"], False


# -- facts and needs --------------------------------------------------------------------


def _flags(text: str, extra: tuple[str, ...] = ()) -> set[str]:
    flags = set(extra)
    if injection_flags(text):
        flags.add(INSTRUCTION_LIKE)
    return flags


def add_fact(
    conn: sqlite3.Connection,
    company_id: int,
    kind: str,
    text: str,
    *,
    source_id: int | None,
    confidence: float,
    flags: tuple[str, ...] = (),
    expires_at: str | None = None,
) -> int | None:
    """Store a fact unless the company already has the same one. Returns the new id."""
    body = clean(text)
    if not body:
        return None
    all_flags = _flags(scrub(str(text)), flags)
    exists = conn.execute(
        "SELECT 1 FROM fact WHERE company_id = ? AND kind = ? AND text = ?",
        (company_id, kind, body),
    ).fetchone()
    if exists:
        return None
    cur = conn.execute(
        "INSERT INTO fact(company_id, kind, text, confidence, source_id, observed_at, "
        "expires_at, flags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (company_id, kind, body, confidence, source_id, db.now(), expires_at,
         ",".join(sorted(all_flags))),
    )
    return cur.lastrowid


def add_need(
    conn: sqlite3.Connection, company_id: int, text: str, *, source_id: int | None
) -> int | None:
    """An open need, unclassified (kind NULL) until `classify`. Instruction-like text is
    stored with status `flagged` so it is never shown as a need."""
    body = clean(text, 1000)
    if not body:
        return None
    exists = conn.execute(
        "SELECT 1 FROM need WHERE company_id = ? AND text = ?", (company_id, body)
    ).fetchone()
    if exists:
        return None
    status = "flagged" if INSTRUCTION_LIKE in _flags(scrub(str(text))) else "open"
    cur = conn.execute(
        "INSERT INTO need(company_id, text, kind, status, source_id) VALUES (?, ?, NULL, ?, ?)",
        (company_id, body, status, source_id),
    )
    return cur.lastrowid


def quarantine(values: dict[str, str], keys: tuple[str, ...], label: str) -> list[str]:
    """Blank instruction-like cells that would become names or header fields (facts and
    needs are flagged instead). Returns their text for flagged facts of kind "other"."""
    moved = []
    for key in keys:
        if values.get(key) and injection_flags(values[key]):
            moved.append(f"{label} field {key}: {values[key]}")
            values[key] = ""
    return moved


def flags_of(row: sqlite3.Row) -> set[str]:
    return {f for f in (row["flags"] or "").split(",") if f}
