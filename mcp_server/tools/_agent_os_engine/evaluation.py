"""Part of the _agent_os_engine package — extracted from the single-file engine.

Pure-computation core. Callers should import from the package facade
(`from mcp_server.tools._agent_os_engine import X`), which re-exports from
these sub-modules.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .models import QUALITY_DIMENSIONS, GoalVector, WorldModel, _clamp
from .taste import compute_taste_fit


# ── Evaluation Engine ─────────────────────────────────────────────────
# _clamp lives in .models — shared with taste.py to avoid circular imports.

def _extract_dimension_value(
    sonic: dict,
    dimension: str,
) -> Optional[float]:
    """Map a quality dimension to a measurable value from sonic data.

    Returns None for unmeasurable dimensions (confidence=0.0 in Phase 1).
    All returned values are clamped to 0.0-1.0 for consistent scoring.
    """
    if not sonic:
        return None
    # Accept both "spectrum" and "bands" keys — get_master_spectrum returns
    # {"bands": {...}} while the evaluator historically expected {"spectrum": {...}}.
    # Finding 2 fix: tolerate either shape so raw analyzer output works.
    bands = sonic.get("spectrum") or sonic.get("bands")
    if not bands:
        return None
    rms = sonic.get("rms")
    peak = sonic.get("peak")

    if dimension == "brightness":
        high = bands.get("high", 0)
        presence = bands.get("presence", 0)
        return _clamp((high + presence) / 2.0)
    elif dimension == "warmth":
        return _clamp(bands.get("low_mid", 0))
    elif dimension == "weight":
        sub = bands.get("sub", 0)
        low = bands.get("low", 0)
        return _clamp((sub + low) / 2.0)
    elif dimension == "clarity":
        low_mid = bands.get("low_mid", 0)
        return _clamp(1.0 - low_mid)
    elif dimension == "density":
        # Spectral flatness: geometric mean / arithmetic mean of band values.
        # Higher = more evenly distributed energy (noise-like).
        # Lower = more tonal (energy concentrated in few bands).
        vals = [max(v, 1e-10) for v in bands.values() if isinstance(v, (int, float))]
        if not vals:
            return None
        geo_mean = math.exp(sum(math.log(v) for v in vals) / len(vals))
        arith_mean = sum(vals) / len(vals)
        return _clamp(geo_mean / max(arith_mean, 1e-10))
    elif dimension == "energy":
        return _clamp(rms) if rms is not None else None
    elif dimension == "punch":
        if rms and peak and rms > 0:
            crest_db = 20.0 * math.log10(max(peak / rms, 1.0))
            # Normalize: 0 dB = 0.0, 20 dB = 1.0
            return _clamp(crest_db / 20.0)
        return None
    else:
        # Unmeasurable in Phase 1 (width, depth, motion, contrast,
        # groove, tension, novelty, polish, emotion, cohesion)
        return None

def compute_evaluation_score(
    goal: GoalVector,
    before_sonic: dict,
    after_sonic: dict,
    outcome_history: Optional[list[dict]] = None,
) -> dict:
    """Compute whether a move improved the mix toward the goal.

    Returns:
        {
            "score": float (0-1),
            "keep_change": bool,
            "goal_progress": float (-1 to 1),
            "collateral_damage": float (0-1),
            "measurable_delta": float (-1 to 1),
            "notes": list[str],
            "dimension_changes": dict,
            "consecutive_undo_hint": bool,
        }
    """
    notes: list[str] = []
    dimension_changes: dict[str, dict] = {}

    # Compute per-dimension deltas
    total_goal_progress = 0.0
    measurable_count = 0

    for dim, weight in goal.targets.items():
        before_val = _extract_dimension_value(before_sonic, dim)
        after_val = _extract_dimension_value(after_sonic, dim)

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

    # Check protected dimensions (C3 fix: use the actual threshold)
    collateral_damage = 0.0
    protection_violated = False

    for dim, threshold in goal.protect.items():
        before_val = _extract_dimension_value(before_sonic, dim)
        after_val = _extract_dimension_value(after_sonic, dim)

        if before_val is not None and after_val is not None:
            drop = before_val - after_val
            if drop > 0:
                collateral_damage = max(collateral_damage, drop)
            # Violation: value dropped below the user's threshold
            if after_val < threshold:
                protection_violated = True
                notes.append(
                    f"PROTECTED dimension '{dim}' at {after_val:.3f}, "
                    f"below threshold {threshold:.3f}"
                )
            # Also flag large drops even if still above threshold
            elif drop > 0.15:
                protection_violated = True
                notes.append(
                    f"PROTECTED dimension '{dim}' dropped by {drop:.3f} "
                    f"(absolute drop > 0.15)"
                )

    # Measurable delta (average improvement across measured dimensions)
    measurable_delta = total_goal_progress / max(measurable_count, 1)

    # Taste fit: how well does this move align with user preferences?
    taste_fit = compute_taste_fit(goal, outcome_history) if outcome_history else 0.0

    # Compute composite score (spec section 12.2)
    goal_fit = _clamp(0.5 + total_goal_progress)
    measurable_component = _clamp(0.5 + measurable_delta)
    preservation = _clamp(1.0 - collateral_damage * 5)
    confidence = measurable_count / max(len(goal.targets), 1)

    score = (
        0.30 * goal_fit
        + 0.25 * measurable_component
        + 0.15 * preservation
        + 0.10 * taste_fit
        + 0.10 * confidence
        + 0.10 * 1.0   # reversibility: 1.0 for undo-able moves
    )

    # Hard rules
    keep_change = True

    if measurable_count > 0 and measurable_delta <= 0:
        keep_change = False
        notes.append("HARD RULE: measurable delta <= 0 — no measurable improvement")

    if protection_violated:
        keep_change = False
        notes.append("HARD RULE: protected dimension violated")

    if score < 0.40:
        keep_change = False
        notes.append(f"HARD RULE: total score {score:.3f} < 0.40 threshold")

    if measurable_count == 0 and not protection_violated:
        # All TARGET dimensions unmeasurable AND no protection violations —
        # defer keep/undo to the agent's musical judgment.
        # IMPORTANT: protection violations still force undo even when
        # targets are unmeasurable (Finding 1 fix).
        keep_change = True
        notes.append(
            "No measurable target dimensions — deferring keep/undo to agent musical judgment"
        )

    return {
        "score": round(score, 4),
        "keep_change": keep_change,
        "goal_progress": round(total_goal_progress, 4),
        "collateral_damage": round(collateral_damage, 4),
        "measurable_delta": round(measurable_delta, 4),
        "measurable_dimensions": measurable_count,
        "total_dimensions": len(goal.targets),
        "dimension_changes": dimension_changes,
        "notes": notes,
        # I5: hint for the agent to track consecutive undos
        "consecutive_undo_hint": not keep_change,
    }

