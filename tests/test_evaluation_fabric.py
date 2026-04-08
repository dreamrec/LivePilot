"""Tests for Evaluation Fabric — feature extractors, policy, and evaluators."""

import pytest

from mcp_server.evaluation.feature_extractors import extract_dimension_value
from mcp_server.evaluation.policy import apply_hard_rules
from mcp_server.evaluation.fabric import (
    evaluate_sonic_move,
    evaluate_composition_move,
)
from mcp_server.tools._evaluation_contracts import EvaluationRequest, EvaluationResult


# ── Fixtures ─────────────────────────────────────────────────────────

def _make_snapshot(
    sub=0.3, low=0.4, low_mid=0.5, mid=0.4, high_mid=0.3,
    presence=0.2, high=0.3, rms=0.5, peak=0.8,
):
    """Build a normalized sonic snapshot."""
    return {
        "spectrum": {
            "sub": sub, "low": low, "low_mid": low_mid, "mid": mid,
            "high_mid": high_mid, "presence": presence, "high": high,
        },
        "rms": rms,
        "peak": peak,
        "detected_key": None,
        "source": "test",
        "normalized_at_ms": 0,
    }


# ── TestFeatureExtractors ────────────────────────────────────────────

class TestFeatureExtractors:
    def test_brightness(self):
        snap = _make_snapshot(high=0.6, presence=0.4)
        val = extract_dimension_value(snap, "brightness")
        assert val == pytest.approx(0.5, abs=0.01)

    def test_warmth(self):
        snap = _make_snapshot(low_mid=0.7)
        val = extract_dimension_value(snap, "warmth")
        assert val == pytest.approx(0.7, abs=0.01)

    def test_weight(self):
        snap = _make_snapshot(sub=0.6, low=0.8)
        val = extract_dimension_value(snap, "weight")
        assert val == pytest.approx(0.7, abs=0.01)

    def test_clarity(self):
        snap = _make_snapshot(low_mid=0.3)
        val = extract_dimension_value(snap, "clarity")
        assert val == pytest.approx(0.7, abs=0.01)

    def test_density(self):
        # Uniform bands -> high density (close to 1.0)
        snap = _make_snapshot(sub=0.5, low=0.5, low_mid=0.5, mid=0.5,
                              high_mid=0.5, presence=0.5, high=0.5)
        val = extract_dimension_value(snap, "density")
        assert val is not None
        assert val == pytest.approx(1.0, abs=0.01)

    def test_energy(self):
        snap = _make_snapshot(rms=0.65)
        val = extract_dimension_value(snap, "energy")
        assert val == pytest.approx(0.65, abs=0.01)

    def test_punch(self):
        snap = _make_snapshot(rms=0.5, peak=0.9)
        val = extract_dimension_value(snap, "punch")
        assert val is not None
        assert 0.0 <= val <= 1.0

    def test_unmeasurable_returns_none(self):
        snap = _make_snapshot()
        for dim in ("width", "depth", "motion", "contrast", "groove",
                    "tension", "novelty", "polish", "emotion", "cohesion"):
            assert extract_dimension_value(snap, dim) is None

    def test_empty_snapshot_returns_none(self):
        assert extract_dimension_value({}, "brightness") is None
        assert extract_dimension_value(None, "brightness") is None

    def test_no_spectrum_returns_none(self):
        assert extract_dimension_value({"rms": 0.5}, "brightness") is None


# ── TestPolicy ───────────────────────────────────────────────────────

