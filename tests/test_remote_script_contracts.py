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
