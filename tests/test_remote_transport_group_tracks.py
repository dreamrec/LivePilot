"""Regression tests for the Remote Script's transport.get_session_info.

The Live Object Model raises a runtime exception (NOT AttributeError) when
unsupported properties are accessed on Group / Return tracks. `hasattr()`
returns True regardless, so the only safe pattern is try/except. Without
the guard, any session containing a Group track crashes get_session_info
with "Main and Return Tracks have no 'Arm' state!".
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = ROOT / "remote_script" / "LivePilot"


# ─── Module-pollution cleanup ───────────────────────────────────────────────
# The loader injects a fake `Live` module + stubbed remote_script.* modules
# into sys.modules. Without cleanup, these persist into subsequent test files
# (e.g. test_simpler_sample_native.py) and corrupt their imports.

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

    Mirrors the package shimming in test_remote_server_single_client.py —
    Ableton's Remote Script directory isn't a normal Python package, so
    we have to assemble the import graph by hand for hermetic tests.

    transport.py imports `version_detect.version_string()` and `get_api_features()`,
    which in turn `import Live` — the Ableton-only module. We inject a fake
    `Live` module + stub the version_detect helpers so the test can run on
    plain CPython without an Ableton process.
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

    # Fake the Ableton 'Live' module — version_detect.py reads attributes
    # off it but we don't care about the values for these tests.
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

    # Inject a stubbed version_detect to avoid the full Live introspection
    # path — transport.py only consumes version_string() + get_api_features().
    stub_vd = types.ModuleType("remote_script.LivePilot.version_detect")
    stub_vd.version_string = lambda: "12.4.0"
    stub_vd.get_api_features = lambda: {}
    sys.modules["remote_script.LivePilot.version_detect"] = stub_vd

    return _load("remote_script.LivePilot.transport", REMOTE_ROOT / "transport.py")


# ─── LOM doubles ────────────────────────────────────────────────────────────

class _NormalTrack:
    """A regular MIDI/audio track — exposes all properties cleanly."""
    def __init__(self, name: str, *, arm: bool = False,
                 has_midi: bool = True, has_audio: bool = False):
        self.name = name
        self.color_index = 0
        self.mute = False
        self.solo = False
        self.arm = arm
        self.has_midi_input = has_midi
        self.has_audio_input = has_audio


class _GroupTrack:
    """A Group track — accessing arm / has_midi_input / has_audio_input
    raises a RuntimeError, mirroring real LOM behavior. `hasattr()`
    intentionally returns True to mimic Live's actual __getattr__ trap."""
    def __init__(self, name: str):
        self.name = name
        self.color_index = 0
        self.mute = False
        self.solo = False

    def __getattr__(self, item):
        if item in ("arm", "has_midi_input", "has_audio_input"):
            raise RuntimeError(
                "Main and Return Tracks have no '%s' state!" % item.capitalize()
            )
        raise AttributeError(item)


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

def test_get_session_info_handles_group_tracks_without_crashing():
    """A session with one Group track must not raise from get_session_info."""
    transport = _load_transport_module()
    song = _FakeSong([
        _NormalTrack("Drums", arm=True),
        _GroupTrack("Bus 1"),  # the LOM-fragile one
        _NormalTrack("Bass", arm=False),
    ])

    result = transport.get_session_info(song, {})

    # The Group track lands in the response with arm/has_midi_input/has_audio_input
    # set to None — proving the try/except guard fired without aborting the loop.
    assert len(result["tracks"]) == 3
    drums, group, bass = result["tracks"]

    assert drums["name"] == "Drums"
    assert drums["arm"] is True
    assert drums["has_midi_input"] is True

    assert group["name"] == "Bus 1"
    assert group["arm"] is None, "Group track arm should be None, not crash"
    assert group["has_midi_input"] is None
    assert group["has_audio_input"] is None
    # Non-fragile fields should still be populated
    assert group["mute"] is False
    assert group["solo"] is False

    assert bass["name"] == "Bass"
    assert bass["arm"] is False


def test_get_session_info_normal_session_unaffected():
    """Sessions without any Group tracks should be unchanged by the fix."""
    transport = _load_transport_module()
    song = _FakeSong([
        _NormalTrack("Kick", arm=True, has_midi=True, has_audio=False),
        _NormalTrack("Vocal", arm=False, has_midi=False, has_audio=True),
    ])

    result = transport.get_session_info(song, {})

    assert len(result["tracks"]) == 2
    assert result["tracks"][0]["arm"] is True
    assert result["tracks"][0]["has_midi_input"] is True
    assert result["tracks"][1]["arm"] is False
    assert result["tracks"][1]["has_audio_input"] is True


def test_get_session_info_all_group_tracks():
    """An entire session of Group tracks (edge case) must not crash."""
    transport = _load_transport_module()
    song = _FakeSong([
        _GroupTrack("Group A"),
        _GroupTrack("Group B"),
    ])

    result = transport.get_session_info(song, {})

    assert len(result["tracks"]) == 2
    for t in result["tracks"]:
        assert t["arm"] is None
        assert t["has_midi_input"] is None
        assert t["has_audio_input"] is None


def test_get_session_info_lom_failure_does_not_swallow_other_track_data():
    """The arm-property guard must not eat unrelated fields like name/mute."""
    transport = _load_transport_module()
    song = _FakeSong([_GroupTrack("My Group")])

    result = transport.get_session_info(song, {})

    track = result["tracks"][0]
    # These come from explicit attrs that don't go through __getattr__,
    # so they should be present even when the LOM-fragile ones aren't.
    assert track["name"] == "My Group"
    assert track["mute"] is False
    assert track["solo"] is False
    assert track["color_index"] == 0
    assert track["index"] == 0
