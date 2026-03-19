"""Pure Python music theory engine — zero dependencies.

Replaces music21 for LivePilot's 7 theory tools. Implements:
Krumhansl-Schmuckler key detection, Roman numeral analysis,
voice leading checks, chord naming, and scale construction.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

ENHARMONIC = {
    'Cb': 'B', 'Db': 'C#', 'Eb': 'D#', 'Fb': 'E', 'Gb': 'F#',
    'Ab': 'G#', 'Bb': 'A#',
    'B#': 'C', 'E#': 'F',
    'Cbb': 'A#', 'Dbb': 'C', 'Ebb': 'D', 'Fbb': 'D#', 'Gbb': 'F',
    'Abb': 'G', 'Bbb': 'A',
    'C##': 'D', 'D##': 'E', 'E##': 'F#', 'F##': 'G', 'G##': 'A',
    'A##': 'B', 'B##': 'C#',
}

MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

DORIAN_PROFILE     = MAJOR_PROFILE[2:] + MAJOR_PROFILE[:2]
PHRYGIAN_PROFILE   = MAJOR_PROFILE[4:] + MAJOR_PROFILE[:4]
LYDIAN_PROFILE     = MAJOR_PROFILE[5:] + MAJOR_PROFILE[:5]
MIXOLYDIAN_PROFILE = MAJOR_PROFILE[7:] + MAJOR_PROFILE[:7]
LOCRIAN_PROFILE    = MAJOR_PROFILE[11:] + MAJOR_PROFILE[:11]

MODE_PROFILES = {
    'major': MAJOR_PROFILE, 'minor': MINOR_PROFILE,
    'dorian': DORIAN_PROFILE, 'phrygian': PHRYGIAN_PROFILE,
    'lydian': LYDIAN_PROFILE, 'mixolydian': MIXOLYDIAN_PROFILE,
    'locrian': LOCRIAN_PROFILE,
}

SCALES = {
    'major': [0, 2, 4, 5, 7, 9, 11], 'minor': [0, 2, 3, 5, 7, 8, 10],
    'dorian': [0, 2, 3, 5, 7, 9, 10], 'phrygian': [0, 1, 3, 5, 7, 8, 10],
    'lydian': [0, 2, 4, 6, 7, 9, 11], 'mixolydian': [0, 2, 4, 5, 7, 9, 10],
    'locrian': [0, 1, 3, 5, 6, 8, 10],
}

TRIAD_QUALITIES = {
    'major':      ['major', 'minor', 'minor', 'major', 'major', 'minor', 'diminished'],
    'minor':      ['minor', 'diminished', 'major', 'minor', 'minor', 'major', 'major'],
    'dorian':     ['minor', 'minor', 'major', 'major', 'minor', 'diminished', 'major'],
    'phrygian':   ['minor', 'major', 'major', 'minor', 'diminished', 'major', 'minor'],
    'lydian':     ['major', 'major', 'minor', 'diminished', 'major', 'minor', 'minor'],
    'mixolydian': ['major', 'minor', 'diminished', 'major', 'minor', 'minor', 'major'],
    'locrian':    ['diminished', 'major', 'minor', 'minor', 'major', 'major', 'minor'],
}

CHORD_PATTERNS = {
    (0, 4, 7): 'major triad', (0, 3, 7): 'minor triad',
    (0, 3, 6): 'diminished triad', (0, 4, 8): 'augmented triad',
    (0, 2, 7): 'sus2', (0, 5, 7): 'sus4',
    (0, 4, 7, 11): 'major seventh', (0, 3, 7, 10): 'minor seventh',
    (0, 4, 7, 10): 'dominant seventh', (0, 3, 6, 9): 'diminished seventh',
    (0, 3, 6, 10): 'half-diminished seventh',
}

ROMAN_LABELS = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII']

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def pitch_name(midi: int) -> str:
    """MIDI number -> note name. Always sharp spelling."""
    return NOTE_NAMES[midi % 12] + str(midi // 12 - 1)


def parse_key(key_str: str) -> dict:
    """Parse key string -> {tonic: 0-11, tonic_name: str, mode: str}.

    Accepts: "D minor", "Dm", "C# major", "C#m", "Bb", "Bbm", "F#m".
    """
    s = key_str.strip()

    # Shorthand: trailing 'm' after a note name means minor (e.g. "Am", "C#m", "Bbm")
    # But not "Dm" vs "D" — check if removing 'm' leaves a valid tonic
    if len(s) >= 2 and s[-1] == 'm' and ' ' not in s:
        candidate = s[:-1]
        norm = candidate[0].upper() + candidate[1:]
        if norm in ENHARMONIC:
            norm = ENHARMONIC[norm]
        if norm in NOTE_NAMES:
            return {"tonic": NOTE_NAMES.index(norm), "tonic_name": norm, "mode": "minor"}

    parts = s.split()
    raw_tonic = parts[0]
    mode = parts[1].lower() if len(parts) > 1 else 'major'

    # Normalize tonic: capitalize first letter
    tonic_name = raw_tonic[0].upper() + raw_tonic[1:]

    # Resolve enharmonics
    if tonic_name in ENHARMONIC:
        tonic_name = ENHARMONIC[tonic_name]

    if tonic_name not in NOTE_NAMES:
        raise ValueError(f"Unknown tonic: {tonic_name} (from '{key_str}')")

    return {"tonic": NOTE_NAMES.index(tonic_name), "tonic_name": tonic_name, "mode": mode}


def get_scale_pitches(tonic: int, mode: str) -> list[int]:
    """Return pitch classes (0-11) for the scale."""
    intervals = SCALES.get(mode, SCALES['major'])
    return [(tonic + iv) % 12 for iv in intervals]


def build_chord(degree: int, tonic: int, mode: str) -> dict:
    """Build triad from scale degree (0-indexed)."""
    scale = get_scale_pitches(tonic, mode)
    root = scale[degree % 7]
    third = scale[(degree + 2) % 7]
    fifth = scale[(degree + 4) % 7]
    quality = TRIAD_QUALITIES.get(mode, TRIAD_QUALITIES['major'])[degree % 7]
    return {
        "root_pc": root,
        "pitch_classes": [root, third, fifth],
        "quality": quality,
        "root_name": NOTE_NAMES[root],
    }


def _pearson(x: list[float], y: list[float]) -> float:
    """Pearson correlation coefficient."""
    n = len(x)
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    dx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    dy = math.sqrt(sum((yi - my) ** 2 for yi in y))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def detect_key(notes: list[dict], mode_detection: bool = True) -> dict:
    """Krumhansl-Schmuckler key detection."""
    # Build pitch-class histogram weighted by duration
    histogram = [0.0] * 12
    for n in notes:
        if n.get("mute", False):
            continue
        pc = n["pitch"] % 12
        histogram[pc] += n.get("duration", 1.0)

    profiles = MODE_PROFILES if mode_detection else {
        'major': MAJOR_PROFILE, 'minor': MINOR_PROFILE,
    }

    candidates = []
    for mode_name, profile in profiles.items():
        for tonic in range(12):
            rotated = [histogram[(tonic + i) % 12] for i in range(12)]
            r = _pearson(rotated, profile)
            candidates.append({
                "tonic": tonic,
                "tonic_name": NOTE_NAMES[tonic],
                "mode": mode_name,
                "confidence": round(r, 3),
            })

    candidates.sort(key=lambda c: -c["confidence"])
    best = candidates[0]
    return {
        "tonic": best["tonic"],
        "tonic_name": best["tonic_name"],
        "mode": best["mode"],
        "confidence": best["confidence"],
        "alternatives": candidates[1:9],
    }


def chord_name(midi_pitches: list[int]) -> str:
    """Identify chord from MIDI pitches -> 'C-major triad'."""
    pcs = sorted(set(p % 12 for p in midi_pitches))
    if not pcs:
        return "unknown"
    # Try each pitch class as potential root
    for root in pcs:
        intervals = tuple(sorted((pc - root) % 12 for pc in pcs))
        if intervals in CHORD_PATTERNS:
            return f"{NOTE_NAMES[root]}-{CHORD_PATTERNS[intervals]}"
    return f"{NOTE_NAMES[pcs[0]]} chord"


def roman_numeral(chord_pcs: list[int], tonic: int, mode: str) -> dict:
    """Match chord pitch classes -> Roman numeral figure."""
    pcs_set = set(pc % 12 for pc in chord_pcs)
    bass_pc = chord_pcs[0] % 12 if chord_pcs else 0

    best = {"figure": "?", "quality": "unknown", "degree": 0,
            "inversion": 0, "root_name": NOTE_NAMES[tonic]}

    for degree in range(7):
        triad = build_chord(degree, tonic, mode)
        triad_set = set(triad["pitch_classes"])
        if pcs_set == triad_set or pcs_set.issubset(triad_set):
            quality = triad["quality"]
            label = ROMAN_LABELS[degree]
            if quality in ("minor", "diminished"):
                label = label.lower()
            if quality == "diminished":
                label += "\u00b0"
            # Detect inversion
            inv = 0
            if bass_pc != triad["root_pc"]:
                if bass_pc == triad["pitch_classes"][1]:
                    inv = 1
                elif bass_pc == triad["pitch_classes"][2]:
                    inv = 2
            best = {"figure": label, "quality": quality, "degree": degree,
                    "inversion": inv, "root_name": triad["root_name"]}
            break

    return best


def roman_figure_to_pitches(figure: str, tonic: int, mode: str) -> dict:
    """Parse Roman numeral string -> concrete MIDI pitches.

    Handles: 'IV', 'bVII7', '#ivo7', 'ii7', etc.
    """
    remaining = figure
    chromatic_shift = 0
    acc_len = 0

    # Parse leading accidentals
    while remaining and remaining[0] in ('b', '#'):
        if remaining[0] == 'b':
            chromatic_shift -= 1
        else:
            chromatic_shift += 1
        remaining = remaining[1:]
        acc_len += 1

    # Parse Roman numeral
    upper_remaining = remaining.upper()
    numeral = ""
    for rn in ['VII', 'VI', 'IV', 'III', 'II', 'V', 'I']:
        if upper_remaining.startswith(rn):
            numeral = rn
            break

    if not numeral:
        return {"figure": figure, "error": f"Cannot parse: {figure}"}

    # Detect case of the numeral in original figure
    numeral_in_orig = remaining[:len(numeral)]
    is_minor_quality = numeral_in_orig == numeral_in_orig.lower()
    remaining = remaining[len(numeral):]

    degree = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII'].index(numeral)

    # Build base triad from scale
    chord = build_chord(degree, tonic, mode)
    root_pc = (chord["root_pc"] + chromatic_shift) % 12

    # Build pitch classes based on quality
    if is_minor_quality:
        pcs = [root_pc, (root_pc + 3) % 12, (root_pc + 7) % 12]
        quality = "minor"
    else:
        # Use scale-derived quality
        quality = chord["quality"]
        if quality == "minor":
            pcs = [root_pc, (root_pc + 3) % 12, (root_pc + 7) % 12]
        elif quality == "diminished":
            pcs = [root_pc, (root_pc + 3) % 12, (root_pc + 6) % 12]
        elif quality == "augmented":
            pcs = [root_pc, (root_pc + 4) % 12, (root_pc + 8) % 12]
        else:
            pcs = [root_pc, (root_pc + 4) % 12, (root_pc + 7) % 12]

    # Handle suffix
    suffix = remaining.lower()
    if suffix == "7":
        seventh = (root_pc + 10) % 12  # dominant/minor 7th
        pcs.append(seventh)
        if quality == "minor":
            quality = "minor seventh"
        else:
            quality = "dominant seventh"
    elif suffix == "o7":
        seventh = (root_pc + 9) % 12  # diminished 7th
        pcs.append(seventh)
        quality = "diminished seventh"
    elif suffix == "\u00b0":
        quality = "diminished"
        pcs = [root_pc, (root_pc + 3) % 12, (root_pc + 6) % 12]

    # Convert to MIDI pitches in octave 4 (root at its natural octave-4 pitch)
    base_midi = 60 + root_pc
    midi = []
    for pc in pcs:
        p = base_midi + ((pc - root_pc) % 12)
        midi.append(p)

    return {
        "figure": figure,
        "root_pc": root_pc,
        "pitches": [pitch_name(m) for m in midi],
        "midi_pitches": midi,
        "quality": quality,
    }


def check_voice_leading(prev_pitches: list[int], curr_pitches: list[int]) -> list[dict]:
    """Check voice leading issues between two chords."""
    issues = []
    if len(prev_pitches) < 2 or len(curr_pitches) < 2:
        if len(curr_pitches) >= 2 and curr_pitches[-1] < curr_pitches[0]:
            issues.append({"type": "voice_crossing"})
        return issues

    prev_bass, prev_sop = prev_pitches[0], prev_pitches[-1]
    curr_bass, curr_sop = curr_pitches[0], curr_pitches[-1]

    prev_iv = (prev_sop - prev_bass) % 12
    curr_iv = (curr_sop - curr_bass) % 12

    bass_moved = prev_bass != curr_bass
    sop_moved = prev_sop != curr_sop
    both_moved = bass_moved and sop_moved

    if both_moved and prev_iv == 7 and curr_iv == 7:
        issues.append({"type": "parallel_fifths"})

    if both_moved and prev_iv % 12 == 0 and curr_iv % 12 == 0:
        issues.append({"type": "parallel_octaves"})

    if curr_sop < curr_bass:
        issues.append({"type": "voice_crossing"})

    # Hidden fifth: same direction motion landing on P5
    if both_moved:
        bass_dir = curr_bass - prev_bass
        sop_dir = curr_sop - prev_sop
        same_dir = (bass_dir > 0 and sop_dir > 0) or (bass_dir < 0 and sop_dir < 0)
        if same_dir and curr_iv == 7:
            issues.append({"type": "hidden_fifth"})

    return issues


def chordify(notes: list[dict], quant: float = 0.125) -> list[dict]:
    """Group notes by quantized beat position."""
    groups: dict[float, list[dict]] = defaultdict(list)
    for n in notes:
        if n.get("mute", False):
            continue
        q_time = round(n["start_time"] / quant) * quant
        groups[q_time].append(n)

    result = []
    for beat in sorted(groups.keys()):
        group = groups[beat]
        pitches = sorted(n["pitch"] for n in group)
        duration = max(max(n["duration"] for n in group), quant)
        result.append({
            "beat": round(beat, 4),
            "duration": round(duration, 4),
            "pitches": pitches,
            "pitch_classes": sorted(set(p % 12 for p in pitches)),
        })
    return result
