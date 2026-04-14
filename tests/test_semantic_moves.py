"""Tests for SemanticMove registry and compilation."""

from mcp_server.semantic_moves.models import SemanticMove
from mcp_server.semantic_moves.registry import get_move, list_moves, count
from mcp_server.semantic_moves.mix_moves import TIGHTEN_LOW_END


def test_semantic_move_has_required_fields():
    move = TIGHTEN_LOW_END
    assert move.move_id == "tighten_low_end"
    assert move.family == "mix"
    assert move.intent == "tighten_low_end" or "tighten" in move.intent.lower()
    assert len(move.plan_template) > 0
    assert move.risk_level in ("low", "medium", "high")


def test_plan_template_has_tool_and_description():
    move = TIGHTEN_LOW_END
    for step in move.plan_template:
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
    assert "plan_template" not in d  # Compact doesn't include plans
    assert "plan_template_steps" in d  # Just the count


def test_to_full_dict_includes_plans():
    move = TIGHTEN_LOW_END
    d = move.to_full_dict()
    assert "plan_template" in d
    assert "verification_plan" in d
    assert isinstance(d["plan_template"], list)


def test_all_registered_moves_have_valid_structure():
    """Every move in the registry must have required fields."""
    for move_dict in list_moves():
        move = get_move(move_dict["move_id"])
        assert move is not None
        assert move.move_id
        assert move.family
        assert move.intent
        assert move.risk_level in ("low", "medium", "high")
        assert len(move.plan_template) > 0, f"{move.move_id} has empty plan_template"


# ── preview_semantic_move compiled_plan (Phase 6) ────────────────────────

def test_preview_semantic_move_returns_compiled_plan_additive_field():
    """preview_semantic_move must include compiled_plan alongside plan_template.

    Previously it just returned move.to_full_dict() — static metadata only.
    Callers had no executable representation to render or inspect.
    """
    from types import SimpleNamespace
    from mcp_server.semantic_moves.tools import preview_semantic_move

    class _Ableton:
        def send_command(self, cmd, params=None):
            return {
                "tempo": 120, "track_count": 3,
                "tracks": [{"index": 0, "name": "Drums"}],
                "scenes": [],
            }

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton()})
    result = preview_semantic_move(ctx, move_id="tighten_low_end")

    # Existing fields still present
    assert "plan_template" in result
    assert "verification_plans" in result or "verification_plan" in result

    # New additive fields
    assert "compiled_plan" in result, "compiled_plan should be an additive field"
    assert "compiled_plan_executable" in result
    assert isinstance(result["compiled_plan_executable"], bool)


def test_preview_semantic_move_unknown_still_errors_cleanly():
    """Unknown move_id path is unaffected by the compile addition."""
    from types import SimpleNamespace
    from mcp_server.semantic_moves.tools import preview_semantic_move

    ctx = SimpleNamespace(lifespan_context={})
    result = preview_semantic_move(ctx, move_id="nonexistent_move_xyz")
    assert "error" in result
    assert "available_moves" in result
