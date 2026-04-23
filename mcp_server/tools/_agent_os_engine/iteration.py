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


def iterate_toward_goal_engine(
    candidate_move_sets: list,
    threshold: float,
    max_iterations: int,
    create_experiment_fn: Callable[[list], str],
    run_experiment_fn: Callable[[str], Any],
    commit_fn: Callable[[str, str], dict],
    discard_fn: Callable[[str], dict],
    on_timeout: str = "commit_best",
) -> IterationResult:
    """Run experiments repeatedly until winner_score >= threshold or timeout.

    Pure orchestration — all I/O happens through the injected callbacks. The
    run/commit/discard callbacks may be sync or async; coroutines will be
    awaited when reached. This keeps the engine reusable by both the
    sync test suite and the async MCP tool wrapper.

    See module docstring for full contract. Invariant: never issues raw
    undo calls — per-branch undo is the responsibility of run_experiment_fn.
    This loop only chooses commit vs discard.
    """
    import asyncio

    async def _as_async():
        return await _iterate_async_core(
            candidate_move_sets=candidate_move_sets,
            threshold=threshold,
            max_iterations=max_iterations,
            create_experiment_fn=create_experiment_fn,
            run_experiment_fn=run_experiment_fn,
            commit_fn=commit_fn,
            discard_fn=discard_fn,
            on_timeout=on_timeout,
        )

    # If any callback is a coroutine function, run via asyncio. Otherwise
    # execute the sync path directly to avoid event-loop overhead in tests.
    any_async = any(
        inspect.iscoroutinefunction(fn)
        for fn in (create_experiment_fn, run_experiment_fn, commit_fn, discard_fn)
    )
    if any_async:
        return asyncio.run(_as_async())

    return _iterate_sync_core(
        candidate_move_sets=candidate_move_sets,
        threshold=threshold,
        max_iterations=max_iterations,
        create_experiment_fn=create_experiment_fn,
        run_experiment_fn=run_experiment_fn,
        commit_fn=commit_fn,
        discard_fn=discard_fn,
        on_timeout=on_timeout,
    )


async def iterate_toward_goal_engine_async(
    candidate_move_sets: list,
    threshold: float,
    max_iterations: int,
    create_experiment_fn: Callable[[list], Any],
    run_experiment_fn: Callable[[str], Any],
    commit_fn: Callable[[str, str], Any],
    discard_fn: Callable[[str], Any],
    on_timeout: str = "commit_best",
) -> IterationResult:
    """Async variant — used by the MCP tool wrapper which has async callbacks."""
    return await _iterate_async_core(
        candidate_move_sets=candidate_move_sets,
        threshold=threshold,
        max_iterations=max_iterations,
        create_experiment_fn=create_experiment_fn,
        run_experiment_fn=run_experiment_fn,
        commit_fn=commit_fn,
        discard_fn=discard_fn,
        on_timeout=on_timeout,
    )


# ── Internal cores ─────────────────────────────────────────────────────────

def _iterate_sync_core(
    candidate_move_sets,
    threshold,
    max_iterations,
    create_experiment_fn,
    run_experiment_fn,
    commit_fn,
    discard_fn,
    on_timeout,
) -> IterationResult:
    if not candidate_move_sets:
        return IterationResult(
            status="no_candidates",
            iterations_run=0,
            committed_experiment_id=None,
            committed_branch_id=None,
            final_score=0.0,
            reason="candidate_move_sets is empty",
        )

    steps: list[IterationStep] = []
    best_score = -1.0
    best_exp_id: Optional[str] = None
    best_branch_id: Optional[str] = None
    n = min(max_iterations, len(candidate_move_sets))

    for i in range(n):
        move_ids = candidate_move_sets[i]
        exp_id = create_experiment_fn(move_ids)
        winner_branch_id, winner_score = run_experiment_fn(exp_id)

        met = winner_score >= threshold and winner_branch_id is not None
        steps.append(IterationStep(
            iteration=i,
            experiment_id=exp_id,
            winner_branch_id=winner_branch_id,
            winner_score=winner_score,
            threshold_met=met,
            note=(
                f"committed on iteration {i}" if met
                else f"below threshold (need {threshold}, got {winner_score})"
            ),
        ))

        if met:
            # Discard any prior best-so-far before committing the new winner —
            # otherwise the old non-winning experiment leaks in the store.
            if best_exp_id is not None and best_exp_id != exp_id:
                discard_fn(best_exp_id)
            commit_fn(exp_id, winner_branch_id)
            return IterationResult(
                status="committed",
                iterations_run=i + 1,
                committed_experiment_id=exp_id,
                committed_branch_id=winner_branch_id,
                final_score=winner_score,
                steps=steps,
                reason=f"threshold {threshold} met on iteration {i}",
            )

        if winner_branch_id is not None and winner_score > best_score:
            # Supersede previous best-so-far. It's now stale, free the slot.
            if best_exp_id is not None:
                discard_fn(best_exp_id)
            best_score = winner_score
            best_exp_id = exp_id
            best_branch_id = winner_branch_id
        else:
            discard_fn(exp_id)

    if on_timeout == "commit_best" and best_exp_id and best_branch_id:
        commit_fn(best_exp_id, best_branch_id)
        return IterationResult(
            status="exhausted",
            iterations_run=n,
            committed_experiment_id=best_exp_id,
            committed_branch_id=best_branch_id,
            final_score=best_score,
            steps=steps,
            reason=(
                f"max_iterations={n} reached, threshold {threshold} never met; "
                f"committed best-so-far with score {best_score}"
            ),
        )

    if best_exp_id:
        discard_fn(best_exp_id)
    return IterationResult(
        status="timeout_no_commit",
        iterations_run=n,
        committed_experiment_id=None,
        committed_branch_id=None,
        final_score=max(best_score, 0.0),
        steps=steps,
        reason=f"max_iterations={n} reached, policy={on_timeout}, no commit issued",
    )


