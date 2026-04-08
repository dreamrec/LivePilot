"""Evaluation Fabric — main entry point for unified evaluation.

Provides evaluate_sonic_move() and evaluate_composition_move() which
produce canonical EvaluationResult objects.

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

    score = (
        0.30 * goal_fit
        + 0.25 * measurable_component
        + 0.15 * preservation
        + 0.10 * 0.0   # taste_fit: placeholder, no history in fabric v1
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
        decision_mode = "measured"

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
