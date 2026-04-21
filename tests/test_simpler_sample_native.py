# tests/test_simpler_sample_native.py
"""Live 12.4+ native SimplerDevice.replace_sample handler.

The handler lives in remote_script/LivePilot/simpler_sample.py. Tests
patch the Live module and the router's @register decorator to capture
behavior without importing Ableton.
"""

import sys
import types
from unittest.mock import MagicMock


# ── Fake Live module with an Application that exposes a pinned version ──

def _install_fake_live(major: int, minor: int, patch: int) -> None:
    """Install a fake Live module in sys.modules with a pinned version."""
    live = types.ModuleType("Live")
    app_module = types.ModuleType("Live.Application")

    class _FakeApp:
        def get_major_version(self):
            return major

        def get_minor_version(self):
            return minor

        def get_bugfix_version(self):
            return patch

    app_module.get_application = lambda: _FakeApp()
    live.Application = app_module
    sys.modules["Live"] = live
    sys.modules["Live.Application"] = app_module


def _reset_version_detect_cache():
    """Clear the module-level _cached_version so the next version probe runs fresh."""
    vd = sys.modules.get("remote_script.LivePilot.version_detect")
    if vd is not None:
        vd._cached_version = None


# ── Fake Song / Track / Device objects ──────────────────────────────────

def _fake_song_with_simpler_at(track_index: int, device_index: int,
                                class_name: str = "SimplerDevice"):
    simpler = MagicMock()
    simpler.class_name = class_name
    simpler.name = "Simpler"
    simpler.replace_sample = MagicMock()  # The 12.4 API under test.

    track = MagicMock()
    track.devices = [MagicMock() for _ in range(device_index)] + [simpler]
    track.name = f"track_{track_index}"

    song = MagicMock()
    song.tracks = [MagicMock() for _ in range(track_index)] + [track]
    return song, track, simpler


# ── Fake handler registry so @register decorators are inspectable ──────

class _FakeRegistry:
    def __init__(self):
        self.handlers = {}

    def register(self, name):
        def decorator(func):
            self.handlers[name] = func
            return func
        return decorator


def _fresh_import(version_tuple: tuple) -> _FakeRegistry:
    """Install fake Live + registry, import (or reload) the handler module."""
    _install_fake_live(*version_tuple)
    _reset_version_detect_cache()

    reg = _FakeRegistry()
    fake_router = types.ModuleType("remote_script.LivePilot.router")
    fake_router.register = reg.register
    sys.modules["remote_script.LivePilot.router"] = fake_router

    # Stub the package namespaces so Python doesn't execute __init__.py
    # (which imports _Framework.ControlSurface — only available inside Ableton).
    # __path__ must be set so CPython treats the stub as a package, allowing
    # submodule imports like remote_script.LivePilot.simpler_sample.
    import os as _os
    _rs_path = _os.path.join(_os.path.dirname(__file__), "..", "remote_script")
    _lp_path = _os.path.join(_rs_path, "LivePilot")

    if "remote_script" not in sys.modules:
        _rs_mod = types.ModuleType("remote_script")
        _rs_mod.__path__ = [_rs_path]
        _rs_mod.__package__ = "remote_script"
        sys.modules["remote_script"] = _rs_mod

    if "remote_script.LivePilot" not in sys.modules:
        _lp_mod = types.ModuleType("remote_script.LivePilot")
        _lp_mod.__path__ = [_lp_path]
        _lp_mod.__package__ = "remote_script.LivePilot"
        sys.modules["remote_script.LivePilot"] = _lp_mod

    import importlib
    target = "remote_script.LivePilot.simpler_sample"
    if target in sys.modules:
        importlib.reload(sys.modules[target])
    else:
        importlib.import_module(target)

    return reg


def _cleanup():
    """Remove patched modules so other tests aren't affected."""
    for key in list(sys.modules):
        if key == "Live" or key.startswith("Live."):
            sys.modules.pop(key, None)
        if key.startswith("remote_script.LivePilot."):
            sys.modules.pop(key, None)


# ── Tests ───────────────────────────────────────────────────────────────

class TestReplaceSampleNative:
    def teardown_method(self):
        _cleanup()

    def test_handler_is_registered(self):
        reg = _fresh_import((12, 4, 0))
        assert "replace_sample_native" in reg.handlers

    def test_calls_simpler_replace_sample_with_path(self):
        reg = _fresh_import((12, 4, 0))
        song, _track, simpler = _fake_song_with_simpler_at(track_index=1, device_index=0)
        handler = reg.handlers["replace_sample_native"]

        result = handler(song, {"track_index": 1, "device_index": 0,
                                "file_path": "/tmp/audio.wav"})

        simpler.replace_sample.assert_called_once_with("/tmp/audio.wav")
        assert result["sample_loaded"] is True
        assert result["track_index"] == 1
        assert result["device_index"] == 0
        assert result["method"] == "native_12_4"

    def test_rejects_non_simpler_device(self):
        reg = _fresh_import((12, 4, 0))
        song, _t, simpler = _fake_song_with_simpler_at(
            track_index=0, device_index=0, class_name="OperatorDevice"
        )
        handler = reg.handlers["replace_sample_native"]

        result = handler(song, {"track_index": 0, "device_index": 0,
                                "file_path": "/tmp/x.wav"})

        assert "error" in result
        assert "Simpler" in result["error"]
        simpler.replace_sample.assert_not_called()

    def test_rejects_missing_track(self):
        reg = _fresh_import((12, 4, 0))
        song = MagicMock()
        song.tracks = []
        handler = reg.handlers["replace_sample_native"]

        result = handler(song, {"track_index": 0, "device_index": 0,
                                "file_path": "/tmp/x.wav"})

        assert "error" in result
        assert result.get("code") == "INDEX_ERROR"

    def test_rejects_missing_device(self):
        reg = _fresh_import((12, 4, 0))
        track = MagicMock()
        track.devices = []
        song = MagicMock()
        song.tracks = [track]
        handler = reg.handlers["replace_sample_native"]

        result = handler(song, {"track_index": 0, "device_index": 0,
                                "file_path": "/tmp/x.wav"})

        assert "error" in result
        assert result.get("code") == "INDEX_ERROR"

    def test_wraps_replace_sample_exception_as_structured_error(self):
        reg = _fresh_import((12, 4, 0))
        song, _t, simpler = _fake_song_with_simpler_at(track_index=0, device_index=0)
        simpler.replace_sample.side_effect = RuntimeError("file not found")
        handler = reg.handlers["replace_sample_native"]

        result = handler(song, {"track_index": 0, "device_index": 0,
                                "file_path": "/nope.wav"})

        assert "error" in result
        assert result.get("code") == "INTERNAL"
        assert "file not found" in result["error"]


class TestVersionGate:
    def teardown_method(self):
        _cleanup()

    def test_raises_state_error_when_live_is_12_3(self):
        reg = _fresh_import((12, 3, 6))

        song, _t, simpler = _fake_song_with_simpler_at(track_index=0, device_index=0)
        handler = reg.handlers["replace_sample_native"]

        result = handler(song, {"track_index": 0, "device_index": 0,
                                "file_path": "/x.wav"})

        assert "error" in result
        assert "12.4" in result["error"]
        assert result.get("code") == "STATE_ERROR"
        simpler.replace_sample.assert_not_called()
