"""Tests for SemanticMove registry and compilation."""

from mcp_server.semantic_moves.models import SemanticMove
from mcp_server.semantic_moves.registry import get_move, list_moves, count
from mcp_server.semantic_moves.mix_moves import TIGHTEN_LOW_END


def test_semantic_move_has_required_fields():
    move = TIGHTEN_LOW_END
    assert move.move_id == "tighten_low_end"
    assert move.family == "mix"
    assert move.intent == "tighten_low_end" or "tighten" in move.intent.lower()
    assert len(move.compile_plan) > 0
    assert move.risk_level in ("low", "medium", "high")


def test_compile_plan_has_tool_and_description():
    move = TIGHTEN_LOW_END
    for step in move.compile_plan:
        assert "tool" in step, f"Step missing 'tool': {step}"
        assert "description" in step, f"Step missing 'description': {step}"


def test_verification_plan_has_tool_and_check():
    move = TIGHTEN_LOW_END
    for step in move.verification_plan:
        assert "tool" in step, f"Step missing 'tool': {step}"
        assert "check" in step, f"Step missing 'check': {step}"


def test_registry_lists_moves():
    moves = list_moves()
    assert len(moves) >= 5
    assert any(m["move_id"] == "tighten_low_end" for m in moves)


def test_registry_count():
    assert count() >= 8  # Our initial batch


def test_registry_get_by_id():
    move = get_move("tighten_low_end")
    assert move is not None
    assert move.family == "mix"


def test_registry_get_unknown_returns_none():
    assert get_move("nonexistent_move") is None


def test_registry_filter_by_domain():
    mix_moves = list_moves(domain="mix")
    assert all(m["family"] == "mix" for m in mix_moves)
    assert len(mix_moves) >= 5

    arr_moves = list_moves(domain="arrangement")
    assert all(m["family"] == "arrangement" for m in arr_moves)
    assert len(arr_moves) >= 2


def test_to_dict_compact():
    move = TIGHTEN_LOW_END
    d = move.to_dict()
    assert "move_id" in d
    assert "compile_plan" not in d  # Compact doesn't include plans
    assert "compile_plan_steps" in d  # Just the count


def test_to_full_dict_includes_plans():
    move = TIGHTEN_LOW_END
    d = move.to_full_dict()
    assert "compile_plan" in d
    assert "verification_plan" in d
    assert isinstance(d["compile_plan"], list)


def test_all_registered_moves_have_valid_structure():
    """Every move in the registry must have required fields."""
    for move_dict in list_moves():
        move = get_move(move_dict["move_id"])
        assert move is not None
        assert move.move_id
        assert move.family
        assert move.intent
        assert move.risk_level in ("low", "medium", "high")
        assert len(move.compile_plan) > 0, f"{move.move_id} has empty compile_plan"
