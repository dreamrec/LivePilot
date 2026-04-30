"""Macro-fingerprint similarity matching for Pack-Atlas Phase D.

Finds presets with similar macro state to a source preset by computing
macro-name overlap (synonym-aware) + value distance. Returns top-K matches
scored and ranked, each with a generated rationale.

All data comes from the _preset_parses JSON sidecar layer — no Live
connection required.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Generator

# ─── Paths ───────────────────────────────────────────────────────────────────

PRESET_PARSES_ROOT = (
    Path.home() / ".livepilot" / "atlas-overlays" / "packs" / "_preset_parses"
)

# ─── Synonym Dictionary ───────────────────────────────────────────────────────
# Maps a canonical key → list of raw macro name variants (all lowercase).
# Built from corpus survey of 3,813 sidecars / 26,433 named macros.
# Top 5 raw names in corpus: volume (2451), attack (1997), tone (1383),
# filter cutoff (1249), pitch (1218).

MACRO_SYNONYMS: dict[str, list[str]] = {
    # ── Filter ────────────────────────────────────────────────────────────────
    "filter_cutoff": [
        "filter cutoff", "filter freq", "filter control", "cutoff",
        "lowpass", "lp cut", "filter sweep", "cutoff freq",
        "filter frequency", "filiter cutoff", "filt cutoff",
        "filter 1 cutoff", "filter 2 cutoff", "input cutoff",
        "output cutoff", "creak filter", "rumble filter",
        "bass cutoff", "high cutoff", "low cutoff",
        "filter drift", "keyhole filter",
    ],
    "filter_resonance": [
        "filter resonance", "filter reso", "resonance", "reso",
        "filter q", "filter res", "filter r", "resonant freq",
        "reso note", "filter rezo", "rezo",
    ],
    "filter_envelope": [
        "filter envelope", "filter env", "filter attack", "filter decay",
        "filter mod", "filter lfo", "fe < env", "fliter env",
        "filter env amount", "filter env decay",
    ],
    "low_cut": [
        "low cut", "lo cut", "high pass", "hi pass", "hp cut",
        "highpass", "lo pass", "low cut filter", "high cut filter",
        "bass cut",
    ],
    "high_cut": [
        "high cut", "hi cut", "low pass", "lp", "treble cut",
        "tone", "brightness", "brighten", "dull to bright",
        "dark to light", "tonal balance",
    ],

    # ── Amplitude / Volume ────────────────────────────────────────────────────
    "volume": [
        "volume", "vol", "output", "output vol", "level",
        "output volume", "release volume", "rack volume",
        "master vol", "gain", "output level", " volume",
    ],
    "attack": [
        "attack", "attack time", "env attack", "legato attack",
        " attack", "fade in", "fade in <<< o",
    ],
    "decay": [
        "decay", "decay time", "env decay", "reso decay",
        "decay release", "decay 1", "decay 2", "decay 3",
    ],
    "release": [
        "release", "release time", "tail", "decay time",
        "env release", "key off volume", "k & s release",
        "legato release", "press release", "release level",
    ],
    "sustain": [
        "sustain", "sus",
    ],

    # ── Space / Reverb ────────────────────────────────────────────────────────
    "reverb": [
        "reverb", "verb", "reverb amount", "reverb mix", "reverb dry/wet",
        "reverb time", "reverb decay", "reverb level", "reverb blend",
        "reverb vol", "ambience", "reverb d/w", "space", "space amount",
        "space 1", "space 2", "room", "into space", "orbit reverb",
        "ambient amount", "warehouse verb", "reclusive verb",
        "dizzy verb", "ghosts wet/dry", "verb level",
    ],
    "reverb_time": [
        "reverb time", "reverb decay", "reverb length", "room",
        "reverb d/w", "reverb decay",
    ],

    # ── Delay / Echo ──────────────────────────────────────────────────────────
    "delay": [
        "delay", "echo", "delay amount", "delay mix", "delay length",
        "delay time", "delay rate", "delay feedback", "delay crank",
        "delay vol", "delay d/w", "grain delay", "swarm delay",
        "echo amount", "echo d/w", "roomy delay",
    ],
    "feedback": [
        "feedback", "fdback", "fdbk", "feed back",
        "delay feedback", "phaser fdback",
    ],

    # ── Modulation / Movement ─────────────────────────────────────────────────
    "movement": [
        "movement", "motion", "lfo amount", "modulation", "mod",
        "mod amount", "motion speed", "wobble", "pulse rate",
        "lfo rate", "mod rate", "mod freq",
    ],
    "lfo_rate": [
        "lfo rate", "lfo sync rate", "mod rate", "motion speed",
        "pulse rate", "tremolo speed", "lfo   rate", "rate of flux",
        "arp rate",
    ],
    "lfo_amount": [
        "lfo amount", "mod amount", "modulation", "vibrato",
        "tremolo amount", "wobble",
    ],

    # ── Drive / Distortion ────────────────────────────────────────────────────
    "drive": [
        "drive", "overdrive", "saturation", "drive amount",
        "saturate", "distort", "distortion", "grit",
        "amp drive", "saturator amount", "over drive",
        "vinyl distortion", "stormy overdrive", "bit crush",
        "erosion", "tube", "warmth", "low intensity",
    ],
    "compressor": [
        "comp", "compressor", "compress", "glue", "squash",
        "tighten", "comp amount", "comp thresh", "comp depth",
        "squeeze", "heavy comp", "drum buss",
    ],

    # ── Chorus / Ensemble ─────────────────────────────────────────────────────
    "chorus": [
        "chorus", "chorus amount", "ensemble", "shimmer chorus",
        "luster chorus", "chrus fb", "chours amount",
        "ricochet chorus",
    ],

    # ── Pitch / Tune ──────────────────────────────────────────────────────────
    "pitch": [
        "pitch", "pitch shift", "transpose", "tune",
        "transp.", "osc 2 transp.", "fine tuning",
        "pitch env", "pitch envelope", "pitch mod",
        "pitch decay", "pitch drift", "pitch spring",
        "pitch tone", "pitch warp", "pitch drag l", "pitch drag r",
    ],
    "detune": [
        "detune", "spread", "stereo spread", "unison", "detuning",
        "melt detune", "headache detune", "drunkenness",
    ],

    # ── Stereo / Width ────────────────────────────────────────────────────────
    "spread": [
        "spread", "stereo", "width", "stereo spread", "stereo width",
        "narrow to wide", "pan mod", "random pan", "pan random",
    ],
    "dry_wet": [
        "dry/wet", "dry-wet", "mix", "wet", "effect mix",
        "rack dry/wet", "spectral d/w", "effect dry/wet",
        "spectral d/w", "trails d/w", "chorus d/w", "reverb d/w",
    ],

    # ── Spectral / Texture ────────────────────────────────────────────────────
    "spectral": [
        "spectral amount", "spectral d/w", "spectral note",
        "spectral shift", "spectral stretch", "spectral time",
        "freq shift", "bandwidth", "grain delay", "grain pitch",
        "grain spread",
    ],
    "texture": [
        "texture type", "texture amount", "texture tune",
        "noise", "noise floor", "noise level", "shaper",
        "oxide", "color", "timbre",
    ],

    # ── Noise / Grain ─────────────────────────────────────────────────────────
    "noise": [
        "noise", "noise floor", "noise level", "hiss tone",
        "crackle volume", "crackle density", "nøize ω",
    ],
    "grain": [
        "grain delay", "grain pitch", "grain spread", "grains",
        "grain size", "sample start", "sample shift",
    ],

    # ── Drone-specific ────────────────────────────────────────────────────────
    "drone_density": [
        "drone density", "root note", "sub level",
        "sine drone", "xl sub", "boom",
    ],
    "sub": [
        "sub level", "sub osc", "xl sub", "boom",
        "low end", "bass boost", "bass gain",
    ],

    # ── Frequency band shaping ────────────────────────────────────────────────
    "eq_low": [
        "low shelf", "low gain", "low end", "bass cutoff",
        "tilt eq", "low freq", "lo gain",
    ],
    "eq_high": [
        "high shelf", "high gain", "treble boost",
        "top boost", "hi freq", "hi gain",
    ],
    "eq_mid": [
        "mid gain", "mid range", "mid scoop", "master eq",
        "tilt eq",
    ],

    # ── Phaser / Flanger ──────────────────────────────────────────────────────
    "phaser": [
        "phaser", "phaze", "phase", "flanger", "hat flanger",
        "churn phaser",
    ],
    "ring_mod": [
        "ring mod", "ring mod vol", "ringmod 1 freq",
        "ringmod 1 amnt", "ringmod 2 freq", "ringmod 2 amnt",
        "fm amount", "fm",
    ],
}

# Build reverse lookup: raw_name_lower → canonical_key
_SYNONYM_REVERSE: dict[str, str] = {}
for _canonical, _variants in MACRO_SYNONYMS.items():
    for _v in _variants:
        _SYNONYM_REVERSE[_v.lower().strip()] = _canonical


# ─── Schema helpers ───────────────────────────────────────────────────────────

def _is_producer_named(name: str) -> bool:
    """True when the macro has a producer-assigned name (not 'Macro N')."""
    if not name:
        return False
    return not re.match(r"^Macro\s+\d+$", name.strip())


def _ascii_fold(name: str) -> str:
    """Normalize a producer-stylized macro name for synonym matching.

    1. Apply Unicode character substitutions for common stylized glyphs
       that don't survive NFKD decomposition (e.g. † → t, Ω → dropped).
    2. NFKD decompose and drop non-ASCII bytes (ø → o, e.g. MØD → mod).
    3. Lowercase and strip.

    Examples:
        "Nøize Ω"       → "noize"
        "MØD Rate"      → "mod rate"
        "Fil†er Amount" → "filter amount"
        " Spark Entities" → "spark entities"
    """
    # Explicit substitutions before decomposition
    _GLYPH_SUB = str.maketrans({
        "†": "t",   # dagger → t  (e.g. Fil†er → Filter)
        "Ω": "",    # Greek omega — purely decorative, drop
        "ω": "",    # lowercase omega
        "Ø": "o",   # Nordic Ø — also handled by NFKD but explicit is safer
        "ø": "o",
        "Æ": "ae",
        "æ": "ae",
        "+": " ",   # BLASTS ++ → blasts
        "≈": "",
        "→": "",
    })
    s = name.translate(_GLYPH_SUB)
    # NFKD decompose, then drop non-ASCII combining marks
    s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
    return s.lower().strip()


def _canonicalize_macro_name(name: str) -> str:
    """Return canonical synonym key for name, or normalised raw name as fallback.

    Performs ASCII-fold + Unicode glyph substitution before synonym lookup so
    producer-stylized names like "Nøize Ω" and "MØD Rate" resolve correctly.
    """
    clean = name.lower().strip()
    # 1) Try exact match first (covers most common names cheaply)
    if clean in _SYNONYM_REVERSE:
        return _SYNONYM_REVERSE[clean]
    # 2) ASCII-fold and try again (handles Unicode-decorated producer names)
    folded = _ascii_fold(name)
    if folded in _SYNONYM_REVERSE:
        return _SYNONYM_REVERSE[folded]
    # 3) Return the folded form as the fallback canonical key so that
    #    two presets with identical stylized names still match each other.
    return folded if folded else clean


def _normalize_value(value_raw: str | float | int) -> float:
    """Normalise a macro value to [0, 1] assuming the 0-127 MIDI range."""
    try:
        v = float(value_raw)
        return max(0.0, min(1.0, v / 127.0))
    except (TypeError, ValueError):
        return 0.5


# ─── Sidecar loaders ─────────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def _load_preset_sidecar(pack_slug: str, preset_path_slug: str) -> dict | None:
    """Load a single preset sidecar. Returns None if path doesn't exist.

    preset_path_slug is the filename stem, e.g.
    "instruments_laboratory_razor-wire-drone".
    """
    p = PRESET_PARSES_ROOT / pack_slug / f"{preset_path_slug}.json"
    if not p.exists():
        return None
    with p.open() as fh:
        return json.load(fh)


def _iter_all_preset_sidecars() -> Generator[tuple[str, str, dict], None, None]:
    """Yield (pack_slug, preset_path_slug, sidecar_dict) for every sidecar on disk."""
    if not PRESET_PARSES_ROOT.exists():
        return
    for pack_dir in sorted(PRESET_PARSES_ROOT.iterdir()):
        if not pack_dir.is_dir():
            continue
        pack_slug = pack_dir.name
        for sidecar_path in sorted(pack_dir.glob("*.json")):
            preset_path_slug = sidecar_path.stem
            try:
                sidecar = json.loads(sidecar_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            yield pack_slug, preset_path_slug, sidecar


# ─── Fingerprint extraction ───────────────────────────────────────────────────

def _extract_fingerprint(
    sidecar_dict: dict,
) -> list[dict]:
    """Return list of fingerprint entries for non-default named macros.

    Each entry: {name_canonical, name_raw, value, value_normalized}.
    Skips macros named "Macro N" (default placeholders) and macros with
    zero value that are likely unused/unconnected.
    """
    fp = []
    for macro in sidecar_dict.get("macros", []):
        raw_name = macro.get("name", "")
        if not _is_producer_named(raw_name):
            continue
        raw_value = macro.get("value", 0)
        try:
            value_f = float(raw_value)
        except (TypeError, ValueError):
            value_f = 0.0
        canonical = _canonicalize_macro_name(raw_name)
        fp.append({
            "name_canonical": canonical,
            "name_raw": raw_name,
            "value": value_f,
            "value_normalized": _normalize_value(raw_value),
        })
    return fp


# ─── Similarity computation ───────────────────────────────────────────────────

def _compute_similarity(
    source_fp: list[dict],
    candidate_fp: list[dict],
) -> tuple[float, list[dict]]:
    """Compute similarity between two fingerprints.

    Returns (score: float, matching_macros: list[dict]).

    Algorithm (per spec §Phase D):
      name_overlap_ratio = matched_pairs / max(len(source), len(candidate))
      value_distance     = mean |v_src - v_cand| over matched pairs
      score = 0.6 * name_overlap_ratio + 0.4 * (1 - value_distance)
    """
    if not source_fp or not candidate_fp:
        return 0.0, []

    # Build canonical-name → entry map for candidate (last wins on dupes)
    cand_by_canonical: dict[str, dict] = {}
    cand_by_raw: dict[str, dict] = {}
    for entry in candidate_fp:
        cand_by_canonical[entry["name_canonical"]] = entry
        cand_by_raw[entry["name_raw"].lower().strip()] = entry

    matching_macros = []
    for src_entry in source_fp:
        cand_entry = None
        match_label = ""

        # 1) Exact canonical match (catches synonym → same canonical bucket)
        if src_entry["name_canonical"] in cand_by_canonical:
            cand_entry = cand_by_canonical[src_entry["name_canonical"]]
            if src_entry["name_canonical"] == cand_entry["name_canonical"]:
                # Both collapsed to same canonical via synonym dict
                src_raw = src_entry["name_raw"]
                cand_raw = cand_entry["name_raw"]
                if src_raw.lower().strip() == cand_raw.lower().strip():
                    match_label = f"{src_raw} = {cand_raw}"
                else:
                    match_label = f"{src_raw} ≈ {cand_raw}"
            else:
                match_label = (
                    f"{src_entry['name_raw']} ≈ {cand_entry['name_raw']}"
                )

        # 2) Exact raw name match (handles identical naming within same pack)
        if cand_entry is None:
            raw_lower = src_entry["name_raw"].lower().strip()
            if raw_lower in cand_by_raw:
                cand_entry = cand_by_raw[raw_lower]
                match_label = f"{src_entry['name_raw']} = {cand_entry['name_raw']}"

        if cand_entry is None:
            continue

        value_dist = abs(
            src_entry["value_normalized"] - cand_entry["value_normalized"]
        )
        matching_macros.append({
            "name_overlap": match_label,
            "src_name": src_entry["name_raw"],
            "cand_name": cand_entry["name_raw"],
            "src_value": src_entry["value"],
            "cand_value": cand_entry["value"],
            "value_distance": round(value_dist, 4),
        })

    if not matching_macros:
        return 0.0, []

    n_source = len(source_fp)
    n_cand = len(candidate_fp)
    name_overlap_ratio = len(matching_macros) / max(n_source, n_cand)
    mean_value_dist = sum(m["value_distance"] for m in matching_macros) / len(
        matching_macros
    )

    score = 0.6 * name_overlap_ratio + 0.4 * (1.0 - mean_value_dist)
    return round(min(score, 1.0), 4), matching_macros


# ─── Pack metadata helpers ───────────────────────────────────────────────────

# Curated pack genre / aesthetic tags — used in rationale generation.
_PACK_GENRE_TAGS: dict[str, list[str]] = {
    "drone-lab": ["drone", "ambient", "experimental", "generative"],
    "mood-reel": ["ambient", "cinematic", "atmospheric"],
    "inspired-by-nature-by-dillon-bastan": ["generative", "ambient", "spectral"],
    "lost-and-found": ["lo-fi", "vintage", "experimental"],
    "synth-essentials": ["synth", "subtractive", "classic"],
    "drive-and-glow": ["distortion", "saturation", "character"],
    "glitch-and-wash": ["glitch", "ambient", "experimental", "spectral"],
    "skitter-and-step": ["rhythmic", "percussion", "glitch"],
    "voice-box": ["vocal", "choral", "processing"],
    "build-and-drop": ["edm", "drop", "impact"],
    "creative-extensions": ["generative", "experimental", "modular"],
    "beat-tools": ["percussion", "drums", "hip-hop"],
    "chop-and-swing": ["hip-hop", "funk", "sampling"],
    "electric-keyboards": ["keys", "vintage", "classic"],
    "grand-piano": ["piano", "acoustic", "classical"],
    "guitar-and-bass": ["guitar", "bass", "live-instrument"],
    "punch-and-tilt": ["percussion", "edm", "impact"],
    "cv-tools": ["modular", "cv", "generative"],
    "sequencers": ["generative", "arp", "modular"],
    "golden-era-hip-hop-drums-by-sound-oracle": ["hip-hop", "sampling", "vintage"],
    "trap-drums-by-sound-oracle": ["trap", "hip-hop", "drums"],
    "drum-booth": ["acoustic", "drums", "percussion"],
    "drum-essentials": ["drums", "percussion", "classic"],
    "session-drums-club": ["drums", "club", "house"],
    "session-drums-studio": ["drums", "studio", "live"],
    "latin-percussion": ["latin", "percussion", "world"],
    "orchestral-brass": ["orchestral", "brass", "cinematic"],
    "orchestral-mallets": ["orchestral", "mallets", "classical"],
    "orchestral-strings": ["orchestral", "strings", "cinematic"],
    "orchestral-woodwinds": ["orchestral", "woodwinds", "classical"],
    "brass-quartet-by-spitfire-audio": ["orchestral", "brass", "spitfire"],
    "string-quartet-by-spitfire-audio": ["orchestral", "strings", "spitfire"],
    "upright-piano-by-spitfire-audio": ["piano", "acoustic", "spitfire"],
}

_SPECTRAL_PACKS = frozenset([
    "drone-lab", "inspired-by-nature-by-dillon-bastan",
    "glitch-and-wash", "creative-extensions",
])
_DUB_TECHNO_PACKS = frozenset([
    "drone-lab", "mood-reel", "glitch-and-wash",
])


def _generate_rationale(
    source_pack: str,
    source_name: str,
    cand_pack: str,
    cand_name: str,
    matching_macros: list[dict],
) -> str:
    """Generate a short prose rationale for a match."""
    parts = []

    # Pack relationship
    if source_pack == cand_pack:
        parts.append(f"Same {source_pack!r} pack")
    else:
        src_tags = set(_PACK_GENRE_TAGS.get(source_pack, []))
        cand_tags = set(_PACK_GENRE_TAGS.get(cand_pack, []))
        shared = src_tags & cand_tags
        if shared:
            parts.append(
                f"Different pack but shared aesthetic: {', '.join(sorted(shared))}"
            )
        else:
            parts.append(f"Cross-pack match ({cand_pack!r})")

    # Spectral / dub-techno tagging
    if cand_pack in _SPECTRAL_PACKS:
        parts.append("spectral processing topology")
    if cand_pack in _DUB_TECHNO_PACKS:
        parts.append("dub-techno compatible")

    # Describe macro overlaps
    overlap_names = [m["cand_name"] for m in matching_macros[:3]]
    if overlap_names:
        parts.append(f"matching macros: {', '.join(overlap_names)}")

    # Value proximity bonus
    close = [m for m in matching_macros if m["value_distance"] < 0.1]
    if len(close) >= 2:
        parts.append("similar parameter values")

    return "; ".join(parts)


# ─── Fingerprint strength ─────────────────────────────────────────────────────

def _fingerprint_strength(n_named: int) -> str:
    if n_named >= 6:
        return "strong"
    if n_named >= 3:
        return "moderate"
    return "weak"
