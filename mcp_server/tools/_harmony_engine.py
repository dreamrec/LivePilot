"""Neo-Riemannian harmony engine — pure Python with optional opycleid.

Implements P/L/R transforms, Tonnetz navigation, BFS path finding,
progression classification, and chromatic mediant computation.
"""

from __future__ import annotations

from collections import deque
from typing import Callable

from . import _theory_engine as engine


# ---------------------------------------------------------------------------
# Note name display
# ---------------------------------------------------------------------------

_PC_NAMES_MAJOR = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
_PC_NAMES_MINOR = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb', 'B']


def chord_to_str(root_pc: int, quality: str) -> str:
    """Convert (root_pc, quality) to display string like 'Ab major'."""
    names = _PC_NAMES_MAJOR if quality == "major" else _PC_NAMES_MINOR
    return f"{names[root_pc % 12]} {quality}"


def parse_chord(chord_str: str) -> tuple[int, str]:
    """Parse 'C major' → (0, 'major'), 'F# minor' → (6, 'minor').

    Also handles 7th chord qualities by reducing to base triad:
    'D minor seventh' → (2, 'minor'), 'G dominant seventh' → (7, 'major').
    Neo-Riemannian transforms operate on triads, so we strip extensions.
    """
    # Normalize extended chord quality names to base triad
    s = chord_str.strip()
    _QUALITY_MAP = {
        "minor seventh": "minor", "minor 7th": "minor", "minor7": "minor",
        "major seventh": "major", "major 7th": "major", "major7": "major",
        "dominant seventh": "major", "dominant 7th": "major", "dominant7": "major",
        "diminished seventh": "minor", "diminished 7th": "minor",
        "half-diminished seventh": "minor", "half-diminished": "minor",
    }
    for ext, base in _QUALITY_MAP.items():
        if ext in s.lower():
            # Extract root (everything before the quality)
            idx = s.lower().index(ext)
            root = s[:idx].strip() or s.split()[0]
            return (engine.parse_key(f"{root} {base}")["tonic"], base)

    parsed = engine.parse_key(chord_str)
    mode = parsed["mode"]
    if mode not in ("major", "minor"):
        raise ValueError(f"Only major/minor chords supported, got: {mode}")
    return (parsed["tonic"], mode)


# ---------------------------------------------------------------------------
# PRL transforms
# ---------------------------------------------------------------------------

def parallel(root_pc: int, quality: str) -> tuple[int, str]:
    """P: flip the third. Major ↔ minor, same root."""
    new_q = "minor" if quality == "major" else "major"
    return (root_pc, new_q)


def leading_tone(root_pc: int, quality: str) -> tuple[int, str]:
    """L: major → lower root by semitone → minor; minor → raise fifth by semitone → major."""
    if quality == "major":
        return ((root_pc + 4) % 12, "minor")
    else:
        return ((root_pc - 4) % 12, "major")


def relative(root_pc: int, quality: str) -> tuple[int, str]:
    """R: major → raise fifth by whole tone → minor; minor → lower root by whole tone → major."""
    if quality == "major":
        return ((root_pc + 9) % 12, "minor")
    else:
        return ((root_pc + 3) % 12, "major")


TRANSFORMS: dict[str, Callable] = {
    "P": parallel,
    "L": leading_tone,
    "R": relative,
}


def apply_transforms(root_pc: int, quality: str, transforms: str) -> tuple[int, str]:
    """Apply a sequence of PRL transforms: 'PRL' → P, then R, then L."""
    current = (root_pc, quality)
    for char in transforms:
        fn = TRANSFORMS.get(char)
        if fn is None:
            raise ValueError(f"Unknown transform: {char}. Use P, L, or R.")
        current = fn(*current)
    return current


def chord_to_midi(root_pc: int, quality: str, octave: int = 4) -> list[int]:
    """Convert chord to MIDI pitches in the given octave."""
    base = (octave + 1) * 12 + root_pc
    if quality == "major":
        return [base, base + 4, base + 7]
    else:
        return [base, base + 3, base + 7]


