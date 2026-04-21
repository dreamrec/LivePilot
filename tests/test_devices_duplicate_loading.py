"""Tests for find_and_load_device's duplicate-detection behavior.

Guards against the 2026-04-21 bug where auto-loading LivePilot_Analyzer
at session start produced TWO analyzers on the master because
find_and_load_device blindly appended even when an identical device was
already in the chain.

Follows the pattern in test_remote_script_contracts.py — fake out the
`Live` module + the `remote_script.LivePilot` package so we can import
devices.py directly and call its handlers with lightweight stubs.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = ROOT / "remote_script" / "LivePilot"


def _install_fake_live():
    """Install a fake `Live` module before loading remote_script modules.

    devices.py does `import Live` at module top, and version_detect.py
    touches Live.Application to detect the Live version. Returning
    (12, 0, 0) from the fake means has_feature('insert_device') is False
    — so the 12.3 native-insert fast path is bypassed in tests and we
    can observe the duplicate-check logic in isolation.
    """
    app = types.SimpleNamespace(
        get_major_version=lambda: 12,
        get_minor_version=lambda: 0,
        get_bugfix_version=lambda: 0,
        browser=types.SimpleNamespace(),
    )
    application_ns = types.SimpleNamespace(get_application=lambda: app)
    live = types.ModuleType("Live")
    live.Application = application_ns
    sys.modules["Live"] = live


def _load_remote_devices():
    for name in [
        "remote_script.LivePilot.devices",
        "remote_script.LivePilot.version_detect",
        "remote_script.LivePilot.router",
        "remote_script.LivePilot.utils",
        "remote_script.LivePilot",
        "remote_script",
    ]:
        sys.modules.pop(name, None)

    _install_fake_live()

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
    _load("remote_script.LivePilot.version_detect",
          REMOTE_ROOT / "version_detect.py")
    return _load("remote_script.LivePilot.devices",
                 REMOTE_ROOT / "devices.py")


# ── Stubs ────────────────────────────────────────────────────────────────


class _FakeDevice:
    def __init__(self, name: str):
        self.name = name


class _FakeTrack:
    def __init__(self, devices, name: str = "Master"):
        self.devices = list(devices)
        self.name = name


class _FakeSong:
    """Minimal Song — master_track + tracks + return_tracks."""
    def __init__(self, master_devices=None, tracks=None):
        self.master_track = _FakeTrack(master_devices or [], name="Master")
        self.tracks = list(tracks or [])
        self.return_tracks = []


# ── Tests ────────────────────────────────────────────────────────────────


def test_returns_already_present_when_same_name_exists_on_master():
    """The actual 2026-04-21 regression: auto-loaded analyzer twice."""
    devices = _load_remote_devices()
    song = _FakeSong(master_devices=[_FakeDevice("LivePilot_Analyzer")])

    result = devices.find_and_load_device(song, {
        "track_index": -1000,
        "device_name": "LivePilot_Analyzer",
    })

    assert result["already_present"] is True
    assert result["device_index"] == 0
    assert result["loaded"] == "LivePilot_Analyzer"
    assert result["track_index"] == -1000
    # The critical assertion: chain is still one device, NOT two.
    assert len(song.master_track.devices) == 1


def test_already_present_index_points_to_existing_device():
    """When duplicate is not at index 0, the returned device_index must
    point to the existing instance — not 0, not -1, not len-1."""
    devices = _load_remote_devices()
    song = _FakeSong(master_devices=[
        _FakeDevice("EQ Eight"),
        _FakeDevice("Compressor"),
        _FakeDevice("LivePilot_Analyzer"),
    ])

    result = devices.find_and_load_device(song, {
        "track_index": -1000,
        "device_name": "LivePilot_Analyzer",
    })

    assert result["already_present"] is True
    assert result["device_index"] == 2


def test_case_insensitive_duplicate_match():
    devices = _load_remote_devices()
    song = _FakeSong(master_devices=[_FakeDevice("LivePilot_Analyzer")])

    result = devices.find_and_load_device(song, {
        "track_index": -1000,
        "device_name": "livepilot_analyzer",
    })

    assert result["already_present"] is True


def test_underscore_vs_space_normalized_duplicate_match():
    """The frozen .amxd ships different names across versions — sometimes
    'LivePilot_Analyzer', sometimes 'LivePilot Analyzer'. Both should be
    detected as duplicates of the other. (See _require_analyzer in
    mcp_server/tools/devices.py for the same normalization.)"""
    devices = _load_remote_devices()
    song = _FakeSong(master_devices=[_FakeDevice("LivePilot Analyzer")])

    result = devices.find_and_load_device(song, {
        "track_index": -1000,
        "device_name": "LivePilot_Analyzer",
    })

    assert result["already_present"] is True


def test_allow_duplicate_bypasses_check(monkeypatch):
    """allow_duplicate=True must skip the check and proceed to load.
    We observe 'proceeded to load' by making _get_browser raise a sentinel
    — if we see that error, the duplicate check was skipped as intended."""
    devices = _load_remote_devices()
    song = _FakeSong(master_devices=[_FakeDevice("LivePilot_Analyzer")])

    def _sentinel_browser():
        raise RuntimeError("browser_queried_sentinel")
    monkeypatch.setattr(devices, "_get_browser", _sentinel_browser)

    with pytest.raises(RuntimeError, match="browser_queried_sentinel"):
        devices.find_and_load_device(song, {
            "track_index": -1000,
            "device_name": "LivePilot_Analyzer",
            "allow_duplicate": True,
        })


def test_no_duplicate_proceeds_to_browser_search(monkeypatch):
    """When no matching device exists, the handler must fall through to
    the normal load path (not short-circuit with already_present)."""
    devices = _load_remote_devices()
    song = _FakeSong(master_devices=[_FakeDevice("Reverb")])

    browser_calls = []
    def _sentinel_browser():
        browser_calls.append(1)
        raise RuntimeError("browser_queried_sentinel")
    monkeypatch.setattr(devices, "_get_browser", _sentinel_browser)

    with pytest.raises(RuntimeError, match="browser_queried_sentinel"):
        devices.find_and_load_device(song, {
            "track_index": -1000,
            "device_name": "LivePilot_Analyzer",
        })
    assert browser_calls == [1]


def test_duplicate_check_works_on_regular_tracks():
    """Not just master — duplicate detection on a regular track 0."""
    devices = _load_remote_devices()
    regular = _FakeTrack([_FakeDevice("Reverb")], name="Audio 1")
    song = _FakeSong(tracks=[regular])

    result = devices.find_and_load_device(song, {
        "track_index": 0,
        "device_name": "Reverb",
    })

    assert result["already_present"] is True
    assert result["device_index"] == 0
    assert result["track_index"] == 0
    assert len(regular.devices) == 1


def test_empty_track_proceeds_to_browser_search(monkeypatch):
    """Empty device chain — duplicate check must not raise, just fall through."""
    devices = _load_remote_devices()
    song = _FakeSong(master_devices=[])

    def _sentinel_browser():
        raise RuntimeError("browser_queried_sentinel")
    monkeypatch.setattr(devices, "_get_browser", _sentinel_browser)

    with pytest.raises(RuntimeError, match="browser_queried_sentinel"):
        devices.find_and_load_device(song, {
            "track_index": -1000,
            "device_name": "LivePilot_Analyzer",
        })


def test_different_device_on_chain_does_not_trip_duplicate(monkeypatch):
    """A Reverb on the master must not be mistaken for LivePilot_Analyzer."""
    devices = _load_remote_devices()
    song = _FakeSong(master_devices=[
        _FakeDevice("Reverb"),
        _FakeDevice("EQ Eight"),
    ])

    def _sentinel_browser():
        raise RuntimeError("browser_queried_sentinel")
    monkeypatch.setattr(devices, "_get_browser", _sentinel_browser)

    with pytest.raises(RuntimeError, match="browser_queried_sentinel"):
        devices.find_and_load_device(song, {
            "track_index": -1000,
            "device_name": "LivePilot_Analyzer",
        })
