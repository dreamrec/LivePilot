"""Unit tests for Wonder Mode variant distinctness enforcement."""

from mcp_server.wonder_mode.engine import (
    build_analytical_variant,
    build_variant,
    select_distinct_variants,
)


# ── Helpers ──────────────────────────────────────────────────────


def _move(move_id, family, tools=None, risk="low"):
    return {
        "move_id": move_id,
        "family": family,
        "intent": f"Test move {move_id}",
        "targets": {"energy": 0.5},
        "protect": {"clarity": 0.7},
        "risk_level": risk,
        "compile_plan": [
            {"tool": t, "params": {}, "description": f"Do {t}"} for t in (tools or ["set_track_volume"])
        ],
        "relevance_score": 0.5,
        "confidence": 0.7,
    }


# ── Distinct selection ───────────────────────────────────────────


def test_three_different_families_gives_three():
    """3 moves from different families -> 3 distinct variants."""
    moves = [
        _move("punch", "mix"),
        _move("build_section", "arrangement"),
        _move("add_riser", "transition"),
    ]
    result = select_distinct_variants(moves)
    assert len(result) == 3
    families = {m["family"] for m in result}
    assert len(families) == 3


def test_two_families_gives_two():
    """2 distinct families -> only 2 moves returned."""
    moves = [
        _move("punch", "mix", tools=["set_track_volume"]),
        _move("widen", "mix", tools=["set_track_volume"]),  # same family AND same shape
        _move("build_section", "arrangement", tools=["create_clip"]),
    ]
    result = select_distinct_variants(moves)
    assert len(result) == 2
    ids = {m["move_id"] for m in result}
    assert "punch" in ids
    assert "build_section" in ids


def test_same_family_different_shape_is_distinct():
    """Same family but different compile_plan shapes = distinct."""
    moves = [
        _move("punch", "mix", tools=["set_track_volume", "set_track_send"]),
        _move("widen", "mix", tools=["set_device_parameter", "set_track_pan"]),
    ]
    result = select_distinct_variants(moves)
    assert len(result) == 2


def test_same_family_same_shape_not_distinct():
    """Same family + same tool set = NOT distinct."""
    moves = [
        _move("punch", "mix", tools=["set_track_volume"]),
        _move("louder", "mix", tools=["set_track_volume"]),
    ]
    result = select_distinct_variants(moves)
    assert len(result) == 1


def test_one_move_returns_one():
    """Single move -> 1 variant."""
    moves = [_move("punch", "mix")]
    result = select_distinct_variants(moves)
    assert len(result) == 1


def test_zero_moves_returns_empty():
    """No moves -> empty list."""
    result = select_distinct_variants([])
    assert result == []


def test_same_move_id_never_duplicated():
    """Same move_id must not appear twice."""
    moves = [
        _move("punch", "mix"),
        _move("punch", "mix"),
        _move("widen", "sound_design"),
    ]
    result = select_distinct_variants(moves)
    ids = [m["move_id"] for m in result]
    assert len(ids) == len(set(ids))


# ── analytical_only field ────────────────────────────────────────


def test_build_variant_has_analytical_only_false():
    move = _move("punch", "mix")
    v = build_variant(label="safe", move_dict=move, novelty_level=0.25, variant_id="v1")
    assert v["analytical_only"] is False


def test_build_analytical_variant_has_analytical_only_true():
    v = build_analytical_variant(label="safe", request_text="test", novelty_level=0.25, variant_id="v1")
    assert v["analytical_only"] is True
    assert v["compiled_plan"] is None


def test_build_variant_has_distinctness_reason():
    move = _move("punch", "mix")
    v = build_variant(label="safe", move_dict=move, novelty_level=0.25, variant_id="v1")
    assert "distinctness_reason" in v
