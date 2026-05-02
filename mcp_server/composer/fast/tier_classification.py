"""Tier classification for instruments — used by fast-mode brief hunt-order.

The framework provides VOCABULARY (descriptive). The LLM provides FORM (creative).
For instrument candidates: Tier-A and Tier-B are safe to return in briefs.
Tier-C bare URIs MUST NEVER be returned — the brief substitutes a curated preset
or omits that synth entirely.

Tier table (BINDING):
  A_curated_preset — .adg / .adv from sounds/ folder. Loaded with character.
  A_drum_sample    — raw sample (.aif/.wav) from drums/ folder. load_browser_item
                     auto-wraps in Simpler with drum-role defaults.
  B_drum_synth     — drum-specific synth (DS Kick etc). Default patch IS the drum.
  B_audible_default — generic melodic synth (Operator, Wavetable etc).
                      Default patch is "generic AI synth" — only return as fallback
                      when sounds/ returns nothing for a melodic role.
  C_needs_preset   — empty container (Drum Sampler, Emit etc). NEVER return.

Legacy tier value "A_sample_ready" is accepted in VALID_BRIEF_TIERS so old
tests still pass; new candidates use the specific A_* values.
"""

from __future__ import annotations

from typing import Optional


# ── Tier VALUE constants (used as the `tier` field in brief candidates) ──

TIER_A_CURATED_PRESET = "A_curated_preset"
TIER_A_DRUM_SAMPLE = "A_drum_sample"
TIER_B_DRUM_SYNTH = "B_drum_synth"
TIER_B_AUDIBLE_DEFAULT_VALUE = "B_audible_default"
TIER_C_NEEDS_PRESET_VALUE = "C_needs_preset"

# Tiers that are valid in brief output (Tier-C is NEVER valid)
VALID_BRIEF_TIERS = frozenset({
    TIER_A_CURATED_PRESET,
    TIER_A_DRUM_SAMPLE,
    TIER_B_DRUM_SYNTH,
    TIER_B_AUDIBLE_DEFAULT_VALUE,
    # Legacy alias — kept so old briefs and tests still work
    "A_sample_ready",
    # Legacy alias — "B_audible_default" is also the old tier value and is valid
    "B_audible_default",
})

# Role sets
DRUM_ROLES = frozenset({"kick", "snare", "hat", "perc", "clap", "tom", "drum"})
MELODIC_ROLES = frozenset({"bass", "lead", "pad", "atmos", "vox", "fx", "texture"})


# ── Frozensets of instrument names (used for name-based classification) ──

# Drum-specific synths — purpose-built drum sound generators.
# Their default patches ARE the intended drum sound (unlike generic melodic
# synths whose defaults are "generic AI synth").
# Allowed in drum-role briefs as Tier-B without curated presets.
DRUM_SPECIFIC_SYNTHS: frozenset[str] = frozenset({
    "DS Kick",
    "DS Snare",
    "DS Hi-Hat",
    "DS Clap",
    "DS Cymbal",
    "DS Tom",
    "DS Sampler",
    "DS Drum Bus",
})

# Melodic synths with audible defaults — "generic AI synth" risk.
# Renamed from TIER_B_AUDIBLE_DEFAULT to MELODIC_AUDIBLE_DEFAULTS to
# disambiguate from the tier VALUE string TIER_B_AUDIBLE_DEFAULT_VALUE.
# The old name TIER_B_AUDIBLE_DEFAULT is kept as an alias for backward compat.
MELODIC_AUDIBLE_DEFAULTS: frozenset[str] = frozenset({
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

# Backward-compat alias (old tests and callers use this name)
TIER_B_AUDIBLE_DEFAULT = MELODIC_AUDIBLE_DEFAULTS

# Containers + programming-required synths — NEVER return bare URIs.
# Renamed from TIER_C_NEEDS_PRESET to CONTAINERS_NEEDING_PRESETS to
# disambiguate from the tier VALUE string TIER_C_NEEDS_PRESET_VALUE.
# The old name TIER_C_NEEDS_PRESET is kept as an alias for backward compat.
CONTAINERS_NEEDING_PRESETS: frozenset[str] = frozenset({
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

# Backward-compat alias
TIER_C_NEEDS_PRESET = CONTAINERS_NEEDING_PRESETS

# Combined lookup: name → tier string
# Drum-specific synths → "B_drum_synth"; melodic audible defaults → "B_audible_default";
# containers → "C_needs_preset". Unknown instruments return None.
TIER_CLASSIFICATION: dict[str, str] = {
    name: "B_drum_synth" for name in DRUM_SPECIFIC_SYNTHS
} | {
    name: "B_audible_default" for name in MELODIC_AUDIBLE_DEFAULTS
} | {
    name: "C_needs_preset" for name in CONTAINERS_NEEDING_PRESETS
}


def classify_instrument(name: str) -> Optional[str]:
    """Classify an instrument by name.

    Returns one of:
      "B_drum_synth"      — drum-specific synth, safe for drum roles bare
      "B_audible_default" — generic melodic synth, only as fallback
      "C_needs_preset"    — container, NEVER return bare
      None                — unknown instrument
    """
    return TIER_CLASSIFICATION.get(name)


def is_drum_specific_synth(name: str) -> bool:
    """True if `name` is a drum-specific synth — safe to return bare for drum roles."""
    return name in DRUM_SPECIFIC_SYNTHS


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
