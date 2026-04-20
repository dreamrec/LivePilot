"""Tests for the experiment engine — branch-based creative search."""

import pytest

from mcp_server.branches import (
    BranchSeed, seed_from_move_id, freeform_seed, analytical_seed,
)
from mcp_server.experiment.models import (
    ExperimentSet, ExperimentBranch, BranchSnapshot,
)
from mcp_server.experiment.engine import (
    create_experiment, create_experiment_from_seeds,
    get_experiment, list_experiments,
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


# ── PR3 — branch-native (seed-based) experiment creation ────────────────

class TestExperimentBranchFromSeed:

    def test_from_semantic_move_seed(self):
        seed = seed_from_move_id("make_punchier")
        branch = ExperimentBranch.from_seed(
            seed=seed,
            branch_id="br_1",
        )
        assert branch.move_id == "make_punchier"  # mirrored from seed
        assert branch.seed is seed
        assert branch.status == "pending"
        assert branch.compiled_plan is None
        assert branch.name.startswith("Branch (semantic_move:")

    def test_from_freeform_seed_has_empty_move_id(self):
        seed = freeform_seed(
            seed_id="f_1",
            hypothesis="Audio-rate LFO into filter",
            source="synthesis",
        )
        branch = ExperimentBranch.from_seed(seed=seed, branch_id="br_2")
        assert branch.seed is seed
        assert branch.move_id == ""
        assert branch.name.startswith("Branch (synthesis:")

    def test_from_seed_accepts_precompiled_plan(self):
        seed = freeform_seed(seed_id="f_1", hypothesis="h")
        plan = {"steps": [{"tool": "set_track_volume"}], "step_count": 1, "summary": "q"}
        branch = ExperimentBranch.from_seed(
            seed=seed,
            branch_id="br_3",
            compiled_plan=plan,
        )
        assert branch.compiled_plan is plan

    def test_from_seed_custom_name(self):
        seed = seed_from_move_id("widen_pad")
        branch = ExperimentBranch.from_seed(
            seed=seed,
            branch_id="br_4",
            name="Custom Label",
        )
        assert branch.name == "Custom Label"

    def test_to_dict_surfaces_seed_and_source(self):
        seed = freeform_seed(
            seed_id="f_1",
            hypothesis="Modulate cutoff",
            source="synthesis",
        )
        branch = ExperimentBranch.from_seed(seed=seed, branch_id="br_5")
        d = branch.to_dict()
        assert d["branch_source"] == "synthesis"
        assert d["seed"]["hypothesis"] == "Modulate cutoff"
        assert d["analytical_only"] is True  # no plan ⇒ analytical

    def test_analytical_only_reflected_in_to_dict(self):
        seed = analytical_seed(seed_id="a_1", hypothesis="consider X")
        # Even with a plan, analytical_only seed flag wins.
        branch = ExperimentBranch.from_seed(
            seed=seed,
            branch_id="br_6",
            compiled_plan={"steps": [], "step_count": 0},
        )
        assert branch.to_dict()["analytical_only"] is True


class TestCreateExperimentFromSeeds:

    def test_basic_semantic_move_seeds(self):
        seeds = [
            seed_from_move_id("make_punchier"),
            seed_from_move_id("widen_stereo"),
        ]
        exp = create_experiment_from_seeds(
            request_text="creative_search",
            seeds=seeds,
        )
        assert exp.branch_count == 2
        assert exp.branches[0].move_id == "make_punchier"
        assert exp.branches[1].move_id == "widen_stereo"
        assert all(b.seed is not None for b in exp.branches)

    def test_freeform_seeds_without_plans(self):
        seeds = [
            freeform_seed(seed_id="a", hypothesis="Boost mids"),
            freeform_seed(seed_id="b", hypothesis="Widen top end"),
        ]
        exp = create_experiment_from_seeds(
            request_text="freeform test",
            seeds=seeds,
        )
        assert exp.branch_count == 2
        assert all(b.move_id == "" for b in exp.branches)
        assert all(b.compiled_plan is None for b in exp.branches)

    def test_compiled_plans_attach_by_position(self):
        seeds = [
            freeform_seed(seed_id="a", hypothesis="h1"),
            freeform_seed(seed_id="b", hypothesis="h2"),
        ]
        plans = [
            {"steps": [{"tool": "set_track_volume"}], "step_count": 1},
            None,  # second seed uses no plan
        ]
        exp = create_experiment_from_seeds(
            request_text="mixed compile",
            seeds=seeds,
            compiled_plans=plans,
        )
        assert exp.branches[0].compiled_plan == plans[0]
        assert exp.branches[1].compiled_plan is None

    def test_compiled_plans_length_mismatch_raises(self):
        seeds = [freeform_seed(seed_id="a", hypothesis="h")]
        with pytest.raises(ValueError, match="compiled_plans length"):
            create_experiment_from_seeds(
                request_text="bad",
                seeds=seeds,
                compiled_plans=[{}, {}],
            )


class TestLegacyCreateExperimentStillWorks:
    """PR3 keeps the legacy create_experiment(move_ids=...) path identical."""

    def test_branches_carry_seed_after_delegation(self):
        """Legacy path now internally builds seeds; branches carry them for
        downstream branch-native consumers."""
        exp = create_experiment(
            request_text="legacy",
            move_ids=["make_punchier"],
        )
        b = exp.branches[0]
        assert b.move_id == "make_punchier"  # legacy callers keep reading this
        assert b.seed is not None
        assert b.seed.source == "semantic_move"
        assert b.seed.move_id == "make_punchier"

    def test_existing_test_pattern_still_works(self):
        # Constructor without move_id — used to be a TypeError; now defaults "".
        # This lets producers build branches without mirroring move_id by hand.
        branch = ExperimentBranch(branch_id="b", name="n")
        assert branch.move_id == ""
        assert branch.seed is None

    def test_positional_move_id_still_accepted(self):
        # Pre-PR3 test pattern used move_id positionally — verify it still
        # works so we don't break anything outside the test suite.
        branch = ExperimentBranch("b", "n", "make_punchier")
        assert branch.move_id == "make_punchier"
