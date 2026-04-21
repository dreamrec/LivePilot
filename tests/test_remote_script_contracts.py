"""Contract tests for remote_script modules without importing Ableton-only __init__."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = ROOT / "remote_script" / "LivePilot"


def _load_remote_modules():
    for name in [
        "remote_script.LivePilot.diagnostics",
        "remote_script.LivePilot.arrangement",
        "remote_script.LivePilot.router",
        "remote_script.LivePilot.utils",
        "remote_script.LivePilot",
        "remote_script",
    ]:
        sys.modules.pop(name, None)

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
    router = _load("remote_script.LivePilot.router", REMOTE_ROOT / "router.py")
    arrangement = _load("remote_script.LivePilot.arrangement", REMOTE_ROOT / "arrangement.py")
    diagnostics = _load("remote_script.LivePilot.diagnostics", REMOTE_ROOT / "diagnostics.py")
    return router, arrangement, diagnostics


def _load_remote_clips():
    """Load remote_script.LivePilot.clips with its dependencies isolated."""
    for name in [
        "remote_script.LivePilot.clips",
        "remote_script.LivePilot.router",
        "remote_script.LivePilot.utils",
        "remote_script.LivePilot",
        "remote_script",
    ]:
        sys.modules.pop(name, None)

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
    router = _load("remote_script.LivePilot.router", REMOTE_ROOT / "router.py")
    clips = _load("remote_script.LivePilot.clips", REMOTE_ROOT / "clips.py")
    return router, clips


def _load_remote_mixing():
    for name in [
        "remote_script.LivePilot.mixing",
        "remote_script.LivePilot.router",
        "remote_script.LivePilot.utils",
        "remote_script.LivePilot",
        "remote_script",
    ]:
        sys.modules.pop(name, None)

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
    return _load("remote_script.LivePilot.mixing", REMOTE_ROOT / "mixing.py")


def test_router_missing_required_param_maps_to_invalid_param():
    router, _arrangement, _diagnostics = _load_remote_modules()

    @router.register("needs_name")
    def _needs_name(song, params):
        return {"name": params["name"]}

    response = router.dispatch(None, {"id": "abc", "type": "needs_name", "params": {}})
    assert response["ok"] is False
    assert response["error"]["code"] == "INVALID_PARAM"
    assert "Missing required parameter" in response["error"]["message"]


def test_router_rejects_non_dict_params():
    router, _arrangement, _diagnostics = _load_remote_modules()

    @router.register("noop")
    def _noop(song, params):
        return {"ok": True}

    response = router.dispatch(None, {"id": "abc", "type": "noop", "params": ["bad"]})
    assert response["ok"] is False
    assert response["error"]["code"] == "INVALID_PARAM"
    assert "params" in response["error"]["message"]


def test_arrangement_automation_unsupported_returns_outer_error():
    router, _arrangement, _diagnostics = _load_remote_modules()

    class _Param:
        def __init__(self, name: str):
            self.name = name
            self.min = 0.0
            self.max = 1.0

    class _Mixer:
        def __init__(self):
            self.volume = _Param("Volume")
            self.panning = _Param("Pan")
            self.sends = []

    class _Clip:
        def automation_envelope(self, parameter):
            return None

        def create_automation_envelope(self, parameter):
            return None

    class _Track:
        def __init__(self):
            self.arrangement_clips = [_Clip()]
            self.mixer_device = _Mixer()
            self.devices = []

    class _Song:
        def __init__(self):
            self.tracks = [_Track()]

    response = router.dispatch(
        _Song(),
        {
            "id": "abc",
            "type": "set_arrangement_automation",
            "params": {
                "track_index": 0,
                "clip_index": 0,
                "parameter_type": "volume",
                "points": [{"time": 0.0, "value": 0.5}],
            },
        },
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "STATE_ERROR"
    assert "Cannot create automation envelope" in response["error"]["message"]


def test_session_diagnostics_flags_plugin_health_categories():
    _router, _arrangement, diagnostics = _load_remote_modules()

    class _Param:
        pass

    class _Device:
        def __init__(self, name: str, class_name: str, parameter_count: int):
            self.name = name
            self.class_name = class_name
            self.parameters = [_Param() for _ in range(parameter_count)]

    class _Slot:
        has_clip = True

    class _Track:
        def __init__(self):
            self.arm = False
            self.solo = False
            self.mute = False
            self.name = "Lead"
            self.clip_slots = [_Slot()]
            self.has_midi_input = False
            self.devices = [
                _Device("CHOWTapeModel", "PluginDevice", 1),
                _Device("iDensity (Instr)", "PluginDevice", 25),
            ]

    class _Scene:
        name = "A"

    class _Song:
        tracks = [_Track()]
        scenes = [_Scene()]
        return_tracks = []

    result = diagnostics.get_session_diagnostics(_Song(), {})
    issue_types = {issue["type"] for issue in result["issues"]}

    assert "opaque_or_failed_plugins" in issue_types
    assert "sample_dependent_devices" in issue_types


def test_session_diagnostics_skips_missing_track_properties():
    _router, _arrangement, diagnostics = _load_remote_modules()

    class _Slot:
        has_clip = True

    class _Track:
        name = "Main"
        clip_slots = [_Slot()]
        devices = []
        has_midi_input = False

        @property
        def arm(self):
            raise RuntimeError("missing arm")

        @property
        def solo(self):
            raise RuntimeError("missing solo")

        @property
        def mute(self):
            raise RuntimeError("missing mute")

    class _Scene:
        name = "A"

    class _Song:
        tracks = [_Track()]
        scenes = [_Scene()]
        return_tracks = []

    result = diagnostics.get_session_diagnostics(_Song(), {})
    assert isinstance(result, dict)
    assert "healthy" in result


def test_get_track_meters_zeroes_muted_tracks():
    mixing = _load_remote_mixing()

    class _Track:
        def __init__(self, name: str, mute: bool, level: float):
            self.name = name
            self.mute = mute
            self.has_audio_output = True
            self.output_meter_level = level
            self.output_meter_left = level
            self.output_meter_right = level

    class _Song:
        tracks = [_Track("Open", False, 0.42), _Track("Muted", True, 0.77)]

    result = mixing.get_track_meters(_Song(), {"include_stereo": True})

    assert result["tracks"][0]["level"] == 0.42
    assert result["tracks"][1]["level"] == 0.0
    assert result["tracks"][1]["left"] == 0.0
    assert result["tracks"][1]["right"] == 0.0


# ─── BUG-A1 / A4 / A5 — Batch 2 regressions ─────────────────────────────────

def _make_audio_clip(pitch_coarse=0, pitch_fine=0.0, gain=1.0):
    """Minimal audio-clip stub that exposes the attributes get_clip_info touches."""
    class _Clip:
        pass
    c = _Clip()
    c.name = "audio"
    c.color_index = 0
    c.length = 4.0
    c.is_playing = False
    c.is_recording = False
    c.is_midi_clip = False
    c.is_audio_clip = True
    c.looping = True
    c.loop_start = 0.0
    c.loop_end = 4.0
    c.start_marker = 0.0
    c.end_marker = 4.0
    c.launch_mode = 0
    c.launch_quantization = 0
    c.warping = True
    c.warp_mode = 4
    c.pitch_coarse = pitch_coarse
    c.pitch_fine = pitch_fine
    c.gain = gain
    return c


def _song_with_clip(clip):
    """Build a minimal Song-like object holding one track with one clip slot."""
    class _Slot:
        pass

    class _Track:
        pass

    class _Song:
        pass

    slot = _Slot()
    slot.clip = clip
    track = _Track()
    track.clip_slots = [slot]
    song = _Song()
    song.tracks = [track]
    song.master_track = None
    song.return_tracks = []
    return song


def test_bug_a4_get_clip_info_exposes_audio_pitch_and_gain():
    """BUG-A4: get_clip_info on an audio clip must include pitch_coarse /
    pitch_fine / gain so callers can detect sample-vs-session key drift."""
    _router, clips = _load_remote_clips()
    clip = _make_audio_clip(pitch_coarse=-1, pitch_fine=12.5, gain=0.85)
    song = _song_with_clip(clip)

    info = clips.get_clip_info(song, {"track_index": 0, "clip_index": 0})

    assert info["is_audio_clip"] is True
    assert info["pitch_coarse"] == -1
    assert info["pitch_fine"] == 12.5
    assert info["gain"] == 0.85


def test_bug_a4_midi_clips_do_not_report_pitch_fields():
    """Pitch fields are audio-only in Live — midi clips must not leak
    fake values into the response."""
    _router, clips = _load_remote_clips()

    class _MidiClip:
        name = "midi"
        color_index = 0
        length = 4.0
        is_playing = False
        is_recording = False
        is_midi_clip = True
        is_audio_clip = False
        looping = True
        loop_start = 0.0
        loop_end = 4.0
        start_marker = 0.0
        end_marker = 4.0
        launch_mode = 0
        launch_quantization = 0

    song = _song_with_clip(_MidiClip())
    info = clips.get_clip_info(song, {"track_index": 0, "clip_index": 0})

    assert info["is_midi_clip"] is True
    assert "pitch_coarse" not in info
    assert "pitch_fine" not in info
    assert "gain" not in info


def test_bug_a5_set_clip_pitch_writes_coarse_and_fine():
    """BUG-A5: set_clip_pitch must mutate pitch_coarse / pitch_fine / gain."""
    _router, clips = _load_remote_clips()
    clip = _make_audio_clip()
    song = _song_with_clip(clip)

    result = clips.set_clip_pitch(song, {
        "track_index": 0, "clip_index": 0,
        "coarse": -1, "fine": -7.5, "gain": 0.5,
    })

    assert clip.pitch_coarse == -1
    assert clip.pitch_fine == -7.5
    assert clip.gain == 0.5
    # Response should round-trip the new values
    assert result["pitch_coarse"] == -1
    assert result["pitch_fine"] == -7.5
    assert result["gain"] == 0.5


def test_bug_a5_set_clip_pitch_rejects_midi_clips():
    """MIDI clips don't have sample pitch — caller mistake should error."""
    import pytest
    _router, clips = _load_remote_clips()

    class _MidiClip:
        is_midi_clip = True
        is_audio_clip = False

    slot = type("_Slot", (), {"clip": _MidiClip()})()
    track = type("_Track", (), {"clip_slots": [slot]})()
    song = type("_Song", (), {
        "tracks": [track], "master_track": None, "return_tracks": [],
    })()

    with pytest.raises(ValueError, match="audio clips"):
        clips.set_clip_pitch(song, {
            "track_index": 0, "clip_index": 0, "coarse": 1,
        })


