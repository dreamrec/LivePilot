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
    return router, arrangement


def test_router_missing_required_param_maps_to_invalid_param():
    router, _arrangement = _load_remote_modules()

    @router.register("needs_name")
    def _needs_name(song, params):
        return {"name": params["name"]}

    response = router.dispatch(None, {"id": "abc", "type": "needs_name", "params": {}})
    assert response["ok"] is False
    assert response["error"]["code"] == "INVALID_PARAM"
    assert "Missing required parameter" in response["error"]["message"]


def test_router_rejects_non_dict_params():
    router, _arrangement = _load_remote_modules()

    @router.register("noop")
    def _noop(song, params):
        return {"ok": True}

    response = router.dispatch(None, {"id": "abc", "type": "noop", "params": ["bad"]})
    assert response["ok"] is False
    assert response["error"]["code"] == "INVALID_PARAM"
    assert "params" in response["error"]["message"]


def test_arrangement_automation_unsupported_returns_outer_error():
    router, _arrangement = _load_remote_modules()

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
    assert response["error"]["code"] == "INVALID_PARAM"
    assert "Cannot create automation envelope" in response["error"]["message"]
