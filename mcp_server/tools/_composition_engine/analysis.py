"""Part of the _composition_engine package — extracted from the single-file engine.

Pure-computation core, no external deps. Callers should import from the package
facade (e.g. `from mcp_server.tools._composition_engine import X`), which
re-exports everything from these sub-modules.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

from .models import SectionNode, CompositionIssue, CompositionAnalysis


# ── Section Outcome Analysis (Round 2) ────────────────────────────────
def analyze_section_outcomes(
    outcomes: list[dict],
) -> dict:
    """Analyze composition outcomes grouped by section type.

    outcomes: list of composition_outcome payloads
    Returns: {section_type: {move_name: {avg_score, count, keep_rate}}}
    """
    by_section: dict[str, list[dict]] = {}

    for o in outcomes:
        section_type = o.get("section_type", "unknown")
        by_section.setdefault(section_type, []).append(o)

    result = {}
    for stype, section_outcomes in by_section.items():
        move_stats: dict[str, dict] = {}
        for o in section_outcomes:
            move = o.get("move_name", "unknown")
            stats = move_stats.setdefault(move, {"scores": [], "kept": 0, "total": 0})
            stats["scores"].append(o.get("score", 0))
            stats["total"] += 1
            if o.get("kept", False):
                stats["kept"] += 1

        result[stype] = {
            move: {
                "avg_score": round(sum(s["scores"]) / len(s["scores"]), 3) if s["scores"] else 0,
                "count": s["total"],
                "keep_rate": round(s["kept"] / s["total"], 3) if s["total"] > 0 else 0,
            }
            for move, s in move_stats.items()
        }

    return {
        "section_types": list(result.keys()),
        "outcomes_by_section": result,
        "total_outcomes": sum(len(v) for v in by_section.values()),
    }


# ── Composition Evaluation ────────────────────────────────────────────
COMPOSITION_DIMENSIONS = frozenset({
    "section_clarity", "phrase_completion", "narrative_pacing",
    "transition_strength", "orchestration_clarity", "tension_release",
})

def evaluate_composition_move(
    before_issues: list[CompositionIssue],
    after_issues: list[CompositionIssue],
    target_dimensions: dict[str, float],
    protect: dict[str, float],
) -> dict:
    """Evaluate whether a composition move improved the arrangement.

    Compares issue counts and severities before and after.
    Returns: {score, keep_change, issue_delta, notes}
    """
    notes: list[str] = []

    # Count issues by type before and after
    before_count = len(before_issues)
    after_count = len(after_issues)
    issue_delta = before_count - after_count

    # Severity-weighted improvement
    before_severity = sum(i.severity for i in before_issues)
    after_severity = sum(i.severity for i in after_issues)
    severity_improvement = before_severity - after_severity

    # Score: positive improvement = good
    if before_count > 0:
        improvement_ratio = severity_improvement / max(before_severity, 0.01)
    else:
        improvement_ratio = 0.0 if after_count == 0 else -0.5

    # Normalize to 0-1 score
    score = max(0.0, min(1.0, 0.5 + improvement_ratio * 0.5))

    # Keep/undo decision
    keep_change = True

    if severity_improvement < 0:
        keep_change = False
        notes.append(f"WORSE: total severity increased by {-severity_improvement:.2f}")

    if after_count > before_count + 1:
        keep_change = False
        notes.append(f"NEW ISSUES: {after_count - before_count} new issues introduced")

    if score < 0.40:
        keep_change = False
        notes.append(f"SCORE: {score:.3f} below 0.40 threshold")

    if keep_change and severity_improvement > 0:
        notes.append(f"IMPROVED: resolved {issue_delta} issue(s), severity reduced by {severity_improvement:.2f}")

    return {
        "score": round(score, 4),
        "keep_change": keep_change,
        "issue_delta": issue_delta,
        "before_issue_count": before_count,
        "after_issue_count": after_count,
        "severity_improvement": round(severity_improvement, 4),
        "notes": notes,
        "consecutive_undo_hint": not keep_change,
    }


# ── Composition Taste Model (Round 4) ───────────────────────────────
def build_composition_taste_model(
    section_outcomes: list[dict],
) -> dict:
    """Build per-section-type preferences from composition outcome history.

    Aggregates section outcomes to learn: what density, foreground count,
    and move types does this user prefer for each section type?

    Returns: {section_type: {preferred_density, preferred_foreground_count,
              top_moves, sample_size}}
    """
    if not section_outcomes:
        return {"section_types": {}, "sample_size": 0}

    by_type: dict[str, list[dict]] = {}
    for o in section_outcomes:
        stype = o.get("section_type", "unknown")
        by_type.setdefault(stype, []).append(o)

    preferences: dict[str, dict] = {}
    for stype, outcomes in by_type.items():
        kept = [o for o in outcomes if o.get("kept", False)]
        densities = [o.get("density", 0.5) for o in kept if "density" in o]
        fg_counts = [o.get("foreground_count", 1) for o in kept if "foreground_count" in o]

        # Tally move types
        move_counts: dict[str, int] = {}
        for o in kept:
            move = o.get("move_name", "unknown")
            move_counts[move] = move_counts.get(move, 0) + 1

        top_moves = sorted(move_counts.items(), key=lambda x: -x[1])[:3]

        preferences[stype] = {
            "preferred_density": round(sum(densities) / len(densities), 2) if densities else 0.5,
            "preferred_foreground_count": round(sum(fg_counts) / len(fg_counts), 1) if fg_counts else 1.0,
            "top_moves": [{"move": m, "count": c} for m, c in top_moves],
            "keep_rate": round(len(kept) / len(outcomes), 3) if outcomes else 0,
            "sample_size": len(outcomes),
        }

    return {
        "section_types": preferences,
        "sample_size": sum(len(v) for v in by_type.values()),
    }

