"""Sound Design Engine planner — rank and suggest timbral moves.

Pure computation, zero I/O.  Takes critic issues and sound design state,
returns a ranked list of reversible moves.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .critics import SoundDesignIssue
from .models import SoundDesignState


# ── SoundDesignMove ──────────────────────────────────────────────────


@dataclass
class SoundDesignMove:
    """A single suggested sound-design move."""

    move_type: str = ""
    target_block: str = ""
    description: str = ""
    estimated_impact: float = 0.0
    risk: float = 0.0
    parameters: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# Move type metadata: (scope, base_risk)
# scope: "parameter" < "block" < "chain" — prefer smallest scope
_MOVE_META: dict[str, tuple[str, float]] = {
    "source_balance": ("block", 0.1),
    "filter_contour": ("parameter", 0.1),
    "envelope_shape": ("parameter", 0.1),
    "modulation_injection": ("block", 0.2),
    "spatial_separation": ("block", 0.15),
    "layer_split": ("chain", 0.3),
}

_SCOPE_PENALTY: dict[str, float] = {
    "parameter": 0.0,
    "block": 0.05,
    "chain": 0.15,
}


# ── Planner ──────────────────────────────────────────────────────────


def plan_sound_design_moves(
    issues: list[SoundDesignIssue],
    state: SoundDesignState,
) -> list[SoundDesignMove]:
    """Generate a ranked list of suggested moves from detected issues.

    Ranking: estimated_impact * (1 - risk), highest first.
    Prefers parameter-level moves over chain-level moves.

    Returns an empty list if no issues are present.
    """
    if not issues:
        return []

    moves: list[SoundDesignMove] = []

    for issue in issues:
        for move_type in issue.recommended_moves:
            scope, base_risk = _MOVE_META.get(move_type, ("block", 0.2))
            risk = min(1.0, base_risk + _SCOPE_PENALTY.get(scope, 0.0))
            impact = issue.severity * issue.confidence

            # Pick the first affected block as target, or empty
            target = issue.affected_blocks[0] if issue.affected_blocks else ""

            move = SoundDesignMove(
                move_type=move_type,
                target_block=target,
                description=(
                    f"{move_type} to address {issue.issue_type} "
                    f"({issue.critic} critic)"
                ),
                estimated_impact=round(impact, 3),
                risk=round(risk, 3),
                parameters={
                    "source_issue": issue.issue_type,
                    "source_critic": issue.critic,
                    "severity": issue.severity,
                },
            )
            moves.append(move)

    # Rank: impact * (1 - risk), highest first; tie-break by scope
    def _rank_key(m: SoundDesignMove) -> tuple[float, float]:
        score = m.estimated_impact * (1.0 - m.risk)
        scope, _ = _MOVE_META.get(m.move_type, ("block", 0.2))
        scope_order = _SCOPE_PENALTY.get(scope, 0.0)
        return (-score, scope_order)

    moves.sort(key=_rank_key)
    return moves
