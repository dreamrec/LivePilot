"""Tests for the follow-up work after the 2026-04-22 bug batch.

Covers:
  - `rename_chain` MCP tool + remote-script `set_chain_name` handler (Phase E)
  - Drum root-note auto-detection in post-load hygiene (Fix #18)
  - Role-aware defaults in `load_browser_item` (Fix #17)
  - `verify_device_health` tool wiring (Fix #19)
  - HTTPS bridge endpoint gating + error shapes (Phase I)
"""

from __future__ import annotations

import asyncio
import os
from unittest import mock

import pytest


# ── Phase E: rename_chain ──────────────────────────────────────────────


def test_rename_chain_exists_in_mcp_layer():
    from mcp_server.tools.devices import rename_chain
    import inspect
    sig = inspect.signature(rename_chain)
    assert "track_index" in sig.parameters
    assert "device_index" in sig.parameters
    assert "chain_index" in sig.parameters
    assert "name" in sig.parameters


def test_rename_chain_rejects_empty_name():
    """Empty/whitespace-only names must raise before round-tripping."""
    from mcp_server.tools.devices import rename_chain
    from types import SimpleNamespace

    ctx = SimpleNamespace(lifespan_context={"ableton": mock.MagicMock()})

    with pytest.raises(ValueError, match="name cannot be empty"):
        rename_chain(ctx, track_index=0, device_index=0, chain_index=0, name="")
    with pytest.raises(ValueError, match="name cannot be empty"):
        rename_chain(ctx, track_index=0, device_index=0, chain_index=0, name="   ")


# ── Fix #18: drum root-note detection ──────────────────────────────────


def test_drum_root_detection_common_kit_pieces():
    """Standard drum filenames map to the GM-ish pad MIDI notes."""
    from mcp_server.tools._analyzer_engine import _detect_drum_root_note
    cases = {
        "/samples/Kick_Hard_01.wav": 36,
        "/samples/KICK-DEEP.wav": 36,
        "/samples/Snare_Dry.wav": 38,
        "/samples/808_Sub.wav": 36,
        "/samples/Clap_Wet.wav": 39,
        "/samples/Closed_Hat_01.wav": 42,
        "/samples/open_hat.wav": 46,
        "/samples/HiHat_Open.wav": 46,  # "hihat_open" → but we match "open_hat" first at len 8
        "/samples/Ride_Bell.wav": 51,
        "/samples/Crash_Medium.wav": 49,
    }
    for path, expected in cases.items():
        assert _detect_drum_root_note(path) == expected, path


def test_drum_root_detection_returns_none_for_non_drum_filenames():
    from mcp_server.tools._analyzer_engine import _detect_drum_root_note
    assert _detect_drum_root_note("/samples/Dreamy_Pad_Cm.wav") is None
    assert _detect_drum_root_note("/samples/Vocal_Chop_02.wav") is None
    assert _detect_drum_root_note("/samples/bass_stab_120bpm.wav") is None


def test_drum_root_detection_prefers_specific_matches():
    """'closed_hat' must beat 'hat' via longest-match ordering."""
    from mcp_server.tools._analyzer_engine import _detect_drum_root_note
    # 'closed_hat' is longer than 'hat' — result should be 42 (closed HH),
    # not whatever 'hat' alone maps to (also 42, but via different key).
    assert _detect_drum_root_note("/samples/closed_hat_01.wav") == 42
    # Open hat should NOT match closed_hat/hat path.
    assert _detect_drum_root_note("/samples/open_hat_01.wav") == 46


# ── Fix #17: role-aware load_browser_item ──────────────────────────────


def test_load_browser_item_accepts_role_param():
    import inspect
    from mcp_server.tools.browser import load_browser_item
    sig = inspect.signature(load_browser_item)
    assert "role" in sig.parameters
    # Allowed roles are documented
    from mcp_server.tools.browser import _SIMPLER_ROLE_DEFAULTS
    assert {"drum", "melodic", "texture"} <= set(_SIMPLER_ROLE_DEFAULTS)


def test_load_browser_item_rejects_unknown_role():
    from mcp_server.tools.browser import load_browser_item
    from types import SimpleNamespace
    ctx = SimpleNamespace(lifespan_context={"ableton": mock.MagicMock()})
    with pytest.raises(ValueError, match="role must be one of"):
        load_browser_item(ctx, track_index=0, uri="query:foo", role="synth")


def test_role_defaults_reasonable_for_drum_role():
    """Drum role must set Snap=0 (playback fix) and root=C1 (pad convention)."""
    from mcp_server.tools.browser import _SIMPLER_ROLE_DEFAULTS
    drum = dict(_SIMPLER_ROLE_DEFAULTS["drum"])
    assert drum["Snap"] == 0
    assert drum["Sample Pitch Coarse"] == 36
    assert drum["Trigger Mode"] == 0  # Trigger (per BUG-#9 polarity note)


