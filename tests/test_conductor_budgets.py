"""Tests for the Conductor Budget System."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._conductor_budgets import (
    TurnBudget,
    create_budget,
    spend_risk,
    spend_change,
    record_undo,
    spend_research,
    spend_novelty,
    is_budget_exhausted,
    get_budget_summary,
)
from mcp_server.tools._conductor import create_conductor_plan


class TestTurnBudget:
    def test_defaults(self):
        b = TurnBudget()
        assert b.latency_ms == 30000
        assert b.risk_points == 1.0
        assert b.novelty_points == 0.5
        assert b.change_count == 3
        assert b.undo_count == 3
        assert b.research_calls == 2

    def test_tracking_starts_at_zero(self):
        b = TurnBudget()
        assert b.elapsed_ms == 0
        assert b.risk_spent == 0.0
        assert b.novelty_spent == 0.0
        assert b.changes_made == 0
        assert b.undos_consecutive == 0
        assert b.research_used == 0

    def test_to_dict(self):
        b = TurnBudget()
        d = b.to_dict()
        assert isinstance(d, dict)
        assert d["latency_ms"] == 30000
        assert d["risk_spent"] == 0.0


class TestCreateBudget:
    def test_improve_is_default(self):
        b = create_budget()
        assert b.latency_ms == 30000
        assert b.risk_points > 0
        assert b.change_count > 0

    def test_observe_is_readonly(self):
        b = create_budget("observe")
        assert b.change_count == 0
        assert b.risk_points == 0.1
        assert b.novelty_points == 0.1
        assert b.research_calls == 0

    def test_explore_is_bold(self):
        b = create_budget("explore", aggression=1.0)
        assert b.risk_points >= 0.75
        assert b.novelty_points == 1.0
        assert b.change_count >= 3
        assert b.latency_ms == 45000

    def test_finish_is_conservative(self):
        b = create_budget("finish")
        assert b.novelty_points == 0.1
        assert b.risk_points <= 0.3
        assert b.change_count <= 2

    def test_diagnose_zero_change(self):
        b = create_budget("diagnose")
        assert b.change_count == 0
        assert b.risk_points == 0.0
        assert b.novelty_points == 0.0
        assert b.research_calls == 3

    def test_performance_low_latency(self):
        b = create_budget("performance")
        assert b.latency_ms == 10000
        assert b.risk_points <= 0.2
        assert b.research_calls == 0

    def test_aggression_scales_risk(self):
        low = create_budget("improve", aggression=0.0)
        high = create_budget("improve", aggression=1.0)
        assert high.risk_points > low.risk_points

    def test_aggression_scales_changes(self):
        low = create_budget("improve", aggression=0.0)
        high = create_budget("improve", aggression=1.0)
        assert high.change_count >= low.change_count

    def test_aggression_clamped(self):
        b1 = create_budget("improve", aggression=-5.0)
        b2 = create_budget("improve", aggression=0.0)
        assert b1.risk_points == b2.risk_points

        b3 = create_budget("improve", aggression=10.0)
        b4 = create_budget("improve", aggression=1.0)
        assert b3.risk_points == b4.risk_points

    def test_unknown_mode_uses_defaults(self):
        b = create_budget("nonexistent_mode")
        # Should still produce a valid budget (no preset overrides)
        assert b.latency_ms == 30000


class TestSpendRisk:
    def test_spend_within_budget(self):
        b = create_budget("improve", aggression=1.0)
        b, ok = spend_risk(b, 0.1)
        assert ok is True
        assert b.risk_spent == 0.1

    def test_spend_exceeding_budget(self):
        b = create_budget("improve", aggression=1.0)
        b, ok = spend_risk(b, 5.0)
        assert ok is False
        assert b.risk_spent == 0.0  # unchanged

    def test_spend_exactly_to_limit(self):
        b = TurnBudget(risk_points=0.5)
        b, ok = spend_risk(b, 0.5)
        assert ok is True
        assert b.risk_spent == 0.5

    def test_incremental_spending(self):
        b = TurnBudget(risk_points=0.3)
        b, ok1 = spend_risk(b, 0.1)
        b, ok2 = spend_risk(b, 0.1)
        b, ok3 = spend_risk(b, 0.1)
        b, ok4 = spend_risk(b, 0.1)  # over budget
        assert ok1 and ok2 and ok3
        assert ok4 is False


class TestSpendChange:
    def test_counts_down(self):
        b = TurnBudget(change_count=2)
        b, ok1 = spend_change(b)
        assert ok1 and b.changes_made == 1
        b, ok2 = spend_change(b)
        assert ok2 and b.changes_made == 2
        b, ok3 = spend_change(b)
        assert ok3 is False

    def test_change_resets_undo_count(self):
        b = TurnBudget(change_count=3, undo_count=3)
        b, _ = record_undo(b)
        b, _ = record_undo(b)
        assert b.undos_consecutive == 2
        b, _ = spend_change(b)
        assert b.undos_consecutive == 0


class TestRecordUndo:
    def test_tracks_consecutive(self):
        b = TurnBudget(undo_count=3)
        b, ok1 = record_undo(b)
        assert ok1 and b.undos_consecutive == 1
        b, ok2 = record_undo(b)
        assert ok2 and b.undos_consecutive == 2
        b, ok3 = record_undo(b)
        assert ok3 and b.undos_consecutive == 3

    def test_returns_false_at_limit(self):
        b = TurnBudget(undo_count=2)
        b, _ = record_undo(b)
        b, _ = record_undo(b)
        b, ok = record_undo(b)  # 3 > 2
        assert ok is False
        assert b.undos_consecutive == 3


class TestSpendResearch:
    def test_counts_down(self):
        b = TurnBudget(research_calls=2)
        b, ok1 = spend_research(b)
        assert ok1 and b.research_used == 1
        b, ok2 = spend_research(b)
        assert ok2 and b.research_used == 2
        b, ok3 = spend_research(b)
        assert ok3 is False

    def test_zero_research_budget(self):
        b = TurnBudget(research_calls=0)
        b, ok = spend_research(b)
        assert ok is False


class TestSpendNovelty:
    def test_spend_within_budget(self):
        b = TurnBudget(novelty_points=0.5)
        b, ok = spend_novelty(b, 0.3)
        assert ok is True
        assert abs(b.novelty_spent - 0.3) < 1e-9

    def test_spend_over_budget(self):
        b = TurnBudget(novelty_points=0.2)
        b, ok = spend_novelty(b, 0.5)
        assert ok is False


class TestBudgetExhausted:
    def test_fresh_budget_not_exhausted(self):
        b = create_budget("improve")
        assert is_budget_exhausted(b) is False

    def test_latency_exhaustion(self):
        b = TurnBudget(latency_ms=1000)
        b.elapsed_ms = 1000
        assert is_budget_exhausted(b) is True

    def test_risk_exhaustion(self):
        b = TurnBudget(risk_points=0.5)
        b.risk_spent = 0.5
        assert is_budget_exhausted(b) is True

    def test_change_exhaustion(self):
        b = TurnBudget(change_count=1)
        b.changes_made = 1
        assert is_budget_exhausted(b) is True

    def test_undo_exhaustion(self):
        b = TurnBudget(undo_count=2)
        b.undos_consecutive = 3  # > 2
        assert is_budget_exhausted(b) is True

    def test_novelty_exhaustion(self):
        b = TurnBudget(novelty_points=0.3)
        b.novelty_spent = 0.3
        assert is_budget_exhausted(b) is True

    def test_research_alone_not_exhausting(self):
        b = TurnBudget(research_calls=1)
        b.research_used = 1
        # Research exhaustion alone should NOT exhaust the budget
        assert is_budget_exhausted(b) is False

    def test_diagnose_zero_change_exhausted_immediately(self):
        b = create_budget("diagnose")
        # change_count=0 and changes_made=0 → 0 >= 0 → exhausted for changes
        assert is_budget_exhausted(b) is True


class TestGetBudgetSummary:
    def test_summary_structure(self):
        b = create_budget("improve")
        s = get_budget_summary(b)
        assert "latency" in s
        assert "risk" in s
        assert "novelty" in s
        assert "changes" in s
        assert "undos" in s
        assert "research" in s
        assert "overall_exhausted" in s

    def test_summary_remaining_values(self):
        b = TurnBudget(risk_points=1.0)
        b, _ = spend_risk(b, 0.3)
        s = get_budget_summary(b)
        assert s["risk"]["remaining"] == 0.7
        assert s["risk"]["spent"] == 0.3


class TestModeShaping:
    """Verify that mode presets produce meaningfully different budgets."""

    def test_observe_vs_explore(self):
        obs = create_budget("observe")
        exp = create_budget("explore", aggression=1.0)
        assert obs.change_count == 0
        assert exp.change_count >= 3
        assert obs.risk_points < exp.risk_points
        assert obs.novelty_points < exp.novelty_points

    def test_finish_vs_improve(self):
        fin = create_budget("finish", aggression=0.5)
        imp = create_budget("improve", aggression=0.5)
        assert fin.novelty_points < imp.novelty_points
        assert fin.change_count <= imp.change_count

    def test_performance_is_fast(self):
        perf = create_budget("performance")
        imp = create_budget("improve")
        assert perf.latency_ms < imp.latency_ms

    def test_diagnose_is_readonly(self):
        diag = create_budget("diagnose")
        assert diag.change_count == 0
        assert diag.risk_points == 0.0
        assert diag.research_calls > 0  # can research, just can't change


class TestCreateConductorPlan:
    def test_plan_includes_budget(self):
        plan = create_conductor_plan("make this punchier")
        d = plan.to_dict()
        assert "budget" in d
        assert d["budget"] is not None
        assert "risk_points" in d["budget"]

    def test_plan_mode_shapes_budget(self):
        plan = create_conductor_plan("analyze what's wrong", mode="diagnose")
        d = plan.to_dict()
        assert d["budget"]["change_count"] == 0
        assert d["budget"]["risk_points"] == 0.0

    def test_plan_aggression_affects_budget(self):
        low = create_conductor_plan("make it wider", mode="improve", aggression=0.0)
        high = create_conductor_plan("make it wider", mode="improve", aggression=1.0)
        assert high.to_dict()["budget"]["risk_points"] > low.to_dict()["budget"]["risk_points"]
