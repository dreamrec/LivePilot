"""LLM-creative fast mode helpers.

Architecture (2026-05-01 redesign per user feedback):
  Phase 1 — `compose(mode="fast")` returns a CREATIVE BRIEF: parsed intent,
            atlas-filtered instrument suggestions per role, key/tempo
            context, scale pitches, genre creative guidance, fresh-project
            cleanup state. This phase does NOT generate content.
  Phase 2 — The agent (LLM) reads the brief, picks instruments from
            atlas-filtered suggestions, designs MIDI note patterns inline,
            and submits a complete plan to `compose_fast_apply(plan)`.
  Phase 3 — `compose_fast_apply` bulk-executes server-side: creates tracks,
            loads instruments, populates clips with the LLM's notes, fires
            scene. Same speed as the old template-based execute, but the
            CONTENT is fresh per call.

Why this is faster than the old plan-walking compose AND more creative
than the old template-based fast mode:
  - One LLM round-trip between brief and apply (vs ~16 round-trips
    walking individual tool calls in plan-mode)
  - LLM creativity per call (vs ~hundred bounded combinations in
    template-mode)

What this module contains:
  - Atlas viability filters (§1 ban, drum-keyword check, sample-less skip)
  - Atlas tag-based instrument picker
  - Fresh-project detection + cleanup helpers
  - Key parser, scale-degree math (LLM's optional-use building blocks)
  - Genre creative guidance (text hints, not templates)
  - Brief builder

What this module deliberately does NOT contain (deleted 2026-05-01):
  - Pattern generators (four_floor, bass_walk, progression_*, etc.)
  - FAST_LAYER_TEMPLATES with fixed layer specs
  - select_template / generate_notes_for_layer / _PATTERN_REGISTRY

Patterns now live in the LLM's creative output per call, not in this file.
"""

from __future__ import annotations

import logging
import random
import re
from typing import Any, Optional

from ..prompt_parser import CompositionIntent
from .tier_classification import (
    classify_instrument,
    is_drum_specific_synth,
    CONTAINERS_NEEDING_PRESETS,
    MELODIC_AUDIBLE_DEFAULTS,
    DRUM_ROLES,
    TIER_A_CURATED_PRESET,
    TIER_A_DRUM_SAMPLE,
    TIER_B_DRUM_SYNTH,
    TIER_B_AUDIBLE_DEFAULT_VALUE,
    # Backward-compat alias — used by Tier-C guard in get_role_candidates
    TIER_C_NEEDS_PRESET,
    ROLE_SEARCH_TERMS,
)

logger = logging.getLogger(__name__)


# ── Atlas instrument viability filters ───────────────────────────────

_INSTRUMENT_URI_PREFIXES: tuple[str, ...] = (
    "query:Synths#",
    "query:Drums#",
    "query:Instruments#",
    "query:Sounds",
    "query:UserLibrary#",
)

# Bare empty devices that load silent until further configuration.
# Granular synths and bare racks that load silent until further config.
# Adding to this set means: the picker won't return them, and the agent
# never gets URIs that would produce silence.
_SILENT_WITHOUT_CONFIG: frozenset[str] = frozenset({
    "Granulator III",
    "Vector Grain",  # BUG-M (2026-05-01 live test): same class as Granulator III
    "Looper",
    "External Instrument",
    "External Audio Effect",
    "Sampler",
    "Drum Rack",
    "DrumGroup",
    "Instrument Rack",
})

# §1 ban — Analog/Poli/Drift/Meld are forbidden as defaults per CLAUDE.md.
# The LLM picking creatively from atlas suggestions still won't see these
# as candidates because the brief filters them out.
_BANNED_DEFAULT_DEVICES: frozenset[str] = frozenset({
    "Analog", "Poli", "Drift", "Meld",
})

# Drum-role keyword check. Pattern-fired MIDI notes at drum-rack convention
# pitches (36/38/42) need actual drum sources. A tonal synth there produces
# wrong-pitched output. The LLM is expected to fire MIDI 36/38/42 for
# drum layers (standard convention), so the same correctness check applies.
_DRUM_ROLE_URI_KEYWORDS: dict[str, tuple[str, ...]] = {
    "kick":  ("Drums", "Drum", "Kick", "808", "Bd"),
    "snare": ("Drums", "Drum", "Snare", "Clap", "Rim"),
    "hat":   ("Drums", "Drum", "Hat", "Cymbal", "Hh"),
    "perc":  ("Drums", "Drum", "Perc", "Tom", "Shaker", "Cowbell"),
    "clap":  ("Drums", "Drum", "Clap", "Snare"),
}


def is_viable_instrument_uri(
    uri: str,
    device_name: str = "",
    role: str = "",
) -> bool:
    """True when this URI loads an audible, role-appropriate sound source."""
    if not uri:
        return False
    if not any(uri.startswith(p) for p in _INSTRUMENT_URI_PREFIXES):
        return False
    if device_name in _SILENT_WITHOUT_CONFIG:
        return False
    if device_name in _BANNED_DEFAULT_DEVICES:
        return False
    if role in _DRUM_ROLE_URI_KEYWORDS:
        keywords = _DRUM_ROLE_URI_KEYWORDS[role]
        haystack = (uri + " " + device_name).lower()
        if not any(k.lower() in haystack for k in keywords):
            return False
    return True


# ── Atlas tag-based instrument picker (returns top-N for the brief) ──

_ROLE_TAGS: dict[str, tuple[str, ...]] = {
    "kick":  ("kick", "drum", "808"),
    "snare": ("snare", "clap", "drum"),
    "hat":   ("hihat", "hi-hat", "hat", "cymbal"),
    "perc":  ("perc", "percussion", "drum"),
    "clap":  ("clap", "snare"),
    "bass":  ("bass", "sub_bass", "sub"),
    "pad":   ("pad", "texture", "atmos", "ambient"),
    "lead":  ("lead", "synth_lead", "pluck"),
    "atmos": ("atmos", "ambient", "drone", "texture"),
    "vox":   ("vocal", "vox", "voice"),
}


def pick_instrument_uri(suggestions: list[dict], role: str = "") -> tuple[str, str]:
    """Walk atlas suggestions and return the first viable (uri, device_name)."""
    for s in suggestions or []:
        uri = s.get("uri") or ""
        name = s.get("device_name") or ""
        if is_viable_instrument_uri(uri, name, role):
            return uri, name
    return "", ""


# Per-role sonic-description queries used by the atlas_search fallback
# when _by_tag returns no candidates (BUG-K caught 2026-05-01: many user
# atlases don't tag canonical "kick"/"hat"/"bass"/"pad" — but atlas_search
# with sonic queries finds the same devices via character_tags / use_cases).
_ROLE_SONIC_QUERIES: dict[str, str] = {
    "kick":  "punchy techno kick drum sub bass anchor",
    "snare": "snare clap drum",
    "hat":   "crisp closed hihat hi-hat metal",
    "perc":  "percussion shaker tom cowbell",
    "clap":  "clap snare drum",
    "bass":  "warm techno bass sub low end",
    "pad":   "evolving pad atmospheric texture warm",
    "lead":  "lead synth pluck arp",
    "atmos": "drone atmosphere texture ambient",
    "vox":   "vocal voice",
}


