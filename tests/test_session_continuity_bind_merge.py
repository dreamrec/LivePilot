"""Regression tests for the lazy/late project-store bind merge.

The bug: ``bind_project_store_from_session`` used to UNCONDITIONALLY reassign
the module-global ``_threads`` and ``_turns`` from disk. When the startup bind
could not reach Ableton (the exact case the lazy bind path exists for), the
tracker accepted ``open_thread`` / ``record_turn_resolution`` with NO store
attached — those entries lived only in memory and were never flushed. The
later bind then discarded them (silent data loss).

These tests pin the fix: a late bind MERGES — in-memory entries absent from
disk survive AND get persisted, while disk stays the truth for ids it holds.
"""

import tempfile
from pathlib import Path

import mcp_server.session_continuity.tracker as tracker
from mcp_server.persistence.project_store import ProjectStore
from mcp_server.session_continuity.tracker import (
    bind_project_store_from_session,
    open_thread,
    record_turn_resolution,
    reset_story,
)


def setup_function():
    reset_story()


def _bind_with_tempdir(monkeypatch_dir: Path, session_info: dict):
    """Bind via the real ProjectStore but rooted under a temp dir.

    ``bind_project_store_from_session`` imports ProjectStore *inside* the
    function from ``..persistence.project_store``, so we patch the source
    module's class with a thin subclass that injects ``base_dir``. This
    exercises the real merge path without writing under ``~/.livepilot``.
    """
    import mcp_server.persistence.project_store as ps_mod

    class _TempProjectStore(ProjectStore):
        def __init__(self, project_id, base_dir=None):
            super().__init__(project_id, base_dir=monkeypatch_dir)

    orig = ps_mod.ProjectStore
    ps_mod.ProjectStore = _TempProjectStore
    try:
        return bind_project_store_from_session(session_info)
    finally:
        ps_mod.ProjectStore = orig


def test_inmemory_thread_survives_late_bind():
    """(a) no store bound, (b) open a thread in-memory, (c) bind a store that
    lacks it → the in-memory thread must survive AND be persisted."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        session_info = {"tempo": 128.0, "tracks": [{"index": 0, "name": "Drums"}]}

        # (a) no store bound yet
        assert tracker._project_store is None
        # (b) open a thread purely in-memory (no flush possible)
        thread = open_thread("finish the chorus lift", domain="arrangement")
        assert tracker._project_store is None  # still unbound — proves no flush

        # (c) bind a store whose disk state does NOT contain this thread
        project_id = _bind_with_tempdir(base, session_info)
        assert project_id is not None

        # Survivor must still be live in memory.
        assert thread.thread_id in tracker._threads
        assert tracker._threads[thread.thread_id].description == "finish the chorus lift"

        # ...and it must now be persisted to disk (so a rebind keeps it).
        on_disk = ProjectStore(project_id, base_dir=base).get_threads()
        assert any(t["thread_id"] == thread.thread_id for t in on_disk), \
            "unflushed in-memory thread was not persisted on bind"


def test_inmemory_turn_survives_late_bind():
    """Same scenario for turn resolutions (append-only history)."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        session_info = {"tempo": 128.0, "tracks": [{"index": 0, "name": "Bass"}]}

        assert tracker._project_store is None
        turn = record_turn_resolution("make it darker", outcome="accepted")
        assert tracker._project_store is None

        project_id = _bind_with_tempdir(base, session_info)
        assert project_id is not None

        assert any(t.turn_id == turn.turn_id for t in tracker._turns)
        on_disk = ProjectStore(project_id, base_dir=base).get_turns()
        assert any(t["turn_id"] == turn.turn_id for t in on_disk), \
            "unflushed in-memory turn was not persisted on bind"


def test_disk_truth_merged_with_memory():
    """Disk entries and unflushed in-memory entries coexist after bind — disk
    is not clobbered by memory, and memory is not clobbered by disk."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        session_info = {"tempo": 124.0, "tracks": [{"index": 0, "name": "Pad"}]}

        # Pre-seed disk with a thread + turn from a "previous session".
        project_id_seed = None
        # Compute the project id the bind will use, then seed that store.
        from mcp_server.persistence.project_store import project_hash
        project_id_seed = project_hash(session_info)
        seed = ProjectStore(project_id_seed, base_dir=base)
        seed.save_thread({"thread_id": "disk_thread", "description": "from disk", "status": "open"})
        seed.save_turn({"turn_id": "disk_turn", "outcome": "accepted"})

        # In-memory (unbound) work this session.
        mem_thread = open_thread("from memory", domain="mix")
        mem_turn = record_turn_resolution("memory request", outcome="accepted")

        project_id = _bind_with_tempdir(base, session_info)
        assert project_id == project_id_seed

        # Both disk and memory threads present in live state.
        assert "disk_thread" in tracker._threads
        assert mem_thread.thread_id in tracker._threads

        # Both disk and memory turns present in live state.
        turn_ids = {t.turn_id for t in tracker._turns}
        assert "disk_turn" in turn_ids
        assert mem_turn.turn_id in turn_ids

        # Disk now holds the merged superset.
        final = ProjectStore(project_id, base_dir=base)
        disk_thread_ids = {t["thread_id"] for t in final.get_threads()}
        assert {"disk_thread", mem_thread.thread_id} <= disk_thread_ids
        disk_turn_ids = {t["turn_id"] for t in final.get_turns()}
        assert {"disk_turn", mem_turn.turn_id} <= disk_turn_ids


def test_disk_wins_on_thread_id_conflict():
    """If an id exists both on disk and in memory, disk is the persisted truth
    and is not overwritten by the (older, unflushed) in-memory copy."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        session_info = {"tempo": 100.0, "tracks": [{"index": 0, "name": "Keys"}]}
        from mcp_server.persistence.project_store import project_hash
        pid = project_hash(session_info)

        seed = ProjectStore(pid, base_dir=base)
        seed.save_thread({"thread_id": "shared", "description": "DISK", "status": "resolved"})

        # Force an in-memory thread with the SAME id but stale content.
        from mcp_server.session_continuity.models import CreativeThread
        tracker._threads["shared"] = CreativeThread(
            thread_id="shared", description="MEMORY", status="open"
        )

        _bind_with_tempdir(base, session_info)

        # Disk truth wins on conflict.
        assert tracker._threads["shared"].description == "DISK"
        assert tracker._threads["shared"].status == "resolved"


def test_same_session_identity_survives_mutable_edits_and_new_set_rebinds():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        first = {
            "session_instance_id": "song-1",
            "tempo": 120.0,
            "tracks": [{"index": 0, "name": "Bass"}],
        }
        first_id = _bind_with_tempdir(base, first)
        first_store = tracker._project_store

        edited = {
            "session_instance_id": "song-1",
            "tempo": 132.0,
            "tracks": [{"index": 0, "name": "Renamed Bass"}],
        }
        assert _bind_with_tempdir(base, edited) == first_id
        assert tracker._project_store is first_store

        new_set = {
            "session_instance_id": "song-2",
            "tempo": 132.0,
            "tracks": [{"index": 0, "name": "Renamed Bass"}],
        }
        second_id = _bind_with_tempdir(base, new_set)
        assert second_id != first_id
        assert tracker._bound_session_instance_id == "song-2"


def test_new_session_does_not_inherit_previous_project_threads():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        _bind_with_tempdir(base, {"session_instance_id": "song-a"})
        open_thread("belongs only to A", domain="arrangement")
        assert tracker._threads

        _bind_with_tempdir(base, {"session_instance_id": "song-b"})
        assert not tracker._threads
