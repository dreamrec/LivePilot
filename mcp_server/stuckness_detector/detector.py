"""Stuckness detection engine — pure computation, zero I/O.

Analyzes action history, session state, and patterns to detect
when the user is stuck and suggest rescue strategies.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from .models import RescueSuggestion, StucknessReport, StucknessSignal


# ── Main detection ────────────────────────────────────────────────


def detect_stuckness(
    action_history: list[dict],
    session_info: Optional[dict] = None,
    song_brain: Optional[dict] = None,
    section_count: int = 0,
) -> StucknessReport:
    """Detect whether the session is stuck.

    Analyzes action history for repeated undos, local tweaking,
    long loops without structural edits, and other stuckness signals.
    """
    session_info = session_info or {}
    song_brain = song_brain or {}
    signals: list[StucknessSignal] = []

    # 1. Repeated undos
    undo_signal = _check_repeated_undos(action_history)
    if undo_signal:
        signals.append(undo_signal)

    # 2. Local tweaking (many small changes in one area)
    tweak_signal = _check_local_tweaking(action_history)
    if tweak_signal:
        signals.append(tweak_signal)

    # 3. Long loop time without structural edits
    loop_signal = _check_loop_without_structure(action_history, section_count)
    if loop_signal:
        signals.append(loop_signal)

    # 4. Repeated asks without acceptance
    repeat_signal = _check_repeated_requests(action_history)
    if repeat_signal:
        signals.append(repeat_signal)

    # 5. Too many decorative layers
    density_signal = _check_decoration_overload(session_info)
    if density_signal:
        signals.append(density_signal)

    # 6. Identity unclear
    identity_signal = _check_identity_unclear(song_brain)
    if identity_signal:
        signals.append(identity_signal)

    # Compute overall confidence
    if not signals:
        return StucknessReport(confidence=0.0, level="flowing")

    confidence = min(1.0, sum(s.strength for s in signals) / max(len(signals), 1))

    # Determine level
    if confidence > 0.7:
        level = "deeply_stuck"
    elif confidence > 0.45:
        level = "stuck"
    elif confidence > 0.2:
        level = "slowing"
    else:
        level = "flowing"

    # Determine rescue types
    primary, secondary = _classify_rescue_type(signals, song_brain, session_info)
    diagnosis = _build_diagnosis(signals, level)

    return StucknessReport(
        confidence=confidence,
        level=level,
        signals=signals,
        diagnosis=diagnosis,
        primary_rescue_type=primary,
        secondary_rescue_types=secondary,
    )


# ── Signal checkers ───────────────────────────────────────────────


def _check_repeated_undos(history: list[dict]) -> Optional[StucknessSignal]:
    """Check for repeated undo actions."""
    recent = history[-20:] if len(history) > 20 else history
    undo_count = sum(1 for a in recent if a.get("action") == "undo")

    if undo_count >= 4:
        return StucknessSignal(
            signal_type="repeated_undo",
            strength=min(0.8, undo_count * 0.15),
            evidence=f"{undo_count} undos in last {len(recent)} actions",
        )
    return None


def _check_local_tweaking(history: list[dict]) -> Optional[StucknessSignal]:
    """Check for many small parameter changes in one local area."""
    recent = history[-15:] if len(history) > 15 else history
    param_changes = [
        a for a in recent
        if a.get("action") in ("set_device_parameter", "set_track_volume", "set_track_pan",
                                "set_send_level", "set_clip_loop")
    ]

    if len(param_changes) >= 6:
        # Check if they're in the same area
        targets = Counter(a.get("target", "") for a in param_changes)
        most_common = targets.most_common(1)
        if most_common and most_common[0][1] >= 4:
            return StucknessSignal(
                signal_type="local_tweaking",
                strength=min(0.7, len(param_changes) * 0.1),
                evidence=f"{len(param_changes)} parameter tweaks, mostly on {most_common[0][0]}",
            )
    return None


def _check_loop_without_structure(
    history: list[dict], section_count: int
) -> Optional[StucknessSignal]:
    """Check for long work without structural changes."""
    recent = history[-30:] if len(history) > 30 else history
    structural_actions = {"create_clip", "delete_clip", "create_midi_track",
                          "create_audio_track", "delete_track", "duplicate_clip"}
    structural = sum(1 for a in recent if a.get("action") in structural_actions)

    if len(recent) >= 15 and structural == 0:
        return StucknessSignal(
            signal_type="long_loop_no_structure",
            strength=0.5,
            evidence=f"{len(recent)} actions without any structural changes",
        )

    if section_count <= 1 and len(recent) > 20:
        return StucknessSignal(
            signal_type="single_loop",
            strength=0.4,
            evidence="Working in a single loop/scene for extended period",
        )

    return None


def _check_repeated_requests(history: list[dict]) -> Optional[StucknessSignal]:
    """Check for repeated similar requests without acceptance."""
    recent = history[-10:] if len(history) > 10 else history
    requests = [a.get("request", "").lower() for a in recent if a.get("request")]

    if len(requests) >= 3:
        # Check for repetitive keywords
        words = Counter()
        for req in requests:
            for word in req.split():
                if len(word) > 3:
                    words[word] += 1

        repeated = {w: c for w, c in words.items() if c >= 3}
        if repeated:
            return StucknessSignal(
                signal_type="repeated_requests",
                strength=0.5,
                evidence=f"Repeated keywords: {', '.join(repeated.keys())}",
            )
    return None


def _check_decoration_overload(session_info: dict) -> Optional[StucknessSignal]:
    """Check for too many decorative layers without role clarity."""
    track_count = session_info.get("track_count", 0)
    if track_count > 16:
        return StucknessSignal(
            signal_type="high_density",
            strength=min(0.6, (track_count - 16) * 0.05),
            evidence=f"{track_count} tracks — may be too dense to progress",
        )
    return None


def _check_identity_unclear(song_brain: dict) -> Optional[StucknessSignal]:
    """Check if song identity is unclear."""
    confidence = song_brain.get("identity_confidence", 0.5)
    if confidence < 0.3:
        return StucknessSignal(
            signal_type="identity_unclear",
            strength=0.5,
            evidence="Song identity is not clearly established",
        )
    return None


# ── Rescue classification ─────────────────────────────────────────


def _classify_rescue_type(
    signals: list[StucknessSignal],
    song_brain: dict,
    session_info: dict,
) -> tuple[str, list[str]]:
    """Determine the best rescue type from signals."""
    signal_types = {s.signal_type for s in signals}

    primary = "contrast_needed"  # default
    secondary: list[str] = []

    if "identity_unclear" in signal_types:
        primary = "identity_unclear"
        secondary = ["hook_underdeveloped", "too_safe_to_progress"]
    elif "single_loop" in signal_types:
        primary = "overpolished_loop"
        secondary = ["section_missing", "contrast_needed"]
    elif "high_density" in signal_types:
        primary = "too_dense_to_progress"
        secondary = ["contrast_needed", "identity_unclear"]
    elif "local_tweaking" in signal_types:
        primary = "overpolished_loop"
        secondary = ["contrast_needed", "section_missing"]
    elif "repeated_undo" in signal_types:
        primary = "contrast_needed"
        secondary = ["hook_underdeveloped", "too_safe_to_progress"]
    elif "long_loop_no_structure" in signal_types:
        primary = "section_missing"
        secondary = ["contrast_needed", "transition_not_earned"]

    return primary, secondary


# ── Rescue suggestions ────────────────────────────────────────────


def suggest_rescue(
    report: StucknessReport,
    mode: str = "gentle",
) -> list[RescueSuggestion]:
    """Generate rescue suggestions based on stuckness analysis."""
    suggestions: list[RescueSuggestion] = []

    rescue_strategies = {
        "contrast_needed": RescueSuggestion(
            rescue_type="contrast_needed",
            title="Add contrast to break the plateau",
            description="The session needs a moment that feels different from what's been happening.",
            strategies=[
                "Strip everything except the hook for 4-8 bars, then re-enter",
                "Introduce a new timbral element that wasn't there before",
                "Change the harmonic context (try a relative minor/major shift)",
                "Create a rhythmic break — half-time or double-time feel",
            ],
        ),
        "section_missing": RescueSuggestion(
            rescue_type="section_missing",
            title="Add a new section for structural progress",
            description="The track needs more form — a new section would create momentum.",
            strategies=[
                "Create a B section that contrasts the current loop",
                "Add an intro that sets up the main idea",
                "Build a breakdown section that strips to essentials",
                "Design a transition that earns the next section",
            ],
        ),
        "hook_underdeveloped": RescueSuggestion(
            rescue_type="hook_underdeveloped",
            title="Develop the hook before adding more layers",
            description="The most memorable idea needs more attention before the arrangement grows.",
            strategies=[
                "Write a variation of the hook for a different section",
                "Add a countermelody that complements the hook",
                "Create a stripped version of the hook for contrast sections",
                "Make the hook hit harder — better sound design or arrangement support",
            ],
        ),
        "transition_not_earned": RescueSuggestion(
            rescue_type="transition_not_earned",
            title="Build better transitions between sections",
            description="Sections jump abruptly — earn the transitions.",
            strategies=[
                "Add a 2-4 bar transition between sections",
                "Use filter sweeps or risers to build anticipation",
                "Create drum fills or melodic ornaments at section boundaries",
                "Use silence or space before the next section arrives",
            ],
        ),
        "overpolished_loop": RescueSuggestion(
            rescue_type="overpolished_loop",
            title="Stop polishing — move forward structurally",
            description="This loop is getting over-refined. Time to build form.",
            strategies=[
                "Duplicate the scene and subtract elements for a contrasting section",
                "Record a live take over the loop to find new directions",
                "Commit to the current state and start the arrangement",
                "Create a completely different section from scratch",
            ],
        ),
        "identity_unclear": RescueSuggestion(
            rescue_type="identity_unclear",
            title="Define the track's identity before adding more",
            description="It's hard to progress when the track doesn't know what it is.",
            strategies=[
                "Identify or create one defining melodic/rhythmic idea",
                "Choose a reference track and distill its key principles",
                "Remove tracks that don't serve a clear purpose",
                "Write a one-sentence description of what this track should feel like",
            ],
        ),
        "too_dense_to_progress": RescueSuggestion(
            rescue_type="too_dense_to_progress",
            title="Subtract before adding more",
            description="Too many elements fighting for attention. Simplify first.",
            strategies=[
                "Mute all tracks, then bring back only the essential ones",
                "Delete or freeze tracks with no clear role",
                "Create a stripped version as a new starting point",
                "Focus on making 3-4 elements work perfectly instead of 12 elements existing",
            ],
        ),
        "too_safe_to_progress": RescueSuggestion(
            rescue_type="too_safe_to_progress",
            title="Take a risk — the safe path isn't working",
            description="Everything is technically correct but uninspired. Time for a bold move.",
            strategies=[
                "Try a dramatic sound design change on a key element",
                "Add an unexpected harmonic or rhythmic element",
                "Radically change the arrangement structure",
                "Experiment with an extreme processing chain (distortion, granular, etc.)",
            ],
        ),
    }

    # Primary suggestion
    primary_strat = rescue_strategies.get(report.primary_rescue_type)
    if primary_strat:
        primary_strat.urgency = "high" if report.confidence > 0.6 else "medium"
        suggestions.append(primary_strat)

    # Secondary suggestions (in gentle mode, only show primary)
    if mode == "direct":
        for rt in report.secondary_rescue_types[:2]:
            sec = rescue_strategies.get(rt)
            if sec:
                sec.urgency = "medium"
                suggestions.append(sec)

    return suggestions


# ── Diagnosis builder ─────────────────────────────────────────────


def _build_diagnosis(signals: list[StucknessSignal], level: str) -> str:
    """Build a human-readable diagnosis from signals."""
    if level == "flowing":
        return "Session is flowing well — no intervention needed"

    signal_descriptions = {
        "repeated_undo": "frequent undos suggest dissatisfaction with results",
        "local_tweaking": "lots of small parameter changes in one area",
        "long_loop_no_structure": "no structural changes for a while",
        "single_loop": "working in a single loop without expanding",
        "repeated_requests": "similar requests being repeated",
        "high_density": "track count is very high",
        "identity_unclear": "the song's identity isn't clear yet",
    }

    parts = []
    for s in signals:
        desc = signal_descriptions.get(s.signal_type, s.signal_type)
        parts.append(desc)

    prefix = {
        "slowing": "The session is slowing down",
        "stuck": "The session appears stuck",
        "deeply_stuck": "The session is deeply stuck",
    }.get(level, "Momentum issue detected")

    return f"{prefix}: {'; '.join(parts)}"
