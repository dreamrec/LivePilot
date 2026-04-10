"""Unit tests for Wonder Mode engine — pure computation, no Ableton needed."""

import math

from mcp_server.wonder_mode.engine import (
    assign_moves_to_tiers,
    build_analytical_variant,
    build_variant,
    compute_taste_fit,
    discover_moves,
    generate_and_rank,
    rank_variants,
)
from mcp_server.memory.taste_graph import TasteGraph


# ── Helpers ──────────────────────────────────────────────────────


def _sample_move():
    return {
        "move_id": "make_punchier",
        "family": "mix",
        "intent": "Make the mix punchier with tighter transients",
        "targets": {"punch": 0.5, "energy": 0.3, "contrast": 0.2},
        "protect": {"clarity": 0.7, "warmth": 0.5},
        "risk_level": "low",
        "compile_plan": [
            {"tool": "set_device_parameter", "params": {"track": 0}, "description": "Boost attack"}
        ],
        "confidence": 0.7,
    }


def _sample_brain():
    return {
        "identity_core": "Dark minimal techno",
        "sacred_elements": [
            {"element_type": "groove", "description": "808 kick pattern", "salience": 0.8},
            {"element_type": "texture", "description": "Pad atmosphere", "salience": 0.6},
        ],
        "identity_confidence": 0.7,
        "energy_arc": [0.3, 0.5, 0.8],
    }


def _three_variants():
    return [
        {
            "variant_id": "v_safe", "label": "safe", "move_id": "a", "family": "mix",
            "identity_effect": "preserves", "novelty_level": 0.25,
            "taste_fit": 0.6, "targets_snapshot": {"punch": 0.35},
            "what_changed": "x", "what_preserved": "y", "why_it_matters": "z",
            "intent": "i", "compiled_plan": [], "score": 0, "rank": 0,
            "score_breakdown": {},
        },
        {
            "variant_id": "v_strong", "label": "strong", "move_id": "b", "family": "mix",
            "identity_effect": "evolves", "novelty_level": 0.55,
            "taste_fit": 0.6, "targets_snapshot": {"energy": 0.5},
            "what_changed": "x", "what_preserved": "y", "why_it_matters": "z",
            "intent": "i", "compiled_plan": [], "score": 0, "rank": 0,
            "score_breakdown": {},
        },
        {
            "variant_id": "v_unexpected", "label": "unexpected", "move_id": "c", "family": "arrangement",
            "identity_effect": "contrasts", "novelty_level": 0.85,
            "taste_fit": 0.6, "targets_snapshot": {"width": 0.7},
            "what_changed": "x", "what_preserved": "y", "why_it_matters": "z",
            "intent": "i", "compiled_plan": [], "score": 0, "rank": 0,
            "score_breakdown": {},
        },
    ]


# ── Move discovery ───────────────────────────────────────────────


def test_moves_matched_by_keyword_relevance():
    moves = discover_moves("make it punchier")
    move_ids = [m["move_id"] for m in moves]
    assert "make_punchier" in move_ids


def test_different_requests_different_moves():
    punch_moves = discover_moves("make it punchier")
    wide_moves = discover_moves("widen the stereo field")
    assert punch_moves[0]["move_id"] != wide_moves[0]["move_id"]


def test_no_matching_moves_returns_empty():
    moves = discover_moves("quantum entanglement vibes")
    assert moves == []


def test_discover_includes_compile_plan():
    moves = discover_moves("make it punchier")
    for m in moves:
        assert isinstance(m.get("compile_plan"), list)


# ── Tier assignment ──────────────────────────────────────────────


def test_moves_assigned_by_risk_tier():
    moves = [
        {"move_id": "a", "risk_level": "low", "targets": {"x": 0.5}, "protect": {}, "compile_plan": []},
        {"move_id": "b", "risk_level": "medium", "targets": {"y": 0.5}, "protect": {}, "compile_plan": []},
        {"move_id": "c", "risk_level": "high", "targets": {"z": 0.5}, "protect": {}, "compile_plan": []},
    ]
    tiers = assign_moves_to_tiers(moves)
    assert tiers["safe"]["move_id"] == "a"
    assert tiers["unexpected"]["move_id"] == "c"


def test_novelty_envelopes_when_one_move():
    moves = [
        {"move_id": "only", "risk_level": "low", "targets": {"punch": 0.5},
         "protect": {"warmth": 0.6}, "compile_plan": [{"tool": "x"}]},
    ]
    tiers = assign_moves_to_tiers(moves)
    assert tiers["safe"]["targets"]["punch"] < 0.5
    assert tiers["strong"]["targets"]["punch"] == 0.5
    assert tiers["unexpected"]["targets"]["punch"] > 0.5
    for label in ("safe", "strong", "unexpected"):
        assert tiers[label]["compile_plan"] == [{"tool": "x"}]


