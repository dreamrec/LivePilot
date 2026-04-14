"""Shared accessors for reading from a taste-graph dict.

Three shapes exist in the wild:
  canonical:   {"dimension_weights": {"dim": 0.3, ...}, ...}   TasteGraph.to_dict()
  legacy flat: {"dim": 0.3, ...}                               arbitrary caller dicts
  legacy obj:  {"dim": {"value": 0.3, ...}}                    TasteDimension.to_dict()

Every consumer that wants to read a dimension preference MUST route through
get_dimension_pref so new callers standardize on the canonical path and
pre-existing dicts keep working until fully migrated.

Do not add new shapes. If you find yourself writing a fourth shape, fix the
producer instead.
"""

from __future__ import annotations


def get_dimension_pref(
    taste_graph: object,
    dimension: str,
    default: float = 0.5,
) -> float:
    """Read a dimension preference from a taste graph dict, regardless of shape.

    Returns default for non-dict input, missing dimensions, or non-numeric values.
    """
    if not isinstance(taste_graph, dict):
        return default

    # Canonical shape wins
    dw = taste_graph.get("dimension_weights")
    if isinstance(dw, dict) and dimension in dw:
        val = dw[dimension]
        if isinstance(val, (int, float)):
            return float(val)

    # Legacy flat shapes
    val = taste_graph.get(dimension)
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict):
        v = val.get("value")
        if isinstance(v, (int, float)):
            return float(v)

    return default