def get_role_candidates(
    atlas: Any,
    role: str,
    genre: str = "",
    top_n: int = 5,
    exclude_names: Optional[set[str]] = None,
    *,
    ableton: Any = None,
    excluded_uris: Optional[set[str]] = None,
) -> list[dict]:
    """Return up to top_n viable instrument candidates for a role.

    v1.24 hunt order (Phase 4 Task 18a-followup — §1 fix):
      Step 1:  sounds/ — curated .adg/.adv presets (Tier-A, always preferred)
      Step 1b: drums/  — raw samples for drum roles (Tier-A)
      Step 2:  atlas   — Tier-B fallback:
                 - drum-specific synths (DS Kick etc.) → allowed bare for drum roles
                 - melodic synths (Operator/Wavetable etc.) → ONLY if Step 1 returned
                   nothing for a melodic role (§1 hard rule)
                 - Tier-C containers → NEVER

    Args:
      atlas:          atlas object for tag/search fallback
      role:           "kick", "bass", "pad", etc.
      genre:          genre hint for sorting
      top_n:          max candidates to return
      exclude_names:  set of device names to filter (anti-repeat by name)
      ableton:        optional ableton client; if provided, Steps 1/1b fire
      excluded_uris:  set of recently-used preset URIs to filter (anti-repeat by URI)

    Each candidate dict has: uri, name, tier, tags, pack, genre_affinity, source.
    """
    if atlas is None and ableton is None:
        return []
    exclude_names = exclude_names or set()
    excluded_uris = excluded_uris or set()

    role_lower = role.lower()
    is_drum = role_lower in DRUM_ROLES
    candidates: list[dict] = []

    # ── Step 1: sounds/ — curated presets (always Tier-A) ────────────────
    if ableton is not None:
        sounds_term = ROLE_SEARCH_TERMS.get(role_lower, {}).get("sounds_term", role_lower)
        try:
            sounds_results = ableton.send_command("search_browser", {
                "path": "sounds", "name_filter": sounds_term,
                "max_depth": 4, "max_results": 8, "loadable_only": True,
            })
            for item in (sounds_results or {}).get("items", []):
                uri = item.get("uri", "")
                name = item.get("name", "")
                if not name or not uri:
                    continue
                if name in exclude_names or uri in excluded_uris:
                    continue
                name_lower = name.lower()
                if item.get("is_loadable") and (
                    name_lower.endswith(".adg") or name_lower.endswith(".adv")
                ):
                    candidates.append({
                        "uri": uri, "name": name,
                        "tier": TIER_A_CURATED_PRESET, "source": "sounds/",
                        "tags": [], "pack": "", "genre_affinity": {},
                    })
        except Exception as exc:
            logger.debug("get_role_candidates sounds/ search failed for role=%s: %s", role, exc)

        # ── Step 1b: drums/ — raw samples for drum roles (Tier-A) ────────
        if is_drum:
            drums_term = ROLE_SEARCH_TERMS.get(role_lower, {}).get("drums_term")
            if drums_term:
                try:
                    drums_results = ableton.send_command("search_browser", {
                        "path": "drums", "name_filter": drums_term,
                        "max_depth": 6, "max_results": 8, "loadable_only": True,
                    })
                    for item in (drums_results or {}).get("items", []):
                        uri = item.get("uri", "")
                        name = item.get("name", "")
                        if not name or not uri:
                            continue
                        if name in exclude_names or uri in excluded_uris:
                            continue
                        name_lower = name.lower()
                        if item.get("is_loadable") and name_lower.endswith(
                            (".aif", ".wav", ".adg", ".adv")
                        ):
                            candidates.append({
                                "uri": uri, "name": name,
                                "tier": TIER_A_DRUM_SAMPLE, "source": "drums/",
                                "tags": [], "pack": "", "genre_affinity": {},
                            })
                except Exception as exc:
                    logger.debug("get_role_candidates drums/ search failed for role=%s: %s", role, exc)

    # has_tier_a: whether Steps 1/1b returned any curated candidates
    has_tier_a = len(candidates) > 0

    # ── Step 2: atlas — Tier-B fallback ──────────────────────────────────
    # Collect atlas candidates (tag-based, then sonic query)
    if atlas is not None:
        atlas_candidates: list[dict] = []
        seen_uris: set[str] = set()

        # Stage 2a: tag-based lookup
        by_tag = getattr(atlas, "_by_tag", None)
        if by_tag is not None:
            tags = _ROLE_TAGS.get(role_lower, (role_lower,))
            for tag in tags:
                for dev in by_tag.get(tag.lower(), []):
                    uri = dev.get("uri") or ""
                    if uri and uri not in seen_uris:
                        seen_uris.add(uri)
                        dev_copy = dict(dev)
                        dev_copy["__source"] = "tag"
                        atlas_candidates.append(dev_copy)

        # Stage 2b: sonic-description query fallback
        if len(atlas_candidates) < top_n and hasattr(atlas, "search"):
            sonic_query = _ROLE_SONIC_QUERIES.get(role_lower, role_lower)
            try:
                search_results = atlas.search(sonic_query, category="instruments", limit=top_n * 2)
            except Exception:
                search_results = []
            for r in search_results or []:
                dev_data = r.get("device") if isinstance(r, dict) and "device" in r else r
                if not isinstance(dev_data, dict):
                    continue
                uri = dev_data.get("uri") or ""
                if uri and uri not in seen_uris:
                    seen_uris.add(uri)
                    dev_copy = dict(dev_data)
                    dev_copy["__source"] = "search"
                    atlas_candidates.append(dev_copy)

        # Filter + classify atlas candidates
        for dev in atlas_candidates:
            uri = dev.get("uri") or ""
            instrument_name = dev.get("name") or ""

            if instrument_name in exclude_names or uri in excluded_uris:
                continue

            # Tier-C container: NEVER include
            if instrument_name in CONTAINERS_NEEDING_PRESETS:
                continue

            # Viability gate (§1 ban on Analog/Poli/Drift/Meld + drum keyword)
            if not is_viable_instrument_uri(uri, instrument_name, role_lower):
                continue

            # Drum-specific synths: always allowed for drum roles (their default IS the drum)
            if is_drum_specific_synth(instrument_name):
                if is_drum:
                    candidates.append({
                        "uri": uri, "name": instrument_name,
                        "tier": TIER_B_DRUM_SYNTH, "source": "atlas/",
                        "tags": dev.get("character_tags") or dev.get("tags") or [],
                        "pack": dev.get("pack") or "",
                        "genre_affinity": dev.get("genre_affinity") or dev.get("genres") or {},
                    })
                # For melodic roles, drum-specific synths don't make sense — skip
                continue

            # Known generic melodic synths (Operator, Wavetable, etc.):
            # §1 hard rule — ONLY include as fallback when Tier-A is empty for this role.
            # These are the "generic AI synth" defaults the user has rejected repeatedly.
            if instrument_name in MELODIC_AUDIBLE_DEFAULTS:
                if not has_tier_a:
                    candidates.append({
                        "uri": uri, "name": instrument_name,
                        "tier": TIER_B_AUDIBLE_DEFAULT_VALUE,
                        "source": dev.get("__source", "atlas/"),
                        "tags": dev.get("character_tags") or dev.get("tags") or [],
                        "pack": dev.get("pack") or "",
                        "genre_affinity": dev.get("genre_affinity") or dev.get("genres") or {},
                        "fallback_warning": (
                            "no curated preset found in sounds/ for this role; "
                            "bare-synth default may sound generic"
                        ),
                    })
                # If has_tier_a, SKIP this Tier-B melodic synth entirely (§1 fix)
                continue

            # Unknown classification — custom atlas device (named preset, curated device).
            # These are NOT generic defaults — they have specific character via atlas.
            # Include as Tier-B; viability gate already ran above.
            candidates.append({
                "uri": uri, "name": instrument_name,
                "tier": TIER_B_AUDIBLE_DEFAULT_VALUE, "source": dev.get("__source", "atlas/"),
                "tags": dev.get("character_tags") or dev.get("tags") or [],
                "pack": dev.get("pack") or "",
                "genre_affinity": dev.get("genre_affinity") or dev.get("genres") or {},
            })

    # ── Sort: Tier-A first, then Tier-B; within same tier, genre affinity ──
    _TIER_ORDER = {
        TIER_A_CURATED_PRESET: 0,
        TIER_A_DRUM_SAMPLE: 1,
        TIER_B_DRUM_SYNTH: 2,
        TIER_B_AUDIBLE_DEFAULT_VALUE: 3,
        # Legacy alias — sort same as B_audible_default
        "B_audible_default": 3,
    }
    gl = (genre or "").lower()

    def _genre_score(c: dict) -> int:
        if not gl:
            return 0
        aff = c.get("genre_affinity") or {}
        if isinstance(aff, dict):
            primary = [str(g).lower() for g in (aff.get("primary") or [])]
            secondary = [str(g).lower() for g in (aff.get("secondary") or [])]
            if gl in primary:
                return 2
            if gl in secondary:
                return 1
        return 0

    candidates.sort(
        key=lambda c: (_TIER_ORDER.get(c.get("tier", ""), 99), -_genre_score(c))
    )

    return candidates[:top_n]


# Legacy name — kept for callers that still want a single pick (e.g. unit
# tests checking the deterministic path with top_n=1).
def pick_by_role_tag(
    atlas: Any,
    role: str,
    genre: str = "",
    top_n: int = 5,
    rng: Optional[random.Random] = None,
) -> tuple[str, str]:
    """Single pick from atlas tag-based candidates with weighted random."""
    candidates = get_role_candidates(atlas, role, genre=genre, top_n=top_n)
    if not candidates:
        return "", ""
    if len(candidates) == 1 or top_n == 1:
        return candidates[0]["uri"], candidates[0]["name"]
    rng = rng or random.Random()
    weights = list(range(len(candidates), 0, -1))
    pick = rng.choices(candidates, weights=weights, k=1)[0]
    return pick["uri"], pick["name"]