def test_role_defaults_reasonable_for_melodic_role():
    from mcp_server.tools.browser import _SIMPLER_ROLE_DEFAULTS
    melodic = dict(_SIMPLER_ROLE_DEFAULTS["melodic"])
    assert melodic["Trigger Mode"] == 1  # Gate — held
    assert melodic["Sample Pitch Coarse"] == 60  # C3


# ── Fix #19: verify_device_health tool ─────────────────────────────────


def test_verify_device_health_signature():
    import inspect
    from mcp_server.tools.analyzer import verify_device_health
    sig = inspect.signature(verify_device_health)
    assert "track_index" in sig.parameters
    assert "test_midi_note" in sig.parameters
    assert "test_velocity" in sig.parameters
    assert "test_duration_ms" in sig.parameters
    assert "threshold" in sig.parameters


def test_verify_device_health_rejects_invalid_pitch():
    from mcp_server.tools.analyzer import verify_device_health
    from types import SimpleNamespace
    ctx = SimpleNamespace(lifespan_context={"ableton": mock.MagicMock()})
    result = asyncio.run(verify_device_health(
        ctx, track_index=0, test_midi_note=200,
    ))
    assert result["ok"] is False
    assert "0-127" in result["error"]


def test_verify_device_health_rejects_invalid_velocity():
    from mcp_server.tools.analyzer import verify_device_health
    from types import SimpleNamespace
    ctx = SimpleNamespace(lifespan_context={"ableton": mock.MagicMock()})
    result = asyncio.run(verify_device_health(
        ctx, track_index=0, test_velocity=0,
    ))
    assert result["ok"] is False
    assert "1-127" in result["error"]


# ── Phase I: HTTPS bridge ──────────────────────────────────────────────


def test_http_config_defaults_are_safe_guesses():
    from mcp_server.splice_client.http_bridge import SpliceHTTPConfig
    cfg = SpliceHTTPConfig()
    assert cfg.base_url.startswith("https://")
    assert cfg.describe_endpoint.startswith("/")
    assert cfg.variation_endpoint.startswith("/")
    assert cfg.timeout_sec > 0


def test_http_config_is_user_configured_flag():
    from mcp_server.splice_client.http_bridge import SpliceHTTPConfig
    cfg = SpliceHTTPConfig()
    # Sanity: in the default env, at least one of the envvars controls
    # the "configured" flag. When none are set, it's False.
    original = {
        k: os.environ.get(k) for k in (
            "SPLICE_API_BASE_URL",
            "SPLICE_DESCRIBE_ENDPOINT",
            "SPLICE_VARIATION_ENDPOINT",
            "SPLICE_SEARCH_WITH_SOUND_ENDPOINT",
            "SPLICE_ALLOW_UNVERIFIED_ENDPOINTS",
        )
    }
    try:
        for k in list(original):
            os.environ.pop(k, None)
        assert cfg.is_user_configured is False
        os.environ["SPLICE_ALLOW_UNVERIFIED_ENDPOINTS"] = "1"
        assert cfg.is_user_configured is True
    finally:
        for k, v in original.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_describe_sound_refuses_when_unconfigured():
    """Unconfigured endpoints MUST refuse with a structured error."""
    from mcp_server.splice_client.http_bridge import (
        SpliceHTTPBridge, SpliceHTTPError,
    )
    # Ensure no envvar override is active for this test.
    original = {
        k: os.environ.pop(k, None) for k in (
            "SPLICE_API_BASE_URL",
            "SPLICE_DESCRIBE_ENDPOINT",
            "SPLICE_VARIATION_ENDPOINT",
            "SPLICE_SEARCH_WITH_SOUND_ENDPOINT",
            "SPLICE_ALLOW_UNVERIFIED_ENDPOINTS",
        )
    }
    try:
        bridge = SpliceHTTPBridge(grpc_client=None)
        # No grpc_client → NO_AUTH is the immediate blocker
        with pytest.raises(SpliceHTTPError) as exc_info:
            asyncio.run(bridge.describe_sound("dark pad"))
        assert exc_info.value.code in ("ENDPOINT_NOT_CONFIGURED", "NO_AUTH")
    finally:
        for k, v in original.items():
            if v is not None:
                os.environ[k] = v


def test_variation_refuses_when_unconfigured():
    from mcp_server.splice_client.http_bridge import (
        SpliceHTTPBridge, SpliceHTTPError,
    )
    original = {
        k: os.environ.pop(k, None) for k in (
            "SPLICE_API_BASE_URL",
            "SPLICE_DESCRIBE_ENDPOINT",
            "SPLICE_VARIATION_ENDPOINT",
            "SPLICE_SEARCH_WITH_SOUND_ENDPOINT",
            "SPLICE_ALLOW_UNVERIFIED_ENDPOINTS",
        )
    }
    try:
        bridge = SpliceHTTPBridge(grpc_client=None)
        with pytest.raises(SpliceHTTPError) as exc_info:
            asyncio.run(bridge.generate_variation("abc-hash"))
        assert exc_info.value.code in ("ENDPOINT_NOT_CONFIGURED", "NO_AUTH")
    finally:
        for k, v in original.items():
            if v is not None:
                os.environ[k] = v


