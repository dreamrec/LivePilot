"""Prompt parser — natural language → structured CompositionIntent.

Extracts genre, mood, tempo, key, descriptors, and explicit element requests
from free-form text prompts. Pure computation, no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Data Model ─────────────────────────────────────────────────────

@dataclass
class CompositionIntent:
    """Structured representation of a composition request."""

    genre: str = ""
    sub_genre: str = ""
    mood: str = ""
    tempo: int = 0               # 0 = auto-detect from genre
    key: str = ""                # "" = auto-pick based on mood
    descriptors: list[str] = field(default_factory=list)
    explicit_elements: list[str] = field(default_factory=list)
    energy: float = 0.5          # 0.0-1.0
    layer_count: int = 0         # 0 = auto (genre determines)
    duration_bars: int = 64      # total arrangement length

    def to_dict(self) -> dict:
        return {
            "genre": self.genre,
            "sub_genre": self.sub_genre,
            "mood": self.mood,
            "tempo": self.tempo,
            "key": self.key,
            "descriptors": self.descriptors,
            "explicit_elements": self.explicit_elements,
            "energy": self.energy,
            "layer_count": self.layer_count,
            "duration_bars": self.duration_bars,
        }


# ── Genre Defaults ─────────────────────────────────────────────────
# genre → (default_tempo, default_keys, default_energy, layer_range)

GENRE_DEFAULTS: dict[str, dict] = {
    "techno": {
        "tempo": 128, "keys": ["Am", "Cm"], "energy": 0.7,
        "layers_min": 5, "layers_max": 7,
    },
    # Dub techno is its own canonical genre — continuous-evolution aesthetic
    # referencing Basic Channel / Rhythm & Sound / Gas. Previously aliased to
    # "techno" which defaulted to Drop-based scaffolds (v1.18.1 #2 fix).
    "dub techno": {
        "tempo": 125, "keys": ["Am", "Em"], "energy": 0.4,
        "layers_min": 3, "layers_max": 5,
    },
    "house": {
        "tempo": 124, "keys": ["Cm", "Fm"], "energy": 0.6,
        "layers_min": 5, "layers_max": 6,
    },
    "hip hop": {
        "tempo": 90, "keys": ["Cm", "Gm"], "energy": 0.5,
        "layers_min": 4, "layers_max": 6,
    },
    "ambient": {
        "tempo": 80, "keys": ["C", "Am"], "energy": 0.2,
        "layers_min": 3, "layers_max": 5,
    },
    "drum and bass": {
        "tempo": 174, "keys": ["Am", "Em"], "energy": 0.8,
        "layers_min": 5, "layers_max": 7,
    },
    "trap": {
        "tempo": 140, "keys": ["Cm", "Bbm"], "energy": 0.6,
        "layers_min": 4, "layers_max": 6,
    },
    "lo-fi": {
        "tempo": 85, "keys": ["Fm", "Cm"], "energy": 0.3,
        "layers_min": 3, "layers_max": 5,
    },
}

# Aliases that map to canonical genre names
_GENRE_ALIASES: dict[str, str] = {
    "dnb": "drum and bass",
    "d&b": "drum and bass",
    "jungle": "drum and bass",
    "lofi": "lo-fi",
    "lo fi": "lo-fi",
    "hiphop": "hip hop",
    "hip-hop": "hip hop",
    "deep house": "house",
    "tech house": "house",
    "acid techno": "techno",
    "hard techno": "techno",
    "industrial techno": "techno",
    "minimal techno": "techno",
    "detroit techno": "techno",
    # NOTE: "dub techno" is intentionally NOT aliased to "techno" —
    # it's now its own canonical genre with dub-appropriate defaults
    # (see GENRE_DEFAULTS above) and a non-Drop section template (see
    # layer_planner.SECTION_TEMPLATES).  v1.18.1 #2 fix.
    "dub-techno": "dub techno",
}


# ── Mood Mapping ───────────────────────────────────────────────────
# mood → (energy_range, key_bias_list)

MOOD_MAPPING: dict[str, dict] = {
    "dark": {
        "energy_min": 0.4, "energy_max": 0.6,
        "key_bias": ["Am", "Cm", "Em", "Dm"],
    },
    "euphoric": {
        "energy_min": 0.8, "energy_max": 1.0,
        "key_bias": ["C", "G", "F", "A"],
    },
    "melancholic": {
        "energy_min": 0.2, "energy_max": 0.4,
        "key_bias": ["Fm", "Cm", "Dm", "Bbm"],
    },
    "aggressive": {
        "energy_min": 0.8, "energy_max": 0.9,
        "key_bias": ["Am", "Em", "Bm", "F#m"],
    },
    "dreamy": {
        "energy_min": 0.2, "energy_max": 0.3,
        "key_bias": ["C", "F", "Bb", "Eb"],
    },
    "chill": {
        "energy_min": 0.2, "energy_max": 0.4,
        "key_bias": ["Fm", "Cm", "Gm", "Dm"],
    },
    "hypnotic": {
        "energy_min": 0.5, "energy_max": 0.7,
        "key_bias": ["Am", "Em", "Dm"],
    },
    "ethereal": {
        "energy_min": 0.2, "energy_max": 0.4,
        "key_bias": ["C", "F", "Ab", "Eb"],
    },
    "driving": {
        "energy_min": 0.7, "energy_max": 0.9,
        "key_bias": ["Am", "Em", "Cm"],
    },
    "warm": {
        "energy_min": 0.3, "energy_max": 0.5,
        "key_bias": ["F", "Bb", "Eb", "Ab"],
    },
}


# ── Sub-genre keywords ─────────────────────────────────────────────

_SUB_GENRE_KEYWORDS: list[str] = [
    "minimal", "deep", "acid", "industrial", "detroit", "dub",
    "progressive", "melodic", "hard", "dark", "atmospheric",
    "organic", "analog", "modular", "breakbeat", "uk garage",
    "2-step", "drill", "boom bap", "old school", "new wave",
]


# ── Descriptor keywords (adjectives that color the composition) ────

_DESCRIPTOR_KEYWORDS: list[str] = [
    "industrial", "ghostly", "warm", "cold", "metallic", "organic",
    "spacious", "intimate", "raw", "polished", "gritty", "clean",
    "distorted", "saturated", "lush", "sparse", "dense", "airy",
    "punchy", "soft", "crisp", "muddy", "bright", "muted",
    "psychedelic", "glitchy", "cinematic", "underground", "futuristic",
    "retro", "vintage", "modern", "classic", "experimental",
]


# ── Element extraction patterns ────────────────────────────────────

_ELEMENT_PATTERNS: list[tuple[str, str]] = [
    # (regex_pattern, element_name)
    (r"\bwith\s+vocals?\b", "vocal"),
    (r"\bwith\s+strings?\b", "strings"),
    (r"\badd\s+strings?\b", "strings"),
    (r"\b808\s*bass\b", "808"),
    (r"\bwith\s+808\b", "808"),
    (r"\bwith\s+synth\b", "synth"),
    (r"\bwith\s+pads?\b", "pad"),
    (r"\bwith\s+piano\b", "piano"),
    (r"\bwith\s+guitar\b", "guitar"),
    (r"\bwith\s+brass\b", "brass"),
    (r"\bwith\s+horns?\b", "brass"),
    (r"\bwith\s+(?:fx|effects?)\b", "fx"),
    (r"\bwith\s+risers?\b", "fx"),
    (r"\bwith\s+(?:perc|percussion)\b", "percussion"),
    (r"\bwith\s+textures?\b", "texture"),
    (r"\bghostly\s+vocals?\b", "vocal"),
    (r"\bvocal\s+chops?\b", "vocal"),
    (r"\bvocal\s+stabs?\b", "vocal"),
    (r"\bsub\s*bass\b", "bass"),
    (r"\breese\s*bass\b", "bass"),
    (r"\bamen\s+break\b", "drums"),
    (r"\bbreakbeat\b", "drums"),
    (r"\bfoley\b", "texture"),
    (r"\bfield\s+recordings?\b", "texture"),
    (r"\batmospheric\b", "texture"),
]


# ── Regex helpers ──────────────────────────────────────────────────

_TEMPO_RE = re.compile(r"\b(\d{2,3})\s*bpm\b", re.IGNORECASE)

# Key patterns: must have either an accidental (C#, Db) OR an explicit
# quality word (C minor, F major, Am). The previous regex made the
# quality group optional AND allowed a bare letter — so "dark ambient"
# matched D as a key root, silently overwriting any mood-inferred key.
_KEY_RE = re.compile(
    # Case 1: root + quality word (explicit minor/major/min/maj/m suffix)
    r"\b([A-Ga-g])\s*(minor|major|min|maj|m)\b"
    # Case 2: root + accidental (optional quality)
    r"|\b([A-Ga-g][#b])\s*(minor|major|min|maj|m)?\b"
)


# ── Parser ─────────────────────────────────────────────────────────

def parse_prompt(text: str) -> CompositionIntent:
    """Parse a natural language composition prompt into structured intent.

    Examples:
        "dark minimal techno 128bpm Cm"
        "euphoric deep house with vocals"
        "lo-fi hip hop 85bpm F minor dreamy"
        "aggressive drum and bass 174bpm Am"
    """
    intent = CompositionIntent()
    text_lower = text.lower().strip()

    # 1. Extract tempo
    tempo_match = _TEMPO_RE.search(text)
    if tempo_match:
        intent.tempo = int(tempo_match.group(1))

    # 2. Extract key (search original text to preserve case)
    # Regex has TWO alternations (root+quality OR root-with-accidental
    # +optional-quality). Take whichever branch matched.
    key_match = _KEY_RE.search(text)
    if key_match:
        root = key_match.group(1) or key_match.group(3)
        quality = key_match.group(2) or key_match.group(4) or ""
        # Normalize root: uppercase first letter, preserve accidental
        root = root[0].upper() + root[1:] if len(root) > 1 else root.upper()
        quality_lower = quality.lower()
        if quality_lower in ("minor", "min", "m"):
            intent.key = f"{root}m"
        elif quality_lower in ("major", "maj"):
            intent.key = root
        else:
            # Only reached when Case 2 matched without quality — an
            # accidental was present (C#, Db), so this IS a legit key root.
            intent.key = root

    # 3. Match genre (check aliases first, then canonical names)
    # Sort by length descending to match longer aliases first
    all_genres = list(_GENRE_ALIASES.items()) + [
        (g, g) for g in GENRE_DEFAULTS
    ]
    all_genres.sort(key=lambda x: -len(x[0]))

    for alias, canonical in all_genres:
        if alias in text_lower:
            intent.genre = canonical
            # Extract sub-genre from the alias if it differs
            if alias != canonical and " " in alias:
                parts = alias.split()
                for part in parts:
                    if part != canonical and part in text_lower:
                        intent.sub_genre = part
            break

    # 4. Check for sub-genre keywords not caught by alias matching
    if not intent.sub_genre:
        for kw in _SUB_GENRE_KEYWORDS:
            if kw in text_lower and kw != intent.genre:
                intent.sub_genre = kw
                break

    # 5. Match mood
    for mood_name in MOOD_MAPPING:
        if mood_name in text_lower:
            intent.mood = mood_name
            break

    # 6. Extract descriptors
    for descriptor in _DESCRIPTOR_KEYWORDS:
        if descriptor in text_lower and descriptor != intent.mood and descriptor != intent.sub_genre:
            intent.descriptors.append(descriptor)

    # 7. Extract explicit elements
    seen_elements: set[str] = set()
    for pattern, element in _ELEMENT_PATTERNS:
        if re.search(pattern, text_lower) and element not in seen_elements:
            intent.explicit_elements.append(element)
            seen_elements.add(element)

    # 8. Apply genre defaults for missing fields
    genre_info = GENRE_DEFAULTS.get(intent.genre, {})

    if intent.tempo == 0 and genre_info:
        intent.tempo = genre_info["tempo"]

    if not intent.key:
        # Use mood bias if available, otherwise genre default
        if intent.mood and intent.mood in MOOD_MAPPING:
            intent.key = MOOD_MAPPING[intent.mood]["key_bias"][0]
        elif genre_info:
            intent.key = genre_info["keys"][0]

    # 9. Compute energy from mood, fallback to genre
    if intent.mood and intent.mood in MOOD_MAPPING:
        mood_info = MOOD_MAPPING[intent.mood]
        intent.energy = (mood_info["energy_min"] + mood_info["energy_max"]) / 2.0
    elif genre_info:
        intent.energy = genre_info["energy"]
    else:
        intent.energy = 0.5

    # 10. Determine layer count from genre + energy
    if intent.layer_count == 0 and genre_info:
        base_min = genre_info["layers_min"]
        base_max = genre_info["layers_max"]
        # Higher energy → more layers
        energy_factor = intent.energy
        intent.layer_count = round(
            base_min + (base_max - base_min) * energy_factor
        )

    # Fallback defaults
    if intent.tempo == 0:
        intent.tempo = 120
    if not intent.key:
        intent.key = "Am"
    if intent.layer_count == 0:
        intent.layer_count = 5

    return intent
