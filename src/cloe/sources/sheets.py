"""Read tabs of a Google Sheet through the Sheets API, read-only.

Auth is a service account (`GOOGLE_SERVICE_ACCOUNT_FILE`) with the `spreadsheets.readonly`
scope; the sheet is shared with the service account's address as Viewer. Cells come back
as formatted strings (`FORMATTED_VALUE`), so formulas are never read or evaluated.
Needs the `sheets` extra (`uv sync --extra sheets`).
"""

from __future__ import annotations

import re
from typing import Any, Protocol
from urllib.parse import quote

SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
VALUES_URL = "https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{range}"
MAX_ROWS = 20_000
TIMEOUT_S = 30

_SHEET_ID = re.compile(r"[A-Za-z0-9_-]{20,100}")


class SheetsError(Exception):
    pass


class _Session(Protocol):
    def get(self, url: str, params: dict[str, str], timeout: int) -> Any: ...


def session(service_account_file: str) -> _Session:
    """An authorised read-only HTTP session for the service account."""
    if not service_account_file:
        raise SheetsError("GOOGLE_SERVICE_ACCOUNT_FILE is not set")
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
    except ImportError as exc:
        raise SheetsError("the Google client is not installed: uv sync --extra sheets") from exc
    try:
        creds = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=[SCOPE]
        )
    except (OSError, ValueError) as exc:
        raise SheetsError(f"cannot read the service account key: {type(exc).__name__}") from exc
    return AuthorizedSession(creds)


def _cell(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return "" if value is None else str(value)


def read_tab(sess: _Session, sheet_id: str, tab: str, *, missing_ok: bool = False) -> list[list[str]]:
    """All rows of one tab as strings. `missing_ok`: a tab that doesn't exist reads as []."""
    if not _SHEET_ID.fullmatch(sheet_id or ""):
        raise SheetsError("CLOE_JOINFORM_SHEET_ID does not look like a sheet id")
    a1 = "'" + tab.replace("'", "''") + "'!A1:AZ"
    url = VALUES_URL.format(sheet_id=sheet_id, range=quote(a1, safe=""))
    params = {"majorDimension": "ROWS", "valueRenderOption": "FORMATTED_VALUE",
              "dateTimeRenderOption": "FORMATTED_STRING"}
    resp = sess.get(url, params=params, timeout=TIMEOUT_S)
    if resp.status_code == 400 and missing_ok:
        return []
    if resp.status_code != 200:
        hint = {403: " (is the sheet shared with the service account?)",
                404: " (wrong sheet id?)"}.get(resp.status_code, "")
        raise SheetsError(f"Sheets API returned {resp.status_code} for tab {tab!r}{hint}")
    values = resp.json().get("values", [])
    if not isinstance(values, list) or len(values) > MAX_ROWS:
        raise SheetsError(f"unexpected values for tab {tab!r}")
    return [[_cell(v) for v in row] for row in values if isinstance(row, list)]
