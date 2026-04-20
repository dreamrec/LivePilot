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
    defer_on_unmeasurable: bool = True,
) -> tuple[bool, list[str]]:
    """Enforce hard rules and return (keep_change, failure_reasons).

    Rules (evaluated in order):
    1. (optional) All targets unmeasurable + no protection violation
       -> defer to agent. Fires only when defer_on_unmeasurable=True
       (the default). The evaluation fabric relies on this to mark
       decision_mode="deferred". Score-producing evaluators (branch
       lifecycle, PR7) pass defer_on_unmeasurable=False because the
       score IS the judgment — no deferral needed.
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
        defer_on_unmeasurable: when True (default), rule 1 returns
            (True, [defer message]) as soon as no measurable targets
            exist. When False, rule 1 is skipped and rules 2-4 run
            unconditionally.

    Returns:
        (keep_change, list_of_rule_failure_reasons)
    """
    failures: list[str] = []

    # Rule 1: all unmeasurable + no protection violation -> defer
    if (
        defer_on_unmeasurable
        and measurable_count == 0
        and not protection_violated
    ):
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


def derive_goal_progress_from_fingerprint(
    fingerprint_diff: dict,
    target: Optional[dict] = None,
) -> tuple[float, int]:
    """Derive (goal_progress, measurable_count) from a fingerprint diff.

    PR4 wiring: TimbralFingerprint dimensions (brightness, warmth, bite,
    softness, instability, width, texture_density, movement, polish) are
    effectively a goal vector. When a branch has before/after fingerprints
    extracted from actual captured audio, the per-dimension diff IS the
    measurable evidence classify_branch_outcome needs to make a real
    decision — no reason to fall back to the heuristic score alone.

    fingerprint_diff: output of synthesis_brain.diff_fingerprint(before, after).
      Shape: {"brightness": float, "warmth": float, ...}
    target: optional TimbralFingerprint dict ({"brightness": 0.3, ...}).
      When provided, goal_progress counts only dimensions the target
      cared about (non-zero target value). When None, every dimension
      with a non-trivial diff counts as a target.

    Returns:
      (goal_progress, measurable_count) tuple ready to feed into
      classify_branch_outcome. goal_progress is signed (positive =
      branch moved in the intended direction; negative = moved away).
      measurable_count is how many dimensions had a readable diff.
    """
    if not fingerprint_diff:
        return (0.0, 0)

    # Epsilon — diffs this small are noise, not signal.
    eps = 0.02
    progress = 0.0
    count = 0

    # If target is provided, score each dimension by
    #   sign(target) * diff
    # so moving in the target's direction counts positive, regardless
    # of target magnitude. When no target, count any non-trivial diff
    # in either direction as progress (a branch that "moves" at all
    # is evidence the producer did something).
    if target:
        for dim, delta in fingerprint_diff.items():
            if not isinstance(delta, (int, float)):
                continue
            if abs(delta) < eps:
                continue
            target_val = target.get(dim, 0.0)
            if abs(target_val) < eps:
                continue  # target didn't care about this dimension
            count += 1
            # Normalize: sign(target) * delta, scaled so each dimension
            # contributes at most 1.0 to progress.
            direction = 1.0 if target_val > 0 else -1.0
            progress += direction * max(-1.0, min(1.0, delta))
    else:
        for dim, delta in fingerprint_diff.items():
            if not isinstance(delta, (int, float)):
                continue
            if abs(delta) < eps:
                continue
            count += 1
            # Without a target, we can't tell "good" from "bad" movement.
            # Count as weakly positive — branch did something measurable.
            progress += abs(max(-1.0, min(1.0, delta))) * 0.5

    return (round(progress, 3), count)


def classify_branch_outcome(
    score: float,
    *,
    protection_violated: bool = False,
    measurable_count: int = 0,
    target_count: int = 0,
    goal_progress: float = 0.0,
    exploration_rules: bool = False,
    fingerprint_diff: Optional[dict] = None,
    timbral_target: Optional[dict] = None,
) -> BranchOutcome:
    """Classify a branch's terminal status from a score + optional hard-rule inputs.

    Delegates to apply_hard_rules with ``defer_on_unmeasurable=False`` — a
    score-producing evaluator DID make a judgment, so rule 1's deferral
    path is not appropriate here. The score alone is enough to push a
    branch toward undo / interesting_but_failed.

    Post-processing:
      - ``exploration_rules=False`` (technical safety, default):
        any hard-rule failure ⇒ status="undo".
      - ``exploration_rules=True`` (creative exploration):
        protection violations still force undo (safety invariant);
        all other failures downgrade to "interesting_but_failed".

    PR4 additions (optional):
      fingerprint_diff: output of synthesis_brain.diff_fingerprint
        between before/after snapshots. When provided AND no caller-
        supplied measurable_count/goal_progress were passed (both 0),
        the classifier derives them from the diff — so the dimensions
        of the TimbralFingerprint become the goal vector.
      timbral_target: optional target fingerprint dict. Scores diff in
        the target's direction (moving brighter counts positive when
        target.brightness > 0). Omit when the branch had no specific
        target; dimensions with non-trivial movement still contribute
        measurable_count but progress is unsigned magnitude * 0.5.

    Returns a BranchOutcome that callers can plug into branch.score /
    .status / .evaluation without further interpretation.
    """
    # PR4 — derive measurable evidence from fingerprint diff when the
    # caller didn't supply their own. Keeps back-compat for existing
    # callers that compute their own measurable inputs.
    if (
        fingerprint_diff
        and measurable_count == 0
        and abs(goal_progress) < 1e-6
    ):
        derived_progress, derived_count = derive_goal_progress_from_fingerprint(
            fingerprint_diff, target=timbral_target,
        )
        goal_progress = derived_progress
        measurable_count = derived_count
        # target_count should also reflect the derived dimensions so the
        # hard-rule path treats this as a genuinely measurable outcome.
        target_count = max(target_count, derived_count)
    keep_change, failures = apply_hard_rules(
        goal_progress=goal_progress,
        collateral_damage=0.0,  # not threaded here — branch lifecycle doesn't compute it yet
        protection_violated=protection_violated,
        measurable_count=measurable_count,
        score=score,
        target_count=target_count,
        defer_on_unmeasurable=False,
    )

    if keep_change:
        return BranchOutcome(
            status="keep",
            keep_change=True,
            score=score,
            failure_reasons=[],
            note="",
        )

    # Failed — decide between undo and interesting_but_failed.
    protection_failure = any("protected dimension" in f for f in failures)

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
