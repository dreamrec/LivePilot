"""Tests for mixing MCP tool wrappers.

Kept thin — most mixing logic lives in the Remote Script (covered by
test_remote_script_contracts.py). This file holds regression tests for
tool-wrapper-level behavior like BUG-B3's playback-aware stereo suppression.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace


# ─── BUG-B3 regressions — stereo meters during stopped playback ────────────


def _fake_ctx(tracks_response, is_playing):
    """Build a fake MCP context whose Ableton answers get_track_meters
    with *tracks_response* and get_session_info with is_playing."""
    def send(cmd, params=None):
        if cmd == "get_track_meters":
            # Response is a dict with a "tracks" key — mirror Remote Script
            return {"tracks": list(tracks_response)}
        if cmd == "get_session_info":
            return {"is_playing": is_playing, "tracks": []}
        return {}
    return SimpleNamespace(
        lifespan_context={"ableton": SimpleNamespace(send_command=send)}
    )


class TestBugB3StereoSuppression:
    """BUG-B3: get_track_meters used to report {level: 0.81, left: 0,
    right: 0} during stopped playback — `level` holds peak-hold while
    left/right decay to 0. Looks like a killed signal but isn't. Fix:
    tag is_playing in the response and null-out left/right when stopped."""

    def test_is_playing_flag_propagated(self):
        """Response must always carry is_playing so callers can interpret."""
        from mcp_server.tools.mixing import get_track_meters
        ctx = _fake_ctx(
            tracks_response=[{"level": 0.5, "left": 0.5, "right": 0.5}],
            is_playing=True,
        )
        result = asyncio.run(get_track_meters(ctx, include_stereo=True))
        assert result["is_playing"] is True

    def test_left_right_nulled_when_stopped(self):
        """When is_playing=False AND left/right are 0 (decayed), null
        them out so callers don't mistake decay for a killed signal."""
        from mcp_server.tools.mixing import get_track_meters
        ctx = _fake_ctx(
            tracks_response=[{"level": 0.81, "left": 0, "right": 0}],
            is_playing=False,
        )
        result = asyncio.run(get_track_meters(ctx, include_stereo=True))
        track = result["tracks"][0]
        assert track["left"] is None
        assert track["right"] is None
        # level stays as peak-hold (informational)
        assert track["level"] == 0.81
        # User-facing explanation note is attached
        assert "_stereo_note" in track

    def test_left_right_preserved_when_playing(self):
        """When actually playing, left/right reflect live signal and
        must NOT be nulled out even if they happen to be 0."""
        from mcp_server.tools.mixing import get_track_meters
        ctx = _fake_ctx(
            tracks_response=[{"level": 0.5, "left": 0.5, "right": 0.5}],
            is_playing=True,
        )
        result = asyncio.run(get_track_meters(ctx, include_stereo=True))
        track = result["tracks"][0]
        assert track["left"] == 0.5
        assert track["right"] == 0.5

    def test_non_stereo_request_untouched(self):
        """include_stereo=False — the suppression logic must not fire."""
        from mcp_server.tools.mixing import get_track_meters
        ctx = _fake_ctx(
            tracks_response=[{"level": 0.81}],
            is_playing=False,
        )
        result = asyncio.run(get_track_meters(ctx, include_stereo=False))
        track = result["tracks"][0]
        assert track["level"] == 0.81
        # Still exposes is_playing for consistency
        assert result["is_playing"] is False
