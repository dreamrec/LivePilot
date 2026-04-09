"""Experiment MCP tools — create, run, compare, commit, discard experiments.

5 tools for branch-based creative search:
  create_experiment — set up branches from semantic moves
  run_experiment — trial each branch (apply → capture → undo)
  compare_experiments — rank branches by evaluation score
  commit_experiment — re-apply the winner permanently
  discard_experiment — throw away all branches
"""

from __future__ import annotations

import time
from typing import Optional

from fastmcp import Context

from ..server import mcp
from . import engine
from .models import BranchSnapshot


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _capture_snapshot(ctx: Context) -> BranchSnapshot:
    """Capture current session state as a BranchSnapshot."""
    ableton = _get_ableton(ctx)
    spectral = ctx.lifespan_context.get("spectral")

    snapshot = BranchSnapshot(timestamp_ms=int(time.time() * 1000))

    # Track meters (always available)
    try:
        meters = ableton.send_command("get_track_meters", {"include_stereo": True})
        snapshot.track_meters = meters.get("tracks", [])
    except Exception:
        pass

    # Spectral data (requires M4L analyzer)
    if spectral and spectral.is_connected:
        try:
            spec = spectral.get("spectrum")
            if spec:
                snapshot.spectrum = spec.get("value", {})
        except Exception:
            pass

        try:
            rms_data = spectral.get("rms")
            if rms_data:
                snapshot.rms = rms_data.get("value")
        except Exception:
            pass

    return snapshot


@mcp.tool()
def create_experiment(
    ctx: Context,
    request_text: str,
    move_ids: Optional[list] = None,
    limit: int = 3,
) -> dict:
    """Create an experiment set to compare multiple approaches.

    If move_ids is provided, creates one branch per move.
    Otherwise, uses propose_next_best_move to find candidates.

    request_text: what the user wants (e.g., "make this punchier")
    move_ids: specific moves to try (e.g., ["make_punchier", "tighten_low_end"])
    limit: max branches when auto-proposing (default 3)

    Returns: experiment set with branch IDs ready for run_experiment.
    """
    if not move_ids:
        # Auto-propose moves from the registry
        from ..semantic_moves import registry
        from ..semantic_moves.tools import propose_next_best_move
        # Use the propose function's logic directly
        all_moves = list(registry._REGISTRY.values())
        request_lower = request_text.lower()
        scored = []
        for move in all_moves:
            score = 0.0
            move_words = set(move.move_id.replace("_", " ").split())
            intent_words = set(move.intent.lower().split())
            request_words = set(request_lower.split())
            overlap = request_words & (move_words | intent_words)
            score += len(overlap) * 0.3
            for dim in move.targets:
                if dim in request_lower:
                    score += 0.2
            if score > 0.1:
                scored.append((move.move_id, score))
        scored.sort(key=lambda x: -x[1])
        move_ids = [m[0] for m, _ in scored[:limit]] if scored else []

    if not move_ids:
        return {"error": "No matching semantic moves found for this request"}

    # Build kernel_id from session
    ableton = _get_ableton(ctx)
    session = ableton.send_command("get_session_info")
    kernel_id = f"kern_{int(time.time())}"

    experiment = engine.create_experiment(
        request_text=request_text,
        move_ids=move_ids,
        kernel_id=kernel_id,
    )

    return experiment.to_dict()


@mcp.tool()
def run_experiment(
    ctx: Context,
    experiment_id: str,
) -> dict:
    """Run all pending branches in an experiment.

    For each branch:
    1. Compile the semantic move against current session
    2. Capture before state
    3. Execute the compiled plan
    4. Capture after state
    5. Undo all changes (revert to checkpoint)
    6. Evaluate the branch

    Branches run sequentially (Ableton has linear undo).
    """
    experiment = engine.get_experiment(experiment_id)
    if not experiment:
        return {"error": f"Experiment {experiment_id} not found"}

    ableton = _get_ableton(ctx)

    # Import compiler
    from ..semantic_moves import registry, compiler

    results = []
    for branch in experiment.branches:
        if branch.status != "pending":
            continue

        # Compile the move
        move = registry.get_move(branch.move_id)
        if not move:
            branch.status = "evaluated"
            branch.score = 0.0
            branch.evaluation = {"error": f"Move {branch.move_id} not found"}
            results.append(branch.to_dict())
            continue

        session_info = ableton.send_command("get_session_info")
        kernel = {"session_info": session_info, "mode": "explore"}
        plan = compiler.compile(move, kernel)
        compiled_dict = plan.to_dict()

        # Run the branch (apply → capture → undo)
        engine.run_branch(
            branch=branch,
            ableton=ableton,
            compiled_plan=compiled_dict,
            capture_fn=lambda: _capture_snapshot(ctx),
        )

        # Evaluate
        def eval_fn(before, after):
            # Simple heuristic evaluation when spectral data isn't available
            score = 0.5  # Neutral
            if before.get("track_meters") and after.get("track_meters"):
                # Check all tracks still alive
                before_alive = sum(1 for t in before["track_meters"] if t.get("level", 0) > 0)
                after_alive = sum(1 for t in after["track_meters"] if t.get("level", 0) > 0)
                if after_alive >= before_alive:
                    score += 0.1
                else:
                    score -= 0.2  # Lost a track

            if before.get("spectrum") and after.get("spectrum"):
                # Spectral balance improvement heuristic
                score += 0.1  # Bonus for having spectral data

            return {"score": round(score, 3), "keep_change": score > 0.45}

        engine.evaluate_branch(branch, eval_fn)
        results.append(branch.to_dict())

    return {
        "experiment_id": experiment_id,
        "branches_run": len(results),
        "results": results,
        "ranking": [
            {"branch_id": b.branch_id, "name": b.name, "score": b.score, "move_id": b.move_id}
            for b in experiment.ranked_branches()
        ],
    }


@mcp.tool()
def compare_experiments(
    ctx: Context,
    experiment_id: str,
) -> dict:
    """Compare and rank all evaluated branches in an experiment.

    Returns branches sorted by score with their evaluations and summaries.
    """
    experiment = engine.get_experiment(experiment_id)
    if not experiment:
        return {"error": f"Experiment {experiment_id} not found"}

    ranked = experiment.ranked_branches()
    return {
        "experiment_id": experiment_id,
        "request": experiment.request_text,
        "branch_count": experiment.branch_count,
        "ranking": [
            {
                "rank": i + 1,
                "branch_id": b.branch_id,
                "name": b.name,
                "move_id": b.move_id,
                "score": b.score,
                "summary": b.compiled_plan.get("summary", "") if b.compiled_plan else "",
                "evaluation": b.evaluation,
            }
            for i, b in enumerate(ranked)
        ],
        "winner": ranked[0].to_dict() if ranked else None,
    }


@mcp.tool()
def commit_experiment(
    ctx: Context,
    experiment_id: str,
    branch_id: str,
) -> dict:
    """Commit the winning branch — re-apply its moves permanently.

    This executes the branch's compiled plan again, this time without undoing.
    The experiment is marked as committed.
    """
    experiment = engine.get_experiment(experiment_id)
    if not experiment:
        return {"error": f"Experiment {experiment_id} not found"}

    ableton = _get_ableton(ctx)
    return engine.commit_branch(experiment, branch_id, ableton)


@mcp.tool()
def discard_experiment(
    ctx: Context,
    experiment_id: str,
) -> dict:
    """Discard an entire experiment — no changes are kept."""
    return engine.discard_experiment(experiment_id)