# ── Role → simpler-role mapping for load_browser_item ────────────────


def simpler_role_for(role: str) -> str | None:
    if role in ("kick", "snare", "hat", "perc", "clap"):
        return "drum"
    if role in ("bass", "lead", "pad", "atmos"):
        return "melodic"
    return None


# ── Fresh-project detection ──────────────────────────────────────────

_DEFAULT_TRACK_NAME_RE = re.compile(
    r"^\s*\d*[-\s]*(?:midi|audio)\s*\d*\s*$",
    re.IGNORECASE,
)


def is_default_track_name(name: str) -> bool:
    if not name:
        return False
    return bool(_DEFAULT_TRACK_NAME_RE.match(name))


def detect_fresh_project(session_info: dict) -> bool:
    tracks = session_info.get("tracks", []) or []
    if not tracks or len(tracks) > 4:
        return False
    return all(is_default_track_name(t.get("name", "") or "") for t in tracks)


def track_is_empty(track_info: dict) -> bool:
    if not track_info:
        return True
    has_clips = any(s.get("has_clip") for s in (track_info.get("clip_slots") or []))
    has_devices = bool(track_info.get("devices"))
    return not has_clips and not has_devices


# ── Key parser + scale-degree math (helper math the LLM may reference) ─

_NOTE_TO_OFFSET = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
    "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}

_SCALE_INTERVALS_MINOR = [0, 2, 3, 5, 7, 8, 10]   # Aeolian
_SCALE_INTERVALS_MAJOR = [0, 2, 4, 5, 7, 9, 11]   # Ionian


def parse_key(key_str: str) -> tuple[int, str]:
    """Parse "Cm" / "Am" / "F#m" / "C" / "G" → (root_offset_0_to_11, mode_str)."""
    if not key_str:
        return 0, "minor"
    s = key_str.strip()
    mode = "minor" if s.endswith("m") else "major"
    note_part = s.rstrip("m")
    if note_part not in _NOTE_TO_OFFSET:
        return 0, "minor"
    return _NOTE_TO_OFFSET[note_part], mode


def degree_to_pitch(degree: int, key_root: int, octave: int, mode: str) -> int:
    scale = _SCALE_INTERVALS_MINOR if mode == "minor" else _SCALE_INTERVALS_MAJOR
    octaves_up = (degree - 1) // 7
    in_octave = (degree - 1) % 7
    return 12 * (octave + octaves_up) + key_root + scale[in_octave]


def chord_at_degree(degree: int, key_root: int, octave: int, mode: str) -> list[int]:
    return [
        degree_to_pitch(degree, key_root, octave, mode),
        degree_to_pitch(degree + 2, key_root, octave, mode),
        degree_to_pitch(degree + 4, key_root, octave, mode),
    ]


def scale_pitches_in_octave(key_root: int, octave: int, mode: str) -> list[int]:
    """Return the 7 scale pitches for the LLM's reference (octave starts on tonic)."""
    return [degree_to_pitch(d, key_root, octave, mode) for d in range(1, 8)]


# ── Genre creative guidance (Phase A — structured palettes, NOT templates) ─
#
# Each genre entry includes:
#   - rhythmic_feel (text): high-level groove description
#   - harmonic_palette (structured): suggested chord progressions with
#     scale degrees + color-tone hints (modal mixture, secondary dom, etc.)
#   - rhythmic_palette (structured): named gestures the agent can pick from
#     (4-on-floor, 2-step, polyrhythm 3-against-4, etc.) WITH swing %
#   - articulation_targets (structured): velocity stddev, ghost-note range,
#     duration variation count, swing % — the agent should hit these
#   - effect_chain_hints (structured): genre-typical effect chains per role
#   - knowledge_search_queries (list): suggested queries for the agent to
#     run against the Ableton Knowledge MCP for producer-voice inspiration

