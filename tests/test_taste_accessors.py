"""Tests for the taste-graph dimension accessor helper.

Three shapes exist in the codebase:
  canonical:   {"dimension_weights": {"dim": 0.3, ...}, ...}   — TasteGraph.to_dict()
  legacy flat: {"dim": 0.3, ...}                               — arbitrary caller dicts
  legacy obj:  {"dim": {"value": 0.3, ...}}                    — TasteDimension.to_dict()

Consumers should route through get_dimension_pref so all shapes work.
"""

from mcp_server.memory.taste_accessors import get_dimension_pref


def test_canonical_shape_dimension_weights():
    g = {"dimension_weights": {"transition_boldness": 0.8}}
    assert get_dimension_pref(g, "transition_boldness", default=0.5) == 0.8


def test_canonical_shape_missing_dim_returns_default():
    g = {"dimension_weights": {"other": 0.8}}
    assert get_dimension_pref(g, "transition_boldness", default=0.42) == 0.42


def test_fallback_flat_float_shape():
    g = {"transition_boldness": 0.7}
    assert get_dimension_pref(g, "transition_boldness", default=0.5) == 0.7


def test_fallback_flat_dict_shape():
    g = {"transition_boldness": {"value": 0.6, "evidence_count": 3}}
    assert get_dimension_pref(g, "transition_boldness", default=0.5) == 0.6


def test_missing_returns_default():
    assert get_dimension_pref({}, "unknown", default=0.42) == 0.42


def test_empty_dimension_weights_returns_default():
    g = {"dimension_weights": {}}
    assert get_dimension_pref(g, "transition_boldness", default=0.5) == 0.5


def test_non_dict_input_returns_default():
    assert get_dimension_pref(None, "x", default=0.3) == 0.3
    assert get_dimension_pref("not a dict", "x", default=0.3) == 0.3


def test_canonical_takes_precedence_over_flat():
    """If both shapes coexist, canonical wins."""
    g = {
        "dimension_weights": {"transition_boldness": 0.9},
        "transition_boldness": 0.1,
    }
    assert get_dimension_pref(g, "transition_boldness", default=0.5) == 0.9


def test_int_values_coerced_to_float():
    g = {"dimension_weights": {"transition_boldness": 1}}
    result = get_dimension_pref(g, "transition_boldness", default=0.5)
    assert isinstance(result, float)
    assert result == 1.0
