"""A company's profile as markdown, for Chloe and the team (not for companies).

Facts are ordered by confidence, then date; expired facts are left out. Text flagged
`instruction_like` never appears as prose: it is listed under "Flagged text" as an
indented code block, with its source, so it cannot render as links or markup.
"""

from __future__ import annotations

import re
import sqlite3
import textwrap
from pathlib import Path

from cloe import db, people, records

TELL_URL = "https://tell.newtexeco.nl"
DOES_KINDS = ("does", "makes")
OTHER_KINDS = ("project", "event", "contact", "other")
PURPOSE_LABEL = {"followup": "follow-up", "newsletter": "newsletter",
                 "cloe_updates": "Cloé updates"}


def _md(text: str) -> str:
    """Prose-safe: no links, HTML or code spans from outside text."""
    return re.sub(r"([\\`\[\]<>])", r"\\\1", text)


LINK_STATUS = {
    "detected": "not asked yet",
    "asked": "asked · newcomer: {newcomer_ok}, colleague: {existing_ok}",
    "connected": "connected: both said yes",
    "declined": "declined: keep them apart",
}


def _source_label(src: sqlite3.Row, who: dict[str, str]) -> str:
    url = src["url"] or ""
    imported = (src["fetched_at"] or "")[:10]
    if src["kind"] == "joinform":
        submitted = url.split(":", 1)[1].rsplit(":", 1)[0] if url.count(":") >= 2 else "?"
        name = who.get(url.rsplit(":", 1)[-1])
        label = f"Join form{f' from {name}' if name else ''}, submitted {submitted or '?'}"
    elif src["kind"] == "tell":
        origin = url.removeprefix("tell:").split("#", 1)[0]
        label = "TELL database" if origin == "db" else f"TELL export {origin}"
    else:
        label = f"{src['kind']} {url}".strip()
    return f"{_md(label)} · imported {imported}"


class _Sources:
    """Numbers the sources a profile cites. `who` maps an email hash to the person's name,
    so each join-form submission shows whose answers it holds."""

    def __init__(self, conn: sqlite3.Connection, who: dict[str, str]):
        self.conn, self.who, self.used = conn, who, {}

    def ref(self, source_id: int | None) -> str:
        if source_id is None:
            return "[no source]"
        if source_id not in self.used:
            row = self.conn.execute("SELECT * FROM source WHERE id = ?", (source_id,)).fetchone()
            self.used[source_id] = _source_label(row, self.who) if row else "deleted source"
        return f"[S{source_id}]"


def _facts(conn: sqlite3.Connection, company_id: int, now: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM fact WHERE company_id = ? AND (expires_at IS NULL OR expires_at > ?) "
        "ORDER BY confidence DESC, observed_at DESC, id",
        (company_id, now),
    ).fetchall()


def _header(c: sqlite3.Row) -> list[str]:
    def val(v: object) -> str:
        return _md(str(v)) if v not in (None, "") else "—"

    place = val(c["city"]) + (f" ({_md(c['postcode'])})" if c["postcode"] else "")
    tell = "not matched" if not c["tell_id"] else (
        f"listed · {TELL_URL}" if str(c["tell_id"]).startswith("export:")
        else f"id {_md(str(c['tell_id']))} · {TELL_URL}"
    )
    return [
        f"# {_md(c['name'])}",
        "",
        f"- **Domain:** {val(c['domain'])} · **Website:** {val(c['website'])}",
        f"- **Place:** {place}",
        (f"- **Tier:** {val(c['tier'])} · **Category:** {val(c['category'])} · "
         f"**Class:** {val(c['company_class'])}"),
        (f"- **Employees:** {val(c['employees'])} · **Founded:** {val(c['year_start'])} · "
         f"**KvK:** {val(c['kvk'])}"),
        f"- **TELL:** {tell}",
    ]


def _consent_text(state: dict[str, str], channel: str) -> str:
    return ", ".join(f"{PURPOSE_LABEL[p]} {state[f'{channel}/{p}']}" for p in people.PURPOSES)


