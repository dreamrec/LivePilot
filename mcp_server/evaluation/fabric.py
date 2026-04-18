"""Evaluation Fabric — unified entry point for all engine evaluators.

Provides evaluate() as the single router, plus engine-specific evaluators:
  - evaluate_sonic_move()       — spectral before/after
  - evaluate_composition_move() — issue list before/after
  - evaluate_mix_move()         — mix critic issues before/after
  - evaluate_transition()       — transition score before/after
  - evaluate_translation()      — translation report before/after

Uses feature_extractors for dimension extraction, policy for hard rules,
and the existing contracts from _evaluation_contracts.

Design: EVALUATION_FABRIC_V1.md
"""

from __future__ import annotations

from typing import Optional

from ..tools._evaluation_contracts import (
    EvaluationRequest,
    EvaluationResult,
    MEASURABLE_DIMENSIONS,
    is_dimension_measurable,
)
from ..tools._snapshot_normalizer import normalize_sonic_snapshot
from .feature_extractors import extract_dimension_value, _clamp
from .policy import apply_hard_rules


# ── Sonic Evaluator ──────────────────────────────────────────────────


def _compute_taste_fit(
    dimension_changes: dict[str, dict],
    outcome_history: Optional[list[dict]],
) -> float:
    """Score how well this move aligns with the user's recent taste.

    Shipped in v1.10.9 — previously hardcoded to 0.0.

    For each dimension that moved (in ``dimension_changes``), look at the
    user's last few kept/undone outcomes for the same dimension:
      * kept with the same direction of delta → +0.2 per match
      * undone with the same direction of delta → −0.2 per match

    Returns a value in 0..1 (0.5 = neutral, neither signal). Empty history
    returns 0.5, which is the correct "no information yet" neutral the
    composite score already expects.

    ``outcome_history`` entries are dicts of the shape::

        {"dimension": "punch", "delta": 0.12, "kept": True}

    Callers that pass a richer shape should extract those three fields.
    Malformed entries are skipped silently so a schema bump upstream can't
    break the evaluator.
    """
    if not outcome_history or not dimension_changes:
        return 0.5

    # Only weigh the most recent slice — taste drifts, and older signals
    # shouldn't veto a current evaluation.
    recent = outcome_history[-10:]

    adjustment = 0.0
    matched = 0
    for dim, change in dimension_changes.items():
        current_delta = change.get("delta", 0.0)
        current_sign = 1 if current_delta > 0 else (-1 if current_delta < 0 else 0)
        if current_sign == 0:
            continue
        for entry in recent:
            if not isinstance(entry, dict):
                continue
            if entry.get("dimension") != dim:
                continue
            past_delta = entry.get("delta")
            if not isinstance(past_delta, (int, float)):
                continue
            past_sign = 1 if past_delta > 0 else (-1 if past_delta < 0 else 0)
            if past_sign != current_sign:
                continue
            kept = bool(entry.get("kept", False))
            adjustment += 0.2 if kept else -0.2
            matched += 1

    if matched == 0:
        return 0.5
    # Neutral baseline 0.5 + averaged adjustment, clamped to [0, 1].
    return _clamp(0.5 + adjustment / matched)


