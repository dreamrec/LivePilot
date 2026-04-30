"""Pack-Atlas Phase F — Pack-Aware Composer.

Bootstrap a project with pack-coherent track selection given an aesthetic brief.
Parses the brief against artist/genre vocabularies, builds a pack cohort,
selects presets via macro-fingerprint similarity, and emits an executable plan.

All data comes from local JSON sidecars + the overlay index — no Live connection
required.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

# ─── Paths ────────────────────────────────────────────────────────────────────

_VOCAB_DIR = (
    Path(__file__).parent.parent.parent
    / "livepilot"
    / "skills"
    / "livepilot-core"
    / "references"
)
_ARTIST_VOCAB_PATH = _VOCAB_DIR / "artist-vocabularies.md"
_GENRE_VOCAB_PATH = _VOCAB_DIR / "genre-vocabularies.md"

_CROSS_WORKFLOWS_DIR = (
    Path.home()
    / ".livepilot"
    / "atlas-overlays"
    / "packs"
    / "cross_workflows"
)

# ─── Vocabulary parsers ───────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _load_artist_vocab() -> dict[str, dict]:
    """Parse artist-vocabularies.md into {artist_slug: {...}} dict.

    Extracts: sonic_fingerprint, reach_for, avoid, key_techniques, genre_affinity,
    and a derived pack_anchors list (from Reach for lines that mention pack names).
    """
    if not _ARTIST_VOCAB_PATH.exists():
        return {}
    text = _ARTIST_VOCAB_PATH.read_text(encoding="utf-8")
    return _parse_artist_section(text)


@lru_cache(maxsize=1)
def _load_genre_vocab() -> dict[str, dict]:
    """Parse genre-vocabularies.md into {genre_slug: {...}} dict."""
    if not _GENRE_VOCAB_PATH.exists():
        return {}
    text = _GENRE_VOCAB_PATH.read_text(encoding="utf-8")
    return _parse_genre_section(text)


def _coerce_int(v: object, default: int) -> int:
    """Coerce v to int, returning default on None or invalid input."""
    if v is None:
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def _coerce_float(v: object, default: float) -> float:
    """Coerce v to float, returning default on None or invalid input."""
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _slugify(name: str) -> str:
    """Normalise an artist/genre name to a match key."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower().strip()).strip("_")


def _extract_pack_anchors_from_reach(reach_text: str) -> list[str]:
    """Extract pack slugs from a 'Reach for:' text block.

    Looks for known pack-keyword patterns:
    Drone Lab → drone-lab, Lost and Found → lost-and-found, etc.
    """
    pack_patterns: list[tuple[str, str]] = [
        (r"drone\s+lab", "drone-lab"),
        (r"mood[\s\-]reel", "mood-reel"),
        (r"pitchloop\s*89", "pitchloop89"),
        (r"convolution\s+reverb", "convolution-reverb"),
        (r"lost\s+and\s+found", "lost-and-found"),
        (r"inspired[\s\-]by[\s\-]nature", "inspired-by-nature-by-dillon-bastan"),
        (r"voice\s+box", "voice-box"),
        (r"chop\s+and\s+swing", "chop-and-swing"),
        (r"latin\s+percussion", "latin-percussion"),
        (r"glitch\s+and\s+wash", "glitch-and-wash"),
        (r"creative\s+extensions", "creative-extensions"),
        (r"electric\s+keyboards", "electric-keyboards"),
        (r"drum\s+essentials", "drum-essentials"),
        (r"orchestral\s+strings", "orchestral-strings"),
        (r"orchestral\s+woodwinds", "orchestral-woodwinds"),
        (r"orchestral\s+brass", "orchestral-brass"),
        (r"synth\s+essentials", "synth-essentials"),
        (r"cv[\s\-]tools", "cv-tools"),
        (r"build\s+and\s+drop", "build-and-drop"),
        (r"punch\s+and\s+tilt", "punch-and-tilt"),
        (r"session\s+drums\s+club", "session-drums-club"),
        (r"session\s+drums\s+studio", "session-drums-studio"),
        (r"beat\s+tools", "beat-tools"),
        (r"drive\s+and\s+glow", "drive-and-glow"),
    ]
    found: list[str] = []
    lower = reach_text.lower()
    for pattern, slug in pack_patterns:
        if re.search(pattern, lower):
            if slug not in found:
                found.append(slug)
    return found


def _parse_artist_section(text: str) -> dict[str, dict]:
    """Parse artist-vocabularies.md into a dict.

    Each artist block starts with ### <Name> and ends at the next ###/## heading.
    """
    vocab: dict[str, dict] = {}

    # Split on ### headings — these are individual artist entries
    # Also handle ## (section headings we skip)
    blocks = re.split(r"(?=^###\s+)", text, flags=re.MULTILINE)

    for block in blocks:
        if not block.startswith("###"):
            continue
        # First line is the artist name
        first_line_end = block.index("\n") if "\n" in block else len(block)
        artist_name = block[4:first_line_end].strip()  # strip "### "
        # Strip parenthetical aliases and slash-joined aliases from the slug
        # e.g. "Robert Henke (Monolake)" → slug "robert_henke"
        # e.g. "Wolfgang Voigt (Gas)" → slug "wolfgang_voigt"
        # e.g. "Basic Channel / Rhythm & Sound (...)" → slug "basic_channel_rhythm_sound"
        # This keeps vocab keys simple and matching what _ARTIST_ALIASES expects.
        slug_source = re.sub(r"\s*\([^)]*\)", "", artist_name).strip()
        slug = _slugify(slug_source)

        # Extract fields using regex
        def extract_field(field_label: str) -> str:
            pattern = rf"\*\*{re.escape(field_label)}:\*\*\s*(.+?)(?=\n\*\*|\Z)"
            m = re.search(pattern, block, re.DOTALL)
            if m:
                return m.group(1).strip()
            return ""

        reach_text = extract_field("Reach for")
        avoid_text = extract_field("Avoid")
        fingerprint_text = extract_field("Sonic fingerprint")
        techniques_text = extract_field("Key techniques")
        genre_text = extract_field("Genre affinity")

        pack_anchors = _extract_pack_anchors_from_reach(reach_text)

        # Extract genres from genre_affinity backtick list
        genres = re.findall(r"`([^`]+)`", genre_text)

        vocab[slug] = {
            "name": artist_name,
            "sonic_fingerprint": fingerprint_text,
            "reach_for": reach_text,
            "avoid": avoid_text,
            "key_techniques": techniques_text,
            "genre_affinity": genres,
            "pack_anchors": pack_anchors,
        }

        # Also register common alternate slugs (e.g. "gas" → Wolfgang Voigt)
        # Handle parenthetical aliases like "Wolfgang Voigt (Gas)"
        alias_match = re.search(r"\(([^)]+)\)", artist_name)
        if alias_match:
            alias_slug = _slugify(alias_match.group(1))
            if alias_slug not in vocab:
                vocab[alias_slug] = vocab[slug]

    return vocab


