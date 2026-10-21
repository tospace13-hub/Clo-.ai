"""Shared fixtures: the local http.server from test_fetch, for the crawl tests too, and a
work-order folder per test (without an API key the default engine writes work orders, and
none may land in the repository's docs/workorders)."""

import pytest
from test_fetch import routes, server  # noqa: F401

from cloe import workorders


@pytest.fixture(autouse=True)
def _workorder_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(workorders, "WORKORDER_DIR", tmp_path / "docs" / "workorders")