GENRE_CREATIVE_GUIDANCE: dict[str, dict] = {
    "techno": {
        "rhythmic_feel": "Driving 4-on-floor on the kick OR syncopated minimal kick. Hats on offbeats are signature; vary 8th/16th density per layer.",
        "harmonic_palette": {
            "summary": "Natural minor, modal — i-VI-VII or static i drones common. Avoid functional V-i.",
            "progressions": [
                {"name": "modal i-VI-VII", "degrees": [1, 6, 7], "feel": "ascending, hopeful within minor"},
                {"name": "static i drone", "degrees": [1, 1, 1, 1], "feel": "hypnotic, single-chord vamp"},
                {"name": "dorian i-IV", "degrees": [1, 4], "feel": "modal mixture, slight tension"},
                {"name": "i-bVI-bIII", "degrees": [1, 6, 3], "feel": "chromatic mediant moves, dark"},
                {"name": "i-VII alternation", "degrees": [1, 7], "feel": "2-bar cycle, Basic Channel adjacent"},
            ],
            "color_tones": ["b9 over the i for tension", "11 over the iv for openness"],
        },
        "rhythmic_palette": [
            {"name": "4_on_floor", "kick_pattern": "every quarter", "swing_pct": 50},
            {"name": "syncopated_minimal", "kick_pattern": "1, 3, and-of-3 only", "swing_pct": 50},
            {"name": "polyrhythm_3_4", "kick_pattern": "3-against-4 hat against quarter kick", "swing_pct": 55},
            {"name": "swung_offbeats", "kick_pattern": "4OTF + offbeat hats with swing", "swing_pct": 58},
        ],
        "articulation_targets": {
            "velocity_stddev_min": 8,
            "ghost_note_velocity_range": [25, 45],
            "duration_variation_count_min": 3,
            "swing_pct": 50,
            "humanization_timing_ms": 5,
        },
        "effect_chain_hints": {
            "kick": [
                {"device": "Saturator", "params": {"Drive": 0.4}},
                {"device": "Compressor", "params": {"Threshold": 0.75, "Ratio": 0.75}},
            ],
            "bass": [
                {"device": "Saturator", "params": {"Drive": 0.5}},
                {"device": "Compressor", "params": {"Threshold": 0.7, "Ratio": 0.75}},
            ],
            "hat": [
                {"device": "EQ Eight", "params": {}},
            ],
            "pad": [
                {"device": "Auto Filter", "params": {}},
                {"device": "Reverb", "params": {}},
            ],
        },
        "send_hints": {
            "hat": [{"return_name": "A-Reverb", "value": 0.15}],
            "pad": [{"return_name": "A-Reverb", "value": 0.4}, {"return_name": "B-Delay", "value": 0.2}],
        },
        "knowledge_search_queries": [
            "minimal techno production technique",
            "techno bass design saturation",
            "techno hi-hat swing",
        ],
        "spacing_advice": "Carve room for the kick — keep bass fundamental above 100Hz or use a sub layer. Pad usually long-released, sits behind.",
        "production_hints": "Long pads, sidechain pumping under the kick, careful EQ around 200Hz mud.",
    },
    "dub techno": {
        "rhythmic_feel": "Minimal kick (bar-1 or 4OTF). Off-beat chord stabs (and-of-2, and-of-4). Sparse percussion. Silence is the content.",
        "harmonic_palette": {
            "summary": "i-VII repeating cycle (Basic Channel signature). Held drone chords. Two-bar changes. Single-pitch ostinati.",
            "progressions": [
                {"name": "i-VII cycle", "degrees": [1, 7], "feel": "the canonical Basic Channel move, 2 bars per chord"},
                {"name": "i-iv modal", "degrees": [1, 4], "feel": "dorian flavor, breathing"},
                {"name": "single i drone", "degrees": [1, 1, 1, 1], "feel": "absolute stasis, all atmosphere"},
                {"name": "i-bVI", "degrees": [1, 6], "feel": "chromatic mediant, slow descent"},
            ],
            "color_tones": ["maj7 over the i for openness", "9 added to chord stabs"],
        },
        "rhythmic_palette": [
            {"name": "minimal_kick_bar_1", "kick_pattern": "kick on bar-1 only, every other bar", "swing_pct": 50},
            {"name": "4_on_floor_minimal", "kick_pattern": "4OTF, but quiet (vel 60-80)", "swing_pct": 50},
            {"name": "kick_off", "kick_pattern": "no kick, just texture and chord", "swing_pct": 50},
        ],
        "articulation_targets": {
            "velocity_stddev_min": 6,
            "ghost_note_velocity_range": [20, 35],
            "duration_variation_count_min": 2,
            "swing_pct": 52,
            "humanization_timing_ms": 8,
        },
        "effect_chain_hints": {
            "kick": [
                {"device": "Compressor", "params": {"Threshold": 0.8, "Ratio": 0.5}},
                {"device": "EQ Eight", "params": {}},
            ],
            "pad": [
                {"device": "Auto Filter", "params": {}},
                {"device": "Echo", "params": {}},
            ],
            "perc": [
                {"device": "Echo", "params": {}},
            ],
            "atmos": [
                {"device": "Auto Filter", "params": {}},
            ],
        },
        "send_hints": {
            "pad": [{"return_name": "A-Reverb", "value": 0.6}, {"return_name": "B-Delay", "value": 0.4}],
            "perc": [{"return_name": "A-Reverb", "value": 0.5}, {"return_name": "B-Delay", "value": 0.3}],
            "atmos": [{"return_name": "A-Reverb", "value": 0.7}],
        },
        "knowledge_search_queries": [
            "dub techno production",
            "Basic Channel production technique",
            "dub chord stab Auto Filter",
        ],
        "spacing_advice": "TRUST silence. 4-bar loops can be 80% empty. Atmosphere IS the content.",
        "production_hints": "Long reverb tails (4-8 sec), low-pass filter sweeps, dub delay 1/8 with ~50% feedback.",
    },
    "house": {
        "rhythmic_feel": "4OTF kick, claps on 2 and 4, hats offbeats. Bass often pumps with sidechain — space on beat 1.",
        "harmonic_palette": {
            "summary": "Minor or major; i-VI-iv-V common. Soulful chord extensions (maj7, m7). 4-bar cycles.",
            "progressions": [
                {"name": "i-VI-iv-V", "degrees": [1, 6, 4, 5], "feel": "classic house cycle"},
                {"name": "i-iv-VII-III", "degrees": [1, 4, 7, 3], "feel": "deeper, modal"},
                {"name": "ii-V-i", "degrees": [2, 5, 1], "feel": "jazz-house resolution"},
                {"name": "i-VII-VI-V", "degrees": [1, 7, 6, 5], "feel": "Andalusian descending"},
            ],
            "color_tones": ["m7 chord extensions", "9 and 11 added to pad chords"],
        },
        "rhythmic_palette": [
            {"name": "4OTF_classic", "kick_pattern": "every quarter, full vel", "swing_pct": 50},
            {"name": "4OTF_with_swing", "kick_pattern": "every quarter + 16ths swung", "swing_pct": 60},
            {"name": "syncopated_house", "kick_pattern": "kicks 1, 2.5, 3, 3.5", "swing_pct": 55},
        ],
        "articulation_targets": {
            "velocity_stddev_min": 7,
            "ghost_note_velocity_range": [30, 50],
            "duration_variation_count_min": 3,
            "swing_pct": 55,
            "humanization_timing_ms": 5,
        },
        "effect_chain_hints": {
            "kick": [
                {"device": "Compressor", "params": {"Threshold": 0.75, "Ratio": 0.75}},
                {"device": "EQ Eight", "params": {}},
            ],
            "bass": [
                {"device": "Saturator", "params": {"Drive": 0.45}},
                {"device": "Compressor", "params": {"Threshold": 0.7, "Ratio": 0.85}},
                {"device": "EQ Eight", "params": {}},
            ],
            "clap": [
                {"device": "EQ Eight", "params": {}},
            ],
            "pad": [
                {"device": "Compressor", "params": {"Threshold": 0.7, "Ratio": 0.75}},
                {"device": "Chorus-Ensemble", "params": {}},
            ],
        },
        "send_hints": {
            "clap": [{"return_name": "A-Reverb", "value": 0.3}],
            "pad": [{"return_name": "A-Reverb", "value": 0.3}],
        },
        "knowledge_search_queries": [
            "deep house production",
            "house bass sidechain technique",
            "house chord progression jazzy",
        ],
        "spacing_advice": "Bass leaves room on beat 1 for kick (sidechain). Hats fill offbeats. Pad held, lead carries melody.",
        "production_hints": "Sidechain on bass + pad triggered by kick. Warm tape saturation. Reverb on snare/clap.",
    },
    "hip hop": {
        "rhythmic_feel": "Boom-bap kick (1, 2.5, 3, 3.75) OR trap-sparse kicks. Snare/clap on 2 and 4 (locked). Hats 8ths or rolling 16ths.",
        "harmonic_palette": {
            "summary": "Minor often, jazzy chord extensions (m7, maj7, m9). Sample-based sometimes — progressions less strict.",
            "progressions": [
                {"name": "i-VI-ii°-V", "degrees": [1, 6, 2, 5], "feel": "jazzy minor"},
                {"name": "i-iv-bVII-bIII", "degrees": [1, 4, 7, 3], "feel": "modal mixture, soulful"},
                {"name": "i-bVI-bIII-bVII", "degrees": [1, 6, 3, 7], "feel": "all minor, all chromatic mediant"},
                {"name": "static i with passing", "degrees": [1, 1, 1, 1], "feel": "hold on i, agent adds passing tones"},
            ],
            "color_tones": ["maj7 chord extensions on i", "9 and 11 added (jazz voicing)"],
        },
        "rhythmic_palette": [
            {"name": "boom_bap", "kick_pattern": "1, 2.5, 3, 3.75 (offbeat 8ths)", "swing_pct": 58},
            {"name": "trap_sparse", "kick_pattern": "1, 1.75, 2.5, 3.5 (sparse syncopation)", "swing_pct": 50},
            {"name": "j_dilla_swung", "kick_pattern": "1, 2.5+30ms, 3 (Dilla swung)", "swing_pct": 65},
        ],
        "articulation_targets": {
            "velocity_stddev_min": 10,
            "ghost_note_velocity_range": [30, 50],
            "duration_variation_count_min": 4,
            "swing_pct": 58,
            "humanization_timing_ms": 8,
        },
        "effect_chain_hints": {
            "kick": [
                {"device": "Saturator", "params": {"Drive": 0.3}},
                {"device": "Compressor", "params": {"Threshold": 0.8, "Ratio": 0.85}},
                {"device": "EQ Eight", "params": {}},
            ],
            "snare": [
                {"device": "Compressor", "params": {"Threshold": 0.75, "Ratio": 0.75}},
                {"device": "EQ Eight", "params": {}},
            ],
            "bass": [
                {"device": "Saturator", "params": {"Drive": 0.4}},
                {"device": "EQ Eight", "params": {}},
            ],
            "pad": [
                {"device": "Auto Filter", "params": {}},
                {"device": "Chorus-Ensemble", "params": {}},
            ],
        },
        "send_hints": {
            "snare": [{"return_name": "A-Reverb", "value": 0.2}],
            "pad": [{"return_name": "A-Reverb", "value": 0.25}],
        },
        "knowledge_search_queries": [
            "boom bap production technique",
            "lo-fi hip hop chord voicing",
            "J Dilla swing humanization",
        ],
        "spacing_advice": "Bass on the down — leave kick room. Pad/keys often jazzy chord stabs not held pads.",
        "production_hints": "Lo-fi tape saturation, vinyl crackle (sparingly), warm low-pass filter.",
    },
    "drum and bass": {
        "rhythmic_feel": "Kick on 1 and 2.75. Snare strict 2 and 4. Hats fast 16ths with strong velocity arc.",
        "harmonic_palette": {
            "summary": "Minor, often single-chord vamps. Reese basses chromatic. Ambient pads above the chaos.",
            "progressions": [
                {"name": "static i", "degrees": [1, 1, 1, 1], "feel": "hold on tonic, drums dominate"},
                {"name": "i-bVI", "degrees": [1, 6], "feel": "chromatic mediant, dark"},
                {"name": "chromatic walk", "degrees": [1, 1, 1, 1], "feel": "bass walks chromatically over static chord"},
            ],
            "color_tones": ["b5 over chromatic walks (Phrygian flavor)"],
        },
        "rhythmic_palette": [
            {"name": "amen_break_inspired", "kick_pattern": "1, 2.75, snare 2&4 with ghost rolls", "swing_pct": 50},
            {"name": "two_step", "kick_pattern": "1 and 2.75 only", "swing_pct": 50},
            {"name": "neurofunk", "kick_pattern": "1, 2.5, 3, 3.75 with double-time", "swing_pct": 50},
        ],
        "articulation_targets": {
            "velocity_stddev_min": 12,
            "ghost_note_velocity_range": [25, 50],
            "duration_variation_count_min": 4,
            "swing_pct": 50,
            "humanization_timing_ms": 3,
        },
        "effect_chain_hints": {
            "kick": [
                {"device": "Saturator", "params": {"Drive": 0.6}},
                {"device": "Compressor", "params": {"Threshold": 0.85, "Ratio": 0.9}},
                {"device": "EQ Eight", "params": {}},
            ],
            "snare": [
                {"device": "Compressor", "params": {"Threshold": 0.8, "Ratio": 0.9}},
                {"device": "Saturator", "params": {"Drive": 0.4}},
            ],
            "bass": [
                {"device": "Auto Filter", "params": {}},
                {"device": "Saturator", "params": {"Drive": 0.6}},
                {"device": "EQ Eight", "params": {}},
            ],
            "hat": [
                {"device": "EQ Eight", "params": {}},
            ],
        },
        "send_hints": {
            "snare": [{"return_name": "A-Reverb", "value": 0.3}],
            "hat": [{"return_name": "A-Reverb", "value": 0.1}],
        },
        "knowledge_search_queries": [
            "drum and bass production",
            "reese bass design",
            "amen break programming",
        ],
        "spacing_advice": "Drums dominate. Bass and pad carry harmonic content but stay out of drum frequencies.",
        "production_hints": "Reese bass = detuned saw stack with movement. Pad above the noise. Tight compression on drums.",
    },
    "ambient": {
        "rhythmic_feel": "Often rhythmless, or sparse percussive accents. NO drums needed unless explicit.",
        "harmonic_palette": {
            "summary": "Slow chord changes (4-8 bars per chord). Modal/static. Pedal points, drones.",
            "progressions": [
                {"name": "single chord drone", "degrees": [1, 1, 1, 1], "feel": "16-32 bar held chord"},
                {"name": "i-bVI very slow", "degrees": [1, 6], "feel": "8 bars per chord, chromatic mediant"},
                {"name": "modal cycle slow", "degrees": [1, 4, 1, 5], "feel": "8 bars per chord, breathing"},
            ],
            "color_tones": ["maj7, 9, 11 — every color tone available"],
        },
        "rhythmic_palette": [
            {"name": "no_drums", "kick_pattern": "(skip drum layers entirely)", "swing_pct": 50},
            {"name": "sparse_perc", "kick_pattern": "occasional bell or bowl, no kick", "swing_pct": 50},
        ],
        "articulation_targets": {
            "velocity_stddev_min": 4,
            "ghost_note_velocity_range": [20, 40],
            "duration_variation_count_min": 2,
            "swing_pct": 50,
            "humanization_timing_ms": 15,
        },
        "effect_chain_hints": {
            "pad": [
                {"device": "Auto Filter", "params": {}},
                {"device": "Reverb", "params": {}},
                {"device": "Chorus-Ensemble", "params": {}},
            ],
            "atmos": [
                {"device": "Echo", "params": {}},
                {"device": "Erosion", "params": {}},
            ],
        },
        "send_hints": {
            "atmos": [{"return_name": "A-Reverb", "value": 0.7}],
        },
        "knowledge_search_queries": [
            "ambient texture design",
            "drone production technique",
            "Brian Eno ambient",
        ],
        "spacing_advice": "Massive space. Single notes can carry whole bars. Reverb is the rhythm.",
        "production_hints": "Long reverb (10s+), evolving texture, granular sample movement.",
    },
    "lo-fi": {
        "rhythmic_feel": "Boom-bap-ish kick, snare on 2/4, hats with swing. Slight tempo wobble feel.",
        "harmonic_palette": {
            "summary": "Jazzy minor or major 7th chords. Borrowed chords, Em7-A7-Dmaj7-style progressions.",
            "progressions": [
                {"name": "ii-V-I", "degrees": [2, 5, 1], "feel": "jazz turnaround"},
                {"name": "i-bIII-VI-IV", "degrees": [1, 3, 6, 4], "feel": "modal-mixture lo-fi"},
                {"name": "i-iv-bVII-bIII", "degrees": [1, 4, 7, 3], "feel": "soulful"},
            ],
            "color_tones": ["maj7, m7, 9, 13 (jazz voicings)"],
        },
        "rhythmic_palette": [
            {"name": "boom_bap_swung", "kick_pattern": "1, 2.5, 3, 3.75 with heavy swing", "swing_pct": 62},
            {"name": "j_dilla", "kick_pattern": "1, off-by-30ms, 3", "swing_pct": 65},
        ],
        "articulation_targets": {
            "velocity_stddev_min": 12,
            "ghost_note_velocity_range": [30, 55],
            "duration_variation_count_min": 4,
            "swing_pct": 62,
            "humanization_timing_ms": 12,
        },
        "effect_chain_hints": {
            "kick": [
                {"device": "Saturator", "params": {"Drive": 0.35}},
                {"device": "EQ Eight", "params": {}},
            ],
            "bass": [
                {"device": "Saturator", "params": {"Drive": 0.4}},
                {"device": "EQ Eight", "params": {}},
            ],
            "pad": [
                {"device": "Auto Filter", "params": {}},
                {"device": "Chorus-Ensemble", "params": {}},
                {"device": "Vinyl Distortion", "params": {}},
            ],
        },
        "send_hints": {
            "pad": [{"return_name": "A-Reverb", "value": 0.25}],
        },
        "knowledge_search_queries": [
            "lo-fi hip hop production",
            "jazz chord voicing for lo-fi",
            "tape saturation technique",
        ],
        "spacing_advice": "Mid-density. Lots of room for the warmth/dust to breathe.",
        "production_hints": "Tape saturation HEAVY. Vinyl crackle LOW. Detune chord pads slightly.",
    },
    "trap": {
        "rhythmic_feel": "Sparse trap kick. Snare/clap on 2 and 4. Hats rolling 16ths/32nds with rolls.",
        "harmonic_palette": {
            "summary": "Minor, often single-chord. Cinematic, dark. 808 sub bass.",
            "progressions": [
                {"name": "static i", "degrees": [1, 1, 1, 1], "feel": "hold on tonic, drums + 808 dominate"},
                {"name": "i-bVI", "degrees": [1, 6], "feel": "cinematic chromatic mediant"},
                {"name": "i-iv", "degrees": [1, 4], "feel": "modal, dark"},
            ],
            "color_tones": ["b5, m7"],
        },
        "rhythmic_palette": [
            {"name": "sparse_trap", "kick_pattern": "1, 1.75, 2.5, 3, 3.75 (5 hits/bar)", "swing_pct": 50},
            {"name": "808_long_sustain", "kick_pattern": "1 + bass 808 sustains", "swing_pct": 50},
        ],
        "articulation_targets": {
            "velocity_stddev_min": 8,
            "ghost_note_velocity_range": [30, 55],
            "duration_variation_count_min": 5,
            "swing_pct": 50,
            "humanization_timing_ms": 4,
        },
        "effect_chain_hints": {
            "kick": [
                {"device": "Saturator", "params": {"Drive": 0.55}},
                {"device": "EQ Eight", "params": {}},
            ],
            "bass": [
                {"device": "Saturator", "params": {"Drive": 0.7}},
                {"device": "Compressor", "params": {}},
                {"device": "Auto Filter", "params": {}},
            ],
            "hat": [
                {"device": "EQ Eight", "params": {}},
            ],
            "snare": [
                {"device": "Reverb", "params": {}},
            ],
        },
        "send_hints": {
            "snare": [{"return_name": "A-Reverb", "value": 0.22}],
            "hat": [{"return_name": "A-Reverb", "value": 0.10}],
        },
        "knowledge_search_queries": [
            "trap 808 design",
            "trap hi-hat rolls programming",
            "trap production",
        ],
        "spacing_advice": "Drums are dense; bass holds the harmonic foundation. Pad/melody (if used) sparse.",
        "production_hints": "808 sub long sustains. Tight kick. Saturated hats. Reverb on snare/clap.",
    },
}