# ---------------------------------------------------------------------------
# Tonnetz navigation
# ---------------------------------------------------------------------------

def get_neighbors(root_pc: int, quality: str, depth: int = 1) -> dict:
    """Return all reachable chords up to depth PRL transforms."""
    result = {}
    _explore(root_pc, quality, "", depth, result)
    return result


def _explore(root_pc: int, quality: str, path: str, remaining: int,
             result: dict) -> None:
    """Recursive neighbor exploration."""
    if remaining <= 0:
        return
    for label, fn in TRANSFORMS.items():
        new_chord = fn(root_pc, quality)
        key = path + label
        if key not in result:
            result[key] = new_chord
            _explore(*new_chord, key, remaining - 1, result)


# ---------------------------------------------------------------------------
# BFS path finding
# ---------------------------------------------------------------------------

def find_shortest_path(
    from_chord: tuple[int, str],
    to_chord: tuple[int, str],
    max_depth: int = 4,
) -> dict:
    """BFS through PRL space to find shortest path between two chords."""
    if from_chord == to_chord:
        return {
            "found": True,
            "steps": 0,
            "path": [from_chord],
            "transforms": [],
        }

    queue: deque = deque()
    visited: set = {from_chord}

    for label, fn in TRANSFORMS.items():
        next_chord = fn(*from_chord)
        if next_chord == to_chord:
            return {
                "found": True,
                "steps": 1,
                "path": [from_chord, to_chord],
                "transforms": [label],
            }
        if next_chord not in visited:
            visited.add(next_chord)
            queue.append((next_chord, [from_chord, next_chord], [label]))

    depth = 1
    while queue and depth < max_depth:
        depth += 1
        level_size = len(queue)
        for _ in range(level_size):
            current, path, transforms = queue.popleft()
            for label, fn in TRANSFORMS.items():
                next_chord = fn(*current)
                if next_chord == to_chord:
                    return {
                        "found": True,
                        "steps": depth,
                        "path": path + [to_chord],
                        "transforms": transforms + [label],
                    }
                if next_chord not in visited:
                    visited.add(next_chord)
                    queue.append((next_chord, path + [next_chord],
                                  transforms + [label]))

    return {"found": False, "steps": -1, "path": [], "transforms": []}


# ---------------------------------------------------------------------------
# Progression classification
# ---------------------------------------------------------------------------

def classify_transform_sequence(chords: list[tuple[int, str]]) -> list[str]:
    """Identify the PRL transform between each consecutive pair of chords.

    Tries single transforms (P, L, R) first, then 2-step compound
    transforms (PL, PR, LP, LR, RP, RL) for richer classification.
    """
    _COMPOUNDS = ["PL", "PR", "LP", "LR", "RP", "RL",
                  "PP", "LL", "RR"]
    result = []
    for i in range(len(chords) - 1):
        found = "?"
        # Try single transforms first
        for label, fn in TRANSFORMS.items():
            if fn(*chords[i]) == chords[i + 1]:
                found = label
                break
        # Try 2-step compound transforms
        if found == "?":
            for compound in _COMPOUNDS:
                try:
                    if apply_transforms(*chords[i], compound) == chords[i + 1]:
                        found = compound
                        break
                except (ValueError, KeyError):
                    continue
        result.append(found)
    return result


# ---------------------------------------------------------------------------
# Chromatic mediants
# ---------------------------------------------------------------------------

def get_chromatic_mediants(root_pc: int, quality: str) -> dict:
    """Return all 6 chromatic mediant relations."""
    return {
        "upper_major_third": ((root_pc + 4) % 12, quality),
        "lower_major_third": ((root_pc - 4) % 12, quality),
        "upper_minor_third": ((root_pc + 3) % 12, quality),
        "lower_minor_third": ((root_pc - 3) % 12, quality),
        "upper_major_third_flip": ((root_pc + 4) % 12,
                                   "minor" if quality == "major" else "major"),
        "lower_major_third_flip": ((root_pc - 4) % 12,
                                   "minor" if quality == "major" else "major"),
    }
