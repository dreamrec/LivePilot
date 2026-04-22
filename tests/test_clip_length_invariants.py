"""Tests that lock down clip-length invariants — BUG-2026-04-22 #1c.

Pure-Python contract tests against the Live-free helpers in
`remote_script/LivePilot/_clip_helpers.py`. Loaded by file path to
bypass the package `__init__.py` (which imports `_Framework`, only
present inside Ableton).

Two invariants:
  1. After `create_clip(length=N)`, the clip's `loop_end` must equal N
     (Live's `clip_slot.create_clip(length)` defaults loop_end to N/2
     in some configurations — silent data corruption that downstream
     tools inherit).
  2. `add_notes` must extend `loop_end` when an incoming note's
     `start_time + duration` exceeds it. Without this, Live silently
     drops the out-of-range notes.
"""

from __future__ import annotations

import importlib.util
import os

import pytest


def _load_clip_helpers():
    """Import _clip_helpers.py by file path, bypassing the package __init__."""
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    path = os.path.join(repo, "remote_script", "LivePilot", "_clip_helpers.py")
    spec = importlib.util.spec_from_file_location("_clip_helpers_std", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── Fake-Live shape (just enough to drive the helpers) ───────────────


class _FakeClip:
    def __init__(self, length):
        self.length = length
        # Reproduce the Live default-bug shape: loop_end starts at length/2.
        self.loop_end = length / 2.0
        self.loop_start = 0.0
        self.end_marker = length / 2.0
        self.name = "fake"


# ── #1c — _required_loop_end ──────────────────────────────────────────


def test_required_loop_end_simple():
    helpers = _load_clip_helpers()
    notes = [
        {"pitch": 36, "start_time": 0.0, "duration": 0.25, "velocity": 100},
        {"pitch": 36, "start_time": 7.5, "duration": 0.25, "velocity": 100},
    ]
    assert helpers._required_loop_end(notes) == pytest.approx(7.75)


def test_required_loop_end_empty_notes():
    helpers = _load_clip_helpers()
    assert helpers._required_loop_end([]) == 0.0


def test_required_loop_end_handles_missing_duration():
    helpers = _load_clip_helpers()
    notes = [{"pitch": 36, "start_time": 4.0}]
    assert helpers._required_loop_end(notes) == pytest.approx(4.0)


def test_required_loop_end_picks_largest():
    helpers = _load_clip_helpers()
    notes = [
        {"start_time": 1.0, "duration": 0.5},
        {"start_time": 5.0, "duration": 2.0},  # ends at 7.0
        {"start_time": 3.0, "duration": 0.25},
    ]
    assert helpers._required_loop_end(notes) == pytest.approx(7.0)


# ── #1c — _apply_clip_length_invariants ───────────────────────────────


def test_apply_clip_length_invariants_overwrites_half_length_default():
    """After create_clip(length=8), loop_end should be 8, not 4."""
    helpers = _load_clip_helpers()
    clip = _FakeClip(length=8.0)
    assert clip.loop_end == 4.0  # baseline: the Live bug shape

    out = helpers._apply_clip_length_invariants(clip, 8.0)

    assert clip.loop_end == 8.0
    assert clip.end_marker == 8.0
    assert out == {"loop_end": 8.0, "end_marker": 8.0}


def test_apply_clip_length_invariants_handles_fractional_length():
    helpers = _load_clip_helpers()
    clip = _FakeClip(length=3.5)
    helpers._apply_clip_length_invariants(clip, 3.5)
    assert clip.loop_end == 3.5
    assert clip.end_marker == 3.5


# ── #1c — _extend_loop_end_for_notes ──────────────────────────────────


def test_extend_loop_end_when_note_exceeds():
    """Note at beat 7.75 in a clip with loop_end=4 must extend to 7.75."""
    helpers = _load_clip_helpers()
    clip = _FakeClip(length=8.0)  # loop_end starts at 4.0
    notes = [{"start_time": 7.5, "duration": 0.25}]

    new_end = helpers._extend_loop_end_for_notes(clip, notes)

    assert new_end == pytest.approx(7.75)
    assert clip.loop_end == pytest.approx(7.75)
    assert clip.end_marker >= 7.75


def test_does_not_shrink_loop_end():
    """If no note exceeds current loop_end, return None and leave it."""
    helpers = _load_clip_helpers()
    clip = _FakeClip(length=8.0)
    clip.loop_end = 8.0
    notes = [{"start_time": 0.0, "duration": 0.25}]

    new_end = helpers._extend_loop_end_for_notes(clip, notes)

    assert new_end is None
    assert clip.loop_end == 8.0


def test_does_not_shrink_end_marker():
    """If end_marker is already further out than the new loop_end, keep it."""
    helpers = _load_clip_helpers()
    clip = _FakeClip(length=8.0)
    clip.end_marker = 16.0  # caller has manually set this further out
    notes = [{"start_time": 7.5, "duration": 0.25}]

    helpers._extend_loop_end_for_notes(clip, notes)

    assert clip.loop_end == pytest.approx(7.75)
    assert clip.end_marker == 16.0  # preserved


def test_empty_notes_does_not_extend():
    helpers = _load_clip_helpers()
    clip = _FakeClip(length=8.0)
    original = clip.loop_end

    new_end = helpers._extend_loop_end_for_notes(clip, [])

    assert new_end is None
    assert clip.loop_end == original
