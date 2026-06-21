"""Layer planner — convert CompositionIntent into LayerSpec list.

Pure computation. Determines which layers to create, what to search for,
which techniques to use, and how to arrange sections. No I/O.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from ..prompt_parser import CompositionIntent


# ── Data Model ─────────────────────────────────────────────────────

@dataclass
class LayerSpec:
    """Specification for a single layer in a composition."""

    role: str                        # "drums", "bass", "lead", "pad", "texture", "vocal", "percussion", "fx"
    search_query: str                # Splice search query
    splice_filters: dict = field(default_factory=dict)  # key, bpm_range, genre, tags, sample_type
    technique_id: str = ""           # from the 29-technique library
    processing: list[dict] = field(default_factory=list)  # devices to add + param targets
    volume_db: float = 0.0           # mix level
    pan: float = 0.0                 # -1.0 to 1.0
    sections: list[str] = field(default_factory=list)  # which arrangement sections
    priority: int = 5                # download order (1=first, 10=last)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "search_query": self.search_query,
            "splice_filters": self.splice_filters,
            "technique_id": self.technique_id,
            "processing": self.processing,
            "volume_db": self.volume_db,
            "pan": self.pan,
            "sections": self.sections,
            "priority": self.priority,
        }


# ── Role Templates ─────────────────────────────────────────────────
# role → default config used to build LayerSpec
#
# 2026-05-01 unit-fix pass (six bugs surfaced by live full-mode test):
#   - EQ Eight `1 Filter Type A` is an int 0-7 enum (1 = "High Pass 12dB"),
#     NOT the string "highpass".
#   - EQ Eight `1 Frequency A` is 0-1 normalized log-scale, NOT Hz direct.
#     30 Hz ≈ 0.143, 200 Hz ≈ 0.30 (verified via live `value_string` probe).
#   - Compressor (Compressor2 — modern default) `Threshold` and `Ratio` are
#     0-1 normalized. Threshold 0.85 ≈ 0 dB, 0.70 ≈ -12 dB. Ratio 0.75 = 4:1.
#   - Saturator `Drive` is 0-1 normalized. Drive 0.6 ≈ +7 dB.
#   - Chorus-Ensemble's rate parameter is `Rate`, NOT `Rate 1`.
#   - Grain Delay's wet-mix parameter is `DryWet` (no slash); only Reverb
#     uses `Dry/Wet`.
#   - Auto Filter `Frequency` is also 0-1 normalized on AutoFilter2; left
#     params={} where this conflict arose (matches fast.py convention).
#
# Reference: fast.py's GENRE_CREATIVE_GUIDANCE.effect_chain_hints (lines
# 436-456) already uses the correct normalized convention. This table is
# the older planner; bringing it in line.

_ROLE_TEMPLATES: dict[str, dict] = {
    "drums": {
        "query_template": "{genre} drums {tempo}bpm",
        "sample_type": "loop",
        "technique_id": "slice_and_sequence",
        "processing": [
            {"name": "EQ Eight", "params": {"1 Filter Type A": 1, "1 Frequency A": 0.143}},
            {"name": "Compressor", "params": {"Threshold": 0.70, "Ratio": 0.75}},
        ],
        "volume_db": -3.0,
        "pan": 0.0,
        "priority": 1,
    },
    "bass": {
        "query_template": "{genre} bass {key} oneshot",
        "sample_type": "oneshot",
        "technique_id": "key_matched_layer",
        "processing": [
            {"name": "Saturator", "params": {"Drive": 0.6}},
            {"name": "EQ Eight", "params": {"1 Filter Type A": 1, "1 Frequency A": 0.143}},
        ],
        "volume_db": -5.0,
        "pan": 0.0,
        "priority": 2,
    },
    "lead": {
        "query_template": "{genre} {mood} melody {key}",
        "sample_type": "loop",
        "technique_id": "counterpoint_from_chops",
        "processing": [
            # AutoFilter2 Frequency is 0-1 normalized log; leave defaults
            # (matches fast.py convention — see fast.py line 449).
            {"name": "Auto Filter", "params": {}},
            {"name": "Delay", "params": {"Feedback": 0.35}},
        ],
        "volume_db": -6.0,
        "pan": 0.0,
        "priority": 4,
    },
    "pad": {
        "query_template": "{mood} pad {key}",
        "sample_type": "loop",
        "technique_id": "extreme_stretch",
        "processing": [
            # Reverb Decay Time is 0-1 normalized log; 0.55 ≈ 4.6s (live-verified).
            {"name": "Reverb", "params": {"Decay Time": 0.55, "Dry/Wet": 0.6}},
            {"name": "Chorus-Ensemble", "params": {"Rate": 0.5}},
        ],
        "volume_db": -10.0,
        "pan": 0.0,
        "priority": 5,
    },
    "texture": {
        "query_template": "{mood} texture ambient",
        "sample_type": "loop",
        "technique_id": "granular_scatter",
        "processing": [
            # Grain Delay's wet param is named "DryWet" (no slash), distinct
            # from Reverb's "Dry/Wet". Frequency is 0-1 normalized.
            {"name": "Grain Delay", "params": {"Frequency": 0.5, "DryWet": 0.5}},
            {"name": "Reverb", "params": {"Decay Time": 0.62, "Dry/Wet": 0.7}},
        ],
        "volume_db": -15.0,
        "pan": 0.0,
        "priority": 6,
    },
    "vocal": {
        "query_template": "vocal {mood} {key}",
        "sample_type": "loop",
        "technique_id": "vocal_chop_rhythm",
        "processing": [
            {"name": "Auto Filter", "params": {}},
            {"name": "Reverb", "params": {"Decay Time": 0.45, "Dry/Wet": 0.4}},
        ],
        "volume_db": -8.0,
        "pan": 0.0,
        "priority": 7,
    },
    "percussion": {
        "query_template": "{genre} percussion loop",
        "sample_type": "loop",
        "technique_id": "ghost_note_texture",
        "processing": [
            {"name": "EQ Eight", "params": {"1 Filter Type A": 1, "1 Frequency A": 0.30}},
            {"name": "Compressor", "params": {"Threshold": 0.66, "Ratio": 0.65}},
        ],
        "volume_db": -12.0,
        "pan": 0.0,
        "priority": 3,
    },
    "fx": {
        "query_template": "{genre} riser fx",
        "sample_type": "oneshot",
        "technique_id": "one_sample_challenge",
        "processing": [],
        "volume_db": -6.0,
        "pan": 0.0,
        "priority": 8,
    },
}


# ── Role Selection per Genre + Energy ──────────────────────────────
# Define which roles appear at different energy levels per genre.

_GENRE_ROLE_PRIORITY: dict[str, list[str]] = {
    # Roles listed in order of priority (first added, last dropped)
    "techno": ["drums", "bass", "percussion", "lead", "texture", "vocal", "fx"],
    "house": ["drums", "bass", "lead", "pad", "vocal", "texture"],
    "hip hop": ["drums", "bass", "lead", "vocal", "texture", "fx"],
    "ambient": ["pad", "texture", "vocal", "lead", "percussion"],
    "drum and bass": ["drums", "bass", "lead", "percussion", "texture", "vocal", "fx"],
    "trap": ["drums", "bass", "lead", "vocal", "fx", "texture"],
    "lo-fi": ["drums", "bass", "pad", "texture", "vocal"],
}

_DEFAULT_ROLE_PRIORITY = ["drums", "bass", "lead", "pad", "texture", "vocal", "percussion", "fx"]


# v1.24: SECTION_TEMPLATES and _DEFAULT_SECTION_TEMPLATE removed per
# vocabulary-not-form principle (Task 12). The framework provides VOCABULARY
# (descriptive). The LLM provides FORM (creative). Genre section sequences
# with bar counts belong in the LLM's training data + WebSearch fallback.


# ── Planner Functions ──────────────────────────────────────────────

def _build_search_query(template: str, intent: CompositionIntent) -> str:
    """Fill a query template with intent fields."""
    return template.format(
        genre=intent.genre or "electronic",
        mood=intent.mood or "",
        key=intent.key or "",
        tempo=intent.tempo or 120,
    ).strip()


# BUG-FULL-MODE-9 (2026-05-01) — per-role instrument category for Splice
# server-side filtering. Splice's gRPC `SearchSampleRequest.Instrument`
# field supports values like "bass", "drum", "synth", "piano", "vocal",
# "guitar", "pad", "fx". Without this, a query of "electro bass Am
# oneshot" lexically matches `Piano_OneShot_PianoPhrase_Am.wav` because
# the filename contains "OneShot" + "Am" — the bass slot got a piano.
# Setting `instrument` makes Splice filter at the catalog level.
#
# When omitted (e.g. drums where any drum sub-category is fine, or
# texture where we want creative latitude), Splice falls back to its
# normal text+tag scoring.
_ROLE_INSTRUMENT: dict[str, str] = {
    "bass": "bass",
    "lead": "synth",
    "pad": "synth",
    "vocal": "vocal",
    "percussion": "drum",
    # drums: omit — drum loops aren't classified as a single Instrument
    # texture: omit — too freeform; we want any-instrument FX/textures
    # fx: omit — same reasoning
}

# BUG-FULL-MODE-13 (2026-05-01) — non-tonal roles must NOT receive
# `key` or `chord_type` filters. Splice's drum/percussion/fx samples
# don't carry pitch metadata, so applying `chord_type=minor, key=a`
# narrows the catalog to ZERO matches, returning unresolved. Excluding
# these roles from the key filter lets the BPM + sample_type filters
# still narrow appropriately while drum samples can actually match.
_NON_TONAL_ROLES: frozenset[str] = frozenset({"drums", "percussion", "fx"})


def _build_splice_filters(
    intent: CompositionIntent,
    sample_type: str,
    role: str = "",
) -> dict:
    """Build Splice filter dict from intent + role.

    `role` (added 2026-05-01 BUG-FULL-MODE-9): when set, an `instrument`
    field is added per `_ROLE_INSTRUMENT` so Splice filters at the
    server side instead of relying on text matching.

    `role` also gates the key/chord_type filters (BUG-FULL-MODE-13):
    drums/percussion/fx don't carry pitch metadata in Splice's catalog,
    so applying `chord_type=minor, key=a` to those roles narrows the
    catalog to ZERO matches → unresolved. Tonal roles (bass/lead/pad/
    vocal/texture) keep the full filter set.
    """
    filters: dict = {}
    role_lower = (role or "").lower()
    is_tonal = role_lower not in _NON_TONAL_ROLES

    # Key → Splice format (lowercase root, separate chord_type) — tonal roles only.
    if intent.key and is_tonal:
        key = intent.key
        if key.endswith("m") and len(key) >= 2:
            root = key[:-1].lower()
            filters["chord_type"] = "minor"
        else:
            root = key.lower()
            filters["chord_type"] = "major"
        filters["key"] = root

    # BPM range (+-5) — applies to every role
    if intent.tempo:
        filters["bpm_min"] = max(1, intent.tempo - 5)
        filters["bpm_max"] = intent.tempo + 5

    if intent.genre:
        filters["genre"] = intent.genre

    if sample_type:
        filters["sample_type"] = sample_type

    # Instrument category — server-side filter at Splice
    instrument = _ROLE_INSTRUMENT.get(role_lower)
    if instrument:
        filters["instrument"] = instrument

    return filters


def _select_roles(intent: CompositionIntent) -> list[str]:
    """Select which roles to include based on genre, energy, and explicit elements."""
    role_priority = _GENRE_ROLE_PRIORITY.get(intent.genre, _DEFAULT_ROLE_PRIORITY)

    # How many layers to pick
    count = intent.layer_count or 5

    # Start with the top N roles by priority
    roles = list(role_priority[:count])

    # Add any explicitly requested elements as roles
    element_to_role = {
        "vocal": "vocal",
        "808": "bass",
        "bass": "bass",
        "drums": "drums",
        "percussion": "percussion",
        "pad": "pad",
        "texture": "texture",
        "fx": "fx",
        "strings": "pad",     # strings map to pad role
        "piano": "lead",      # piano maps to lead role
        "guitar": "lead",
        "brass": "lead",
        "synth": "lead",
    }

    for element in intent.explicit_elements:
        role = element_to_role.get(element)
        if role and role not in roles:
            roles.append(role)

    return roles


def plan_layers(intent: CompositionIntent) -> list[LayerSpec]:
    """Convert a CompositionIntent into a list of LayerSpec.

    Each LayerSpec describes one track to create: what to search for,
    which technique to use, processing chain, and mix settings.

    # DEPRECATED in v1.24 — full mode is now LLM-creative. Tool may stay
    # functional but should not be relied on for v1.24+ flows.
    # v1.24: SECTION_TEMPLATES removed per vocabulary-not-form principle (Task 12).
    # This function will raise until callers are updated in Task 14.
    """
    roles = _select_roles(intent)
    sections = plan_sections(intent)  # raises in v1.24 — Task 14 will rewire
    section_names = [s["name"] for s in sections]

    layers: list[LayerSpec] = []

    for role in roles:
        template = _ROLE_TEMPLATES.get(role)
        if not template:
            continue

        # Build search query
        query = _build_search_query(template["query_template"], intent)

        # Add descriptors to query for richer searches
        if intent.descriptors:
            query += " " + " ".join(intent.descriptors[:2])

        # Build Splice filters (pass `role` so per-role instrument category
        # gets server-side filtering — BUG-FULL-MODE-9).
        splice_filters = _build_splice_filters(intent, template["sample_type"], role=role)

        # Determine which sections this role appears in
        role_sections: list[str] = []
        for section in sections:
            section_layers = section.get("layers", [])
            for layer_ref in section_layers:
                # Parse "drums:-6dB" → "drums"
                layer_role = layer_ref.split(":")[0]
                if layer_role == role:
                    role_sections.append(section["name"])
                    break
        # If no section template match, include in all sections
        if not role_sections:
            role_sections = section_names

        # Pan spread for stereo width
        pan = _compute_pan(role, intent.energy)

        layer = LayerSpec(
            role=role,
            search_query=query,
            splice_filters=splice_filters,
            technique_id=template["technique_id"],
            processing=list(template["processing"]),  # copy
            volume_db=template["volume_db"],
            pan=pan,
            sections=role_sections,
            priority=template["priority"],
        )

        layers.append(layer)

    # Sort by priority (drums first, fx last)
    layers.sort(key=lambda l: l.priority)

    return layers


def plan_sections(
    intent: CompositionIntent,
    section_template: list[dict] | None = None,
) -> list[dict]:
    """Plan arrangement sections based on a caller-supplied template and duration.

    # DEPRECATED in v1.24 — full mode is now LLM-creative. This function may
    # remain callable but must NOT be relied on for v1.24+ flows. Section
    # templates (section sequences with bar counts) are forbidden in the
    # framework — the LLM provides form, not the registry.
    # v1.24: SECTION_TEMPLATES removed per vocabulary-not-form principle (Task 12).

    Args:
        intent: CompositionIntent with duration_bars.
        section_template: List of dicts {name, bars, layers}. Required in
            v1.24+. The LLM or caller supplies this — no built-in registry.

    Returns a list of dicts: {name, bars, layers, start_bar}.
    """
    if section_template is None:
        raise ValueError(
            "plan_sections() requires explicit section_template in v1.24+. "
            "SECTION_TEMPLATES was removed — the LLM provides form, not the "
            "framework. Pass a section_template list or use the v1.24 full-mode "
            "compose flow which is LLM-creative."
        )

    template = section_template

    # Scale sections to fit duration_bars
    total_template_bars = sum(s["bars"] for s in template)
    if total_template_bars == 0:
        total_template_bars = 64

    scale = intent.duration_bars / total_template_bars

    sections: list[dict] = []
    current_bar = 0

    for section in template:
        scaled_bars = max(4, round(section["bars"] * scale))
        # Round to nearest 4 bars
        scaled_bars = max(4, (scaled_bars // 4) * 4)

        sections.append({
            "name": section["name"],
            "bars": scaled_bars,
            "layers": list(section["layers"]),
            "start_bar": current_bar,
        })
        current_bar += scaled_bars

    # Clamp overshoot. Rounding each section up to the nearest 4 bars plus
    # the min-of-4-bars floor means a short duration_bars (e.g. 16) against
    # a 6-section template could produce 24+ bars of sections — a 50%
    # overshoot that pushed arrangement clips into unexpected territory.
    # Trim from the longest non-intro section until we fit.
    total_placed = sum(s["bars"] for s in sections)
    overshoot = total_placed - intent.duration_bars
    if overshoot > 0 and sections:
        # Sort indices by section length desc, skipping the first section
        # (usually intro) which we'd rather preserve at its snapped length.
        trimmable = sorted(
            range(1, len(sections)),
            key=lambda i: -sections[i]["bars"],
        ) or [0]
        i = 0
        while overshoot > 0 and i < len(trimmable) * 4:
            idx = trimmable[i % len(trimmable)]
            if sections[idx]["bars"] > 4:
                sections[idx]["bars"] -= 4
                overshoot -= 4
            i += 1
        # Recompute start_bar values after any trim
        running = 0
        for s in sections:
            s["start_bar"] = running
            running += s["bars"]

    return sections


def _compute_pan(role: str, energy: float) -> float:
    """Compute pan position for a role.

    Core elements (drums, bass) stay centered.
    Support elements get wider spread at higher energy.
    """
    _PAN_MAP = {
        "drums": 0.0,
        "bass": 0.0,
        "lead": 0.0,
        "pad": 0.0,
        "vocal": 0.0,
        "percussion": 0.3,
        "texture": -0.3,
        "fx": 0.4,
    }
    base_pan = _PAN_MAP.get(role, 0.0)
    # Widen slightly with energy
    return base_pan * (0.5 + 0.5 * energy)
