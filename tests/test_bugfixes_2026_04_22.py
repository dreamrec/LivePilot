"""Tests for bug fixes shipped per docs/2026-04-22-bugs-discovered.md.

Each test references the numbered bug it locks down. These are
contract-level tests that don't need a live Ableton session — they
exercise the MCP layer's parameter normalization and fallback logic.
"""

from __future__ import annotations

import importlib.util
import os

import pytest

from mcp_server.tools.devices import _normalize_batch_entry


def _load_scale_helpers():
    """Import _scale_helpers.py by file path, bypassing the package __init__.

    `remote_script/LivePilot/__init__.py` imports `_Framework.ControlSurface`
    which only exists inside Ableton. To test pure helpers outside Ableton,
    we load the helper file directly via its absolute path.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    path = os.path.join(
        repo, "remote_script", "LivePilot", "_scale_helpers.py",
    )
    spec = importlib.util.spec_from_file_location("_scale_helpers_std", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Expose friendly aliases matching the test-side names
    module.coerce_root_note = module._coerce_root_note
    module.resolve_scale_names = module._resolve_scale_names
    module.builtin_fallback = module._BUILTIN_SCALES_FALLBACK
    return module


# ── BUG-#3: batch_set_parameters accepts index/name aliases ────────────


def test_bug3_batch_accepts_short_index():
    """`index` key (from get_device_parameters) feeds straight back in."""
    entry = _normalize_batch_entry({"index": 5, "value": 0.7})
    assert entry == {"name_or_index": 5, "value": 0.7}


def test_bug3_batch_accepts_short_name():
    """`name` key (from get_device_parameters) feeds straight back in."""
    entry = _normalize_batch_entry({"name": "Dry/Wet", "value": 0.5})
    assert entry == {"name_or_index": "Dry/Wet", "value": 0.5}


def test_bug3_batch_still_accepts_legacy_name_or_index():
    """Legacy shape still works."""
    entry = _normalize_batch_entry({"name_or_index": "Filter Freq", "value": 1000})
    assert entry == {"name_or_index": "Filter Freq", "value": 1000}


def test_bug3_batch_still_accepts_aligned_parameter_index():
    """Aligned shape (matches set_device_parameter) still works."""
    entry = _normalize_batch_entry({"parameter_index": 0, "value": 1.0})
    assert entry == {"name_or_index": 0, "value": 1.0}


def test_bug3_batch_still_accepts_aligned_parameter_name():
    entry = _normalize_batch_entry({"parameter_name": "Gain", "value": -6})
    assert entry == {"name_or_index": "Gain", "value": -6}


def test_bug3_batch_rejects_multiple_keys():
    """Ambiguous entry with both `index` and `name` is rejected."""
    with pytest.raises(ValueError, match="not multiple"):
        _normalize_batch_entry({"index": 1, "name": "X", "value": 0.5})


def test_bug3_batch_rejects_no_key():
    with pytest.raises(ValueError, match="exactly one"):
        _normalize_batch_entry({"value": 0.5})


def test_bug3_batch_rejects_missing_value():
    with pytest.raises(ValueError, match="must include 'value'"):
        _normalize_batch_entry({"index": 1})


# ── BUG-#2: set_song_scale root_note coercion ──────────────────────────


def test_bug2_root_note_coercion_integer_in_range():
    _coerce_root_note = _load_scale_helpers().coerce_root_note
    assert _coerce_root_note(0) == 0
    assert _coerce_root_note(6) == 6
    assert _coerce_root_note(11) == 11


def test_bug2_root_note_coercion_integer_string():
    _coerce_root_note = _load_scale_helpers().coerce_root_note
    assert _coerce_root_note("0") == 0
    assert _coerce_root_note("6") == 6


def test_bug2_root_note_coercion_note_names():
    _coerce_root_note = _load_scale_helpers().coerce_root_note
    cases = {
        "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
        "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
        "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
    }
    for name, expected in cases.items():
        assert _coerce_root_note(name) == expected, name


def test_bug2_root_note_coercion_lowercase_first_char_is_uppercased():
    _coerce_root_note = _load_scale_helpers().coerce_root_note
    assert _coerce_root_note("f#") == 6


def test_bug2_root_note_coercion_rejects_unknown():
    _coerce_root_note = _load_scale_helpers().coerce_root_note
    with pytest.raises(ValueError):
        _coerce_root_note("Z#")


def test_bug2_root_note_coercion_rejects_out_of_range_int():
    _coerce_root_note = _load_scale_helpers().coerce_root_note
    with pytest.raises(ValueError):
        _coerce_root_note(12)
    with pytest.raises(ValueError):
        _coerce_root_note(-1)


def test_bug2_root_note_coercion_rejects_wrong_type():
    _coerce_root_note = _load_scale_helpers().coerce_root_note
    with pytest.raises(ValueError):
        _coerce_root_note(1.5)
    with pytest.raises(ValueError):
        _coerce_root_note(None)


def test_bug2_resolve_scale_names_fallback_when_attr_missing():
    """When Song lacks `scale_names` (Live 12.4.0), fallback list is used."""
    helpers = _load_scale_helpers()
    class _FakeSong12_4:
        """Mimics Live 12.4.0 Song — no scale_names attribute."""
        pass

    names = helpers.resolve_scale_names(_FakeSong12_4())
    assert names == helpers.builtin_fallback
    assert "Major" in names
    assert "Minor" in names


def test_bug2_resolve_scale_names_uses_direct_attr_when_available():
    helpers = _load_scale_helpers()
    class _FakeSong12_3:
        scale_names = ("Major", "Minor", "Custom Scale")

    names = helpers.resolve_scale_names(_FakeSong12_3())
    assert names == ["Major", "Minor", "Custom Scale"]


def test_bug2_resolve_scale_names_tries_alternate_attr():
    helpers = _load_scale_helpers()
    class _FakeSongAlt:
        available_scale_names = ("Mode-A", "Mode-B")

    names = helpers.resolve_scale_names(_FakeSongAlt())
    assert names == ["Mode-A", "Mode-B"]


# ── BUG-#4: search param aliases (verified at signature level) ─────────


def test_bug4_search_samples_accepts_q_alias_signature():
    """The `q` alias is in the tool signature so callers can use it."""
    import inspect
    from mcp_server.sample_engine.tools import search_samples
    sig = inspect.signature(search_samples)
    assert "q" in sig.parameters
    assert "query" in sig.parameters


def test_bug4_search_browser_accepts_query_alias_signature():
    import inspect
    from mcp_server.tools.browser import search_browser
    sig = inspect.signature(search_browser)
    assert "query" in sig.parameters
    assert "name_filter" in sig.parameters


# ── BUG-#5: get_browser_items pagination params ────────────────────────


def test_bug5_get_browser_items_exposes_pagination_signature():
    import inspect
    from mcp_server.tools.browser import get_browser_items
    sig = inspect.signature(get_browser_items)
    assert "limit" in sig.parameters
    assert "offset" in sig.parameters
    assert "filter_pattern" in sig.parameters


# ── BUG-#6: get_master_spectrum windowing ──────────────────────────────


def test_bug6_master_spectrum_exposes_window_ms():
    import inspect
    from mcp_server.tools.analyzer import get_master_spectrum
    sig = inspect.signature(get_master_spectrum)
    assert "window_ms" in sig.parameters
    assert "samples" in sig.parameters


# ── BUG-#7: get_track_meters multi-sample ──────────────────────────────


def test_bug7_track_meters_exposes_samples_param():
    import inspect
    from mcp_server.tools.mixing import get_track_meters
    sig = inspect.signature(get_track_meters)
    assert "samples" in sig.parameters
    assert "sample_interval_ms" in sig.parameters


# ── BUG-#1: add_drum_rack_pad tool exists ──────────────────────────────


def test_bug1_add_drum_rack_pad_tool_exists():
    from mcp_server.tools.analyzer import add_drum_rack_pad
    assert callable(add_drum_rack_pad)


def test_bug1_replace_simpler_sample_accepts_chain_index():
    import inspect
    from mcp_server.tools.analyzer import replace_simpler_sample
    sig = inspect.signature(replace_simpler_sample)
    assert "chain_index" in sig.parameters
    assert "nested_device_index" in sig.parameters


# ── BUG-#8: analyze_loudness_live tool exists ──────────────────────────


def test_bug8_analyze_loudness_live_tool_exists():
    from mcp_server.tools.analyzer import analyze_loudness_live
    import inspect
    sig = inspect.signature(analyze_loudness_live)
    assert "window_sec" in sig.parameters
    assert "sample_interval_ms" in sig.parameters
