"""Regression tests for the Remote Script's tracks.get_track_info on Group tracks.

Companion to test_remote_transport_group_tracks.py. get_session_info was fixed
to guard the LOM-fragile arm / has_midi_input / has_audio_input properties, but
get_track_info still gated them on `track_index >= 0`, which is wrong: a Group
track has a positive index yet raises RuntimeError on those properties. These
tests pin the try/except guard so a Group track at a positive index no longer
crashes get_track_info.
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
    "remote_script.LivePilot.tracks",
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


def _load_tracks_module():
    for name in [
        "remote_script.LivePilot.tracks",
        "remote_script.LivePilot.router",
        "remote_script.LivePilot.utils",
        "remote_script.LivePilot",
        "remote_script",
        "Live",
    ]:
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
    return _load("remote_script.LivePilot.tracks", REMOTE_ROOT / "tracks.py")


# ─── LOM doubles ────────────────────────────────────────────────────────────

class _Param:
    def __init__(self, value=0.0):
        self.value = value


class _MixerDevice:
    def __init__(self):
        self.volume = _Param(0.85)
        self.panning = _Param(0.0)
        self.sends = []


class _NormalTrack:
    def __init__(self, name, *, arm=False, has_midi=True, has_audio=False):
        self.name = name
        self.color_index = 0
        self.mute = False
        self.solo = False
        self.is_foldable = False
        self.is_grouped = False
        self.clip_slots = []
        self.devices = []
        self.mixer_device = _MixerDevice()
        self.arm = arm
        self.has_midi_input = has_midi
        self.has_audio_input = has_audio
        self.current_monitoring_state = 1


class _GroupTrack:
    """A Group track: positive index, but arm / has_midi_input /
    has_audio_input / current_monitoring_state raise RuntimeError. hasattr()
    returns True regardless (mirrors Live's __getattr__ trap)."""
    _FRAGILE = ("arm", "has_midi_input", "has_audio_input", "current_monitoring_state")

    def __init__(self, name):
        self.name = name
        self.color_index = 0
        self.mute = False
        self.solo = False
        self.is_foldable = True
        self.is_grouped = False
        self.fold_state = 0
        self.clip_slots = []
        self.devices = []
        self.mixer_device = _MixerDevice()

    def __getattr__(self, item):
        if item in _GroupTrack._FRAGILE:
            raise RuntimeError(
                "Main and Return Tracks have no '%s' state!" % item.capitalize()
            )
        raise AttributeError(item)


class _FakeSong:
    def __init__(self, tracks):
        self.tracks = tracks
        self.return_tracks = []


# ─── Tests ──────────────────────────────────────────────────────────────────

def test_get_track_info_group_track_does_not_crash():
    """A Group track at a positive index must not raise from get_track_info."""
    tracks = _load_tracks_module()
    song = _FakeSong([_NormalTrack("Drums", arm=True), _GroupTrack("Bus 1")])

    result = tracks.get_track_info(song, {"track_index": 1})

    assert result["name"] == "Bus 1"
    assert result["arm"] is None, "Group track arm should be None, not crash"
    assert result["has_midi_input"] is None
    assert result["has_audio_input"] is None
    assert result["current_monitoring_state"] is None
    # Non-fragile fields still populated
    assert result["mute"] is False
    assert result["is_foldable"] is True
    assert result["fold_state"] is False


def test_get_track_info_normal_track_unaffected():
    """A regular track still reports real arm / input values."""
    tracks = _load_tracks_module()
    song = _FakeSong([_NormalTrack("Kick", arm=True, has_midi=True, has_audio=False)])

    result = tracks.get_track_info(song, {"track_index": 0})

    assert result["arm"] is True
    assert result["has_midi_input"] is True
    assert result["has_audio_input"] is False
    assert result["current_monitoring_state"] == 1
