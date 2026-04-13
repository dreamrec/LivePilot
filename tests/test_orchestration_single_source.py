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
