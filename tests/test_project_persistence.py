"""Tests for per-project persistent state."""

import tempfile
from pathlib import Path

from mcp_server.persistence.project_store import ProjectStore, project_hash


# ── Project identity ─────────────────────────────────────────────


def test_project_hash_stable():
    info = {"tempo": 120.0, "tracks": [{"name": "Drums"}, {"name": "Bass"}]}
    h1 = project_hash(info)
    h2 = project_hash(info)
    assert h1 == h2
    assert len(h1) == 12


def test_project_hash_differs():
    info1 = {"tempo": 120.0, "tracks": [{"name": "Drums"}]}
    info2 = {"tempo": 128.0, "tracks": [{"name": "Drums"}]}
    assert project_hash(info1) != project_hash(info2)


# ── Thread persistence ───────────────────────────────────────────


def test_thread_persists():
    with tempfile.TemporaryDirectory() as d:
        store = ProjectStore("proj1", base_dir=Path(d))
        store.save_thread({"thread_id": "t1", "description": "Chorus lift", "status": "open"})

        store2 = ProjectStore("proj1", base_dir=Path(d))
        threads = store2.get_threads()
        assert any(t["thread_id"] == "t1" for t in threads)


def test_thread_update():
    with tempfile.TemporaryDirectory() as d:
        store = ProjectStore("proj1", base_dir=Path(d))
        store.save_thread({"thread_id": "t1", "description": "Chorus", "status": "open"})
        store.save_thread({"thread_id": "t1", "description": "Chorus", "status": "resolved"})

        threads = ProjectStore("proj1", base_dir=Path(d)).get_threads()
        t = next(t for t in threads if t["thread_id"] == "t1")
        assert t["status"] == "resolved"
        assert len(threads) == 1  # no duplicate


# ── Turn persistence ─────────────────────────────────────────────


def test_turn_persists():
    with tempfile.TemporaryDirectory() as d:
        store = ProjectStore("proj1", base_dir=Path(d))
        store.save_turn({"turn_id": "tr1", "outcome": "accepted"})

        turns = ProjectStore("proj1", base_dir=Path(d)).get_turns()
        assert any(t["turn_id"] == "tr1" for t in turns)


def test_turn_capped():
    with tempfile.TemporaryDirectory() as d:
        store = ProjectStore("proj1", base_dir=Path(d))
        for i in range(60):
            store.save_turn({"turn_id": f"tr_{i}", "outcome": "accepted"})

        turns = ProjectStore("proj1", base_dir=Path(d)).get_turns()
        assert len(turns) == 50  # capped


# ── Wonder outcomes ──────────────────────────────────────────────


def test_wonder_outcome_persists():
    with tempfile.TemporaryDirectory() as d:
        store = ProjectStore("proj1", base_dir=Path(d))
        store.save_wonder_outcome({"session_id": "ws1", "outcome": "committed"})

        outcomes = ProjectStore("proj1", base_dir=Path(d)).get_wonder_outcomes()
        assert any(o["session_id"] == "ws1" for o in outcomes)


# ── Project isolation ────────────────────────────────────────────


def test_different_projects_isolated():
    with tempfile.TemporaryDirectory() as d:
        s1 = ProjectStore("proj_a", base_dir=Path(d))
        s2 = ProjectStore("proj_b", base_dir=Path(d))

        s1.save_thread({"thread_id": "ta", "description": "A"})
        s2.save_thread({"thread_id": "tb", "description": "B"})

        assert len(ProjectStore("proj_a", base_dir=Path(d)).get_threads()) == 1
        assert len(ProjectStore("proj_b", base_dir=Path(d)).get_threads()) == 1
        assert ProjectStore("proj_a", base_dir=Path(d)).get_threads()[0]["thread_id"] == "ta"
