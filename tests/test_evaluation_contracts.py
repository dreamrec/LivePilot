"""Tests for shared evaluation contract types."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._evaluation_contracts import (
    EvaluationRequest,
    EvaluationResult,
    MEASURABLE_DIMENSIONS,
    ALL_DIMENSIONS,
    is_dimension_measurable,
)


class TestMeasurableDimensions:
    def test_brightness_is_measurable(self):
        assert is_dimension_measurable("brightness")

    def test_warmth_is_measurable(self):
        assert is_dimension_measurable("warmth")

    def test_weight_is_measurable(self):
        assert is_dimension_measurable("weight")

    def test_clarity_is_measurable(self):
        assert is_dimension_measurable("clarity")

    def test_energy_is_measurable(self):
        assert is_dimension_measurable("energy")

    def test_punch_is_measurable(self):
        assert is_dimension_measurable("punch")

    def test_density_is_measurable(self):
        assert is_dimension_measurable("density")

    def test_width_is_not_measurable(self):
        assert not is_dimension_measurable("width")

    def test_groove_is_not_measurable(self):
        assert not is_dimension_measurable("groove")

    def test_depth_is_not_measurable(self):
        assert not is_dimension_measurable("depth")

    def test_motion_is_not_measurable(self):
        assert not is_dimension_measurable("motion")

    def test_unknown_is_not_measurable(self):
        assert not is_dimension_measurable("nonexistent")

    def test_measurable_is_subset_of_all(self):
        assert MEASURABLE_DIMENSIONS.issubset(ALL_DIMENSIONS)


class TestEvaluationRequest:
    def test_creates_valid_request(self):
        req = EvaluationRequest(
            engine="mix",
            goal={"targets": {"clarity": 0.5}},
            before={"spectrum": {"sub": 0.1}},
            after={"spectrum": {"sub": 0.2}},
        )
        assert req.engine == "mix"
        assert req.goal["targets"]["clarity"] == 0.5

    def test_to_dict(self):
        req = EvaluationRequest(engine="composition", goal={}, before={}, after={})
        d = req.to_dict()
        assert d["engine"] == "composition"
        assert "before" in d
        assert "after" in d

    def test_defaults_are_empty(self):
        req = EvaluationRequest(engine="test")
        assert req.goal == {}
        assert req.protect == {}
        assert req.context == {}


class TestEvaluationResult:
    def test_creates_valid_result(self):
        res = EvaluationResult(
            engine="mix", score=0.7, keep_change=True,
            goal_progress=0.5, collateral_damage=0.1,
        )
        assert res.keep_change is True
        assert res.score == 0.7

    def test_to_dict(self):
        res = EvaluationResult(engine="mix", score=0.5, keep_change=False)
        d = res.to_dict()
        assert d["score"] == 0.5
        assert d["keep_change"] is False
        assert d["engine"] == "mix"

    def test_default_decision_mode(self):
        res = EvaluationResult(engine="test")
        assert res.decision_mode == "measured"

    def test_memory_candidate_default_false(self):
        res = EvaluationResult(engine="test")
        assert res.memory_candidate is False

    def test_hard_rule_failures_empty_by_default(self):
        res = EvaluationResult(engine="test")
        assert res.hard_rule_failures == []
