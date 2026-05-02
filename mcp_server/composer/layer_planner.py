"""Backward-compat shim — layer_planner has moved to full/layer_planner.py.

Existing code that imports from ``mcp_server.composer.layer_planner`` continues
to work unchanged. New code should import from
``mcp_server.composer.full.layer_planner`` directly.
"""
from .full.layer_planner import (  # noqa: F401
    LayerSpec,
    plan_layers,
    plan_sections,
    _ROLE_TEMPLATES,
    _GENRE_ROLE_PRIORITY,
    _DEFAULT_ROLE_PRIORITY,
    # v1.24: _DEFAULT_SECTION_TEMPLATE removed per vocabulary-not-form principle (Task 12).
    _build_search_query,
    _ROLE_INSTRUMENT,
    _NON_TONAL_ROLES,
    _build_splice_filters,
    _select_roles,
    _compute_pan,
)
