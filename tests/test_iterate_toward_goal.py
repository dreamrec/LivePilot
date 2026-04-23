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


def test_iterate_exhausts_and_commits_best_when_threshold_never_met():
    from mcp_server.tools._agent_os_engine.iteration import iterate_toward_goal_engine

    create, run, commit, discard, committed, discarded = _make_fake_callbacks(
        run_results=[
            ("br_a", 0.50),
            ("br_b", 0.65),  # best
            ("br_c", 0.55),
        ],
    )

    result = iterate_toward_goal_engine(
        candidate_move_sets=[["m1"], ["m2"], ["m3"]],
        threshold=0.80,
        max_iterations=3,
        create_experiment_fn=create,
        run_experiment_fn=run,
        commit_fn=commit,
        discard_fn=discard,
        on_timeout="commit_best",
    )

    assert result.status == "exhausted"
    assert result.iterations_run == 3
    assert result.committed_branch_id == "br_b"
    assert result.final_score == 0.65
    assert committed == [("exp_iter_1", "br_b")]
    # exp_iter_0 was best-so-far at i=0 then superseded at i=1, so discarded
    # during iteration. exp_iter_2 was worse than best, so discarded immediately.
    # exp_iter_1 was the surviving best, committed at end — NOT discarded.
    assert "exp_iter_0" in discarded
    assert "exp_iter_2" in discarded
    assert "exp_iter_1" not in discarded


def test_iterate_discard_on_timeout_never_commits():
    from mcp_server.tools._agent_os_engine.iteration import iterate_toward_goal_engine

    create, run, commit, discard, committed, discarded = _make_fake_callbacks(
        run_results=[("br_a", 0.30), ("br_b", 0.40)],
    )

    result = iterate_toward_goal_engine(
        candidate_move_sets=[["m1"], ["m2"]],
        threshold=0.80,
        max_iterations=2,
        create_experiment_fn=create,
        run_experiment_fn=run,
        commit_fn=commit,
        discard_fn=discard,
        on_timeout="discard_on_timeout",
    )

    assert result.status == "timeout_no_commit"
    assert committed == []
    assert "exp_iter_0" in discarded
    assert "exp_iter_1" in discarded


def test_iterate_no_candidates():
    from mcp_server.tools._agent_os_engine.iteration import iterate_toward_goal_engine

    create, run, commit, discard, committed, _ = _make_fake_callbacks(run_results=[])

    result = iterate_toward_goal_engine(
        candidate_move_sets=[],
        threshold=0.50,
        max_iterations=3,
        create_experiment_fn=create,
        run_experiment_fn=run,
        commit_fn=commit,
        discard_fn=discard,
    )

    assert result.status == "no_candidates"
    assert result.iterations_run == 0
    assert committed == []


def test_iterate_run_returns_no_winner_counts_as_failed_iteration():
    """A branch that all failed/rejected returns (None, 0.0). Should not crash
    and should not commit."""
    from mcp_server.tools._agent_os_engine.iteration import iterate_toward_goal_engine

    create, run, commit, discard, committed, discarded = _make_fake_callbacks(
        run_results=[(None, 0.0), ("br_ok", 0.90)],
    )

    result = iterate_toward_goal_engine(
        candidate_move_sets=[["m1"], ["m2"]],
        threshold=0.70,
        max_iterations=2,
        create_experiment_fn=create,
        run_experiment_fn=run,
        commit_fn=commit,
        discard_fn=discard,
    )

    assert result.status == "committed"
    assert result.committed_branch_id == "br_ok"
    # First experiment (no winner) discarded; second (winner) NOT discarded.
    assert "exp_iter_0" in discarded
    assert "exp_iter_1" not in discarded


def test_iterate_max_iterations_caps_candidate_list():
    """max_iterations < len(candidate_move_sets) stops early."""
    from mcp_server.tools._agent_os_engine.iteration import iterate_toward_goal_engine

    create, run, commit, discard, committed, discarded = _make_fake_callbacks(
        run_results=[("br_a", 0.1), ("br_b", 0.2), ("br_c", 0.3), ("br_d", 0.9)],
    )

    result = iterate_toward_goal_engine(
        candidate_move_sets=[["m1"], ["m2"], ["m3"], ["m4"]],
        threshold=0.80,
        max_iterations=2,  # only first two candidates tried
        create_experiment_fn=create,
        run_experiment_fn=run,
        commit_fn=commit,
        discard_fn=discard,
        on_timeout="commit_best",
    )

    assert result.iterations_run == 2
    assert result.final_score == 0.2  # br_b, best of the two tried
    assert result.committed_branch_id == "br_b"


