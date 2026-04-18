"""Layer planner — convert CompositionIntent into LayerSpec list.

Pure computation. Determines which layers to create, what to search for,
which techniques to use, and how to arrange sections. No I/O.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .prompt_parser import CompositionIntent


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

_ROLE_TEMPLATES: dict[str, dict] = {
    "drums": {
        "query_template": "{genre} drums {tempo}bpm",
        "sample_type": "loop",
        "technique_id": "slice_and_sequence",
        "processing": [
            {"name": "EQ Eight", "params": {"1 Filter Type A": "highpass", "1 Frequency A": 30.0}},
            {"name": "Compressor", "params": {"Threshold": -12.0, "Ratio": 4.0}},
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
            {"name": "Saturator", "params": {"Drive": 6.0}},
            {"name": "EQ Eight", "params": {"1 Filter Type A": "highpass", "1 Frequency A": 30.0}},
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
            {"name": "Auto Filter", "params": {"Frequency": 2000.0, "Resonance": 0.3}},
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
            {"name": "Reverb", "params": {"Decay Time": 4.0, "Dry/Wet": 0.6}},
            {"name": "Chorus-Ensemble", "params": {"Rate 1": 0.5}},
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
            {"name": "Grain Delay", "params": {"Frequency": 1000.0, "Dry/Wet": 0.5}},
            {"name": "Reverb", "params": {"Decay Time": 6.0, "Dry/Wet": 0.7}},
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
            {"name": "Auto Filter", "params": {"Frequency": 3000.0}},
            {"name": "Reverb", "params": {"Decay Time": 2.5, "Dry/Wet": 0.4}},
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
            {"name": "EQ Eight", "params": {"1 Filter Type A": "highpass", "1 Frequency A": 200.0}},
            {"name": "Compressor", "params": {"Threshold": -15.0, "Ratio": 3.0}},
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


# ── Section Templates ──────────────────────────────────────────────
# Each section: name, bar count, which roles play (with optional volume offset)

SECTION_TEMPLATES: dict[str, list[dict]] = {
    "techno": [
        {"name": "Intro",     "bars": 8,  "layers": ["drums:-6dB", "texture"]},
        {"name": "Build",     "bars": 8,  "layers": ["drums", "bass", "percussion"]},
        {"name": "Drop",      "bars": 16, "layers": ["drums", "bass", "lead", "percussion", "texture"]},
        {"name": "Breakdown", "bars": 8,  "layers": ["texture", "vocal", "pad"]},
        {"name": "Drop 2",   "bars": 16, "layers": ["drums", "bass", "lead", "percussion", "vocal", "texture"]},
        {"name": "Outro",     "bars": 8,  "layers": ["drums:-6dB", "texture", "pad"]},
    ],
    "house": [
        {"name": "Intro",     "bars": 8,  "layers": ["drums:-6dB", "pad"]},
        {"name": "Verse",     "bars": 16, "layers": ["drums", "bass", "pad"]},
        {"name": "Drop",      "bars": 16, "layers": ["drums", "bass", "lead", "vocal"]},
        {"name": "Breakdown", "bars": 8,  "layers": ["pad", "texture", "vocal"]},
        {"name": "Drop 2",   "bars": 16, "layers": ["drums", "bass", "lead", "vocal", "texture"]},
        {"name": "Outro",     "bars": 8,  "layers": ["drums:-6dB", "pad"]},
    ],
    "hip hop": [
        {"name": "Intro",  "bars": 4,  "layers": ["texture"]},
        {"name": "Verse",  "bars": 16, "layers": ["drums", "bass", "texture"]},
        {"name": "Hook",   "bars": 8,  "layers": ["drums", "bass", "lead", "vocal"]},
        {"name": "Verse 2", "bars": 16, "layers": ["drums", "bass", "percussion", "texture"]},
        {"name": "Hook 2", "bars": 8,  "layers": ["drums", "bass", "lead", "vocal", "fx"]},
        {"name": "Outro",  "bars": 4,  "layers": ["texture", "vocal:-10dB"]},
    ],
    "ambient": [
        {"name": "Opening",   "bars": 16, "layers": ["pad", "texture"]},
        {"name": "Evolve",    "bars": 16, "layers": ["pad", "texture", "vocal"]},
        {"name": "Peak",      "bars": 16, "layers": ["pad", "texture", "vocal", "lead"]},
        {"name": "Dissolve",  "bars": 16, "layers": ["pad", "texture"]},
    ],
    "drum and bass": [
        {"name": "Intro",     "bars": 8,  "layers": ["texture", "percussion:-6dB"]},
        {"name": "Build",     "bars": 8,  "layers": ["drums:-6dB", "bass", "percussion"]},
        {"name": "Drop",      "bars": 16, "layers": ["drums", "bass", "lead", "percussion", "texture"]},
        {"name": "Breakdown", "bars": 8,  "layers": ["texture", "vocal", "pad"]},
        {"name": "Drop 2",   "bars": 16, "layers": ["drums", "bass", "lead", "percussion", "vocal", "fx"]},
        {"name": "Outro",     "bars": 8,  "layers": ["drums:-6dB", "texture"]},
    ],
    "trap": [
        {"name": "Intro",   "bars": 4,  "layers": ["texture"]},
        {"name": "Verse",   "bars": 16, "layers": ["drums", "bass", "texture"]},
        {"name": "Drop",    "bars": 8,  "layers": ["drums", "bass", "lead", "vocal", "fx"]},
        {"name": "Verse 2", "bars": 16, "layers": ["drums", "bass", "texture", "vocal"]},
        {"name": "Drop 2",  "bars": 8,  "layers": ["drums", "bass", "lead", "vocal", "fx"]},
        {"name": "Outro",   "bars": 4,  "layers": ["texture:-6dB"]},
    ],
    "lo-fi": [
        {"name": "Intro",   "bars": 4,  "layers": ["texture", "pad"]},
        {"name": "A",       "bars": 16, "layers": ["drums", "bass", "pad", "texture"]},
        {"name": "B",       "bars": 16, "layers": ["drums", "bass", "pad", "vocal"]},
        {"name": "A2",      "bars": 16, "layers": ["drums", "bass", "pad", "texture"]},
        {"name": "Outro",   "bars": 8,  "layers": ["pad", "texture"]},
    ],
}

# Fallback template for unknown genres
_DEFAULT_SECTION_TEMPLATE: list[dict] = [
    {"name": "Intro",     "bars": 8,  "layers": ["texture"]},
    {"name": "Build",     "bars": 8,  "layers": ["drums", "bass"]},
    {"name": "Main",      "bars": 16, "layers": ["drums", "bass", "lead", "texture"]},
    {"name": "Breakdown", "bars": 8,  "layers": ["pad", "texture"]},
    {"name": "Main 2",   "bars": 16, "layers": ["drums", "bass", "lead", "vocal", "texture"]},
    {"name": "Outro",     "bars": 8,  "layers": ["drums:-6dB", "texture"]},
]


# ── Planner Functions ──────────────────────────────────────────────

def _build_search_query(template: str, intent: CompositionIntent) -> str:
    """Fill a query template with intent fields."""
    return template.format(
        genre=intent.genre or "electronic",
        mood=intent.mood or "",
        key=intent.key or "",
        tempo=intent.tempo or 120,
    ).strip()


def _build_splice_filters(
    intent: CompositionIntent,
    sample_type: str,
) -> dict:
    """Build Splice filter dict from intent."""
    filters: dict = {}

    # Key → Splice format (lowercase root, separate chord_type)
    if intent.key:
        key = intent.key
        if key.endswith("m") and len(key) >= 2:
            root = key[:-1].lower()
            filters["chord_type"] = "minor"
        else:
            root = key.lower()
            filters["chord_type"] = "major"
        filters["key"] = root

    # BPM range (+-5)
    if intent.tempo:
        filters["bpm_min"] = max(1, intent.tempo - 5)
        filters["bpm_max"] = intent.tempo + 5

    if intent.genre:
        filters["genre"] = intent.genre

    if sample_type:
        filters["sample_type"] = sample_type

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
    """
    roles = _select_roles(intent)
    sections = plan_sections(intent)
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

        # Build Splice filters
        splice_filters = _build_splice_filters(intent, template["sample_type"])

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


def plan_sections(intent: CompositionIntent) -> list[dict]:
    """Plan arrangement sections based on genre and duration.

    Returns a list of dicts: {name, bars, layers, start_bar}.
    """
    template = SECTION_TEMPLATES.get(intent.genre, _DEFAULT_SECTION_TEMPLATE)

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
