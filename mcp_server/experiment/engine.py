"""Experiment engine — runs branches sequentially using Ableton's undo system.

The engine manages the lifecycle: create branches from semantic moves,
run each one (apply → capture → undo), evaluate, rank, and commit the winner.

Critical constraint: Ableton has linear undo. Experiments MUST run sequentially:
  1. Capture before state
  2. Apply semantic move (compiled plan)
  3. Capture after state
  4. Undo all changes back to the checkpoint
  5. Repeat for next branch
  6. When winner is chosen, re-apply that branch's moves permanently

All I/O happens through the AbletonConnection passed to run methods.
The engine itself is pure orchestration logic.
"""

from __future__ import annotations

import hashlib
import time
from typing import Optional

from .models import ExperimentSet, ExperimentBranch, BranchSnapshot
from ..branches import BranchSeed, seed_from_move_id
import logging

logger = logging.getLogger(__name__)

# ── In-memory experiment store ───────────────────────────────────────────────

_EXPERIMENTS: dict[str, ExperimentSet] = {}


def _gen_id(prefix: str, seed: str) -> str:
    """Generate a short deterministic ID."""
    h = hashlib.sha256(f"{prefix}:{seed}:{time.time()}".encode()).hexdigest()[:8]
    return f"{prefix}_{h}"

# ── Create experiments ───────────────────────────────────────────────────────


def create_experiment_from_seeds(
    request_text: str,
    seeds: list[BranchSeed],
    kernel_id: str = "",
    compiled_plans: Optional[list] = None,
) -> ExperimentSet:
    """Create an experiment set from BranchSeeds (PR3 canonical path).

    seeds: one BranchSeed per desired branch. Can be any source — semantic_move,
      freeform, synthesis, composer, technique.
    compiled_plans: optional parallel list; when entry ``i`` is a dict, that
      plan is attached to branch ``i`` (used by freeform / synthesis / composer
      producers that do their own compilation). When None or entry is None,
      run_experiment compiles from the seed at run time — which only succeeds
      for source="semantic_move" seeds.

    Does NOT execute anything — call run_experiment() to trial each branch.
    """
    if compiled_plans is not None and len(compiled_plans) != len(seeds):
        raise ValueError(
            f"compiled_plans length ({len(compiled_plans)}) must match "
            f"seeds length ({len(seeds)})"
        )

    exp_id = _gen_id("exp", request_text)
    now = int(time.time() * 1000)

    branches = []
    for i, seed in enumerate(seeds):
        plan = compiled_plans[i] if compiled_plans else None
        display = seed.move_id or (seed.hypothesis[:32] if seed.hypothesis else seed.seed_id)
        branch = ExperimentBranch.from_seed(
            seed=seed,
            branch_id=_gen_id("br", f"{seed.seed_id}_{i}"),
            name=f"Branch {i+1}: {display}",
            source_kernel_id=kernel_id,
            compiled_plan=plan,
            created_at_ms=now,
        )
        branches.append(branch)

    experiment = ExperimentSet(
        experiment_id=exp_id,
        request_text=request_text,
        branches=branches,
        status="open",
        created_at_ms=now,
    )

    _EXPERIMENTS[exp_id] = experiment
    return experiment


def create_experiment(
    request_text: str,
    move_ids: list[str],
    kernel_id: str = "",
) -> ExperimentSet:
    """Create an experiment set with one semantic_move branch per move_id.

    Legacy API — kept for back-compat. Internally builds one BranchSeed per
    move_id via seed_from_move_id and delegates to create_experiment_from_seeds.
    Branch naming, ids, and lifecycle are unchanged for existing callers.
    """
    seeds = [seed_from_move_id(mid) for mid in move_ids]
    return create_experiment_from_seeds(
        request_text=request_text,
        seeds=seeds,
        kernel_id=kernel_id,
    )


def get_experiment(experiment_id: str) -> Optional[ExperimentSet]:
    """Get an experiment by ID."""
    return _EXPERIMENTS.get(experiment_id)


def list_experiments() -> list[dict]:
    """List all experiment sets."""
    return [exp.to_dict() for exp in _EXPERIMENTS.values()]

# ── Run experiments (requires Ableton connection) ────────────────────────────


def run_branch(
    branch: ExperimentBranch,
    ableton,  # AbletonConnection
    compiled_plan: dict,
    capture_fn,  # function() -> BranchSnapshot
) -> ExperimentBranch:
    """Run a single branch experiment.

    1. Capture before state
    2. Execute compiled plan steps
    3. Capture after state
    4. Undo all changes

    The branch is updated in-place with snapshots and status.
    """
    # NOTE: this function was converted to an async wrapper around the
    # async execution router in v1.10.3 (Truth Release). The synchronous
    # _run_branch_sync stays for any caller that still uses it, but it now
    # fails loudly on execution errors instead of silently swallowing them.
    # The canonical path is run_branch_async below. Callers (tools.py) use
    # the async variant directly.
    return _run_branch_sync(branch, ableton, compiled_plan, capture_fn)


