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


# ── In-memory experiment store ───────────────────────────────────────────────

_EXPERIMENTS: dict[str, ExperimentSet] = {}


def _gen_id(prefix: str, seed: str) -> str:
    """Generate a short deterministic ID."""
    h = hashlib.sha256(f"{prefix}:{seed}:{time.time()}".encode()).hexdigest()[:8]
    return f"{prefix}_{h}"


# ── Create experiments ───────────────────────────────────────────────────────

def create_experiment(
    request_text: str,
    move_ids: list[str],
    kernel_id: str = "",
) -> ExperimentSet:
    """Create an experiment set with branches for each semantic move.

    Does NOT execute anything — just creates the branch structures.
    Call run_experiment() to actually trial each branch.
    """
    exp_id = _gen_id("exp", request_text)
    now = int(time.time() * 1000)

    branches = []
    for i, move_id in enumerate(move_ids):
        branch = ExperimentBranch(
            branch_id=_gen_id("br", f"{move_id}_{i}"),
            name=f"Branch {i+1}: {move_id}",
            move_id=move_id,
            source_kernel_id=kernel_id,
            status="pending",
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
    branch.status = "running"
    branch.compiled_plan = compiled_plan

    # 1. Capture before
    branch.before_snapshot = capture_fn()

    # 2. Execute plan steps
    steps_executed = 0
    for step in compiled_plan.get("steps", []):
        tool = step.get("tool", "")
        params = step.get("params", {})
        if not tool:
            continue
        # Skip read-only verification steps
        if tool in ("get_track_meters", "get_master_spectrum", "analyze_mix"):
            continue
        try:
            ableton.send_command(tool, params)
            steps_executed += 1
        except Exception:
            pass  # Best effort — continue with remaining steps

    branch.executed_at_ms = int(time.time() * 1000)

    # 3. Capture after
    branch.after_snapshot = capture_fn()

    # 4. Undo all changes back to checkpoint
    for _ in range(steps_executed):
        try:
            ableton.send_command("undo", {})
        except Exception:
            break

    branch.status = "evaluated"
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

def commit_branch(
    experiment: ExperimentSet,
    branch_id: str,
    ableton,
) -> dict:
    """Re-apply the winning branch's moves permanently."""
    branch = experiment.get_branch(branch_id)
    if not branch:
        return {"error": f"Branch {branch_id} not found"}

    if not branch.compiled_plan:
        return {"error": "Branch has no compiled plan"}

    # Re-execute the plan (this time without undoing)
    executed = []
    for step in branch.compiled_plan.get("steps", []):
        tool = step.get("tool", "")
        params = step.get("params", {})
        if not tool or tool in ("get_track_meters", "get_master_spectrum", "analyze_mix"):
            continue
        try:
            result = ableton.send_command(tool, params)
            executed.append({"tool": tool, "ok": True})
        except Exception as exc:
            executed.append({"tool": tool, "ok": False, "error": str(exc)})

    branch.status = "committed"
    experiment.winner_branch_id = branch_id
    experiment.status = "committed"

    return {
        "committed": True,
        "branch_id": branch_id,
        "branch_name": branch.name,
        "steps_executed": len(executed),
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
