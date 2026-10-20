"""`cloe orchestrate`: orchestrating a challenge (opgave), after PONT's "Orkestreren als
ontwerpcompetentie" (Jotte de Koning & Willem-Jan Renger, De Publieke Ontwerppraktijk,
2025; CONTEXT §H).

Orchestrating is connecting the efforts, interests and timelines of different actors so
that coherence, momentum and movement emerge: steering by connecting, not by power or a
mandate. Its basis is finding people and connecting them: who you involve when, and how
their contribution stays relevant for the process and for themselves. The paper names
three components, and this module keeps a board for each:

1. **Steer, don't govern** (sturen maar niet besturen): actors with their interest,
   timeline, mandate, *when* to involve them (stakeholder timing) and *how*, so that their
   input has value (stakeholder staging); tensions made discussable.
2. **Signal and navigate** (signaleren en navigeren): patterns, tensions, opportunities
   and blockages, at micro, meso and macro level.
3. **Make and use space** (ruimte maken en benutten): interventions in the model's four
   quadrants. Short term vs long term, crossed with seeking access to mandate vs working
   with stakeholders.

The closing chord asks that lessons, successes and failures alike, be anchored in a
collective memory: lessons here are searchable across challenges.

`check()` reads a board against the model and says what is missing; `suggest()` finds
candidate actors in what Cloé already knows (companies, research projects, their Dutch
partners). Nothing here contacts anyone: reaching out is a draft with Chloe's approval
(Sprints 4 and 5).
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, ValidationError

from cloe import db, library, records

QUADRANTS: dict[str, dict[str, str]] = {
    "timing_mandate": {
        "label": "Timing & mandate", "pont": "timing & mandaat", "term": "short",
        "side": "mandate",
        "value": "guard timing and sequence; involve those with a mandate at the right "
                 "moment, so they feel ownership",
        "example": "using the momentum of a steering meeting to present an experiment and "
                   "get formal support",
    },
    "strategic": {
        "label": "Strategic orchestration", "pont": "strategische orkestratie",
        "term": "long", "side": "mandate",
        "value": "anchor change structurally; couple experiments to policy changes; build "
                 "legitimacy",
        "example": "aligning the order and intensity of transition steps with the board or "
                   "alderman, and recalibrating policy as you go",
    },
    "use_space": {
        "label": "Using space with stakeholders", "pont": "ruimte benutten met betrokkenen",
        "term": "short", "side": "stakeholders",
        "value": "release energy; learn from direct experience; build support",
        "example": "a studio, a small intervention or a pilot where companies, knowledge "
                   "partners and officials experiment together",
    },
    "make_space": {
        "label": "Making space with stakeholders", "pont": "ruimte maken met betrokkenen",
        "term": "long", "side": "stakeholders",
        "value": "connect small experiences to a larger transition; develop collaboration "
                 "over the long term",
        "example": "keeping companies and partners involved in vision development and "
                   "structural changes",
    },
}
ACTOR_KINDS = ("company", "knowledge", "government", "network", "funder", "project",
               "citizen", "other")
LEVELS = ("micro", "meso", "macro")
ACTOR_STATUSES = ("not_yet", "involved", "resting", "left")
SIGNAL_KINDS = ("pattern", "tension", "opportunity", "blockage")
INTERVENTION_KINDS = ("workshop", "shared_map", "shared_language", "scenario",
                      "visualisation", "prototype", "pilot", "meeting", "other")
INTERVENTION_STATUSES = ("idea", "planned", "done", "dropped")
LESSON_KINDS = ("success", "failure", "insight")
CRUCIAL_KINDS = ("company", "knowledge", "government")
# The regions TOS13 targets (team, 2026-10-20; the ACT × PONT proposal). A company is in a
# region when its province (TELL) or its city matches; join-form companies have a city only.
REGIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "brabant": {
        "provinces": ("Noord-Brabant",),
        "cities": ("Tilburg", "Eindhoven", "Helmond", "'s-Hertogenbosch", "Den Bosch", "Breda",
                   "Oss", "Roosendaal", "Bergen op Zoom", "Waalwijk", "Veghel", "Oisterwijk"),
    },
    "oost-nederland": {
        "provinces": ("Overijssel", "Gelderland"),
        "cities": ("Enschede", "Hengelo", "Almelo", "Oldenzaal", "Borne", "Haaksbergen",
                   "Rijssen", "Zwolle", "Deventer", "Kampen", "Arnhem", "Nijmegen", "Apeldoorn",
                   "Ede", "Doetinchem", "Winterswijk", "Zutphen"),
    },
    "amsterdam": {"provinces": (), "cities": ("Amsterdam",)},
}
REGION_ALIASES = {"twente": "oost-nederland", "oost-nl": "oost-nederland", "oost nl":
                  "oost-nederland", "noord-brabant": "brabant", "mra": "amsterdam"}
# CORDIS activity types of a project's Dutch partners → actor kinds.
ORG_KIND = {"PRC": "company", "HES": "knowledge", "REC": "knowledge", "PUB": "government",
            "OTH": "network"}
_STOP = frozenset({
    "about", "also", "been", "connect", "deze", "door", "from", "have", "help", "into", "maar",
    "make", "more", "most", "naar", "need", "needs", "niet", "only", "onze", "ook", "over",
    "small", "some", "such", "than", "that", "their", "them", "then", "they", "this", "very",
    "voor", "want", "were", "what", "when", "where", "which", "will", "with", "worden",
    "wordt", "zijn",
})


class OrchestrateError(ValueError):
    """Unknown challenge, actor or intervention, or an invalid value."""


def _clean(text: object, limit: int = 500) -> str:
    return records.clean(text, limit)


def _choice(value: str, allowed: tuple[str, ...], what: str) -> str:
    if value not in allowed:
        raise OrchestrateError(f"{what} must be one of: {', '.join(allowed)}")
    return value


# -- challenges -------------------------------------------------------------------------


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _clean(text, 80).lower()).strip("-")
    if not slug:
        raise OrchestrateError("a challenge needs a name of letters or digits")
    return slug[:60]


def opgave(conn: sqlite3.Connection, slug: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM opgave WHERE slug = ?", (slugify(slug),)).fetchone()
    if row is None:
        raise OrchestrateError(f"no challenge {slug!r} (see `cloe orchestrate list`)")
    return row


def new_opgave(conn: sqlite3.Connection, slug: str, title: str, *, frame: str = "",
               region: str = "") -> int:
    slug = slugify(slug)
    if conn.execute("SELECT 1 FROM opgave WHERE slug = ?", (slug,)).fetchone():
        raise OrchestrateError(f"challenge {slug!r} exists already")
    now = db.now()
    cur = conn.execute(
        "INSERT INTO opgave(slug, title, frame, region, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (slug, _clean(title, 200) or slug, _clean(frame, 2000), _clean(region, 120), now, now))
    conn.commit()
    db.event(conn, "orchestrate", "opgave_new", ref=f"opgave:{cur.lastrowid}")
    return cur.lastrowid


def _touch(conn: sqlite3.Connection, oid: int) -> None:
    conn.execute("UPDATE opgave SET updated_at = ? WHERE id = ?", (db.now(), oid))


# -- actors (who, when, how) --------------------------------------------------------------


def set_actor(conn: sqlite3.Connection, slug: str, name: str, **fields) -> tuple[int, bool]:
    """Add an actor to a challenge, or update the fields given. Fields: kind, level,
    has_mandate, interest, timeline, involve_when, staging, status, company_id,
    project_id, person_id. Returns (actor_id, created)."""
    oid = opgave(conn, slug)["id"]
    name = _clean(name, 200)
    if not name:
        raise OrchestrateError("an actor needs a name")
    vals: dict[str, object] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if key == "kind":
            vals[key] = _choice(value, ACTOR_KINDS, "kind")
        elif key == "level":
            vals[key] = _choice(value, LEVELS, "level")
        elif key == "status":
            vals[key] = _choice(value, ACTOR_STATUSES, "status")
        elif key == "has_mandate":
            vals[key] = int(bool(value))
        elif key in ("interest", "timeline", "involve_when", "staging"):
            vals[key] = _clean(value, 500)
        elif key in ("company_id", "project_id", "person_id"):
            vals[key] = int(value)
        else:
            raise OrchestrateError(f"unknown actor field {key!r}")
    now = db.now()
    row = conn.execute("SELECT * FROM orch_actor WHERE opgave_id = ? AND name = ?",
                       (oid, name)).fetchone()
    if row is None:
        vals.setdefault("kind", "other")
        cols = ["opgave_id", "name", "status_at", "created_at", *vals]
        cur = conn.execute(
            f"INSERT INTO orch_actor({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            (oid, name, now, now, *vals.values()))
        actor_id, created = cur.lastrowid, True
    else:
        actor_id, created = row["id"], False
        if "status" in vals and vals["status"] != row["status"]:
            vals["status_at"] = now
        if vals:
            sets = ", ".join(f"{k} = ?" for k in vals)
            conn.execute(f"UPDATE orch_actor SET {sets} WHERE id = ?", (*vals.values(), actor_id))
    _touch(conn, oid)
    conn.commit()
    return actor_id, created


def _actor_id(conn: sqlite3.Connection, oid: int, name: str) -> int:
    row = conn.execute("SELECT id FROM orch_actor WHERE opgave_id = ? AND name = ? "
                       "COLLATE NOCASE", (oid, _clean(name, 200))).fetchone()
    if row is None:
        raise OrchestrateError(f"no actor {name!r} on this challenge (add it first)")
    return row["id"]


# -- signals (signal and navigate) -----------------------------------------------------


def add_signal(conn: sqlite3.Connection, slug: str, kind: str, text: str, *,
               level: str = "meso", actor: str | None = None) -> int:
    oid = opgave(conn, slug)["id"]
    text = _clean(text, 1000)
    if not text:
        raise OrchestrateError("a signal needs text")
    cur = conn.execute(
        "INSERT INTO orch_signal(opgave_id, kind, level, text, actor_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (oid, _choice(kind, SIGNAL_KINDS, "kind"), _choice(level, LEVELS, "level"), text,
         _actor_id(conn, oid, actor) if actor else None, db.now()))
    _touch(conn, oid)
    conn.commit()
    return cur.lastrowid


def set_signal_status(conn: sqlite3.Connection, signal_id: int, status: str) -> None:
    status = _choice(status, ("open", "addressed", "dropped"), "status")
    if conn.execute("UPDATE orch_signal SET status = ? WHERE id = ?",
                    (status, signal_id)).rowcount == 0:
        raise OrchestrateError(f"no signal #{signal_id}")
    conn.commit()


# -- interventions (make and use space) ------------------------------------------------


def add_intervention(conn: sqlite3.Connection, slug: str, title: str, quadrant: str, *,
                     kind: str = "other", value: str = "", planned_for: str = "",
                     status: str = "idea", actors: list[str] | None = None,
                     follows: int | None = None, signal: int | None = None) -> int:
    oid = opgave(conn, slug)["id"]
    title = _clean(title, 300)
    if not title:
        raise OrchestrateError("an intervention needs a title")
    for ref, table in ((follows, "orch_intervention"), (signal, "orch_signal")):
        if ref is not None and not conn.execute(
                f"SELECT 1 FROM {table} WHERE id = ? AND opgave_id = ?", (ref, oid)).fetchone():
            raise OrchestrateError(f"no {table.removeprefix('orch_')} #{ref} on this challenge")
    actor_ids = [_actor_id(conn, oid, a) for a in actors or []]
    now = db.now()
    cur = conn.execute(
        "INSERT INTO orch_intervention(opgave_id, title, kind, quadrant, value, planned_for, "
        "status, follows_id, signal_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (oid, title, _choice(kind, INTERVENTION_KINDS, "kind"),
         _choice(quadrant, tuple(QUADRANTS), "quadrant"), _clean(value, 500),
         _clean(planned_for, 80), _choice(status, INTERVENTION_STATUSES, "status"),
         follows, signal, now, now))
    conn.executemany("INSERT OR IGNORE INTO orch_intervention_actor VALUES (?, ?)",
                     [(cur.lastrowid, a) for a in actor_ids])
    _touch(conn, oid)
    conn.commit()
    if status == "done":
        _addressed(conn, cur.lastrowid)
    return cur.lastrowid


def _addressed(conn: sqlite3.Connection, iid: int) -> None:
    conn.execute("UPDATE orch_signal SET status = 'addressed' WHERE status = 'open' AND id = "
                 "(SELECT signal_id FROM orch_intervention WHERE id = ?)", (iid,))
    conn.commit()


def set_intervention_status(conn: sqlite3.Connection, iid: int, status: str) -> None:
    status = _choice(status, INTERVENTION_STATUSES, "status")
    if conn.execute("UPDATE orch_intervention SET status = ?, updated_at = ? WHERE id = ?",
                    (status, db.now(), iid)).rowcount == 0:
        raise OrchestrateError(f"no intervention #{iid}")
    conn.commit()
    if status == "done":
        _addressed(conn, iid)


# -- lessons (collective memory) -------------------------------------------------------


def add_lesson(conn: sqlite3.Connection, slug: str, text: str, *, kind: str = "insight",
               intervention: int | None = None) -> int:
    oid = opgave(conn, slug)["id"]
    text = _clean(text, 1000)
    if not text:
        raise OrchestrateError("a lesson needs text")
    if intervention is not None and not conn.execute(
            "SELECT 1 FROM orch_intervention WHERE id = ? AND opgave_id = ?",
            (intervention, oid)).fetchone():
        raise OrchestrateError(f"no intervention #{intervention} on this challenge")
    cur = conn.execute(
        "INSERT INTO orch_lesson(opgave_id, intervention_id, kind, text, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (oid, intervention, _choice(kind, LESSON_KINDS, "kind"), text, db.now()))
    conn.execute("INSERT INTO orch_lesson_fts(rowid, text) VALUES (?, ?)",
                 (cur.lastrowid, text))
    _touch(conn, oid)
    conn.commit()
    return cur.lastrowid


def _terms(text: str) -> list[str]:
    words = re.findall(r"\w+", records.clean(text, 4000).lower())
    return list(dict.fromkeys(w for w in words if len(w) >= 4 and w not in _STOP))[:12]


def search_lessons(conn: sqlite3.Connection, query: str, k: int = 10, *,
                   exclude_opgave: int | None = None) -> list[sqlite3.Row]:
    """Lessons from every challenge, best match first (any of the words, as prefixes)."""
    terms = _terms(query)
    if not terms:
        return []
    match = " OR ".join(f'"{t}"*' for t in terms)
    return conn.execute(
        "SELECT l.*, o.slug, o.title AS opgave_title FROM orch_lesson_fts f "
        "JOIN orch_lesson l ON l.id = f.rowid JOIN opgave o ON o.id = l.opgave_id "
        "WHERE orch_lesson_fts MATCH ? AND l.opgave_id IS NOT ? ORDER BY bm25(orch_lesson_fts) "
        "LIMIT ?", (match, exclude_opgave, k)).fetchall()


# -- seeding boards from a file (the team's shared setup) --------------------------------


class SeedActor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    kind: str = "other"
    level: str = "meso"
    has_mandate: bool = False
    interest: str = ""
    timeline: str = ""
    involve_when: str = ""
    staging: str = ""
    status: str = "not_yet"


class SeedSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    text: str
    level: str = "meso"
    actor: str | None = None


class SeedChallenge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str
    title: str
    frame: str = ""
    region: str = ""
    actors: list[SeedActor] = []
    signals: list[SeedSignal] = []


class Seed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = ""
    challenges: list[SeedChallenge]


def load_seed(conn: sqlite3.Connection, data: bytes | str) -> dict[str, int]:
    """Create the challenges, actors and signals a seed file describes. Only what is
    missing is added: re-loading never changes what the team has edited since."""
    try:
        seed = Seed.model_validate_json(data)
    except ValidationError as exc:
        raise OrchestrateError(f"seed file does not match the format ({exc.error_count()} "
                               "errors)") from None
    counts = {"challenges": 0, "actors": 0, "signals": 0}
    for ch in seed.challenges:
        slug = slugify(ch.slug)
        if not conn.execute("SELECT 1 FROM opgave WHERE slug = ?", (slug,)).fetchone():
            new_opgave(conn, slug, ch.title, frame=ch.frame, region=ch.region)
            counts["challenges"] += 1
        oid = opgave(conn, slug)["id"]
        for a in ch.actors:
            exists = conn.execute("SELECT 1 FROM orch_actor WHERE opgave_id = ? AND name = ? "
                                  "COLLATE NOCASE", (oid, _clean(a.name, 200))).fetchone()
            if not exists:
                set_actor(conn, slug, a.name, **a.model_dump(exclude={"name"}))
                counts["actors"] += 1
        for sig in ch.signals:
            exists = conn.execute("SELECT 1 FROM orch_signal WHERE opgave_id = ? AND text = ?",
                                  (oid, _clean(sig.text, 1000))).fetchone()
            if not exists:
                add_signal(conn, slug, sig.kind, sig.text, level=sig.level, actor=sig.actor)
                counts["signals"] += 1
    return counts


# -- reading the board against the model ------------------------------------------------


@dataclass(frozen=True)
class Finding:
    component: str   # steer | signal | space | memory
    level: str       # ok | warn | info
    text: str


COMPONENTS = {
    "steer": "Steer, don't govern (sturen maar niet besturen)",
    "signal": "Signal and navigate (signaleren en navigeren)",
    "space": "Make and use space (ruimte maken en benutten)",
    "memory": "Collective memory",
}


def _names(rows) -> str:
    return ", ".join(r["name"] for r in rows)


def check(conn: sqlite3.Connection, slug: str) -> list[Finding]:
    o = opgave(conn, slug)
    oid = o["id"]
    actors = conn.execute("SELECT * FROM orch_actor WHERE opgave_id = ? ORDER BY id",
                          (oid,)).fetchall()
    signals = conn.execute("SELECT * FROM orch_signal WHERE opgave_id = ? ORDER BY id",
                           (oid,)).fetchall()
    live = conn.execute("SELECT * FROM orch_intervention WHERE opgave_id = ? AND "
                        "status != 'dropped' ORDER BY id", (oid,)).fetchall()
    out: list[Finding] = []

    def add(component: str, level: str, text: str) -> None:
        out.append(Finding(component, level, text))

    # 1. Steer, don't govern
    involved = [a for a in actors if a["status"] == "involved"]
    if not actors:
        add("steer", "warn", "No actors yet. Finding and connecting people is where "
            "orchestrating starts (try `cloe orchestrate suggest`).")
    with_mandate = [a for a in involved if a["has_mandate"]]
    if actors and not with_mandate:
        add("steer", "warn", "Nobody with a formal mandate is involved. Find the moment to "
            "bring one in, so they feel ownership (timing & mandate).")
    elif with_mandate:
        add("steer", "ok", f"Involved with a mandate: {_names(with_mandate)}.")
    if live and not any(QUADRANTS[i["quadrant"]]["side"] == "mandate" for i in live):
        add("steer", "warn", "No intervention seeks access to mandate (the upper half of the "
            "model): a decision will need someone who can take it.")
    present = {a["kind"] for a in actors}
    for kind in CRUCIAL_KINDS:
        if actors and kind not in present:
            add("steer", "warn", f"No {kind} actor on the board: is a crucial voice missing?")
    untimed = [a for a in actors if a["status"] == "not_yet" and not a["involve_when"]]
    if untimed:
        add("steer", "warn", f"Decide when to involve {_names(untimed)} (stakeholder timing).")
    unstaged = [a for a in involved if not a["staging"]]
    if unstaged:
        add("steer", "warn", f"Say how {_names(unstaged)} can add value, so their input "
            "counts (stakeholder staging).")
    busy = {r[0] for r in conn.execute(
        "SELECT DISTINCT ia.actor_id FROM orch_intervention_actor ia JOIN orch_intervention i "
        "ON i.id = ia.intervention_id WHERE i.opgave_id = ? AND i.status IN "
        "('planned', 'done')", (oid,))}
    idle = [a for a in involved if a["id"] not in busy]
    if idle and live:
        add("steer", "warn", f"{_names(idle)}: involved, but in no planned or done "
            "intervention. Give them a role, or let them rest (people held too long drop out).")
    handled = {i["signal_id"] for i in live if i["signal_id"]}
    for s in signals:
        if s["status"] == "open" and s["kind"] in ("tension", "blockage") and \
                s["id"] not in handled:
            add("steer", "warn", f"Open {s['kind']} #{s['id']}: \"{s['text'][:80].rstrip('.')}"
                "\". Make it discussable before it escalates (link an intervention).")

    # 2. Signal and navigate
    if not signals:
        add("signal", "warn", "No signals yet: map the patterns, tensions, opportunities "
            "and blockages.")
    levels = {a["level"] for a in actors} | {s["level"] for s in signals}
    if (actors or signals) and len(levels) < 2:
        only = next(iter(levels))
        add("signal", "warn", f"Only the {only} level is in view: move between micro, meso "
            "and macro.")
    elif len(levels) >= 2:
        add("signal", "ok", f"Levels in view: {', '.join(sorted(levels, key=LEVELS.index))}.")

    # 3. Make and use space
    terms = {QUADRANTS[i["quadrant"]]["term"] for i in live}
    if not live:
        add("space", "warn", "No interventions yet. Small steps build trust; plan one.")
    elif terms == {"short"}:
        add("space", "warn", "Only short-term steps: connect the experiments to structural "
            "change (strategic orchestration, making space).")
    elif terms == {"long"}:
        add("space", "warn", "Only long-term plans: small interventions take away "
            "uncertainty and open the way (using space).")
    else:
        add("space", "ok", "Short-term steps and long-term anchoring are both planned.")

    # 4. Collective memory
    learned = {r[0] for r in conn.execute(
        "SELECT intervention_id FROM orch_lesson WHERE opgave_id = ? AND intervention_id IS "
        "NOT NULL", (oid,))}
    unlearned = [i for i in live if i["status"] == "done" and i["id"] not in learned]
    if unlearned:
        add("memory", "warn", "Done without a lesson: " + ", ".join(
            f"#{i['id']}" for i in unlearned) + ". Record what worked and what didn't.")
    for lesson in search_lessons(conn, f"{o['title']} {o['frame']}", 3, exclude_opgave=oid):
        add("memory", "info", f"Earlier lesson ({lesson['slug']}, {lesson['kind']}): "
            f"{lesson['text'][:140]}")
    return out


# -- finding people (suggestions from Cloé's network) ------------------------------------


def org_kind(org: dict) -> str:
    """A project partner's actor kind: CORDIS activity type, else read from the name."""
    kind = ORG_KIND.get(str(org.get("type") or "").upper())
    if kind:
        return kind
    name = str(org.get("name") or "").lower()
    if re.search(r"universit|hogeschool|school|academ|institu|lectoraat", name):
        return "knowledge"
    return "other"


