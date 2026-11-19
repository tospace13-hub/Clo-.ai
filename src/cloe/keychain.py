"""Cloé's settings and secrets in the macOS Keychain (team, 2026-11-19).

Each setting is one generic-password item: service `cloe`, account = the setting's name
(e.g. `ANTHROPIC_API_KEY`). Keychain Access shows them under "cloe". `config.load` reads
them in this order:

    the process environment  >  the macOS Keychain  >  .env

So `.env` can keep only non-secret settings, or nothing at all.

The Keychain is used only on macOS, with the `keychain` extra installed (the `keyring`
library, which talks to the Security framework, never putting a value on a command line),
and not when `CLOE_KEYCHAIN=0`. Tests set that, so they never touch a real Keychain.
Values are never printed or logged: `cloe secrets list` shows names and where each comes
from.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Mapping
from typing import Any

SERVICE = "cloe"
PLATFORM = sys.platform
_backend: Any = None  # tests put a stand-in here


class KeychainError(RuntimeError):
    """The Keychain refused or failed (locked, access denied, not available)."""


def _keyring():
    if _backend is not None:
        return _backend
    try:
        import keyring
    except ImportError:
        return None
    return keyring


def enabled(environ: Mapping[str, str] | None = None) -> bool:
    """True on macOS with the `keychain` extra installed, unless CLOE_KEYCHAIN=0."""
    import os

    env = os.environ if environ is None else environ
    if env.get("CLOE_KEYCHAIN", "1").strip() == "0":
        return False
    return PLATFORM == "darwin" and _keyring() is not None


def why_not(environ: Mapping[str, str] | None = None) -> str:
    import os

    env = os.environ if environ is None else environ
    if env.get("CLOE_KEYCHAIN", "1").strip() == "0":
        return "CLOE_KEYCHAIN=0 turns it off"
    if PLATFORM != "darwin":
        return "the Keychain is macOS only"
    return "the keychain extra is not installed: uv sync --all-extras"


def get(name: str) -> str | None:
    kr = _keyring()
    if kr is None:
        return None
    try:
        return kr.get_password(SERVICE, name)
    except Exception as exc:  # noqa: BLE001 - any backend failure means "not available"
        raise KeychainError(f"the Keychain refused to read {name} ({type(exc).__name__})") \
            from None


def load(names: Iterable[str]) -> dict[str, str]:
    """{name: value} for every name that has a non-empty item."""
    found = {}
    for name in names:
        value = get(name)
        if value:
            found[name] = value
    return found


def put(name: str, value: str) -> None:
    kr = _keyring()
    if kr is None:
        raise KeychainError(why_not())
    try:
        kr.set_password(SERVICE, name, value)
    except Exception as exc:  # noqa: BLE001
        raise KeychainError(f"the Keychain refused to store {name} ({type(exc).__name__})") \
            from None
    if get(name) != value:
        raise KeychainError(f"{name} did not read back from the Keychain as stored")


def delete(name: str) -> bool:
    kr = _keyring()
    if kr is None:
        raise KeychainError(why_not())
    if get(name) is None:
        return False
    try:
        kr.delete_password(SERVICE, name)
    except Exception as exc:  # noqa: BLE001
        raise KeychainError(f"the Keychain refused to delete {name} ({type(exc).__name__})") \
            from None
    return True
