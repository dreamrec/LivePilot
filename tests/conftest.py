"""Pytest safety rails for LivePilot user-scoped persistence."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest


_SUITE_LIVEPILOT_HOME = Path(
    tempfile.mkdtemp(prefix="livepilot-pytest-home-")
).resolve()
os.environ["LIVEPILOT_HOME"] = str(_SUITE_LIVEPILOT_HOME)


@pytest.fixture(autouse=True)
def isolate_livepilot_home(tmp_path, monkeypatch):
    """Keep tests from writing to the operator's real ~/.livepilot tree.

    Some modules create store instances during import, so this file also sets a
    suite-level LIVEPILOT_HOME above before test collection begins. The fixture
    gives ordinary lazy store resolution a fresh per-test home.
    """
    monkeypatch.setenv("LIVEPILOT_HOME", str(tmp_path / "livepilot-home"))


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    shutil.rmtree(_SUITE_LIVEPILOT_HOME, ignore_errors=True)
