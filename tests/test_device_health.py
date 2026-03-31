"""Device/analyzer health annotation regressions."""

from __future__ import annotations

import os
import sys
import types

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.m4l_bridge import SpectralCache
from mcp_server.tools import analyzer as analyzer_tools
from mcp_server.tools import devices as device_tools


def _ctx_with_ableton(ableton):
    return types.SimpleNamespace(lifespan_context={"ableton": ableton})


class _FakeAbleton:
    def __init__(self, responses):
        self._responses = responses

    def send_command(self, command, params=None):
        response = self._responses.get(command)
        if callable(response):
            return response(params or {})
        if response is None:
            raise AssertionError(f"Unexpected command: {command}")
        return response


def test_postflight_loaded_device_marks_opaque_plugin():
    ableton = _FakeAbleton({
        "get_track_info": {
            "devices": [
                {
                    "index": 0,
                    "name": "Drum Rack",
                    "class_name": "InstrumentGroupDevice",
                    "is_active": True,
                    "parameters": [{}, {}],
                },
                {
                    "index": 1,
                    "name": "CHOWTapeModel",
                    "class_name": "PluginDevice",
                    "is_active": True,
                    "parameters": [{}],
                },
            ]
        }
    })

    result = device_tools._postflight_loaded_device(
        _ctx_with_ableton(ableton),
        {"loaded": "CHOWTapeModel", "track_index": 0},
    )

    assert result["device_index"] == 1
    assert result["parameter_count"] == 1
    assert result["plugin_host_status"] == "opaque_or_failed"
    assert "opaque_or_failed_plugin" in result["health_flags"]
    assert result["mcp_sound_design_ready"] is False


def test_postflight_loaded_device_marks_sample_dependent_plugin():
    ableton = _FakeAbleton({
        "get_track_info": {
            "devices": [
                {
                    "index": 0,
                    "name": "iDensity (Instr)",
                    "class_name": "PluginDevice",
                    "is_active": True,
                    "parameters": [{}] * 25,
                },
            ]
        }
    })

    result = device_tools._postflight_loaded_device(
        _ctx_with_ableton(ableton),
        {"loaded": "iDensity (Instr)", "track_index": 1},
    )

    assert result["device_index"] == 0
    assert result["parameter_count"] == 25
    assert result["plugin_host_status"] == "host_visible"
    assert "sample_dependent" in result["health_flags"]
    assert result["mcp_sound_design_ready"] is False
    assert any("Requires source audio loaded" in warning for warning in result["warnings"])


def test_analyzer_error_explains_bridge_conflict(monkeypatch):
    cache = SpectralCache()
    ctx = types.SimpleNamespace(
        lifespan_context={
            "spectral": cache,
            "ableton": _FakeAbleton({
                "get_master_track": {
                    "devices": [
                        {
                            "index": 0,
                            "name": "LivePilot_Analyzer",
                            "class_name": "MxDeviceAudioEffect",
                            "is_active": True,
                            "parameters": [],
                        }
                    ]
                }
            }),
        }
    )

    analyzer_tools._get_spectral(ctx)
    monkeypatch.setattr(
        analyzer_tools,
        "_identify_port_holder",
        lambda port: "12345 (python3 -m mcp_server)",
    )

    with pytest.raises(ValueError, match="UDP bridge is not connected"):
        analyzer_tools._require_analyzer(cache)
