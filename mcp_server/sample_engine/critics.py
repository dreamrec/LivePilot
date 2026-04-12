"""Sample Engine critics — score sample fitness against the current song.

Six critics: key_fit, tempo_fit, frequency_fit, role_fit, vibe_fit, intent_fit.
All pure computation, zero I/O. Scores are 0.0-1.0 continuous (not issue-detection).
"""

from __future__ import annotations

from typing import Optional

from .models import CriticResult, SampleProfile, SampleIntent


# ── Music Theory Helpers ────────────────────────────────────────────

_NOTE_TO_NUM = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
    "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}


def _parse_key_to_num(key_str: str) -> tuple[int, bool]:
    """Parse key string to (pitch_class, is_minor)."""
    if not key_str:
        return (-1, False)
    is_minor = key_str.endswith("m") and not key_str.endswith("maj")
    root = key_str.rstrip("m").rstrip("inor").rstrip("aj").rstrip("ajor")
    num = _NOTE_TO_NUM.get(root, -1)
    return (num, is_minor)


def _key_distance(key_a: str, key_b: str) -> int:
    """Compute musical distance between two keys (0-6 on circle of fifths)."""
    num_a, minor_a = _parse_key_to_num(key_a)
    num_b, minor_b = _parse_key_to_num(key_b)
    if num_a < 0 or num_b < 0:
        return 7  # unknown

    # Convert minor to relative major for comparison
    if minor_a:
        num_a = (num_a + 3) % 12
    if minor_b:
        num_b = (num_b + 3) % 12

    # Circle of fifths distance
    diff = (num_a - num_b) % 12
    fifths = min(
        _count_fifths(diff),
        _count_fifths(12 - diff),
    )
    return fifths


def _count_fifths(semitones: int) -> int:
    """Count steps on circle of fifths for a given semitone interval."""
    # Map: 0->0, 7->1, 2->2, 9->3, 4->4, 11->5, 6->6
    fifths_map = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6,
                  5: 1, 10: 2, 3: 3, 8: 4, 1: 5}
    return fifths_map.get(semitones % 12, 6)


# ── Critics ─────────────────────────────────────────────────────────


def run_key_fit_critic(
    profile: SampleProfile,
    song_key: Optional[str] = None,
) -> CriticResult:
    """Score how well the sample's key fits the song."""
    if profile.key is None:
        return CriticResult(
            critic_name="key_fit", score=0.0,
            recommendation="Key unknown — verify by ear",
        )
    if song_key is None:
        return CriticResult(
            critic_name="key_fit", score=0.5,
            recommendation="Song key unknown — cannot evaluate fit",
        )

    dist = _key_distance(profile.key, song_key)
    # Score: 0 fifths = 1.0, 1 = 0.85, 2 = 0.7, 3 = 0.55, 4 = 0.4, 5+ = 0.3
    score_map = {0: 1.0, 1: 0.85, 2: 0.7, 3: 0.55, 4: 0.4, 5: 0.3, 6: 0.25}
    score = score_map.get(dist, 0.2)

    if score >= 0.8:
        rec = "Key matches well — load directly"
    elif score >= 0.6:
        rec = f"Closely related key — works for most intents"
    elif score >= 0.4:
        semitones = _suggest_transpose(profile.key, song_key)
        rec = f"Distant key — transpose {semitones:+d} semitones or use as texture"
    else:
        rec = "Chromatic clash — use with heavy filtering or as intentional tension"

    return CriticResult(critic_name="key_fit", score=score, recommendation=rec)


def _suggest_transpose(from_key: str, to_key: str) -> int:
    """Suggest semitone transpose to match target key."""
    num_from, _ = _parse_key_to_num(from_key)
    num_to, _ = _parse_key_to_num(to_key)
    if num_from < 0 or num_to < 0:
        return 0
    diff = (num_to - num_from) % 12
    return diff if diff <= 6 else diff - 12


