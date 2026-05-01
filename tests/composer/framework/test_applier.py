"""Tests for the shared Applier pre-flight + post-flight logic."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, call

from mcp_server.composer.framework.applier import Applier


# ── preflight basic ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_applier_preflight_loads_analyzer_and_connects_bridge():
    """Happy path: analyzer loads, bridge connects, ping succeeds first try."""
    ctx = MagicMock()
    ensure_analyzer = AsyncMock(return_value={"status": "ok"})
    reconnect_bridge = AsyncMock(return_value={"connected": True})
    bridge_ping = AsyncMock(return_value={"pong": True})

    applier = Applier(
        ensure_analyzer_fn=ensure_analyzer,
        reconnect_bridge_fn=reconnect_bridge,
        bridge_ping_fn=bridge_ping,
    )
    result = await applier.preflight(ctx)

    assert result["analyzer_status"] == "ok"
    assert result["bridge_connected"] is True
    assert result["handshake_attempts"] == 1
    ensure_analyzer.assert_awaited_once_with(ctx)
    reconnect_bridge.assert_awaited_once_with(ctx)
    bridge_ping.assert_awaited_once()


# ── preflight bridge handshake retry (BUG-FULL-MODE-14) ──────────────

@pytest.mark.asyncio
async def test_applier_preflight_retries_bridge_ping():
    """Bridge ping fails twice then succeeds — applier retries up to 3 times with gaps."""
    ctx = MagicMock()
    ensure_analyzer = AsyncMock(return_value={"status": "ok"})
    reconnect_bridge = AsyncMock(return_value={"connected": True})

    # First two pings fail, third succeeds
    bridge_ping = AsyncMock(side_effect=[
        Exception("bridge not ready"),
        Exception("bridge not ready"),
        {"pong": True},
    ])

    applier = Applier(
        ensure_analyzer_fn=ensure_analyzer,
        reconnect_bridge_fn=reconnect_bridge,
        bridge_ping_fn=bridge_ping,
        handshake_max_attempts=3,
        handshake_gap_seconds=0.001,  # fast for tests
    )
    result = await applier.preflight(ctx)

    assert result["bridge_connected"] is True
    assert result["handshake_attempts"] == 3
    assert bridge_ping.await_count == 3


@pytest.mark.asyncio
async def test_applier_preflight_handshake_failure_after_all_retries():
    """Bridge ping never succeeds — applier reports failure after exhausting retries."""
    ctx = MagicMock()
    ensure_analyzer = AsyncMock(return_value={"status": "ok"})
    reconnect_bridge = AsyncMock(return_value={"connected": True})
    bridge_ping = AsyncMock(side_effect=Exception("persistent bridge failure"))

    applier = Applier(
        ensure_analyzer_fn=ensure_analyzer,
        reconnect_bridge_fn=reconnect_bridge,
        bridge_ping_fn=bridge_ping,
        handshake_max_attempts=3,
        handshake_gap_seconds=0.001,
    )
    result = await applier.preflight(ctx)

    assert result["bridge_connected"] is False
    assert result["handshake_attempts"] == 3
    assert "handshake_error" in result


# ── postflight (BUG-FULL-MODE-17) ────────────────────────────────────

@pytest.mark.asyncio
async def test_applier_postflight_sets_monitoring_and_returns_to_arranger():
    """Postflight fixes BUG-FULL-MODE-17 — sets monitoring=In on each track + back_to_arranger."""
    ctx = MagicMock()
    set_monitoring = AsyncMock(return_value={"ok": True})
    back_to_arranger = AsyncMock(return_value={"ok": True})

    applier = Applier(
        ensure_analyzer_fn=AsyncMock(),
        reconnect_bridge_fn=AsyncMock(),
        bridge_ping_fn=AsyncMock(),
        set_track_input_monitoring_fn=set_monitoring,
        back_to_arranger_fn=back_to_arranger,
    )
    result = await applier.postflight(ctx, applied_track_indices=[0, 1, 2])

    # BUG-FIX (post-live-test): state=1 (Auto, the default for new tracks).
    # state=0 was "In" — wrong; left tracks "hot" (always passing input
    # through). Auto is correct: lets arrangement clips play, no input
    # passthrough. The actual fix for "manual arm required" is back_to_arranger.
    assert set_monitoring.await_count == 3
    set_monitoring.assert_has_awaits([
        call(ctx, track_index=0, state=1),
        call(ctx, track_index=1, state=1),
        call(ctx, track_index=2, state=1),
    ])
    # back_to_arranger called once after monitoring set
    back_to_arranger.assert_awaited_once_with(ctx)
    assert result["tracks_set"] == 3
    assert result["back_to_arranger"] is True


@pytest.mark.asyncio
async def test_applier_postflight_empty_track_list_skips_monitoring():
    """If no new tracks created (e.g. develop mode writing only session clips),
    skip per-track monitoring. Still call back_to_arranger as a safe-default."""
    ctx = MagicMock()
    set_monitoring = AsyncMock()
    back_to_arranger = AsyncMock(return_value={"ok": True})

    applier = Applier(
        ensure_analyzer_fn=AsyncMock(),
        reconnect_bridge_fn=AsyncMock(),
        bridge_ping_fn=AsyncMock(),
        set_track_input_monitoring_fn=set_monitoring,
        back_to_arranger_fn=back_to_arranger,
    )
    result = await applier.postflight(ctx, applied_track_indices=[])

    set_monitoring.assert_not_awaited()
    back_to_arranger.assert_awaited_once_with(ctx)
    assert result["tracks_set"] == 0