def region_key(region: str | None) -> str | None:
    """The REGIONS key a challenge's region names ('Oost-Nederland', 'Twente', …), or None."""
    low = (region or "").strip().lower()
    if not low:
        return None
    key = REGION_ALIASES.get(low, low.replace(" ", "-"))
    return key if key in REGIONS else None


def in_region(company: sqlite3.Row, key: str) -> bool:
    scope = REGIONS[key]
    province = (company["region"] or "").strip().lower()
    city = (company["city"] or "").strip().lower()
    return province in {p.lower() for p in scope["provinces"]} or \
        city in {c.lower() for c in scope["cities"]}


@dataclass(frozen=True)
class Candidate:
    name: str
    kind: str
    reason: str
    company_id: int | None = None
    project_id: int | None = None


def suggest(conn: sqlite3.Connection, slug: str, k: int = 8) -> list[Candidate]:
    """Candidate actors from Cloé's data that fit the challenge's title and frame: companies
    whose facts or needs match (only those in the challenge's region, when it names one of
    REGIONS), research projects (library cards) and their Dutch partners (national; the
    datasets give no location). Flagged text is never used. Actors already on the board
    are left out."""
    o = opgave(conn, slug)
    query = f"{o['title']} {o['frame']}"
    have = conn.execute("SELECT name, company_id, project_id FROM orch_actor WHERE "
                        "opgave_id = ?", (o["id"],)).fetchall()
    names = {r["name"].lower() for r in have}
    companies = {r["company_id"] for r in have if r["company_id"]}
    projects = {r["project_id"] for r in have if r["project_id"]}
    groups: dict[str, list[Candidate]] = {"companies": [], "projects": [], "partners": []}
    seen: set[str] = set()

    def keep(group: str, c: Candidate) -> None:
        if c.name.lower() not in names and c.name.lower() not in seen and \
                (c.company_id is None or c.company_id not in companies) and \
                (c.project_id is None or c.project_id not in projects):
            seen.add(c.name.lower())
            groups[group].append(c)

    for hit in library.search(conn, query, 10):
        doc = conn.execute("SELECT project_id FROM document WHERE id = ?", (hit.id,)).fetchone()
        project = conn.execute("SELECT * FROM project WHERE id = ?",
                               (doc["project_id"],)).fetchone() if doc else None
        if project is None:
            continue
        label = project["acronym"] or project["title"]
        keep("projects", Candidate(label, "project", f"research project "
                                   f"({project['programme'] or '-'}): "
                       f"{project['title'][:80]}", project_id=project["id"]))
        for org in json.loads(project["nl_orgs_json"] or "[]")[:6]:
            keep("partners", Candidate(org["name"], org_kind(org), f"Dutch partner in {label}"))
    scores: dict[int, set[str]] = {}
    for term in _terms(query):
        for (cid,) in conn.execute(
                "SELECT company_id FROM fact WHERE instr(flags, 'instruction_like') = 0 AND "
                "text LIKE ? UNION SELECT company_id FROM need WHERE status != 'flagged' AND "
                "text LIKE ?", (f"%{term}%", f"%{term}%")):
            scores.setdefault(cid, set()).add(term)
    region = region_key(o["region"])
    if region:
        # A regional challenge: every company in the region is a candidate, ranked by the
        # words it matches and by whether someone there registered through the join form.
        rows = [c for c in conn.execute("SELECT id, name, city, region, tier FROM company")
                if in_region(c, region)]
        registered = {r[0] for r in conn.execute(
            "SELECT DISTINCT p.company_id FROM person p JOIN consent c ON c.person_id = p.id "
            "WHERE c.source = 'joinform'")}
        ranked = sorted(rows, key=lambda c: (-len(scores.get(c["id"], ())),
                                             c["id"] not in registered, c["name"]))
    else:
        ids = [cid for cid, _ in sorted(scores.items(), key=lambda kv: -len(kv[1]))]
        ranked = [c for cid in ids if (c := conn.execute(
            "SELECT id, name, city, region, tier FROM company WHERE id = ?", (cid,)).fetchone())]
    for c in ranked:
        terms = scores.get(c["id"], set())
        where = ", ".join(x for x in (c["city"], c["tier"]) if x)
        why = [f"in the network ({where or '-'})"]
        if terms:
            why.append(f"matches {', '.join(sorted(terms))}")
        if region and c["id"] in registered:
            why.append("registered through the join form")
        keep("companies", Candidate(c["name"], "company", "; ".join(why), company_id=c["id"]))
    # The network's own companies first, then research projects, then their partners.
    return [c for group in groups.values() for c in group[:k]]


