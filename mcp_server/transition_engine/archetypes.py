"""Transition archetype library — 7 curated transition patterns.

Each archetype encodes a musically validated approach to section
boundaries, with use cases, risk profile, devices, gestures, and
verification cues.

Zero I/O.
"""

from __future__ import annotations

from .models import TransitionArchetype, TransitionBoundary


# ── Archetype Library ─────────────────────────────────────────────────

TRANSITION_ARCHETYPES: dict[str, TransitionArchetype] = {
    "subtractive_inhale": TransitionArchetype(
        name="subtractive_inhale",
        description="Pull energy back before impact — strip elements to create anticipation, then release into the new section.",
        use_cases=["build_to_drop", "verse_to_chorus", "pre_peak_tension"],
        risk_profile="low",
        devices=["Auto Filter", "Utility", "Compressor"],
        gestures=["inhale", "conceal", "release"],
        verification=[
            "Energy dips before boundary bar",
            "At least 2 tracks reduce volume or filter cutoff",
            "New section feels louder by contrast, not by gain",
        ],
    ),
    "fill_and_reset": TransitionArchetype(
        name="fill_and_reset",
        description="Drum fill or rhythmic intensification, then clean downbeat — classic transition that signals change without ambiguity.",
        use_cases=["verse_to_chorus", "chorus_to_verse", "any_section_change"],
        risk_profile="low",
        devices=["Drum Rack", "Simpler", "Beat Repeat"],
        gestures=["punctuate", "release"],
        verification=[
            "Fill occupies last 1-2 bars before boundary",
            "Downbeat of new section is rhythmically clean",
            "Fill density doesn't overwhelm the arrangement",
        ],
    ),
    "tail_throw": TransitionArchetype(
        name="tail_throw",
        description="Delay or reverb throw on the last hit of outgoing section — creates continuity while the new section enters.",
        use_cases=["phrase_cadence", "section_end_punctuation", "dub_style_transition"],
        risk_profile="low",
        devices=["Delay", "Reverb", "Echo"],
        gestures=["punctuate", "drift"],
        verification=[
            "Send level spikes on last beat/bar of outgoing section",
            "Tail decays naturally into new section",
            "Tail doesn't mask arrival of new elements",
        ],
    ),
    "width_bloom": TransitionArchetype(
        name="width_bloom",
        description="Narrow the stereo field before the boundary, then widen at arrival — creates a sense of opening up.",
        use_cases=["verse_to_chorus", "breakdown_to_drop", "section_expansion"],
        risk_profile="medium",
        devices=["Utility", "Auto Pan", "Chorus-Ensemble", "Wider"],
        gestures=["conceal", "reveal"],
        verification=[
            "Stereo width measurably narrows before boundary",
            "Width expands at or just after boundary bar",
            "Mono compatibility preserved during narrow phase",
        ],
    ),
    "harmonic_suspend": TransitionArchetype(
        name="harmonic_suspend",
        description="Suspend chord (sus2/sus4) or dominant 7th at section end, resolve on arrival — harmonic tension drives the transition.",
        use_cases=["key_change", "chord_progression_pivot", "harmonic_lift"],
        risk_profile="medium",
        devices=["Instrument Rack", "Wavetable", "Operator"],
        gestures=["lift", "release"],
        verification=[
            "Suspension or dominant chord appears in last 1-2 bars",
            "Resolution lands on downbeat of new section",
            "Voice leading is smooth (no large parallel jumps)",
        ],
    ),
    "impact_vacuum": TransitionArchetype(
        name="impact_vacuum",
        description="Everything cuts to silence (or near-silence), brief pause, then full impact — maximum contrast transition.",
        use_cases=["build_to_drop", "pre_peak_climax", "dramatic_reentry"],
        risk_profile="high",
        devices=["Utility", "Gate", "Compressor"],
        gestures=["conceal", "release"],
        verification=[
            "Clear silence or near-silence for at least half a bar",
            "Impact arrival is immediate and full",
            "Silence doesn't feel like a mistake or glitch",
        ],
    ),
    "delayed_foreground_handoff": TransitionArchetype(
        name="delayed_foreground_handoff",
        description="Old lead element fades while new lead enters underneath — overlapping handoff avoids abrupt role change.",
        use_cases=["lead_change", "hook_rotation", "verse_vocal_to_instrumental_hook"],
        risk_profile="medium",
        devices=["Utility", "Auto Filter", "EQ Eight"],
        gestures=["conceal", "reveal", "handoff"],
        verification=[
            "Outgoing lead fades over 2-4 bars across boundary",
            "Incoming lead enters before outgoing fully exits",
            "No frequency masking between overlapping leads",
        ],
    ),
}


# ── Archetype Selection ───────────────────────────────────────────────

# Maps (from_type, to_type) pairs to preferred archetypes.
_SECTION_PAIR_PREFERENCES: dict[tuple[str, str], list[str]] = {
    ("build", "drop"): ["subtractive_inhale", "impact_vacuum"],
    ("verse", "chorus"): ["fill_and_reset", "width_bloom", "subtractive_inhale"],
    ("chorus", "verse"): ["tail_throw", "delayed_foreground_handoff"],
    ("intro", "verse"): ["delayed_foreground_handoff", "fill_and_reset"],
    ("breakdown", "drop"): ["impact_vacuum", "subtractive_inhale"],
    ("breakdown", "chorus"): ["width_bloom", "subtractive_inhale"],
    ("verse", "bridge"): ["harmonic_suspend", "tail_throw"],
    ("bridge", "chorus"): ["subtractive_inhale", "width_bloom"],
    ("chorus", "bridge"): ["tail_throw", "harmonic_suspend"],
    ("pre_chorus", "chorus"): ["subtractive_inhale", "fill_and_reset"],
    ("verse", "pre_chorus"): ["fill_and_reset", "tail_throw"],
    ("drop", "breakdown"): ["tail_throw", "delayed_foreground_handoff"],
    ("chorus", "outro"): ["tail_throw", "delayed_foreground_handoff"],
    ("verse", "outro"): ["tail_throw", "delayed_foreground_handoff"],
}


def select_archetype(boundary: TransitionBoundary) -> TransitionArchetype:
    """Pick the best-fit archetype for a given boundary.

    Strategy:
    1. Check section-type pair preferences.
    2. Fall back to energy-delta heuristics.
    """
    pair = (boundary.from_type, boundary.to_type)

    # Check explicit section-pair preferences
    if pair in _SECTION_PAIR_PREFERENCES:
        preferred = _SECTION_PAIR_PREFERENCES[pair]
        return TRANSITION_ARCHETYPES[preferred[0]]

    # Energy-delta heuristics
    ed = boundary.energy_delta

    # Large energy increase — needs preparation
    if ed > 0.3:
        return TRANSITION_ARCHETYPES["subtractive_inhale"]

    # Large energy decrease — needs graceful exit
    if ed < -0.3:
        return TRANSITION_ARCHETYPES["tail_throw"]

    # Moderate increase — fill works universally
    if ed > 0.1:
        return TRANSITION_ARCHETYPES["fill_and_reset"]

    # Moderate decrease — handoff preserves continuity
    if ed < -0.1:
        return TRANSITION_ARCHETYPES["delayed_foreground_handoff"]

    # Flat energy — width bloom adds interest without energy change
    return TRANSITION_ARCHETYPES["width_bloom"]