def test_bug_a5_set_clip_pitch_requires_at_least_one_param():
    import pytest
    _router, clips = _load_remote_clips()
    song = _song_with_clip(_make_audio_clip())

    with pytest.raises(ValueError, match="at least one"):
        clips.set_clip_pitch(song, {"track_index": 0, "clip_index": 0})


def test_bug_a5_set_clip_pitch_rejects_out_of_range_coarse():
    import pytest
    _router, clips = _load_remote_clips()
    song = _song_with_clip(_make_audio_clip())

    with pytest.raises(ValueError, match="semitones"):
        clips.set_clip_pitch(song, {
            "track_index": 0, "clip_index": 0, "coarse": 500,
        })


def _compressor_routing_song(compressor):
    class _Track:
        def __init__(self, devices):
            self.devices = devices

    class _Song:
        tracks = [_Track([compressor])]
        return_tracks = []
        master_track = None

    return _Song()


def test_bug_a3_reopen_legacy_compressor_uses_flat_surface():
    """Legacy Compressor (I) exposes the flat available_sidechain_input_*
    attrs and the handler should keep matching by display_name — this is
    the original Batch 19 behavior that must not regress."""
    mixing = _load_remote_mixing()

    class _RT:
        def __init__(self, name):
            self.display_name = name

    class _RC:
        def __init__(self, name):
            self.display_name = name

    rt_kick, rt_ext = _RT("1-KICK"), _RT("Ext. In")
    rc_pre, rc_post = _RC("Pre FX"), _RC("Post FX")

    class _Compressor:
        class_name = "Compressor"
        name = "Compressor"
        parameters = []

        def __init__(self):
            self.sidechain_enabled = False
            self.available_sidechain_input_routing_types = [rt_kick, rt_ext]
            self.available_sidechain_input_routing_channels = [rc_pre, rc_post]
            self.sidechain_input_routing_type = rt_ext
            self.sidechain_input_routing_channel = rc_post

    comp = _Compressor()
    result = mixing.set_compressor_sidechain(
        _compressor_routing_song(comp),
        {
            "track_index": 0, "device_index": 0,
            "source_type": "1-KICK", "source_channel": "Pre FX",
        },
    )
    assert result["ok"] is True
    assert comp.sidechain_enabled is True
    assert comp.sidechain_input_routing_type is rt_kick
    assert comp.sidechain_input_routing_channel is rc_pre
    assert result["sidechain"]["type"] == "1-KICK"
    assert result["sidechain"]["channel"] == "Pre FX"


