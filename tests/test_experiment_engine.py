"""Tests for the experiment engine — branch-based creative search."""

import pytest

from mcp_server.experiment.models import (
    ExperimentSet, ExperimentBranch, BranchSnapshot,
)
from mcp_server.experiment.engine import (
    create_experiment, get_experiment, list_experiments,
    run_branch, evaluate_branch, commit_branch, discard_experiment,
)


# ── Model tests ──────────────────────────────────────────────────────────────

def test_branch_snapshot_to_dict():
    snap = BranchSnapshot(rms=0.15, peak=0.45, timestamp_ms=1000)
    d = snap.to_dict()
    assert d["rms"] == 0.15
    assert d["peak"] == 0.45
    assert "spectrum" not in d  # None values excluded


def test_branch_lifecycle():
    branch = ExperimentBranch(
        branch_id="br_test",
        name="Test Branch",
        move_id="make_punchier",
        status="pending",
    )
    assert branch.status == "pending"
    branch.status = "evaluated"
    branch.score = 0.72
    d = branch.to_dict()
    assert d["score"] == 0.72
    assert d["status"] == "evaluated"


def test_experiment_set_ranking():
    exp = ExperimentSet(
        experiment_id="exp_test",
        request_text="test",
        branches=[
            ExperimentBranch(branch_id="b1", name="B1", move_id="a", status="evaluated", score=0.5),
            ExperimentBranch(branch_id="b2", name="B2", move_id="b", status="evaluated", score=0.8),
            ExperimentBranch(branch_id="b3", name="B3", move_id="c", status="pending", score=0.0),
        ],
    )
    ranked = exp.ranked_branches()
    assert len(ranked) == 2  # Only evaluated branches
    assert ranked[0].branch_id == "b2"  # Highest score first
    assert ranked[1].branch_id == "b1"


def test_experiment_to_dict():
    exp = ExperimentSet(
        experiment_id="exp_test",
        request_text="make it punchier",
        branches=[
            ExperimentBranch(branch_id="b1", name="B1", move_id="make_punchier"),
        ],
    )
    d = exp.to_dict()
    assert d["branch_count"] == 1
    assert d["status"] == "open"
    assert "ranking" in d


# ── Engine tests ─────────────────────────────────────────────────────────────

def test_create_experiment():
    exp = create_experiment(
        request_text="test experiment",
        move_ids=["make_punchier", "widen_stereo"],
    )
    assert exp.branch_count == 2
    assert exp.status == "open"
    assert all(b.status == "pending" for b in exp.branches)
    assert exp.branches[0].move_id == "make_punchier"
    assert exp.branches[1].move_id == "widen_stereo"


def test_get_experiment():
    exp = create_experiment(
        request_text="retrieve test",
        move_ids=["make_punchier"],
    )
    retrieved = get_experiment(exp.experiment_id)
    assert retrieved is not None
    assert retrieved.experiment_id == exp.experiment_id


def test_list_experiments():
    # Should have at least the ones we created above
    exps = list_experiments()
    assert len(exps) >= 1


def test_run_branch_with_mock():
    """Test branch execution with mock Ableton connection."""
    branch = ExperimentBranch(
        branch_id="br_mock",
        name="Mock Branch",
        move_id="make_punchier",
        status="pending",
    )

    # Mock Ableton that tracks calls
    class MockAbleton:
        def __init__(self):
            self.calls = []
        def send_command(self, tool, params=None):
            self.calls.append((tool, params or {}))
            return {"ok": True}

    mock = MockAbleton()
    plan = {
        "steps": [
            {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.75}},
            {"tool": "set_track_volume", "params": {"track_index": 3, "volume": 0.25}},
        ],
        "step_count": 2,
    }

    def capture():
        return BranchSnapshot(rms=0.15, peak=0.45, timestamp_ms=1000)

    run_branch(branch, mock, plan, capture)

    assert branch.status == "evaluated"
    assert branch.before_snapshot is not None
    assert branch.after_snapshot is not None
    # Should have: 2 tool calls + 2 undos
    tool_calls = [c[0] for c in mock.calls]
    assert tool_calls.count("set_track_volume") == 2
    assert tool_calls.count("undo") == 2


def test_evaluate_branch():
    branch = ExperimentBranch(
        branch_id="br_eval",
        name="Eval Branch",
        move_id="test",
        status="evaluated",
        before_snapshot=BranchSnapshot(rms=0.15),
        after_snapshot=BranchSnapshot(rms=0.18),
    )

    def eval_fn(before, after):
        return {"score": 0.75, "keep_change": True}

    evaluate_branch(branch, eval_fn)
    assert branch.score == 0.75
    assert branch.evaluation["keep_change"] is True


def test_commit_branch_with_mock():
    exp = ExperimentSet(
        experiment_id="exp_commit",
        request_text="commit test",
        branches=[
            ExperimentBranch(
                branch_id="br_win",
                name="Winner",
                move_id="make_punchier",
                status="evaluated",
                score=0.8,
                compiled_plan={
                    "steps": [
                        {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.75}},
                    ],
                },
            ),
        ],
    )

    class MockAbleton:
        def send_command(self, tool, params=None):
            return {"ok": True}

    result = commit_branch(exp, "br_win", MockAbleton())
    assert result["committed"] is True
    assert result["score"] == 0.8
    assert exp.status == "committed"
    assert exp.winner_branch_id == "br_win"


def test_discard_experiment():
    exp = create_experiment(
        request_text="discard test",
        move_ids=["make_punchier"],
    )
    result = discard_experiment(exp.experiment_id)
    assert result["discarded"] is True
    assert exp.status == "discarded"
