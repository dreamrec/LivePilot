"""Policy — hard rule enforcement for all evaluators.

Consistent keep/undo semantics shared across sonic, composition,
and all future evaluators.

Design: EVALUATION_FABRIC_V1.md, section 8
"""

from __future__ import annotations


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