def test_bug_a3_reopen_compressor2_missing_surface_raises_with_diagnostic():
    """Compressor2 without any known LOM sidechain surface — the error
    must embed a dir() audit so the next run reveals what IS exposed.
    Regression guard for the 2026-04-21 Live 12.3.6 regression where
    available_sidechain_input_routing_types disappeared on Compressor2."""
    import pytest

    mixing = _load_remote_mixing()

    class _Compressor2:
        class_name = "Compressor2"
        name = "Compressor"
        parameters = []

        def __init__(self):
            self.sidechain_enabled = False
            # Carry a distinct routing-related attr so we can confirm
            # the diagnostic actually walks dir() and surfaces it.
            self.some_routing_marker = "probe-breadcrumb"

    comp = _Compressor2()
    with pytest.raises(ValueError) as exc:
        mixing.set_compressor_sidechain(
            _compressor_routing_song(comp),
            {"track_index": 0, "device_index": 0, "source_type": "1-KICK"},
        )
    msg = str(exc.value)
    assert "doesn't expose a sidechain routing surface" in msg
    assert "Compressor2" in msg
    assert "Inspected attrs:" in msg
    assert "some_routing_marker" in msg  # diagnostic walked dir()


def test_bug_a3_reopen_compressor2_nested_sidechain_input_surface():
    """Compressor2 hypothesis: routing moved to a nested sidechain_input
    DeviceIO child. The probe should find it and route writes through."""
    mixing = _load_remote_mixing()

    class _RT:
        def __init__(self, name):
            self.display_name = name

    class _RC:
        def __init__(self, name):
            self.display_name = name

    rt_drums = _RT("1-DRUMS")
    rc_post = _RC("Post FX")

    class _DeviceIO:
        def __init__(self):
            self.available_routing_types = [rt_drums]
            self.available_routing_channels = [rc_post]
            self.routing_type = rt_drums
            self.routing_channel = rc_post

    class _Compressor2:
        class_name = "Compressor2"
        name = "Compressor"
        parameters = []

        def __init__(self):
            self.sidechain_enabled = False
            self.sidechain_input = _DeviceIO()

    comp = _Compressor2()
    result = mixing.set_compressor_sidechain(
        _compressor_routing_song(comp),
        {
            "track_index": 0, "device_index": 0,
            "source_type": "1-DRUMS", "source_channel": "Post FX",
        },
    )
    assert result["ok"] is True
    assert comp.sidechain_input.routing_type is rt_drums
    assert comp.sidechain_input.routing_channel is rc_post
    assert result["sidechain"]["type"] == "1-DRUMS"
    assert result["sidechain"]["channel"] == "Post FX"