def evaluate_sonic_move(
    request: EvaluationRequest,
    outcome_history: Optional[list[dict]] = None,
) -> EvaluationResult:
    """Evaluate a sonic move using the Evaluation Fabric.

    Normalizes before/after snapshots, extracts dimension values,
    computes score and goal progress, and applies hard rules.

    Args:
        request: EvaluationRequest with before/after snapshots,
                 goal targets/protect in goal and protect dicts.
        outcome_history: optional list of past outcomes for taste fit.

    Returns:
        EvaluationResult with score, keep_change, dimension_changes, etc.
    """
    # Normalize snapshots
    before_norm = normalize_sonic_snapshot(request.before, source="before")
    after_norm = normalize_sonic_snapshot(request.after, source="after")

    targets = request.goal.get("targets", {})
    protect = request.protect

    notes: list[str] = []
    dimension_changes: dict[str, dict] = {}

    # Compute per-dimension deltas
    total_goal_progress = 0.0
    measurable_count = 0

    for dim, weight in targets.items():
        before_val = extract_dimension_value(before_norm, dim) if before_norm else None
        after_val = extract_dimension_value(after_norm, dim) if after_norm else None

        if before_val is not None and after_val is not None:
            delta = after_val - before_val
            dimension_changes[dim] = {
                "before": round(before_val, 4),
                "after": round(after_val, 4),
                "delta": round(delta, 4),
            }
            total_goal_progress += delta * weight
            measurable_count += 1
        else:
            notes.append(f"{dim}: not measurable in Phase 1 (confidence=0.0)")

    # Check protected dimensions
    collateral_damage = 0.0
    protection_violated = False

    for dim, threshold in protect.items():
        before_val = extract_dimension_value(before_norm, dim) if before_norm else None
        after_val = extract_dimension_value(after_norm, dim) if after_norm else None

        if before_val is not None and after_val is not None:
            drop = before_val - after_val
            if drop > 0:
                collateral_damage = max(collateral_damage, drop)
            if after_val < threshold:
                protection_violated = True
                notes.append(
                    f"PROTECTED dimension '{dim}' at {after_val:.3f}, "
                    f"below threshold {threshold:.3f}"
                )
            elif drop > 0.15:
                protection_violated = True
                notes.append(
                    f"PROTECTED dimension '{dim}' dropped by {drop:.3f} "
                    f"(absolute drop > 0.15)"
                )

    # Compute composite score
    measurable_delta = total_goal_progress / max(measurable_count, 1)
    goal_fit = _clamp(0.5 + total_goal_progress)
    measurable_component = _clamp(0.5 + measurable_delta)
    preservation = _clamp(1.0 - collateral_damage * 5)
    confidence = measurable_count / max(len(targets), 1)
    taste_fit = _compute_taste_fit(dimension_changes, outcome_history)

    score = (
        0.30 * goal_fit
        + 0.25 * measurable_component
        + 0.15 * preservation
        + 0.10 * taste_fit
        + 0.10 * confidence
        + 0.10 * 1.0   # reversibility: 1.0 for undo-able moves
    )

    # Apply hard rules via policy engine
    keep_change, rule_failures = apply_hard_rules(
        goal_progress=total_goal_progress,
        collateral_damage=collateral_damage,
        protection_violated=protection_violated,
        measurable_count=measurable_count,
        score=score,
        target_count=len(targets),
    )
    notes.extend(rule_failures)

    # Decide decision_mode
    if measurable_count == 0:
        decision_mode = "deferred"
    elif keep_change:
        decision_mode = "measured"
    else:
        decision_mode = "measured_reject"

    return EvaluationResult(
        engine=request.engine or "sonic",
        score=round(score, 4),
        keep_change=keep_change,
        goal_progress=round(total_goal_progress, 4),
        collateral_damage=round(collateral_damage, 4),
        hard_rule_failures=rule_failures,
        dimension_changes=dimension_changes,
        notes=notes,
        decision_mode=decision_mode,
        memory_candidate=keep_change and measurable_count > 0,
    )


# ── Composition Evaluator ────────────────────────────────────────────