def test_iterate_async_variant_awaits_coroutine_callbacks():
    """Async variant awaits coroutine callbacks transparently."""
    import asyncio
    from mcp_server.tools._agent_os_engine.iteration import (
        iterate_toward_goal_engine_async,
    )

    committed = []
    discarded = []
    iteration_idx = [0]

    async def async_create(move_ids):
        return f"exp_async_{iteration_idx[0]}"

    async def async_run(exp_id):
        idx = iteration_idx[0]
        iteration_idx[0] += 1
        results = [("br_x", 0.4), ("br_y", 0.85)]
        return results[idx] if idx < len(results) else (None, 0.0)

    async def async_commit(exp_id, branch_id):
        committed.append((exp_id, branch_id))
        return {"ok": True}

    async def async_discard(exp_id):
        discarded.append(exp_id)
        return {"ok": True}

    result = asyncio.run(iterate_toward_goal_engine_async(
        candidate_move_sets=[["m1"], ["m2"]],
        threshold=0.80,
        max_iterations=2,
        create_experiment_fn=async_create,
        run_experiment_fn=async_run,
        commit_fn=async_commit,
        discard_fn=async_discard,
    ))

    assert result.status == "committed"
    assert result.committed_branch_id == "br_y"
    assert committed == [("exp_async_1", "br_y")]
    assert "exp_async_0" in discarded


# ── Commit-result inspection (P1#1 fix, v1.17.3) ───────────────────────
#
# Prior behavior: _iterate_async_core awaited commit_fn and dropped the
# return value on the floor, then unconditionally returned
# status="committed". If the underlying experiment commit failed (zero
# steps applied) or partially succeeded, the iteration result lied.
# These tests reproduce the bug and lock the truthful shape.


def _make_scripted_commit_callbacks(run_results, commit_results):
    """Like _make_fake_callbacks but commit_fn pulls from a scripted list.

    commit_results[i] is the dict returned by the i-th commit_fn call.
    Allows simulating {committed: False}, {status: "committed_with_errors"},
    {steps_failed: N} etc. in deterministic order.
    """
    committed_calls = []
    discarded = []
    iteration_idx = [0]
    commit_idx = [0]

    def fake_create(seeds):
        return f"exp_iter_{iteration_idx[0]}"

    def fake_run(experiment_id):
        idx = iteration_idx[0]
        iteration_idx[0] += 1
        if idx >= len(run_results):
            return None, 0.0
        return run_results[idx]

    def fake_commit(experiment_id, branch_id):
        idx = commit_idx[0]
        commit_idx[0] += 1
        committed_calls.append((experiment_id, branch_id))
        if idx >= len(commit_results):
            return {"ok": True, "steps_failed": 0, "steps_ok": 1}
        return commit_results[idx]

    def fake_discard(experiment_id):
        discarded.append(experiment_id)
        return {"ok": True}

    return (
        fake_create, fake_run, fake_commit, fake_discard,
        committed_calls, discarded,
    )


def test_iterate_reports_commit_failed_when_commit_returns_committed_false():
    """Commit returning {committed: False, error: ...} must not be reported
    as status='committed'. Iteration must surface the commit failure."""
    from mcp_server.tools._agent_os_engine.iteration import iterate_toward_goal_engine

    create, run, commit, discard, committed_calls, _ = _make_scripted_commit_callbacks(
        run_results=[("br_win", 0.85)],
        commit_results=[
            {"committed": False, "error": "No steps executed successfully"},
        ],
    )

    result = iterate_toward_goal_engine(
        candidate_move_sets=[["make_punchier"]],
        threshold=0.70,
        max_iterations=1,
        create_experiment_fn=create,
        run_experiment_fn=run,
        commit_fn=commit,
        discard_fn=discard,
        on_timeout="commit_best",
    )

    assert result.status == "commit_failed", (
        f"commit returned committed=False; iteration must not claim success. "
        f"Got status={result.status!r}"
    )
    assert result.committed_experiment_id is None
    assert result.committed_branch_id is None
    # commit_fn was called exactly once
    assert len(committed_calls) == 1
    # The commit payload is surfaced on the result for inspection
    assert "commit_result" in result.to_dict()
    assert result.to_dict()["commit_result"]["committed"] is False


