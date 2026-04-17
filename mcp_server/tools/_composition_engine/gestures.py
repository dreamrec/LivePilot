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

from .models import GestureIntent, GesturePlan

_GESTURE_MAPPINGS: dict[GestureIntent, dict] = {
    GestureIntent.REVEAL: {
        "description": "Open filter, introduce width, grow send level, unmask harmonics",
        "parameter_hints": ["filter_cutoff", "send_level", "utility_width"],
        "curve_family": "exponential",
        "default_direction": "up",
        "typical_duration_bars": 4,
    },
    GestureIntent.CONCEAL: {
        "description": "Close filter, narrow image, reduce send, darken support",
        "parameter_hints": ["filter_cutoff", "volume", "utility_width"],
        "curve_family": "logarithmic",
        "default_direction": "down",
        "typical_duration_bars": 4,
    },
    GestureIntent.HANDOFF: {
        "description": "One voice dims while another emerges",
        "parameter_hints": ["volume", "send_level"],
        "curve_family": "s_curve",
        "default_direction": "crossfade",
        "typical_duration_bars": 2,
    },
    GestureIntent.INHALE: {
        "description": "Pull energy back before impact — pre-drop vacuum",
        "parameter_hints": ["volume", "filter_cutoff", "send_level"],
        "curve_family": "exponential",
        "default_direction": "down",
        "typical_duration_bars": 2,
    },
    GestureIntent.RELEASE: {
        "description": "Restore weight, width, or harmonic color after tension",
        "parameter_hints": ["filter_cutoff", "utility_width", "volume"],
        "curve_family": "spring",
        "default_direction": "up",
        "typical_duration_bars": 1,
    },
    GestureIntent.LIFT: {
        "description": "HP filter rise, reverb send increase — upward energy",
        "parameter_hints": ["hp_filter", "send_level", "reverb_mix"],
        "curve_family": "exponential",
        "default_direction": "up",
        "typical_duration_bars": 8,
    },
    GestureIntent.SINK: {
        "description": "LP filter close, remove highs, settle into sub",
        "parameter_hints": ["filter_cutoff", "eq_high"],
        "curve_family": "logarithmic",
        "default_direction": "down",
        "typical_duration_bars": 4,
    },
    GestureIntent.PUNCTUATE: {
        "description": "Dub throw spike, beat repeat burst — accent a moment",
        "parameter_hints": ["send_level", "beat_repeat"],
        "curve_family": "spike",
        "default_direction": "burst",
        "typical_duration_bars": 1,
    },
    GestureIntent.DRIFT: {
        "description": "Subtle organic movement — perlin noise on parameters",
        "parameter_hints": ["filter_cutoff", "pan", "send_level"],
        "curve_family": "perlin",
        "default_direction": "oscillate",
        "typical_duration_bars": 8,
    },
}

def plan_gesture(
    intent: GestureIntent,
    target_tracks: list[int],
    start_bar: int,
    duration_bars: Optional[int] = None,
    foreground: bool = False,
) -> GesturePlan:
    """Create a gesture plan from a musical intent.

    Maps the abstract intent to concrete automation parameters and curve type.
    The agent uses this plan with apply_automation_shape to execute.
    """
    mapping = _GESTURE_MAPPINGS.get(intent)
    if mapping is None:
        raise ValueError(f"Unknown gesture intent: {intent}")

    actual_duration = duration_bars or mapping["typical_duration_bars"]

    return GesturePlan(
        gesture_id=f"gest_{intent.value}_{start_bar}",
        intent=intent,
        description=mapping["description"],
        target_tracks=target_tracks,
        parameter_hints=mapping["parameter_hints"],
        curve_family=mapping["curve_family"],
        direction=mapping["default_direction"],
        start_bar=start_bar,
        end_bar=start_bar + actual_duration,
        foreground=foreground,
    )

