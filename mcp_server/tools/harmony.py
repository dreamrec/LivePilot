"""Neo-Riemannian harmony tools — Tonnetz navigation, voice-leading paths,
progression classification, chromatic mediant suggestions.

4 tools for advanced harmonic analysis and exploration.
Pure computation — no Ableton connection needed.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp import Context

from ..server import mcp
from . import _harmony_engine as harmony
from . import _theory_engine as theory


def _ensure_list(value: Any) -> list:
    if isinstance(value, str):
        return json.loads(value)
    return value


# -- Tool 1: navigate_tonnetz ------------------------------------------------

@mcp.tool()
def navigate_tonnetz(
    ctx: Context,
    chord: str,
    depth: int = 1,
) -> dict:
    """Show neo-Riemannian neighbors of a chord on the Tonnetz.

    P (Parallel) flips the third: C major → C minor.
    L (Leading-tone) shifts by semitone: C major → E minor.
    R (Relative) shifts by whole tone: C major → A minor.

    Use depth 2-3 to see compound transforms (PL, PR, PRL, etc.).
    """
    if not 1 <= depth <= 3:
        return {"error": "depth must be 1-3"}
    try:
        root_pc, quality = harmony.parse_chord(chord)
    except ValueError as e:
        return {"error": str(e)}

    all_neighbors = harmony.get_neighbors(root_pc, quality, depth)

    descriptions = {
        "P": "flip third (Parallel)",
        "L": "shift by semitone (Leading-tone)",
        "R": "shift by whole tone (Relative)",
    }

    depth_1 = {}
    for label in ("P", "L", "R"):
        if label in all_neighbors:
            r, q = all_neighbors[label]
            depth_1[label] = {
                "chord": harmony.chord_to_str(r, q),
                "transform": label,
                "description": descriptions[label],
            }

    result: dict = {"chord": chord, "neighbors": depth_1}

    if depth >= 2:
        depth_2 = {}
        for key, (r, q) in all_neighbors.items():
            if len(key) == 2:
                depth_2[key] = {
                    "chord": harmony.chord_to_str(r, q),
                    "transforms": key,
                }
        result["depth_2"] = depth_2

    if depth >= 3:
        depth_3 = {}
        for key, (r, q) in all_neighbors.items():
            if len(key) == 3:
                depth_3[key] = {
                    "chord": harmony.chord_to_str(r, q),
                    "transforms": key,
                }
        result["depth_3"] = depth_3

    return result


# -- Tool 2: find_voice_leading_path -----------------------------------------

@mcp.tool()
def find_voice_leading_path(
    ctx: Context,
    from_chord: str,
    to_chord: str,
    max_steps: int = 4,
) -> dict:
    """Find the shortest neo-Riemannian path between two chords.

    Returns each intermediate chord and the specific voice movements.
    This is the 'film score progression finder' — chromatic mediants,
    hexatonic poles, and other cinematic chord moves.
    """
    if not 1 <= max_steps <= 6:
        return {"error": "max_steps must be 1-6"}
    try:
        from_parsed = harmony.parse_chord(from_chord)
        to_parsed = harmony.parse_chord(to_chord)
    except ValueError as e:
        return {"error": str(e)}

    result = harmony.find_shortest_path(from_parsed, to_parsed, max_steps)

    if not result["found"]:
        return {
            "from": from_chord,
            "to": to_chord,
            "found": False,
            "steps": -1,
            "path": [],
            "transforms": [],
            "voice_leading": [],
        }

    path_strs = [harmony.chord_to_str(*c) for c in result["path"]]
    voice_leading = []
    for i in range(len(result["path"]) - 1):
        from_midi = harmony.chord_to_midi(*result["path"][i])
        to_midi = harmony.chord_to_midi(*result["path"][i + 1])
        movements = []
        for f, t in zip(from_midi, to_midi):
            if f != t:
                movements.append(f"{theory.pitch_name(f)}→{theory.pitch_name(t)}")
        voice_leading.append({
            "from": from_midi,
            "to": to_midi,
            "movement": ", ".join(movements) if movements else "no movement",
        })

    return {
        "from": from_chord,
        "to": to_chord,
        "found": True,
        "steps": result["steps"],
        "path": path_strs,
        "transforms": result["transforms"],
        "voice_leading": voice_leading,
    }


# -- Tool 3: classify_progression --------------------------------------------

@mcp.tool()
def classify_progression(
    ctx: Context,
    chords: Any,
) -> dict:
    """Classify a chord progression by its neo-Riemannian transform pattern.

    Identifies hexatonic cycles (PL), octatonic cycles (PR), diatonic
    cycles (LR), and other known patterns. Pairs with analyze_harmony
    to understand why a progression sounds 'cinematic' or 'otherworldly'.
    """
    chords = _ensure_list(chords)
    if len(chords) < 2:
        return {"error": "Need at least 2 chords to classify"}

    try:
        parsed = [harmony.parse_chord(c) for c in chords]
    except ValueError as e:
        return {"error": str(e)}

    transforms = harmony.classify_transform_sequence(parsed)
    pattern = "".join(transforms)

    classification = "free neo-Riemannian progression"
    notable_usage = None
    clean = pattern.replace("?", "")

    if len(clean) >= 2:
        pair = clean[:2]
        if pair in ("PL", "LP") and all(c in "PL" for c in clean):
            classification = "hexatonic cycle fragment"
            notable_usage = "Radiohead, film scores (Zimmer, Howard)"
        elif pair in ("PR", "RP") and all(c in "PR" for c in clean):
            classification = "octatonic cycle fragment"
            notable_usage = "late Romantic (Wagner, Strauss), horror film scores"
        elif pair in ("LR", "RL") and all(c in "LR" for c in clean):
            classification = "diatonic cycle fragment"
            notable_usage = "functional harmony, common in classical and pop"

    if len(clean) == 1:
        names = {"P": "parallel transform", "L": "leading-tone transform",
                 "R": "relative transform"}
        classification = names.get(clean, classification)

    return {
        "chords": chords,
        "transforms": transforms,
        "pattern": pattern,
        "classification": classification,
        "notable_usage": notable_usage,
    }


# -- Tool 4: suggest_chromatic_mediants --------------------------------------

@mcp.tool()
def suggest_chromatic_mediants(
    ctx: Context,
    chord: str,
) -> dict:
    """Suggest all chromatic mediant relations for a chord.

    Chromatic mediants are chords a major/minor third away — they share
    0-1 common tones, creating maximum color shift with minimal voice movement.
    Includes 'cinematic picks' highlighting the most film-score-friendly options.
    """
    try:
        root_pc, quality = harmony.parse_chord(chord)
    except ValueError as e:
        return {"error": str(e)}

    mediants = harmony.get_chromatic_mediants(root_pc, quality)

    chord_pcs = {p % 12 for p in harmony.chord_to_midi(root_pc, quality)}
    formatted = {}
    for key, (r, q) in mediants.items():
        mediant_pcs = {p % 12 for p in harmony.chord_to_midi(r, q)}
        common = len(chord_pcs & mediant_pcs)
        formatted[key] = {
            "chord": harmony.chord_to_str(r, q),
            "common_tones": common,
            "relation": key.replace("_", " "),
        }

    cinematic = [
        harmony.chord_to_str(*mediants["lower_major_third"]),
        harmony.chord_to_str(*mediants["upper_major_third"]),
    ]

    return {
        "chord": chord,
        "chromatic_mediants": formatted,
        "cinematic_picks": cinematic,
        "explanation": (
            "Chromatic mediants share 0-1 common tones with the original chord. "
            "Maximum color shift with minimal voice movement — the 'epic' sound."
        ),
    }
