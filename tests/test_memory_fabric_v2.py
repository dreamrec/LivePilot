"""Tests for Memory Fabric V2 — anti-memory, promotion rules."""

from __future__ import annotations

import pytest

from mcp_server.memory.anti_memory import AntiPreference, AntiMemoryStore
from mcp_server.memory.promotion import (
    PromotionCandidate,
    evaluate_promotion,
    batch_evaluate_promotions,
)


# ── helpers ───────────────────────────────────────────────────────────


def _make_entry(
    *,
    kept: bool = True,
    score: float = 0.8,
    intent: str = "add tension to buildup",
    engine: str = "composition",
    dimension_improvements: dict | None = None,
    entry_id: str = "move_0001",
) -> dict:
    """Build a minimal ledger entry dict for promotion testing."""
    if dimension_improvements is None:
        dimension_improvements = {"tension": 0.15, "clarity": 0.08}
    return {
        "id": entry_id,
        "engine": engine,
        "intent": intent,
        "score": score,
        "kept": kept,
        "evaluation": {"dimension_improvements": dimension_improvements},
    }


# ── AntiPreference ───────────────────────────────────────────────────


class TestAntiPreference:
    def test_creates(self):
        p = AntiPreference(
            dimension="brightness",
            direction="increase",
            strength=0.4,
            evidence_count=2,
            last_seen_ms=1000,
        )
        assert p.dimension == "brightness"
        assert p.direction == "increase"
        assert p.strength == 0.4
        assert p.evidence_count == 2

    def test_to_dict(self):
        p = AntiPreference(
            dimension="width",
            direction="decrease",
            strength=0.6,
            evidence_count=3,
            last_seen_ms=2000,
        )
        d = p.to_dict()
        assert d["dimension"] == "width"
        assert d["direction"] == "decrease"
        assert d["strength"] == 0.6
        assert d["evidence_count"] == 3
        assert d["last_seen_ms"] == 2000


# ── AntiMemoryStore ──────────────────────────────────────────────────


class TestAntiMemoryStore:
    def test_record_dislike_increments(self):
        store = AntiMemoryStore()
        p1 = store.record_dislike("brightness", "increase")
        assert p1.evidence_count == 1
        p2 = store.record_dislike("brightness", "increase")
        assert p2.evidence_count == 2
        # Same object
        assert p1 is p2

    def test_get_anti_preferences(self):
        store = AntiMemoryStore()
        store.record_dislike("brightness", "increase")
        store.record_dislike("width", "decrease")
        prefs = store.get_anti_preferences()
        assert len(prefs) == 2

    def test_get_anti_preference_existing(self):
        store = AntiMemoryStore()
        store.record_dislike("density", "increase")
        p = store.get_anti_preference("density", "increase")
        assert p is not None
        assert p.dimension == "density"

    def test_get_anti_preference_missing(self):
        store = AntiMemoryStore()
        assert store.get_anti_preference("density", "increase") is None

    def test_should_caution_threshold(self):
        store = AntiMemoryStore()
        store.record_dislike("brightness", "increase")
        assert store.should_caution("brightness", "increase") is False
        store.record_dislike("brightness", "increase")
        assert store.should_caution("brightness", "increase") is True

    def test_should_caution_missing(self):
        store = AntiMemoryStore()
        assert store.should_caution("nonexistent", "increase") is False

    def test_multiple_dimensions(self):
        store = AntiMemoryStore()
        store.record_dislike("brightness", "increase")
        store.record_dislike("brightness", "decrease")
        store.record_dislike("width", "increase")
        prefs = store.get_anti_preferences()
        assert len(prefs) == 3
        # They are distinct preferences
        dims = {(p.dimension, p.direction) for p in prefs}
        assert dims == {
            ("brightness", "increase"),
            ("brightness", "decrease"),
            ("width", "increase"),
        }

    def test_strength_caps_at_one(self):
        store = AntiMemoryStore()
        for _ in range(10):
            store.record_dislike("density", "increase")
        p = store.get_anti_preference("density", "increase")
        assert p is not None
        assert p.strength <= 1.0

    def test_to_dict(self):
        store = AntiMemoryStore()
        store.record_dislike("brightness", "increase")
        d = store.to_dict()
        assert d["count"] == 1
        assert len(d["anti_preferences"]) == 1