def _run_branch_sync(branch, ableton, compiled_plan, capture_fn):
    """Legacy sync run_branch body. Preserved for back-compat only.

    Experiment tools now use run_branch_async which routes through the
    unified execution substrate.
    """
    branch.status = "running"
    branch.compiled_plan = compiled_plan
    branch.before_snapshot = capture_fn()

    from ..runtime.execution_router import READ_ONLY_TOOLS

    steps_executed = 0
    log = []
    for step in compiled_plan.get("steps", []):
        tool = step.get("tool", "")
        params = step.get("params", {})
        if not tool:
            continue
        if tool in READ_ONLY_TOOLS:
            continue
        try:
            result = ableton.send_command(tool, params)
            steps_executed += 1
            log.append({"tool": tool, "backend": "remote_command", "ok": True, "result": result})
        except Exception as exc:
            log.append({"tool": tool, "backend": "remote_command", "ok": False, "error": str(exc)})

    branch.execution_log = log
    branch.executed_at_ms = int(time.time() * 1000)
    branch.after_snapshot = capture_fn()

    for _ in range(steps_executed):
        try:
            ableton.send_command("undo", {})
        except Exception as exc:
            logger.debug("_run_branch_sync failed: %s", exc)
            break

    branch.status = "evaluated" if steps_executed > 0 else "failed"
    return branch


async def run_branch_async(
    branch,
    ableton,
    compiled_plan: dict,
    capture_fn,
    bridge=None,
    mcp_registry=None,
    ctx=None,
):
    """Run a single branch experiment through the async execution router.

    Same semantics as run_branch (apply → capture → evaluate → undo) but
    dispatches each step through execute_plan_steps_async so remote /
    bridge / mcp backends are all routed correctly and per-step failures
    are visible in branch.execution_log.

    Read-only verification steps (get_track_meters, get_master_spectrum,
    analyze_mix) are skipped in the apply pass — they're used for snapshot
    capture separately.
    """
    from ..runtime.execution_router import execute_plan_steps_async, filter_apply_steps

    branch.status = "running"
    branch.compiled_plan = compiled_plan

    branch.before_snapshot = capture_fn()

    # Filter out read-only verification steps from the apply pass (canonical
    # list lives in execution_router.READ_ONLY_TOOLS).
    all_steps = compiled_plan.get("steps", []) or []
    apply_steps = filter_apply_steps(all_steps)

    exec_results = await execute_plan_steps_async(
        apply_steps,
        ableton=ableton,
        bridge=bridge,
        mcp_registry=mcp_registry or {},
        ctx=ctx,
        stop_on_failure=False,  # best-effort, but log every failure
    )

    # Record per-step results on the branch for visibility
    branch.execution_log = [
        {
            "tool": r.tool,
            "backend": r.backend,
            "ok": r.ok,
            **({"result": r.result} if r.ok else {"error": r.error}),
        }
        for r in exec_results
    ]

    steps_executed = sum(1 for r in exec_results if r.ok)
    branch.executed_at_ms = int(time.time() * 1000)
    branch.after_snapshot = capture_fn()

    # Undo all successful steps back to checkpoint. Undo is a remote_command,
    # route it through the normal ableton.send_command path for simplicity.
    for _ in range(steps_executed):
        try:
            ableton.send_command("undo", {})
        except Exception as exc:
            logger.debug("run_branch_async failed: %s", exc)
            break

    # A branch is "evaluated" only if it actually applied at least one step.
    # If every step failed, mark it "failed" — this is the truth-release
    # behavior that makes the experiment honest instead of pretending
    # a broken branch produced a neutral result.
    branch.status = "evaluated" if steps_executed > 0 else "failed"
    return branch


def evaluate_branch(
    branch: ExperimentBranch,
    evaluate_fn,  # function(before, after) -> dict with "score", "keep_change"
) -> ExperimentBranch:
    """Score a branch using the evaluation fabric."""
    if not branch.before_snapshot or not branch.after_snapshot:
        branch.evaluation = {"error": "Missing snapshots"}
        branch.score = 0.0
        return branch

    result = evaluate_fn(
        branch.before_snapshot.to_dict(),
        branch.after_snapshot.to_dict(),
    )
    branch.evaluation = result
    branch.score = result.get("score", 0.0)
    return branch

# ── Commit / discard ─────────────────────────────────────────────────────────


