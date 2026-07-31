"""Regression test: commit_preview_variant must not block the asyncio event loop.

``commit_preview_variant`` is ``async def`` but, on a Wonder-linked accepted
commit, used to call ``session_continuity.tracker.record_turn_resolution``
directly. That function synchronously acquires the tracker module's plain
``threading.Lock`` and, while holding it, does blocking disk I/O
(``_project_store.save_turn`` -> ``os.fsync``). Calling it un-offloaded from
an async handler stalls the whole event loop — every other in-flight MCP
request — for the duration of the call, which gets worse whenever the lock
is contended (e.g. ``bind_project_store_from_session``'s merge loop holding
it across many sequential disk writes).

This test proves the loop stays responsive during that call by running a
cheap heartbeat coroutine concurrently with ``commit_preview_variant`` while
``record_turn_resolution`` is monkeypatched to a slow *synchronous* function.
Pre-fix (direct call, no ``asyncio.to_thread``), the heartbeat cannot tick
while the sync call is blocking the single OS thread the event loop runs on.
Post-fix (offloaded via ``asyncio.to_thread``), the sync call runs on a
worker thread and the heartbeat keeps ticking.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.preview_studio.engine import store_preview_set
from mcp_server.preview_studio.models import PreviewSet, PreviewVariant


def _make_set(set_id: str, variants: list[PreviewVariant]) -> PreviewSet:
    ps = PreviewSet(
        set_id=set_id,
        request_text="event-loop repro",
        strategy="creative_triptych",
        source_kernel_id="k",
        variants=variants,
        created_at_ms=int(time.time() * 1000),
    )
    store_preview_set(ps)
    return ps


def _executable_variant(variant_id: str) -> PreviewVariant:
    return PreviewVariant(
        variant_id=variant_id,
        label="strong",
        intent="executable plan",
        novelty_level=0.5,
        identity_effect="evolves",
        move_id="make_punchier",
        compiled_plan=[
            {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.5}},
        ],
        status="pending",
        taste_fit=0.55,
        what_preserved="core hook",
        why_it_matters="low-risk evolution",
    )


def test_commit_preview_variant_offloads_blocking_turn_resolution(monkeypatch):
    """Event loop must stay responsive while record_turn_resolution runs.

    A heartbeat coroutine ticks on a fast timer concurrently with the
    commit. If commit_preview_variant calls the (monkeypatched, slow) sync
    record_turn_resolution directly on the event-loop thread, the heartbeat
    starves for the whole blocking duration and its tick count stays near
    zero. If the call is properly offloaded via asyncio.to_thread, the
    heartbeat keeps ticking throughout.
    """
    import mcp_server.runtime.execution_router as execution_router
    import mcp_server.session_continuity.tracker as tracker_module
    from mcp_server.preview_studio.tools import commit_preview_variant
    from mcp_server.wonder_mode.session import WonderSession, store_wonder_session

    set_id = "ps_evloop_block"
    variant_id = "v_evloop_exec"
    _make_set(set_id, [_executable_variant(variant_id)])

    ws = WonderSession(
        session_id="ws_evloop_block",
        request_text="event-loop repro",
        preview_set_id=set_id,
        status="previewing",
        variants=[{"variant_id": variant_id, "family": "evolve"}],
    )
    store_wonder_session(ws)

    async def _fake_exec_async(
        steps, ableton=None, bridge=None, mcp_registry=None,
        ctx=None, stop_on_failure=True,
    ):
        return [
            SimpleNamespace(
                ok=True, tool=step.get("tool"), backend="remote_command",
                result={"ok": True}, error="",
            )
            for step in steps
        ]

    monkeypatch.setattr(execution_router, "execute_plan_steps_async", _fake_exec_async)

    BLOCK_SECONDS = 0.3
    HEARTBEAT_INTERVAL = 0.01

    def _slow_sync_record_turn_resolution(**kwargs):
        # Stands in for record_turn_resolution's real behavior: a
        # synchronous function that blocks the calling OS thread (in
        # production this is threading.Lock.acquire() + os.fsync()).
        time.sleep(BLOCK_SECONDS)
        return SimpleNamespace()

    monkeypatch.setattr(
        tracker_module, "record_turn_resolution", _slow_sync_record_turn_resolution
    )

    class _Ableton:
        def send_command(self, cmd, params=None):
            return {"ok": True}

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton()})

    heartbeat_count = 0

    async def _run():
        nonlocal heartbeat_count
        stop = asyncio.Event()

        async def _heartbeat():
            nonlocal heartbeat_count
            while not stop.is_set():
                heartbeat_count += 1
                await asyncio.sleep(HEARTBEAT_INTERVAL)

        hb_task = asyncio.create_task(_heartbeat())
        result = await commit_preview_variant(ctx, set_id=set_id, variant_id=variant_id)
        stop.set()
        await hb_task
        return result

    result = asyncio.run(_run())

    assert result["committed"] is True, result

    # Pre-fix: a direct blocking call starves the heartbeat for the full
    # BLOCK_SECONDS window -> heartbeat_count stays at ~1. Post-fix, offload
    # via asyncio.to_thread lets the heartbeat tick roughly every
    # HEARTBEAT_INTERVAL throughout the block -> ~30 ticks for these values.
    # Use a generous but discriminating threshold to avoid CI flakiness.
    min_expected_ticks = int((BLOCK_SECONDS / HEARTBEAT_INTERVAL) * 0.3)
    assert heartbeat_count >= min_expected_ticks, (
        f"event loop was blocked during commit_preview_variant's tracker "
        f"call — heartbeat only ticked {heartbeat_count} times during a "
        f"{BLOCK_SECONDS}s sync record_turn_resolution call (expected >= "
        f"{min_expected_ticks}); the sync tracker call must be offloaded "
        f"via asyncio.to_thread"
    )