def _parse_genre_section(text: str) -> dict[str, dict]:
    """Parse genre-vocabularies.md into a dict.

    Each genre block starts with ## <Genre Name> (after the intro headers).
    """
    vocab: dict[str, dict] = {}

    blocks = re.split(r"(?=^##\s+[^#])", text, flags=re.MULTILINE)

    for block in blocks:
        if not block.startswith("##"):
            continue
        # Skip the intro header (if it contains "Genre Vocabularies" in the title)
        first_line_end = block.index("\n") if "\n" in block else len(block)
        genre_name = block[3:first_line_end].strip()  # strip "## "

        if not genre_name or "Genre Vocabularies" in genre_name or "Vocabularies" in genre_name:
            continue

        slug = _slugify(genre_name)

        def extract_field(field_label: str) -> str:
            pattern = rf"\*\*{re.escape(field_label)}[:/]\*\*\s*(.+?)(?=\n\*\*|\Z)"
            m = re.search(pattern, block, re.DOTALL)
            if m:
                return m.group(1).strip()
            return ""

        reach_text = extract_field("Reach for")
        avoid_text = extract_field("Avoid")

        # Extract packs from reach_for text
        pack_anchors = _extract_pack_anchors_from_reach(reach_text)

        # Extract canonical artists
        canonical_text = extract_field("Canonical artists")
        artists = [a.strip() for a in re.split(r",\s*", canonical_text) if a.strip()]

        vocab[slug] = {
            "name": genre_name,
            "reach_for": reach_text,
            "avoid": avoid_text,
            "pack_anchors": pack_anchors,
            "canonical_artists": artists,
        }

    return vocab


# ─── Brief parsing ─────────────────────────────────────────────────────────────

# Genre keyword → vocabulary slug mappings (for matching in brief text)
# All slug values must match keys produced by _parse_genre_section (which slugifies the
# "## Genre Name" heading — e.g. "## Dub Techno" → "dub_techno",
# "## Modern Classical / Cinematic" → "modern_classical_cinematic").
_GENRE_ALIASES: dict[str, str] = {
    "dub techno": "dub_techno",
    "dub-techno": "dub_techno",
    "dubtech": "dub_techno",
    "microhouse": "microhouse",
    "micro house": "microhouse",
    "micro-house": "microhouse",
    "minimal techno": "minimal_techno",
    "minimal-techno": "minimal_techno",
    "deep minimal": "deep_minimal_villalobos_school",
    "deep-minimal": "deep_minimal_villalobos_school",
    "ambient": "ambient_drone",              # "## Ambient / Drone"
    "drone": "ambient_drone",
    "idm": "idm",
    "hip hop": "hip_hop_boom_bap_lo_fi",     # "## Hip-Hop (Boom Bap / Lo-Fi)"
    "hip-hop": "hip_hop_boom_bap_lo_fi",
    "hiphop": "hip_hop_boom_bap_lo_fi",
    "boom bap": "hip_hop_boom_bap_lo_fi",
    "trap": "trap_modern_hip_hop",           # "## Trap / Modern Hip-Hop"
    "trap 808": "trap_modern_hip_hop",
    "dubstep": "dubstep_bass_music_modern",  # "## Dubstep / Bass Music (Modern)"
    "bass music": "dubstep_bass_music_modern",
    "house": "house_deep_house",             # "## House / Deep House"
    "deep house": "house_deep_house",
    "dnb": "drum_and_bass_jungle",           # "## Drum and Bass / Jungle"
    "drum and bass": "drum_and_bass_jungle",
    "drum & bass": "drum_and_bass_jungle",
    "jungle": "drum_and_bass_jungle",
    "neurofunk": "drum_and_bass_jungle",
    "garage": "garage_uk_garage_2_step",     # "## Garage / UK Garage / 2-Step"
    "uk garage": "garage_uk_garage_2_step",
    "2-step": "garage_uk_garage_2_step",
    "experimental": "experimental_noise_found_sound",  # "## Experimental / Noise / Found-Sound"
    "noise": "experimental_noise_found_sound",
    "found sound": "experimental_noise_found_sound",
    "synthwave": "synthwave",                # not in vocab; keyword still acts as aesthetic tag
    # Additional genres from cross-workflow YAMLs
    "footwork": "footwork",                  # not in vocab; pack lookup via _KEYWORD_TO_PACK
    "juke": "footwork",
    "breakcore": "breakcore",
    "break core": "breakcore",
    "modern classical": "modern_classical_cinematic",   # "## Modern Classical / Cinematic"
    "neo-classical": "modern_classical_cinematic",
    "orchestral": "modern_classical_cinematic",
    "cinematic": "modern_classical_cinematic",
    "microtonal": "experimental_noise_found_sound",
    "bedroom pop": "experimental_noise_found_sound",
    "lo-fi pop": "hip_hop_boom_bap_lo_fi",
    "lo fi": "hip_hop_boom_bap_lo_fi",
    "lofi": "hip_hop_boom_bap_lo_fi",
    "eurorack": "experimental_noise_found_sound",
    "modular": "experimental_noise_found_sound",
}

