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
      - "committed" — a winner hit threshold AND commit succeeded (steps_ok>0, steps_failed==0)
      - "committed_with_errors" — commit applied some steps but not all (steps_ok>0 AND steps_failed>0)
      - "commit_failed" — commit was attempted but applied zero steps (steps_ok==0 OR committed:false)
      - "exhausted" — max_iterations reached, committed best-so-far cleanly (on_timeout=commit_best)
      - "timeout_no_commit" — max_iterations reached, no commit (on_timeout=discard_on_timeout)
      - "no_candidates" — caller provided empty candidate_move_sets

    commit_result: the raw dict returned by commit_fn, surfaced for caller
      inspection. Populated whenever commit_fn was called (regardless of
      whether the commit succeeded). None when no commit was attempted.
    """
    status: str
    iterations_run: int
    committed_experiment_id: Optional[str]
    committed_branch_id: Optional[str]
    final_score: float
    steps: list[IterationStep] = field(default_factory=list)
    reason: str = ""
    commit_result: Optional[dict] = None

    def to_dict(self) -> dict:
        d = {
            "status": self.status,
            "iterations_run": self.iterations_run,
            "committed_experiment_id": self.committed_experiment_id,
            "committed_branch_id": self.committed_branch_id,
            "final_score": self.final_score,
            "steps": [s.to_dict() for s in self.steps],
            "reason": self.reason,
        }
        if self.commit_result is not None:
            d["commit_result"] = self.commit_result
        return d


def _classify_commit_result(result: Any) -> str:
    """Inspect a commit_fn return value and classify into an IterationResult
    status. Conservative: any failure signal produces 'commit_failed', any
    partial signal produces 'committed_with_errors', only clean success
    produces 'committed'.

    Known failure signals:
      - {"committed": False, ...}
      - {"status": "failed", ...}
      - {"ok": False, ...}
      - {"error": ...} present at top level (unless committed explicitly True)
      - {"steps_ok": 0, ...}

    Known partial signals:
      - {"status": "committed_with_errors", ...}
      - {"steps_failed": N, "steps_ok": M>0} where N>0
    """
    if not isinstance(result, dict):
        # Non-dict returns: trust the caller but don't confirm partial/error.
        return "committed"

    # Hard failure signals
    if result.get("committed") is False:
        return "commit_failed"
    if result.get("ok") is False:
        return "commit_failed"
    if result.get("status") == "failed":
        return "commit_failed"
    steps_ok = result.get("steps_ok")
    steps_failed = result.get("steps_failed")
    if steps_ok == 0 and (steps_failed is None or steps_failed > 0):
        return "commit_failed"

    # Partial success
    if result.get("status") == "committed_with_errors":
        return "committed_with_errors"
    if (
        isinstance(steps_failed, int) and steps_failed > 0
        and isinstance(steps_ok, int) and steps_ok > 0
    ):
        return "committed_with_errors"

    # Otherwise: clean success
    return "committed"


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
            commit_payload = commit_fn(exp_id, winner_branch_id)
            commit_status = _classify_commit_result(commit_payload)
            commit_dict = commit_payload if isinstance(commit_payload, dict) else None
            if commit_status == "commit_failed":
                return IterationResult(
                    status="commit_failed",
                    iterations_run=i + 1,
                    committed_experiment_id=None,
                    committed_branch_id=None,
                    final_score=winner_score,
                    steps=steps,
                    reason=(
                        f"threshold {threshold} met on iteration {i} but commit "
                        f"applied no steps; see commit_result"
                    ),
                    commit_result=commit_dict,
                )
            return IterationResult(
                status=commit_status,  # "committed" or "committed_with_errors"
                iterations_run=i + 1,
                committed_experiment_id=exp_id,
                committed_branch_id=winner_branch_id,
                final_score=winner_score,
                steps=steps,
                reason=(
                    f"threshold {threshold} met on iteration {i}"
                    if commit_status == "committed"
                    else f"threshold {threshold} met on iteration {i}; "
                         f"commit applied with partial failures (see commit_result)"
                ),
                commit_result=commit_dict,
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
        commit_payload = commit_fn(best_exp_id, best_branch_id)
        commit_status = _classify_commit_result(commit_payload)
        commit_dict = commit_payload if isinstance(commit_payload, dict) else None
        if commit_status == "commit_failed":
            return IterationResult(
                status="commit_failed",
                iterations_run=n,
                committed_experiment_id=None,
                committed_branch_id=None,
                final_score=best_score,
                steps=steps,
                reason=(
                    f"max_iterations={n} reached; commit_best selected best-so-far "
                    f"(score {best_score}) but the commit applied no steps; "
                    f"see commit_result"
                ),
                commit_result=commit_dict,
            )
        return IterationResult(
            status="exhausted" if commit_status == "committed" else "committed_with_errors",
            iterations_run=n,
            committed_experiment_id=best_exp_id,
            committed_branch_id=best_branch_id,
            final_score=best_score,
            steps=steps,
            reason=(
                f"max_iterations={n} reached, threshold {threshold} never met; "
                f"committed best-so-far with score {best_score}"
                + ("" if commit_status == "committed" else " (partial commit — see commit_result)")
            ),
            commit_result=commit_dict,
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
            commit_payload = await _maybe_await(commit_fn(exp_id, winner_branch_id))
            commit_status = _classify_commit_result(commit_payload)
            commit_dict = commit_payload if isinstance(commit_payload, dict) else None
            if commit_status == "commit_failed":
                return IterationResult(
                    status="commit_failed",
                    iterations_run=i + 1,
                    committed_experiment_id=None,
                    committed_branch_id=None,
                    final_score=winner_score,
                    steps=steps,
                    reason=(
                        f"threshold {threshold} met on iteration {i} but commit "
                        f"applied no steps; see commit_result"
                    ),
                    commit_result=commit_dict,
                )
            return IterationResult(
                status=commit_status,
                iterations_run=i + 1,
                committed_experiment_id=exp_id,
                committed_branch_id=winner_branch_id,
                final_score=winner_score,
                steps=steps,
                reason=(
                    f"threshold {threshold} met on iteration {i}"
                    if commit_status == "committed"
                    else f"threshold {threshold} met on iteration {i}; "
                         f"commit applied with partial failures (see commit_result)"
                ),
                commit_result=commit_dict,
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
        commit_payload = await _maybe_await(commit_fn(best_exp_id, best_branch_id))
        commit_status = _classify_commit_result(commit_payload)
        commit_dict = commit_payload if isinstance(commit_payload, dict) else None
        if commit_status == "commit_failed":
            return IterationResult(
                status="commit_failed",
                iterations_run=n,
                committed_experiment_id=None,
                committed_branch_id=None,
                final_score=best_score,
                steps=steps,
                reason=(
                    f"max_iterations={n} reached; commit_best selected best-so-far "
                    f"(score {best_score}) but the commit applied no steps; "
                    f"see commit_result"
                ),
                commit_result=commit_dict,
            )
        return IterationResult(
            status="exhausted" if commit_status == "committed" else "committed_with_errors",
            iterations_run=n,
            committed_experiment_id=best_exp_id,
            committed_branch_id=best_branch_id,
            final_score=best_score,
            steps=steps,
            reason=(
                f"max_iterations={n} reached, threshold {threshold} never met; "
                f"committed best-so-far with score {best_score}"
                + ("" if commit_status == "committed" else " (partial commit — see commit_result)")
            ),
            commit_result=commit_dict,
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