# ── Ableton Knowledge integration: per-genre-role query templates ───
#
# Queries fired against the Ableton Knowledge MCP (search_transcripts +
# search_live_manual + search_videos) to surface producer-voice technique
# snippets per role. The brief includes these as `recommended_searches`;
# the agent fires them inline before designing and attributes techniques
# in the apply plan.
#
# Coverage strategy: 1-2 queries per (genre × role) targeting the
# search_transcripts tool (the gold mine — semantic search over Ableton's
# YouTube tutorial transcripts, which is where producer-voice context lives).

_DEVICE_FOR_ROLE: dict[str, list[str]] = {
    "kick":  ["Saturator", "Drum Buss", "Compressor"],
    "snare": ["Drum Buss", "Compressor", "Reverb"],
    "hat":   ["EQ Eight", "Reverb"],
    "perc":  ["Echo", "Reverb"],
    "clap":  ["Reverb", "Drum Buss"],
    "bass":  ["Saturator", "Auto Filter", "Operator", "Wavetable"],
    "pad":   ["Auto Filter", "Reverb", "Chorus-Ensemble"],
    "lead":  ["Operator", "Wavetable", "Auto Filter"],
    "atmos": ["Reverb", "Auto Filter", "Granulator III"],
}


def _build_genre_role_queries(genre: str, role: str) -> list[dict]:
    """BUG-L (2026-05-01): Ableton's tutorial corpus is feature/device-named,
    NOT producer-technique-named. The previous queries ("techno kick design
    saturation transient") returned 0 results because the corpus indexes by
    "Saturator", "Drum Buss", etc. — Live's actual feature names.

    This builder generates queries that reliably hit the corpus:
      1. Device-name searches against the Live manual (authoritative, dense)
      2. User-question-shape transcript searches (broader hit rate)
      3. One genre-named video search (catches "Made in Ableton" producer content)
    """
    devices = _DEVICE_FOR_ROLE.get(role, ["EQ Eight"])
    queries: list[dict] = []

    # 1. Device-name in manual (always returns dense, high-quality content)
    if devices:
        queries.append({"tool": "search_live_manual", "query": devices[0]})

    # 2. User-question shape transcript search
    if role in ("kick", "snare", "hat", "perc", "clap"):
        queries.append({
            "tool": "search_transcripts",
            "query": f"how to mix {role}",
        })
    elif role == "bass":
        queries.append({"tool": "search_transcripts", "query": "bass synthesis low end"})
    elif role == "pad":
        queries.append({"tool": "search_transcripts", "query": "pad sound design"})
    else:
        queries.append({"tool": "search_transcripts", "query": f"{role} design"})

    # 3. Genre-keyword video search (catches "Made in Ableton" producer content)
    g = (genre or "").strip()
    if g:
        queries.append({"tool": "search_videos", "query": f"{g} {role}"})

    return queries


