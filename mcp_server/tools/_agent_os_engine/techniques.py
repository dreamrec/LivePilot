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

from .models import TechniqueCard

def build_technique_card_from_outcome(outcome: dict) -> Optional[TechniqueCard]:
    """Extract a technique card from a successful outcome.

    Only produces a card if the outcome was kept and had meaningful improvement.
    """
    if not outcome.get("kept", False):
        return None
    if outcome.get("score", 0) < 0.6:
        return None

    gv = outcome.get("goal_vector", {})
    move = outcome.get("move", {})
    dim_changes = outcome.get("dimension_changes", {})

    # Build problem description from goal
    targets = gv.get("targets", {})
    if not targets:
        return None

    top_dim = max(targets.items(), key=lambda x: x[1])[0] if targets else "general"
    problem = f"Improve {top_dim} in production"

    # Build method from move
    method = move.get("name", "unknown technique")
    if isinstance(move.get("actions"), list):
        method = " → ".join(move["actions"])

    # Build verification from dimension changes
    verification = []
    for dim, change in dim_changes.items():
        if isinstance(change, dict) and change.get("delta", 0) > 0:
            verification.append(f"{dim} should improve (was +{change['delta']:.3f})")

    return TechniqueCard(
        problem=problem,
        context=list(gv.get("tags", [])) if isinstance(gv.get("tags"), list) else [],
        devices=move.get("devices", []) if isinstance(move.get("devices"), list) else [],
        method=method,
        verification=verification,
        evidence={"score": outcome.get("score", 0), "in_session_tested": True},
    )


# ── Background Technique Mining (Round 3) ───────────────────────────
def should_mine_technique(
    outcome: dict,
    existing_techniques: Optional[list[dict]] = None,
) -> bool:
    """Determine if an outcome is novel enough to auto-create a technique card.

    Returns True if:
    - Score > 0.7 (high quality)
    - At least one dimension improved by > 0.15
    - No similar technique already exists in memory
    """
    if not outcome.get("kept", False):
        return False
    if outcome.get("score", 0) < 0.7:
        return False

    # Check for meaningful dimension improvement
    dim_changes = outcome.get("dimension_changes", {})
    has_significant_improvement = False
    for dim, change in dim_changes.items():
        delta = change.get("delta", 0) if isinstance(change, dict) else 0
        if delta > 0.15:
            has_significant_improvement = True
            break

    if not has_significant_improvement:
        return False

    # Check for novelty — don't create duplicate techniques
    if existing_techniques:
        move = outcome.get("move", {})
        move_name = move.get("name", "") if isinstance(move, dict) else ""
        if move_name:
            for tech in existing_techniques:
                payload = tech.get("payload", {})
                existing_method = payload.get("method", "")
                if move_name.lower() in existing_method.lower():
                    return False  # Similar technique already exists

    return True

def mine_technique_from_outcome(outcome: dict) -> Optional[TechniqueCard]:
    """Extract a technique card from a high-quality outcome.

    This is the "background mining" — when the agent detects a novel
    approach that worked well, it auto-creates a technique card for future use.
    """
    if not outcome.get("kept", False):
        return None

    gv = outcome.get("goal_vector", {})
    move = outcome.get("move", {})
    dim_changes = outcome.get("dimension_changes", {})
    score = outcome.get("score", 0)

    # Build problem description
    targets = gv.get("targets", {})
    if targets:
        top_dims = sorted(targets.items(), key=lambda x: -x[1])[:2]
        problem = f"Improve {' and '.join(d for d, _ in top_dims)}"
    else:
        problem = "General production improvement"

    # Build method
    move_name = move.get("name", "unknown") if isinstance(move, dict) else str(move)
    actions = move.get("actions", []) if isinstance(move, dict) else []
    if isinstance(actions, list) and actions:
        method = f"{move_name}: {' → '.join(str(a) for a in actions)}"
    else:
        method = move_name

    # Build verification from what actually improved
    verification = []
    for dim, change in dim_changes.items():
        if isinstance(change, dict) and change.get("delta", 0) > 0.05:
            verification.append(
                f"{dim} should improve (observed +{change['delta']:.3f})"
            )

    # Devices used
    devices = move.get("devices", []) if isinstance(move, dict) else []
    if not isinstance(devices, list):
        devices = []

    return TechniqueCard(
        problem=problem,
        context=list(gv.get("tags", [])) if isinstance(gv.get("tags"), list) else [],
        devices=devices,
        method=method,
        verification=verification,
        evidence={
            "score": score,
            "in_session_tested": True,
            "auto_mined": True,
            "dimension_improvements": {
                dim: change.get("delta", 0)
                for dim, change in dim_changes.items()
                if isinstance(change, dict) and change.get("delta", 0) > 0
            },
        },
    )

