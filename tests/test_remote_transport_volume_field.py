"""Regression tests for P2-21 — get_session_info now emits per-track volume.

Without a `volume` field, semantic-move compilers (mix/sound-design/
transition) had no way to read a track's CURRENT level and could only write
an absolute value — e.g. "make it punchier" could turn a hot drum bus DOWN
by blindly writing 0.75. This adds `track.mixer_device.volume.value` to
each per-track dict in get_session_info, guarded the same way as
arm/has_midi_input/has_audio_input so a track type (or older test double)
that doesn't expose mixer_device degrades to None instead of crashing the
whole scan.
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
    "remote_script.LivePilot.transport",
    "remote_script.LivePilot.version_detect",
)


@pytest.fixture(autouse=True)
def _cleanup_sys_modules():
    """Snapshot the polluted modules before each test and restore after."""
    snapshot = {name: sys.modules.get(name) for name in _POLLUTED_MODULES}
    yield
    for name, original in snapshot.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


def _load_transport_module():
    """Load remote_script.LivePilot.transport in isolation.

    Mirrors test_remote_transport_group_tracks.py's loader — see that file
    for the rationale on faking `Live` + stubbing version_detect.
    """
    for name in [
        "remote_script.LivePilot.transport",
        "remote_script.LivePilot.version_detect",
        "remote_script.LivePilot.router",
        "remote_script.LivePilot.utils",
        "remote_script.LivePilot",
        "remote_script",
        "Live",
    ]:
        sys.modules.pop(name, None)

    fake_live = types.ModuleType("Live")
    fake_live.Application = types.SimpleNamespace(
        get_application=lambda: types.SimpleNamespace(
            get_major_version=lambda: 12,
            get_minor_version=lambda: 4,
            get_bugfix_version=lambda: 0,
        ),
    )
    sys.modules["Live"] = fake_live

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

    stub_vd = types.ModuleType("remote_script.LivePilot.version_detect")
    stub_vd.version_string = lambda: "12.4.0"
    stub_vd.get_api_features = lambda: {}
    sys.modules["remote_script.LivePilot.version_detect"] = stub_vd

    return _load("remote_script.LivePilot.transport", REMOTE_ROOT / "transport.py")


class _SongProxy:
    """Fresh wrappers compare equal when they represent the same Live Set."""

    def __init__(self, underlying_id: str):
        self.underlying_id = underlying_id

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, _SongProxy)
            and self.underlying_id == other.underlying_id
        )


def test_session_identity_survives_fresh_proxy_objects():
    transport = _load_transport_module()

    first = transport._get_session_instance_id(_SongProxy("set-a"))
    second = transport._get_session_instance_id(_SongProxy("set-a"))

    assert first == second


def test_session_identity_changes_for_a_new_live_set():
    transport = _load_transport_module()

    first = transport._get_session_instance_id(_SongProxy("set-a"))
    second = transport._get_session_instance_id(_SongProxy("set-b"))

    assert first != second


# ─── LOM doubles ────────────────────────────────────────────────────────────

class _Volume:
    def __init__(self, value: float):
        self.value = value


class _Mixer:
    def __init__(self, volume: float):
        self.volume = _Volume(volume)


class _NormalTrack:
    """A regular track exposing mixer_device.volume.value like real Live."""

    def __init__(self, name: str, volume: float = 0.85):
        self.name = name
        self.color_index = 0
        self.mute = False
        self.solo = False
        self.arm = False
        self.has_midi_input = True
        self.has_audio_input = False
        self.mixer_device = _Mixer(volume)


class _NoMixerTrack:
    """A track/test-double that doesn't expose mixer_device at all — must
    degrade to volume=None rather than raising."""

    def __init__(self, name: str):
        self.name = name
        self.color_index = 0
        self.mute = False
        self.solo = False
        self.arm = False
        self.has_midi_input = True
        self.has_audio_input = False


class _RaisingMixerTrack:
    """A track whose mixer_device access raises — mirrors the RuntimeError
    trap Group/Return tracks spring on arm/has_midi_input/has_audio_input,
    just applied to volume instead."""

    def __init__(self, name: str):
        self.name = name
        self.color_index = 0
        self.mute = False
        self.solo = False
        self.arm = False
        self.has_midi_input = True
        self.has_audio_input = False

    @property
    def mixer_device(self):
        raise RuntimeError("mixer_device unavailable")


class _FakeSong:
    def __init__(self, tracks):
        self.tracks = tracks
        self.return_tracks = []
        self.scenes = []
        self.tempo = 120.0
        self.signature_numerator = 4
        self.signature_denominator = 4
        self.is_playing = False
        self.song_length = 64.0
        self.current_song_time = 0.0
        self.loop = False
        self.loop_start = 0.0
        self.loop_length = 4.0
        self.metronome = False
        self.record_mode = False
        self.session_record = False


# ─── Tests ──────────────────────────────────────────────────────────────────

def test_get_session_info_emits_track_volume():
    transport = _load_transport_module()
    song = _FakeSong([
        _NormalTrack("Drums", volume=0.7),
        _NormalTrack("Bass", volume=0.65),
    ])

    result = transport.get_session_info(song, {})

    assert result["tracks"][0]["volume"] == pytest.approx(0.7)
    assert result["tracks"][1]["volume"] == pytest.approx(0.65)


def test_get_session_info_volume_none_when_mixer_device_missing():
    """A track without mixer_device must not crash the whole scan — it
    should degrade to volume=None, same discipline as arm/has_midi_input."""
    transport = _load_transport_module()
    song = _FakeSong([_NoMixerTrack("Weird Track")])

    result = transport.get_session_info(song, {})

    assert len(result["tracks"]) == 1
    assert result["tracks"][0]["volume"] is None
    # Other fields must still be populated — the guard must not eat them.
    assert result["tracks"][0]["name"] == "Weird Track"


def test_get_session_info_volume_none_when_mixer_device_raises():
    """A track whose mixer_device access raises (LOM-fragile track type)
    must degrade to volume=None instead of aborting get_session_info."""
    transport = _load_transport_module()
    song = _FakeSong([
        _NormalTrack("Drums", volume=0.7),
        _RaisingMixerTrack("Fragile Bus"),
        _NormalTrack("Bass", volume=0.6),
    ])

    result = transport.get_session_info(song, {})

    assert len(result["tracks"]) == 3
    assert result["tracks"][0]["volume"] == pytest.approx(0.7)
    assert result["tracks"][1]["volume"] is None
    assert result["tracks"][1]["name"] == "Fragile Bus"
    assert result["tracks"][2]["volume"] == pytest.approx(0.6)