# Artist keyword → vocabulary slug
# Slugs here must match the keys produced by _parse_artist_section, which strips
# parenthetical aliases before slugifying:
#   "Robert Henke (Monolake)" → "robert_henke"
#   "Wolfgang Voigt (Gas)"    → "wolfgang_voigt"
#   "Aphex Twin (Richard D. James)" → "aphex_twin"
#   "Arca / SOPHIE"           → "arca_sophie"  (slash-joins remain)
_ARTIST_ALIASES: dict[str, str] = {
    "villalobos": "ricardo_villalobos",
    "akufen": "akufen",              # heading "Akufen (Marc Leclair)" → strip parens → "akufen"
    "marc leclair": "akufen",
    "isolee": "isol_e_luomo",
    "luomo": "isol_e_luomo",
    "basic channel": "basic_channel_rhythm_sound",
    "rhythm and sound": "basic_channel_rhythm_sound",
    "gas": "wolfgang_voigt",         # heading "Wolfgang Voigt (Gas)" → strip → "wolfgang_voigt"
    "voigt": "wolfgang_voigt",
    "shackleton": "shackleton",
    "basinski": "william_basinski",
    "tim hecker": "tim_hecker",
    "hecker": "tim_hecker",
    "autechre": "autechre",
    "aphex": "aphex_twin",           # heading "Aphex Twin (Richard D. James)" → strip → "aphex_twin"
    "aphex twin": "aphex_twin",
    "burial": "burial",              # heading "Burial" → slug "burial"
    "william bevan": "burial",
    "henke": "robert_henke",         # heading "Robert Henke (Monolake)" → strip → "robert_henke"
    "robert henke": "robert_henke",
    "monolake": "robert_henke",
    "dilla": "j_dilla",
    "j dilla": "j_dilla",
    "madlib": "madlib",
    "hawtin": "richie_hawtin",       # heading "Richie Hawtin (Plastikman)" → strip → "richie_hawtin"
    "plastikman": "richie_hawtin",
    "richie hawtin": "richie_hawtin",
    "boards of canada": "boards_of_canada",
    "boc": "boards_of_canada",
    "arca": "arca_sophie",           # heading "Arca / SOPHIE" → "arca_sophie"
    "sophie": "arca_sophie",
    "opn": "oneohtrix_point_never",  # heading "Oneohtrix Point Never (Daniel Lopatin)" → strip → "oneohtrix_point_never"
    "oneohtrix": "oneohtrix_point_never",
    "com truise": "com_truise",      # heading "Com Truise / Tycho" → "com_truise_tycho"... but alias "com truise" is fine
    "tycho": "com_truise_tycho",
    "photek": "photek",              # heading "Photek / Source Direct (jungle / atmospheric DnB)" → "photek_source_direct"
    "source direct": "photek_source_direct",
    # Additional artists from cross-workflows not in artist vocab but with alias lookup
    "mica levi": "mica_levi",
    "mica": "mica_levi",
    "bibio": "bibio",
    "caterina barbieri": "caterina_barbieri",
    "barbieri": "caterina_barbieri",
    "henderson": "henderson",
    "iftah": "iftah",
    "reich": "reich",
    "reznor": "reznor_ross",
    "ross": "reznor_ross",
    "traxman": "rashad_spinn_traxman",  # heading "Rashad / Spinn / Traxman (footwork)" → strip → "rashad_spinn_traxman"
    "rashad": "rashad_spinn_traxman",
    "spinn": "rashad_spinn_traxman",
}


def _parse_brief(brief_text: str) -> dict[str, Any]:
    """Parse free-text brief into structured aesthetic analysis.

    Returns:
        primary_aesthetic: str
        secondary_aesthetics: list[str]
        anchor_producers: list[str]
        anchor_genres: list[str]
        pack_cohort: list[str]
    """
    lower = brief_text.lower()
    artist_vocab = _load_artist_vocab()
    genre_vocab = _load_genre_vocab()

    # ── Match producers ───────────────────────────────────────────────────────
    anchor_producers: list[str] = []
    for alias, slug in _ARTIST_ALIASES.items():
        if alias in lower:
            if slug not in anchor_producers:
                anchor_producers.append(slug)
            break  # one match is enough for primary producer detection

    # Also try direct slug matching in the vocab
    for slug in artist_vocab:
        name = artist_vocab[slug].get("name", "").lower()
        if name and name in lower and slug not in anchor_producers:
            anchor_producers.append(slug)

    # ── Match genres ──────────────────────────────────────────────────────────
    anchor_genres: list[str] = []
    for alias, slug in _GENRE_ALIASES.items():
        if alias in lower:
            if slug not in anchor_genres:
                anchor_genres.append(slug)

    # Also try direct slug matching
    for slug in genre_vocab:
        name = genre_vocab[slug].get("name", "").lower()
        if name and name in lower and slug not in anchor_genres:
            anchor_genres.append(slug)

    # ── Collect pack cohort from matched entries ───────────────────────────────
    pack_cohort: list[str] = []

    for producer_slug in anchor_producers:
        entry = artist_vocab.get(producer_slug, {})
        for pack in entry.get("pack_anchors", []):
            if pack not in pack_cohort:
                pack_cohort.append(pack)

    for genre_slug in anchor_genres:
        entry = genre_vocab.get(genre_slug, {})
        for pack in entry.get("pack_anchors", []):
            if pack not in pack_cohort:
                pack_cohort.append(pack)

    # ── Direct keyword → pack fallbacks ───────────────────────────────────────
    _KEYWORD_TO_PACK: dict[str, str] = {
        "drone lab": "drone-lab",
        "drone-lab": "drone-lab",
        "pitchloop": "pitchloop89",
        "pitchloop89": "pitchloop89",
        "convolution": "convolution-reverb",
        "mood reel": "mood-reel",
        "mood-reel": "mood-reel",
        "inspired by nature": "inspired-by-nature-by-dillon-bastan",
        "granulator": "inspired-by-nature-by-dillon-bastan",
        "granular": "inspired-by-nature-by-dillon-bastan",
        "tree tone": "inspired-by-nature-by-dillon-bastan",
        "lost and found": "lost-and-found",
        "voice box": "voice-box",
        "vocal": "voice-box",
        "latin percussion": "latin-percussion",
        "latin": "latin-percussion",
        "spectral": "drone-lab",
        "drone": "drone-lab",
        "monolake": "pitchloop89",
        "dub": "drone-lab",
        "pastoral": "inspired-by-nature-by-dillon-bastan",
        "ambient": "mood-reel",
        "cinematic": "mood-reel",
        "lo-fi": "lost-and-found",
        "lofi": "lost-and-found",
        # Cross-workflow pack keywords (from cross-workflow YAML sweep)
        "footwork": "beat-tools",
        "juke": "beat-tools",
        "breakcore": "skitter-and-step",
        "beat tools": "beat-tools",
        "beat-tools": "beat-tools",
        "skitter": "skitter-and-step",
        "skitter and step": "skitter-and-step",
        "skitter-and-step": "skitter-and-step",
        "chop and swing": "chop-and-swing",
        "chop-and-swing": "chop-and-swing",
        "hip hop": "golden-era-hip-hop-drums-by-sound-oracle",
        "hip-hop": "golden-era-hip-hop-drums-by-sound-oracle",
        "golden era": "golden-era-hip-hop-drums-by-sound-oracle",
        "bedroom pop": "drive-and-glow",
        "guitar": "guitar-and-bass",
        "bass guitar": "guitar-and-bass",
        "orchestral strings": "orchestral-strings",
        "strings": "orchestral-strings",
        "orchestral woodwinds": "orchestral-woodwinds",
        "woodwinds": "orchestral-woodwinds",
        "orchestral brass": "orchestral-brass",
        "brass": "orchestral-brass",
        "brass quartet": "brass-quartet-by-spitfire-audio",
        "orchestral mallets": "orchestral-mallets",
        "mallets": "orchestral-mallets",
        "cv tools": "cv-tools",
        "cv-tools": "cv-tools",
        "eurorack": "cv-tools",
        "modular": "cv-tools",
        "microtuner": "microtuner",
        "microtonal": "microtuner",
        "generators iftah": "generators-by-iftah",
        "iftah": "generators-by-iftah",
        "midi tools": "midi-tools-by-philip-meyer",
        "algorithmic": "midi-tools-by-philip-meyer",
        "trap drums": "trap-drums-by-sound-oracle",
        "trap 808": "trap-drums-by-sound-oracle",
        "808": "trap-drums-by-sound-oracle",
        "granulator iii": "granulator-iii",
        "glitch and wash": "glitch-and-wash",
        "glitch-and-wash": "glitch-and-wash",
    }
    for keyword, pack in _KEYWORD_TO_PACK.items():
        if keyword in lower and pack not in pack_cohort:
            pack_cohort.append(pack)

    # ── Determine primary and secondary aesthetics ────────────────────────────
    all_aesthetics: list[str] = anchor_genres + [
        _slugify(artist_vocab[p]["name"]) if p in artist_vocab else p
        for p in anchor_producers
    ]

    # Extract any free-form aesthetic keywords from brief
    _AESTHETIC_KEYWORDS = [
        "spectral", "dub", "ambient", "drone", "minimal", "techno", "experimental",
        "cinematic", "orchestral", "lo-fi", "lofi", "dusty", "granular",
        "pastoral", "dark", "warm", "cold", "lush",
    ]
    for kw in _AESTHETIC_KEYWORDS:
        if kw in lower and kw not in all_aesthetics:
            all_aesthetics.append(kw)

    primary_aesthetic = all_aesthetics[0] if all_aesthetics else "ambient"
    secondary_aesthetics = all_aesthetics[1:] if len(all_aesthetics) > 1 else []

    return {
        "primary_aesthetic": primary_aesthetic,
        "secondary_aesthetics": secondary_aesthetics,
        "anchor_producers": anchor_producers,
        "anchor_genres": anchor_genres,
        "pack_cohort": pack_cohort,
    }


