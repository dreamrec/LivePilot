"""Input-validation parity regression tests (DEEP_REVIEW P3-11/12/13).

Three tool families forwarded unvalidated inputs while sibling functions in
the same files validated theirs:

  P3-11  devices.set_simpler_playback_mode forwarded slice_by / sensitivity
         unchecked (its own docstring promises the ranges; sibling
         set_drum_chain_note range-checks note).
  P3-12  generative.layer_euclidean_rhythms raw-subscripted
         layer["pulses"]/["steps"]/["pitch"] — malformed layers surfaced as
         unstructured KeyError/TypeError (INTERNAL) instead of INVALID_PARAM.
  P3-13  analyzer warp/scrub bridge tools forwarded track_index/clip_index/
         beat_time to the M4L bridge with zero validation, unlike their
         clips.py TCP siblings (_validate_track_index/_validate_clip_index).
  P9     get_warp_markers and stop_scrub — the first function in the "Phase
         2: Warp Markers" section and the function immediately after
         scrub_clip in "Phase 2: Clip & Display" — were missed by the
         P3-13 sweep despite taking the identical track_index/clip_index
         pair and building the identical bridge path as their now-guarded
         siblings.

Each guard must fire BEFORE any connection/bridge access, so all tests use
dummy contexts that would explode if touched.
"""
from __future__ import annotations

import asyncio

import pytest

from mcp_server.tools.analyzer import (
    add_warp_marker,
    get_warp_markers,
    move_warp_marker,
    remove_warp_marker,
    scrub_clip,
    stop_scrub,
)
from mcp_server.tools.devices import set_simpler_playback_mode
from mcp_server.tools.generative import layer_euclidean_rhythms


class _ExplodingCtx:
    """Any attribute access means the guard failed to fire first."""

    def __getattr__(self, name):
        raise AssertionError(
            f"validation guard did not fire before ctx.{name} access"
        )


class _FakeAbleton:
    def __init__(self):
        self.sent = []

    def send_command(self, command, params=None):
        self.sent.append((command, params))
        return {"ok": True, "command": command, "params": params}


class _CtxWithAbleton:
    def __init__(self, ableton):
        self.lifespan_context = {"ableton": ableton}


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# P3-11: set_simpler_playback_mode slice_by / sensitivity ranges
# ---------------------------------------------------------------------------


def test_slice_by_out_of_enum_rejected():
    with pytest.raises(ValueError, match="slice_by"):
        set_simpler_playback_mode(
            _ExplodingCtx(), track_index=0, device_index=0,
            playback_mode=2, slice_by=7,
        )


def test_slice_by_negative_rejected():
    with pytest.raises(ValueError, match="slice_by"):
        set_simpler_playback_mode(
            _ExplodingCtx(), track_index=0, device_index=0,
            playback_mode=2, slice_by=-1,
        )


def test_sensitivity_above_one_rejected():
    with pytest.raises(ValueError, match="sensitivity"):
        set_simpler_playback_mode(
            _ExplodingCtx(), track_index=0, device_index=0,
            playback_mode=2, sensitivity=5.0,
        )


def test_sensitivity_negative_rejected():
    with pytest.raises(ValueError, match="sensitivity"):
        set_simpler_playback_mode(
            _ExplodingCtx(), track_index=0, device_index=0,
            playback_mode=2, sensitivity=-0.1,
        )


def test_valid_slice_by_and_sensitivity_forwarded():
    """Boundary values (slice_by=3, sensitivity=0.0/1.0) must still pass."""
    ableton = _FakeAbleton()
    ctx = _CtxWithAbleton(ableton)
    result = set_simpler_playback_mode(
        ctx, track_index=0, device_index=0,
        playback_mode=2, slice_by=3, sensitivity=1.0,
    )
    assert result["ok"] is True
    command, params = ableton.sent[0]
    assert command == "set_simpler_playback_mode"
    assert params["slice_by"] == 3
    assert params["sensitivity"] == 1.0

    set_simpler_playback_mode(
        ctx, track_index=0, device_index=0,
        playback_mode=2, slice_by=0, sensitivity=0.0,
    )
    _, params = ableton.sent[1]
    assert params["slice_by"] == 0
    assert params["sensitivity"] == 0.0


# ---------------------------------------------------------------------------
# P3-12: layer_euclidean_rhythms layer-shape validation
# ---------------------------------------------------------------------------


