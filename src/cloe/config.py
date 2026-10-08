"""Settings from `.env` + the process environment (environment wins).

No dotenv / pydantic-settings: a ~30-line parser is enough and keeps the dependency list
short. The canary (see `untrusted.py`) is generated on first load and appended to `.env`.
"""

from __future__ import annotations

import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

EFFORTS = ("low", "medium", "high", "xhigh", "max")
DEFAULT_ENV_PATH = Path(".env")

_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def parse_env(text: str) -> dict[str, str]:
    """Parse `.env` text: KEY=VALUE lines, `#` comments, optional quotes, optional `export`."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = _LINE.match(raw)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if value[:1] in ('"', "'"):
            quote = value[0]
            end = value.find(quote, 1)
            value = value[1:end] if end != -1 else value[1:]
        else:
            value = re.split(r"(?:^|\s+)#", value, maxsplit=1)[0].strip()
        out[key] = value
    return out


def _csv(value: str, *, lower: bool = False) -> tuple[str, ...]:
    items = (v.strip() for v in value.split(","))
    return tuple((v.lower() if lower else v) for v in items if v)


def _hhmm(value: str) -> time:
    h, m = value.strip().split(":")
    return time(int(h), int(m))


def _quiet_hours(value: str) -> tuple[time, time]:
    start, end = value.split("-")
    return _hhmm(start), _hhmm(end)


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = field(default="", repr=False)
    model: str = "claude-opus-5-5"
    model_bulk: str = "claude-opus-5-5"
    effort: str = "high"
    db: Path = Path("data/cloe.db")
    send: bool = False
    approvers: tuple[str, ...] = ()
    timezone: str = "Europe/Amsterdam"
    quiet_hours: tuple[time, time] = (time(20, 0), time(8, 0))
    max_msgs_per_person_per_14d: int = 1
    allowed_link_domains: tuple[str, ...] = ()
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = field(default="", repr=False)
    mail_from: str = ""
    imap_host: str = ""
    imap_user: str = ""
    imap_password: str = field(default="", repr=False)
    twilio_account_sid: str = field(default="", repr=False)
    twilio_auth_token: str = field(default="", repr=False)
    twilio_from: str = ""
    webhook_secret: str = field(default="", repr=False)
    tell_db_url: str = field(default="", repr=False)
    tell_db_ca_cert: str = ""
    joinform_sheet_id: str = ""
    google_service_account_file: str = ""
    canary: str = field(default="", repr=False)
    env_path: Path = DEFAULT_ENV_PATH


def new_canary() -> str:
    return "cloe-canary-" + secrets.token_hex(12)


def _persist_canary(env_path: Path, canary: str) -> None:
    existed = env_path.exists()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    current = env_path.read_text(encoding="utf-8") if existed else ""
    prefix = "\n" if current and not current.endswith("\n") else ""
    with env_path.open("a", encoding="utf-8") as f:
        f.write(f"{prefix}# Generated on first run. Never share; see untrusted.py.\n")
        f.write(f"CLOE_CANARY={canary}\n")
    if not existed:
        env_path.chmod(0o600)


def load(
    env_path: Path | str | None = None,
    environ: dict[str, str] | None = None,
    *,
    persist_canary: bool = True,
) -> Settings:
    """Load settings. `environ` defaults to `os.environ`; it overrides values in `.env`."""
    path = Path(env_path) if env_path is not None else DEFAULT_ENV_PATH
    file_vals = parse_env(path.read_text(encoding="utf-8")) if path.exists() else {}
    env = {**file_vals, **(os.environ if environ is None else environ)}

    def get(key: str, default: str = "") -> str:
        value = env.get(key, "")
        return value if value != "" else default

    effort = get("CLOE_EFFORT", "high").lower()
    if effort not in EFFORTS:
        raise ValueError(f"CLOE_EFFORT must be one of {EFFORTS}, got {effort!r}")

    canary = get("CLOE_CANARY")
    if not canary:
        canary = new_canary()
        if persist_canary:
            _persist_canary(path, canary)

    model = get("CLOE_MODEL", "claude-opus-5-5")
    return Settings(
        anthropic_api_key=get("ANTHROPIC_API_KEY"),
        model=model,
        model_bulk=get("CLOE_MODEL_BULK", model),
        effort=effort,
        db=Path(get("CLOE_DB", "data/cloe.db")),
        send=get("CLOE_SEND", "0").strip() == "1",
        approvers=_csv(get("CLOE_APPROVERS"), lower=True),
        timezone=get("CLOE_TIMEZONE", "Europe/Amsterdam"),
        quiet_hours=_quiet_hours(get("CLOE_QUIET_HOURS", "20:00-08:00")),
        max_msgs_per_person_per_14d=int(get("CLOE_MAX_MSGS_PER_PERSON_PER_14D", "1")),
        allowed_link_domains=_csv(get("CLOE_ALLOWED_LINK_DOMAINS"), lower=True),
        smtp_host=get("SMTP_HOST"),
        smtp_port=int(get("SMTP_PORT", "587")),
        smtp_user=get("SMTP_USER"),
        smtp_password=get("SMTP_PASSWORD"),
        mail_from=get("MAIL_FROM"),
        imap_host=get("IMAP_HOST"),
        imap_user=get("IMAP_USER"),
        imap_password=get("IMAP_PASSWORD"),
        twilio_account_sid=get("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=get("TWILIO_AUTH_TOKEN"),
        twilio_from=get("TWILIO_FROM"),
        webhook_secret=get("CLOE_WEBHOOK_SECRET"),
        tell_db_url=get("TELL_DB_URL"),
        tell_db_ca_cert=get("TELL_DB_CA_CERT"),
        joinform_sheet_id=get("CLOE_JOINFORM_SHEET_ID"),
        google_service_account_file=get("GOOGLE_SERVICE_ACCOUNT_FILE"),
        canary=canary,
        env_path=path,
    )