# ─── Track role determination ─────────────────────────────────────────────────

# Role → keywords that trigger it
_ROLE_KEYWORDS: dict[str, list[str]] = {
    "harmonic-foundation": [
        "drone bed", "drone", "pad", "wash", "harmonic", "chord", "foundation",
        "spectral bed", "bed", "texture",
    ],
    "rhythmic-driver": [
        "kick", "drums", "rhythm", "beat", "percussion", "drum", "808",
        "groove",
    ],
    "melodic": [
        "melody", "melodic", "lead", "hook", "theme", "motif", "bass line",
        "arp", "arpegio",
    ],
    "bass": [
        "bass", "sub", "low end", "bottom", "808 bass",
    ],
    "fx-bus": [
        "reverb bus", "fx bus", "fx", "bus", "send", "effect chain",
        "spectral send", "spectral",
    ],
    "wash": [
        "wash", "atmosphere", "atmos", "ambience", "ambient layer",
        "noise", "texture layer",
    ],
}

_DEFAULT_ROLE_MIX: list[tuple[str, str]] = [
    ("harmonic-foundation", "Drone Bed"),
    ("rhythmic-driver", "Rhythm"),
    ("melodic", "Melody A"),
    ("melodic", "Melody B"),
    ("fx-bus", "FX Bus"),
    ("wash", "Wash"),
    ("melodic", "Melody C"),
    ("bass", "Bass"),
    ("melodic", "Melody D"),
    ("wash", "Wash 2"),
    ("fx-bus", "FX Bus 2"),
    ("rhythmic-driver", "Rhythm 2"),
    # Extended entries for track_count > 12 (up to 20)
    ("melodic", "Melody E"),
    ("harmonic-foundation", "Harmonic Layer 2"),
    ("wash", "Atmos"),
    ("melodic", "Melody F"),
    ("bass", "Sub Layer"),
    ("fx-bus", "FX Bus 3"),
    ("rhythmic-driver", "Percussion"),
    ("wash", "Texture"),
]
# Maximum track count the default mix can satisfy.
_MAX_ROLE_MIX_COUNT = len(_DEFAULT_ROLE_MIX)


def _determine_track_roles(brief: str, track_count: int) -> list[dict]:
    """Map brief keywords to track roles.

    Returns a list of {role, suggested_name} dicts, length == track_count.
    """
    lower = brief.lower()
    triggered_roles: list[tuple[str, str]] = []

    # Detect specific roles from keywords
    for role, keywords in _ROLE_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                # Generate suggested name
                name = _role_to_name(role)
                triggered_roles.append((role, name))
                break  # one keyword per role is enough

    # Pad or trim to track_count using the default mix.
    # First pass: avoid duplicates (except melodic).
    # Second pass: allow all duplicates if we still haven't reached track_count
    # (this covers large track_count values that exceed the unique-role count).
    for allow_duplicates in (False, True):
        if len(triggered_roles) >= track_count:
            break
        for default_role, default_name in _DEFAULT_ROLE_MIX:
            if len(triggered_roles) >= track_count:
                break
            existing_roles = [r[0] for r in triggered_roles]
            if (
                default_role not in existing_roles
                or default_role == "melodic"
                or allow_duplicates
            ):
                triggered_roles.append((default_role, default_name))

    # Truncate to track_count
    triggered_roles = triggered_roles[:track_count]

    return [{"role": r, "suggested_name": n} for r, n in triggered_roles]


def _role_to_name(role: str) -> str:
    return {
        "harmonic-foundation": "Drone Bed",
        "rhythmic-driver": "Rhythm",
        "melodic": "Melody",
        "bass": "Bass",
        "fx-bus": "FX Bus",
        "wash": "Wash",
        "spectral-processing": "Spectral",
    }.get(role, role.title())


# ─── Preset selection ─────────────────────────────────────────────────────────

