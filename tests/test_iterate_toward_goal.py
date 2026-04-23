"""Tests for iterate_toward_goal — the outer evaluation loop."""

import pytest

from mcp_server.tools._agent_os_engine.iteration import (
    IterationResult,
    IterationStep,
)


def test_iteration_step_to_dict():
    step = IterationStep(
        iteration=0,
        experiment_id="exp_abc",
        winner_branch_id="br_123",
        winner_score=0.72,
        threshold_met=False,
        note="below threshold",
    )
    d = step.to_dict()
    assert d["iteration"] == 0
    assert d["winner_score"] == 0.72
    assert d["threshold_met"] is False


def test_iteration_result_to_dict_success():
    result = IterationResult(
        status="committed",
        iterations_run=2,
        committed_experiment_id="exp_abc",
        committed_branch_id="br_123",
        final_score=0.85,
        steps=[],
        reason="threshold met on iteration 1",
    )
    d = result.to_dict()
    assert d["status"] == "committed"
    assert d["final_score"] == 0.85
    assert d["committed_branch_id"] == "br_123"


def test_iteration_result_to_dict_exhausted():
    result = IterationResult(
        status="exhausted",
        iterations_run=3,
        committed_experiment_id=None,
        committed_branch_id=None,
        final_score=0.55,
        steps=[],
        reason="max_iterations reached, best score below threshold",
    )
    d = result.to_dict()
    assert d["status"] == "exhausted"
    assert d["committed_branch_id"] is None


# ── Engine tests with injected fakes ───────────────────────────────────

def _make_fake_callbacks(
    run_results,  # [(branch_id, score), ...] per iteration
    committed=None,
):
    """Build fake create/run/commit/discard callbacks driven by a script.

    run_results[i] is the (winner_branch_id, winner_score) to return on the
    i-th iteration. `committed` is a shared list the commit callback appends
    (experiment_id, branch_id) to when called.
    """
    committed = committed if committed is not None else []
    discarded = []
    iteration_idx = [0]

    def fake_create(seeds):
        exp_id = f"exp_iter_{iteration_idx[0]}"
        return exp_id

    def fake_run(experiment_id):
        idx = iteration_idx[0]
        iteration_idx[0] += 1
        if idx >= len(run_results):
            return None, 0.0
        return run_results[idx]

    def fake_commit(experiment_id, branch_id):
        committed.append((experiment_id, branch_id))
        return {"ok": True, "steps_failed": 0}

    def fake_discard(experiment_id):
        discarded.append(experiment_id)
        return {"ok": True}

    return fake_create, fake_run, fake_commit, fake_discard, committed, discarded


def test_iterate_commits_when_threshold_met_on_first_iteration():
    from mcp_server.tools._agent_os_engine.iteration import iterate_toward_goal_engine

    create, run, commit, discard, committed, discarded = _make_fake_callbacks(
        run_results=[("br_win", 0.85)],
    )

    result = iterate_toward_goal_engine(
        candidate_move_sets=[["make_punchier", "widen_stereo"]],
        threshold=0.70,
        max_iterations=3,
        create_experiment_fn=create,
        run_experiment_fn=run,
        commit_fn=commit,
        discard_fn=discard,
        on_timeout="commit_best",
    )

    assert result.status == "committed"
    assert result.iterations_run == 1
    assert result.committed_branch_id == "br_win"
    assert result.final_score == 0.85
    assert committed == [("exp_iter_0", "br_win")]
    assert discarded == []
    assert len(result.steps) == 1
    assert result.steps[0].threshold_met is True