class TestPolicy:
    def test_measurable_improvement_kept(self):
        keep, failures = apply_hard_rules(
            goal_progress=0.1,
            collateral_damage=0.0,
            protection_violated=False,
            measurable_count=2,
            score=0.65,
            target_count=2,
        )
        assert keep is True
        assert len(failures) == 0

    def test_no_improvement_undone(self):
        keep, failures = apply_hard_rules(
            goal_progress=-0.05,
            collateral_damage=0.0,
            protection_violated=False,
            measurable_count=2,
            score=0.45,
            target_count=2,
        )
        assert keep is False
        assert any("measurable delta" in f for f in failures)

    def test_protection_violated(self):
        keep, failures = apply_hard_rules(
            goal_progress=0.1,
            collateral_damage=0.2,
            protection_violated=True,
            measurable_count=2,
            score=0.60,
            target_count=2,
        )
        assert keep is False
        assert any("protected" in f.lower() for f in failures)

    def test_score_threshold(self):
        keep, failures = apply_hard_rules(
            goal_progress=0.01,
            collateral_damage=0.0,
            protection_violated=False,
            measurable_count=2,
            score=0.35,
            target_count=2,
        )
        assert keep is False
        assert any("0.40" in f for f in failures)

    def test_unmeasurable_defers(self):
        keep, failures = apply_hard_rules(
            goal_progress=0.0,
            collateral_damage=0.0,
            protection_violated=False,
            measurable_count=0,
            score=0.50,
            target_count=3,
        )
        assert keep is True
        assert any("deferring" in f.lower() for f in failures)


# ── TestFabricSonicEvaluation ────────────────────────────────────────

class TestFabricSonicEvaluation:
    def test_improvement_kept(self):
        before = _make_snapshot(high=0.3, presence=0.2)
        after = _make_snapshot(high=0.6, presence=0.5)
        req = EvaluationRequest(
            engine="sonic",
            goal={"targets": {"brightness": 1.0}},
            before=before,
            after=after,
            protect={},
        )
        result = evaluate_sonic_move(req)
        assert isinstance(result, EvaluationResult)
        assert result.keep_change is True
        assert result.goal_progress > 0
        assert result.score > 0.40

    def test_regression_undone(self):
        before = _make_snapshot(high=0.6, presence=0.5)
        after = _make_snapshot(high=0.2, presence=0.1)
        req = EvaluationRequest(
            engine="sonic",
            goal={"targets": {"brightness": 1.0}},
            before=before,
            after=after,
            protect={},
        )
        result = evaluate_sonic_move(req)
        assert isinstance(result, EvaluationResult)
        assert result.keep_change is False
        assert result.goal_progress < 0

    def test_protected_violation(self):
        before = _make_snapshot(low_mid=0.3)
        after = _make_snapshot(low_mid=0.8)  # warmth went up, but clarity dropped
        req = EvaluationRequest(
            engine="sonic",
            goal={"targets": {"warmth": 1.0}},
            before=before,
            after=after,
            protect={"clarity": 0.8},  # clarity = 1 - low_mid; after = 0.2, below 0.8
        )
        result = evaluate_sonic_move(req)
        assert isinstance(result, EvaluationResult)
        assert result.keep_change is False
        assert any("protected" in f.lower() for f in result.hard_rule_failures)

    def test_unmeasurable_defer(self):
        before = _make_snapshot()
        after = _make_snapshot()
        req = EvaluationRequest(
            engine="sonic",
            goal={"targets": {"width": 0.5, "depth": 0.5}},
            before=before,
            after=after,
            protect={},
        )
        result = evaluate_sonic_move(req)
        assert isinstance(result, EvaluationResult)
        assert result.keep_change is True  # deferred to agent
        assert result.decision_mode == "deferred"


# ── TestFabricCompositionEvaluation ──────────────────────────────────

class TestFabricCompositionEvaluation:
    def test_issue_reduction_kept(self):
        before = [
            {"issue_type": "repetition", "severity": 0.8},
            {"issue_type": "stale_section", "severity": 0.6},
        ]
        after = [
            {"issue_type": "repetition", "severity": 0.3},
        ]
        result = evaluate_composition_move(before, after)
        assert isinstance(result, EvaluationResult)
        assert result.keep_change is True
        assert result.score > 0.5

    def test_issue_increase_undone(self):
        before = [
            {"issue_type": "repetition", "severity": 0.3},
        ]
        after = [
            {"issue_type": "repetition", "severity": 0.5},
            {"issue_type": "stale_section", "severity": 0.7},
            {"issue_type": "no_contrast", "severity": 0.6},
        ]
        result = evaluate_composition_move(before, after)
        assert isinstance(result, EvaluationResult)
        assert result.keep_change is False