def run_tempo_fit_critic(
    profile: SampleProfile,
    session_tempo: float = 120.0,
) -> CriticResult:
    """Score how well the sample's BPM fits the session tempo."""
    if profile.bpm is None:
        return CriticResult(
            critic_name="tempo_fit", score=0.0,
            recommendation="BPM unknown — estimate from onsets or verify manually",
        )

    bpm = profile.bpm
    # Check exact, half, double
    ratios = [bpm / session_tempo, bpm / (session_tempo * 2), bpm / (session_tempo / 2)]
    best_ratio = min(ratios, key=lambda r: abs(r - 1.0))
    deviation = abs(best_ratio - 1.0)

    if deviation < 0.01:
        score, rec = 1.0, "Exact tempo match — no warping needed"
    elif deviation < 0.02:
        score, rec = 0.95, f"Near-exact match — minimal warping"
    elif deviation < 0.05:
        score, rec = 0.8, f"Within 5% — light warp preserves quality"
    elif deviation < 0.10:
        score, rec = 0.6, f"Within 10% — moderate warp, choose mode carefully"
    elif deviation < 0.15:
        score, rec = 0.4, f"Within 15% — significant warp, use Texture mode for ambient"
    else:
        score, rec = 0.2, f"Extreme tempo mismatch — use as texture, not rhythmically"

    # Check if half/double time is the best match
    if abs(bpm / session_tempo - 0.5) < 0.05:
        score = max(score, 0.9)
        rec = "Half-time match — set warp accordingly"
    elif abs(bpm / session_tempo - 2.0) < 0.1:
        score = max(score, 0.9)
        rec = "Double-time match — set warp accordingly"

    return CriticResult(critic_name="tempo_fit", score=score, recommendation=rec)


def run_frequency_fit_critic(
    profile: SampleProfile,
    mix_snapshot: Optional[dict] = None,
) -> CriticResult:
    """Score frequency fit against existing mix.

    Without mix_snapshot (no M4L bridge), returns neutral 0.5.
    """
    if mix_snapshot is None:
        return CriticResult(
            critic_name="frequency_fit", score=0.5,
            recommendation="No spectral data — verify frequency fit by ear",
        )

    # With mix data: check where sample energy sits vs existing tracks
    # This is a simplified version — real implementation uses spectral overlap
    score = 0.5
    rec = "Frequency analysis requires spectral data from M4L bridge"
    return CriticResult(critic_name="frequency_fit", score=score, recommendation=rec)


def run_role_fit_critic(
    profile: SampleProfile,
    existing_roles: Optional[list[str]] = None,
) -> CriticResult:
    """Score whether this sample fills a missing role in the song."""
    if existing_roles is None:
        return CriticResult(
            critic_name="role_fit", score=0.5,
            recommendation="No role data available",
        )

    # Map material types to roles they fill
    role_map = {
        "vocal": ["vocal", "voice", "melody"],
        "drum_loop": ["drums", "percussion", "rhythm", "beat"],
        "one_shot": ["drums", "percussion", "hit"],
        "instrument_loop": ["synth", "keys", "guitar", "melody"],
        "texture": ["texture", "pad", "ambient", "atmosphere"],
        "foley": ["texture", "foley", "sfx"],
        "fx": ["fx", "transition", "riser"],
        "full_mix": [],
    }

    sample_roles = role_map.get(profile.material_type, [])
    existing_lower = [r.lower() for r in existing_roles]

    # Check for overlap
    overlap = sum(1 for r in sample_roles if any(r in e for e in existing_lower))

    if overlap == 0 and sample_roles:
        score = 1.0
        rec = f"Fills missing role — no existing {profile.material_type} in track"
    elif overlap == 0:
        score = 0.5
        rec = "Material type unclear for role analysis"
    elif sample_roles and overlap >= len(sample_roles) / 2:
        score = 0.3
        rec = f"Redundant — already have {', '.join(existing_lower[:3])}. Use as texture instead"
    elif overlap < len(sample_roles):
        score = 0.7
        rec = "Some role overlap — complements existing elements"
    else:
        score = 0.3
        rec = f"Redundant — already have {', '.join(existing_lower[:3])}. Use as texture instead"

    return CriticResult(critic_name="role_fit", score=score, recommendation=rec)


