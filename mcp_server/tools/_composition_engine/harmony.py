"""Part of the _composition_engine package — extracted from the single-file engine.

Pure-computation core, no external deps. Callers should import from the package
facade (e.g. `from mcp_server.tools._composition_engine import X`), which
re-exports everything from these sub-modules.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

from .models import HarmonyField


# ── BUG-E3: harmonic-ness scoring ────────────────────────────────────────
# get_harmony_field used to take the FIRST track in section.tracks_active
# that had notes and lock in its key detection. When that track was
# percussion (all notes at a single pitch, staccato), detect_key would
# return a bogus "C major" for the whole section. The fix: score every
# track's notes for harmonic-ness, aggregate notes from tracks that pass
# a threshold, and run key detection on the combined pool.

_PERC_NAME_TOKENS = (
    "kick", "snare", "clap", "hat", "hihat", "hi-hat", "hh", "drum",
    "drums", "perc", "percussion", "rim", "crash", "ride", "tom",
    "cymbal", "shaker", "tambourine", "cowbell", "808", "909",
    "breakbeat", "break", "stick", "click",
)
_HARMONIC_NAME_TOKENS = (
    "pad", "pads", "bass", "sub", "lead", "chord", "chords", "keys",
    "synth", "piano", "rhodes", "organ", "lush", "string", "strings",
    "brass", "pluck", "arp", "melody", "harmony", "voice", "choir",
)


def harmonic_score(notes: list[dict], track_name: str = "") -> float:
    """Rate how likely a track's notes carry harmonic content (0.0 - 1.0).

    Used by get_harmony_field to decide which tracks to include in
    aggregate key detection. Percussion (single-pitch, staccato) scores
    near 0. Sustained chordal/melodic material scores near 1.

    Signals combined:
      - unique pitch classes (chords vary, kicks don't)
      - median note duration (sustain vs staccato)
      - pitch range (melody moves, drums don't)
      - minimum pitch (above the GM drum range)
      - track-name hint tokens (soft nudge)

    Returns a score in [0.0, 1.0]. Callers typically threshold at 0.3 or 0.4.
    """
    if not notes:
        return 0.0

    pitches = [int(n.get("pitch", 60)) for n in notes]
    durations = [float(n.get("duration", 0.0)) for n in notes]
    pcs = set(p % 12 for p in pitches)

    # Use statistics.median for a more stable middle value. Falling back
    # to a manual median keeps this file free of an extra import.
    sorted_durs = sorted(durations)
    median_dur = sorted_durs[len(sorted_durs) // 2] if sorted_durs else 0.0
    unique_pcs = len(pcs)
    pitch_range = max(pitches) - min(pitches) if pitches else 0
    min_pitch = min(pitches) if pitches else 0

    score = 0.0
    # Unique pitch-class diversity: 3+ distinct pcs is a strong harmonic signal
    if unique_pcs >= 4:
        score += 0.45
    elif unique_pcs >= 3:
        score += 0.35
    elif unique_pcs >= 2:
        score += 0.15

    # Duration: sustained notes carry harmony; staccato is rhythmic
    if median_dur >= 1.0:
        score += 0.30
    elif median_dur >= 0.5:
        score += 0.25
    elif median_dur >= 0.25:
        score += 0.10

    # Pitch range: melody spans more than an octave often; drums don't
    if pitch_range >= 12:
        score += 0.20
    elif pitch_range >= 5:
        score += 0.10

    # Minimum pitch out of the GM drum-map range (35–51) suggests melody
    if min_pitch >= 48:
        score += 0.10

    # Track-name hints — mild nudges either way
    name_lower = str(track_name or "").lower()
    if any(tok in name_lower for tok in _PERC_NAME_TOKENS):
        score -= 0.45
    if any(tok in name_lower for tok in _HARMONIC_NAME_TOKENS):
        score += 0.20

    return max(0.0, min(1.0, score))


def build_harmony_field(
    section_id: str,
    harmony_analysis: Optional[dict] = None,
    scale_info: Optional[dict] = None,
    progression_info: Optional[dict] = None,
    voice_leading_info: Optional[dict] = None,
) -> HarmonyField:
    """Build a HarmonyField from theory/harmony tool outputs.

    All parameters are optional — degrades gracefully.
    """
    hf = HarmonyField(section_id=section_id)

    # Scale / key info
    if scale_info:
        top = scale_info.get("top_match", {})
        hf.key = top.get("tonic", "")
        hf.mode = top.get("mode", "")
        hf.confidence = top.get("confidence", 0.0)

    # Chord progression
    if harmony_analysis:
        chords = harmony_analysis.get("chords", [])
        hf.chord_progression = [c.get("chord_name", "?") for c in chords]

        # Instability: ratio of non-tonic chords
        roman_numerals = [c.get("roman_numeral", "?") for c in chords]
        if roman_numerals:
            non_tonic = sum(1 for r in roman_numerals if r not in ("i", "I", "?"))
            hf.instability = non_tonic / len(roman_numerals)

        # Resolution potential: does it end on tonic?
        if roman_numerals:
            hf.resolution_potential = 1.0 if roman_numerals[-1] in ("i", "I") else 0.3

    # Progression classification
    if progression_info:
        classification = progression_info.get("classification", "")
        # "diatonic" = more stable, "free neo-Riemannian" = more unstable
        if "diatonic" in classification.lower():
            hf.instability = max(0.0, hf.instability - 0.1)
        elif "free" in classification.lower():
            hf.instability = min(1.0, hf.instability + 0.1)

    # Voice leading quality
    if voice_leading_info:
        steps = voice_leading_info.get("steps", 0)
        found = voice_leading_info.get("found", False)
        if found and steps > 0:
            # Fewer steps = smoother voice leading
            hf.voice_leading_quality = max(0.0, 1.0 - (steps - 1) * 0.15)

    return hf