def get_knowledge_queries_for_role(genre: str, role: str) -> list[dict]:
    """Return the recommended search queries for a (genre, role) pair.

    Built dynamically from device-name lookups + user-question patterns
    so we hit Ableton's actual tutorial/manual corpus (BUG-L).
    """
    return _build_genre_role_queries(genre or "", role)


# Kept for backward compat — referenced by tests + reportable from
# brief metadata if needed.
GENRE_KNOWLEDGE_QUERIES: dict[str, dict[str, list[dict]]] = {
    genre: {role: _build_genre_role_queries(genre, role) for role in _DEVICE_FOR_ROLE}
    for genre in ("techno", "dub techno", "house", "hip hop",
                  "drum and bass", "ambient", "lo-fi", "trap")
}


def reference_artist_queries(artist: str, genre: str = "") -> list[dict]:
    """Return search queries for a reference-artist composition.

    Tier 2: when the user says compose(reference="Ricardo Villalobos"),
    the brief includes these searches so the agent designs USING that
    artist's signature techniques.
    """
    if not artist:
        return []
    a = artist.strip()
    queries = [
        {"tool": "search_videos", "query": f"{a} production technique"},
        {"tool": "search_transcripts", "query": f"{a} {genre or ''}".strip()},
        {"tool": "search_transcripts", "query": f"{a} signature sound"},
    ]
    return queries


# ── Creative seeds (random aesthetic bias per call) ──────────────────
# The brief picks one randomly per call. The agent reads it and tilts
# the design that way. Same prompt + different seed → different feel.

CREATIVE_SEEDS: list[dict] = [
    {"label": "spacious / minimal", "directive": "Leave more silence than you think you should. ~70% of the loop should breathe. Single notes can carry full bars."},
    {"label": "dense / driving", "directive": "Pack the rhythm — overlapping perc, busy hats, syncopated bass. Push the energy."},
    {"label": "fragmented / glitchy", "directive": "Break up the pulse — start mid-phrase, cut notes short, stutter rhythms. Embrace asymmetry."},
    {"label": "warm / dusty", "directive": "Soften everything — gentle velocities, smooth durations, no sharp transients. Tape-saturation feel even without effects."},
    {"label": "hypnotic / repetitive", "directive": "Lock into a single 1-bar phrase and repeat. Tiny micro-variations across bars 2-4. Trance-inducing."},
    {"label": "off-balance / asymmetric", "directive": "Use 5-bar phrases, polyrhythm 3-against-4, displaced downbeats. Make it feel WRONG in a good way."},
    {"label": "spacious dub", "directive": "Treat reverb and delay as instruments. Notes are just excitations of the space."},
    {"label": "cinematic / brooding", "directive": "Long sustains, slow chord changes, low-velocity layers. Atmosphere is the content."},
    {"label": "playful / bouncy", "directive": "Stagger note placements off-grid by tens of ms. Velocity ramps and dips. Make it dance."},
    {"label": "monochromatic / focused", "directive": "Stick to 2-3 pitches max across all melodic layers. The single repeated motif is the hook."},
]


# ── Anti-defaults per genre (random anti-pattern bias per call) ──────
# Forces creative reach by explicitly forbidding the most-common pattern
# choice for the genre on this call. Picks 1-2 randomly.

ANTI_DEFAULTS_BY_GENRE: dict[str, list[str]] = {
    "techno": [
        "no four-on-floor — try a syncopated kick instead",
        "no held-chord pad — use stabs or evolving texture",
        "no bass on every 8th — leave space",
        "no minor key — try Phrygian or Locrian for this call",
    ],
    "dub techno": [
        "no four-on-floor kick — minimal kick or no kick",
        "no on-the-grid chord stabs — push them off-beat or polyrhythmic",
        "no major-7 pad — use sus2/sus4 or single-pitch drone",
    ],
    "house": [
        "no plain four-on-floor — add ghost kicks or syncopated 16ths",
        "no claps strictly on 2 and 4 — try displaced clap on 2.5",
        "no 4-bar progression — try 8-bar or 5-bar phrasing",
    ],
    "hip hop": [
        "no boom-bap kick — try trap-sparse or off-grid placement",
        "no snare/clap strictly on 2 and 4 — push or pull by 30ms",
        "no held pad — use jazzy chord stabs",
    ],
    "drum and bass": [
        "no straight 2-step — try amen-break-inspired ghost rolls",
        "no chromatic reese — try modal vamping",
        "no 4-bar phrase — try 6 or 8",
    ],
    "ambient": [
        "no perfect cadence — avoid V-I",
        "no 4-bar phrasing — extend chord changes to 8-16 bars",
        "no static velocity — slow swells and dips",
    ],
    "lo-fi": [
        "no straight boom-bap — push the swing past 65%",
        "no on-grid chord changes — anticipate by an 8th",
        "no major-key happy progression — keep it minor and jazzy",
    ],
    "trap": [
        "no kick exactly on 1 — anticipate by 16th or push by 16th",
        "no 16th hat rolls — try 32nd or 64th with varying velocity arcs",
        "no minor pad — try a single 808 with vibrato as the only melodic content",
    ],
    "_default": [
        "avoid the most obvious rhythmic choice for this genre",
        "leave at least one beat fully silent across the loop",
        "use a non-diatonic color tone at least once",
    ],
}