def test_two_moves_fills_three_tiers():
    moves = [
        {"move_id": "a", "risk_level": "low", "targets": {"x": 0.4}, "protect": {}, "compile_plan": []},
        {"move_id": "b", "risk_level": "medium", "targets": {"y": 0.6}, "protect": {}, "compile_plan": []},
    ]
    tiers = assign_moves_to_tiers(moves)
    assert tiers["safe"]["move_id"] == "a"
    assert tiers["strong"]["move_id"] == "a"
    assert tiers["unexpected"]["move_id"] == "b"


def test_zero_moves_returns_empty():
    tiers = assign_moves_to_tiers([])
    assert tiers == {}


# ── Variant building ─────────────────────────────────────────────


def test_what_changed_populated_from_targets():
    v = build_variant("safe", _sample_move(), {}, 0.25)
    assert v["what_changed"]
    assert "punch" in v["what_changed"].lower()


def test_what_preserved_references_sacred_and_protect():
    v = build_variant("safe", _sample_move(), _sample_brain(), 0.25)
    assert "clarity" in v["what_preserved"].lower() or "warmth" in v["what_preserved"].lower()
    assert "808" in v["what_preserved"] or "kick" in v["what_preserved"].lower()


def test_compiled_plan_is_list_of_dicts():
    v = build_variant("safe", _sample_move(), {}, 0.25)
    assert isinstance(v["compiled_plan"], list)
    assert len(v["compiled_plan"]) > 0
    assert isinstance(v["compiled_plan"][0], dict)


def test_variant_has_targets_snapshot():
    v = build_variant("safe", _sample_move(), {}, 0.25)
    assert "targets_snapshot" in v
    assert "punch" in v["targets_snapshot"]


def test_no_song_brain_still_works():
    v = build_variant("safe", _sample_move(), {}, 0.25)
    assert v["what_preserved"]
    assert "clarity" in v["what_preserved"].lower() or "warmth" in v["what_preserved"].lower()


def test_identity_effect_from_risk():
    low = build_variant("safe", {**_sample_move(), "risk_level": "low"}, {}, 0.25)
    med = build_variant("strong", {**_sample_move(), "risk_level": "medium"}, {}, 0.55)
    high = build_variant("unexpected", {**_sample_move(), "risk_level": "high"}, {}, 0.85)
    assert low["identity_effect"] == "preserves"
    assert med["identity_effect"] == "evolves"
    assert high["identity_effect"] == "contrasts"


def test_analytical_fallback_has_none_plan():
    v = build_analytical_variant("safe", "test", 0.25)
    assert v["compiled_plan"] is None
    assert v["what_changed"]


# ── Taste fit ────────────────────────────────────────────────────


def test_taste_fit_neutral_when_no_evidence():
    tg = TasteGraph()
    score = compute_taste_fit(_sample_move(), tg)
    assert score == 0.5


def test_taste_fit_uses_full_taste_graph():
    tg = TasteGraph()
    tg.record_move_outcome("make_punchier", "mix", kept=True)
    tg.record_move_outcome("make_punchier", "mix", kept=True)
    score_with_pref = compute_taste_fit(_sample_move(), tg)

    tg2 = TasteGraph()
    score_neutral = compute_taste_fit(_sample_move(), tg2)
    assert score_with_pref != score_neutral


def test_anti_preference_reduces_taste_fit():
    tg = TasteGraph()
    tg.evidence_count = 1
    tg.dimension_avoidances["punch"] = "less"
    score = compute_taste_fit(_sample_move(), tg)

    tg2 = TasteGraph()
    tg2.evidence_count = 1
    score_no_avoid = compute_taste_fit(_sample_move(), tg2)
    assert score < score_no_avoid


def test_family_preference_shifts_taste_fit():
    tg = TasteGraph()
    tg.record_move_outcome("x", "mix", kept=True)
    tg.record_move_outcome("x", "mix", kept=True)
    tg.record_move_outcome("x", "mix", kept=True)

    mix_move = _sample_move()
    arr_move = {**_sample_move(), "family": "arrangement", "move_id": "arr_move"}

    mix_score = compute_taste_fit(mix_move, tg)
    arr_score = compute_taste_fit(arr_move, tg)
    assert mix_score > arr_score


def test_high_novelty_band_boosts_risky_moves():
    tg = TasteGraph()
    tg.evidence_count = 1
    tg.novelty_band = 0.8

    low_risk = {**_sample_move(), "risk_level": "low"}
    high_risk = {**_sample_move(), "risk_level": "high", "move_id": "risky"}

    low_score = compute_taste_fit(low_risk, tg)
    high_score = compute_taste_fit(high_risk, tg)
    assert high_score > low_score


