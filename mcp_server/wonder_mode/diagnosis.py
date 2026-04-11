"""Wonder Mode diagnosis builder — pure computation, zero I/O.

Builds a WonderDiagnosis from stuckness report, SongBrain, action
ledger, and open creative threads. Each input is optional — the
builder degrades gracefully.
"""

from __future__ import annotations

from typing import Optional

from .session import WonderDiagnosis


# ── Problem class -> candidate domains mapping ────────────────────

_DOMAIN_MAP: dict[str, list[str]] = {
    "overpolished_loop": ["arrangement", "transition"],
    "identity_unclear": ["sound_design", "mix"],
    "contrast_needed": ["transition", "arrangement", "sound_design"],
    "hook_underdeveloped": ["sound_design", "mix"],
    "too_dense_to_progress": ["mix", "arrangement"],
    "too_safe_to_progress": ["sound_design", "transition"],
    "section_missing": ["arrangement", "transition"],
    "transition_not_earned": ["transition", "arrangement"],
}

_STUCKNESS_THRESHOLD = 0.2  # Below this, treat as user_request


def build_diagnosis(
    stuckness_report: Optional[dict] = None,
    song_brain: Optional[dict] = None,
    action_ledger: Optional[list[dict]] = None,
) -> WonderDiagnosis:
    """Build a WonderDiagnosis from available session state.

    Note: open_threads domain prioritization is deferred — not yet implemented.
    """
    degraded: list[str] = []

    # 1. Determine trigger reason and problem class from stuckness
    trigger_reason = "user_request"
    problem_class = "exploration"
    confidence = 0.0

    # Check action ledger for repeated undos first
    if action_ledger:
        undo_count = sum(1 for a in action_ledger if a.get("kept") is False)
        if undo_count >= 3:
            trigger_reason = "repeated_undos"

    if stuckness_report and stuckness_report.get("confidence", 0) >= _STUCKNESS_THRESHOLD:
        trigger_reason = "stuckness_detected"
        problem_class = stuckness_report.get("primary_rescue_type", "exploration") or "exploration"
        confidence = stuckness_report.get("confidence", 0.0)

    # If trigger is repeated_undos but no stuckness, keep problem_class as exploration
    if trigger_reason == "repeated_undos" and problem_class == "exploration":
        confidence = max(confidence, 0.3)

    # 2. Read SongBrain
    current_identity = ""
    sacred_elements: list[dict] = []

    if song_brain:
        current_identity = song_brain.get("identity_core", "")
        sacred_elements = song_brain.get("sacred_elements", [])
    else:
        degraded.append("song_brain")

    # 3. Map problem_class to candidate domains
    candidate_domains = _DOMAIN_MAP.get(problem_class, [])

    return WonderDiagnosis(
        trigger_reason=trigger_reason,
        problem_class=problem_class,
        current_identity=current_identity,
        sacred_elements=sacred_elements,
        blocked_dimensions=[],
        candidate_domains=list(candidate_domains),  # copy
        confidence=confidence,
        degraded_capabilities=degraded,
    )