def get_creative_guidance(genre: str, sub_genre: str = "") -> dict:
    """Return the creative-guidance dict for a genre, falling back to the
    closest match if the exact genre isn't in our guidance map."""
    g = (genre or "").lower().strip()
    if g in GENRE_CREATIVE_GUIDANCE:
        return GENRE_CREATIVE_GUIDANCE[g]
    s = (sub_genre or "").lower().strip()
    if s in GENRE_CREATIVE_GUIDANCE:
        return GENRE_CREATIVE_GUIDANCE[s]
    # Generic fallback (must include all the structured fields too)
    return {
        "rhythmic_feel": "Match the prompt's vibe; favor groove + space over density.",
        "harmonic_palette": {
            "summary": "Use the requested key. Minor by default unless prompt suggests major.",
            "progressions": [
                {"name": "static i", "degrees": [1, 1, 1, 1], "feel": "hold on tonic"},
                {"name": "i-IV-V-i", "degrees": [1, 4, 5, 1], "feel": "classic functional"},
            ],
            "color_tones": ["maj7", "9"],
        },
        "rhythmic_palette": [
            {"name": "generic_4OTF", "kick_pattern": "every quarter", "swing_pct": 50},
        ],
        "articulation_targets": {
            "velocity_stddev_min": 6,
            "ghost_note_velocity_range": [25, 45],
            "duration_variation_count_min": 2,
            "swing_pct": 50,
            "humanization_timing_ms": 5,
        },
        "effect_chain_hints": {},
        "send_hints": {},
        "knowledge_search_queries": [],
        "spacing_advice": "Leave room between layers. More space = more impact.",
        "production_hints": "Velocity humanization, voice-leading, vary durations.",
    }


def pick_creative_seed(rng: Optional[random.Random] = None) -> dict:
    """Pick a random creative seed for THIS call. Different per call =
    different aesthetic bias = different sound from same prompt."""
    rng = rng or random.Random()
    return rng.choice(CREATIVE_SEEDS)


def pick_anti_defaults(
    genre: str, count: int = 2, rng: Optional[random.Random] = None
) -> list[str]:
    """Pick `count` random anti-defaults for the genre. Forces the agent
    to reach beyond the obvious genre-default move on each call."""
    rng = rng or random.Random()
    g = (genre or "").lower().strip()
    pool = ANTI_DEFAULTS_BY_GENRE.get(g) or ANTI_DEFAULTS_BY_GENRE.get("_default") or []
    if not pool:
        return []
    n = min(count, len(pool))
    return rng.sample(pool, n)


# ── Brief builder — the heart of the new fast mode ───────────────────


# Recommended MIDI octave per role — prevents the agent from designing
# bass at A1 (sub-bass territory, often inaudible or muddy) or pad at
# octave 6 (too thin). User feedback 2026-05-01: "the drums and bass
# everything is super low pitched". The brief now explicitly tells the
# agent which octaves work for each role.
RECOMMENDED_OCTAVES_PER_ROLE: dict[str, dict] = {
    "kick":  {"midi_pitch": 36, "note": "C1", "rationale": "drum-rack convention; sample plays at natural pitch"},
    "snare": {"midi_pitch": 38, "note": "D1", "rationale": "drum-rack convention"},
    "hat":   {"midi_pitch": 42, "note": "F#1", "rationale": "drum-rack closed hat convention"},
    "perc":  {"midi_pitch": 39, "note": "Eb1", "rationale": "drum-rack perc convention"},
    "clap":  {"midi_pitch": 39, "note": "Eb1", "rationale": "drum-rack clap convention"},
    "bass":  {"recommended_octave": 2, "midi_range": [33, 50], "rationale": "bass synth presence — A2-Bb2 range. AVOID octave 1 (A1=33) for techno bass; sub-territory becomes inaudible/muddy."},
    "pad":   {"recommended_octave": 4, "midi_range": [55, 76], "rationale": "mid-range pad sits behind kick/bass. C4=60, A4=69 typical."},
    "lead":  {"recommended_octave": 5, "midi_range": [60, 84], "rationale": "lead cuts through; octaves 5-6 typical."},
    "atmos": {"recommended_octave": 5, "midi_range": [60, 84], "rationale": "atmos floats above the mix. Layered drones can use multiple octaves."},
    "vox":   {"recommended_octave": 4, "midi_range": [55, 76], "rationale": "vocal range C3-C5."},
}


def _extract_loaded_device_names(session_info: dict) -> set[str]:
    """Anti-repeat helper: extract names of devices currently loaded in the
    session, so the brief picker can bias AWAY from already-used devices.

    This solves the "Tree Tone always wins for pad" repetition the user
    called out — once Tree Tone is loaded on track 3, the next call's
    pad picker will see it in exclude_names and pick something else.
    """
    names: set[str] = set()
    for track in (session_info.get("tracks") or []):
        # Some session_info shapes carry track devices; if not, the brief
        # builder has to look up via get_track_info per track. The cheap
        # path is fine for now — read whatever names are available.
        for dev in (track.get("devices") or []):
            n = dev.get("name") or ""
            if n:
                names.add(n)
    return names


def _extract_loaded_preset_uris(session_info: dict) -> set[str]:
    """Anti-repeat helper: extract browser URIs of curated presets already
    loaded in the session.

    Looks for device names ending in .adg or .adv (these are curated presets
    that were loaded via load_browser_item and carry a browser URI). Adds the
    URI so get_role_candidates can filter them via excluded_uris.

    Also extracts sample paths from Simpler/Sampler devices when available.
    """
    uris: set[str] = set()
    for track in (session_info.get("tracks") or []):
        for dev in (track.get("devices") or []):
            uri = dev.get("uri") or dev.get("browser_uri") or ""
            if uri:
                uris.add(uri)
            # Also capture sample paths stored on Simpler devices
            sample_path = dev.get("sample_path") or dev.get("file_path") or ""
            if sample_path:
                uris.add(sample_path)
    return uris


