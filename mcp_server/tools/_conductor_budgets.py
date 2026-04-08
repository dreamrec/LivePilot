"""Conductor Budget System — prevents the agent from overcommitting.

Every turn maintains six resource pools: latency, risk, novelty, change,
undo, and research. Mode shapes the initial budget; spend functions enforce
limits and return (updated_budget, allowed) tuples.

Zero external dependencies beyond stdlib.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Tuple


# ── TurnBudget ──────────────────────────────────────────────────────

@dataclass
class TurnBudget:
    """Resource pools for a single agent turn."""

    # Limits
    latency_ms: int = 30000       # max 30s per turn
    risk_points: float = 1.0      # 0-1, how much risk left
    novelty_points: float = 0.5   # 0-1, how much novelty allowed
    change_count: int = 3         # max moves per turn
    undo_count: int = 3           # max consecutive undos before stop
    research_calls: int = 2       # max research calls per turn

    # Tracking
    elapsed_ms: int = 0
    risk_spent: float = 0.0
    novelty_spent: float = 0.0
    changes_made: int = 0
    undos_consecutive: int = 0
    research_used: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ── Mode Presets ────────────────────────────────────────────────────

# Each mode overrides specific budget fields.
# Keys map to TurnBudget field names.
_MODE_PRESETS: dict[str, dict] = {
    "observe": {
        "risk_points": 0.1,
        "novelty_points": 0.1,
        "change_count": 0,
        "research_calls": 0,
        "latency_ms": 15000,
    },
    "improve": {
        # Default values — no overrides needed
    },
    "explore": {
        "risk_points": 1.0,
        "novelty_points": 1.0,
        "change_count": 5,
        "research_calls": 3,
        "latency_ms": 45000,
    },
    "finish": {
        "risk_points": 0.3,
        "novelty_points": 0.1,
        "change_count": 2,
        "research_calls": 1,
        "latency_ms": 20000,
    },
    "diagnose": {
        "risk_points": 0.0,
        "novelty_points": 0.0,
        "change_count": 0,
        "research_calls": 3,
        "latency_ms": 20000,
    },
    "performance": {
        "risk_points": 0.2,
        "novelty_points": 0.1,
        "change_count": 2,
        "undo_count": 1,
        "research_calls": 0,
        "latency_ms": 10000,
    },
}


# ── Budget Factory ──────────────────────────────────────────────────

def create_budget(mode: str = "improve", aggression: float = 0.5) -> TurnBudget:
    """Create a TurnBudget shaped by mode and aggression.

    mode: observe | improve | explore | finish | diagnose | performance
    aggression: 0.0 (subtle) to 1.0 (bold) — scales risk and change limits.
    """
    aggression = max(0.0, min(1.0, float(aggression)))

    budget = TurnBudget()

    # Apply mode preset
    preset = _MODE_PRESETS.get(mode, {})
    for key, value in preset.items():
        setattr(budget, key, value)

    # Aggression scales risk_points and change_count (never below preset floor)
    if mode not in ("observe", "diagnose"):
        base_risk = budget.risk_points
        budget.risk_points = round(base_risk * (0.5 + aggression * 0.5), 3)
        base_changes = budget.change_count
        budget.change_count = max(1, int(base_changes * (0.5 + aggression * 0.5)))

    return budget


# ── Spend Functions ─────────────────────────────────────────────────

def spend_risk(budget: TurnBudget, amount: float) -> Tuple[TurnBudget, bool]:
    """Spend risk points. Returns (updated_budget, allowed)."""
    amount = max(0.0, float(amount))
    remaining = budget.risk_points - budget.risk_spent
    if amount > remaining + 1e-9:
        return budget, False
    budget.risk_spent = round(budget.risk_spent + amount, 6)
    return budget, True


def spend_change(budget: TurnBudget) -> Tuple[TurnBudget, bool]:
    """Record one change. Returns (updated_budget, allowed)."""
    if budget.changes_made >= budget.change_count:
        return budget, False
    budget.changes_made += 1
    # A successful change resets consecutive undo count
    budget.undos_consecutive = 0
    return budget, True


def record_undo(budget: TurnBudget) -> Tuple[TurnBudget, bool]:
    """Record a consecutive undo. Returns False if limit exceeded (should stop)."""
    budget.undos_consecutive += 1
    if budget.undos_consecutive > budget.undo_count:
        return budget, False
    return budget, True


def spend_research(budget: TurnBudget) -> Tuple[TurnBudget, bool]:
    """Spend one research call. Returns (updated_budget, allowed)."""
    if budget.research_used >= budget.research_calls:
        return budget, False
    budget.research_used += 1
    return budget, True


def spend_novelty(budget: TurnBudget, amount: float) -> Tuple[TurnBudget, bool]:
    """Spend novelty points. Returns (updated_budget, allowed)."""
    amount = max(0.0, float(amount))
    remaining = budget.novelty_points - budget.novelty_spent
    if amount > remaining + 1e-9:
        return budget, False
    budget.novelty_spent = round(budget.novelty_spent + amount, 6)
    return budget, True


# ── Budget Queries ──────────────────────────────────────────────────

def is_budget_exhausted(budget: TurnBudget) -> bool:
    """Check if any budget dimension is fully spent."""
    if budget.elapsed_ms >= budget.latency_ms:
        return True
    if budget.risk_spent >= budget.risk_points:
        return True
    if budget.changes_made >= budget.change_count:
        return True
    if budget.undos_consecutive > budget.undo_count:
        return True
    if budget.novelty_spent >= budget.novelty_points:
        return True
    # research_used exhaustion alone doesn't exhaust the budget —
    # running out of research calls just blocks further research.
    return False


def get_budget_summary(budget: TurnBudget) -> dict:
    """Return a human-readable summary of the current budget state."""
    return {
        "latency": {
            "used_ms": budget.elapsed_ms,
            "limit_ms": budget.latency_ms,
            "remaining_ms": max(0, budget.latency_ms - budget.elapsed_ms),
            "exhausted": budget.elapsed_ms >= budget.latency_ms,
        },
        "risk": {
            "spent": round(budget.risk_spent, 3),
            "limit": round(budget.risk_points, 3),
            "remaining": round(max(0.0, budget.risk_points - budget.risk_spent), 3),
            "exhausted": budget.risk_spent >= budget.risk_points,
        },
        "novelty": {
            "spent": round(budget.novelty_spent, 3),
            "limit": round(budget.novelty_points, 3),
            "remaining": round(max(0.0, budget.novelty_points - budget.novelty_spent), 3),
            "exhausted": budget.novelty_spent >= budget.novelty_points,
        },
        "changes": {
            "made": budget.changes_made,
            "limit": budget.change_count,
            "remaining": max(0, budget.change_count - budget.changes_made),
            "exhausted": budget.changes_made >= budget.change_count,
        },
        "undos": {
            "consecutive": budget.undos_consecutive,
            "limit": budget.undo_count,
            "should_stop": budget.undos_consecutive > budget.undo_count,
        },
        "research": {
            "used": budget.research_used,
            "limit": budget.research_calls,
            "remaining": max(0, budget.research_calls - budget.research_used),
            "exhausted": budget.research_used >= budget.research_calls,
        },
        "overall_exhausted": is_budget_exhausted(budget),
    }