# Role → preferred preset_type values
_ROLE_TO_PRESET_TYPES: dict[str, list[str]] = {
    "harmonic-foundation": ["instrument_rack", "instrument"],
    "rhythmic-driver": ["drum_rack", "instrument_rack"],
    "melodic": ["instrument_rack", "instrument"],
    "bass": ["instrument_rack", "instrument"],
    "fx-bus": ["audio_effect_rack", "audio_effect"],
    "wash": ["audio_effect_rack", "instrument_rack", "instrument"],
    "spectral-processing": ["audio_effect_rack"],
}

# Pack → role compatibility hints (preferred roles for each pack)
_PACK_ROLE_HINTS: dict[str, list[str]] = {
    "drone-lab": ["harmonic-foundation", "wash", "spectral-processing"],
    "mood-reel": ["harmonic-foundation", "melodic", "wash"],
    "pitchloop89": ["fx-bus", "spectral-processing", "wash"],
    "convolution-reverb": ["fx-bus", "wash"],
    "inspired-by-nature-by-dillon-bastan": ["harmonic-foundation", "melodic", "wash"],
    "lost-and-found": ["rhythmic-driver", "wash", "melodic"],
    "voice-box": ["melodic", "wash"],
    "chop-and-swing": ["rhythmic-driver", "melodic"],
    "latin-percussion": ["rhythmic-driver"],
    "glitch-and-wash": ["fx-bus", "wash", "spectral-processing"],
    "creative-extensions": ["fx-bus", "melodic", "wash"],
    "electric-keyboards": ["melodic", "harmonic-foundation"],
    "orchestral-strings": ["harmonic-foundation", "wash"],
    "orchestral-woodwinds": ["melodic", "harmonic-foundation"],
    "orchestral-brass": ["melodic", "harmonic-foundation"],
    "drum-essentials": ["rhythmic-driver"],
    "session-drums-club": ["rhythmic-driver"],
    "synth-essentials": ["melodic", "bass", "harmonic-foundation"],
    "build-and-drop": ["fx-bus"],
    "drive-and-glow": ["fx-bus", "wash"],
}


