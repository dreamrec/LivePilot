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

from .models import QUALITY_DIMENSIONS, _clamp


# store_purpose: technique_library
# analyze_outcome_history consumes payloads from the persistent
# technique library (memory_list(type="outcome")) — NOT recency data.
# Taste-inference work reads accumulated outcome records, unlike
# anti-repetition which reads SessionLedger.get_recent_moves.

# ── Outcome Memory Analysis (Round 1) ────────────────────────────────
def analyze_outcome_history(outcomes: list[dict]) -> dict:
    """Analyze accumulated outcome memories to identify user taste patterns.

    outcomes: list of outcome technique payloads from memory_list(type="outcome")
    Returns taste analysis: keep rate, dimension success, inferred preferences.
    """
    if not outcomes:
        return {
            "total_outcomes": 0,
            "keep_rate": 0.0,
            "dimension_success": {},
            "common_kept_moves": [],
            "common_undone_moves": [],
            "taste_vector": {},
            "notes": ["No outcome history — use the evaluation loop to build taste data"],
        }

    total = len(outcomes)
    kept = [o for o in outcomes if o.get("kept", False)]
    undone = [o for o in outcomes if not o.get("kept", False)]
    keep_rate = len(kept) / total

    # Dimension success: average improvement per dimension when kept
    dimension_success: dict[str, list[float]] = {}
    for o in kept:
        for dim, change in o.get("dimension_changes", {}).items():
            delta = change.get("delta", 0) if isinstance(change, dict) else 0
            dimension_success.setdefault(dim, []).append(delta)

    avg_dimension_success = {
        dim: round(sum(vals) / len(vals), 4)
        for dim, vals in dimension_success.items()
        if vals
    }

    # Common move types
    kept_moves = {}
    undone_moves = {}
    for o in kept:
        move_name = o.get("move", {}).get("name", "unknown") if isinstance(o.get("move"), dict) else "unknown"
        kept_moves[move_name] = kept_moves.get(move_name, 0) + 1
    for o in undone:
        move_name = o.get("move", {}).get("name", "unknown") if isinstance(o.get("move"), dict) else "unknown"
        undone_moves[move_name] = undone_moves.get(move_name, 0) + 1

    common_kept = sorted(kept_moves.items(), key=lambda x: -x[1])[:5]
    common_undone = sorted(undone_moves.items(), key=lambda x: -x[1])[:5]

    # Taste vector: which dimensions does this user care about?
    # Weight by how often each dimension appears in kept outcomes
    taste_vector: dict[str, float] = {}
    for o in kept:
        gv = o.get("goal_vector", {})
        targets = gv.get("targets", {}) if isinstance(gv, dict) else {}
        for dim, weight in targets.items():
            taste_vector[dim] = taste_vector.get(dim, 0) + weight

    # Normalize
    taste_total = sum(taste_vector.values())
    if taste_total > 0:
        taste_vector = {k: round(v / taste_total, 3) for k, v in taste_vector.items()}

    notes = []
    if keep_rate < 0.3:
        notes.append(f"Low keep rate ({keep_rate:.0%}) — agent may be too aggressive")
    if keep_rate > 0.8:
        notes.append(f"High keep rate ({keep_rate:.0%}) — agent is well-calibrated or too conservative")

    return {
        "total_outcomes": total,
        "kept": len(kept),
        "undone": len(undone),
        "keep_rate": round(keep_rate, 3),
        "dimension_success": avg_dimension_success,
        "common_kept_moves": [{"move": m, "count": c} for m, c in common_kept],
        "common_undone_moves": [{"move": m, "count": c} for m, c in common_undone],
        "taste_vector": taste_vector,
        "notes": notes,
    }


# ── Taste Model (Round 4) ────────────────────────────────────────────
def compute_taste_fit(
    goal: GoalVector,
    outcome_history: Optional[list[dict]] = None,
) -> float:
    """Compute how well a goal aligns with the user's accumulated taste preferences.

    Analyzes outcome history to build a taste vector (which dimensions matter
    most to this user), then scores the current goal's alignment.

    Returns 0.0-1.0 where:
    - 0.0 = no data or goal doesn't match taste
    - 1.0 = goal perfectly aligns with user's demonstrated preferences
    """
    if not outcome_history:
        return 0.0

    # Build taste vector from kept outcomes
    taste_vector: dict[str, float] = {}
    total_kept = 0

    for o in outcome_history:
        if not o.get("kept", False):
            continue
        total_kept += 1
        gv = o.get("goal_vector", {})
        targets = gv.get("targets", {}) if isinstance(gv, dict) else {}
        for dim, weight in targets.items():
            taste_vector[dim] = taste_vector.get(dim, 0) + weight

    if not taste_vector or total_kept == 0:
        return 0.0

    # Normalize taste vector
    taste_total = sum(taste_vector.values())
    if taste_total > 0:
        taste_vector = {k: v / taste_total for k, v in taste_vector.items()}

    # Score: how much does the current goal overlap with taste preferences?
    # Dot product of normalized goal weights and taste weights
    goal_targets = goal.targets
    if not goal_targets:
        return 0.0

    goal_total = sum(goal_targets.values())
    if goal_total <= 0:
        return 0.0

    overlap = 0.0
    for dim, weight in goal_targets.items():
        normalized_weight = weight / goal_total
        taste_weight = taste_vector.get(dim, 0)
        overlap += normalized_weight * taste_weight

    # Scale: overlap is typically small (product of two normalized distributions)
    # Amplify so that moderate overlap gives a meaningful score
    return _clamp(overlap * 4.0)

def get_taste_profile(outcome_history: list[dict]) -> dict:
    """Build a full taste profile from outcome history.

    Returns: {taste_vector, preferred_dimensions, avoided_dimensions,
              keep_rate, sample_size}
    """
    analysis = analyze_outcome_history(outcome_history)
    taste_vector = analysis.get("taste_vector", {})

    # Identify preferred and avoided dimensions
    preferred = sorted(taste_vector.items(), key=lambda x: -x[1])[:5]
    avoided_dims: dict[str, float] = {}
    for o in outcome_history:
        if o.get("kept", False):
            continue  # Only look at undone moves
        gv = o.get("goal_vector", {})
        targets = gv.get("targets", {}) if isinstance(gv, dict) else {}
        for dim, weight in targets.items():
            avoided_dims[dim] = avoided_dims.get(dim, 0) + weight

    if avoided_dims:
        avoid_total = sum(avoided_dims.values())
        if avoid_total > 0:
            avoided_dims = {k: v / avoid_total for k, v in avoided_dims.items()}

    avoided = sorted(avoided_dims.items(), key=lambda x: -x[1])[:5]

    return {
        "taste_vector": taste_vector,
        "preferred_dimensions": [{"dim": d, "weight": round(w, 3)} for d, w in preferred],
        "avoided_dimensions": [{"dim": d, "weight": round(w, 3)} for d, w in avoided],
        "keep_rate": analysis.get("keep_rate", 0),
        "sample_size": analysis.get("total_outcomes", 0),
        "notes": analysis.get("notes", []),
    }

