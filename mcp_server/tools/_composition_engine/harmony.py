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

