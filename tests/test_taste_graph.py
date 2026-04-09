"""Tests for TasteGraph — extended taste model for personalized ranking."""

import pytest

from mcp_server.memory.taste_graph import (
    TasteGraph, MoveFamilyScore, DeviceAffinity, build_taste_graph,
)


def test_empty_graph():
    graph = TasteGraph()
    assert graph.evidence_count == 0
    assert graph.novelty_band == 0.5
    assert graph.to_dict()["evidence_count"] == 0


def test_record_move_outcome_kept():
    graph = TasteGraph()
    graph.record_move_outcome("make_punchier", "mix", kept=True, score=0.7)
    assert graph.evidence_count == 1
    assert "mix" in graph.move_family_scores
    assert graph.move_family_scores["mix"].score > 0
    assert graph.move_family_scores["mix"].kept_count == 1


def test_record_move_outcome_undone():
    graph = TasteGraph()
    graph.record_move_outcome("darken_mix", "mix", kept=False, score=0.3)
    assert graph.move_family_scores["mix"].score < 0
    assert graph.move_family_scores["mix"].undone_count == 1


def test_repeated_outcomes_accumulate():
    graph = TasteGraph()
    for _ in range(5):
        graph.record_move_outcome("punchier", "mix", kept=True)
    assert graph.move_family_scores["mix"].score > 0.3
    assert graph.move_family_scores["mix"].kept_count == 5
    assert graph.evidence_count == 5


def test_record_device_use():
    graph = TasteGraph()
    graph.record_device_use("Operator", positive=True)
    graph.record_device_use("Operator", positive=True)
    graph.record_device_use("Wavetable", positive=False)
    assert graph.device_affinities["Operator"].affinity > 0
    assert graph.device_affinities["Wavetable"].affinity < 0
    assert graph.device_affinities["Operator"].use_count == 2


def test_novelty_band_shifts():
    graph = TasteGraph()
    assert graph.novelty_band == 0.5
    graph.update_novelty_from_experiment(chose_bold=True)
    assert graph.novelty_band > 0.5
    graph.update_novelty_from_experiment(chose_bold=False)
    graph.update_novelty_from_experiment(chose_bold=False)
    assert graph.novelty_band < 0.5


def test_rank_moves_neutral():
    """With no evidence, all moves should score near 0.5."""
    graph = TasteGraph()
    moves = [
        {"move_id": "a", "family": "mix", "targets": {"punch": 0.5}, "risk_level": "low"},
        {"move_id": "b", "family": "mix", "targets": {"width": 0.5}, "risk_level": "medium"},
    ]
    ranked = graph.rank_moves(moves)
    assert len(ranked) == 2
    assert all(0.4 < m["taste_score"] < 0.7 for m in ranked)


def test_rank_moves_favors_preferred_family():
    graph = TasteGraph()
    # Build preference for mix moves
    for _ in range(5):
        graph.record_move_outcome("punchier", "mix", kept=True)

    moves = [
        {"move_id": "a", "family": "mix", "targets": {}, "risk_level": "low"},
        {"move_id": "b", "family": "arrangement", "targets": {}, "risk_level": "low"},
    ]
    ranked = graph.rank_moves(moves)
    assert ranked[0]["move_id"] == "a"  # Mix preferred
    assert ranked[0]["taste_score"] > ranked[1]["taste_score"]


def test_rank_moves_penalizes_anti_preferences():
    graph = TasteGraph()
    graph.dimension_avoidances["brightness"] = "increase"

    moves = [
        {"move_id": "bright", "family": "mix", "targets": {"brightness": 0.5}, "risk_level": "low"},
        {"move_id": "warm", "family": "mix", "targets": {"warmth": 0.5}, "risk_level": "low"},
    ]
    ranked = graph.rank_moves(moves)
    assert ranked[0]["move_id"] == "warm"  # Warm preferred (brightness penalized)


def test_explain_with_evidence():
    graph = TasteGraph()
    for _ in range(3):
        graph.record_move_outcome("punchier", "mix", kept=True)
    graph.record_device_use("Operator", positive=True)
    graph.record_device_use("Operator", positive=True)
    graph.dimension_avoidances["brightness"] = "increase"

    explanation = graph.explain()
    assert explanation["evidence_count"] > 0
    assert len(explanation["explanations"]) > 0
    assert any("mix" in e.lower() for e in explanation["explanations"])
    assert any("brightness" in e.lower() for e in explanation["explanations"])


def test_explain_empty_graph():
    graph = TasteGraph()
    explanation = graph.explain()
    assert explanation["evidence_count"] == 0
    # Might have no explanations or just the neutral novelty one


def test_build_taste_graph_integration():
    """Test building from existing stores (with mocks)."""
    from mcp_server.memory.taste_memory import TasteMemoryStore
    from mcp_server.memory.anti_memory import AntiMemoryStore

    taste_store = TasteMemoryStore()
    anti_store = AntiMemoryStore()
    anti_store.record_dislike("brightness", "increase")

    graph = build_taste_graph(taste_store=taste_store, anti_store=anti_store)
    assert "brightness" in graph.dimension_avoidances


def test_to_dict_structure():
    graph = TasteGraph()
    graph.record_move_outcome("punchier", "mix", kept=True)
    graph.record_device_use("Operator", positive=True)
    d = graph.to_dict()
    assert "dimension_weights" in d
    assert "move_family_scores" in d
    assert "device_affinities" in d
    assert "novelty_band" in d
    assert "evidence_count" in d