# ── PromotionCandidate ───────────────────────────────────────────────


class TestPromotionCandidate:
    def test_creates(self):
        c = PromotionCandidate(
            ledger_entry_id="move_0001",
            engine="composition",
            intent="add tension",
            score=0.8,
            dimension_improvements={"tension": 0.15},
            eligible=True,
            reason="meets all criteria",
        )
        assert c.ledger_entry_id == "move_0001"
        assert c.eligible is True

    def test_to_dict(self):
        c = PromotionCandidate(
            ledger_entry_id="move_0002",
            engine="mix",
            intent="boost clarity",
            score=0.7,
        )
        d = c.to_dict()
        assert d["ledger_entry_id"] == "move_0002"
        assert d["engine"] == "mix"
        assert d["score"] == 0.7
        assert d["eligible"] is False


# ── evaluate_promotion ───────────────────────────────────────────────


class TestEvaluatePromotion:
    def test_kept_high_score_is_eligible(self):
        entry = _make_entry(kept=True, score=0.8)
        c = evaluate_promotion(entry)
        assert c.eligible is True
        assert "meets all" in c.reason

    def test_undone_entry_not_eligible(self):
        entry = _make_entry(kept=False, score=0.9)
        c = evaluate_promotion(entry)
        assert c.eligible is False
        assert "not kept" in c.reason

    def test_low_score_not_eligible(self):
        entry = _make_entry(kept=True, score=0.3)
        c = evaluate_promotion(entry)
        assert c.eligible is False
        assert "score too low" in c.reason

    def test_no_improvements_not_eligible(self):
        entry = _make_entry(
            kept=True, score=0.8, dimension_improvements={"tension": 0.01}
        )
        c = evaluate_promotion(entry)
        assert c.eligible is False
        assert "no dimension improvement" in c.reason

    def test_empty_improvements_not_eligible(self):
        entry = _make_entry(kept=True, score=0.8, dimension_improvements={})
        c = evaluate_promotion(entry)
        assert c.eligible is False

    def test_empty_intent_not_eligible(self):
        entry = _make_entry(kept=True, score=0.8, intent="")
        c = evaluate_promotion(entry)
        assert c.eligible is False
        assert "empty intent" in c.reason

    def test_whitespace_intent_not_eligible(self):
        entry = _make_entry(kept=True, score=0.8, intent="   ")
        c = evaluate_promotion(entry)
        assert c.eligible is False
        assert "empty intent" in c.reason

    def test_score_exactly_at_threshold(self):
        entry = _make_entry(kept=True, score=0.6)
        c = evaluate_promotion(entry)
        assert c.eligible is True


# ── batch_evaluate_promotions ────────────────────────────────────────


class TestBatchEvaluatePromotions:
    def test_filters_to_only_eligible(self):
        entries = [
            _make_entry(kept=True, score=0.8, entry_id="move_0001"),
            _make_entry(kept=False, score=0.9, entry_id="move_0002"),
            _make_entry(kept=True, score=0.3, entry_id="move_0003"),
            _make_entry(kept=True, score=0.7, entry_id="move_0004"),
        ]
        eligible = batch_evaluate_promotions(entries)
        assert len(eligible) == 2
        ids = {c.ledger_entry_id for c in eligible}
        assert ids == {"move_0001", "move_0004"}

    def test_empty_list(self):
        assert batch_evaluate_promotions([]) == []

    def test_all_ineligible(self):
        entries = [
            _make_entry(kept=False, score=0.1, entry_id="move_0001"),
            _make_entry(kept=True, score=0.2, entry_id="move_0002"),
        ]
        assert batch_evaluate_promotions(entries) == []