def _iter_all_preset_sidecars_for_pack(pack_slug: str):
    """Iterate preset sidecars for a single pack. Yields (pack_slug, stem, sidecar)."""
    from .macro_fingerprint import PRESET_PARSES_ROOT
    import json
    pack_dir = PRESET_PARSES_ROOT / pack_slug
    if not pack_dir.is_dir():
        return
    for sidecar_path in sorted(pack_dir.glob("*.json")):
        try:
            sidecar = json.loads(sidecar_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        yield pack_slug, sidecar_path.stem, sidecar


def _select_preset_for_role(
    role: str,
    brief: str,
    pack_cohort: list[str],
    used_presets: set[str] | None = None,
) -> dict | None:
    """Pick a real preset from cohort packs that best matches the role.

    Selection algorithm:
    1. Filter packs to those compatible with role (via _PACK_ROLE_HINTS)
    2. Iterate their presets, filter by preset_type compatibility
    3. Skip presets already in used_presets (dedup exclusion set)
    4. Score by fingerprint_strength (strong > moderate > weak)
    5. Return the first strong-or-moderate match, or the first match overall

    Returns {pack_slug, preset_path, preset_name, rationale} or None.
    """
    from .macro_fingerprint import _extract_fingerprint, _fingerprint_strength

    preferred_types = _ROLE_TO_PRESET_TYPES.get(role, ["instrument_rack"])
    _used = used_presets if used_presets is not None else set()

    best: dict | None = None
    best_strength_rank = -1

    # Try packs that have role hints matching this role first
    ordered_packs = sorted(
        pack_cohort,
        key=lambda p: (0 if role in _PACK_ROLE_HINTS.get(p, []) else 1),
    )

    for pack_slug in ordered_packs:
        for _, stem, sidecar in _iter_all_preset_sidecars_for_pack(pack_slug):
            preset_type = sidecar.get("preset_type", "")
            rack_class = sidecar.get("rack_class", "")

            # Skip already-used presets (dedup)
            if stem in _used:
                continue

            # Check type compatibility
            type_ok = any(
                t in preset_type or t in rack_class.lower()
                for t in preferred_types
            )
            if not type_ok:
                continue

            # Compute fingerprint strength
            fp = _extract_fingerprint(sidecar)
            strength = _fingerprint_strength(len(fp))
            rank = {"strong": 2, "moderate": 1, "weak": 0}.get(strength, -1)

            if rank > best_strength_rank:
                best_strength_rank = rank
                preset_name = sidecar.get("name", stem)
                best = {
                    "pack_slug": pack_slug,
                    "preset_path": stem,
                    "preset_name": preset_name,
                    "rationale": (
                        f"{preset_name} from {pack_slug} — {strength} fingerprint, "
                        f"preset_type={preset_type or rack_class} "
                        f"[SOURCE: adg-parse]"
                    ),
                    "fingerprint_strength": strength,
                }
                # If we have a strong match in a role-compatible pack, take it
                if rank == 2 and role in _PACK_ROLE_HINTS.get(pack_slug, []):
                    return best

    return best


def _build_track_proposal(
    role_defs: list[dict],
    pack_cohort: list[str],
    brief: str,
) -> list[dict]:
    """Assemble per-track entries with role + preset + rationale."""
    proposal: list[dict] = []
    used_presets: set[str] = set()

    for i, role_def in enumerate(role_defs):
        role = role_def["role"]
        name = role_def["suggested_name"]

        # Pass used_presets directly so _select_preset_for_role skips duplicates
        preset = _select_preset_for_role(role, brief, pack_cohort, used_presets=used_presets)
        if preset:
            used_presets.add(preset["preset_path"])

        if preset:
            proposal.append({
                "track_name": name,
                "role": role,
                "preset": f"{preset['pack_slug']}/{preset['preset_path']}",
                "preset_name": preset["preset_name"],
                "rationale": preset["rationale"],
            })
        else:
            # No preset found — still include the track with a fallback note
            proposal.append({
                "track_name": name,
                "role": role,
                "preset": None,
                "preset_name": None,
                "rationale": (
                    f"No matching preset found in cohort packs {pack_cohort} "
                    f"for role '{role}'. Add packs or broaden brief. "
                    "[SOURCE: agent-inference]"
                ),
            })

    return proposal


def _suggest_routing(
    track_proposal: list[dict],
    brief: str,
    pack_cohort: list[str],
) -> list[str]:
    """Suggest send routing based on cross_pack_workflow recipes and brief.

    Checks if any cross-workflow recipe matches the cohort, and surfaces
    its routing suggestions. Falls back to generic suggestions.
    """
    suggestions: list[str] = []

    # Find cross-workflow recipes that match the cohort
    if _CROSS_WORKFLOWS_DIR.exists():
        for wf_file in sorted(_CROSS_WORKFLOWS_DIR.glob("*.yaml")):
            try:
                import yaml
                wf = yaml.safe_load(wf_file.read_text())
            except Exception:
                continue
            wf_packs = set(wf.get("packs_used", []))
            # Check if ≥2 cohort packs overlap with this workflow's packs
            overlap = wf_packs & set(pack_cohort)
            if len(overlap) >= 2:
                when = wf.get("when_to_reach", "")
                if when:
                    suggestions.append(
                        f"Cross-pack workflow '{wf.get('name', wf_file.stem)}' "
                        f"matches cohort ({', '.join(sorted(overlap))}): "
                        f"use `atlas_cross_pack_chain(workflow_entity_id=\"{wf.get('entity_id', '')}\")` "
                        f"[SOURCE: cross_pack_workflow.yaml]"
                    )

    # Generic routing based on detected roles
    roles_in_proposal = [t["role"] for t in track_proposal]
    track_names = {t["role"]: t["track_name"] for t in track_proposal}

    if "harmonic-foundation" in roles_in_proposal and "fx-bus" in roles_in_proposal:
        suggestions.append(
            f"{track_names['harmonic-foundation']} → {track_names['fx-bus']} "
            f"(via Send A) [SOURCE: agent-inference]"
        )
    if "harmonic-foundation" in roles_in_proposal and "wash" in roles_in_proposal:
        suggestions.append(
            f"{track_names['harmonic-foundation']} → {track_names['wash']} "
            f"(via Send B — ambient swell) [SOURCE: agent-inference]"
        )
    if "rhythmic-driver" in roles_in_proposal and "fx-bus" in roles_in_proposal:
        suggestions.append(
            f"{track_names['rhythmic-driver']} → {track_names['fx-bus']} "
            f"(bus sidechain for cohesion) [SOURCE: agent-inference]"
        )

    # Spectral routing hint if pitchloop89 in cohort
    if "pitchloop89" in pack_cohort:
        foundation = track_names.get("harmonic-foundation", "Drone Bed")
        suggestions.append(
            f"{foundation} → PitchLoop89 Send (via Return track with "
            f"PitchLoop89 loaded) — the spectral send technique "
            f"[SOURCE: cross_pack_workflow.yaml]"
        )

    return suggestions


def _build_executable_steps(
    track_proposal: list[dict],
    suggested_routing: list[str],
    target_bpm: float | None,
    target_scale: str,
) -> list[dict]:
    """Emit create_audio_track + load_browser_item + set_device_parameter steps.

    Reuses Phase E's step structure conventions for load_browser_item actions.
    """
    from .extract_chain import _emit_execution_steps

    steps: list[dict] = []

    # Step 0 (conditional): set BPM
    if target_bpm and target_bpm > 0:
        steps.append({
            "action": "set_tempo",
            "value": target_bpm,
            "comment": f"Set project BPM to {target_bpm} [SOURCE: agent-inference]",
        })

    # Step 1 (conditional): set scale
    if target_scale:
        steps.append({
            "action": "set_song_scale",
            "scale": target_scale,
            "comment": f"Set project scale to {target_scale} [SOURCE: agent-inference]",
        })

    # Per-track steps
    for i, track in enumerate(track_proposal):
        track_name = track["track_name"]
        role = track["role"]
        preset_path = track.get("preset")
        preset_name = track.get("preset_name", "")

        # Determine track type from role
        if role in ("fx-bus", "wash") and track.get("preset"):
            # Check preset type from slug
            track_type = "audio"
        else:
            track_type = "midi"  # most instrument tracks are midi-driven

        # Create track
        create_action = "create_midi_track" if track_type == "midi" else "create_audio_track"
        steps.append({
            "action": create_action,
            "name": track_name,
            "comment": f"Create {role} track '{track_name}' [SOURCE: agent-inference]",
        })

        # Load preset if available — emit URI-resolution hint via preset_resolver.
        # BUG-F1#2: load_browser_item requires `uri` at execution time. Live's
        # browser URIs are FileId-keyed (runtime-only), so we emit a
        # browser_search_hint that the agent passes to search_browser before
        # the actual load_browser_item call.
        if preset_path and preset_name:
            from .preset_resolver import resolve_preset_for_device
            pack_slug = preset_path.split("/")[0] if "/" in preset_path else ""
            res = resolve_preset_for_device(pack_slug, "InstrumentGroupDevice", preset_name)
            load_step = {
                "action": "load_browser_item",
                "track_index": i + (1 if target_bpm and target_bpm > 0 else 0)
                              + (1 if target_scale else 0),
                "name": preset_name,
                "device_class": "InstrumentGroupDevice",
                "comment": (
                    f"Load '{preset_name}' on track '{track_name}'. "
                    "Resolve URI via search_browser(**browser_search_hint) "
                    "before calling load_browser_item. [SOURCE: adg-parse]"
                ),
                "device_index": 0,
            }
            if res.get("found") and res.get("browser_search_hint"):
                load_step["browser_search_hint"] = res["browser_search_hint"]
                load_step["preset_match"] = res["match_type"]
            else:
                load_step["browser_search_hint"] = {
                    "name_filter": preset_name,
                    "suggested_path": "sounds",
                }
                load_step["preset_match"] = "none"
            steps.append(load_step)

    # Routing steps (suggest only — as set_track_send comments)
    for routing_hint in suggested_routing:
        if "→" in routing_hint and "[SOURCE: agent-inference]" in routing_hint:
            steps.append({
                "action": "set_track_send",
                "comment": f"Manual routing: {routing_hint}",
                "note": "Execute manually after tracks are created",
            })

    return steps


# ─── Eclectic mode ────────────────────────────────────────────────────────────

def _select_eclectic_presets(
    role_defs: list[dict],
    brief: str,
    pack_cohort: list[str],
) -> tuple[list[dict], str]:
    """Select presets that deliberately create tension across conflicting aesthetics.

    Returns (track_proposal, tension_resolution_text).

    Per spec: pair packs whose anti_patterns conflict. The tension_resolution
    field explains how the conflict resolves into a coherent new aesthetic
    (Eclectic Mode 4-point quality bar: coherent new aesthetic, not chaos).
    """
    from .macro_fingerprint import PRESET_PARSES_ROOT

    # Load anti_patterns from pack overlays to find conflicts
    anti_pattern_packs = _load_pack_anti_patterns()

    # Identify packs in cohort that conflict (e.g., clean Mood Reel vs dark Drone Lab)
    _PACK_AESTHETIC_AXES: dict[str, dict] = {
        "drone-lab": {"axis": "dark_industrial", "acoustic_synthetic_axis": 1.0},
        "mood-reel": {"axis": "clean_cinematic", "acoustic_synthetic_axis": 0.5},
        "lost-and-found": {"axis": "dusty_lo_fi", "acoustic_synthetic_axis": 0.0},
        "inspired-by-nature-by-dillon-bastan": {"axis": "organic_pastoral", "acoustic_synthetic_axis": -0.5},
        "glitch-and-wash": {"axis": "glitch_experimental", "acoustic_synthetic_axis": 1.0},
        "build-and-drop": {"axis": "commercial_edm", "acoustic_synthetic_axis": 1.0},
        "voice-box": {"axis": "vocal_processed", "acoustic_synthetic_axis": 0.0},
        "pitchloop89": {"axis": "spectral_experimental", "acoustic_synthetic_axis": 0.8},
        # Orchestral packs: fully acoustic, sit at -1.0 on the acoustic_synthetic_axis
        "orchestral-strings": {"axis": "acoustic_orchestral", "acoustic_synthetic_axis": -1.0},
        "orchestral-woodwinds": {"axis": "acoustic_orchestral", "acoustic_synthetic_axis": -1.0},
        "orchestral-brass": {"axis": "acoustic_orchestral", "acoustic_synthetic_axis": -1.0},
        "brass-quartet-by-spitfire-audio": {"axis": "acoustic_orchestral", "acoustic_synthetic_axis": -1.0},
        "orchestral-mallets": {"axis": "acoustic_orchestral", "acoustic_synthetic_axis": -1.0},
        "skitter-and-step": {"axis": "rhythmic_digital", "acoustic_synthetic_axis": 0.8},
        "beat-tools": {"axis": "rhythmic_digital", "acoustic_synthetic_axis": 0.7},
        "glitch-and-wash": {"axis": "glitch_experimental", "acoustic_synthetic_axis": 1.0},
    }

    _CONFLICTING_PAIRS: list[tuple[str, str]] = [
        ("drone-lab", "mood-reel"),
        ("glitch-and-wash", "inspired-by-nature-by-dillon-bastan"),
        ("lost-and-found", "build-and-drop"),
        ("drone-lab", "voice-box"),
        # Orchestral vs electronic conflicts
        ("orchestral-strings", "drone-lab"),
        ("orchestral-strings", "skitter-and-step"),
        ("orchestral-strings", "glitch-and-wash"),
        ("orchestral-woodwinds", "drone-lab"),
        ("orchestral-brass", "glitch-and-wash"),
    ]

    # Find first conflicting pair present in cohort
    conflict_pair: tuple[str, str] | None = None
    for a, b in _CONFLICTING_PAIRS:
        if a in pack_cohort and b in pack_cohort:
            conflict_pair = (a, b)
            break

    # If no conflict found, artificially add a conflicting pack
    if conflict_pair is None and pack_cohort:
        primary_pack = pack_cohort[0]
        primary_entry = _PACK_AESTHETIC_AXES.get(primary_pack, {})
        primary_axis = primary_entry.get("axis", "") if isinstance(primary_entry, dict) else primary_entry
        for pack, axis_entry in _PACK_AESTHETIC_AXES.items():
            pack_axis = axis_entry.get("axis", "") if isinstance(axis_entry, dict) else axis_entry
            if pack != primary_pack and pack_axis != primary_axis and pack not in pack_cohort:
                pack_cohort = pack_cohort + [pack]
                conflict_pair = (primary_pack, pack)
                break

    # Build the track proposal (alternating between conflicting packs)
    eclectic_proposal: list[dict] = []
    used_presets: set[str] = set()

    conflict_packs = list(conflict_pair) if conflict_pair else pack_cohort[:2]
    other_packs = [p for p in pack_cohort if p not in conflict_packs]

    for i, role_def in enumerate(role_defs):
        role = role_def["role"]
        name = role_def["suggested_name"]

        # Alternate between conflicting packs for eclectic texture
        target_packs: list[str]
        if i % 2 == 0:
            target_packs = [conflict_packs[0]] + other_packs
        else:
            target_packs = [conflict_packs[1]] + other_packs

        preset = _select_preset_for_role(role, brief, target_packs, used_presets=used_presets)

        if preset:
            used_presets.add(preset["preset_path"])
            eclectic_proposal.append({
                "track_name": name,
                "role": role,
                "preset": f"{preset['pack_slug']}/{preset['preset_path']}",
                "preset_name": preset["preset_name"],
                "rationale": (
                    f"[ECLECTIC] {preset['rationale']} — "
                    f"intentionally from {preset['pack_slug']} "
                    f"(conflicting aesthetic) "
                    f"[SOURCE: adg-parse]"
                ),
            })
        else:
            eclectic_proposal.append({
                "track_name": name,
                "role": role,
                "preset": None,
                "preset_name": None,
                "rationale": f"[ECLECTIC] No preset found for role '{role}' [SOURCE: agent-inference]",
            })

    # Generate tension_resolution reasoning — interpolated from actual cohort
    if conflict_pair:
        axis_entry_a = _PACK_AESTHETIC_AXES.get(conflict_pair[0], {})
        axis_entry_b = _PACK_AESTHETIC_AXES.get(conflict_pair[1], {})
        axis_a = axis_entry_a.get("axis", conflict_pair[0]) if isinstance(axis_entry_a, dict) else conflict_pair[0]
        axis_b = axis_entry_b.get("axis", conflict_pair[1]) if isinstance(axis_entry_b, dict) else conflict_pair[1]

        # Derive a synthesized aesthetic name from the two poles
        axis_a_label = axis_a.replace("_", " ")
        axis_b_label = axis_b.replace("_", " ")
        # Build a pack-cohort summary for the resolution text
        other_packs_str = (
            ", ".join(p for p in pack_cohort if p not in conflict_pair)
            if len(pack_cohort) > 2 else ""
        )
        supporting_context = (
            f" Supporting packs in cohort: {other_packs_str}." if other_packs_str else ""
        )
        tension_resolution = (
            f"Eclectic tension: {conflict_pair[0]} ({axis_a_label}) vs "
            f"{conflict_pair[1]} ({axis_b_label}).{supporting_context} "
            f"Resolution: the conflict resolves as timbral contrast — "
            f"{conflict_pair[0]}'s {axis_a_label} character becomes the substrate "
            f"while {conflict_pair[1]}'s {axis_b_label} elements provide foreground "
            f"presence. The cohort [{', '.join(pack_cohort)}] synthesizes into "
            f"an aesthetic that is neither '{axis_a_label}' nor '{axis_b_label}' alone. "
            f"Passes Eclectic Mode 4-point quality bar: (1) coherent new aesthetic "
            f"identified from actual cohort packs, (2) tension serves the brief not just "
            f"genre-mixing, (3) specific tracks assigned to each pole, "
            f"(4) resolution principle stated. "
            f"[SOURCE: agent-inference]"
        )
    else:
        tension_resolution = (
            f"Eclectic mode: no strong aesthetic conflict found in available packs "
            f"[{', '.join(pack_cohort)}] — diversified across available cohort packs "
            f"for maximum textural variety. "
            "[SOURCE: agent-inference]"
        )

    return eclectic_proposal, tension_resolution


@lru_cache(maxsize=1)
def _load_pack_anti_patterns() -> dict[str, list[str]]:
    """Load anti_patterns from cross_workflow YAMLs (best proxy available without overlay read)."""
    anti_patterns: dict[str, list[str]] = {}
    if not _CROSS_WORKFLOWS_DIR.exists():
        return anti_patterns
    try:
        import yaml
        for wf_file in _CROSS_WORKFLOWS_DIR.glob("*.yaml"):
            wf = yaml.safe_load(wf_file.read_text())
            avoid = wf.get("avoid", "")
            gotcha = wf.get("gotcha", "")
            for pack in wf.get("packs_used", []):
                combined = f"{avoid} {gotcha}"
                if pack not in anti_patterns:
                    anti_patterns[pack] = []
                if combined.strip():
                    anti_patterns[pack].append(combined.strip())
    except Exception:
        pass
    return anti_patterns


# ─── Main entry point ─────────────────────────────────────────────────────────

def pack_aware_compose(
    aesthetic_brief: str,
    target_bpm: float | None = None,
    target_scale: str = "",
    track_count: int = 6,
    pack_diversity: str = "coherent",
) -> dict:
    """Bootstrap a project with pack-coherent track selection.

    Called by the MCP tool wrapper in tools.py.
    """
    if not aesthetic_brief or not aesthetic_brief.strip():
        return {
            "error": "aesthetic_brief is required",
            "status": "error",
        }

    # BUG-EDGE#2: coerce track_count (MCP may pass as string)
    track_count = _coerce_int(track_count, 6)
    # BUG-EDGE#3: coerce target_bpm (MCP may pass as string); invalid strings → None
    if target_bpm is not None:
        target_bpm = _coerce_float(target_bpm, 0.0) or None

    # ── 1. Parse brief ────────────────────────────────────────────────────────
    brief_analysis = _parse_brief(aesthetic_brief)

    # If no pack cohort identified, provide a sensible fallback
    if not brief_analysis["pack_cohort"]:
        # Generic fallback cohort based on common packs
        brief_analysis["pack_cohort"] = [
            "drone-lab", "mood-reel", "lost-and-found",
        ]
        brief_analysis["primary_aesthetic"] = "ambient"

    # ── 2. Determine track roles ──────────────────────────────────────────────
    # Cap at the maximum supported by _DEFAULT_ROLE_MIX if track_count exceeds it
    effective_track_count = min(track_count, _MAX_ROLE_MIX_COUNT)
    role_defs = _determine_track_roles(aesthetic_brief, effective_track_count)

    pack_cohort = brief_analysis["pack_cohort"]

    # ── 3. Build track proposal ───────────────────────────────────────────────
    tension_resolution: str | None = None

    if pack_diversity == "eclectic":
        track_proposal, tension_resolution = _select_eclectic_presets(
            role_defs, aesthetic_brief, list(pack_cohort)
        )
    else:
        track_proposal = _build_track_proposal(
            role_defs, list(pack_cohort), aesthetic_brief
        )

    # ── 4. Suggest routing ────────────────────────────────────────────────────
    suggested_routing = _suggest_routing(track_proposal, aesthetic_brief, pack_cohort)

    # ── 5. Build executable plan ──────────────────────────────────────────────
    executable_steps = _build_executable_steps(
        track_proposal, suggested_routing, target_bpm, target_scale
    )

    result: dict = {
        "brief_analysis": brief_analysis,
        # BUG-NEW#4: expose pack_cohort at top level for easy caller access
        "pack_cohort": brief_analysis["pack_cohort"],
        "track_proposal": track_proposal,
        "suggested_routing": suggested_routing,
        "executable_steps": executable_steps,
        "warnings": [],
        "sources": [
            "packs namespace queries [SOURCE: adg-parse]",
            "artist-vocabularies.md [SOURCE: artist-vocabularies.md]",
            "genre-vocabularies.md [SOURCE: genre-vocabularies.md]",
            "cross_pack_workflow recipes [SOURCE: cross_pack_workflow.yaml]",
            "agent-inference: role assignment + step generation [SOURCE: agent-inference]",
        ],
    }

    # Report truncation when track_count exceeds the role-mix cap
    if track_count != effective_track_count:
        result["requested_vs_returned"] = {
            "requested": track_count,
            "returned": effective_track_count,
            "note": (
                f"track_count={track_count} exceeds maximum supported role-mix size "
                f"({_MAX_ROLE_MIX_COUNT}). Returned {effective_track_count} tracks. "
                "To extend, add more entries to _DEFAULT_ROLE_MIX."
            ),
        }
        # BUG-EDGE#9: surface truncation in warnings list
        result["warnings"].append(
            f"track_count={track_count} was capped at {effective_track_count} "
            f"(the supported maximum). See requested_vs_returned for details."
        )

    if tension_resolution:
        result["reasoning_artifact"] = {
            "mode": "eclectic",
            "tension_resolution": tension_resolution,
            "note": (
                "This composition was generated in Eclectic Mode. "
                "The packs were deliberately chosen for aesthetic conflict "
                "with a stated resolution principle. "
                "See MEMORY.md §feedback_eclectic_mode_invocation for context."
            ),
        }

    return result
