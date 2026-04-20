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
from ..branches import BranchSeed
from . import engine
from .models import BranchSnapshot
import logging

logger = logging.getLogger(__name__)


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
    except Exception as exc:
        logger.debug("_capture_snapshot failed: %s", exc)
    # Spectral data (requires M4L analyzer)
    if spectral and spectral.is_connected:
        try:
            spec = spectral.get("spectrum")
            if spec:
                snapshot.spectrum = spec.get("value", {})
        except Exception as exc:
            logger.debug("_capture_snapshot failed: %s", exc)
        try:
            rms_data = spectral.get("rms")
            if rms_data:
                snapshot.rms = rms_data.get("value")
        except Exception as exc:
            logger.debug("_capture_snapshot failed: %s", exc)
    return snapshot


@mcp.tool()
def create_experiment(
    ctx: Context,
    request_text: str,
    move_ids: Optional[list] = None,
    limit: int = 3,
    seeds: Optional[list] = None,
    compiled_plans: Optional[list] = None,
) -> dict:
    """Create an experiment set to compare multiple approaches.

    Three input modes (in priority order):

    1. seeds (PR3+): a list of BranchSeed dicts. Each seed becomes one branch.
       compiled_plans (optional parallel list) attaches pre-compiled plans
       for freeform / synthesis / composer producers. Seed dict shape:
         {seed_id, source, move_id, hypothesis, protected_qualities,
          affected_scope, distinctness_reason, risk_label, novelty_label,
          analytical_only}
       Missing fields default per BranchSeed. This is the canonical path
       for producers that have already done their own selection work.

    2. move_ids: legacy path — one semantic_move seed per move_id.
       Unchanged behavior; internally delegates to the seeds path.

    3. Auto-proposal: neither seeds nor move_ids provided. Scans the semantic
       move registry by keyword overlap with request_text and takes the top
       ``limit`` moves (default 3).

    Returns: experiment set with branch IDs ready for run_experiment.
    """
    # ── Mode 1: seeds provided ──────────────────────────────────────────
    if seeds:
        rehydrated: list[BranchSeed] = []
        for i, s in enumerate(seeds):
            if isinstance(s, BranchSeed):
                rehydrated.append(s)
            elif isinstance(s, dict):
                try:
                    rehydrated.append(BranchSeed(**s))
                except TypeError as exc:
                    return {"error": f"seeds[{i}] invalid: {exc}"}
            else:
                return {
                    "error": (
                        f"seeds[{i}] must be dict or BranchSeed, "
                        f"got {type(s).__name__}"
                    )
                }

        if compiled_plans is not None and len(compiled_plans) != len(rehydrated):
            return {
                "error": (
                    f"compiled_plans length ({len(compiled_plans)}) must match "
                    f"seeds length ({len(rehydrated)})"
                )
            }

        ableton = _get_ableton(ctx)
        ableton.send_command("get_session_info")
        kernel_id = f"kern_{int(time.time())}"

        experiment = engine.create_experiment_from_seeds(
            request_text=request_text,
            seeds=rehydrated,
            kernel_id=kernel_id,
            compiled_plans=compiled_plans,
        )
        return experiment.to_dict()

    # ── Mode 2/3: legacy move_ids path ──────────────────────────────────
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
async def run_experiment(
    ctx: Context,
    experiment_id: str,
    exploration_rules: bool = False,
) -> dict:
    """Run all pending branches in an experiment.

    For each branch:
    1. Compile the semantic move against current session
       (skipped when branch.compiled_plan is already set — PR3+)
    2. Capture before state
    3. Execute the compiled plan (through the async router)
    4. Capture after state
    5. Undo all successful steps (revert to checkpoint)
    6. Evaluate the branch and classify its outcome via evaluation.policy
    7. Record per-step results on branch.execution_log

    Branches run sequentially (Ableton has linear undo).

    exploration_rules (PR7): when True, branches that fail technical gates
    (score < 0.40, non-positive measurable delta) are classified as
    "interesting_but_failed" instead of "failed" — they stay in the
    experiment for audit but don't appear in the ranking. Protection
    violations STILL force undo regardless of this flag — that's a safety
    invariant, not a taste judgment.

    Default False preserves pre-PR7 behavior exactly.
    """
    experiment = engine.get_experiment(experiment_id)
    if not experiment:
        return {"error": f"Experiment {experiment_id} not found"}

    ableton = _get_ableton(ctx)
    bridge = ctx.lifespan_context.get("m4l")
    mcp_registry = ctx.lifespan_context.get("mcp_dispatch", {})

    # Import compiler
    from ..semantic_moves import registry, compiler

    results = []
    for branch in experiment.branches:
        if branch.status != "pending":
            continue

        # PR3: respect a pre-existing compiled_plan on the branch (freeform /
        # synthesis / composer producers bring their own). Only compile from
        # move_id when the branch arrived without a plan — which requires a
        # semantic_move seed (or a legacy move-only branch).
        compiled_dict = branch.compiled_plan

        if compiled_dict is None:
            # Analytical-only branches short-circuit — no plan to run.
            # Marked with status="analytical" so ranked_branches()
            # (which only surfaces "evaluated") excludes them, and
            # commit_experiment refuses to re-apply them.
            if branch.seed is not None and branch.seed.analytical_only:
                branch.status = "analytical"
                branch.score = 0.0
                branch.evaluation = {
                    "score": 0.0,
                    "keep_change": False,
                    "status": "analytical",
                    "note": "analytical_only branch — no execution path",
                }
                results.append(branch.to_dict())
                continue

            if not branch.move_id:
                branch.status = "failed"
                branch.score = 0.0
                branch.evaluation = {
                    "error": (
                        "Branch has no compiled_plan and no move_id — "
                        "freeform producers must pre-populate compiled_plan"
                    )
                }
                results.append(branch.to_dict())
                continue

            # Compile from semantic move
            move = registry.get_move(branch.move_id)
            if not move:
                branch.status = "failed"
                branch.score = 0.0
                branch.evaluation = {"error": f"Move {branch.move_id} not found"}
                results.append(branch.to_dict())
                continue

            session_info = ableton.send_command("get_session_info")
            kernel = {"session_info": session_info, "mode": "explore"}
            plan = compiler.compile(move, kernel)
            compiled_dict = plan.to_dict()

        # Run the branch through the async router
        await engine.run_branch_async(
            branch=branch,
            ableton=ableton,
            compiled_plan=compiled_dict,
            capture_fn=lambda: _capture_snapshot(ctx),
            bridge=bridge,
            mcp_registry=mcp_registry,
            ctx=ctx,
        )

        # Evaluate — score via the inline heuristic, then classify via
        # evaluation.policy for a unified keep/undo/interesting_but_failed
        # decision (PR7).
        from ..evaluation.policy import classify_branch_outcome

        def eval_fn(before, after):
            # Simple heuristic evaluation when spectral data isn't available.
            # protection_violated is rough — derived from whether any track
            # went silent (signal lost on a track = protection violation).
            score = 0.5  # Neutral
            protection_violated = False
            lost_tracks = 0

            if before.get("track_meters") and after.get("track_meters"):
                before_alive = sum(1 for t in before["track_meters"] if t.get("level", 0) > 0)
                after_alive = sum(1 for t in after["track_meters"] if t.get("level", 0) > 0)
                lost_tracks = max(0, before_alive - after_alive)
                if lost_tracks == 0:
                    score += 0.1
                else:
                    score -= 0.2
                    # A track going silent is a protection violation — always
                    # undo regardless of exploration mode.
                    protection_violated = True

            if before.get("spectrum") and after.get("spectrum"):
                score += 0.1  # presence-of-data bonus

            score = round(score, 3)
            outcome = classify_branch_outcome(
                score=score,
                protection_violated=protection_violated,
                # Minimal hard-rule inputs — the heuristic doesn't compute
                # measurable_count / goal_progress deltas. target_count=0 and
                # measurable_count=0 lets rule 1 defer to score-only judgment.
                measurable_count=0,
                target_count=0,
                goal_progress=0.0,
                exploration_rules=exploration_rules,
            )

            return {
                "score": outcome.score,
                "keep_change": outcome.keep_change,
                "status": outcome.status,
                "failure_reasons": outcome.failure_reasons,
                "note": outcome.note,
                "lost_tracks": lost_tracks,
            }

        engine.evaluate_branch(branch, eval_fn)

        # Promote the classified status onto the branch. ranked_branches()
        # only surfaces status="evaluated", so branches the classifier
        # rejected ("undo") or retained for audit ("interesting_but_failed")
        # are both correctly excluded from winner recommendations.
        # Without this mapping, a branch the hard-rule classifier explicitly
        # rejected could still win a ranking and be re-applied by commit.
        if branch.evaluation and branch.evaluation.get("status"):
            status = branch.evaluation["status"]
            if status == "keep":
                branch.status = "evaluated"
            elif status == "interesting_but_failed":
                branch.status = "interesting_but_failed"
            elif status == "undo":
                # Undo-classified branches had their steps rolled back by
                # run_branch_async's undo pass; they must NOT be eligible
                # winners. "rejected" is a terminal branch status distinct
                # from "failed" (execution failed) and distinct from
                # "interesting_but_failed" (exploration-mode retention).
                branch.status = "rejected"

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

    # Surface non-winning branch categories separately. None of these are
    # candidates for commit — ranked_branches() filters them out — but the
    # user sees what was tried.
    interesting_failed = [
        b for b in experiment.branches if b.status == "interesting_but_failed"
    ]
    rejected = [
        b for b in experiment.branches if b.status == "rejected"
    ]
    analytical = [
        b for b in experiment.branches if b.status == "analytical"
    ]

    def _audit_row(b):
        return {
            "branch_id": b.branch_id,
            "name": b.name,
            "move_id": b.move_id,
            "score": b.score,
            "summary": b.compiled_plan.get("summary", "") if b.compiled_plan else "",
            "evaluation": b.evaluation,
        }

    return {
        "experiment_id": experiment_id,
        "request": experiment.request_text,
        "branch_count": experiment.branch_count,
        "ranking": [
            {
                "rank": i + 1,
                **_audit_row(b),
            }
            for i, b in enumerate(ranked)
        ],
        "winner": ranked[0].to_dict() if ranked else None,
        "interesting_but_failed": [_audit_row(b) for b in interesting_failed],
        "rejected": [_audit_row(b) for b in rejected],
        "analytical": [_audit_row(b) for b in analytical],
    }