async def commit_branch_async(
    experiment: ExperimentSet,
    branch_id: str,
    ableton,
    bridge=None,
    mcp_registry=None,
    ctx=None,
) -> dict:
    """Re-apply the winning branch's moves permanently, through the async
    execution router. No undo — the changes stick.

    Returns a dict with the committed branch info AND the execution_log
    (per-step ok/error results). If any step failed, the branch is marked
    'committed_with_errors' so the caller can tell the commit was partial.
    """
    from ..runtime.execution_router import execute_plan_steps_async

    branch = experiment.get_branch(branch_id)
    if not branch:
        return {"error": f"Branch {branch_id} not found"}

    if not branch.compiled_plan:
        return {"error": "Branch has no compiled plan"}

    all_steps = branch.compiled_plan.get("steps", []) or []
    apply_steps = [
        s for s in all_steps
        if s.get("tool") and s.get("tool") not in (
            "get_track_meters", "get_master_spectrum", "analyze_mix",
        )
    ]

    exec_results = await execute_plan_steps_async(
        apply_steps,
        ableton=ableton,
        bridge=bridge,
        mcp_registry=mcp_registry or {},
        ctx=ctx,
        stop_on_failure=False,  # best-effort commit — record everything
    )

    log = [
        {
            "tool": r.tool,
            "backend": r.backend,
            "ok": r.ok,
            **({"result": r.result} if r.ok else {"error": r.error}),
        }
        for r in exec_results
    ]
    branch.execution_log = log
    steps_ok = sum(1 for r in exec_results if r.ok)
    steps_failed = len(exec_results) - steps_ok

    if steps_failed == 0 and steps_ok > 0:
        branch.status = "committed"
    elif steps_ok > 0:
        branch.status = "committed_with_errors"
    else:
        # Zero successful steps — don't claim the commit happened
        branch.status = "failed"
        return {
            "committed": False,
            "branch_id": branch_id,
            "branch_name": branch.name,
            "error": "No steps executed successfully",
            "steps_attempted": len(apply_steps),
            "execution_log": log,
        }

    experiment.winner_branch_id = branch_id
    experiment.status = "committed"

    return {
        "committed": True,
        "branch_id": branch_id,
        "branch_name": branch.name,
        "steps_executed": steps_ok,
        "steps_failed": steps_failed,
        "status": branch.status,
        "score": branch.score,
        "execution_log": log,
    }


def commit_branch(
    experiment: ExperimentSet,
    branch_id: str,
    ableton,
) -> dict:
    """Legacy sync wrapper kept for any direct caller. The canonical path
    is commit_branch_async through tools.py → execute_plan_steps_async.

    Still truth-honest: records per-step ok/error, marks branches as
    'committed_with_errors' on partial failure rather than lying about it.
    """
    branch = experiment.get_branch(branch_id)
    if not branch:
        return {"error": f"Branch {branch_id} not found"}

    if not branch.compiled_plan:
        return {"error": "Branch has no compiled plan"}

    executed = []
    for step in branch.compiled_plan.get("steps", []):
        tool = step.get("tool", "")
        params = step.get("params", {})
        if not tool or tool in ("get_track_meters", "get_master_spectrum", "analyze_mix"):
            continue
        try:
            result = ableton.send_command(tool, params)
            executed.append({"tool": tool, "ok": True, "backend": "remote_command"})
        except Exception as exc:
            executed.append({"tool": tool, "ok": False, "backend": "remote_command", "error": str(exc)})

    branch.execution_log = executed
    ok_count = sum(1 for e in executed if e.get("ok"))
    failed_count = len(executed) - ok_count

    if failed_count == 0 and ok_count > 0:
        branch.status = "committed"
    elif ok_count > 0:
        branch.status = "committed_with_errors"
    else:
        branch.status = "failed"
        return {
            "committed": False,
            "branch_id": branch_id,
            "branch_name": branch.name,
            "error": "No steps executed successfully",
            "steps_attempted": len(executed),
            "execution_log": executed,
        }

    experiment.winner_branch_id = branch_id
    experiment.status = "committed"

    return {
        "committed": True,
        "branch_id": branch_id,
        "branch_name": branch.name,
        "steps_executed": ok_count,
        "steps_failed": failed_count,
        "status": branch.status,
        "score": branch.score,
    }


def discard_experiment(experiment_id: str) -> dict:
    """Discard an entire experiment set."""
    exp = _EXPERIMENTS.get(experiment_id)
    if not exp:
        return {"error": f"Experiment {experiment_id} not found"}

    for branch in exp.branches:
        if branch.status not in ("committed", "discarded"):
            branch.status = "discarded"
    exp.status = "discarded"

    return {"discarded": True, "experiment_id": experiment_id}


# ── v1.19 Item A — between-branch baseline restore ───────────────────────────


def prepare_for_next_branch(ableton, baseline, stabilize_ms: int = 300) -> None:
    """Restore baseline transport state before capturing the next branch.

    Called by ``run_experiment`` between branches so each branch's
    ``before_snapshot`` reads from identical starting conditions. No-op
    when ``baseline`` is None (first branch — the baseline was just
    captured, no drift to correct).

    Thin wrapper around ``baseline.restore_baseline``; exists so the
    MCP tool body stays small and the wiring is testable in isolation.
    """
    if baseline is None:
        return
    from .baseline import restore_baseline
    restore_baseline(ableton, baseline, stabilize_ms=stabilize_ms)
