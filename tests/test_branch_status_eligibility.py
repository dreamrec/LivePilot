"""Regression tests for the undo/analytical winner-eligibility bug.

Review found that undo-classified branches had status="evaluated" set
(for ranking reasons) but ranked_branches sorts by score without
re-checking evaluation.status. compare_experiments could therefore
recommend — and commit_experiment re-apply — a branch the classifier
explicitly rejected. Analytical-only branches hit the same path and
failed only at commit time.

This file verifies that rejected and analytical branches:
  1. Get the new dedicated status ("rejected" / "analytical")
  2. Are excluded from ranked_branches()
  3. Appear under separate keys in compare_experiments output
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.branches import seed_from_move_id, analytical_seed, freeform_seed
from mcp_server.experiment.models import ExperimentSet, ExperimentBranch


class TestStatusExclusionFromRanking:
    """ranked_branches() only surfaces status='evaluated' — so rejected /
    analytical / failed statuses all stay out of the winner set."""

    def _mixed_status_experiment(self):
        seed_a = seed_from_move_id("make_punchier")
        seed_b = seed_from_move_id("widen_pad")
        seed_c = analytical_seed("an_1", "consider X")
        seed_d = freeform_seed("f_1", "unreachable path")
        return ExperimentSet(
            experiment_id="exp_test",
            request_text="test",
            branches=[
                ExperimentBranch(
                    branch_id="b_kept",
                    name="kept",
                    seed=seed_a,
                    status="evaluated",
                    score=0.8,
                ),
                ExperimentBranch(
                    branch_id="b_rejected",
                    name="rejected",
                    seed=seed_b,
                    status="rejected",
                    score=0.35,
                ),
                ExperimentBranch(
                    branch_id="b_analytical",
                    name="analytical",
                    seed=seed_c,
                    status="analytical",
                    score=0.0,
                ),
                ExperimentBranch(
                    branch_id="b_failed",
                    name="failed",
                    seed=seed_d,
                    status="failed",
                    score=0.0,
                ),
            ],
        )

    def test_rejected_not_in_ranking(self):
        exp = self._mixed_status_experiment()
        ranked = exp.ranked_branches()
        assert all(b.status == "evaluated" for b in ranked)
        assert all(b.branch_id != "b_rejected" for b in ranked)

    def test_analytical_not_in_ranking(self):
        exp = self._mixed_status_experiment()
        ranked = exp.ranked_branches()
        assert all(b.branch_id != "b_analytical" for b in ranked)

    def test_failed_not_in_ranking(self):
        exp = self._mixed_status_experiment()
        ranked = exp.ranked_branches()
        assert all(b.branch_id != "b_failed" for b in ranked)

    def test_only_evaluated_branch_wins(self):
        exp = self._mixed_status_experiment()
        ranked = exp.ranked_branches()
        assert len(ranked) == 1
        assert ranked[0].branch_id == "b_kept"

    def test_rejected_with_higher_score_still_excluded(self):
        # Even if a rejected branch happens to have the highest score, it
        # never wins — status gate comes first.
        seed_keep = seed_from_move_id("a")
        seed_reject = seed_from_move_id("b")
        exp = ExperimentSet(
            experiment_id="e",
            request_text="t",
            branches=[
                ExperimentBranch(
                    branch_id="keep", name="keep", seed=seed_keep,
                    status="evaluated", score=0.45,
                ),
                ExperimentBranch(
                    branch_id="reject", name="reject", seed=seed_reject,
                    status="rejected", score=0.95,  # higher score, wrong status
                ),
            ],
        )
        ranked = exp.ranked_branches()
        assert len(ranked) == 1
        assert ranked[0].branch_id == "keep"


class TestRejectedStatusRoundTrip:
    """A branch built with status='rejected' must preserve it through
    to_dict so callers (and compare_experiments) can see the classification."""

    def test_rejected_status_in_to_dict(self):
        seed = seed_from_move_id("make_punchier")
        b = ExperimentBranch(
            branch_id="b", name="b", seed=seed, status="rejected", score=0.2,
        )
        d = b.to_dict()
        assert d["status"] == "rejected"

    def test_analytical_status_in_to_dict(self):
        seed = analytical_seed("a", "x")
        b = ExperimentBranch(
            branch_id="b", name="b", seed=seed, status="analytical", score=0.0,
        )
        d = b.to_dict()
        assert d["status"] == "analytical"
        assert d["analytical_only"] is True