def test_http_error_to_dict_shape():
    from mcp_server.splice_client.http_bridge import SpliceHTTPError
    err = SpliceHTTPError(code="X", message="Y", endpoint="/e", status_code=403)
    d = err.to_dict()
    assert d == {
        "ok": False, "error": "Y", "code": "X",
        "endpoint": "/e", "status_code": 403,
    }


def test_mcp_describe_sound_tool_registered():
    """The MCP layer exposes the three bridge tools."""
    from mcp_server.sample_engine.tools import (
        splice_describe_sound,
        splice_generate_variation,
        splice_search_with_sound,
    )
    import inspect
    for fn in (splice_describe_sound, splice_generate_variation, splice_search_with_sound):
        assert inspect.iscoroutinefunction(fn), fn.__name__


# ── Remote script set_chain_name handler ───────────────────────────────


def test_set_chain_name_handler_registered():
    """Handler is registered in the remote_script devices module."""
    import importlib.util
    import sys
    import types

    # Fake a minimal _Framework so the module's __init__ imports don't blow up.
    # For this specific test we only load devices.py — its decorator runs via
    # its own `from .router import register` path, so we stub out the router
    # to capture registration.
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    devices_path = os.path.join(repo, "remote_script", "LivePilot", "devices.py")

    # Stub router and utils so their decorators + helpers can be imported.
    captured = {}

    stub_router = types.ModuleType("router_stub")
    def _register(name):
        def _deco(fn):
            captured[name] = fn
            return fn
        return _deco
    stub_router.register = _register

    stub_utils = types.ModuleType("utils_stub")
    stub_utils.get_track = lambda s, i: None
    stub_utils.get_device = lambda t, i: None

    stub_version = types.ModuleType("version_detect_stub")
    stub_version.has_feature = lambda _: True
    stub_version.version_string = lambda: "12.4.0"

    stub_drum = types.ModuleType("drum_helpers_stub")
    stub_drum._next_drum_chain_note = lambda _d: 36

    # Stub `Live` module (devices.py does `import Live` at module scope).
    if "Live" not in sys.modules:
        fake_live = types.ModuleType("Live")
        fake_live.Device = types.SimpleNamespace()
        fake_live.Track = types.SimpleNamespace()
        sys.modules["Live"] = fake_live

    # Ensure the script is loaded with a fresh module namespace.
    parent_pkg = "lp_devices_test"
    if parent_pkg in sys.modules:
        del sys.modules[parent_pkg]

    pkg = types.ModuleType(parent_pkg)
    pkg.__path__ = [os.path.join(repo, "remote_script", "LivePilot")]
    pkg.__package__ = parent_pkg
    sys.modules[parent_pkg] = pkg
    sys.modules[f"{parent_pkg}.router"] = stub_router
    sys.modules[f"{parent_pkg}.utils"] = stub_utils
    sys.modules[f"{parent_pkg}.version_detect"] = stub_version
    sys.modules[f"{parent_pkg}._drum_helpers"] = stub_drum

    spec = importlib.util.spec_from_file_location(
        f"{parent_pkg}.devices", devices_path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        # Clean up so other tests aren't affected.
        for key in list(sys.modules):
            if key.startswith(parent_pkg):
                sys.modules.pop(key, None)

    assert "set_chain_name" in captured
    # Handler rejects empty name
    with pytest.raises(ValueError, match="cannot be empty"):
        captured["set_chain_name"](None, {"track_index": 0, "device_index": 0, "chain_index": 0, "name": ""})


# ── fire_test_note / cleanup_test_note handlers registered ────────────


def test_fire_test_note_handler_registered():
    """The remote-script clips module registers fire_test_note + cleanup_test_note."""
    import importlib.util
    import sys
    import types

    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    clips_path = os.path.join(repo, "remote_script", "LivePilot", "clips.py")

    captured = {}
    stub_router = types.ModuleType("router_stub")
    def _register(name):
        def _deco(fn):
            captured[name] = fn
            return fn
        return _deco
    stub_router.register = _register

    stub_utils = types.ModuleType("utils_stub")
    stub_utils.get_clip = lambda s, t, c: None
    stub_utils.get_clip_slot = lambda s, t, c: None

    parent_pkg = "lp_clips_test"
    if parent_pkg in sys.modules:
        del sys.modules[parent_pkg]

    pkg = types.ModuleType(parent_pkg)
    pkg.__path__ = [os.path.join(repo, "remote_script", "LivePilot")]
    pkg.__package__ = parent_pkg
    sys.modules[parent_pkg] = pkg
    sys.modules[f"{parent_pkg}.router"] = stub_router
    sys.modules[f"{parent_pkg}.utils"] = stub_utils

    spec = importlib.util.spec_from_file_location(
        f"{parent_pkg}.clips", clips_path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        for key in list(sys.modules):
            if key.startswith(parent_pkg):
                sys.modules.pop(key, None)

    assert "fire_test_note" in captured
    assert "cleanup_test_note" in captured
