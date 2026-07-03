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


def _reset_persistence_project_roots() -> None:
    """Clear module-level project-root seams between tests.

    Individual tests may monkeypatch these globals. Resetting them here keeps
    lazy default services pointed at the per-test LIVEPILOT_HOME instead of a
    stale fixture path or the operator's real project ledger.
    """
    from mcp_server.persistence import agent_focus
    from mcp_server.persistence import briefs
    from mcp_server.persistence import layer_groups
    from mcp_server.persistence import orchestration_queue
    from mcp_server.persistence import production_context
    from mcp_server.persistence import project_store
    from mcp_server.persistence import track_annotations

    for module in (
        agent_focus,
        briefs,
        layer_groups,
        orchestration_queue,
        production_context,
        project_store,
        track_annotations,
    ):
        if hasattr(module, "_PROJECTS_DIR"):
            module._PROJECTS_DIR = None


@pytest.fixture(autouse=True)
def isolate_livepilot_home(tmp_path, monkeypatch):
    """Keep tests from writing to the operator's real ~/.livepilot tree.

    Some modules create store instances during import, so this file also sets a
    suite-level LIVEPILOT_HOME above before test collection begins. The fixture
    gives ordinary lazy store resolution a fresh per-test home.
    """
    monkeypatch.setenv("LIVEPILOT_HOME", str(tmp_path / "livepilot-home"))
    _reset_persistence_project_roots()
    yield
    _reset_persistence_project_roots()


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    shutil.rmtree(_SUITE_LIVEPILOT_HOME, ignore_errors=True)
