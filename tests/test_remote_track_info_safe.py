"""Regression tests for safe track-level device inspection."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = ROOT / "remote_script" / "LivePilot"


def _load_remote_tracks():
    for name in [
        "remote_script.LivePilot.tracks",
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

    _load("remote_script.LivePilot.router", REMOTE_ROOT / "router.py")
    _load("remote_script.LivePilot.utils", REMOTE_ROOT / "utils.py")
    return _load("remote_script.LivePilot.tracks", REMOTE_ROOT / "tracks.py")


class _Param:
    def __init__(self, name: str, value: float):
        self.name = name
        self.value = value
        self.min = 0.0
        self.max = 1.0
        self.is_quantized = False


class _ExplodingDevice:
    name = "Huge Plugin"
    class_name = "PluginDevice"
    is_active = True

    @property
    def parameters(self):
        raise RuntimeError("parameter list should not be touched")


class _CappedDevice:
    name = "Inspectable Plugin"
    class_name = "PluginDevice"
    is_active = True
    parameters = [_Param("A", 0.1), _Param("B", 0.2), _Param("C", 0.3)]


class _Mixer:
    volume = types.SimpleNamespace(value=0.5)
    panning = types.SimpleNamespace(value=0.0)
    sends = []


class _Track:
    name = "Track"
    color_index = 0
    mute = False
    solo = False
    is_foldable = False
    is_grouped = False
    arm = False
    has_midi_input = True
    has_audio_input = False
    current_monitoring_state = 1
    clip_slots = []
    mixer_device = _Mixer()

    def __init__(self, devices):
        self.devices = devices


class _Song:
    return_tracks = []
    master_track = _Track([])

    def __init__(self, devices):
        self.tracks = [_Track(devices)]


def test_get_track_info_omits_device_parameters_by_default():
    tracks = _load_remote_tracks()

    result = tracks.get_track_info(_Song([_ExplodingDevice()]), {"track_index": 0})

    assert result["devices"] == [
        {
            "index": 0,
            "name": "Huge Plugin",
            "class_name": "PluginDevice",
            "is_active": True,
        }
    ]


def test_get_track_info_parameter_sample_is_explicit_and_capped():
    tracks = _load_remote_tracks()

    result = tracks.get_track_info(
        _Song([_CappedDevice()]),
        {
            "track_index": 0,
            "include_device_parameters": True,
            "max_device_parameters": 2,
        },
    )

    device = result["devices"][0]
    assert [p["name"] for p in device["parameters"]] == ["A", "B"]
    assert device["parameters_returned"] == 2
    assert device["parameters_truncated"] is True