# ── Ranking ──────────────────────────────────────────────────────


def test_bell_curve_moderate_user_strong_wins():
    variants = _three_variants()
    ranked = rank_variants(variants, {}, novelty_band=0.5)
    novelty_scores = {r["label"]: r["score_breakdown"]["novelty"] for r in ranked}
    assert novelty_scores["strong"] > novelty_scores["safe"]
    assert novelty_scores["strong"] > novelty_scores["unexpected"]


def test_bell_curve_experimental_user_unexpected_wins():
    variants = _three_variants()
    ranked = rank_variants(variants, {}, novelty_band=0.85)
    novelty_scores = {r["label"]: r["score_breakdown"]["novelty"] for r in ranked}
    assert novelty_scores["unexpected"] > novelty_scores["strong"]


def test_sacred_element_overlap_penalty():
    variants = _three_variants()
    brain = {"sacred_elements": [{"element_type": "energy", "salience": 0.8}]}
    ranked = rank_variants(variants, brain, novelty_band=0.5)
    strong = next(r for r in ranked if r["label"] == "strong")
    safe = next(r for r in ranked if r["label"] == "safe")
    assert strong["score_breakdown"]["identity"] < safe["score_breakdown"]["identity"]


def test_coherence_penalty_same_move():
    variants = _three_variants()
    variants[1]["move_id"] = "a"  # same as safe
    ranked = rank_variants(variants, {}, novelty_band=0.5)
    safe_coherence = next(r["score_breakdown"]["coherence"] for r in ranked if r["label"] == "safe")
    unexpected_coherence = next(r["score_breakdown"]["coherence"] for r in ranked if r["label"] == "unexpected")
    assert unexpected_coherence > safe_coherence


def test_weight_shift_high_identity_confidence():
    variants = _three_variants()
    brain = {"identity_confidence": 0.85}
    ranked = rank_variants(variants, brain, novelty_band=0.5)
    weights = ranked[0]["score_breakdown"]["weights"]
    assert weights["identity"] == 0.40


def test_weight_shift_no_taste_evidence():
    variants = _three_variants()
    ranked = rank_variants(variants, {}, novelty_band=0.5, taste_evidence=0)
    weights = ranked[0]["score_breakdown"]["weights"]
    assert weights["taste"] == 0.00


def test_resets_never_beats_preserves_equal_novelty():
    variants = _three_variants()
    variants[0]["identity_effect"] = "preserves"
    variants[0]["novelty_level"] = 0.5
    variants[2]["identity_effect"] = "resets"
    variants[2]["novelty_level"] = 0.5
    ranked = rank_variants(variants, {}, novelty_band=0.5)
    preserves_score = next(r["score"] for r in ranked if r["identity_effect"] == "preserves")
    resets_score = next(r["score"] for r in ranked if r["identity_effect"] == "resets")
    assert preserves_score > resets_score


def test_score_breakdown_returned():
    variants = _three_variants()
    ranked = rank_variants(variants, {}, novelty_band=0.5)
    for r in ranked:
        bd = r["score_breakdown"]
        assert "taste" in bd
        assert "identity" in bd
        assert "novelty" in bd
        assert "coherence" in bd
        assert "weights" in bd
        assert 0 <= r["score"] <= 1


# ── Pipeline ─────────────────────────────────────────────────────


def test_full_pipeline_with_matching_request():
    result = generate_and_rank("make it punchier")
    assert result["mode"] == "wonder"
    assert len(result["variants"]) == 3
    assert result["recommended"]
    assert result["move_count_matched"] >= 1
    labels = {v["label"] for v in result["variants"]}
    assert labels == {"safe", "strong", "unexpected"}


def test_full_pipeline_no_matches():
    result = generate_and_rank("quantum entanglement vibes")
    assert len(result["variants"]) == 3
    assert result["move_count_matched"] == 0
    for v in result["variants"]:
        assert v["compiled_plan"] is None


def test_rank_preserves_all_fields():
    """Input dict fields survive round-trip through rank_variants."""
    variants = _three_variants()
    variants[0]["compiled_plan"] = [{"tool": "test"}]
    variants[0]["what_changed"] = "Custom change text"
    ranked = rank_variants(variants, {}, novelty_band=0.5)
    v0 = next(r for r in ranked if r["variant_id"] == "v_safe")
    assert v0["compiled_plan"] == [{"tool": "test"}]
    assert v0["what_changed"] == "Custom change text"
    assert v0["targets_snapshot"] == {"punch": 0.35}