def test_iterate_reports_committed_with_errors_on_partial_commit():
    """Commit returning status='committed_with_errors' with steps_failed > 0
    must NOT be reported as plain 'committed'. The partial failure must
    be surfaced on the IterationResult."""
    from mcp_server.tools._agent_os_engine.iteration import iterate_toward_goal_engine

    create, run, commit, discard, committed_calls, _ = _make_scripted_commit_callbacks(
        run_results=[("br_win", 0.85)],
        commit_results=[
            {
                "committed": True,
                "status": "committed_with_errors",
                "steps_ok": 2,
                "steps_failed": 1,
            },
        ],
    )

    result = iterate_toward_goal_engine(
        candidate_move_sets=[["make_punchier"]],
        threshold=0.70,
        max_iterations=1,
        create_experiment_fn=create,
        run_experiment_fn=run,
        commit_fn=commit,
        discard_fn=discard,
        on_timeout="commit_best",
    )

    assert result.status == "committed_with_errors", (
        f"Partial commit must not be reported as plain 'committed'. "
        f"Got status={result.status!r}"
    )
    assert result.committed_experiment_id == "exp_iter_0"
    assert result.committed_branch_id == "br_win"
    assert result.to_dict()["commit_result"]["steps_failed"] == 1


def test_iterate_commit_best_path_also_inspects_commit_result():
    """Same inspection discipline on the timeout commit-best path."""
    from mcp_server.tools._agent_os_engine.iteration import iterate_toward_goal_engine

    # Below threshold → exhaustion triggers commit_best.
    # Commit fails → must not claim 'exhausted' success.
    create, run, commit, discard, committed_calls, _ = _make_scripted_commit_callbacks(
        run_results=[("br_a", 0.50), ("br_b", 0.60)],  # best=br_b at 0.60
        commit_results=[
            {"committed": False, "error": "all steps failed"},
        ],
    )

    result = iterate_toward_goal_engine(
        candidate_move_sets=[["m1"], ["m2"]],
        threshold=0.80,
        max_iterations=2,
        create_experiment_fn=create,
        run_experiment_fn=run,
        commit_fn=commit,
        discard_fn=discard,
        on_timeout="commit_best",
    )

    assert result.status == "commit_failed", (
        f"timeout commit_best with failing commit must report commit_failed. "
        f"Got {result.status!r}"
    )
    assert result.committed_experiment_id is None
    assert result.committed_branch_id is None


def test_iterate_plain_committed_still_reported_for_clean_success():
    """Back-compat: when commit returns {ok: True, steps_failed: 0, steps_ok: N>0}
    (or the legacy fake shape {ok: True, steps_failed: 0}), status='committed'
    must still work — we're tightening failure detection, not breaking success."""
    from mcp_server.tools._agent_os_engine.iteration import iterate_toward_goal_engine

    create, run, commit, discard, committed_calls, _ = _make_scripted_commit_callbacks(
        run_results=[("br_win", 0.85)],
        commit_results=[
            {"ok": True, "committed": True, "steps_failed": 0, "steps_ok": 3},
        ],
    )

    result = iterate_toward_goal_engine(
        candidate_move_sets=[["make_punchier"]],
        threshold=0.70,
        max_iterations=1,
        create_experiment_fn=create,
        run_experiment_fn=run,
        commit_fn=commit,
        discard_fn=discard,
        on_timeout="commit_best",
    )

    assert result.status == "committed"
    assert result.committed_branch_id == "br_win"


# ── MCP tool registration smoke ────────────────────────────────────────

def test_iterate_toward_goal_tool_registered():
    import asyncio
    from mcp_server.server import mcp
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert "iterate_toward_goal" in names