def evaluate_composition_move(
    before_issues: list[dict],
    after_issues: list[dict],
) -> EvaluationResult:
    """Evaluate a composition move by comparing issue lists.

    Wraps the existing composition evaluation logic using the
    canonical EvaluationResult contract.

    Args:
        before_issues: list of dicts with at least "severity" (float).
        after_issues: list of dicts with at least "severity" (float).

    Returns:
        EvaluationResult with score, keep_change, notes.
    """
    notes: list[str] = []

    before_count = len(before_issues)
    after_count = len(after_issues)
    issue_delta = before_count - after_count

    before_severity = sum(i.get("severity", 0.0) for i in before_issues)
    after_severity = sum(i.get("severity", 0.0) for i in after_issues)
    severity_improvement = before_severity - after_severity

    if before_count > 0:
        improvement_ratio = severity_improvement / max(before_severity, 0.01)
    else:
        improvement_ratio = 0.0 if after_count == 0 else -0.5

    score = max(0.0, min(1.0, 0.5 + improvement_ratio * 0.5))

    keep_change = True

    if severity_improvement < 0:
        keep_change = False
        notes.append(
            f"WORSE: total severity increased by {-severity_improvement:.2f}"
        )

    if after_count > before_count + 1:
        keep_change = False
        notes.append(
            f"NEW ISSUES: {after_count - before_count} new issues introduced"
        )

    if score < 0.40:
        keep_change = False
        notes.append(f"SCORE: {score:.3f} below 0.40 threshold")

    if keep_change and severity_improvement > 0:
        notes.append(
            f"IMPROVED: resolved {issue_delta} issue(s), "
            f"severity reduced by {severity_improvement:.2f}"
        )

    hard_rule_failures = [n for n in notes if n.startswith(("WORSE:", "NEW ISSUES:", "SCORE:"))]

    return EvaluationResult(
        engine="composition",
        score=round(score, 4),
        keep_change=keep_change,
        goal_progress=round(severity_improvement, 4),
        collateral_damage=0.0,
        hard_rule_failures=hard_rule_failures,
        dimension_changes={"issue_delta": issue_delta},
        notes=notes,
        decision_mode="measured",
        memory_candidate=keep_change and severity_improvement > 0,
    )


# ── Mix Evaluator ───────────────────────────────────────────────────


def evaluate_mix_move(
    before_issues: list[dict],
    after_issues: list[dict],
) -> EvaluationResult:
    """Evaluate a mix move by comparing mix critic issue lists.

    Scores masking reduction, punch change, headroom, stereo stability
    and applies hard rules from policy.py.

    Args:
        before_issues: list of MixIssue dicts (from run_all_mix_critics).
        after_issues: list of MixIssue dicts (from run_all_mix_critics).

    Returns:
        EvaluationResult with score, keep_change, dimension_changes.
    """
    notes: list[str] = []

    # Severity helpers per critic category
    def _severity_for(issues: list[dict], critic: str) -> float:
        return sum(i.get("severity", 0.0) for i in issues if i.get("critic") == critic)

    # Track four key dimensions
    before_masking = _severity_for(before_issues, "masking")
    after_masking = _severity_for(after_issues, "masking")
    masking_delta = before_masking - after_masking  # positive = improvement

    before_dynamics = _severity_for(before_issues, "dynamics")
    after_dynamics = _severity_for(after_issues, "dynamics")
    headroom_delta = before_dynamics - after_dynamics

    before_stereo = _severity_for(before_issues, "stereo")
    after_stereo = _severity_for(after_issues, "stereo")
    stereo_delta = before_stereo - after_stereo

    before_balance = _severity_for(before_issues, "balance")
    after_balance = _severity_for(after_issues, "balance")
    balance_delta = before_balance - after_balance

    dimension_changes = {
        "masking_reduction": round(masking_delta, 4),
        "headroom_change": round(headroom_delta, 4),
        "stereo_stability": round(stereo_delta, 4),
        "balance_change": round(balance_delta, 4),
    }

    # Overall severity comparison
    before_total = sum(i.get("severity", 0.0) for i in before_issues)
    after_total = sum(i.get("severity", 0.0) for i in after_issues)
    severity_improvement = before_total - after_total

    before_count = len(before_issues)
    after_count = len(after_issues)

    if before_total > 0:
        improvement_ratio = severity_improvement / max(before_total, 0.01)
    else:
        improvement_ratio = 0.0 if after_count == 0 else -0.5

    score = _clamp(0.5 + improvement_ratio * 0.5)

    # Hard-rule style checks
    keep_change = True

    if severity_improvement < 0:
        keep_change = False
        notes.append(
            f"WORSE: total mix severity increased by {-severity_improvement:.2f}"
        )

    if after_count > before_count + 2:
        keep_change = False
        notes.append(
            f"NEW ISSUES: {after_count - before_count} new mix issues introduced"
        )

    if score < 0.40:
        keep_change = False
        notes.append(f"SCORE: {score:.3f} below 0.40 threshold")

    if keep_change and severity_improvement > 0:
        notes.append(
            f"IMPROVED: mix severity reduced by {severity_improvement:.2f} "
            f"across {before_count - after_count} fewer issues"
        )

    hard_rule_failures = [
        n for n in notes if n.startswith(("WORSE:", "NEW ISSUES:", "SCORE:"))
    ]

    return EvaluationResult(
        engine="mix",
        score=round(score, 4),
        keep_change=keep_change,
        goal_progress=round(severity_improvement, 4),
        collateral_damage=0.0,
        hard_rule_failures=hard_rule_failures,
        dimension_changes=dimension_changes,
        notes=notes,
        decision_mode="measured",
        memory_candidate=keep_change and severity_improvement > 0,
    )


