"""Tier classification for instruments — used by fast-mode brief hunt-order.

The framework provides VOCABULARY (descriptive). The LLM provides FORM (creative).
For instrument candidates: Tier-A and Tier-B are safe to return in briefs.
Tier-C bare URIs MUST NEVER be returned — the brief substitutes a curated preset
or omits that synth entirely.

Tier table (BINDING):
  A — sample-ready   : Factory .adg/.adv from sounds/; raw samples from drums/samples/.
                       Plays sound on note-on without additional configuration.
  B — audible default: Self-contained synths with a non-silent default patch.
                       Plays a sound on note-on without preset.
  C — needs preset   : Containers + programming-required synths.
                       Silent or sub-audible without a sample or preset loaded.
"""

from __future__ import annotations

from typing import Optional


# Tier-B: self-contained synths with audible default patch (no preset needed).
TIER_B_AUDIBLE_DEFAULT: frozenset[str] = frozenset({
    "Operator",
    "Wavetable",
    "Drift",
    "Analog",
    "Bass",
    "Electric",
    "Tension",
    "Collision",
    "Meld",
})

# Tier-C: containers + programming-required synths.
# These need either a sample loaded inside (containers) or a curated preset
# (programming-required synths). NEVER return the bare URI in a brief.
TIER_C_NEEDS_PRESET: frozenset[str] = frozenset({
    "Drum Sampler",
    "Drum Rack",
    "DrumGroup",      # internal alias for Drum Rack
    "Simpler",
    "Sampler",
    "Impulse",
    "Emit",
    "Vector FM",
    "Vector Grain",
    "Granulator III",
    "Granulator II",  # legacy
    "Instrument Rack",
    "Looper",
    "External Instrument",
})

# Combined lookup: name → tier string
TIER_CLASSIFICATION: dict[str, str] = {
    name: "B_audible_default" for name in TIER_B_AUDIBLE_DEFAULT
} | {
    name: "C_needs_preset" for name in TIER_C_NEEDS_PRESET
}


def classify_instrument(name: str) -> Optional[str]:
    """Classify an instrument by name.

    Returns "B_audible_default", "C_needs_preset", or None (unknown).
    Caller decides what to do with None — typically skip (defensive default).
    """
    return TIER_CLASSIFICATION.get(name)


# Search terms for hunting curated chains in sounds/ and drums/ per role.
# Used by build_creative_brief to populate instruments_by_role.
ROLE_SEARCH_TERMS: dict[str, dict[str, Optional[str]]] = {
    # drum roles — search drums/ first, sounds/ second
    "kick":    {"sounds_term": "kick",       "drums_term": "kick"},
    "snare":   {"sounds_term": "snare",      "drums_term": "snare"},
    "hat":     {"sounds_term": "hihat",      "drums_term": "hihat"},
    "perc":    {"sounds_term": "percussion", "drums_term": "perc"},
    "clap":    {"sounds_term": "clap",       "drums_term": "clap"},
    "tom":     {"sounds_term": "tom",        "drums_term": "tom"},
    # melodic roles — search sounds/ for curated presets
    "bass":    {"sounds_term": "bass",    "drums_term": None},
    "lead":    {"sounds_term": "lead",    "drums_term": None},
    "pad":     {"sounds_term": "pad",     "drums_term": None},
    "atmos":   {"sounds_term": "ambient", "drums_term": None},
    "vox":     {"sounds_term": "vocal",   "drums_term": None},
    "fx":      {"sounds_term": "fx",      "drums_term": None},
    "texture": {"sounds_term": "texture", "drums_term": None},
}
