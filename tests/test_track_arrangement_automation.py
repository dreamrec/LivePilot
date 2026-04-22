"""Tests for T5 (2026-04-22 handoff) — session-record arrangement automation.

The MCP tool `set_arrangement_automation_via_session_record` orchestrates
a TWO-phase protocol against the remote script:

  1. `arrangement_automation_via_session_record_start` — sets up, arms, fires
  2. (MCP server sleeps for duration × 60/tempo + 0.5s)
  3. `arrangement_automation_via_session_record_complete` — stops, cleans up

These tests lock down the request shape AND the two-phase ordering. They
use a fake Ableton dispatcher that records every call, plus a
monkey-patched `asyncio.sleep` so tests don't actually wait seconds.
"""

from __future__ import annotations

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Import the tool and unwrap the FastMCP decorator ────────────────


def _load_tool():
    from mcp_server.tools.automation import (
        set_arrangement_automation_via_session_record,
    )
    # FastMCP wraps the function in a Tool object; the original callable
    # hangs off `.fn`. Handle both decorator shapes defensively so tests
    # survive FastMCP upgrades.
    tool = set_arrangement_automation_via_session_record
    return getattr(tool, "fn", tool)


# ── Fake Ableton dispatcher ─────────────────────────────────────────


class _FakeAbleton:
    """Records every send_command call; lets individual tests script
    per-command responses."""

    def __init__(self, responses=None):
        self.calls = []
        self._responses = responses or {}

    def send_command(self, cmd, params=None):
        self.calls.append((cmd, params))
        if cmd in self._responses:
            return self._responses[cmd]
        # Default: start returns a recording status with a tempo, complete
        # returns a completed status. Tests override for error paths.
        if cmd.endswith("_start"):
            return {"status": "recording", "tempo": 120.0,
                    "track_index": params.get("track_index")}
        if cmd.endswith("_complete"):
            return {"status": "completed",
                    "arrangement_clip_index": 0,
                    "arrangement_clip_found": True}
        return {"status": "ok"}


class _FakeCtx:
    def __init__(self, responses=None):
        self.ableton = _FakeAbleton(responses)
        self.lifespan_context = {"ableton": self.ableton}


@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    """Replace asyncio.sleep with a no-op so tests don't wait real seconds."""
    async def _noop(_sec):
        return None
    monkeypatch.setattr(asyncio, "sleep", _noop)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) \
        if sys.version_info < (3, 10) else asyncio.run(coro)


# ── Happy path ───────────────────────────────────────────────────────


def test_two_phase_start_then_complete_called_in_order():
    tool = _load_tool()
    ctx = _FakeCtx()
    points = [{"time": 0.0, "value": 0.0}, {"time": 4.0, "value": 1.0}]
    result = _run(tool(
        ctx,
        track_index=0,
        parameter_type="volume",
        points=points,
        target_beat=16.0,
        duration_beats=8.0,
    ))
    assert result["ok"] is True
    assert len(ctx.ableton.calls) == 2
    assert ctx.ableton.calls[0][0] == "arrangement_automation_via_session_record_start"
    assert ctx.ableton.calls[1][0] == "arrangement_automation_via_session_record_complete"


def test_start_params_include_points_and_automation_target():
    tool = _load_tool()
    ctx = _FakeCtx()
    points = [{"time": 0.0, "value": 0.5}]
    _run(tool(
        ctx,
        track_index=2,
        parameter_type="volume",
        points=points,
        target_beat=32.0,
        duration_beats=16.0,
    ))
    _, start_params = ctx.ableton.calls[0]
    assert start_params["track_index"] == 2
    assert start_params["parameter_type"] == "volume"
    assert start_params["points"] == points
    assert start_params["target_beat"] == 32.0
    assert start_params["duration_beats"] == 16.0
    assert start_params["session_clip_slot"] == 0


