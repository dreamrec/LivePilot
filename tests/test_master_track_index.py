"""Tests for the -1000 master-track convention — BUG-2026-04-22 #11.

The codebase uses track_index=-1000 to mean "master track" across most
track-addressing tools (set_track_volume, find_and_load_device, etc.).
But get_track_info historically rejected -1000 with "track_index must be
>= 0 for regular tracks, or -1..-99 for return tracks". These tests
lock down that -1000 is universally accepted as master.
"""

from __future__ import annotations

import pytest

from mcp_server.tools.tracks import (
    MASTER_TRACK_INDEX,
    _validate_track_index,
)


def test_master_track_index_constant():
    assert MASTER_TRACK_INDEX == -1000


def test_validate_accepts_master_index():
    """-1000 must validate cleanly."""
    _validate_track_index(-1000)  # should not raise


def test_validate_accepts_regular_track_zero():
    _validate_track_index(0)


def test_validate_accepts_return_tracks():
    _validate_track_index(-1)
    _validate_track_index(-2)
    _validate_track_index(-99)


def test_validate_rejects_below_minus_99_except_master():
    with pytest.raises(ValueError, match="must be >= 0"):
        _validate_track_index(-100)
    with pytest.raises(ValueError, match="must be >= 0"):
        _validate_track_index(-500)


def test_validate_master_blocked_when_disallowed():
    """Operations that don't make sense on master can opt out."""
    with pytest.raises(ValueError, match="master"):
        _validate_track_index(-1000, allow_master=False)


def test_validate_return_blocked_when_disallowed():
    """Operations like create_scene that only work on regular tracks."""
    with pytest.raises(ValueError, match="return tracks not supported"):
        _validate_track_index(-1, allow_return=False)
