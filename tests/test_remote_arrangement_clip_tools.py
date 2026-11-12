"""Regression tests for Remote Script arrangement clip handlers (P2-52/53/54).

P2-53: force_arrangement swallowed every per-track clip-stop error and
returned unconditional success, defeating the §9c partial-failure contract.
A clip that fails to stop re-asserts the session override → "playback starts
mid-song". The handler must now surface a per-track stop error and reflect
partial failure (arrangement_active=False) instead of always claiming success.

P2-54: create_arrangement_clip left a silent gap of (loop_length -
source_length) beats between copies when loop_length > source_length, despite
the docstring promising a "seamless" fill. Copies must now tile by
min(loop_length, source_length) so no un-filled gap remains.

P2-52 is exercised indirectly: the post-loop single-pass keeps copies named
correctly without re-listing arrangement_clips per iteration.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = ROOT / "remote_script" / "LivePilot"

_POLLUTED_MODULES = (
    "Live",
    "remote_script",
    "remote_script.LivePilot",
    "remote_script.LivePilot.utils",
    "remote_script.LivePilot.router",
    "remote_script.LivePilot.clip_automation",
    "remote_script.LivePilot.arrangement",
)


@pytest.fixture(autouse=True)
def _cleanup_sys_modules():
    snapshot = {name: sys.modules.get(name) for name in _POLLUTED_MODULES}
    yield
    for name, original in snapshot.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


def _load_arrangement_module():
    for name in _POLLUTED_MODULES:
        sys.modules.pop(name, None)

    sys.modules["Live"] = types.ModuleType("Live")

    remote_pkg = types.ModuleType("remote_script")
    remote_pkg.__path__ = [str(ROOT / "remote_script")]
    sys.modules["remote_script"] = remote_pkg

    live_pkg = types.ModuleType("remote_script.LivePilot")
    live_pkg.__path__ = [str(REMOTE_ROOT)]
    sys.modules["remote_script.LivePilot"] = live_pkg

    def _load(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    _load("remote_script.LivePilot.utils", REMOTE_ROOT / "utils.py")
    _load("remote_script.LivePilot.router", REMOTE_ROOT / "router.py")
    _load(
        "remote_script.LivePilot.clip_automation",
        REMOTE_ROOT / "clip_automation.py",
    )
    return _load(
        "remote_script.LivePilot.arrangement", REMOTE_ROOT / "arrangement.py"
    )


# ─── LOM doubles ────────────────────────────────────────────────────────────


class _SessionClip:
    def __init__(self, length):
        self.length = length


class _ArrClip:
    """A placed arrangement clip. length comes from the source content; the
    loop region can be reshaped by the handler."""

    def __init__(self, start_time, length):
        self.start_time = start_time
        self.length = length
        self.name = ""
        self.color_index = 0
        self.looping = False
        self.loop_start = 0.0
        self.loop_end = length

    def remove_notes_extended(self, *args, **kwargs):
        pass


class _Slot:
    def __init__(self, clip=None, is_playing=False, stop_raises=False):
        self.clip = clip
        self.has_clip = clip is not None
        self.is_playing = is_playing
        self._stop_raises = stop_raises


class _StoppableClip:
    def __init__(self, slot, stop_raises):
        self._slot = slot
        self._stop_raises = stop_raises
        self.stopped = False

    def stop(self):
        if self._stop_raises:
            raise RuntimeError("clip is in a non-stoppable state")
        self.stopped = True
        self._slot.is_playing = False


class _ArrTrack:
    """A track that records arrangement-clip duplications, modelling Live's
    Track.duplicate_clip_to_arrangement + arrangement_clips vector."""

    def __init__(self):
        self._arr = []

    @property
    def arrangement_clips(self):
        return list(self._arr)

    def duplicate_clip_to_arrangement(self, source_clip, pos):
        self._arr.append(_ArrClip(pos, source_clip.length))


class _SourceTrack(_ArrTrack):
    def __init__(self, source_clip, slot_index):
        super().__init__()
        slots = []
        for i in range(slot_index + 1):
            slots.append(_Slot(clip=source_clip if i == slot_index else None))
        self.clip_slots = slots


class _PlayingTrack:
    """A track with playing session clips, for force_arrangement tests."""

    def __init__(self, slots):
        self.clip_slots = slots


class _FakeSong:
    def __init__(self, tracks, return_tracks=None):
        self.tracks = tracks
        self.return_tracks = return_tracks or []
        self.is_playing = False
        self.back_to_arranger = False
        self.current_song_time = 13.0
        self.loop = False
        self.loop_start = 0.0
        self.loop_length = 0.0

    def begin_undo_step(self):
        pass

    def end_undo_step(self):
        pass

    def stop_playing(self):
        self.is_playing = False

    def start_playing(self):
        self.is_playing = True


# ─── P2-54: create_arrangement_clip seamless fill ───────────────────────────


def test_create_arrangement_clip_no_gap_when_loop_length_exceeds_source():
    """loop_length (16) > source_length (4) must NOT leave un-filled gaps.

    Region is [0, 32). Before the fix, copies were placed at 0 and 16 only
    (stepping by loop_length=16), leaving 4..16 and 20..32 silent. After the
    fix copies tile by min(16, 4)=4, so the whole region is covered with no
    gap larger than the source length.
    """
    arr = _load_arrangement_module()

    source = _SessionClip(length=4.0)
    track = _SourceTrack(source, slot_index=0)
    song = _FakeSong([track])

    arr.create_arrangement_clip(
        song,
        {
            "track_index": 0,
            "clip_slot_index": 0,
            "start_time": 0.0,
            "length": 32.0,
            "loop_length": 16.0,
        },
    )

    starts = sorted(c.start_time for c in track.arrangement_clips)
    assert starts, "expected at least one placed clip"
    # No gap larger than the source length anywhere across [0, 32).
    end_pos = 32.0
    covered_to = 0.0
    for s in starts:
        assert s <= covered_to + 1e-6, (
            "gap before copy at %.2f: covered only to %.2f" % (s, covered_to)
        )
        covered_to = max(covered_to, s + source.length)
    assert covered_to >= end_pos - 1e-6, (
        "region not fully covered: reached only %.2f of %.2f"
        % (covered_to, end_pos)
    )


def test_create_arrangement_clip_default_loop_length_unchanged():
    """Default path (loop_length == source_length) tiles every source_length."""
    arr = _load_arrangement_module()

    source = _SessionClip(length=4.0)
    track = _SourceTrack(source, slot_index=0)
    song = _FakeSong([track])

    arr.create_arrangement_clip(
        song,
        {
            "track_index": 0,
            "clip_slot_index": 0,
            "start_time": 0.0,
            "length": 16.0,
        },
    )
    starts = sorted(c.start_time for c in track.arrangement_clips)
    assert starts == [0.0, 4.0, 8.0, 12.0]


# ─── P2-53: force_arrangement surfaces stop errors ──────────────────────────


def test_force_arrangement_surfaces_per_track_stop_error():
    """A clip that fails to stop must be reported, not swallowed as success."""
    arr = _load_arrangement_module()

    bad_slot = _Slot(is_playing=True, stop_raises=True)
    bad_slot.clip = _StoppableClip(bad_slot, stop_raises=True)
    bad_slot.has_clip = True

    good_slot = _Slot(is_playing=True)
    good_slot.clip = _StoppableClip(good_slot, stop_raises=False)
    good_slot.has_clip = True

    track = _PlayingTrack([good_slot, bad_slot])
    song = _FakeSong([track])

    result = arr.force_arrangement(song, {"play": False})
    while isinstance(result, arr.DeferredResult):
        result = result.resume()

    # The failing stop must be surfaced, not discarded.
    assert result["stop_errors"], "expected stop_errors to be populated"
    assert result["stop_errors"][0]["track"] == 0
    assert result["stop_errors"][0]["slot"] == 1
    assert "non-stoppable" in result["stop_errors"][0]["error"]
    # Partial failure must NOT be reported as unconditional success.
    assert result["arrangement_active"] is False
    assert "warning" in result
    # The good clip still got stopped.
    assert good_slot.clip.stopped is True
    # back_to_arranger still ran as the primary override release.
    assert song.back_to_arranger is True


def test_force_arrangement_clean_path_reports_success():
    """No stop failures → arrangement_active True, empty stop_errors."""
    arr = _load_arrangement_module()

    slot = _Slot(is_playing=True)
    slot.clip = _StoppableClip(slot, stop_raises=False)
    slot.has_clip = True

    track = _PlayingTrack([slot])
    song = _FakeSong([track])

    result = arr.force_arrangement(song, {"play": False})
    while isinstance(result, arr.DeferredResult):
        result = result.resume()

    assert result["stop_errors"] == []
    assert result["arrangement_active"] is True
    assert "warning" not in result
    assert slot.clip.stopped is True


def test_create_arrangement_clip_zero_length_source_raises_not_hangs():
    """ARR-P254-ZEROLEN: a source clip with length 0 + explicit loop_length>0
    must raise a clean ValueError, NOT spin forever placing infinite copies
    (step=min(loop_length,0)=0 → unbounded loop = DAW hard-freeze). The error
    wrapper maps ValueError to INVALID_PARAM."""
    import pytest
    arr = _load_arrangement_module()

    source = _SessionClip(length=0.0)
    track = _SourceTrack(source, slot_index=0)
    song = _FakeSong([track])

    with pytest.raises(ValueError):
        arr.create_arrangement_clip(
            song,
            {
                "track_index": 0,
                "clip_slot_index": 0,
                "start_time": 0.0,
                "length": 32.0,
                "loop_length": 16.0,
            },
        )
    # And it must NOT have placed a runaway number of clips.
    assert len(track.arrangement_clips) == 0
