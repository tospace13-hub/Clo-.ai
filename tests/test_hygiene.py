"""Nothing secret or personal is committed. Runs on `git ls-files`; no network."""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Built from parts so this file does not match itself.
API_KEY = re.compile("sk" + "-ant-" + r"[A-Za-z0-9_\-]{20,}")
TWILIO_SID = re.compile("A" + "C" + r"[0-9a-f]{32}\b")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")

EMAIL_OK_DOMAINS = ("example.org", "example.com", "example.net", "example.nl")
EMAIL_OK_TLDS = (".example", ".test", ".invalid")
EMAIL_OK_ADDRESSES = {"hello@space13.to", "privacy@space13.to"}  # TOS13's public addresses
EMAIL_FREE_PATHS = ("docs/", "tests/fixtures/")


def tracked_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [f for f in out.stdout.splitlines() if (ROOT / f).is_file()]


def read(path: str) -> str:
    try:
        return (ROOT / path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def email_allowed(address: str) -> bool:
    address = address.lower()
    domain = address.rsplit("@", 1)[1]
    return (
        address in EMAIL_OK_ADDRESSES
        or domain in EMAIL_OK_DOMAINS
        or domain.endswith(EMAIL_OK_TLDS)
    )


def test_env_file_not_tracked():
    assert ".env" not in tracked_files()


def test_no_api_keys_or_twilio_sids():
    hits = [f for f in tracked_files() if API_KEY.search(read(f)) or TWILIO_SID.search(read(f))]
    assert hits == []


def test_no_personal_emails_outside_docs_and_fixtures():
    hits = []
    for f in tracked_files():
        if f.startswith(EMAIL_FREE_PATHS):
            continue
        for m in EMAIL.finditer(read(f)):
            if not email_allowed(m.group(0)):
                hits.append(f"{f}: {m.group(0)}")
    assert hits == []


def test_patterns_work():
    assert API_KEY.search("key = " + "sk" + "-ant-" + "a" * 30)
    assert TWILIO_SID.search("A" + "C" + "0" * 32)
    assert not email_allowed("someone@" + "gmail.com")
    assert email_allowed("x@example.org") and email_allowed("hello@space13.to")
