"""Tests for single-source orchestration path (Phase 1).

Verifies that Wonder and Preview use compiler.compile() for executable plans,
not stale SemanticMove.plan_template metadata.
"""
import pytest
from mcp_server.semantic_moves.models import SemanticMove


def test_semantic_move_has_plan_template_not_compile_plan():
    """SemanticMove uses plan_template, not compile_plan."""
    move = SemanticMove(
        move_id="test_move",
        family="test",
        intent="test intent",
        targets=["energy"],
        plan_template=[{"tool": "set_tempo", "params": {"tempo": 120}}],
    )
    assert hasattr(move, "plan_template")
    assert not hasattr(move, "compile_plan")
    # to_dict() is compact — no plan, just step count
    d = move.to_dict()
    assert "plan_template_steps" in d
    assert "compile_plan" not in d
    assert "compile_plan_steps" not in d


def test_semantic_move_full_dict_includes_plan_template():
    """to_full_dict() should include plan_template."""
    move = SemanticMove(
        move_id="test_move",
        family="test",
        intent="test",
        targets=["energy"],
        plan_template=[{"tool": "set_tempo", "params": {"tempo": 120}, "description": "test"}],
    )
    d = move.to_full_dict()
    assert "plan_template" in d
    assert isinstance(d["plan_template"], list)
    assert len(d["plan_template"]) == 1


def test_semantic_move_compact_dict_has_step_count():
    """to_dict() should have plan_template_steps count, not full plan."""
    move = SemanticMove(
        move_id="test_move",
        family="test",
        intent="test",
        targets=["energy"],
        plan_template=[{"tool": "a"}, {"tool": "b"}],
    )
    d = move.to_dict()
    assert "plan_template_steps" in d
    assert d["plan_template_steps"] == 2
    assert "plan_template" not in d


# ── Phase 1 Task 1.2: Wonder uses compiler ─────────────────────────────


def test_wonder_variant_with_kernel_compiles_plan():
    """When kernel is provided, build_variant should compile via the semantic compiler."""
    from mcp_server.wonder_mode.engine import build_variant
    from mcp_server.semantic_moves.compiler import _COMPILERS
    from mcp_server.semantic_moves import registry

    # Find a move that has a registered compiler
    all_moves = registry.list_moves()
    compilable = [m for m in all_moves if m.get("move_id") in _COMPILERS]
    if not compilable:
        pytest.skip("No moves with registered compilers found")

    move_dict = compilable[0]
    kernel = {"session_info": {"tempo": 120, "tracks": []}, "mode": "improve"}

    variant = build_variant(
        label="Test Variant",
        move_dict=move_dict,
        kernel=kernel,
    )

    plan = variant["compiled_plan"]
    # Must be a dict with "steps" key (CompiledPlan.to_dict() shape)
    assert isinstance(plan, dict), f"Expected dict from compiler, got {type(plan)}"
    assert "steps" in plan, f"Missing 'steps' in compiled plan: {list(plan.keys())}"
    assert "summary" in plan
    assert "risk_level" in plan
    assert isinstance(plan["steps"], list)
    assert variant["analytical_only"] is False


def test_wonder_variant_without_kernel_is_analytical():
    """Without a kernel, the variant should be analytical_only."""
    from mcp_server.wonder_mode.engine import build_variant

    move_dict = {
        "move_id": "make_punchier",
        "family": "mix",
        "intent": "Add punch",
        "targets": {"energy": 0.3},
        "protect": {},
        "risk_level": "low",
    }

    variant = build_variant(
        label="Test",
        move_dict=move_dict,
        # No kernel
    )

    assert variant["compiled_plan"] is None
    assert variant["analytical_only"] is True


def test_wonder_variant_uncompilable_move_is_analytical():
    """A move without a registered compiler should be analytical_only even with kernel."""
    from mcp_server.wonder_mode.engine import build_variant

    move_dict = {
        "move_id": "nonexistent_move_xyz",
        "family": "test",
        "intent": "test",
        "targets": {},
        "protect": {},
        "risk_level": "low",
    }
    kernel = {"session_info": {"tempo": 120, "tracks": []}, "mode": "improve"}

    variant = build_variant(
        label="Test",
        move_dict=move_dict,
        kernel=kernel,
    )

    assert variant["compiled_plan"] is None
    assert variant["analytical_only"] is True
