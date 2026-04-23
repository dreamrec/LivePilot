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
    """Capture current session state as a BranchSnapshot (fast path).

    Uses live meters + spectral cache. No audio rendering. Called when
    render_verify is off (default) — adds no latency to branch trials.
    """
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


def _capture_snapshot_with_render_verify(
    ctx: Context, duration_seconds: float = 2.0,
) -> BranchSnapshot:
    """Capture state AND render audio for fingerprint extraction (PR4).

    Runs the fast-path snapshot first, then additionally:
      1. capture_audio duration_seconds seconds from master
      2. analyze_loudness on the captured file
      3. analyze_spectrum_offline on the captured file
      4. extract_timbre_fingerprint from spectrum + loudness

    Attaches capture_path, loudness, spectral_shape, and fingerprint to
    the snapshot. When any stage fails (bridge unavailable, analyzer
    missing, etc.), that stage's field is left None and a debug log is
    emitted — render-verify degrades gracefully to the fast-path snapshot.

    Expected added latency: duration_seconds (capture) + ~1-2s (offline
    analysis). For a 2-branch experiment with 2s captures, that's
    ~8-10s of overhead vs the default path.
    """
    snapshot = _capture_snapshot(ctx)

    ableton = _get_ableton(ctx)
    bridge = ctx.lifespan_context.get("m4l")

    # Step 1: capture_audio is a bridge command — route via bridge.send_command
    # if available, else fall back to ableton TCP which doesn't support it.
    capture_path = None
    if bridge is not None:
        try:
            maybe = bridge.send_command("capture_audio", float(duration_seconds), "master", "")
            # bridge.send_command may return awaitable or plain dict.
            import inspect
            if inspect.isawaitable(maybe):
                # We're in a sync context here — best effort, skip await.
                # Render-verify from within sync capture_fn is the compromise;
                # the async variant wires through from run_branch_async which
                # does have await. Use the fast-path capture only.
                logger.debug("capture_audio returned awaitable in sync context; skipping render-verify for this snapshot")
                return snapshot
            if isinstance(maybe, dict):
                capture_path = maybe.get("file_path") or maybe.get("path") or maybe.get("filename")
        except Exception as exc:
            logger.debug("render-verify capture_audio failed: %s", exc)
    if not capture_path:
        return snapshot  # graceful degrade — caller still gets fast-path data
    snapshot.capture_path = capture_path

    # Step 2-3: offline loudness + spectrum analysis (MCP tools, sync wrappers)
    try:
        from ..tools.analyzer import analyze_loudness as _analyze_loudness
        loud = _analyze_loudness(capture_path)
        if isinstance(loud, dict) and "error" not in loud:
            snapshot.loudness = loud
    except Exception as exc:
        logger.debug("render-verify analyze_loudness failed: %s", exc)

    try:
        from ..tools.analyzer import analyze_spectrum_offline as _analyze_spectrum
        spec = _analyze_spectrum(capture_path)
        if isinstance(spec, dict) and "error" not in spec:
            snapshot.spectral_shape = {
                "centroid": spec.get("centroid_hz"),
                "flatness": spec.get("spectral_flatness"),
                "rolloff": spec.get("rolloff_hz"),
                "bandwidth": spec.get("bandwidth_hz"),
                # Back-map the 5-band balance into the 8-band keys our
                # fingerprint extractor expects. Coarse mapping:
                "bands": _map_5band_to_8band(spec.get("band_balance", {})),
            }
    except Exception as exc:
        logger.debug("render-verify analyze_spectrum_offline failed: %s", exc)

    # Step 4: build fingerprint from what we got
    try:
        from ..synthesis_brain import extract_timbre_fingerprint
        fp = extract_timbre_fingerprint(
            spectrum=(snapshot.spectral_shape or {}).get("bands"),
            loudness=snapshot.loudness,
            spectral_shape=snapshot.spectral_shape,
        )
        snapshot.fingerprint = fp.to_dict()
    except Exception as exc:
        logger.debug("render-verify extract_timbre_fingerprint failed: %s", exc)

    return snapshot


