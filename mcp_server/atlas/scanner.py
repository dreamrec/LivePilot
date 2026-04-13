"""
Device Atlas scanner — transforms raw browser scan data into atlas entries.

Converts the flat {categories: {cat: [items]}} payload from scan_browser_deep
into normalised device dicts ready for enrichment and querying.
"""

from __future__ import annotations

import re
from typing import Any


# ── ID generation ────────────────────────────────────────────────────────────

def make_device_id(name: str, prefix: str = "") -> str:
    """Convert a human-readable device name to a snake_case identifier.

    >>> make_device_id("EQ Eight")
    'eq_eight'
    >>> make_device_id("Model D", prefix="auv3_moog")
    'auv3_moog_model_d'
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    if prefix:
        prefix_slug = re.sub(r"[^a-zA-Z0-9]+", "_", prefix).strip("_").lower()
        return f"{prefix_slug}_{slug}"
    return slug


# ── Category / subcategory mapping ───────────────────────────────────────────

_CATEGORY_MAP: dict[str, str] = {
    "instruments": "instruments",
    "audio_effects": "audio_effects",
    "midi_effects": "midi_effects",
    "drums": "drum_kits",
    "max_for_live": "max_for_live",
    "plugins": "plugins",
    "sounds": "sounds",
}

_INSTRUMENT_SUBCATEGORIES: dict[str, str] = {
    # Synths
    "analog": "synths",
    "wavetable": "synths",
    "operator": "synths",
    "drift": "synths",
    "meld": "synths",
    "emit": "synths",
    "poli": "synths",
    "tree_tone": "synths",
    "vector_fm": "synths",
    "vector_grain": "synths",
    "bass": "synths",
    # Physical modelling
    "collision": "physical_modeling",
    "tension": "physical_modeling",
    "electric": "physical_modeling",
    # Samplers
    "simpler": "samplers",
    "sampler": "samplers",
    # Drums
    "drum_rack": "drums",
    "drum_sampler": "drums",
    "impulse": "drums",
    # Racks
    "instrument_rack": "racks",
    # Routing
    "external_instrument": "routing",
    # Granular
    "granulator_iii": "granular",
}

_AUDIO_EFFECT_SUBCATEGORIES: dict[str, str] = {
    # Dynamics
    "compressor": "dynamics",
    "glue_compressor": "dynamics",
    "limiter": "dynamics",
    "color_limiter": "dynamics",
    "multiband_dynamics": "dynamics",
    "gate": "dynamics",
    "drum_buss": "dynamics",
    "re_enveloper": "dynamics",
    # EQ
    "eq_eight": "eq",
    "eq_three": "eq",
    "channel_eq": "eq",
    # Filter
    "auto_filter": "filter",
    "spectral_resonator": "filter",
    # Delay
    "delay": "delay",
    "echo": "delay",
    "grain_delay": "delay",
    "filter_delay": "delay",
    "gated_delay": "delay",
    "vector_delay": "delay",
    "beat_repeat": "delay",
    "spectral_time": "delay",
    "align_delay": "delay",
    # Reverb
    "reverb": "reverb",
    "hybrid_reverb": "reverb",
    "convolution_reverb": "reverb",
    "convolution_reverb_pro": "reverb",
    # Distortion
    "saturator": "distortion",
    "overdrive": "distortion",
    "pedal": "distortion",
    "roar": "distortion",
    "dynamic_tube": "distortion",
    "erosion": "distortion",
    "redux": "distortion",
    "vinyl_distortion": "distortion",
    "amp": "distortion",
    "cabinet": "distortion",
    # Modulation
    "chorus_ensemble": "modulation",
    "phaser_flanger": "modulation",
    "shifter": "modulation",
    "auto_pan_tremolo": "modulation",
    "auto_shift": "modulation",
    "shaper": "modulation",
    "lfo": "modulation",
    "envelope_follower": "modulation",
    "vector_map": "modulation",
    # Utility
    "utility": "utility",
    "spectrum": "utility",
    "tuner": "utility",
    "variations": "utility",
    "prearranger": "utility",
    # Spatial
    "surround_panner": "spatial",
    # Performance
    "looper": "performance",
    "arrangement_looper": "performance",
    "performer": "performance",
    # Spectral
    "spectral_blur": "spectral",
    # Pitch
    "pitch_hack": "pitch",
    "pitchloop89": "pitch",
    # Physical modelling
    "corpus": "physical_modeling",
    "resonators": "physical_modeling",
    # Special
    "vocoder": "special",
    # Racks
    "audio_effect_rack": "racks",
    # Routing
    "external_audio_effect": "routing",
}


def _classify_subcategory(device_id: str, category: str) -> str:
    """Return the subcategory for a device based on its id and category."""
    if category == "instruments":
        return _INSTRUMENT_SUBCATEGORIES.get(device_id, "other")
    if category == "audio_effects":
        return _AUDIO_EFFECT_SUBCATEGORIES.get(device_id, "other")
    return "other"


# ── Empty device template ────────────────────────────────────────────────────

def _empty_device(
    device_id: str,
    name: str,
    uri: str | None,
    category: str,
    subcategory: str,
    source: str,
) -> dict[str, Any]:
    """Return a skeleton device dict with all atlas fields set to defaults."""
    return {
        "id": device_id,
        "name": name,
        "uri": uri,
        "category": category,
        "subcategory": subcategory,
        "source": source,
        "enriched": False,
        "character_tags": [],
        "use_cases": [],
        "genre_affinity": {"primary": [], "secondary": []},
        "self_contained": True,
        "key_parameters": [],
        "pairs_well_with": [],
        "starter_recipes": [],
        "gotchas": [],
        "health_flags": [],
    }


# ── Normaliser ───────────────────────────────────────────────────────────────

def normalize_scan_results(raw_scan: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert raw scan_browser_deep output to a flat list of device dicts.

    Parameters
    ----------
    raw_scan : dict
        ``{"categories": {cat_name: [{"name", "uri", "is_loadable"}, ...], ...}}``

    Returns
    -------
    list[dict]
        Deduplicated device entries with all atlas fields initialised.
    """
    categories_data = raw_scan.get("categories", {})
    seen_uris: set[str] = set()
    devices: list[dict[str, Any]] = []

    for raw_cat, items in categories_data.items():
        category = _CATEGORY_MAP.get(raw_cat, raw_cat)
        source = "native" if raw_cat in _CATEGORY_MAP else raw_cat

        for item in items:
            name = item.get("name", "")
            uri = item.get("uri")

            # Deduplicate by URI when available
            if uri and uri in seen_uris:
                continue
            if uri:
                seen_uris.add(uri)

            device_id = make_device_id(name)
            subcategory = _classify_subcategory(device_id, category)
            devices.append(
                _empty_device(device_id, name, uri, category, subcategory, source)
            )

    return devices