def build_creative_brief(
    intent: CompositionIntent,
    atlas: Any,
    fresh_project_state: dict,
    bars: int = 4,
    candidates_per_role: int = 12,
    rng: Optional[random.Random] = None,
    reference: Optional[str] = None,
    exclude_loaded_device_names: Optional[set[str]] = None,
    *,
    ableton: Any = None,
    excluded_preset_uris: Optional[set[str]] = None,
) -> dict:
    """Build the creative brief returned by compose(mode="fast").

    Phase-A enrichments (2026-05-01):
      - 12 atlas candidates per role (was 5) → more atlas variety surfaced
      - Creative seed (random aesthetic bias per call from CREATIVE_SEEDS)
      - Anti-defaults (random anti-pattern bias per call)
      - Structured harmonic_palette: chord progressions w/ degrees + color tones
      - Structured rhythmic_palette: named gestures w/ swing %
      - Articulation targets: velocity stddev / ghost-note range / etc.
      - Effect chain hints per role (genre-typical processing)
      - knowledge_search_queries: queries the agent can run via Ableton Knowledge
        MCP (search_transcripts / search_videos / search_live_manual) for
        producer-voice technique inspiration

    Phase-4 Task 18a-followup (§1 fix):
      - ableton: if provided, fires search_browser("sounds/") before atlas so
        curated .adg/.adv presets are Tier-A candidates for every role.
      - excluded_preset_uris: URIs of recently-loaded curated presets — filtered
        out so the agent can't re-pick the same .adv twice in a row.

    The agent reads this, designs creatively, submits to compose_fast_apply.
    """
    rng = rng or random.Random()
    key_root, mode_str = parse_key(intent.key)
    bpm = intent.tempo or 120

    # Scale pitches at multiple octaves
    scale_pitches = {
        "tonic_at_octave": {
            str(o): degree_to_pitch(1, key_root, o, mode_str) for o in range(1, 6)
        },
        "scale_at_octave_4": scale_pitches_in_octave(key_root, 4, mode_str),
        "scale_at_octave_2": scale_pitches_in_octave(key_root, 2, mode_str),
        "diatonic_chord_roots_octave_4": [
            chord_at_degree(d, key_root, 4, mode_str)[0] for d in range(1, 8)
        ],
    }

    # Atlas + sounds/ instrument candidates — 12 per role with anti-repeat exclusion.
    # (NEW 2026-05-01: pass currently-loaded device names so candidates bias toward
    # variety across calls instead of repeating same picks.)
    # (NEW 18a-followup: pass ableton + excluded_preset_uris for sounds/ hunt.)
    suggested_roles = _suggest_layer_roles(intent)
    instruments_by_role: dict[str, list[dict]] = {}
    for role in suggested_roles:
        candidates = get_role_candidates(
            atlas, role,
            genre=intent.genre or "",
            top_n=candidates_per_role,
            exclude_names=exclude_loaded_device_names,
            ableton=ableton,
            excluded_uris=excluded_preset_uris,
        )
        instruments_by_role[role] = candidates

    # Per-role octave recommendations (NEW: prevents A1 bass or octave-6 pad)
    octaves_by_role: dict[str, dict] = {
        role: RECOMMENDED_OCTAVES_PER_ROLE[role]
        for role in suggested_roles
        if role in RECOMMENDED_OCTAVES_PER_ROLE
    }

    # Genre creative guidance (structured palettes + text advice + effect chains)
    guidance = get_creative_guidance(intent.genre or "", intent.sub_genre or "")

    # Phase A — random per-call creative seed + anti-defaults force surprise
    creative_seed = pick_creative_seed(rng=rng)
    anti_defaults = pick_anti_defaults(
        intent.genre or "", count=2, rng=rng,
    )

    # Tier-1A: Per-role recommended searches against Ableton Knowledge MCP.
    # BUG-O fix (2026-05-01): cap at ONE recommended search per role (the
    # device-name manual lookup, which is the most reliable corpus). The
    # earlier 3-per-role design produced 12 searches × ~1-2s each = 24s of
    # extra latency the agent is unlikely to honor anyway. The remaining
    # queries are surfaced in `optional_searches` for the agent to fire
    # only when it has time.
    recommended_searches: list[dict] = []
    optional_searches: list[dict] = []
    for role in suggested_roles:
        role_queries = get_knowledge_queries_for_role(intent.genre or "", role)
        if not role_queries:
            continue
        # Most useful query per role goes in recommended (manual or first)
        primary = role_queries[0]
        recommended_searches.append({
            "role": role,
            "tool": primary["tool"],
            "query": primary["query"],
        })
        # Rest go in optional
        for q in role_queries[1:]:
            optional_searches.append({
                "role": role,
                "tool": q["tool"],
                "query": q["query"],
            })

    # Tier-2: Reference-artist queries when caller passes a reference.
    reference_searches: list[dict] = []
    if reference:
        for q in reference_artist_queries(reference, genre=intent.genre or ""):
            reference_searches.append({
                "role": None,   # global, not role-specific
                "tool": q["tool"],
                "query": q["query"],
            })

    return {
        "phase": "brief",
        "mode": "fast",
        "phase_version": "A",
        "intent": intent.to_dict(),
        "tempo": bpm,
        "key": {
            "key_str": intent.key or "",
            "key_root": key_root,
            "mode": mode_str,
        },
        "scale_pitches": scale_pitches,
        "creative_guidance": guidance,
        "creative_seed": creative_seed,
        "anti_defaults": anti_defaults,
        "recommended_searches": recommended_searches,
        "optional_searches": optional_searches,
        "reference_artist": reference,
        "reference_searches": reference_searches,
        "instruments_by_role": instruments_by_role,
        "octaves_by_role": octaves_by_role,
        "excluded_recently_used": sorted(exclude_loaded_device_names or set()),
        "suggested_layer_count": len(suggested_roles),
        "suggested_roles": suggested_roles,
        "bars": bars,
        "fresh_project_state": fresh_project_state,
        "next_step": (
            "READ THIS BRIEF, THEN DESIGN A FRESH LAYER PLAN.\n"
            "1. Honor the creative_seed['directive'] — let it tilt your design.\n"
            "2. Honor the anti_defaults — DO NOT use the patterns listed on this call.\n"
            "3. **OCTAVE DISCIPLINE**: For tonal layers, design notes within the\n"
            "   `octaves_by_role[role].midi_range`. Tonal-range traps to avoid:\n"
            "   bass at A1=33 is sub-territory and inaudible/muddy on most systems —\n"
            "   use A2=45 or higher. Pad at octave 6 is too thin — stay around\n"
            "   octave 4-5. The brief gives you the exact ranges per role.\n"
            "4. **ANTI-REPEAT**: `excluded_recently_used` lists device names already\n"
            "   loaded in the session — the candidate list ALREADY has them filtered\n"
            "   out, so just pick from `instruments_by_role[role]` confidently. If\n"
            "   the list looks short for a role, that's because we're forcing variety.\n"
            "   **TIER A vs B distinction**: Each candidate in `instruments_by_role[role]`\n"
            "   carries a `tier` field. Tier-A candidates ('A_sample_ready') load with\n"
            "   sound on note-on. Tier-B candidates ('B_audible_default') also produce\n"
            "   sound by default. Both are safe to pick. There is no Tier-C in the brief\n"
            "   — those are filtered out before the brief reaches you.\n"
            "5. **TIER-1: Fire each search in `recommended_searches` BEFORE designing\n"
            "   that role.** Each entry gives you a (tool, query) pair — call the named\n"
            "   Ableton Knowledge MCP tool. Most queries hit the Live manual or video\n"
            "   tutorials; capture 1 useful snippet per role and apply it.\n"
            "6. **TIER-2: If `reference_artist` is set**, also fire each search in\n"
            "   `reference_searches` and design USING that artist's signature techniques.\n"
            "7. For each layer: pick ONE uri from instruments_by_role[role], design\n"
            "   MIDI notes (start_time in beats, pitch, duration, velocity 0-127).\n"
            "   Hit the articulation_targets — velocity stddev, ghost notes, etc.\n"
            "8. Pick ONE progression from creative_guidance.harmonic_palette.progressions\n"
            "   (or invent your own with color tones).\n"
            "9. **PHASE B: EFFECT CHAIN PER LAYER** — for each layer, include an\n"
            "   `effects` array of native Live devices (insert_device-compatible).\n"
            "   `creative_guidance.effect_chain_hints[role]` gives you the canonical\n"
            "   genre-typical chain: [{device: 'Saturator', params: {Drive: 0.4}}, ...]\n"
            "   You can ADAPT values to fit the prompt mood (heavier in trap, subtler\n"
            "   in ambient) — but anchor on the hint. Saturator/Compressor params are\n"
            "   normalized 0-1; EQ Eight uses absolute Hz/dB. Leave params={} when\n"
            "   you only want the device with no specific param overrides.\n"
            "10. **PHASE B: SENDS PER LAYER** — for layers that benefit from spatial\n"
            "    depth (pad, vox, snare), include `sends`: [{return_name: 'A-Reverb',\n"
            "    value: 0.25}]. `creative_guidance.send_hints[role]` gives you the\n"
            "    starting point. Skip the layer if no return tracks exist (kicks rarely\n"
            "    need send reverb).\n"
            "11. **TIER-1: Each layer in your plan MUST include `applied_technique`** —\n"
            "    the snippet + source you used. compose_fast_apply will surface these.\n"
            "12. Submit the complete plan via compose_fast_apply(plan={layers:[...]}).\n"
            "13. NEVER use a template. Make every call genuinely different."
        ),
        "apply_schema_hint": {
            "layers": [
                {
                    "role": "string (kick/snare/hat/perc/bass/pad/lead/atmos/etc.)",
                    "uri": "atlas URI from instruments_by_role[role]",
                    "track_name": "optional display name",
                    "notes": [
                        {"pitch": "int 0-127", "start_time": "float beats from clip start",
                         "duration": "float beats", "velocity": "int 0-127"}
                    ],
                    "effects": [
                        {"device": "native Live device name (e.g. Saturator, EQ Eight, Reverb)",
                         "params": "dict of {parameter_name: value}; {} for none"}
                    ],
                    "sends": [
                        {"return_name": "case-insensitive return track name (e.g. A-Reverb)",
                         "value": "float 0-1"}
                    ],
                    "applied_technique": {
                        "snippet": "the producer-voice snippet your design honored",
                        "source": "video title or manual section",
                        "source_url": "url if available",
                        "applied_in": "how you applied it (e.g. '4-bar root sustain with sidechain LFO modulation')",
                    },
                }
            ],
            "scene_index": "int or null (auto-pick)",
            "tempo": "int (overrides intent.tempo if set)",
        },
    }


def _suggest_layer_roles(intent: CompositionIntent) -> list[str]:
    """Suggest which roles to fill based on genre, leaving the LLM free to
    pick fewer or rearrange. This is GUIDANCE, not prescription."""
    genre = (intent.genre or "").lower()
    if genre == "ambient":
        return ["pad", "atmos"]
    if genre == "trap":
        return ["kick", "snare", "hat", "bass"]
    if genre == "drum and bass":
        return ["kick", "snare", "hat", "bass"]
    if genre in ("dub techno", "techno"):
        return ["kick", "hat", "bass", "pad"]
    if genre in ("house", "hip hop", "lo-fi"):
        return ["kick", "snare", "hat", "bass", "pad"]
    # Default: a balanced 4-piece
    return ["kick", "hat", "bass", "pad"]
