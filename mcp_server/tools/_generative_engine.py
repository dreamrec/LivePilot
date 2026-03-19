"""Pure Python generative music engine — zero dependencies.

Implements: Bjorklund/Euclidean rhythms, tintinnabuli, phase shifting,
additive process. All functions are pure — no state, no I/O.
"""

from __future__ import annotations

import math
from collections import defaultdict


# ---------------------------------------------------------------------------
# Known Euclidean rhythms
# ---------------------------------------------------------------------------

KNOWN_RHYTHMS: dict[tuple[int, int], str] = {
    (2, 3): "shuffle",
    (2, 5): "khafif-e-ramal",
    (3, 4): "cumbia",
    (3, 7): "ruchenitza",
    (3, 8): "tresillo",
    (4, 7): "yoruba bell",
    (5, 8): "cinquillo",
    (5, 16): "bossa nova",
    (7, 12): "west african bell",
    (7, 16): "brazilian necklace",
}


# ---------------------------------------------------------------------------
# Bjorklund / Euclidean rhythm
# ---------------------------------------------------------------------------

def bjorklund(pulses: int, steps: int) -> list[int]:
    """Bjorklund/Euclidean rhythm: distribute pulses evenly across steps.

    Returns list of 0s and 1s with length == steps.
    """
    if steps <= 0:
        return []
    if pulses <= 0:
        return [0] * steps
    if pulses >= steps:
        return [1] * steps

    # Bresenham-style Euclidean distribution
    pattern = []
    counts = [0] * steps
    remainders = [0] * steps
    divisor = steps - pulses
    remainders[0] = pulses
    level = 0

    while True:
        counts[level] = divisor // remainders[level]
        remainders[level + 1] = divisor % remainders[level]
        divisor = remainders[level]
        level += 1
        if remainders[level] <= 1:
            break

    counts[level] = divisor

    def _build(lv: int) -> list[int]:
        if lv == -1:
            return [0]
        if lv == -2:
            return [1]
        seq: list[int] = []
        for _ in range(counts[lv]):
            seq.extend(_build(lv - 1))
        if remainders[lv] != 0:
            seq.extend(_build(lv - 2))
        return seq

    pattern = _build(level)
    # Rotate to canonical form: first hit followed by a rest (1 then 0).
    # If every position after a hit is also a hit (e.g. pulses == steps-1),
    # fall back to rotating so the pattern simply starts with 1.
    if not pattern or 1 not in pattern or 0 not in pattern:
        return pattern
    n = len(pattern)
    for rot in range(n):
        rotated = pattern[rot:] + pattern[:rot]
        if rotated[0] == 1 and rotated[1] == 0:
            return rotated
    # Fallback: rotate to first 1
    idx = pattern.index(1)
    return pattern[idx:] + pattern[:idx]


def rotate_pattern(pattern: list[int], rotation: int) -> list[int]:
    """Rotate a pattern by N steps (positive = shift left)."""
    if not pattern:
        return pattern
    n = len(pattern)
    rotation = rotation % n
    return pattern[rotation:] + pattern[:rotation]


def identify_rhythm(pulses: int, steps: int) -> str | None:
    """Return known rhythm name for (pulses, steps), or None."""
    return KNOWN_RHYTHMS.get((pulses, steps))


# ---------------------------------------------------------------------------
# Tintinnabuli (Arvo Pärt)
# ---------------------------------------------------------------------------

def tintinnabuli_voice(
    melody_pitches: list[int],
    triad_pcs: list[int],
    position: str = "nearest",
) -> list[int]:
    """Generate tintinnabuli voice: for each melody pitch, find nearest triad tone.

    Args:
        melody_pitches: MIDI pitch numbers of the melody.
        triad_pcs: Pitch classes (0-11) of the triad (e.g. [0,4,7] for C major).
        position: "above", "below", or "nearest".

    Returns:
        List of MIDI pitches for the tintinnabuli voice.
    """
    result = []
    for mp in melody_pitches:
        best = _find_triad_tone(mp, triad_pcs, position)
        result.append(best)
    return result


def _find_triad_tone(pitch: int, triad_pcs: list[int], position: str) -> int:
    """Find the nearest triad tone relative to a given pitch."""
    candidates = []
    for octave_offset in range(-2, 3):
        for pc in triad_pcs:
            candidate = (pitch // 12 + octave_offset) * 12 + pc
            if 0 <= candidate <= 127:
                candidates.append(candidate)

    if position == "above":
        above = [c for c in candidates if c > pitch]
        return min(above) if above else max(candidates)
    elif position == "below":
        below = [c for c in candidates if c < pitch]
        return max(below) if below else min(candidates)
    else:  # nearest
        others = [c for c in candidates if c != pitch]
        if not others:
            return pitch
        return min(others, key=lambda c: abs(c - pitch))


# ---------------------------------------------------------------------------
# Phase shifting (Steve Reich)
# ---------------------------------------------------------------------------

def phase_shift(
    pattern_notes: list[dict],
    voices: int = 2,
    shift_amount: float = 0.125,
    total_length: float = 16.0,
) -> list[dict]:
    """Generate phase-shifted canon.

    Voice 0 loops the pattern normally. Each subsequent voice accumulates
    shift_amount offset per repetition, creating gradual phase drift.

    Returns combined note array with velocity encoding per voice:
    voice 0 = 100, voice 1 = 90, voice 2 = 80, etc.
    """
    if not pattern_notes:
        return []

    sorted_notes = sorted(pattern_notes, key=lambda n: n["start_time"])
    pattern_length = max(n["start_time"] + n["duration"] for n in sorted_notes)
    if pattern_length <= 0:
        return []

    result: list[dict] = []

    for voice in range(voices):
        velocity = max(100 - voice * 10, 30)
        # Voice N starts shifted by voice * shift_amount and accumulates
        # additional drift of voice * shift_amount per repetition.
        # offset(rep) = rep * pattern_length + voice * shift_amount * (rep + 1)
        repetition = 0
        while True:
            offset = repetition * pattern_length + voice * shift_amount * (repetition + 1)

            if offset >= total_length:
                break

            for note in sorted_notes:
                t = offset + note["start_time"]
                if t >= total_length:
                    continue
                result.append({
                    "pitch": note["pitch"],
                    "start_time": round(t, 4),
                    "duration": note["duration"],
                    "velocity": velocity,
                })
            repetition += 1

    return sorted(result, key=lambda n: n["start_time"])