def render(conn: sqlite3.Connection, company_id: int) -> str:
    c = conn.execute("SELECT * FROM company WHERE id = ?", (company_id,)).fetchone()
    if c is None:
        raise KeyError(company_id)
    now = db.now()
    persons = conn.execute(
        "SELECT * FROM person WHERE company_id = ? ORDER BY id", (company_id,)
    ).fetchall()
    src = _Sources(conn, {people.email_sha256(p["email"]): p["name"] or "a colleague"
                          for p in persons})
    facts = _facts(conn, company_id, now)
    prose = [f for f in facts if records.INSTRUCTION_LIKE not in records.flags_of(f)]
    flagged: list[tuple[str, int | None, str]] = [
        (f"fact · {f['kind']}", f["source_id"], f["text"])
        for f in facts if records.INSTRUCTION_LIKE in records.flags_of(f)
    ]
    needs = conn.execute(
        "SELECT * FROM need WHERE company_id = ? ORDER BY id", (company_id,)
    ).fetchall()
    flagged += [("need", n["source_id"], n["text"]) for n in needs if n["status"] == "flagged"]
    open_needs = [n for n in needs if n["status"] != "flagged"]

    out = _header(c)

    def fact_lines(kinds: tuple[str, ...]) -> list[str]:
        lines = []
        for f in prose:
            if f["kind"] in kinds:
                mark = " _(scraped)_" if records.SCRAPED in records.flags_of(f) else ""
                lines.append(f"- {_md(f['text'])} {src.ref(f['source_id'])}{mark}")
        return lines or ["- (nothing yet)"]

    out += ["", "## What they do", *fact_lines(DOES_KINDS)]
    out += ["", "## What they need"]
    out += [
        f"- ({n['kind'] or 'unclassified'}) {_md(n['text'])} {src.ref(n['source_id'])}"
        for n in open_needs
    ] or ["- (nothing yet)"]
    out += ["", "## Data they have", *fact_lines(("has_data",))]
    out += ["", "## Other facts", *fact_lines(OTHER_KINDS)]

    with_consent, without = [], []
    for p in persons:
        state = people.consents(conn, p["id"])
        (with_consent if "yes" in state.values() else without).append((p, state))
    out += ["", "## People we may contact (with consent)"]
    for p, state in with_consent:
        who = ", ".join(_md(x) for x in (p["name"], p["role"]) if x) or "(no name)"
        out.append(f"- {who} — {_md(p['email'])}")
        out.append(f"  - email: {_consent_text(state, 'email')}")
        out.append(f"  - sms: {_consent_text(state, 'sms')}"
                   + ("" if p["phone"] else " (no phone number)"))
        if "rejoined" in (p["flags"] or "").split(","):
            out.append("  - rejoined after being forgotten: the welcome says it looks like "
                       "they're rejoining and shows what we know about their company")
    if not with_consent:
        out.append("- (nobody yet)")
    if without:
        out += ["", ("Contacts without consent — Cloé may not write to them until Chloe "
                     "records consent (`cloe consent set`):")]
        out += [f"- {_md(p['email'])}" for p, _ in without]

    links = conn.execute(
        "SELECT l.*, n.name AS n_name, n.email AS n_email, e.name AS e_name, "
        "e.email AS e_email FROM colleague_link l JOIN person n ON n.id = l.newcomer_id "
        "JOIN person e ON e.id = l.existing_id WHERE l.company_id = ? ORDER BY l.id",
        (company_id,),
    ).fetchall()
    out += ["", "## Colleagues who registered separately"]
    if links:
        out.append("Cloé tells the newcomer that someone from their company is already "
                   "registered, asks both whether they may be connected, and shares names "
                   "only when both say yes.")
        for link in links:
            status = LINK_STATUS[link["status"]].format(**dict(link))
            out.append(f"- {_md(link['n_name'] or link['n_email'])} registered after "
                       f"{_md(link['e_name'] or link['e_email'])} — {status}")
    else:
        out.append("- (none)")

    out += ["", "## Flagged text"]
    if flagged:
        out.append("Written by outsiders and reads like instructions. Kept as data; never used "
                   "in prose or messages.")
        for label, source_id, text in flagged:
            out += ["", f"{label} {src.ref(source_id)}:", ""]
            out += ["    " + line for line in textwrap.wrap(text, 88)]
    else:
        out.append("- (none)")

    out += ["", "## Sources"]
    out += [f"- [S{sid}] {label}" for sid, label in sorted(src.used.items())] or ["- (none)"]

    out += ["", "## Open questions", *_open_questions(c, open_needs, prose, with_consent,
                                                       persons, flagged)]
    return "\n".join(out) + "\n"


def _open_questions(c, open_needs, prose, with_consent, persons, flagged) -> list[str]:
    qs = []
    if not c["domain"]:
        qs.append("No website known.")
    if not c["city"]:
        qs.append("No city known.")
    if not c["tell_id"]:
        qs.append("Not matched to TELL.")
    if not open_needs:
        qs.append("We don't know yet what they need.")
    unclassified = sum(1 for n in open_needs if not n["kind"])
    if unclassified:
        qs.append(f"{unclassified} need(s) not classified yet (re-run the join-form ingest "
                  "with an API key).")
    if not any(f["kind"] == "has_data" for f in prose):
        qs.append("We don't know what data they have.")
    if not with_consent:
        qs.append("Nobody here has given consent: Cloé cannot write to this company yet.")
    if not any(p["phone"] for p in persons):
        qs.append("No phone number: SMS is not possible.")
    if flagged:
        qs.append("Flagged text from a source: check that source before trusting its other "
                  "facts.")
    return [f"- {q}" for q in qs] or ["- (none)"]


def write(conn: sqlite3.Connection, company_id: int, profiles_dir: Path) -> Path:
    """Render and save `profiles_dir/<domain>.md` (owner-only: it lists people)."""
    company = conn.execute("SELECT * FROM company WHERE id = ?", (company_id,)).fetchone()
    profiles_dir.mkdir(parents=True, exist_ok=True)
    path = profiles_dir / records.profile_filename(company)
    path.write_text(render(conn, company_id), encoding="utf-8")
    path.chmod(0o600)
    return path
