"""Tests for mcp_server/tools/tracks.py — pure-Python path checks.

Guards against the last-track deletion misleading error (BUG-F3) caught
in the 2026-04-18 creative session.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from mcp_server.tools.tracks import delete_track


def _make_ctx(track_count: int):
    """Build a mock Context whose Ableton connection reports N tracks."""
    ableton = MagicMock()

    def send(cmd, params=None):
        if cmd == "get_session_info":
            return {"track_count": track_count}
        if cmd == "delete_track":
            return {"deleted": params["track_index"]}
        raise AssertionError(f"Unexpected command: {cmd}")

    ableton.send_command.side_effect = send

    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}
    return ctx, ableton


# ---------------------------------------------------------------------------
# BUG-F3: delete_track on the last track surfaced a misleading STATE_ERROR
# ("you can't add notes to a clip that doesn't exist yet"). Pre-check
# track_count and raise a clear ValueError instead.
# ---------------------------------------------------------------------------


def test_delete_track_blocks_when_only_one_track_remains():
    ctx, ableton = _make_ctx(track_count=1)
    with pytest.raises(ValueError, match="at least one track"):
        delete_track(ctx, track_index=0)

    # delete_track command should NOT have been sent
    calls = [c.args[0] for c in ableton.send_command.call_args_list]
    assert "delete_track" not in calls
    assert "get_session_info" in calls


def test_delete_track_succeeds_when_multiple_tracks_remain():
    ctx, _ = _make_ctx(track_count=5)
    result = delete_track(ctx, track_index=2)
    assert result == {"deleted": 2}


def test_delete_track_validates_index():
    """Bad indices are rejected BEFORE the session probe."""
    ctx, _ = _make_ctx(track_count=5)
    with pytest.raises(ValueError):
        delete_track(ctx, track_index=-9999)


def test_delete_track_handles_missing_track_count_field():
    """Defensive: if get_session_info doesn't return track_count, assume >1."""
    ableton = MagicMock()

    def send(cmd, params=None):
        if cmd == "get_session_info":
            return {}  # no track_count
        if cmd == "delete_track":
            return {"deleted": params["track_index"]}
        raise AssertionError(f"Unexpected command: {cmd}")

    ableton.send_command.side_effect = send
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    # Without a count, we must NOT block — that would be a regression for
    # edge cases where the session-info call is stubbed in tests.
    # Instead, delegate to Ableton and let it return its own error.
    result = delete_track(ctx, track_index=0)
    assert result == {"deleted": 0}
