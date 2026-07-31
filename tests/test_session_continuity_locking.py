"""Regression tests for session_continuity tracker thread-safety.

The tracker's module globals (``_threads``/``_turns``/``_story``/
``_project_store``) are mutated from both threadpooled sync tools and
event-loop callers (wonder_mode, preview_studio, the lifespan bind) but had
no lock — the last unlocked module-global cache from the July sweep
(preview_studio/engine.py's ``_preview_sets_lock`` is the mirrored pattern).

Two races pinned here:

1. Reader iteration vs writer insert — ``list_open_threads()`` /
   ``get_session_story()`` iterate ``_threads.values()`` while
   ``open_thread()`` inserts → ``RuntimeError: dictionary changed size
   during iteration`` under contention.
2. The bind merge-and-swap — ``bind_project_store_from_session`` reads
   ``_threads``/``_turns`` into its merge, then REASSIGNS both. A write
   landing between the merge read and the swap was silently discarded
   (data loss). The unlocked window is only a few statements wide, so the
   test injects a delay into it via ``TurnResolution.from_dict`` (which the
   merge calls between the ``_threads`` read and the swap) and fires an
   ``open_thread`` from inside that window — deterministically lost without
   the lock, blocked-then-merged with it.
"""
from __future__ import annotations

import sys
import tempfile
import threading
import time
from pathlib import Path

import mcp_server.session_continuity.tracker as tracker
from mcp_server.persistence.project_store import ProjectStore
from mcp_server.session_continuity.models import TurnResolution
from mcp_server.session_continuity.tracker import (
    bind_project_store_from_session,
    get_session_story,
    list_open_threads,
    open_thread,
    record_turn_resolution,
    reset_story,
    resume_last_intent,
)


def setup_function():
    reset_story()


def teardown_function():
    reset_story()


def test_concurrent_open_thread_and_readers_no_runtime_error():
    """Readers iterating _threads must not see the dict resize mid-iteration."""
    errors: list[BaseException] = []
    stop = threading.Event()
    # Force frequent preemption so an unlocked reader is reliably suspended
    # mid-iteration while a writer inserts.
    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        def writer(worker: int):
            try:
                for i in range(400):
                    open_thread(f"thread-{worker}-{i}", domain="test")
            except BaseException as exc:  # noqa: BLE001 — capture everything
                errors.append(exc)
            finally:
                stop.set()

        def reader():
            try:
                while not stop.is_set():
                    list_open_threads()
                    resume_last_intent()
                    get_session_story({})
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        writers = [threading.Thread(target=writer, args=(w,)) for w in range(4)]
        readers = [threading.Thread(target=reader) for _ in range(3)]
        for t in readers + writers:
            t.start()
        for t in writers:
            t.join(timeout=60)
        stop.set()
        for t in readers:
            t.join(timeout=60)
    finally:
        sys.setswitchinterval(old_interval)

    assert not errors, f"concurrent tracker access raised: {errors[:3]}"
    assert len(tracker._threads) == 4 * 400


def test_write_during_bind_merge_window_is_not_lost():
    """A thread opened while the bind merge is between its ``_threads`` read
    and the ``_threads = merged_threads`` swap must survive the swap."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        session_info = {"tempo": 120.0, "tracks": [{"index": 0, "name": "Perc"}]}

        import mcp_server.persistence.project_store as ps_mod

        class _TempProjectStore(ProjectStore):
            def __init__(self, project_id, base_dir=None):
                super().__init__(project_id, base_dir=base)

        orig_store = ps_mod.ProjectStore
        ps_mod.ProjectStore = _TempProjectStore
        try:
            # Seed disk with one turn so the merge's TurnResolution.from_dict
            # loop (our injection point inside the window) actually runs.
            assert bind_project_store_from_session(session_info) is not None
            record_turn_resolution("seed turn", outcome="accepted")
            reset_story()  # drop in-memory state + store; disk survives

            in_window = threading.Event()
            written = threading.Event()
            orig_from_dict = TurnResolution.from_dict.__func__

            @classmethod
            def slow_from_dict(cls, data):
                # Signal the writer that bind is now inside the window
                # (after the _threads unflushed-read, before the swap),
                # then give it time to land its write there. With the lock
                # in place the writer BLOCKS on open_thread instead, so the
                # wait simply times out — keep it short.
                if not in_window.is_set():
                    in_window.set()
                    written.wait(timeout=2)
                    time.sleep(0.05)
                return orig_from_dict(cls, data)

            def writer():
                in_window.wait(timeout=10)
                open_thread("landed in the merge window", domain="test")
                written.set()

            TurnResolution.from_dict = slow_from_dict
            writer_thread = threading.Thread(target=writer)
            writer_thread.start()
            try:
                project_id = bind_project_store_from_session(session_info)
            finally:
                writer_thread.join(timeout=30)
                TurnResolution.from_dict = classmethod(orig_from_dict)

            assert project_id is not None
            descriptions = [t.description for t in tracker._threads.values()]
            assert "landed in the merge window" in descriptions, (
                "thread opened during the bind merge window was discarded "
                "by the _threads swap (unlocked merge-and-swap race)"
            )
        finally:
            ps_mod.ProjectStore = orig_store


def test_get_session_story_returns_isolated_snapshot_not_shared_singleton():
    """A caller's get_session_story() result must survive a concurrent
    second call, not get overwritten by it.

    get_session_story() mutates the module-level ``_story`` singleton
    under the lock, then (pre-fix) returned that same object by
    reference — the mutation is locked, but callers serialize it
    (``.to_dict()``) *after* the lock is released. Since every call
    reuses the one singleton, caller B's get_session_story() landing
    between caller A getting its result and A calling ``.to_dict()`` on
    it would overwrite identity_summary/song_brain_id/threads/turns
    before A ever reads them — a cross-request data leak, not a stale
    read. This test drives that exact interleave with explicit
    synchronization (not timing luck): A gets its result, signals, waits
    for B to run its own call and mutate the singleton, THEN A
    serializes. Pre-fix this observes B's data; post-fix (isolated
    deepcopy snapshot taken under the lock) it must still observe A's.
    """
    a_got_result = threading.Event()
    b_done = threading.Event()
    result_holder: dict = {}

    def caller_a():
        story = get_session_story({"identity_core": "A-identity", "brain_id": "brainA"})
        a_got_result.set()
        # Give caller B a chance to run its own get_session_story() and
        # mutate the shared singleton before A finally serializes what it
        # believes is ITS OWN view.
        b_done.wait(timeout=5)
        result_holder["dict"] = story.to_dict()

    def caller_b():
        a_got_result.wait(timeout=5)
        get_session_story({"identity_core": "B-identity", "brain_id": "brainB"})
        b_done.set()

    ta = threading.Thread(target=caller_a)
    tb = threading.Thread(target=caller_b)
    ta.start()
    tb.start()
    ta.join(timeout=10)
    tb.join(timeout=10)

    assert "dict" in result_holder, "caller A never completed"
    serialized = result_holder["dict"]
    assert serialized["identity_summary"] == "A-identity", (
        f"caller A's serialized story leaked caller B's identity_summary: {serialized}"
    )
    assert serialized["song_brain_id"] == "brainA", (
        f"caller A's serialized story leaked caller B's song_brain_id: {serialized}"
    )