def test_non_dict_layer_raises_valueerror_not_typeerror():
    with pytest.raises(ValueError, match="dict"):
        layer_euclidean_rhythms(_ExplodingCtx(), layers=[[3, 8, 36]])


def test_string_layer_raises_valueerror():
    with pytest.raises(ValueError, match="dict"):
        layer_euclidean_rhythms(_ExplodingCtx(), layers=["kick"])


def test_missing_pulses_raises_valueerror_not_keyerror():
    with pytest.raises(ValueError, match="pulses"):
        layer_euclidean_rhythms(
            _ExplodingCtx(), layers=[{"steps": 8, "pitch": 36}],
        )


def test_missing_pitch_raises_valueerror_naming_the_key():
    with pytest.raises(ValueError, match="pitch"):
        layer_euclidean_rhythms(
            _ExplodingCtx(), layers=[{"pulses": 3, "steps": 8}],
        )


def test_valid_layers_still_generate():
    result = layer_euclidean_rhythms(
        _ExplodingCtx(),
        layers=[
            {"pulses": 3, "steps": 8, "pitch": 36},
            {"pulses": 5, "steps": 16, "pitch": 42, "velocity": 80},
        ],
    )
    assert "notes" in result
    assert len(result["layers"]) == 2
    assert result["layers"][0]["note_count"] == 3


# ---------------------------------------------------------------------------
# P3-13: warp/scrub bridge tools index + beat_time guards
# ---------------------------------------------------------------------------


def test_add_warp_marker_rejects_negative_track_index():
    with pytest.raises(ValueError, match="track_index"):
        _run(add_warp_marker(_ExplodingCtx(), track_index=-1, clip_index=0, beat_time=0.0))


def test_add_warp_marker_rejects_negative_clip_index():
    with pytest.raises(ValueError, match="clip_index"):
        _run(add_warp_marker(_ExplodingCtx(), track_index=0, clip_index=-1, beat_time=0.0))


def test_add_warp_marker_rejects_negative_beat_time():
    with pytest.raises(ValueError, match="beat_time"):
        _run(add_warp_marker(_ExplodingCtx(), track_index=0, clip_index=0, beat_time=-0.5))


def test_move_warp_marker_rejects_negative_old_beat_time():
    with pytest.raises(ValueError, match="old_beat_time"):
        _run(move_warp_marker(
            _ExplodingCtx(), track_index=0, clip_index=0,
            old_beat_time=-1.0, new_beat_time=2.0,
        ))


def test_move_warp_marker_rejects_negative_new_beat_time():
    with pytest.raises(ValueError, match="new_beat_time"):
        _run(move_warp_marker(
            _ExplodingCtx(), track_index=0, clip_index=0,
            old_beat_time=1.0, new_beat_time=-2.0,
        ))


def test_remove_warp_marker_rejects_negative_beat_time():
    with pytest.raises(ValueError, match="beat_time"):
        _run(remove_warp_marker(_ExplodingCtx(), track_index=0, clip_index=0, beat_time=-0.25))


def test_scrub_clip_rejects_negative_indices():
    with pytest.raises(ValueError, match="track_index"):
        _run(scrub_clip(_ExplodingCtx(), track_index=-3, clip_index=0, beat_time=0.0))
    with pytest.raises(ValueError, match="beat_time"):
        _run(scrub_clip(_ExplodingCtx(), track_index=0, clip_index=0, beat_time=-4.0))


# ---------------------------------------------------------------------------
# P9: get_warp_markers / stop_scrub — missed siblings of the P3-13 sweep
# ---------------------------------------------------------------------------


def test_get_warp_markers_rejects_negative_track_index():
    with pytest.raises(ValueError, match="track_index"):
        _run(get_warp_markers(_ExplodingCtx(), track_index=-5, clip_index=0))


def test_get_warp_markers_rejects_negative_clip_index():
    with pytest.raises(ValueError, match="clip_index"):
        _run(get_warp_markers(_ExplodingCtx(), track_index=0, clip_index=-5))


def test_stop_scrub_rejects_negative_track_index():
    with pytest.raises(ValueError, match="track_index"):
        _run(stop_scrub(_ExplodingCtx(), track_index=-5, clip_index=0))


def test_stop_scrub_rejects_negative_clip_index():
    with pytest.raises(ValueError, match="clip_index"):
        _run(stop_scrub(_ExplodingCtx(), track_index=0, clip_index=-5))
