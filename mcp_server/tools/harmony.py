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
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in parameter: {exc}") from exc
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

    # BUG-B25 fix: optimize voice assignment. The old code emitted each
    # chord at its root-position octave-4 voicing, so moving D minor →
    # Bb major (D F A → Bb D F) appeared as a minor-6th jump instead of
    # the smooth D→D / F→F / A→Bb voice leading a pianist would pick.
    # We now walk the path keeping the FIRST chord at its default
    # voicing and, for each subsequent chord, pick the permutation
    # (inversion + octave offsets) that minimizes total semitone
    # movement from the previous voicing.
    voice_leading = []
    prev_voicing = harmony.chord_to_midi(*result["path"][0]) if result["path"] else []

    for i in range(len(result["path"]) - 1):
        next_chord = result["path"][i + 1]
        candidate_voicing = harmony.chord_to_midi(*next_chord)
        optimized_voicing = _optimize_voicing(prev_voicing, candidate_voicing)

        movements = []
        for f, t in zip(prev_voicing, optimized_voicing):
            if f != t:
                movements.append(f"{theory.pitch_name(f)}→{theory.pitch_name(t)}")

        voice_leading.append({
            "from": list(prev_voicing),
            "to": list(optimized_voicing),
            "movement": ", ".join(movements) if movements else "no movement",
            "total_semitone_movement": sum(
                abs(t - f) for f, t in zip(prev_voicing, optimized_voicing)
            ),
        })
        prev_voicing = optimized_voicing

    return {
        "from": from_chord,
        "to": to_chord,
        "found": True,
        "steps": result["steps"],
        "path": path_strs,
        "transforms": result["transforms"],
        "voice_leading": voice_leading,
    }


def _optimize_voicing(prev_voicing: list[int], target_pitches: list[int]) -> list[int]:
    """Pick an inversion/octave arrangement of *target_pitches* that
    minimizes total semitone movement from *prev_voicing*.

    Search space: for each permutation of target_pitches (3 voices →
    6 permutations), for each voice try octave offsets in ±2 octaves.
    That's 6 * 5^3 = 750 combinations per transition — trivial at runtime
    but dramatically smoother output than fixed-octave voicings.

    Assumes same voice-count on both sides; falls back to target_pitches
    unchanged if lengths differ.
    """
    import itertools

    if len(prev_voicing) != len(target_pitches) or not target_pitches:
        return list(target_pitches)

    best_voicing = list(target_pitches)
    best_cost = sum(abs(t - f) for f, t in zip(prev_voicing, best_voicing))

    # Each voice can float ±2 octaves (±24 semitones) from the base pitch
    octave_offsets = (-24, -12, 0, 12, 24)

    for perm in itertools.permutations(target_pitches):
        for offs in itertools.product(octave_offsets, repeat=len(perm)):
            candidate = [p + o for p, o in zip(perm, offs)]
            cost = sum(abs(t - f) for f, t in zip(prev_voicing, candidate))
            if cost < best_cost:
                best_cost = cost
                best_voicing = candidate

    return best_voicing


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

    # Normalize dict inputs like {"root": "F#", "quality": "minor"} to strings
    normalized = []
    for c in chords:
        if isinstance(c, dict):
            root = c.get("root", "")
            quality = c.get("quality", "major")
            normalized.append(f"{root} {quality}")
        else:
            normalized.append(str(c))

    try:
        parsed = [harmony.parse_chord(c) for c in normalized]
    except ValueError as e:
        return {"error": str(e)}

    transforms = harmony.classify_transform_sequence(parsed)
    pattern = "".join(transforms)

    classification = "free neo-Riemannian progression"
    notable_usage = None

    # BUG-B24: the old code did `clean = pattern.replace("?", "")` and
    # then checked alphabet purity on the cleaned string. That gave
    # a cheerful "diatonic cycle fragment" label to a pattern like
    # "LR?LR" — silently ignoring the middle step motion.
    # Now we check alphabet purity on the FULL pattern (only counting
    # transforms that landed in the target alphabet) AND track whether
    # any transforms were unclassified OR were step primitives that
    # aren't part of the target cycle alphabet.

    def _primitives(pat: str) -> list[str]:
        """Split a concatenated pattern into its atomic tokens.

        Tokens: P / L / R single letters, S1u/S1d/S2u/S2d step markers,
        and ? for unknown. The tokenizer walks left-to-right matching
        the longest known token at each position.
        """
        known = ("S1u", "S1d", "S2u", "S2d")
        out = []
        i = 0
        while i < len(pat):
            matched = None
            for tok in known:
                if pat.startswith(tok, i):
                    matched = tok
                    break
            if matched is None:
                out.append(pat[i])
                i += 1
            else:
                out.append(matched)
                i += len(matched)
        return out

    tokens = _primitives(pattern)
    core_tokens = [t for t in tokens if t in ("P", "L", "R")]
    step_tokens = [t for t in tokens if t.startswith("S")]
    unknown_count = sum(1 for t in tokens if t == "?")

    if len(core_tokens) >= 2:
        alphabet = set(core_tokens)
        if alphabet.issubset({"P", "L"}):
            classification = "hexatonic cycle fragment"
            notable_usage = "Radiohead, film scores (Zimmer, Howard)"
        elif alphabet.issubset({"P", "R"}):
            classification = "octatonic cycle fragment"
            notable_usage = "late Romantic (Wagner, Strauss), horror film scores"
        elif alphabet.issubset({"L", "R"}):
            classification = "diatonic cycle fragment"
            notable_usage = "functional harmony, common in classical and pop"
    elif len(core_tokens) == 1:
        names = {"P": "parallel transform", "L": "leading-tone transform",
                 "R": "relative transform"}
        classification = names.get(core_tokens[0], classification)

    # Annotate when the progression isn't purely in the classified alphabet
    annotations = []
    if step_tokens:
        annotations.append("with diatonic step motion")
    if unknown_count:
        annotations.append(
            f"with {unknown_count} unclassified transition"
            + ("s" if unknown_count != 1 else "")
        )
    if annotations:
        classification = f"{classification} ({', '.join(annotations)})"

    return {
        "chords": normalized,
        "transforms": transforms,
        "pattern": pattern,
        "classification": classification,
        "notable_usage": notable_usage,
        "unknown_transitions": unknown_count,
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