# ── Transition Evaluator ────────────────────────────────────────────


def evaluate_transition(
    before_score: dict,
    after_score: dict,
) -> EvaluationResult:
    """Evaluate a transition move by comparing TransitionScore dicts.

    Compares boundary_clarity, payoff_strength, energy_redirection,
    and overall_quality before and after the move.

    Args:
        before_score: dict with transition quality metrics.
        after_score: dict with transition quality metrics.

    Returns:
        EvaluationResult with score, keep_change, dimension_changes.
    """
    notes: list[str] = []

    # Key transition dimensions to compare
    dims = ["boundary_clarity", "payoff_strength", "energy_redirection", "overall_quality"]
    dimension_changes: dict[str, dict] = {}
    total_improvement = 0.0
    measured = 0

    for dim in dims:
        bv = before_score.get(dim)
        av = after_score.get(dim)
        if bv is not None and av is not None:
            delta = av - bv
            dimension_changes[dim] = {
                "before": round(bv, 4),
                "after": round(av, 4),
                "delta": round(delta, 4),
            }
            total_improvement += delta
            measured += 1

    avg_improvement = total_improvement / max(measured, 1)
    score = _clamp(0.5 + avg_improvement)

    keep_change = True

    if measured > 0 and total_improvement < 0:
        keep_change = False
        notes.append(
            f"WORSE: transition quality decreased by {-total_improvement:.3f}"
        )

    if score < 0.40:
        keep_change = False
        notes.append(f"SCORE: {score:.3f} below 0.40 threshold")

    if keep_change and total_improvement > 0:
        notes.append(
            f"IMPROVED: transition quality improved by {total_improvement:.3f} "
            f"across {measured} dimensions"
        )

    hard_rule_failures = [
        n for n in notes if n.startswith(("WORSE:", "SCORE:"))
    ]

    return EvaluationResult(
        engine="transition",
        score=round(score, 4),
        keep_change=keep_change,
        goal_progress=round(total_improvement, 4),
        collateral_damage=0.0,
        hard_rule_failures=hard_rule_failures,
        dimension_changes=dimension_changes,
        notes=notes,
        decision_mode="measured",
        memory_candidate=keep_change and total_improvement > 0,
    )


# ── Translation Evaluator ───────────────────────────────────────────


