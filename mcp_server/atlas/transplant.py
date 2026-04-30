"""Pack-Atlas Phase C — Transplant Engine.

Adapt a structure (demo track set, preset chain, workflow recipe) from one
musical context to another.  Returns a structured translation plan + prose
reasoning artifact.  All data comes from the local JSON sidecar layer —
no Live connection required.

Real sidecar schema (discovered 2026-04-27):
  Demo sidecars  (~/.livepilot/atlas-overlays/packs/_demo_parses/<slug>.json):
    {file, name, bpm, scale{root_note:str, name:str},
     tracks[{name, type, id, device_count, devices[{class, user_name, params,
                                                      macros[{index, value}]}],
             routing}],
     scenes[...]}
    NOTE: demo-track macro entries have {index, value} ONLY — no "name" field.
    Macro names are in _preset_parses sidecars, not demo sidecars.

  Preset sidecars (~/.livepilot/atlas-overlays/packs/_preset_parses/<pack>/<slug>.json):
    {file, name, preset_type, rack_class,
     macros[{index, value:str, name:str}], chains, device_summary, branch_counts}
    NOTE: "name" in macros is the producer-assigned macro label.

File naming: demo sidecar files use hyphens in pack and demo slugs,
  e.g. drone-lab__earth.json.  The spec uses underscores in entity_id strings
  (drone_lab__earth) — this module translates automatically.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

# ─── Paths ────────────────────────────────────────────────────────────────────

DEMO_PARSES_ROOT = (
    Path.home() / ".livepilot" / "atlas-overlays" / "packs" / "_demo_parses"
)
PRESET_PARSES_ROOT = (
    Path.home() / ".livepilot" / "atlas-overlays" / "packs" / "_preset_parses"
)

# ─── Mode-degree tables ───────────────────────────────────────────────────────
# Semitone intervals from root for each mode.

_MODE_DEGREES: dict[str, list[int]] = {
    "major":    [0, 2, 4, 5, 7, 9, 11],
    "minor":    [0, 2, 3, 5, 7, 8, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "dorian":   [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "lydian":   [0, 2, 4, 6, 7, 9, 11],
    "locrian":  [0, 1, 3, 5, 6, 8, 10],
    # Aliases
    "ionian":   [0, 2, 4, 5, 7, 9, 11],
    "aeolian":  [0, 2, 3, 5, 7, 8, 10],
}

# ─── Aesthetic-replace rules ──────────────────────────────────────────────────
# Tuple: (source_device_keywords, target_aesthetic_keywords, replace_action)
# Evaluated in order; first match wins.

_REPLACE_RULES: list[tuple[list[str], list[str], dict]] = [
    # Vinyl Distortion + clean/cinematic target → Saturator (gentle warmth)
    (
        ["vinyl distortion", "vinyl"],
        ["clean", "cinematic", "mood-reel", "sublime", "romantic", "orchestral"],
        {
            "action": "replace",
            "remove_device": "Vinyl Distortion",
            "add_device": "Saturator",
            "parameters": [{"name": "Drive", "value": 0.4}, {"name": "Dry/Wet", "value": 0.6}],
            "rationale_fragment": "Vinyl Distortion conflicts with clean/cinematic aesthetic — replaced with Saturator (drive 0.4) for subtle harmonic warmth.",
        },
    ),
    # Erosion + clean/cinematic target → remove
    (
        ["erosion"],
        ["clean", "cinematic", "mood-reel", "sublime", "romantic"],
        {
            "action": "remove",
            "remove_device": "Erosion",
            "add_device": None,
            "parameters": [],
            "rationale_fragment": "Erosion (digital degradation) removed — incompatible with clean/cinematic aesthetic.",
        },
    ),
    # Redux + clean target → remove
    (
        ["redux"],
        ["clean", "cinematic", "mood-reel", "sublime", "romantic"],
        {
            "action": "remove",
            "remove_device": "Redux",
            "add_device": None,
            "parameters": [],
            "rationale_fragment": "Redux (bit-crusher) removed — incompatible with clean/cinematic aesthetic.",
        },
    ),
    # Saturator high-drive + lo-fi/grit target → keep + add Erosion
    (
        ["saturator"],
        ["lo-fi", "grit", "tape", "dusty", "vintage"],
        {
            "action": "enhance",
            "remove_device": None,
            "add_device": "Erosion",
            "parameters": [{"name": "Amount", "value": 0.2}, {"name": "Dry/Wet", "value": 0.35}],
            "rationale_fragment": "Saturator retained; Erosion added for tape-noise texture consistent with lo-fi/vintage aesthetic.",
        },
    ),
    # Convolution Reverb → short Reverb when mood is intimate/dry
    (
        ["convolution reverb"],
        ["dry", "intimate", "mono", "direct"],
        {
            "action": "replace",
            "remove_device": "Convolution Reverb",
            "add_device": "Reverb",
            "parameters": [{"name": "Decay Time", "value": 0.8}, {"name": "Dry/Wet", "value": 0.25}],
            "rationale_fragment": "Convolution Reverb shortened — intimate/dry aesthetic calls for tight reflections.",
        },
    ),
]

# ─── Producer vocabulary anchors ─────────────────────────────────────────────
# Maps pack/aesthetic keywords to known producer vocabulary from
# livepilot-core/references/artist-vocabularies.md.

_PRODUCER_ANCHORS: dict[str, str] = {
    "drone-lab": "Drone Lab invites the Villalobos / Henke texture-first philosophy: "
                 "harmonic drones as rhythmic structures, macro-controlled spectral erosion "
                 "and recovery, patient evolution over silence.",
    "drone_lab": "Drone Lab invites the Villalobos / Henke texture-first philosophy: "
                 "harmonic drones as rhythmic structures, macro-controlled spectral erosion "
                 "and recovery, patient evolution over silence.",
    "mood-reel": "Mood Reel occupies the Arca / Mica Levi register: cinematic suspension, "
                 "lush stereo field, emotional restraint over grit.",
    "mood_reel": "Mood Reel occupies the Arca / Mica Levi register: cinematic suspension, "
                 "lush stereo field, emotional restraint over grit.",
    "inspired-by-nature": "Inspired by Nature channels Dillon Bastan's "
                          "generative-ecological aesthetic: physical-model resonance, "
                          "slow self-organizing change, biological unpredictability.",
    "inspired_by_nature": "Inspired by Nature channels Dillon Bastan's "
                          "generative-ecological aesthetic: physical-model resonance, "
                          "slow self-organizing change, biological unpredictability.",
    "tree_tone": "Tree Tone (Inspired by Nature) — generative physical-model oscillator; "
                 "reaches for Dillon Bastan's ecosystem aesthetic: filter branching "
                 "that reads as breath, tuning drift that reads as micro-weather.",
    "tree tone": "Tree Tone (Inspired by Nature) — generative physical-model oscillator; "
                 "reaches for Dillon Bastan's ecosystem aesthetic.",
    "henke":    "Robert Henke / Monolake: minimal dub-techno pulse with deep spectral field, "
                "granular erosion as composition, restraint as maximalism.",
    "monolake": "Monolake: minimal dub-techno pulse with deep spectral field.",
    "boc":      "Boards of Canada: chromatic degradation that reads as memory — "
                "cassette saturation, slowed-pitch warble, modal simplicity.",
    "boards of canada": "Boards of Canada: chromatic degradation that reads as memory.",
    "burial":   "Burial: urban desolation through UK garage rhythm displaced by one-tick, "
                "shredded vocal as texture, sidechain 'wobble' as structural element.",
    "arca":     "Arca: body-horror via pitch extremity, metallic percussion, "
                "surgical stereo placement.",
    "mica levi": "Mica Levi: sustained orchestral dread — slow-moving string harmonics, "
                 "unconventional intonation, silence as pressure.",
}

# BPM ratio sanity-clamp threshold
_BPM_RATIO_CLAMP = 2.0   # ratios outside [0.5, 2.0] trigger warning + conservative clamp
_BPM_RATIO_MIN = 0.5


# ─── Slug normalisation helpers ───────────────────────────────────────────────

def _entity_id_to_slug(entity_id: str) -> str:
    """Normalise an entity_id like 'drone_lab__earth' to 'drone-lab__earth'.

    The spec uses underscores; sidecar files use hyphens.  The convention is:
    - pack portion: underscores → hyphens
    - demo portion after '__': underscores → hyphens

    We replace underscores with hyphens unless the separator '__' is involved.
    Strategy: split on '__', hyphenate each part, rejoin with '__'.
    """
    parts = entity_id.split("__")
    return "__".join(p.replace("_", "-") for p in parts)


def _resolve_demo_slug(entity_id: str) -> Path | None:
    """Return the Path for a demo sidecar, handling underscore/hyphen variants.

    Tries in order:
      1. Direct entity_id as slug (e.g. 'drone-lab__earth')
      2. Hyphenated form of underscored entity_id
      3. Underscored form of hyphenated entity_id
    """
    if not DEMO_PARSES_ROOT.exists():
        return None
    candidates = [
        entity_id,
        _entity_id_to_slug(entity_id),
        entity_id.replace("-", "_"),
    ]
    for slug in candidates:
        p = DEMO_PARSES_ROOT / f"{slug}.json"
        if p.exists():
            return p
    return None


def _resolve_preset_slug(pack_slug: str, preset_path: str) -> tuple[str, str] | None:
    """Return (pack_slug, preset_file_stem) for a preset sidecar.

    Handles underscore/hyphen translation in both pack_slug and preset_path.
    """
    if not PRESET_PARSES_ROOT.exists():
        return None
    # Try pack_slug variants
    pack_candidates = [
        pack_slug,
        pack_slug.replace("_", "-"),
        pack_slug.replace("-", "_"),
    ]
    # Preset path may use / or _ separators
    preset_candidates = [
        preset_path,
        preset_path.replace("/", "_"),
        preset_path.replace("-", "_"),
        preset_path.replace("_", "-"),
    ]
    for p_pack in pack_candidates:
        pack_dir = PRESET_PARSES_ROOT / p_pack
        if not pack_dir.exists():
            continue
        for p_preset in preset_candidates:
            candidate = pack_dir / f"{p_preset}.json"
            if candidate.exists():
                return (p_pack, p_preset)
    return None


# ─── Sidecar loaders ─────────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def _load_demo_sidecar(entity_id: str) -> dict | None:
    """Load a demo sidecar by entity_id (handles slug translation).

    Cached per entity_id string.  Returns None if not found.
    """
    p = _resolve_demo_slug(entity_id)
    if p is None:
        return None
    with p.open() as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def _load_preset_sidecar_cached(pack_slug: str, preset_path_slug: str) -> dict | None:
    """Load a preset sidecar.  Wraps macro_fingerprint._load_preset_sidecar."""
    from .macro_fingerprint import _load_preset_sidecar
    return _load_preset_sidecar(pack_slug, preset_path_slug)


# ─── Source structure extraction ─────────────────────────────────────────────

def _walk_device_chain(devices: list[dict], depth: int = 0) -> list[str]:
    """Recursively walk a device chain, collecting class + user_name for each
    device including those nested inside rack chains.

    BUG-C#2 fix: previously only top-level rack class names ("InstrumentGroupDevice",
    "AudioEffectGroupDevice") landed in the inventory, so REPLACE rules that
    target inner-chain devices (Vinyl Distortion, Erosion, Redux — the canonical
    aesthetic-incompatibility cases) had nothing to match against.

    Now uses the v1.23.5 sidecar `chains` field (Schema A: nested) to surface
    every inner device class up to a sane recursion depth.
    """
    inventory: list[str] = []
    if depth > 8:  # defensive cap; real corpus never exceeds 4
        return inventory
    for dev in devices or []:
        class_name = dev.get("class", "") or ""
        user_name = dev.get("user_name") or ""
        if class_name:
            inventory.append(class_name)
        if user_name:
            inventory.append(user_name)
        for chain in dev.get("chains") or []:
            inventory.extend(
                _walk_device_chain(chain.get("devices") or [], depth + 1)
            )
    return inventory


def _extract_source_structure(sidecar: dict) -> dict:
    """Extract musical structure from a demo sidecar.

    Returns:
      {
        bpm: float,
        scale: {root_note: int, name: str},
        tracks_summary: list[str],        # track names
        device_inventory: list[str],      # all device class names + user_names,
                                          #   recursive across rack chains
        track_count: int,
        scene_count: int,
        return_tracks: list[str],
      }
    """
    bpm = float(sidecar.get("bpm") or 120.0)

    scale_raw = sidecar.get("scale") or {}
    try:
        root_note = int(str(scale_raw.get("root_note", "0")))
    except (ValueError, TypeError):
        root_note = 0
    scale_name = scale_raw.get("name", "Major") or "Major"

    tracks = sidecar.get("tracks") or []
    tracks_summary = []
    device_inventory: list[str] = []
    return_tracks = []

    for track in tracks:
        t_name = track.get("name", "")
        t_type = track.get("type", "")
        if t_type in ("ReturnTrack",):
            return_tracks.append(t_name)
        tracks_summary.append(t_name)
        device_inventory.extend(_walk_device_chain(track.get("devices") or []))

    scenes = sidecar.get("scenes") or []

    return {
        "bpm": bpm,
        "scale": {"root_note": root_note, "name": scale_name},
        "tracks_summary": tracks_summary,
        "device_inventory": device_inventory,
        "track_count": len(tracks),
        "scene_count": len(scenes),
        "return_tracks": return_tracks,
    }


# ─── Scale transposition helpers ─────────────────────────────────────────────

def _remap_pitch_class(
    pitch: int,
    src_root: int,
    src_mode: str,
    tgt_root: int,
    tgt_mode: str,
) -> int:
    """Remap a MIDI pitch from source scale to target scale.

    Algorithm:
      1. Compute pitch-class relative to src_root
      2. Find nearest degree in src_mode scale
      3. Map that degree index to corresponding degree in tgt_mode
      4. Shift by (tgt_root - src_root)
    Returns the remapped MIDI pitch.
    """
    src_degrees = _MODE_DEGREES.get(src_mode.lower(), _MODE_DEGREES["major"])
    tgt_degrees = _MODE_DEGREES.get(tgt_mode.lower(), _MODE_DEGREES["minor"])

    # Pitch class relative to source root (0-11)
    rel_pc = (pitch - src_root) % 12
    octave_offset = (pitch - src_root) // 12

    # Find nearest degree in source mode
    best_degree_idx = 0
    best_dist = 12
    for i, deg in enumerate(src_degrees):
        dist = min(abs(rel_pc - deg), 12 - abs(rel_pc - deg))
        if dist < best_dist:
            best_dist = dist
            best_degree_idx = i

    # Map to target mode degree (wrap if target mode has fewer degrees)
    tgt_degree_idx = min(best_degree_idx, len(tgt_degrees) - 1)
    tgt_pc = tgt_degrees[tgt_degree_idx]

    # Reconstruct absolute MIDI pitch
    new_pitch = tgt_root + octave_offset * 12 + tgt_pc
    return new_pitch


# ─── Aesthetic-replace evaluation ────────────────────────────────────────────

def _evaluate_replace_rules(
    device_inventory: list[str],
    target_aesthetic: str,
) -> list[dict]:
    """Return list of replace decisions for aesthetic-incompatible devices.

    Scans the _REPLACE_RULES table against the device_inventory and
    target_aesthetic string.
    """
    aesthetic_lower = target_aesthetic.lower()
    inventory_lower = [d.lower() for d in device_inventory]
    decisions = []
    triggered_removals: set[str] = set()

    for src_keywords, tgt_keywords, action_dict in _REPLACE_RULES:
        # Check if any source device keyword matches inventory
        device_match = any(
            kw in inv_item
            for kw in src_keywords
            for inv_item in inventory_lower
        )
        if not device_match:
            continue
        # Check if any target aesthetic keyword matches
        aesthetic_match = any(kw in aesthetic_lower for kw in tgt_keywords)
        if not aesthetic_match:
            continue
        # Deduplicate — don't emit two rules removing the same device
        remove_key = action_dict.get("remove_device") or ""
        if remove_key and remove_key.lower() in triggered_removals:
            continue
        if remove_key:
            triggered_removals.add(remove_key.lower())
        decisions.append(dict(action_dict))

    return decisions


# ─── Translation decisions ────────────────────────────────────────────────────

def _compute_translation_decisions(
    source_struct: dict,
    target_bpm: float | None,
    target_scale_root: int | None,
    target_scale_name: str,
    target_aesthetic: str,
    preserve_pitch_intervals: bool,
    preserve_macro_ratios: bool,
    source_sidecar: dict | None = None,
) -> tuple[list[dict], list[str]]:
    """Generate per-element translation decisions.

    Returns (decisions_list, warnings_list).

    Decision types:
      PRESERVE — keep as-is (pitch intervals, macro ratios)
      SCALE    — scale rhythmic density by BPM ratio
      REMAP    — scale-locked notes via pitch-class-set transform
      REPLACE  — swap aesthetic-incompatible device
    """
    decisions: list[dict] = []
    warnings: list[str] = []

    src_bpm = source_struct["bpm"]
    src_scale = source_struct["scale"]
    src_root = src_scale["root_note"]   # int
    src_mode = src_scale["name"]

    tgt_root = target_scale_root if target_scale_root is not None else src_root
    tgt_mode = target_scale_name if target_scale_name else src_mode
    tgt_bpm = target_bpm if target_bpm is not None else src_bpm

    # ── BPM ratio + SCALE decision ─────────────────────────────────────────
    bpm_ratio = tgt_bpm / src_bpm if src_bpm > 0 else 1.0
    clamp_applied = False

    if bpm_ratio < _BPM_RATIO_MIN or bpm_ratio > _BPM_RATIO_CLAMP:
        warnings.append(
            f"BPM ratio {bpm_ratio:.2f} is outside the safe range "
            f"[{_BPM_RATIO_MIN}, {_BPM_RATIO_CLAMP}] "
            f"(source {src_bpm:.0f} BPM → target {tgt_bpm:.0f} BPM). "
            "Rhythmic-density scaling clamped to conservative 1:1 — "
            "manual note-density adjustment recommended."
        )
        effective_bpm_ratio = 1.0  # conservative clamp
        clamp_applied = True
    else:
        effective_bpm_ratio = bpm_ratio

    if abs(bpm_ratio - 1.0) > 0.01:
        decisions.append({
            "element": "Global tempo mapping",
            "decision": "SCALE",
            "detail": {
                "source_bpm": src_bpm,
                "target_bpm": tgt_bpm,
                "bpm_ratio": round(bpm_ratio, 4),
                "effective_bpm_ratio": round(effective_bpm_ratio, 4),
                "clamp_applied": clamp_applied,
                "rhythmic_density_multiplier": round(effective_bpm_ratio, 4),
            },
            "rationale": (
                f"Source {src_bpm:.0f} BPM → target {tgt_bpm:.0f} BPM "
                f"(ratio {bpm_ratio:.3f}). "
                + ("Density CLAMPED to 1:1 due to extreme ratio. " if clamp_applied else "")
                + "Delay/echo times scale inversely with BPM ratio to maintain "
                "rhythmic feel (e.g. 1/4 dotted stays proportional to bar length)."
            ),
            "executable_steps": [
                {
                    "action": "set_tempo",
                    "bpm": tgt_bpm,
                    "comment": f"Set project tempo to {tgt_bpm} BPM",
                }
            ],
        })

    # ── Scale REMAP decision ──────────────────────────────────────────────
    scale_changed = (tgt_root != src_root) or (tgt_mode.lower() != src_mode.lower())
    if scale_changed:
        root_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        src_name = f"{root_names[src_root % 12]} {src_mode}"
        tgt_name = f"{root_names[tgt_root % 12]} {tgt_mode}"

        # Example: remap a middle C (60) to show what the pitch shift looks like
        example_remapped = _remap_pitch_class(60, src_root, src_mode, tgt_root, tgt_mode)
        semitone_shift = tgt_root - src_root

        decisions.append({
            "element": "Scale / key transposition",
            "decision": "REMAP",
            "detail": {
                "source_scale": src_name,
                "target_scale": tgt_name,
                "root_shift_semitones": semitone_shift,
                "mode_remap": f"{src_mode} → {tgt_mode}",
                "example": f"MIDI 60 (C4 in {src_name}) → MIDI {example_remapped} in {tgt_name}",
            },
            "rationale": (
                f"All MIDI clips transposed: {src_name} → {tgt_name}. "
                + (f"Root shift {abs(semitone_shift)} semitones "
                   f"({'up' if semitone_shift > 0 else 'down'}). " if semitone_shift != 0 else "")
                + (f"Mode remapped {src_mode} → {tgt_mode}: scale-degree relationships "
                   f"preserved by mapping each degree to nearest equivalent."
                   if src_mode.lower() != tgt_mode.lower() else
                   "Same mode — pitch-class shift only.")
            ),
            "executable_steps": [
                {
                    "action": "set_song_scale",
                    "root": tgt_root,
                    "name": tgt_mode,
                    "comment": (
                        f"Set song scale to {tgt_name}. "
                        "Live's scale-snap will remap scale-locked clips per degree. "
                        "For non-scale-locked clips, manually transpose by "
                        f"{semitone_shift:+d} semitones after setting the scale."
                    ),
                },
            ],
            # LIMITATION: demo sidecars expose only macro {index, value} — no clip
            # note data.  Per-note _remap_pitch_class offsets (Option A) therefore
            # cannot be pre-computed here.  Option B is used: set_song_scale activates
            # Live's built-in per-degree remapping for scale-locked clips.
            # Non-scale-locked clips still need manual transposition (see comment above).
        })

    # ── PRESERVE: pitch intervals ─────────────────────────────────────────
    if preserve_pitch_intervals:
        decisions.append({
            "element": "Pitch interval relationships",
            "decision": "PRESERVE",
            "detail": {"mode": "interval-relative"},
            "rationale": (
                "Pitch intervals within each voice preserved (preserve_pitch_intervals=True). "
                "Transposition applied as a global shift; voicings retain original shape."
            ),
            "executable_steps": [],
        })

    # ── PRESERVE: macro ratios ────────────────────────────────────────────
    if preserve_macro_ratios and source_sidecar:
        tracks = source_sidecar.get("tracks") or []
        macro_notes = []
        for track in tracks:
            devices = track.get("devices") or []
            for dev in devices:
                macros = dev.get("macros") or []
                nonzero = [
                    m for m in macros
                    if float(str(m.get("value", "0"))) != 0.0
                ]
                if nonzero:
                    user_name = dev.get("user_name") or dev.get("class", "device")
                    macro_notes.append(
                        f"{track.get('name','track')} / {user_name}: "
                        f"{len(nonzero)} non-default macros preserved as ratios"
                    )
        decisions.append({
            "element": "Macro values (non-default)",
            "decision": "PRESERVE",
            "detail": {"mode": "ratio", "macro_notes": macro_notes[:8]},
            "rationale": (
                "Non-default macro values preserved as normalised ratios [0-127 → 0-1]. "
                "These encode the author's committed artistic decisions; carry them forward "
                "even when the target preset has different raw parameter ranges."
            ),
            "executable_steps": [
                {
                    "action": "set_device_parameter",
                    "note": "Apply per-track macro values after loading each preset; "
                            "use normalised ratio × 127 to convert back to raw values.",
                }
            ],
        })

    # ── Per-track decisions ───────────────────────────────────────────────
    if source_sidecar:
        tracks = source_sidecar.get("tracks") or []
        for track in tracks:
            t_name = track.get("name", "Unknown Track")
            t_type = track.get("type", "")
            if t_type in ("ReturnTrack", "MasterTrack"):
                continue
            devices = track.get("devices") or []
            if not devices:
                continue

            dev = devices[0]
            dev_class = dev.get("class", "")
            user_name = dev.get("user_name") or dev_class

            # Check aesthetic-replace rules for this device
            track_inventory = [dev_class, user_name]
            replace_decisions = _evaluate_replace_rules(track_inventory, target_aesthetic)

            if replace_decisions:
                for rd in replace_decisions:
                    steps = _build_replace_steps(rd, t_name, user_name)
                    decisions.append({
                        "element": f"{t_name} ({user_name})",
                        "decision": "REPLACE",
                        "detail": rd,
                        "rationale": rd.get("rationale_fragment", "Aesthetic replacement."),
                        "executable_steps": steps,
                    })
            else:
                # Default: PRESERVE the track structure
                # BUG-NEW#1: emit_load_step adds browser_search_hint so the agent
                # can resolve a URI before calling load_browser_item.
                try:
                    from .preset_resolver import emit_load_step as _emit_load_step
                    _pack_slug = source_sidecar.get("file", "").split("/")[-2] if source_sidecar.get("file") else ""
                    preserve_step = _emit_load_step(_pack_slug, dev_class, user_name, -1)
                except Exception:
                    # Fallback if preset_resolver unavailable
                    preserve_step = {
                        "action": "load_browser_item",
                        "name": user_name,
                        "browser_search_hint": {
                            "name_filter": user_name,
                            "suggested_path": "sounds",
                        },
                        "comment": f"Load {user_name} preset from source pack",
                    }
                decisions.append({
                    "element": f"{t_name} ({user_name})",
                    "decision": "PRESERVE",
                    "detail": {
                        "device_class": dev_class,
                        "user_name": user_name,
                    },
                    "rationale": (
                        f"{user_name} is aesthetically compatible with the target context. "
                        "Load via browser URI; apply preserved macro values."
                    ),
                    "executable_steps": [preserve_step],
                })

    # ── Global aesthetic replace (whole-sidecar device inventory) ─────────
    if source_sidecar and target_aesthetic:
        all_inventory = source_struct.get("device_inventory", [])
        global_replaces = _evaluate_replace_rules(all_inventory, target_aesthetic)
        already_covered = {
            d.get("detail", {}).get("remove_device") or ""
            for d in decisions
            if d.get("decision") == "REPLACE"
        }
        for rd in global_replaces:
            if (rd.get("remove_device") or "") not in already_covered:
                decisions.append({
                    "element": f"Global effect chain ({rd.get('remove_device', 'device')})",
                    "decision": "REPLACE",
                    "detail": rd,
                    "rationale": rd.get("rationale_fragment", "Aesthetic replacement."),
                    "executable_steps": _build_replace_steps(rd, "global", rd.get("remove_device", "")),
                })

    return decisions, warnings


def _build_replace_steps(
    rd: dict,
    track_context: str,
    user_name: str,
) -> list[dict]:
    """Build executable_steps list for a REPLACE decision."""
    steps = []
    if rd.get("action") in ("replace", "remove") and rd.get("remove_device"):
        steps.append({
            "action": "delete_device",
            "filter": rd["remove_device"],
            "track_context": track_context,
            "comment": f"Remove {rd['remove_device']}",
        })
    if rd.get("action") in ("replace", "enhance") and rd.get("add_device"):
        steps.append({
            "action": "insert_device",
            "device_name": rd["add_device"],
            "track_context": track_context,
            "comment": f"Insert {rd['add_device']}",
        })
        for param in rd.get("parameters", []):
            steps.append({
                "action": "set_device_parameter",
                "name": param["name"],
                "value": param["value"],
                "track_context": track_context,
            })
    return steps


# ─── Producer vocabulary anchor detection ────────────────────────────────────

def _detect_producer_anchor(
    source_entity_id: str,
    target_aesthetic: str,
    source_namespace: str,
) -> str:
    """Return producer-vocabulary anchor sentences for the reasoning artifact.

    Checks target_aesthetic FIRST (higher priority — the user's intent), then
    source entity_id and namespace.  Returns all matching anchors joined by a
    newline so that both source-pack and target-aesthetic vocabulary are surfaced.
    Returns empty string if no match.
    """
    target_lower = target_aesthetic.lower()
    source_lower = f"{source_entity_id} {source_namespace}".lower()

    seen: set[str] = set()
    results: list[str] = []

    # 1. Target-aesthetic keywords — checked first (intent takes priority)
    for keyword, anchor_text in _PRODUCER_ANCHORS.items():
        if keyword.lower() in target_lower and anchor_text not in seen:
            seen.add(anchor_text)
            results.append(anchor_text)

    # 2. Source entity_id / namespace keywords — appended after target anchors
    for keyword, anchor_text in _PRODUCER_ANCHORS.items():
        if keyword.lower() in source_lower and anchor_text not in seen:
            seen.add(anchor_text)
            results.append(anchor_text)

    return "\n".join(results)


# ─── Reasoning artifact generation ───────────────────────────────────────────

def _generate_reasoning_artifact(
    source_struct: dict,
    target_bpm: float | None,
    target_scale_root: int | None,
    target_scale_name: str,
    target_aesthetic: str,
    decisions: list[dict],
    warnings: list[str],
    depth: str,
    source_entity_id: str,
    source_namespace: str,
) -> str:
    """Generate a prose reasoning artifact.

    depth: "terse" | "standard" | "verbose"
    """
    root_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    src_bpm = source_struct["bpm"]
    src_root = source_struct["scale"]["root_note"]
    src_mode = source_struct["scale"]["name"]
    src_scale_str = f"{root_names[src_root % 12]} {src_mode}"

    tgt_bpm = target_bpm or src_bpm
    tgt_root = target_scale_root if target_scale_root is not None else src_root
    tgt_mode = target_scale_name or src_mode
    tgt_scale_str = f"{root_names[tgt_root % 12]} {tgt_mode}"

    bpm_ratio = tgt_bpm / src_bpm if src_bpm > 0 else 1.0
    n_tracks = source_struct.get("track_count", 0)
    n_replace = sum(1 for d in decisions if d.get("decision") == "REPLACE")
    n_preserve = sum(1 for d in decisions if d.get("decision") == "PRESERVE")
    n_remap = sum(1 for d in decisions if d.get("decision") == "REMAP")

    # Producer anchor
    producer_anchor = _detect_producer_anchor(source_entity_id, target_aesthetic, source_namespace)

    if depth == "terse":
        parts = [
            f"Transplant {source_entity_id} ({src_bpm:.0f} BPM {src_scale_str}) → "
            f"{tgt_bpm:.0f} BPM {tgt_scale_str}."
        ]
        if n_replace:
            parts.append(f"{n_replace} device(s) replaced for aesthetic fit.")
        if warnings:
            parts.append(f"Warning: {warnings[0]}")
        return " ".join(parts)

    if depth == "standard":
        body = (
            f"This transplant adapts {source_entity_id} from {src_bpm:.0f} BPM {src_scale_str} "
            f"to {tgt_bpm:.0f} BPM {tgt_scale_str} (BPM ratio {bpm_ratio:.3f}). "
        )
        if producer_anchor:
            body += producer_anchor + " "
        if n_remap:
            body += (
                f"Key transposition shifts all MIDI clips: {src_scale_str} → {tgt_scale_str}. "
            )
        if n_replace:
            replace_elements = [
                d.get("detail", {}).get("remove_device", "device")
                for d in decisions
                if d.get("decision") == "REPLACE"
            ]
            body += (
                f"{n_replace} aesthetic-incompatible device(s) swapped "
                f"({', '.join(filter(None, replace_elements))}). "
            )
        body += (
            f"{n_preserve} structural element(s) preserved as-is. "
            f"The plan covers {n_tracks} source tracks; execute sequentially."
        )
        if warnings:
            body += f" NOTE: {warnings[0]}"
        return body.strip()

    # verbose
    lines = [
        f"## Transplant Plan: {source_entity_id}",
        f"",
        f"**Source:** {src_bpm:.0f} BPM, {src_scale_str}, "
        f"{n_tracks} tracks, {source_struct.get('scene_count', 0)} scenes",
        f"**Target:** {tgt_bpm:.0f} BPM, {tgt_scale_str}, aesthetic: {target_aesthetic or '(none)'}",
        f"",
    ]
    if producer_anchor:
        lines += [f"### Producer Vocabulary Anchor", f"", producer_anchor, f""]

    lines += [f"### Translation Summary", f""]
    for i, d in enumerate(decisions, 1):
        lines.append(
            f"{i}. **{d['decision']}** — {d['element']}: {d.get('rationale', '')}"
        )

    if warnings:
        lines += [f"", f"### Warnings", f""]
        for w in warnings:
            lines.append(f"- {w}")

    lines += [f"", f"### Executable Plan", f""]
    for d in decisions:
        steps = d.get("executable_steps", [])
        if steps:
            lines.append(f"**{d['element']}**:")
            for step in steps:
                lines.append(f"  - `{step.get('action')}` {step.get('comment', '')}")

    return "\n".join(lines)


# ─── Find compatible target preset (Phase D integration) ─────────────────────

def _find_compatible_preset_targets(
    source_sidecar: dict | None,
    target_aesthetic: str,
    top_k: int = 3,
) -> list[dict]:
    """Use Phase D's macro_fingerprint matcher to find compatible target presets.

    Returns a list of {pack_slug, preset_path, preset_name, similarity_score}.
    Used when source_track_or_preset is a preset sidecar.
    """
    if source_sidecar is None:
        return []
    try:
        from .macro_fingerprint import (
            _extract_fingerprint,
            _compute_similarity,
            _iter_all_preset_sidecars,
            _generate_rationale,
        )
    except ImportError:
        return []

    source_fp = _extract_fingerprint(source_sidecar)
    if not source_fp:
        return []

    # Build target aesthetic pack filter heuristic
    tgt_lower = target_aesthetic.lower()
    # Prefer packs that match aesthetic keywords
    scored: list[tuple[float, str, str, dict, list[dict]]] = []
    for cand_pack, cand_slug, cand_sidecar in _iter_all_preset_sidecars():
        cand_fp = _extract_fingerprint(cand_sidecar)
        if len(cand_fp) < 2:
            continue
        score, matched = _compute_similarity(source_fp, cand_fp)
        if score >= 0.1:
            # Boost if pack name appears in aesthetic
            boost = 0.05 if any(
                kw in tgt_lower
                for kw in cand_pack.replace("-", " ").split()
            ) else 0.0
            scored.append((score + boost, cand_pack, cand_slug, cand_sidecar, matched))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, cand_pack, cand_slug, cand_sidecar, matched in scored[:top_k]:
        rationale = _generate_rationale(
            source_pack=source_sidecar.get("file", "").split("/")[-2] if source_sidecar.get("file") else "",
            source_name=source_sidecar.get("name", ""),
            cand_pack=cand_pack,
            cand_name=cand_sidecar.get("name", ""),
            matching_macros=matched,
        )
        results.append({
            "pack_slug": cand_pack,
            "preset_path": cand_slug,
            "preset_name": cand_sidecar.get("name", ""),
            "similarity_score": score,
            "rationale": rationale,
        })
    return results


# ─── Main transplant function ─────────────────────────────────────────────────

def transplant(
    source_namespace: str,
    source_entity_id: str,
    source_track_or_preset: str = "",
    target_bpm: float | None = None,
    target_scale_root: int | None = None,
    target_scale_name: str = "",
    target_aesthetic: str = "",
    preserve_macro_ratios: bool = True,
    preserve_pitch_intervals: bool = True,
    explanation_depth: str = "standard",
) -> dict:
    """Core transplant logic — returns the structured plan dict.

    Called directly by the MCP tool registration in tools.py.
    Separated from the tool wrapper to allow direct unit-testing.
    """
    sources_cited: list[str] = []
    warnings: list[str] = []

    # ── 0a. Normalize sentinel values ────────────────────────────────────
    # BUG-EDGE#6: -1 is the "keep source root" sentinel from the tools.py wrapper.
    # If the inner function is called directly with target_scale_root=-1, treat it
    # as None (no remapping) rather than emitting an invalid set_song_scale step.
    if target_scale_root is not None and target_scale_root < 0:
        target_scale_root = None

    # ── 0. Validate source_namespace ─────────────────────────────────────
    _ALLOWED_NAMESPACES = ["packs", "m4l-devices", "elektron"]
    if source_namespace not in _ALLOWED_NAMESPACES:
        return {
            "error": (
                f"Unknown source_namespace: '{source_namespace}'. "
                f"Allowed: {_ALLOWED_NAMESPACES}"
            ),
            "status": "error",
        }

    # ── 1. Load source data ───────────────────────────────────────────────
    source_sidecar: dict | None = None
    preset_sidecar: dict | None = None
    entity_id_resolved = source_entity_id

    if source_namespace == "packs":
        # Try demo sidecar first (entity_id like "drone_lab__earth")
        if "__" in source_entity_id:
            source_sidecar = _load_demo_sidecar(source_entity_id)
            if source_sidecar:
                sidecar_path = _resolve_demo_slug(source_entity_id)
                # BUG-C#5: resolve to canonical hyphenated slug, not raw input form
                entity_id_resolved = _entity_id_to_slug(source_entity_id)
                sources_cited.append(
                    f"als-parse: {sidecar_path} [SOURCE: als-parse]"
                )
            else:
                warnings.append(
                    f"Demo sidecar not found for entity_id='{source_entity_id}'. "
                    "Checked slug variants: underscore ↔ hyphen. "
                    "Falling back to minimal structure."
                )

        # If source_track_or_preset provided, try to load the preset sidecar
        if source_track_or_preset:
            # entity_id may be the pack slug (e.g. "drone_lab")
            pack_slug_guess = source_entity_id.replace("__", "_").split("__")[0]
            resolved = _resolve_preset_slug(pack_slug_guess, source_track_or_preset)
            if resolved:
                preset_sidecar = _load_preset_sidecar_cached(*resolved)
                entity_id_resolved = resolved[1]
                sources_cited.append(
                    f"adg-parse: {PRESET_PARSES_ROOT / resolved[0] / resolved[1]}.json "
                    f"[SOURCE: adg-parse]"
                )
            if preset_sidecar is None:
                # Try harder: source_entity_id itself might be the pack slug
                for pack_guess in [
                    source_entity_id,
                    source_entity_id.replace("_", "-"),
                    source_entity_id.split("__")[0].replace("_", "-"),
                ]:
                    resolved2 = _resolve_preset_slug(pack_guess, source_track_or_preset)
                    if resolved2:
                        preset_sidecar = _load_preset_sidecar_cached(*resolved2)
                        sources_cited.append(
                            f"adg-parse: preset/{resolved2[0]}/{resolved2[1]} "
                            f"[SOURCE: adg-parse]"
                        )
                        entity_id_resolved = resolved2[1]
                        break
            if preset_sidecar is None:
                warnings.append(
                    f"Preset sidecar not found for source_track_or_preset='{source_track_or_preset}' "
                    f"in pack '{source_entity_id}'."
                )

    # Choose which sidecar drives the structure
    primary_sidecar = source_sidecar if source_sidecar else preset_sidecar

    # ── 2. Extract source structure ───────────────────────────────────────
    if primary_sidecar:
        source_struct = _extract_source_structure(primary_sidecar)
    elif preset_sidecar:
        source_struct = _extract_preset_structure(preset_sidecar)
    else:
        # Minimal fallback — no sidecar found
        source_struct = {
            "bpm": 120.0,
            "scale": {"root_note": 0, "name": "Major"},
            "tracks_summary": [],
            "device_inventory": [],
            "track_count": 0,
            "scene_count": 0,
            "return_tracks": [],
        }
        warnings.append("No sidecar data found — structural inference not possible.")

    # Override BPM / scale from preset sidecar if that's our primary source
    if preset_sidecar and not source_sidecar:
        # Preset sidecars don't have BPM/scale — keep defaults
        pass

    # ── 3. Find compatible targets via macro-fingerprint if preset source ─
    compatible_targets: list[dict] = []
    if preset_sidecar and target_aesthetic:
        compatible_targets = _find_compatible_preset_targets(
            preset_sidecar, target_aesthetic, top_k=3
        )
        if compatible_targets:
            sources_cited.append(
                f"adg-parse: macro-fingerprint scan across {len(compatible_targets)} "
                f"best matches [SOURCE: adg-parse]"
            )

    # ── 4. Compute translation decisions ──────────────────────────────────
    decisions, decision_warnings = _compute_translation_decisions(
        source_struct=source_struct,
        target_bpm=target_bpm,
        target_scale_root=target_scale_root,
        target_scale_name=target_scale_name,
        target_aesthetic=target_aesthetic,
        preserve_pitch_intervals=preserve_pitch_intervals,
        preserve_macro_ratios=preserve_macro_ratios,
        source_sidecar=primary_sidecar,
    )
    warnings.extend(decision_warnings)

    # ── 5. Build translation_plan (spec return shape) ─────────────────────
    translation_plan = []
    for dec in decisions:
        translation_plan.append({
            "element": dec["element"],
            "decision": dec["decision"],
            "detail": dec.get("detail"),   # BUG-INT#3: was dropped; must include for REPLACE decisions
            "rationale": dec.get("rationale", ""),
            "executable_steps": dec.get("executable_steps", []),
        })

    # Inject compatible targets into plan if found
    if compatible_targets:
        target_names = [ct["preset_name"] for ct in compatible_targets]
        translation_plan.append({
            "element": "Compatible target presets (macro-fingerprint matched)",
            "decision": "REPLACE",  # Preset-swap suggestion — not a scale-degree transform
            "rationale": (
                f"Macro-fingerprint similarity search found {len(compatible_targets)} "
                f"compatible target preset(s) for target aesthetic '{target_aesthetic}': "
                + "; ".join(
                    f"{ct['preset_name']} ({ct['pack_slug']}, score {ct['similarity_score']:.2f})"
                    for ct in compatible_targets
                )
            ),
            "executable_steps": [
                {
                    "action": "load_browser_item",
                    "name": ct["preset_name"],
                    "pack": ct["pack_slug"],
                    "comment": f"Load compatible target: {ct['preset_name']} (score {ct['similarity_score']:.2f})",
                }
                for ct in compatible_targets
            ],
        })

    # ── 6. Generate reasoning artifact ───────────────────────────────────
    reasoning = _generate_reasoning_artifact(
        source_struct=source_struct,
        target_bpm=target_bpm,
        target_scale_root=target_scale_root,
        target_scale_name=target_scale_name,
        target_aesthetic=target_aesthetic,
        decisions=decisions,
        warnings=warnings,
        depth=explanation_depth,
        source_entity_id=entity_id_resolved,
        source_namespace=source_namespace,
    )
    sources_cited.append("agent-inference: translation decisions [SOURCE: agent-inference]")

    # ── Build output ──────────────────────────────────────────────────────
    root_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    src_root = source_struct["scale"]["root_note"]

    return {
        "source": {
            "namespace": source_namespace,
            "entity_id": entity_id_resolved,
            "bpm": source_struct["bpm"],
            "scale": source_struct["scale"],
            "tracks_summary": source_struct["tracks_summary"],
        },
        "target": {
            "bpm": target_bpm if target_bpm is not None else source_struct["bpm"],
            "scale": {
                "root_note": target_scale_root if target_scale_root is not None else src_root,
                "name": target_scale_name or source_struct["scale"]["name"],
            },
            "aesthetic": target_aesthetic,
        },
        "translation_plan": translation_plan,
        "reasoning_artifact": reasoning,
        "warnings": warnings,
        "sources": sources_cited,
    }


def _extract_preset_structure(sidecar: dict) -> dict:
    """Extract minimal structure from a preset sidecar (no BPM/scale available)."""
    macros = sidecar.get("macros") or []
    named_macros = [
        m.get("name", "")
        for m in macros
        if m.get("name") and not m["name"].startswith("Macro ")
    ]
    return {
        "bpm": 120.0,
        "scale": {"root_note": 0, "name": "Major"},
        "tracks_summary": [sidecar.get("name", "preset")],
        "device_inventory": sidecar.get("device_summary") or [],
        "track_count": 1,
        "scene_count": 0,
        "return_tracks": [],
        "named_macros": named_macros,
    }
