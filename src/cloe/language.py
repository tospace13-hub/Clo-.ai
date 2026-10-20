"""Which language Cloé writes to someone in, and how (tone.md §3).

The team's rule (2026-10-20): **default to English, but offer Dutch.** A person's language
is captured from what they tell us, in two strengths:

- **explicit**: the join form's language question (once the form has one), Chloe
  (`cloe language set`, with evidence), or a reply they write (Sprint 5). The newest wins.
- **inferred**: the language of their own join-form answers. Used only while nothing
  explicit is known.

Nothing known → English. Until someone has explicitly chosen English (or written to us in
it), an English message carries one line offering Dutch (Sprint 4), and a reply in Dutch
switches them (Sprint 5). Dutch is *je* unless they use *u* themselves.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from cloe import db, records
from cloe.untrusted import scrub

LANGS = ("en", "nl")
LANG_NAMES = {"en": "English", "nl": "Dutch"}
DEFAULT_LANG = "en"
EXPLICIT_SOURCES = ("joinform", "manual", "inbound")
INFERRED_SOURCES = ("joinform_text",)
SOURCE_TEXT = {
    "joinform": "chosen on the join form",
    "manual": "set by the team",
    "inbound": "the language they last wrote to us in",
    "joinform_text": "the language of their join-form answers",
}
MIN_HITS = 3  # stopwords needed before a guess is made

# Words common in one language and rare in the other ("is", "in", "we", "die" are both).
_NL = frozenset({
    "aan", "bedrijf", "bij", "dat", "de", "deze", "dit", "een", "en", "graag", "heb", "hebben",
    "het", "hoe", "ik", "jullie", "kunnen", "met", "mijn", "naar", "niet", "om", "ons", "onze",
    "ook", "op", "over", "te", "van", "voor", "vraag", "waar", "wat", "welke", "wij", "willen",
    "wordt", "zijn", "zoeken",
})
_EN = frozenset({
    "about", "and", "are", "at", "by", "can", "company", "for", "from", "has", "have", "how",
    "like", "looking", "my", "need", "of", "on", "our", "that", "the", "these", "this", "to",
    "want", "what", "where", "which", "with", "would",
})
_CHOICES = {
    "nl": ("nl", "dutch", "nederlands", "nederlandse", "netherlands"),
    "en": ("en", "english", "engels", "engelse"),
}


def detect(text: str | None) -> str | None:
    """'nl' or 'en' when the text clearly reads as one of them, else None."""
    words = re.findall(r"[a-zà-ÿ]+", scrub(text or "", 5000).lower())
    nl = sum(w in _NL for w in words)
    en = sum(w in _EN for w in words)
    if max(nl, en) < MIN_HITS or nl == en:
        return None
    if nl >= 2 * en:
        return "nl"
    if en >= 2 * nl:
        return "en"
    return None


def formality(text: str | None) -> str | None:
    """'u' when Dutch text addresses the reader as u/uw, else None (je is the default)."""
    return "u" if re.search(r"\b(u|uw|bent u|kunt u|heeft u)\b", (text or "").lower()) else None


def parse_choice(value: str | None) -> str | None:
    """A language answer ('Nederlands', 'English', 'NL', …) → 'nl' / 'en', else None."""
    low = records.clean(value, 40).lower().strip(" .")
    return next((code for code, words in _CHOICES.items() if low in words), None)


@dataclass(frozen=True)
class ContactLanguage:
    lang: str
    formality: str | None   # 'je' / 'u' for Dutch, None for English
    source: str             # a source name, or 'default'
    evidence: str
    offer_dutch: bool        # add the one-line offer to continue in Dutch

    def describe(self) -> str:
        how = f" ({self.formality})" if self.lang == "nl" else ""
        why = SOURCE_TEXT.get(self.source, "default: nothing captured yet")
        offer = "; Cloé offers Dutch" if self.offer_dutch else ""
        return f"{LANG_NAMES[self.lang]}{how}, {why}{offer}"


def contact_language(conn: sqlite3.Connection, person_id: int) -> ContactLanguage:
    row = conn.execute("SELECT lang, lang_source, lang_evidence, formality FROM person "
                       "WHERE id = ?", (person_id,)).fetchone()
    lang = row["lang"] if row and row["lang"] in LANGS else DEFAULT_LANG
    source = row["lang_source"] if row and row["lang"] in LANGS and row["lang_source"] \
        else "default"
    form = ((row["formality"] if row else None) or "je") if lang == "nl" else None
    offer = lang == "en" and source not in EXPLICIT_SOURCES
    return ContactLanguage(lang, form, source, (row["lang_evidence"] or "") if row else "",
                           offer)


def set_language(
    conn: sqlite3.Connection,
    person_id: int,
    lang: str,
    *,
    source: str,
    evidence: str,
    form: str | None = None,
    at: str | None = None,
) -> bool:
    """Record a person's language. An inferred guess never replaces an explicit choice,
    and an older one never replaces a newer one of the same strength. Returns True when
    something changed (and logs an event)."""
    if lang not in LANGS:
        raise ValueError(f"language must be one of {LANGS}")
    if source not in EXPLICIT_SOURCES + INFERRED_SOURCES:
        raise ValueError(f"unknown language source {source!r}")
    if form not in (None, "je", "u"):
        raise ValueError("formality must be je or u")
    row = conn.execute("SELECT lang, lang_source, lang_at, formality FROM person WHERE id = ?",
                       (person_id,)).fetchone()
    if row is None:
        raise ValueError(f"no person {person_id}")
    at = at or db.now()
    explicit_now = row["lang_source"] in EXPLICIT_SOURCES
    explicit_new = source in EXPLICIT_SOURCES
    if explicit_now and not explicit_new:
        return False
    if explicit_now == explicit_new and row["lang_at"] and at < row["lang_at"]:
        return False
    new_form = (form or row["formality"] or None) if lang == "nl" else None
    if (row["lang"], row["lang_source"], row["formality"]) == (lang, source, new_form):
        return False
    conn.execute("UPDATE person SET lang = ?, lang_source = ?, lang_evidence = ?, lang_at = ?, "
                 "formality = ? WHERE id = ?",
                 (lang, source, records.clean(evidence, 300), at, new_form, person_id))
    db.event(conn, "language", "language_set", ref=f"person:{person_id}",
             detail={"lang": lang, "source": source, "formality": new_form or ""})
    return True
