"""Tests for the branch-lifecycle classifier (PR7).

Covers classify_branch_outcome across technical-safety mode and
exploration-rules mode. The pre-existing apply_hard_rules is already
covered by test_evaluation_fabric.py — we only test the new classifier.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.evaluation.policy import (
    classify_branch_outcome,
    BranchOutcome,
)


# ── Technical-safety mode (default) ──────────────────────────────────────


class TestClassifyTechnicalMode:

    def test_high_score_keeps(self):
        outcome = classify_branch_outcome(score=0.75)
        assert outcome.status == "keep"
        assert outcome.keep_change is True
        assert outcome.failure_reasons == []

    def test_low_score_undoes(self):
        outcome = classify_branch_outcome(score=0.20)
        assert outcome.status == "undo"
        assert outcome.keep_change is False
        assert any("score" in f.lower() for f in outcome.failure_reasons)

    def test_protection_violation_always_undoes(self):
        outcome = classify_branch_outcome(
            score=0.95,  # great score
            protection_violated=True,
        )
        assert outcome.status == "undo"
        assert any("protected dimension" in f for f in outcome.failure_reasons)

    def test_exactly_at_threshold_keeps(self):
        outcome = classify_branch_outcome(score=0.40)
        assert outcome.status == "keep"


# ── Exploration-rules mode ───────────────────────────────────────────────


class TestClassifyExplorationMode:

    def test_low_score_becomes_interesting_but_failed(self):
        outcome = classify_branch_outcome(score=0.20, exploration_rules=True)
        assert outcome.status == "interesting_but_failed"
        assert outcome.keep_change is False

    def test_high_score_still_keeps_in_exploration_mode(self):
        outcome = classify_branch_outcome(score=0.75, exploration_rules=True)
        assert outcome.status == "keep"
        assert outcome.keep_change is True

    def test_protection_violation_still_forces_undo(self):
        """Safety invariant — exploration_rules does NOT soften protection."""
        outcome = classify_branch_outcome(
            score=0.95,
            protection_violated=True,
            exploration_rules=True,
        )
        assert outcome.status == "undo"
        assert outcome.keep_change is False

    def test_failure_reasons_preserved_in_exploration(self):
        outcome = classify_branch_outcome(score=0.20, exploration_rules=True)
        # Exploration mode doesn't discard the failure_reasons — they're
        # retained for audit.
        assert outcome.failure_reasons

    def test_note_explains_exploration_decision(self):
        outcome = classify_branch_outcome(score=0.20, exploration_rules=True)
        assert "exploration" in outcome.note.lower()


# ── Measurable-delta rule interaction ───────────────────────────────────


class TestMeasurableDelta:

    def test_zero_measurable_delta_undoes_in_technical_mode(self):
        outcome = classify_branch_outcome(
            score=0.8,
            measurable_count=1,
            target_count=1,
            goal_progress=0.0,  # delta 0 — fails rule 3
        )
        assert outcome.status == "undo"

    def test_zero_measurable_delta_becomes_interesting_in_exploration(self):
        outcome = classify_branch_outcome(
            score=0.8,
            measurable_count=1,
            target_count=1,
            goal_progress=0.0,
            exploration_rules=True,
        )
        assert outcome.status == "interesting_but_failed"


# ── to_dict shape ───────────────────────────────────────────────────────


class TestBranchOutcomeToDict:

    def test_all_fields_present(self):
        outcome = classify_branch_outcome(score=0.5)
        d = outcome.to_dict()
        assert "status" in d
        assert "keep_change" in d
        assert "score" in d
        assert "failure_reasons" in d
        assert "note" in d

    def test_keep_has_no_failure_reasons(self):
        d = classify_branch_outcome(score=0.9).to_dict()
        assert d["failure_reasons"] == []
        assert d["status"] == "keep"
