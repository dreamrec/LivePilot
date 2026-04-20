"""Policy — hard rule enforcement for all evaluators.

Consistent keep/undo semantics shared across sonic, composition,
and all future evaluators.

Design: EVALUATION_FABRIC_V1.md, section 8

PR7 adds ``classify_branch_outcome`` — a branch-lifecycle classifier that
maps a score (and optional hard-rule inputs) to one of three statuses:
"keep", "undo", "interesting_but_failed". The third status exists for
exploration mode: a branch that failed technical gates but surfaced a
novel idea is kept for audit and never re-applied. Protection violations
still force undo regardless of exploration mode — that's a safety
invariant, not a taste judgment.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Optional


BranchOutcomeStatus = Literal["keep", "undo", "interesting_but_failed"]


def apply_hard_rules(
    goal_progress: float,
    collateral_damage: float,
    protection_violated: bool,
    measurable_count: int,
    score: float,
    target_count: int,
) -> tuple[bool, list[str]]:
    """Enforce hard rules and return (keep_change, failure_reasons).

    Rules (evaluated in order):
    1. All targets unmeasurable + no protection violation -> defer to agent
    2. Protection violated -> force undo
    3. Measurable delta <= 0 when measurable targets exist -> force undo
    4. Score < 0.40 -> force undo

    Args:
        goal_progress: weighted sum of dimension deltas
        collateral_damage: max drop across protected dimensions
        protection_violated: any protected dimension below threshold
        measurable_count: how many target dimensions were measurable
        score: composite quality score (0-1)
        target_count: total number of target dimensions

    Returns:
        (keep_change, list_of_rule_failure_reasons)
    """
    failures: list[str] = []

    # Rule 1: all unmeasurable + no protection violation -> defer
    if measurable_count == 0 and not protection_violated:
        return True, [
            "No measurable target dimensions — deferring keep/undo "
            "to agent musical judgment"
        ]

    # Rule 2: protection violated -> force undo
    if protection_violated:
        failures.append("HARD RULE: protected dimension violated")

    # Rule 3: no measurable improvement -> force undo
    if measurable_count > 0:
        measurable_delta = goal_progress / max(measurable_count, 1)
        if measurable_delta <= 0:
            failures.append(
                "HARD RULE: measurable delta <= 0 — no measurable improvement"
            )

    # Rule 4: score threshold -> force undo
    if score < 0.40:
        failures.append(
            f"HARD RULE: total score {score:.3f} < 0.40 threshold"
        )

    keep_change = len(failures) == 0
    return keep_change, failures


# ── PR7 — branch-lifecycle classifier ────────────────────────────────────


@dataclass
class BranchOutcome:
    """Unified branch evaluation result.

    Fields:
      status: terminal classification — "keep" | "undo" | "interesting_but_failed"
      keep_change: True ⇒ status == "keep"; never True for the other statuses.
      score: the composite score that informed the decision.
      failure_reasons: human-readable list of failed hard rules (empty on keep).
      note: optional explanation aimed at the user.
    """

    status: BranchOutcomeStatus
    keep_change: bool
    score: float
    failure_reasons: list[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def classify_branch_outcome(
    score: float,
    *,
    protection_violated: bool = False,
    measurable_count: int = 0,
    target_count: int = 0,
    goal_progress: float = 0.0,
    exploration_rules: bool = False,
) -> BranchOutcome:
    """Classify a branch's terminal status from a score + optional hard-rule inputs.

    Applies each rule independently — apply_hard_rules' rule 1 ("defer to
    agent judgment when measurable_count=0") is intentionally bypassed here
    because a score-producing evaluator DID make a judgment. The classifier
    trusts the score.

    Rule order:
      1. protection_violated → always undo (safety invariant, ignores exploration_rules)
      2. score < 0.40 → undo (technical) or interesting_but_failed (exploration)
      3. measurable_count > 0 with goal_progress <= 0 → same as rule 2
      4. otherwise keep

    Returns a BranchOutcome that callers can plug into branch.score / .status
    / .evaluation without further interpretation.
    """
    failures: list[str] = []
    protection_failure = False

    # Rule 1 — protection violation (safety invariant)
    if protection_violated:
        failures.append("HARD RULE: protected dimension violated")
        protection_failure = True

    # Rule 2 — score threshold
    if score < 0.40:
        failures.append(
            f"HARD RULE: total score {score:.3f} < 0.40 threshold"
        )

    # Rule 3 — measurable delta
    if measurable_count > 0:
        measurable_delta = goal_progress / max(measurable_count, 1)
        if measurable_delta <= 0:
            failures.append(
                "HARD RULE: measurable delta <= 0 — no measurable improvement"
            )

    if not failures:
        return BranchOutcome(
            status="keep",
            keep_change=True,
            score=score,
            failure_reasons=[],
            note="",
        )

    # Failed — decide between undo and interesting_but_failed.
    if exploration_rules and not protection_failure:
        return BranchOutcome(
            status="interesting_but_failed",
            keep_change=False,
            score=score,
            failure_reasons=failures,
            note=(
                "Exploration rule: branch failed technical gates but is "
                "retained for audit. Not re-applied."
            ),
        )

    return BranchOutcome(
        status="undo",
        keep_change=False,
        score=score,
        failure_reasons=failures,
        note=(
            "Protection violation — branch rolled back regardless of "
            "exploration mode."
            if protection_failure
            else "Branch rolled back per hard rules."
        ),
    )