def test_bug_a3_reopen_mismatched_source_type_lists_available():
    """When source_type doesn't match, the error must list the options
    from the discovered surface (not a hardcoded assumption)."""
    import pytest

    mixing = _load_remote_mixing()

    class _RT:
        def __init__(self, name):
            self.display_name = name

    class _Compressor:
        class_name = "Compressor"
        name = "Compressor"
        parameters = []

        def __init__(self):
            self.sidechain_enabled = False
            self.available_sidechain_input_routing_types = [_RT("Ext. In")]
            self.available_sidechain_input_routing_channels = []
            self.sidechain_input_routing_type = None
            self.sidechain_input_routing_channel = None

    with pytest.raises(ValueError) as exc:
        mixing.set_compressor_sidechain(
            _compressor_routing_song(_Compressor()),
            {"track_index": 0, "device_index": 0, "source_type": "1-KICK"},
        )
    msg = str(exc.value)
    assert "Sidechain input type '1-KICK' not found" in msg
    assert "Ext. In" in msg
    # surface tag helps future debugging tell us which shape matched
    assert "flat device.sidechain_input_routing_*" in msg


def test_bug_a1_ping_embeds_remote_script_version_and_commands():
    """BUG-A1: ping response must include remote_script_version and the
    handler set so the MCP server can detect stale installs."""
    router, clips = _load_remote_clips()

    # inject a known version onto the LivePilot pkg — mimics __init__.py
    live_pkg = sys.modules["remote_script.LivePilot"]
    live_pkg.__version__ = "1.10.6"

    response = router.dispatch(None, {"id": "p", "type": "ping", "params": {}})
    assert response["ok"] is True
    result = response["result"]
    assert result["pong"] is True
    assert result["remote_script_version"] == "1.10.6"
    # commands list should include the newly-added set_clip_pitch handler
    assert "set_clip_pitch" in result["commands"]
    assert "get_clip_info" in result["commands"]