def test_complete_params_include_cleanup_flag():
    tool = _load_tool()
    ctx = _FakeCtx()
    _run(tool(
        ctx,
        track_index=0,
        parameter_type="volume",
        points=[{"time": 0.0, "value": 0.0}],
        target_beat=0.0,
        duration_beats=4.0,
        cleanup_session_clip=False,
    ))
    _, complete_params = ctx.ableton.calls[1]
    assert complete_params["cleanup_session_clip"] is False
    assert complete_params["track_index"] == 0
    assert complete_params["target_beat"] == 0.0


def test_device_automation_passes_indices():
    tool = _load_tool()
    ctx = _FakeCtx()
    _run(tool(
        ctx,
        track_index=0,
        parameter_type="device",
        points=[{"time": 0.0, "value": 0.5}],
        target_beat=0.0,
        duration_beats=4.0,
        device_index=1,
        parameter_index=3,
    ))
    _, start_params = ctx.ableton.calls[0]
    assert start_params["device_index"] == 1
    assert start_params["parameter_index"] == 3


def test_send_automation_passes_send_index():
    tool = _load_tool()
    ctx = _FakeCtx()
    _run(tool(
        ctx,
        track_index=0,
        parameter_type="send",
        points=[{"time": 0.0, "value": 0.3}],
        target_beat=0.0,
        duration_beats=4.0,
        send_index=1,
    ))
    _, start_params = ctx.ableton.calls[0]
    assert start_params["send_index"] == 1


# ── Start-phase failure short-circuits ────────────────────────────────


def test_start_failure_prevents_complete_and_reports_details():
    tool = _load_tool()
    ctx = _FakeCtx(responses={
        "arrangement_automation_via_session_record_start": {
            "status": "error", "message": "track not armable",
        },
    })
    result = _run(tool(
        ctx,
        track_index=0,
        parameter_type="volume",
        points=[{"time": 0.0, "value": 0.0}],
        target_beat=0.0,
        duration_beats=4.0,
    ))
    assert result["ok"] is False
    assert result["phase"] == "start"
    assert "details" in result
    # Complete must NOT have been called
    cmds = [c[0] for c in ctx.ableton.calls]
    assert "arrangement_automation_via_session_record_complete" not in cmds


# ── Tempo-based sleep duration ──────────────────────────────────────


def test_sleep_duration_scales_with_tempo(monkeypatch):
    """Confirms the tool reads tempo from start_result and sleeps
    duration_beats * 60/tempo + 0.5s. Monkeypatch sleep to capture the
    arg instead of silencing it."""
    captured = []

    async def spy_sleep(sec):
        captured.append(sec)

    monkeypatch.setattr(asyncio, "sleep", spy_sleep)
    tool = _load_tool()
    ctx = _FakeCtx(responses={
        "arrangement_automation_via_session_record_start": {
            "status": "recording", "tempo": 60.0,  # 1 beat = 1 second
        },
    })
    _run(tool(
        ctx,
        track_index=0,
        parameter_type="volume",
        points=[{"time": 0.0, "value": 0.0}],
        target_beat=0.0,
        duration_beats=4.0,  # 4 beats
    ))
    # At 60 BPM, 4 beats = 4 seconds; + 0.5s buffer = 4.5s total
    assert captured == [4.5]


def test_sleep_uses_default_tempo_when_missing():
    """If phase-1 response is missing tempo, fall back to 120 BPM not 0."""
    tool = _load_tool()
    ctx = _FakeCtx(responses={
        "arrangement_automation_via_session_record_start": {
            "status": "recording",
            # no tempo field
        },
    })
    result = _run(tool(
        ctx,
        track_index=0,
        parameter_type="volume",
        points=[{"time": 0.0, "value": 0.0}],
        target_beat=0.0,
        duration_beats=4.0,
    ))
    # At 120 BPM default: 4 × 0.5s + 0.5s = 2.5s
    assert result["tempo"] == 120.0
    assert result["slept_sec"] == pytest.approx(2.5, abs=0.01)