def run_vibe_fit_critic(
    profile: SampleProfile,
    taste_graph: object = None,
) -> CriticResult:
    """Score vibe fit using TasteGraph if available."""
    if taste_graph is None or not hasattr(taste_graph, "evidence_count"):
        return CriticResult(
            critic_name="vibe_fit", score=0.5,
            recommendation="No taste data — neutral score",
        )

    if taste_graph.evidence_count == 0:
        return CriticResult(
            critic_name="vibe_fit", score=0.5,
            recommendation="No taste evidence yet — neutral score",
        )

    # Use brightness and density as vibe indicators
    score = 0.5  # Enhanced in future with real taste comparison
    rec = "Taste comparison requires more evidence"
    return CriticResult(critic_name="vibe_fit", score=score, recommendation=rec)


def run_intent_fit_critic(
    profile: SampleProfile,
    intent: Optional[SampleIntent] = None,
) -> CriticResult:
    """Score how well the material serves the stated intent."""
    if intent is None:
        return CriticResult(
            critic_name="intent_fit", score=0.5,
            recommendation="No intent specified",
        )

    # Intent-material compatibility matrix
    compat: dict[str, dict[str, float]] = {
        "rhythm": {
            "drum_loop": 1.0, "one_shot": 0.9, "vocal": 0.6,
            "instrument_loop": 0.5, "full_mix": 0.4,
            "texture": 0.2, "foley": 0.5, "fx": 0.3,
        },
        "texture": {
            "texture": 1.0, "foley": 0.8, "vocal": 0.6,
            "drum_loop": 0.5, "instrument_loop": 0.6,
            "one_shot": 0.4, "fx": 0.7, "full_mix": 0.5,
        },
        "layer": {
            "instrument_loop": 1.0, "vocal": 0.8, "texture": 0.7,
            "drum_loop": 0.6, "one_shot": 0.3, "foley": 0.4,
        },
        "melody": {
            "instrument_loop": 1.0, "vocal": 0.9, "one_shot": 0.5,
            "texture": 0.3, "drum_loop": 0.2,
        },
        "vocal": {
            "vocal": 1.0, "instrument_loop": 0.3, "texture": 0.2,
        },
        "atmosphere": {
            "texture": 1.0, "foley": 0.9, "vocal": 0.5,
            "fx": 0.8, "full_mix": 0.4,
        },
        "transform": {
            # Everything is transformable — alchemist territory
            "vocal": 0.9, "drum_loop": 0.9, "instrument_loop": 0.9,
            "one_shot": 0.8, "texture": 0.8, "foley": 0.8,
            "fx": 0.7, "full_mix": 0.7,
        },
    }

    intent_scores = compat.get(intent.intent_type, {})
    score = intent_scores.get(profile.material_type, 0.4)

    if score >= 0.8:
        rec = f"Natural fit for {intent.intent_type}"
    elif score >= 0.6:
        rec = f"Works for {intent.intent_type} with some processing"
    elif score >= 0.4:
        rec = f"Creative use required for {intent.intent_type} — consider alchemist approach"
    else:
        rec = f"Unusual match — would need heavy transformation"

    return CriticResult(critic_name="intent_fit", score=score, recommendation=rec)


# ── Composite Runner ────────────────────────────────────────────────


def run_all_sample_critics(
    profile: SampleProfile,
    intent: Optional[SampleIntent] = None,
    song_key: Optional[str] = None,
    session_tempo: float = 120.0,
    existing_roles: Optional[list[str]] = None,
    mix_snapshot: Optional[dict] = None,
    taste_graph: object = None,
) -> dict[str, CriticResult]:
    """Run the full 6-critic battery. Returns dict keyed by critic name."""
    return {
        "key_fit": run_key_fit_critic(profile, song_key),
        "tempo_fit": run_tempo_fit_critic(profile, session_tempo),
        "frequency_fit": run_frequency_fit_critic(profile, mix_snapshot),
        "role_fit": run_role_fit_critic(profile, existing_roles),
        "vibe_fit": run_vibe_fit_critic(profile, taste_graph),
        "intent_fit": run_intent_fit_critic(profile, intent),
    }