def _map_5band_to_8band(b5: dict) -> dict:
    """Adapt analyze_spectrum_offline's 5-band balance to the 8-band shape
    extract_timbre_fingerprint expects.

    5-band: sub_60hz, low_250hz, mid_2khz, high_8khz, air_16khz
    8-band: sub, low, low_mid, mid, high_mid, high, very_high, ultra
    """
    if not isinstance(b5, dict):
        return {}
    # Conservative mapping — split each 5-band bucket across the 8-band shape.
    return {
        "sub":       float(b5.get("sub_60hz", 0.0) or 0.0),
        "low":       float(b5.get("low_250hz", 0.0) or 0.0) * 0.6,
        "low_mid":   float(b5.get("low_250hz", 0.0) or 0.0) * 0.4,
        "mid":       float(b5.get("mid_2khz", 0.0) or 0.0) * 0.6,
        "high_mid":  float(b5.get("mid_2khz", 0.0) or 0.0) * 0.4,
        "high":      float(b5.get("high_8khz", 0.0) or 0.0) * 0.6,
        "very_high": float(b5.get("high_8khz", 0.0) or 0.0) * 0.4,
        "ultra":     float(b5.get("air_16khz", 0.0) or 0.0),
    }


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
        # Auto-propose moves from the registry by keyword overlap.
        # v1.18.1 #1 fix: the previous selector indexed the first character
        # of each move_id (a Python unpacking trap — the variable was
        # already the full string, the [0] subscript sliced into it).
        # Result pre-fix: single-char move_ids like 't', 'w', 'm' that
        # failed at run_experiment with "Move t not found". Now the whole
        # move_id string is kept.
        from ..semantic_moves import registry
        all_moves = list(registry._REGISTRY.values())
        request_lower = request_text.lower()
        request_words = set(request_lower.split())
        scored: list[tuple[str, float]] = []
        for move in all_moves:
            score = 0.0
            move_words = set(move.move_id.replace("_", " ").split())
            intent_words = set(move.intent.lower().split())
            overlap = request_words & (move_words | intent_words)
            score += len(overlap) * 0.3
            for dim in move.targets:
                if dim in request_lower:
                    score += 0.2
            if score > 0.1:
                scored.append((move.move_id, score))
        scored.sort(key=lambda x: -x[1])
        move_ids = [move_id for move_id, _ in scored[:limit]] if scored else []

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
    render_verify: bool = False,
    render_duration_seconds: float = 2.0,
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

    exploration_rules: when True, branches that fail technical gates
      (score < 0.40, non-positive measurable delta) are classified as
      "interesting_but_failed" instead of "failed" — they stay in the
      experiment for audit but don't appear in the ranking. Protection
      violations STILL force undo regardless of this flag — that's a
      safety invariant, not a taste judgment.

    render_verify (PR4/v2): when True, each branch also captures audio
      before and after execution, analyzes spectrum + loudness offline,
      extracts a TimbralFingerprint, and attaches the before/after
      fingerprint + diff to the branch snapshots. The diff is fed into
      classify_branch_outcome as real measurable evidence — the
      classifier no longer relies on meter heuristics alone. Default
      False preserves speed; opt in when you want the classifier to
      respond to spectral movement, not just track-meter drops.

    render_duration_seconds: capture length per snapshot when
      render_verify is on. Default 2.0 seconds. Each branch adds
      ~2 * duration_seconds of capture time plus ~1-2s of offline
      analysis — a 3-branch experiment at 2s adds ~15-18s.

    Default render_verify=False preserves pre-PR4 behavior exactly.
    """
    experiment = engine.get_experiment(experiment_id)
    if not experiment:
        return {"error": f"Experiment {experiment_id} not found"}

    ableton = _get_ableton(ctx)
    bridge = ctx.lifespan_context.get("m4l")
    mcp_registry = ctx.lifespan_context.get("mcp_dispatch", {})

    # Import compiler
    from ..semantic_moves import registry, compiler

    # v1.19 Item A — capture baseline transport state BEFORE any branch runs.
    # Each branch's before_snapshot is only comparable if it starts from the
    # same reference state. Without this, live testing (v1.18.0 Test 8) showed
    # 3 branches produce wildly inconsistent before_snapshot.track_meters[0].level
    # values — clip stopped mid-experiment between branches.
    if experiment.baseline_transport is None:
        from .baseline import capture_baseline
        try:
            experiment.baseline_transport = capture_baseline(ableton)
        except Exception as exc:
            logger.debug("baseline capture failed: %s", exc)
            experiment.baseline_transport = None

    results = []
    pending_seen = 0
    for branch in experiment.branches:
        if branch.status != "pending":
            continue

        # Between branches (not before the first), restore the baseline so
        # the next before_snapshot reads from the same reference state.
        if pending_seen > 0:
            engine.prepare_for_next_branch(
                ableton, experiment.baseline_transport, stabilize_ms=300,
            )
        pending_seen += 1

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

        # Pick the capture function — render-verify mode captures audio
        # and extracts a TimbralFingerprint, adding latency but giving
        # classify_branch_outcome real measurable evidence.
        if render_verify:
            capture_fn = lambda: _capture_snapshot_with_render_verify(
                ctx, duration_seconds=render_duration_seconds,
            )
        else:
            capture_fn = lambda: _capture_snapshot(ctx)

        # Run the branch through the async router
        await engine.run_branch_async(
            branch=branch,
            ableton=ableton,
            compiled_plan=compiled_dict,
            capture_fn=capture_fn,
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

            # PR4 — fingerprint diff to feed the classifier when render-verify
            # is on. When both before/after have fingerprints, compute the
            # per-dimension diff via synthesis_brain.diff_fingerprint and let
            # classify_branch_outcome derive real measurable_count + goal_progress
            # from it. Much stronger evidence than the meter heuristic alone.
            fingerprint_diff = None
            timbral_target = None
            before_fp = before.get("fingerprint")
            after_fp = after.get("fingerprint")
            if before_fp and after_fp:
                try:
                    from ..synthesis_brain import diff_fingerprint, TimbralFingerprint
                    before_obj = TimbralFingerprint(**{
                        k: v for k, v in before_fp.items()
                        if k in TimbralFingerprint.__dataclass_fields__
                    })
                    after_obj = TimbralFingerprint(**{
                        k: v for k, v in after_fp.items()
                        if k in TimbralFingerprint.__dataclass_fields__
                    })
                    fingerprint_diff = diff_fingerprint(before_obj, after_obj)
                except Exception as exc:
                    logger.debug("fingerprint diff failed: %s", exc)

            # If the branch's seed was a synthesis seed with a timbral target
            # in its producer_payload, score diff in that target's direction.
            if branch.seed is not None and branch.seed.source == "synthesis":
                target_hint = (branch.seed.producer_payload or {}).get("timbral_target")
                if isinstance(target_hint, dict):
                    timbral_target = target_hint

            outcome = classify_branch_outcome(
                score=score,
                protection_violated=protection_violated,
                measurable_count=0,
                target_count=0,
                goal_progress=0.0,
                exploration_rules=exploration_rules,
                fingerprint_diff=fingerprint_diff,
                timbral_target=timbral_target,
            )

            result_eval = {
                "score": outcome.score,
                "keep_change": outcome.keep_change,
                "status": outcome.status,
                "failure_reasons": outcome.failure_reasons,
                "note": outcome.note,
                "lost_tracks": lost_tracks,
            }
            # Surface fingerprint evidence on the evaluation dict so
            # compare_experiments can show per-branch spectral deltas.
            if fingerprint_diff is not None:
                result_eval["fingerprint_diff"] = fingerprint_diff
                result_eval["fingerprint_before"] = before_fp
                result_eval["fingerprint_after"] = after_fp
            return result_eval

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

    # PR3 — composer winner escalation. When the winning branch came from
    # the composer producer, the plan we auditioned was a lightweight
    # scaffold (set_tempo + create_midi_track + create_scene/set_scene_name).
    # Commit should deliver a populated session, not an empty skeleton.
    # Re-run ComposerEngine.compose() on the intent captured in the seed's
    # producer_payload, replace the branch's compiled_plan with the full
    # resolved plan, then commit through the normal async router.
    #
    # When escalation fails (missing intent, zero resolved layers, etc.),
    # fall back to committing the scaffold. Users get tracks + scenes
    # they can populate manually, which is better than an error.
    escalation_info = None
    if (
        target.seed is not None
        and target.seed.source == "composer"
        and target.seed.producer_payload
    ):
        try:
            from ..composer import escalate_composer_branch
            splice_client = ctx.lifespan_context.get("splice_client")
            # browser_client only present on servers with live browser wiring;
            # pass None defensively.
            browser_client = ctx.lifespan_context.get("browser_client")
            search_roots = ctx.lifespan_context.get("sample_search_roots") or []

            escalation_info = await escalate_composer_branch(
                producer_payload=target.seed.producer_payload,
                search_roots=search_roots,
                splice_client=splice_client,
                browser_client=browser_client,
            )

            if escalation_info.get("ok"):
                # Swap the compiled_plan for the fully resolved one before
                # commit_branch_async runs it. Keep the old scaffold on the
                # evaluation dict for audit.
                old_plan = target.compiled_plan or {}
                new_plan = {
                    "steps": escalation_info["plan"],
                    "step_count": escalation_info["step_count"],
                    "summary": (
                        f"Composer escalated: {escalation_info['layer_count']} "
                        f"layers, {escalation_info['step_count']} steps "
                        f"({len(escalation_info['resolved_samples'])} samples resolved)"
                    ),
                }
                target.compiled_plan = new_plan
                if target.evaluation is None:
                    target.evaluation = {}
                target.evaluation["composer_escalation"] = {
                    "escalated": True,
                    "scaffold_step_count": old_plan.get("step_count", 0),
                    "resolved_step_count": escalation_info["step_count"],
                    "layer_count": escalation_info["layer_count"],
                    "resolved_samples": escalation_info["resolved_samples"],
                    "warnings": escalation_info.get("warnings", []),
                }
            else:
                # Record the fallback reason on evaluation so compare /
                # commit responses carry explicit provenance.
                if target.evaluation is None:
                    target.evaluation = {}
                target.evaluation["composer_escalation"] = {
                    "escalated": False,
                    "error": escalation_info.get("error", "unknown"),
                    "warnings": escalation_info.get("warnings", []),
                    "fallback": "scaffold_plan",
                }
        except Exception as exc:
            if target.evaluation is None:
                target.evaluation = {}
            target.evaluation["composer_escalation"] = {
                "escalated": False,
                "error": f"escalation raised: {exc}",
                "fallback": "scaffold_plan",
            }

    commit_result = await engine.commit_branch_async(
        experiment,
        branch_id,
        ableton,
        bridge=bridge,
        mcp_registry=mcp_registry,
        ctx=ctx,
    )

    # Surface escalation details on the commit response so the caller
    # sees whether a scaffold or resolved plan was applied.
    if escalation_info is not None and isinstance(commit_result, dict):
        commit_result["composer_escalation"] = {
            "escalated": bool(escalation_info.get("ok")),
            "step_count": escalation_info.get("step_count"),
            "layer_count": escalation_info.get("layer_count"),
            "error": escalation_info.get("error"),
            "warnings": escalation_info.get("warnings", []),
        }

    return commit_result


@mcp.tool()
def discard_experiment(
    ctx: Context,
    experiment_id: str,
) -> dict:
    """Discard an entire experiment — no changes are kept."""
    return engine.discard_experiment(experiment_id)
