"""Mix Engine planner — rank and suggest mix moves.

Pure computation, zero I/O.  Takes critic issues and mix state,
returns a ranked list of reversible moves.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .critics import MixIssue
from .models import MixState


# ── MixMove ─────────────────────────────────────────────────────────


@dataclass
class MixMove:
    """A single suggested mix move."""

    move_type: str = ""
    target_tracks: list[int] = field(default_factory=list)
    description: str = ""
    estimated_impact: float = 0.0
    risk: float = 0.0
    parameters: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# Move type metadata: (scope, base_risk)
# scope: "track" < "bus" < "master" — prefer smallest scope
_MOVE_META: dict[str, tuple[str, float]] = {
    "eq_correction": ("track", 0.1),
    "transient_shaping": ("track", 0.15),
    "saturation_adjustment": ("track", 0.2),
    "width_adjustment": ("track", 0.15),
    "send_rebalance": ("track", 0.1),
    "gain_staging": ("track", 0.05),
    "bus_compression": ("bus", 0.25),
}

_SCOPE_PENALTY: dict[str, float] = {
    "track": 0.0,
    "bus": 0.1,
    "master": 0.2,
}


# ── Planner ─────────────────────────────────────────────────────────


def plan_mix_moves(
    issues: list[MixIssue],
    mix_state: MixState,
) -> list[MixMove]:
    """Generate a ranked list of suggested moves from detected issues.

    Ranking: estimated_impact * (1 - risk), highest first.
    Prefers track-level moves over bus-level moves.

    Returns an empty list if no issues are present.
    """
    if not issues:
        return []

    moves: list[MixMove] = []

    for issue in issues:
        for move_type in issue.recommended_moves:
            scope, base_risk = _MOVE_META.get(move_type, ("track", 0.2))
            risk = min(1.0, base_risk + _SCOPE_PENALTY.get(scope, 0.0))
            impact = issue.severity * issue.confidence

            move = MixMove(
                move_type=move_type,
                target_tracks=list(issue.affected_tracks),
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

    # Rank: impact * (1 - risk), highest first; tie-break by preferring
    # track-level (lower scope penalty).
    def _rank_key(m: MixMove) -> tuple[float, float]:
        score = m.estimated_impact * (1.0 - m.risk)
        scope, _ = _MOVE_META.get(m.move_type, ("track", 0.2))
        scope_order = _SCOPE_PENALTY.get(scope, 0.0)
        return (-score, scope_order)

    moves.sort(key=_rank_key)
    return moves