GESTURE_TEMPLATES: dict[str, dict] = {
    "pre_arrival_vacuum": {
        "description": "Pull energy back before impact — classic build technique",
        "steps": [
            {"intent": "inhale", "offset_bars": -4, "duration_bars": 3},
            {"intent": "release", "offset_bars": 0, "duration_bars": 1},
        ],
        "best_for": ["pre_drop", "pre_chorus", "turnaround"],
    },
    "sectional_width_bloom": {
        "description": "Narrow then widen — creates sense of opening up",
        "steps": [
            {"intent": "conceal", "offset_bars": -2, "duration_bars": 2},
            {"intent": "reveal", "offset_bars": 0, "duration_bars": 4},
            {"intent": "drift", "offset_bars": 4, "duration_bars": 8},
        ],
        "best_for": ["chorus_entry", "verse_to_chorus", "section_expansion"],
    },
    "phrase_end_throw": {
        "description": "Accent the end of a phrase with a dub throw",
        "steps": [
            {"intent": "punctuate", "offset_bars": -1, "duration_bars": 1},
        ],
        "best_for": ["phrase_cadence", "hook_accent", "transition"],
    },
    "turnaround_accent": {
        "description": "Mark turnaround with lift then settle",
        "steps": [
            {"intent": "lift", "offset_bars": -2, "duration_bars": 2},
            {"intent": "sink", "offset_bars": 0, "duration_bars": 2},
        ],
        "best_for": ["loop_turnaround", "phrase_repeat", "section_end"],
    },
    "outro_decay_dissolve": {
        "description": "Gradual dissolution for endings",
        "steps": [
            {"intent": "conceal", "offset_bars": 0, "duration_bars": 8},
            {"intent": "sink", "offset_bars": 4, "duration_bars": 8},
        ],
        "best_for": ["outro", "fade_out", "ending"],
    },
    "bass_tuck_before_kick": {
        "description": "Duck bass before kick re-entry",
        "steps": [
            {"intent": "inhale", "offset_bars": -1, "duration_bars": 1},
            {"intent": "release", "offset_bars": 0, "duration_bars": 1},
        ],
        "best_for": ["kick_reentry", "drop", "bass_return"],
    },
    "harmonic_tint_rise": {
        "description": "Gradually introduce harmonic color via filter opening",
        "steps": [
            {"intent": "reveal", "offset_bars": 0, "duration_bars": 8},
        ],
        "best_for": ["verse_development", "pad_introduction", "harmonic_shift"],
    },
    "response_echo": {
        "description": "Echo gesture — punctuate then drift the tail",
        "steps": [
            {"intent": "punctuate", "offset_bars": 0, "duration_bars": 1},
            {"intent": "drift", "offset_bars": 1, "duration_bars": 4},
        ],
        "best_for": ["call_and_response", "hook_echo", "delay_throw"],
    },
    "texture_drift_bed": {
        "description": "Subtle ongoing motion for background textures",
        "steps": [
            {"intent": "drift", "offset_bars": 0, "duration_bars": 16},
        ],
        "best_for": ["pad_movement", "background_texture", "atmosphere"],
    },
    "tension_ratchet": {
        "description": "Stepped tension increase — reveal in stages",
        "steps": [
            {"intent": "reveal", "offset_bars": 0, "duration_bars": 4},
            {"intent": "reveal", "offset_bars": 4, "duration_bars": 4},
            {"intent": "lift", "offset_bars": 8, "duration_bars": 4},
        ],
        "best_for": ["long_build", "riser", "gradual_intensification"],
    },
    "re_entry_spotlight": {
        "description": "Spotlight a returning element",
        "steps": [
            {"intent": "conceal", "offset_bars": -2, "duration_bars": 2},
            {"intent": "release", "offset_bars": 0, "duration_bars": 1},
        ],
        "best_for": ["hook_return", "melody_reentry", "element_spotlight"],
    },
}

def resolve_gesture_template(
    template_name: str,
    target_tracks: list[int],
    anchor_bar: int,
    foreground: bool = False,
) -> list[GesturePlan]:
    """Resolve a gesture template into a sequence of concrete GesturePlans.

    anchor_bar: the reference point (e.g., section boundary bar number).
    Steps with negative offsets happen before the anchor.
    """
    template = GESTURE_TEMPLATES.get(template_name)
    if template is None:
        valid = list(GESTURE_TEMPLATES.keys())
        raise ValueError(f"Unknown template '{template_name}'. Valid: {valid}")

    plans = []
    for i, step in enumerate(template["steps"]):
        intent = GestureIntent(step["intent"])
        start = anchor_bar + step.get("offset_bars", 0)
        duration = step.get("duration_bars", None)
        gesture = plan_gesture(intent, target_tracks, start, duration, foreground)
        gesture.gesture_id = f"{template_name}_{i:02d}_{start}"
        plans.append(gesture)

    return plans

