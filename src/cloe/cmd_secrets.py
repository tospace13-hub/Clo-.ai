"""`cloe secrets list|set|delete|move`: Cloé's settings in the macOS Keychain (keychain.py).
Values are never printed."""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from pathlib import Path

from cloe import config, keychain


def _err(msg: str) -> int:
    print(f"FAIL {msg}", file=sys.stderr)
    return 1


def _file_values(settings: config.Settings) -> dict[str, str]:
    path = settings.env_path
    return config.parse_env(path.read_text(encoding="utf-8")) if path.exists() else {}


def _blank_in_env(path: Path, names: set[str]) -> None:
    """Set each name's line in .env to an empty value, noting where it lives now."""
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if m and m.group(1) in names:
            line = f"{m.group(1)}=  # in the macOS Keychain (cloe secrets list)"
        out.append(line)
    mode = path.stat().st_mode & 0o777
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    path.chmod(mode)


def _check(name: str) -> str | None:
    if name not in config.SETTING_NAMES:
        return f"{name} is not one of Cloé's settings (see `cloe secrets list`)"
    if not keychain.enabled():
        return f"the macOS Keychain can't be used here: {keychain.why_not()}"
    return None


def cmd_list(args: argparse.Namespace, settings: config.Settings) -> int:
    stored = keychain.load(config.SETTING_NAMES) if keychain.enabled() else {}
    in_file = _file_values(settings)
    for name in config.SETTING_NAMES:
        if os.environ.get(name):
            where = "environment"
        elif name in stored:
            where = "Keychain"
        elif in_file.get(name):
            where = ".env (plain text)" if name in config.SECRET_NAMES else ".env"
        else:
            where = "-"
        secret = " (secret)" if name in config.SECRET_NAMES else ""
        print(f"{name:<36} {where}{secret}")
    if not keychain.enabled():
        print(f"WARN macOS Keychain not used: {keychain.why_not()}")
    return 0


def cmd_set(args: argparse.Namespace, settings: config.Settings) -> int:
    if why := _check(args.name):
        return _err(why)
    if args.file:
        path = Path(args.file).expanduser()
        if not path.is_file() or path.stat().st_size > 100_000:
            return _err(f"{path}: not a file, or larger than 100 KB")
        value = path.read_text(encoding="utf-8").strip()
    else:
        value = getpass.getpass(f"{args.name} (input hidden): ").strip()
    if not value:
        return _err("empty value: nothing stored")
    try:
        keychain.put(args.name, value)
    except keychain.KeychainError as exc:
        return _err(str(exc))
    print(f"OK   {args.name} stored in the macOS Keychain (service \"{keychain.SERVICE}\")")
    if _file_values(settings).get(args.name):
        print(f"WARN {args.name} also has a value in .env; the Keychain's wins. Blank it with "
              "`cloe secrets move`")
    if args.file:
        print(f"     you can now delete {args.file}, or keep it somewhere safe as a backup")
    return 0


def cmd_delete(args: argparse.Namespace, settings: config.Settings) -> int:
    if why := _check(args.name):
        return _err(why)
    try:
        gone = keychain.delete(args.name)
    except keychain.KeychainError as exc:
        return _err(str(exc))
    print(f"OK   {args.name} " + ("removed from the Keychain" if gone else
                                  "was not in the Keychain"))
    return 0


def cmd_move(args: argparse.Namespace, settings: config.Settings) -> int:
    if not keychain.enabled():
        return _err(f"the macOS Keychain can't be used here: {keychain.why_not()}")
    in_file = _file_values(settings)
    names = config.SETTING_NAMES if args.all else config.SECRET_NAMES
    todo = [n for n in names if in_file.get(n)]
    if not todo:
        print("OK   nothing to move: .env holds no " + ("settings" if args.all else "secrets"))
        return 0
    moved = set()
    for name in todo:
        try:
            keychain.put(name, in_file[name])
        except keychain.KeychainError as exc:
            print(f"FAIL {exc}; it stays in .env", file=sys.stderr)
            continue
        moved.add(name)
    if moved:
        _blank_in_env(settings.env_path, moved)
    print(f"OK   moved to the macOS Keychain and blanked in .env: {', '.join(sorted(moved))}")
    return 0 if moved == set(todo) else 1


def register(sub: argparse._SubParsersAction) -> None:
    s = sub.add_parser("secrets", help="settings and secrets in the macOS Keychain"
                       ).add_subparsers(dest="action", required=True)
    s.add_parser("list", help="every setting and where it comes from (never its value)"
                 ).set_defaults(func=cmd_list)
    p = s.add_parser("set", help="store one setting in the Keychain (asks for it, hidden)")
    p.add_argument("name")
    p.add_argument("--file", help="read the value from a file (e.g. the service account "
                   "key for GOOGLE_SERVICE_ACCOUNT_JSON)")
    p.set_defaults(func=cmd_set)
    p = s.add_parser("delete", help="remove one setting from the Keychain")
    p.add_argument("name")
    p.set_defaults(func=cmd_delete)
    p = s.add_parser("move", help="move the secrets in .env into the Keychain and blank "
                     "them in .env")
    p.add_argument("--all", action="store_true", help="every setting, not only secrets")
    p.set_defaults(func=cmd_move)