@mcp.tool()
async def commit_experiment(
    ctx: Context,
    experiment_id: str,
    branch_id: str,
) -> dict:
    """Commit the winning branch — re-apply its moves permanently.

    Routes the compiled plan through the async router (v1.10.3 truth).
    Returns a result dict with per-step execution_log. If any step failed,
    branch.status is set to 'committed_with_errors' and the response
    reports steps_failed > 0, so callers can tell the commit was partial.
    """
    experiment = engine.get_experiment(experiment_id)
    if not experiment:
        return {"error": f"Experiment {experiment_id} not found"}

    # Refuse to commit branches the classifier rejected or that were
    # analytical-only. Those statuses exist specifically so callers
    # can't route them into re-application, and ranked_branches()
    # already excludes them — so reaching commit with such a branch
    # means the caller is bypassing the ranking layer.
    target = experiment.get_branch(branch_id)
    if target is None:
        return {"error": f"Branch {branch_id} not found"}
    if target.status in ("rejected", "analytical", "failed"):
        return {
            "error": (
                f"Cannot commit branch with status '{target.status}'. "
                f"'rejected' = hard-rule classifier rolled back; "
                f"'analytical' = no executable plan; "
                f"'failed' = zero steps applied successfully. "
                f"Use compare_experiments to see eligible winners "
                f"(only status='evaluated' branches are ranking candidates)."
            ),
            "branch_id": branch_id,
            "branch_status": target.status,
        }

    ableton = _get_ableton(ctx)
    bridge = ctx.lifespan_context.get("m4l")
    mcp_registry = ctx.lifespan_context.get("mcp_dispatch", {})

    return await engine.commit_branch_async(
        experiment,
        branch_id,
        ableton,
        bridge=bridge,
        mcp_registry=mcp_registry,
        ctx=ctx,
    )


@mcp.tool()
def discard_experiment(
    ctx: Context,
    experiment_id: str,
) -> dict:
    """Discard an entire experiment — no changes are kept."""
    return engine.discard_experiment(experiment_id)