# -- the board ---------------------------------------------------------------------------


def _md(text: object) -> str:
    return re.sub(r"([\\`*_\[\]<>|])", r"\\\1", str(text or ""))


def board(conn: sqlite3.Connection, slug: str) -> str:
    o = opgave(conn, slug)
    oid = o["id"]
    out = [f"# {_md(o['title'])}", "",
           f"`{o['slug']}` · {o['status']}" + (f" · {_md(o['region'])}" if o["region"] else "")]
    if o["frame"]:
        out += ["", f"Frame: {_md(o['frame'])}"]

    header = ("| actor | kind | level | mandate | status | when to involve | how (staging) | "
              "interest | timeline |")
    out += ["", "## Actors: who, when, how", "", header, "|---|---|---|---|---|---|---|---|---|"]
    actors = conn.execute("SELECT * FROM orch_actor WHERE opgave_id = ? ORDER BY "
                          "CASE status WHEN 'involved' THEN 0 WHEN 'not_yet' THEN 1 ELSE 2 END,"
                          " id", (oid,)).fetchall()
    for a in actors:
        out.append("| " + " | ".join(_md(x) or "-" for x in (
            a["name"], a["kind"], a["level"], "yes" if a["has_mandate"] else "", a["status"],
            a["involve_when"], a["staging"], a["interest"], a["timeline"])) + " |")
    if not actors:
        out.append("| (none yet) | | | | | | | | |")

    out += ["", "## Signals"]
    signals = conn.execute(
        "SELECT s.*, a.name AS actor FROM orch_signal s LEFT JOIN orch_actor a ON "
        "a.id = s.actor_id WHERE s.opgave_id = ? ORDER BY s.status = 'open' DESC, s.id",
        (oid,)).fetchall()
    for s in signals:
        who = f" ({_md(s['actor'])})" if s["actor"] else ""
        out.append(f"- #{s['id']} [{s['kind']} · {s['level']} · {s['status']}] "
                   f"{_md(s['text'])}{who}")
    if not signals:
        out.append("- (none yet)")

    out += ["", "## Interventions"]
    for key, q in QUADRANTS.items():
        side = "with mandate" if q["side"] == "mandate" else "with stakeholders"
        out += ["", f"### {q['label']} ({q['pont']}): {q['term']} term, {side}",
                f"_Value: {q['value']}._"]
        rows = conn.execute("SELECT * FROM orch_intervention WHERE opgave_id = ? AND "
                            "quadrant = ? ORDER BY id", (oid, key)).fetchall()
        for i in rows:
            who = [r[0] for r in conn.execute(
                "SELECT a.name FROM orch_intervention_actor ia JOIN orch_actor a ON "
                "a.id = ia.actor_id WHERE ia.intervention_id = ? ORDER BY a.name", (i["id"],))]
            extra = []
            if i["planned_for"]:
                extra.append(f"when: {_md(i['planned_for'])}")
            if who:
                extra.append("with: " + ", ".join(_md(w) for w in who))
            if i["follows_id"]:
                extra.append(f"follows #{i['follows_id']}")
            if i["signal_id"]:
                extra.append(f"addresses signal #{i['signal_id']}")
            if i["value"]:
                extra.append(f"value: {_md(i['value'])}")
            out.append(f"- #{i['id']} [{i['status']} · {i['kind']}] {_md(i['title'])}"
                       + (f" ({'; '.join(extra)})" if extra else ""))
        if not rows:
            out.append(f"- (none; for example: {q['example']})")

    out += ["", "## Lessons"]
    lessons = conn.execute("SELECT * FROM orch_lesson WHERE opgave_id = ? ORDER BY id",
                           (oid,)).fetchall()
    for le in lessons:
        ref = f" (from #{le['intervention_id']})" if le["intervention_id"] else ""
        out.append(f"- [{le['kind']}] {_md(le['text'])}{ref}")
    if not lessons:
        out.append("- (none yet)")

    out += ["", "## Check against the orchestration model"]
    all_findings = check(conn, slug)
    for component, label in COMPONENTS.items():
        findings = [f for f in all_findings if f.component == component]
        if findings:
            out += ["", f"**{label}**"]
            out += [f"- {f.level.upper()} {_md(f.text)}" for f in findings]
    return "\n".join(out) + "\n"
