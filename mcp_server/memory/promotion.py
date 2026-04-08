"""Promotion rules — decide which ledger entries deserve long-term memory.

Pure Python, zero I/O.  Evaluates LedgerEntry dicts against promotion
criteria and returns structured candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromotionCandidate:
    """A ledger entry evaluated for memory promotion."""

    ledger_entry_id: str
    engine: str
    intent: str
    score: float
    dimension_improvements: dict = field(default_factory=dict)
    eligible: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "ledger_entry_id": self.ledger_entry_id,
            "engine": self.engine,
            "intent": self.intent,
            "score": self.score,
            "dimension_improvements": dict(self.dimension_improvements),
            "eligible": self.eligible,
            "reason": self.reason,
        }


def evaluate_promotion(entry_dict: dict) -> PromotionCandidate:
    """Evaluate a single ledger entry dict for memory promotion.

    Rules:
    - must be kept (kept=True)
    - score >= 0.6
    - at least one dimension improvement > 0.05
    - non-empty intent
    """
    entry_id = entry_dict.get("id", "unknown")
    engine = entry_dict.get("engine", "")
    intent = entry_dict.get("intent", "")
    score = entry_dict.get("score", 0.0)
    kept = entry_dict.get("kept", False)

    # Extract dimension improvements from evaluation sub-dict
    evaluation = entry_dict.get("evaluation", {})
    dimension_improvements = evaluation.get("dimension_improvements", {})

    candidate = PromotionCandidate(
        ledger_entry_id=entry_id,
        engine=engine,
        intent=intent,
        score=score,
        dimension_improvements=dimension_improvements,
    )

    # Rule 1: must be kept
    if not kept:
        candidate.reason = "not kept — entry was undone or rejected"
        return candidate

    # Rule 2: score threshold
    if score < 0.6:
        candidate.reason = f"score too low ({score:.2f} < 0.60)"
        return candidate

    # Rule 3: non-empty intent
    if not intent or not intent.strip():
        candidate.reason = "empty intent — no semantic goal recorded"
        return candidate

    # Rule 4: at least one meaningful dimension improvement
    has_improvement = any(v > 0.05 for v in dimension_improvements.values())
    if not has_improvement:
        candidate.reason = "no dimension improvement > 0.05"
        return candidate

    # All rules pass
    candidate.eligible = True
    candidate.reason = "meets all promotion criteria"
    return candidate


def batch_evaluate_promotions(entries: list[dict]) -> list[PromotionCandidate]:
    """Evaluate multiple entries, return only eligible ones."""
    return [
        c for c in (evaluate_promotion(e) for e in entries) if c.eligible
    ]
