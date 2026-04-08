"""Evaluation Contracts — shared types for all engine evaluators.

Defines the canonical evaluation request/result types and the
authoritative registry of which quality dimensions are measurable.

All engines should produce EvaluationResult objects. The Evaluation
Fabric (Phase 1D) will consume these through a unified interface.

Design: EVALUATION_FABRIC_V1.md, section 6
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


# ── Dimension Registry ───────────────────────────────────────────────

# Authoritative registry: dimensions with working spectral proxies.
# If it's not here, it's unmeasurable in current phase and the evaluator
# must report confidence=0.0 for that dimension.
MEASURABLE_DIMENSIONS: frozenset[str] = frozenset({
    "brightness", "warmth", "weight", "clarity",
    "density", "energy", "punch",
})

# All valid quality dimensions (measurable + unmeasurable).
ALL_DIMENSIONS: frozenset[str] = frozenset({
    "energy", "punch", "weight", "density", "brightness", "warmth",
    "width", "depth", "motion", "contrast", "clarity", "cohesion",
    "groove", "tension", "novelty", "polish", "emotion",
})


def is_dimension_measurable(dim: str) -> bool:
    """Check if a dimension has a working spectral proxy."""
    return dim in MEASURABLE_DIMENSIONS


# ── Evaluation Request ───────────────────────────────────────────────

@dataclass
class EvaluationRequest:
    """Canonical evaluation request — engine-agnostic.

    All engines submit evaluation through this shape. The Evaluation
    Fabric routes to the appropriate engine-specific evaluator.
    """
    engine: str
    goal: dict = field(default_factory=dict)
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    protect: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Evaluation Result ────────────────────────────────────────────────

@dataclass
class EvaluationResult:
    """Canonical evaluation result — all engines produce this shape.

    Fields:
        engine: which engine produced this result
        score: 0-1 composite quality score
        keep_change: should the move be kept?
        goal_progress: -1 to 1, how much the goal improved
        collateral_damage: 0-1, harm to protected dimensions
        hard_rule_failures: list of rule names that triggered
        dimension_changes: {dim: {before, after, delta}}
        notes: human-readable explanation
        decision_mode: "measured", "judgment", or "deferred"
        memory_candidate: should this outcome be saved to memory?
    """
    engine: str
    score: float = 0.0
    keep_change: bool = True
    goal_progress: float = 0.0
    collateral_damage: float = 0.0
    hard_rule_failures: list[str] = field(default_factory=list)
    dimension_changes: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    decision_mode: str = "measured"
    memory_candidate: bool = False

    def to_dict(self) -> dict:
        return asdict(self)