async def _iterate_async_core(
    candidate_move_sets,
    threshold,
    max_iterations,
    create_experiment_fn,
    run_experiment_fn,
    commit_fn,
    discard_fn,
    on_timeout,
) -> IterationResult:
    if not candidate_move_sets:
        return IterationResult(
            status="no_candidates",
            iterations_run=0,
            committed_experiment_id=None,
            committed_branch_id=None,
            final_score=0.0,
            reason="candidate_move_sets is empty",
        )

    async def _maybe_await(value):
        if inspect.isawaitable(value):
            return await value
        return value

    steps: list[IterationStep] = []
    best_score = -1.0
    best_exp_id: Optional[str] = None
    best_branch_id: Optional[str] = None
    n = min(max_iterations, len(candidate_move_sets))

    for i in range(n):
        move_ids = candidate_move_sets[i]
        exp_id = await _maybe_await(create_experiment_fn(move_ids))
        winner_branch_id, winner_score = await _maybe_await(run_experiment_fn(exp_id))

        met = winner_score >= threshold and winner_branch_id is not None
        steps.append(IterationStep(
            iteration=i,
            experiment_id=exp_id,
            winner_branch_id=winner_branch_id,
            winner_score=winner_score,
            threshold_met=met,
            note=(
                f"committed on iteration {i}" if met
                else f"below threshold (need {threshold}, got {winner_score})"
            ),
        ))

        if met:
            if best_exp_id is not None and best_exp_id != exp_id:
                await _maybe_await(discard_fn(best_exp_id))
            await _maybe_await(commit_fn(exp_id, winner_branch_id))
            return IterationResult(
                status="committed",
                iterations_run=i + 1,
                committed_experiment_id=exp_id,
                committed_branch_id=winner_branch_id,
                final_score=winner_score,
                steps=steps,
                reason=f"threshold {threshold} met on iteration {i}",
            )

        if winner_branch_id is not None and winner_score > best_score:
            if best_exp_id is not None:
                await _maybe_await(discard_fn(best_exp_id))
            best_score = winner_score
            best_exp_id = exp_id
            best_branch_id = winner_branch_id
        else:
            await _maybe_await(discard_fn(exp_id))

    if on_timeout == "commit_best" and best_exp_id and best_branch_id:
        await _maybe_await(commit_fn(best_exp_id, best_branch_id))
        return IterationResult(
            status="exhausted",
            iterations_run=n,
            committed_experiment_id=best_exp_id,
            committed_branch_id=best_branch_id,
            final_score=best_score,
            steps=steps,
            reason=(
                f"max_iterations={n} reached, threshold {threshold} never met; "
                f"committed best-so-far with score {best_score}"
            ),
        )

    if best_exp_id:
        await _maybe_await(discard_fn(best_exp_id))
    return IterationResult(
        status="timeout_no_commit",
        iterations_run=n,
        committed_experiment_id=None,
        committed_branch_id=None,
        final_score=max(best_score, 0.0),
        steps=steps,
        reason=f"max_iterations={n} reached, policy={on_timeout}, no commit issued",
    )