def evaluate_translation(
    before_report: dict,
    after_report: dict,
) -> EvaluationResult:
    """Evaluate a translation move by comparing TranslationReport dicts.

    Compares robustness booleans (mono_safe, small_speaker_safe,
    low_end_stable, front_element_present) and harshness_risk.

    Args:
        before_report: dict from build_translation_report().to_dict().
        after_report: dict from build_translation_report().to_dict().

    Returns:
        EvaluationResult with score, keep_change, dimension_changes.
    """
    notes: list[str] = []
    dimension_changes: dict[str, dict] = {}

    # Boolean robustness flags — True is good, False is bad
    bool_dims = ["mono_safe", "small_speaker_safe", "low_end_stable", "front_element_present"]
    improvements = 0
    regressions = 0

    for dim in bool_dims:
        bv = before_report.get(dim)
        av = after_report.get(dim)
        if bv is not None and av is not None:
            dimension_changes[dim] = {"before": bv, "after": av}
            if not bv and av:
                improvements += 1
            elif bv and not av:
                regressions += 1

    # Harshness risk — lower is better
    bh = before_report.get("harshness_risk", 0.0)
    ah = after_report.get("harshness_risk", 0.0)
    harshness_delta = bh - ah  # positive = improvement
    dimension_changes["harshness_risk"] = {
        "before": round(bh, 4),
        "after": round(ah, 4),
        "delta": round(harshness_delta, 4),
    }

    # Overall robustness classification
    robustness_map = {"robust": 1.0, "fragile": 0.5, "critical": 0.0}
    before_rob = robustness_map.get(before_report.get("overall_robustness", ""), 0.5)
    after_rob = robustness_map.get(after_report.get("overall_robustness", ""), 0.5)
    robustness_delta = after_rob - before_rob
    dimension_changes["overall_robustness"] = {
        "before": before_report.get("overall_robustness", "unknown"),
        "after": after_report.get("overall_robustness", "unknown"),
    }

    # Composite score
    flag_score = (improvements - regressions) / max(len(bool_dims), 1)
    score = _clamp(
        0.5
        + flag_score * 0.3
        + harshness_delta * 0.3
        + robustness_delta * 0.4
    )

    total_improvement = flag_score + harshness_delta + robustness_delta

    keep_change = True

    if regressions > improvements:
        keep_change = False
        notes.append(
            f"WORSE: {regressions} robustness flags regressed vs "
            f"{improvements} improved"
        )

    if after_rob < before_rob:
        keep_change = False
        notes.append(
            f"WORSE: overall robustness degraded from "
            f"{before_report.get('overall_robustness')} to "
            f"{after_report.get('overall_robustness')}"
        )

    if score < 0.40:
        keep_change = False
        notes.append(f"SCORE: {score:.3f} below 0.40 threshold")

    if keep_change and total_improvement > 0:
        notes.append(
            f"IMPROVED: {improvements} robustness flags improved, "
            f"harshness reduced by {harshness_delta:.3f}"
        )

    hard_rule_failures = [
        n for n in notes if n.startswith(("WORSE:", "SCORE:"))
    ]

    return EvaluationResult(
        engine="translation",
        score=round(score, 4),
        keep_change=keep_change,
        goal_progress=round(total_improvement, 4),
        collateral_damage=0.0,
        hard_rule_failures=hard_rule_failures,
        dimension_changes=dimension_changes,
        notes=notes,
        decision_mode="measured",
        memory_candidate=keep_change and total_improvement > 0,
    )


# ── Unified Entry Point ─────────────────────────────────────────────


def evaluate(request: EvaluationRequest) -> EvaluationResult:
    """Unified evaluation entry point — routes to engine-specific evaluator.

    Args:
        request: EvaluationRequest with engine field determining routing:
            - "sonic"       -> evaluate_sonic_move
            - "composition" -> evaluate_composition_move
            - "mix"         -> evaluate_mix_move
            - "transition"  -> evaluate_transition
            - "translation" -> evaluate_translation

    Returns:
        EvaluationResult from the appropriate engine evaluator.
    """
    engine = (request.engine or "sonic").lower()

    if engine == "sonic":
        return evaluate_sonic_move(request)

    elif engine == "composition":
        before_issues = request.before.get("issues", [])
        after_issues = request.after.get("issues", [])
        return evaluate_composition_move(before_issues, after_issues)

    elif engine == "mix":
        before_issues = request.before.get("issues", [])
        after_issues = request.after.get("issues", [])
        return evaluate_mix_move(before_issues, after_issues)

    elif engine == "transition":
        return evaluate_transition(request.before, request.after)

    elif engine == "translation":
        return evaluate_translation(request.before, request.after)

    else:
        return EvaluationResult(
            engine=engine,
            score=0.0,
            keep_change=True,
            decision_mode="deferred",
            notes=[f"Unknown engine '{engine}' — deferring to agent judgment"],
        )
