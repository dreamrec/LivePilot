"""Tests for Wonder Mode sample intelligence integration (Phase 3)."""
import pytest
from mcp_server.wonder_mode.engine import build_variant, _compile_variant_plan


def test_sample_variant_with_resolved_path_is_executable():
    """When sample_file_path is in kernel, compiled plan should have real paths."""
    move_dict = {
        "move_id": "sample_texture_layer",
        "family": "sample",
        "intent": "Add textural sample layer",
        "targets": {"texture": 0.5},
        "protect": {},
        "risk_level": "low",
    }
    kernel = {
        "session_info": {"tempo": 120, "tracks": []},
        "mode": "improve",
        "sample_file_path": "/path/to/texture.wav",
    }
    variant = build_variant(
        label="Texture Layer",
        move_dict=move_dict,
        kernel=kernel,
    )
    plan = variant["compiled_plan"]
    assert plan is not None
    # Check that load_sample_to_simpler has the real path, not placeholder
    load_steps = [s for s in plan["steps"] if s["tool"] == "load_sample_to_simpler"]
    if load_steps:
        assert load_steps[0]["params"]["file_path"] == "/path/to/texture.wav"


def test_sample_variant_without_path_has_placeholder():
    """Without sample_file_path in kernel, compiled plan should have placeholder."""
    move_dict = {
        "move_id": "sample_texture_layer",
        "family": "sample",
        "intent": "Add textural sample layer",
        "targets": {"texture": 0.5},
        "protect": {},
        "risk_level": "low",
    }
    kernel = {
        "session_info": {"tempo": 120, "tracks": []},
        "mode": "improve",
        # No sample_file_path
    }
    variant = build_variant(
        label="Texture Layer",
        move_dict=move_dict,
        kernel=kernel,
    )
    plan = variant["compiled_plan"]
    assert plan is not None
    load_steps = [s for s in plan["steps"] if s["tool"] == "load_sample_to_simpler"]
    if load_steps:
        # Should have placeholder
        assert "{sample_file_path}" in str(load_steps[0]["params"]["file_path"])


def test_compile_variant_plan_returns_none_without_kernel():
    """No kernel → no plan."""
    result = _compile_variant_plan({"move_id": "sample_chop_rhythm"}, None)
    assert result is None


def test_compile_variant_plan_returns_none_for_unknown_move():
    """Unknown move → no plan."""
    kernel = {"session_info": {"tempo": 120, "tracks": []}}
    result = _compile_variant_plan({"move_id": "nonexistent_xyz"}, kernel)
    assert result is None