def test_sleep_ceiling_prevents_runaway():
    """Even if duration_beats × tempo would exceed 10 min, cap at 600s."""
    tool = _load_tool()
    ctx = _FakeCtx(responses={
        "arrangement_automation_via_session_record_start": {
            "status": "recording", "tempo": 30.0,
        },
    })
    result = _run(tool(
        ctx,
        track_index=0,
        parameter_type="volume",
        points=[{"time": 0.0, "value": 0.0}],
        target_beat=0.0,
        duration_beats=1000.0,  # would be 2000+ seconds at 30 BPM
    ))
    assert result["slept_sec"] == 600.0


# ── Input validation (pre-remote-call) ────────────────────────────────


def test_rejects_negative_track_index():
    tool = _load_tool()
    ctx = _FakeCtx()
    with pytest.raises(ValueError, match="track_index must be >= 0"):
        _run(tool(
            ctx,
            track_index=-1,
            parameter_type="volume",
            points=[{"time": 0.0, "value": 0.0}],
            target_beat=0.0,
            duration_beats=4.0,
        ))


def test_rejects_unknown_parameter_type():
    tool = _load_tool()
    ctx = _FakeCtx()
    with pytest.raises(ValueError, match="parameter_type must be"):
        _run(tool(
            ctx,
            track_index=0,
            parameter_type="garbage",
            points=[{"time": 0.0, "value": 0.0}],
            target_beat=0.0,
            duration_beats=4.0,
        ))


def test_rejects_empty_points():
    tool = _load_tool()
    ctx = _FakeCtx()
    with pytest.raises(ValueError, match="points list cannot be empty"):
        _run(tool(
            ctx,
            track_index=0,
            parameter_type="volume",
            points=[],
            target_beat=0.0,
            duration_beats=4.0,
        ))


def test_rejects_negative_target_beat():
    tool = _load_tool()
    ctx = _FakeCtx()
    with pytest.raises(ValueError, match="target_beat must be >= 0"):
        _run(tool(
            ctx,
            track_index=0,
            parameter_type="volume",
            points=[{"time": 0.0, "value": 0.0}],
            target_beat=-1.0,
            duration_beats=4.0,
        ))


def test_rejects_zero_or_negative_duration():
    tool = _load_tool()
    ctx = _FakeCtx()
    with pytest.raises(ValueError, match="duration_beats must be > 0"):
        _run(tool(
            ctx,
            track_index=0,
            parameter_type="volume",
            points=[{"time": 0.0, "value": 0.0}],
            target_beat=0.0,
            duration_beats=0.0,
        ))


def test_device_automation_requires_device_and_parameter_index():
    tool = _load_tool()
    ctx = _FakeCtx()
    with pytest.raises(ValueError, match="device_index and parameter_index"):
        _run(tool(
            ctx,
            track_index=0,
            parameter_type="device",
            points=[{"time": 0.0, "value": 0.0}],
            target_beat=0.0,
            duration_beats=4.0,
        ))


def test_send_automation_requires_send_index():
    tool = _load_tool()
    ctx = _FakeCtx()
    with pytest.raises(ValueError, match="send_index required"):
        _run(tool(
            ctx,
            track_index=0,
            parameter_type="send",
            points=[{"time": 0.0, "value": 0.0}],
            target_beat=0.0,
            duration_beats=4.0,
        ))


def test_accepts_points_as_json_string():
    tool = _load_tool()
    ctx = _FakeCtx()
    _run(tool(
        ctx,
        track_index=0,
        parameter_type="volume",
        points='[{"time": 0.0, "value": 0.5}]',
        target_beat=0.0,
        duration_beats=4.0,
    ))
    _, start_params = ctx.ableton.calls[0]
    assert start_params["points"] == [{"time": 0.0, "value": 0.5}]
