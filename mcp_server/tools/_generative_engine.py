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
