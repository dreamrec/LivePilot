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
