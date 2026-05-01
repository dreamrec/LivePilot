"""Applier — shared Phase-3 executor for fast / full / develop compose modes.

Concentrates pre-flight (analyzer load + bridge connect + handshake retry)
and post-flight (monitoring state + back_to_arranger) so fixes for
BUG-FULL-MODE-14 (bridge race) and BUG-FULL-MODE-17 (manual arm required)
land once across all three modes instead of three times.

Functions are dependency-injected (not imported directly) so unit tests can
mock them without monkey-patching.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


# Type aliases
AsyncCtxFn = Callable[[Any], Awaitable[Any]]
AsyncTrackFn = Callable[..., Awaitable[Any]]


class Applier:
    """Shared pre-flight + apply + post-flight skeleton for compose modes.

    v1.24 Phase 1: pre-flight + post-flight only. The `run()` method (full
    plan execution) stays a stub; each mode's apply.py wires its own
    plan-execution loop using `Applier.preflight()` and `Applier.postflight()`
    around it.

    Future phases may extend this with a unified plan-walker.
    """

    def __init__(
        self,
        *,
        ensure_analyzer_fn: AsyncCtxFn,
        reconnect_bridge_fn: AsyncCtxFn,
        bridge_ping_fn: AsyncCtxFn,
        set_track_input_monitoring_fn: Optional[AsyncTrackFn] = None,
        back_to_arranger_fn: Optional[AsyncCtxFn] = None,
        handshake_max_attempts: int = 3,
        handshake_gap_seconds: float = 0.2,
    ):
        self._ensure_analyzer_fn = ensure_analyzer_fn
        self._reconnect_bridge_fn = reconnect_bridge_fn
        self._bridge_ping_fn = bridge_ping_fn
        self._set_track_input_monitoring_fn = set_track_input_monitoring_fn
        self._back_to_arranger_fn = back_to_arranger_fn
        self._handshake_max_attempts = handshake_max_attempts
        self._handshake_gap_seconds = handshake_gap_seconds

    # ── pre-flight ──────────────────────────────────────────────────

    async def preflight(self, ctx: Any) -> dict:
        """Load analyzer, connect bridge, handshake until ping succeeds.

        Fixes BUG-FULL-MODE-14: the previous code returned success on
        bridge.connect() but the M4L JS listener takes 100-500ms to bind
        the UDP socket. Without the handshake retry loop, the next
        bridge-using call (load_sample_to_simpler etc.) fails with
        "UDP bridge is not connected".

        Returns dict with keys: analyzer_status, bridge_connected,
        handshake_attempts, and optionally handshake_error if all
        retries failed.
        """
        analyzer_result = await self._ensure_analyzer_fn(ctx)
        analyzer_status = (
            analyzer_result.get("status", "unknown")
            if isinstance(analyzer_result, dict)
            else "unknown"
        )

        bridge_result = await self._reconnect_bridge_fn(ctx)
        bridge_connected_initial = (
            bridge_result.get("connected", False)
            if isinstance(bridge_result, dict)
            else False
        )

        handshake_attempts = 0
        handshake_error: Optional[str] = None
        bridge_ready = False

        if bridge_connected_initial:
            for attempt in range(1, self._handshake_max_attempts + 1):
                handshake_attempts = attempt
                try:
                    await self._bridge_ping_fn(ctx)
                    bridge_ready = True
                    break
                except Exception as exc:
                    handshake_error = str(exc)
                    logger.debug(
                        "Applier preflight handshake attempt %d failed: %s",
                        attempt,
                        exc,
                    )
                    if attempt < self._handshake_max_attempts:
                        await asyncio.sleep(self._handshake_gap_seconds)

        result = {
            "analyzer_status": analyzer_status,
            "bridge_connected": bridge_ready,
            "handshake_attempts": handshake_attempts,
        }
        if not bridge_ready and handshake_error is not None:
            result["handshake_error"] = handshake_error
        return result

    # ── post-flight ─────────────────────────────────────────────────

    async def postflight(
        self,
        ctx: Any,
        applied_track_indices: list[int],
    ) -> dict:
        """Set monitoring=Auto on each newly-created track, then back_to_arranger.

        BUG-FIX (post-Phase-4-Task-4 live test): the original BUG-FULL-MODE-17
        fix set monitoring to state=0 ("In"), which is WRONG. State codes:
            0 = In   (always pass input through — leaves track "hot")
            1 = Auto (monitor when armed + recording — DEFAULT for new tracks)
            2 = Off  (never monitor)

        New tracks default to Auto (1) and arrangement clips already play
        correctly with Auto. The actual fix for "manual arm required" is
        back_to_arranger alone — clearing the session-vs-arrangement
        override flag. We set state=Auto here defensively in case any
        other code path moved monitoring away from default.

        applied_track_indices: list of track indices that were created
        during this apply pass. Empty list (e.g. develop mode writing
        only session clips, no new tracks) skips the per-track step but
        still calls back_to_arranger.
        """
        tracks_set = 0
        if self._set_track_input_monitoring_fn is not None:
            for track_index in applied_track_indices:
                try:
                    # state=1 (Auto) — the default for new tracks. NOT 0 (In).
                    await self._set_track_input_monitoring_fn(
                        ctx, track_index=track_index, state=1
                    )
                    tracks_set += 1
                except Exception as exc:
                    logger.warning(
                        "Applier postflight set_monitoring failed for track %d: %s",
                        track_index,
                        exc,
                    )

        back_to_arranger_ok = False
        if self._back_to_arranger_fn is not None:
            try:
                await self._back_to_arranger_fn(ctx)
                back_to_arranger_ok = True
            except Exception as exc:
                logger.warning("Applier postflight back_to_arranger failed: %s", exc)

        return {
            "tracks_set": tracks_set,
            "back_to_arranger": back_to_arranger_ok,
        }

    # ── stub run() — not used in v1.24 ──────────────────────────────

    async def run(self, ctx: Any, plan: list) -> dict:
        """Stub kept from Task 1 — full plan-walk implementation deferred.

        Phase 1 only extracts pre/post-flight. Each mode's apply.py
        continues to execute its own plan loop, just sandwiched by
        ``preflight()`` and ``postflight()``.
        """
        return {"status": "stub"}
