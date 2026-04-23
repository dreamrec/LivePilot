"""Iteration engine — closes the evaluation loop by running experiments
repeatedly against a compiled GoalVector until threshold or timeout.

Pure-python: takes callables for experiment create/run/commit/discard so
tests can substitute in-memory fakes without an Ableton connection. The
callables may be sync or async — the engine uses `iterate_toward_goal_engine`
(sync) for the former and `iterate_toward_goal_engine_async` for the latter.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, Union


@dataclass
class IterationStep:
    """One iteration of the outer loop — one experiment's worth of work."""
    iteration: int
    experiment_id: str
    winner_branch_id: Optional[str]
    winner_score: float
    threshold_met: bool
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "experiment_id": self.experiment_id,
            "winner_branch_id": self.winner_branch_id,
            "winner_score": self.winner_score,
            "threshold_met": self.threshold_met,
            "note": self.note,
        }


@dataclass
class IterationResult:
    """Final result of iterate_toward_goal.

    status:
      - "committed" — a winner hit threshold, was committed permanently
      - "exhausted" — max_iterations reached, committed best-so-far (on_timeout=commit_best)
      - "timeout_no_commit" — max_iterations reached, no commit (on_timeout=discard_on_timeout)
      - "no_candidates" — caller provided empty candidate_move_sets
      - "error" — unrecoverable error; see reason
    """
    status: str
    iterations_run: int
    committed_experiment_id: Optional[str]
    committed_branch_id: Optional[str]
    final_score: float
    steps: list[IterationStep] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "iterations_run": self.iterations_run,
            "committed_experiment_id": self.committed_experiment_id,
            "committed_branch_id": self.committed_branch_id,
            "final_score": self.final_score,
            "steps": [s.to_dict() for s in self.steps],
            "reason": self.reason,
        }
