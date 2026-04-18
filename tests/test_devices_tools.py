"""Tests for mcp_server/tools/devices.py schema normalization.

Guards BUG-F4 from the 2026-04-18 session: batch_set_parameters used
`name_or_index` while set_device_parameter used `parameter_name` +
`parameter_index`. Callers hit schema errors switching tools.
"""
from __future__ import annotations

import pytest

from mcp_server.tools.devices import _normalize_batch_entry


# ---------------------------------------------------------------------------
# BUG-F4: batch_set_parameters now accepts EITHER the legacy
# `name_or_index` shape OR the aligned `parameter_index` / `parameter_name`
# shape used by set_device_parameter.
# ---------------------------------------------------------------------------


def test_normalize_batch_entry_accepts_legacy_name_or_index_int():
    """Legacy integer shape: {'name_or_index': 5, 'value': 0.5}."""
    entry = {"name_or_index": 5, "value": 0.5}
    result = _normalize_batch_entry(entry)
    assert result == {"name_or_index": 5, "value": 0.5}


def test_normalize_batch_entry_accepts_legacy_name_or_index_string():
    """Legacy string shape: {'name_or_index': 'Dry/Wet', 'value': 0.5}."""
    entry = {"name_or_index": "Dry/Wet", "value": 0.5}
    result = _normalize_batch_entry(entry)
    assert result == {"name_or_index": "Dry/Wet", "value": 0.5}


def test_normalize_batch_entry_accepts_parameter_index():
    """New aligned shape: parameter_index → name_or_index for bridge."""
    entry = {"parameter_index": 5, "value": 0.5}
    result = _normalize_batch_entry(entry)
    assert result == {"name_or_index": 5, "value": 0.5}


def test_normalize_batch_entry_accepts_parameter_name():
    """New aligned shape: parameter_name → name_or_index for bridge."""
    entry = {"parameter_name": "Dry/Wet", "value": 0.5}
    result = _normalize_batch_entry(entry)
    assert result == {"name_or_index": "Dry/Wet", "value": 0.5}


def test_normalize_batch_entry_rejects_missing_value():
    with pytest.raises(ValueError, match="value"):
        _normalize_batch_entry({"parameter_index": 5})


def test_normalize_batch_entry_rejects_missing_parameter_key():
    with pytest.raises(ValueError) as exc:
        _normalize_batch_entry({"value": 0.5})
    assert "parameter_name" in str(exc.value)
    assert "parameter_index" in str(exc.value)
    assert "name_or_index" in str(exc.value)


def test_normalize_batch_entry_rejects_mixed_parameter_keys():
    """Sending both parameter_name AND parameter_index is ambiguous."""
    entry = {"parameter_name": "X", "parameter_index": 5, "value": 0.5}
    with pytest.raises(ValueError, match="not multiple|exactly one"):
        _normalize_batch_entry(entry)


def test_normalize_batch_entry_rejects_mixed_legacy_and_new():
    """Can't mix legacy name_or_index with new parameter_index."""
    entry = {"name_or_index": 5, "parameter_index": 5, "value": 0.5}
    with pytest.raises(ValueError, match="not multiple|exactly one"):
        _normalize_batch_entry(entry)


def test_normalize_batch_entry_preserves_value_type():
    """Numeric values stay numeric; strings (enums) stay strings."""
    assert _normalize_batch_entry({"parameter_index": 1, "value": 0})["value"] == 0
    assert _normalize_batch_entry({"parameter_index": 1, "value": 1.5})["value"] == 1.5
    assert _normalize_batch_entry({"parameter_index": 1, "value": "On"})["value"] == "On"


# ---------------------------------------------------------------------------
# BUG-audit-H3: negative parameter_index must be rejected at the MCP layer
# (matches set_device_parameter's validation at devices.py:278), not leak
# through to the Remote Script as an unstructured IndexError.
# ---------------------------------------------------------------------------


def test_normalize_batch_entry_rejects_negative_parameter_index():
    """parameter_index < 0 is invalid — must raise structured error."""
    with pytest.raises(ValueError, match="parameter_index"):
        _normalize_batch_entry({"parameter_index": -1, "value": 0.5})


def test_normalize_batch_entry_accepts_zero_parameter_index():
    """parameter_index = 0 is valid (Device On is usually index 0)."""
    result = _normalize_batch_entry({"parameter_index": 0, "value": 1})
    assert result == {"name_or_index": 0, "value": 1}


def test_normalize_batch_entry_rejects_negative_legacy_name_or_index():
    """Legacy name_or_index with negative int should also be rejected."""
    with pytest.raises(ValueError, match="parameter_index|name_or_index"):
        _normalize_batch_entry({"name_or_index": -5, "value": 0.5})
