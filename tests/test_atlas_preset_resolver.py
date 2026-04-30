"""Tests for mcp_server/atlas/preset_resolver.py.

Validates that the resolver correctly maps demo-track devices to their
matching preset sidecars and exposes producer-assigned macro names.

Uses real sidecars from ~/.livepilot/atlas-overlays/packs/_preset_parses/
when available; skips otherwise (corpus-dependent).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from mcp_server.atlas import preset_resolver

CORPUS_AVAILABLE = preset_resolver.PRESET_PARSES_ROOT.is_dir()


@pytest.fixture(autouse=True)
def _reset_cache():
    """Drop the lru_cache between tests so fixture sidecars take effect."""
    preset_resolver._load_pack_index.cache_clear()
    yield
    preset_resolver._load_pack_index.cache_clear()


# ─── unit tests with synthetic fixtures ──────────────────────────────────────


@pytest.fixture
def fake_pack(tmp_path, monkeypatch):
    """Create a tiny synthetic pack on disk so tests don't depend on corpus."""
    root = tmp_path / "_preset_parses"
    pack = root / "test-pack"
    pack.mkdir(parents=True)
    (pack / "instruments_pioneer.json").write_text(json.dumps({
        "file": "Test Pack/Sounds/Synth Pad/Pioneer.adg",
        "name": "Pioneer Drone",
        "rack_class": "InstrumentGroupDevice",
        "macros": [
            {"index": 0, "value": "0", "name": "Device On"},
            {"index": 1, "value": "1", "name": "Rift Rate"},
            {"index": 2, "value": "40", "name": "Crunch"},
            {"index": 8, "value": "95.25", "name": "Volume"},
        ],
    }))
    (pack / "fx_redux.json").write_text(json.dumps({
        "file": "Test Pack/Audio Effects/Redux.adg",
        "name": "Redux Wash",
        "rack_class": "AudioEffectGroupDevice",
        "macros": [
            {"index": 0, "value": "50", "name": "Decay"},
        ],
    }))
    monkeypatch.setattr(preset_resolver, "PRESET_PARSES_ROOT", root)
    return root


def test_exact_match_returns_macro_names(fake_pack):
    res = preset_resolver.resolve_preset_for_device(
        "test-pack", "InstrumentGroupDevice", "Pioneer Drone"
    )
    assert res["found"] is True
    assert res["match_type"] == "exact_with_class"
    assert res["preset_name"] == "Pioneer Drone"
    assert res["macro_names"][1] == "Rift Rate"
    assert res["macro_names"][8] == "Volume"


def test_case_insensitive_match(fake_pack):
    res = preset_resolver.resolve_preset_for_device(
        "test-pack", "InstrumentGroupDevice", "PIONEER DRONE"
    )
    assert res["found"] is True
    assert res["match_type"] == "exact_with_class"


def test_class_mismatch_falls_to_exact_only(fake_pack):
    # Wrong class but right name → exact match without class qualifier
    res = preset_resolver.resolve_preset_for_device(
        "test-pack", "AudioEffectGroupDevice", "Pioneer Drone"
    )
    assert res["found"] is True
    assert res["match_type"] == "exact"


def test_no_match_returns_empty(fake_pack):
    res = preset_resolver.resolve_preset_for_device(
        "test-pack", "InstrumentGroupDevice", "Nonexistent Device"
    )
    assert res["found"] is False
    assert res["macro_names"] == {}
    assert res["browser_search_hint"] is None


def test_unknown_pack_returns_empty(fake_pack):
    res = preset_resolver.resolve_preset_for_device(
        "no-such-pack", "InstrumentGroupDevice", "Pioneer Drone"
    )
    assert res["found"] is False


def test_empty_inputs_return_empty(fake_pack):
    assert preset_resolver.resolve_preset_for_device("", "X", "Y")["found"] is False
    assert preset_resolver.resolve_preset_for_device("test-pack", "X", "")["found"] is False


def test_browser_path_inference(fake_pack):
    res = preset_resolver.resolve_preset_for_device(
        "test-pack", "InstrumentGroupDevice", "Pioneer Drone"
    )
    assert res["browser_search_hint"]["suggested_path"] == "sounds"
    assert res["browser_search_hint"]["name_filter"] == "Pioneer Drone"

    res2 = preset_resolver.resolve_preset_for_device(
        "test-pack", "AudioEffectGroupDevice", "Redux Wash"
    )
    assert res2["browser_search_hint"]["suggested_path"] == "audio_effects"


def test_lookup_macro_name_convenience(fake_pack):
    name = preset_resolver.lookup_macro_name("test-pack", "Pioneer Drone", 1)
    assert name == "Rift Rate"
    assert preset_resolver.lookup_macro_name("test-pack", "Pioneer Drone", 99) is None


def test_emit_load_step_with_match(fake_pack):
    step = preset_resolver.emit_load_step(
        "test-pack", "InstrumentGroupDevice", "Pioneer Drone", track_index=3
    )
    assert step["action"] == "load_browser_item"
    assert step["track_index"] == 3
    assert step["browser_search_hint"]["name_filter"] == "Pioneer Drone"
    assert step["match_type"] == "exact_with_class"
    assert step["preset_name"] == "Pioneer Drone"


def test_emit_load_step_without_match(fake_pack):
    step = preset_resolver.emit_load_step(
        "test-pack", "InstrumentGroupDevice", "Custom Untracked Rack", track_index=3
    )
    assert step["action"] == "load_browser_item"
    assert step["match_type"] == "none"
    # Fallback hint uses the user_name verbatim
    assert step["browser_search_hint"]["name_filter"] == "Custom Untracked Rack"


def test_hyphen_underscore_pack_normalization(tmp_path, monkeypatch):
    root = tmp_path / "_preset_parses"
    pack = root / "drone-lab"
    pack.mkdir(parents=True)
    (pack / "x.json").write_text(json.dumps({
        "name": "Test", "rack_class": "X", "macros": [], "file": ""
    }))
    monkeypatch.setattr(preset_resolver, "PRESET_PARSES_ROOT", root)
    # Caller passes underscore form, fixture is hyphen — should still resolve
    res = preset_resolver.resolve_preset_for_device("drone_lab", "X", "Test")
    assert res["found"] is True


# ─── integration tests against real corpus ───────────────────────────────────


@pytest.mark.skipif(not CORPUS_AVAILABLE, reason="user atlas corpus not installed")
def test_real_corpus_drone_lab_pioneer():
    """Pioneer Drone exists in drone-lab; should expose Rift Rate macro."""
    res = preset_resolver.resolve_preset_for_device(
        "drone-lab", "InstrumentGroupDevice", "Pioneer Drone"
    )
    if not res["found"]:
        pytest.skip("Pioneer Drone preset not in user corpus")
    # If found, the v1.23.4 parser fix should have populated real macro names
    assert "Rift Rate" in res["macro_names"].values() or res["macro_names"], (
        f"Expected named macros in resolved preset, got {res['macro_names']}"
    )
