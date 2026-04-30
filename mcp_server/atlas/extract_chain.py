"""Pack-Atlas Phase E — Extract Chain.

Surgically rebuilds a specific demo track's device chain in the user's current
project.  Returns a dry-run execution plan (or live execution result when
target_track_index >= 0).  All source data from local JSON sidecars.

Real sidecar schema note (from Phase C appendix):
  Track devices: {class, user_name, params (null in demos), macros [{index, value}]}
  Macros in demo sidecars have NO names — only {index, value}.
  The device class identifies the device type; user_name is the preset's name.

Parameter fidelity modes:
  "exact"         — emit set_device_parameter for every non-default macro
  "approximate"   — top 5 most-committed macros (highest deviation from 0)
  "structure-only"— skip parameter setting; chain structure only
"""

from __future__ import annotations

import re
from typing import Any

from .transplant import (
    DEMO_PARSES_ROOT,
    _load_demo_sidecar,
    _resolve_demo_slug,
)
from .preset_resolver import resolve_preset_for_device

# ─── Known native Live device class names ────────────────────────────────────
# These are built-in Live devices loadable by class name via insert_device.
# GroupDevice/Rack classes handled separately.

_NATIVE_INSTRUMENT_CLASSES = {
    # NOTE: "PluginDevice" intentionally excluded — third-party VST/AU plugins
    # cannot be inserted by class name.  See BUG-E2#PluginDevice fix.
    "OriginalSimpler", "MultiSampler",
    "AnalogSynth", "InstrumentVector", "DrumSynthBass", "DrumSynthBell",
    "DrumSynthCymbal", "DrumSynthHihat", "DrumSynthSnare",
    "Tension", "Electric", "Collision", "Mallet",
    # Common aliases
    "Simpler", "Sampler", "Operator", "Analog", "Drift", "Wavetable",
}

# Third-party plugin classes that cannot be inserted by class name.
# These require a manual_rebuild step with plugin name/vendor from the user.
_PLUGIN_DEVICE_CLASSES = {"PluginDevice"}

_NATIVE_AUDIO_EFFECT_CLASSES = {
    "Reverb", "Delay", "Echo", "Chorus", "Phaser", "Flanger",
    "Compressor2", "MultibandDynamics", "Limiter", "GlueCompressor",
    "EQ8", "EQ3", "AutoFilter", "AutoPan",
    "Saturator", "DynamicTube", "Redux", "Erosion",
    "Vinyl Distortion", "VinylDistortion", "Cabinet",
    "Corpus", "Resonator", "FrequencyShifter", "PitchHack",
    "BeatRepeat", "Grain", "Looper",
    "Amp", "Overdrive", "PedalDistortion", "ExternalInstrument",
    "FilterDelay", "SpectralBlur", "SpectralResonator", "SpectralTime",
}

_NATIVE_MIDI_EFFECT_CLASSES = {
    "MidiRandom", "MidiArpeggiator", "MidiChord", "MidiPitcher",
    "MidiScale", "MidiVelocity", "MidiSysexFlag",
    "MidiNoteLength", "MidiSustain",
}

_GROUP_DEVICE_CLASSES = {
    "InstrumentGroupDevice",
    "AudioEffectGroupDevice",
    "DrumGroupDevice",
    "MidiEffectGroupDevice",
}

_MAX_DEVICE_CLASSES = {
    "MaxAudioEffect",
    "MaxInstrument",
    "MaxMidiEffect",
}

_ALL_KNOWN_NATIVE = (
    _NATIVE_INSTRUMENT_CLASSES
    | _NATIVE_AUDIO_EFFECT_CLASSES
    | _NATIVE_MIDI_EFFECT_CLASSES
)


def _is_group_device(class_name: str) -> bool:
    return class_name in _GROUP_DEVICE_CLASSES


def _is_max_device(class_name: str) -> bool:
    return class_name in _MAX_DEVICE_CLASSES


def _is_native_device(class_name: str) -> bool:
    return class_name in _ALL_KNOWN_NATIVE


# ─── Track finder ────────────────────────────────────────────────────────────

def _find_track_by_name(
    demo_dict: dict, track_name: str
) -> tuple[dict | None, list[str]]:
    """Fuzzy-match a track by name.

    Resolution order:
      1. Exact match
      2. Case-insensitive substring match (track_name in t_name)
      3. Tokenized any-token match (any word of track_name in t_name)
      4. Reverse substring (t_name in track_name, i.e. partial query)

    Returns (matched_track_dict_or_None, other_candidate_names).
    When fuzzy match has >=2 candidates, other_candidate_names is populated
    so callers can surface an ambiguity_warning.
    """
    tracks = demo_dict.get("tracks") or []
    name_lower = track_name.lower().strip()

    # Pass 1: exact — unambiguous
    for t in tracks:
        if t.get("name", "") == track_name:
            return t, []

    # Pass 2: case-insensitive substring — collect all candidates
    candidates_2 = [t for t in tracks if name_lower in t.get("name", "").lower()]
    if candidates_2:
        others = [t.get("name", "") for t in candidates_2[1:]]
        return candidates_2[0], others

    # Pass 3: any token of query present in track name
    tokens = [tok for tok in re.split(r"\s+", name_lower) if tok]
    candidates_3 = [
        t for t in tracks
        if any(tok in t.get("name", "").lower() for tok in tokens)
    ]
    if candidates_3:
        others = [t.get("name", "") for t in candidates_3[1:]]
        return candidates_3[0], others

    # Pass 4: reverse — track name is substring of query
    candidates_4 = [
        t for t in tracks if t.get("name", "").lower() in name_lower
    ]
    if candidates_4:
        others = [t.get("name", "") for t in candidates_4[1:]]
        return candidates_4[0], others

    return None, []


# ─── Device chain walker ─────────────────────────────────────────────────────

_MAX_CHAIN_DEPTH = 4  # matches transplant._walk_device_chain cap and als_deep_parse


def _collect_inner_chain_classes(dev: dict, depth: int = 0) -> list[str]:
    """Recursively collect class names from a rack device's inner chains.

    Used to build chain_summary for group-device steps without blowing up
    the execution plan with nested steps.

    Caps at _MAX_CHAIN_DEPTH to match the parser's depth limit.
    """
    if depth > _MAX_CHAIN_DEPTH:
        return []
    result: list[str] = []
    for chain in dev.get("chains") or []:
        for inner_dev in chain.get("devices") or []:
            cls = inner_dev.get("class", "") or ""
            uname = inner_dev.get("user_name") or ""
            label = uname if (uname and uname != cls) else cls
            if label:
                result.append(label)
            # Recurse into nested racks (e.g. rack-within-rack)
            result.extend(_collect_inner_chain_classes(inner_dev, depth + 1))
    return result


def _walk_device_chain(track: dict) -> list[dict]:
    """Return devices in topological order from a track dict.

    For each device, returns:
      {class, user_name, macros, depth, inner_chain_classes}

    BUG-INT#2 fix: v1.23.5+ sidecars include a `chains` field on rack
    devices (Schema A — nested).  We now populate `inner_chain_classes` by
    recursing into dev.chains up to _MAX_CHAIN_DEPTH levels deep so that
    callers (device_chain_summary, _emit_execution_steps) can surface inner
    devices without emitting thousands of nested execution steps.
    """
    devices = track.get("devices") or []
    result = []
    for dev in devices:
        inner_classes = _collect_inner_chain_classes(dev)
        result.append({
            "class": dev.get("class", ""),
            "user_name": dev.get("user_name") or "",
            "macros": dev.get("macros") or [],
            "params": dev.get("params"),
            "depth": 0,
            "inner_chain_classes": inner_classes,
        })
    return result


# ─── Macro extraction helpers ─────────────────────────────────────────────────

def _safe_float(v: Any) -> float:
    try:
        return float(str(v))
    except (ValueError, TypeError):
        return 0.0


def _get_nonzero_macros(macros: list[dict]) -> list[dict]:
    """Return macro entries with non-zero values."""
    return [m for m in macros if _safe_float(m.get("value", "0")) != 0.0]


def _load_preset_defaults(pack_name: str, preset_user_name: str) -> dict[int, float] | None:
    """Load factory-default macro values from a preset sidecar JSON.

    Sidecars live at:
      ~/.livepilot/atlas-overlays/packs/_preset_parses/<pack>/<preset_slug>.json

    Matching: tries exact name match on sidecar["name"] field, then falls back
    to filename-slug comparison (lowercased, spaces→hyphens).

    Returns {macro_index: default_value} or None if no sidecar found.
    """
    import json
    import os

    preset_root = os.path.expanduser(
        "~/.livepilot/atlas-overlays/packs/_preset_parses"
    )
    pack_dir = os.path.join(preset_root, pack_name)
    if not os.path.isdir(pack_dir):
        return None

    name_lower = preset_user_name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", name_lower).strip("-")

    for fname in os.listdir(pack_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(pack_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        # Name match
        if data.get("name", "").lower().strip() == name_lower:
            macros = data.get("macros") or []
            return {int(m["index"]): _safe_float(m.get("value", "0")) for m in macros}
        # Slug match
        file_slug = re.sub(r"[^a-z0-9]+", "-", fname[:-5].lower()).strip("-")
        if file_slug == slug or file_slug.endswith("-" + slug) or slug in file_slug:
            macros = data.get("macros") or []
            return {int(m["index"]): _safe_float(m.get("value", "0")) for m in macros}

    return None


def _top_k_macros_by_deviation(
    macros: list[dict],
    k: int = 5,
    preset_defaults: dict[int, float] | None = None,
) -> list[dict]:
    """Return the k macros with the largest deviation from factory default.

    In "approximate" fidelity mode — the macros most committed away from their
    factory default are the most production-meaningful.

    If preset_defaults is provided (from a matching preset sidecar), deviation
    is computed as abs(live_value - factory_default).  If not provided (no
    sidecar match), falls back to abs(live_value) (deviation from zero).
    """
    nonzero = _get_nonzero_macros(macros)
    if preset_defaults is not None:
        def _deviation(m: dict) -> float:
            idx = int(m.get("index", 0))
            live = _safe_float(m.get("value", "0"))
            default = preset_defaults.get(idx, 0.0)
            return abs(live - default)
    else:
        # Fallback: deviation from zero
        def _deviation(m: dict) -> float:  # type: ignore[misc]
            return abs(_safe_float(m.get("value", "0")))

    sorted_macros = sorted(nonzero, key=_deviation, reverse=True)
    return sorted_macros[:k]


# ─── Execution step emitter ───────────────────────────────────────────────────

def _emit_execution_steps(
    device: dict,
    fidelity: str,
    track_name: str,
    device_index: int,
    pack_name: str = "",
) -> tuple[list[dict], list[str]]:
    """Emit executable plan steps for one device.

    Returns (steps_list, warnings_list).

    Logic:
      - PluginDevice (third-party VST/AU)
          → manual_rebuild: cannot be inserted by class name; agent must locate
            the plugin by vendor/name. See BUG-E2#PluginDevice.
      - GroupDevice rack (InstrumentGroupDevice, AudioEffectGroupDevice, etc.)
          → try atlas resolution; emit load_browser_item if name is meaningful,
            else manual_rebuild with macro values
      - MaxAudioEffect / MaxInstrument / MaxMidiEffect
          → load_browser_item for the .amxd (user_name is the device label)
      - Known native device
          → insert_device + set_device_parameter (based on fidelity)
      - Unknown class
          → insert_device best-effort + warning

    Parameter fidelity "approximate" uses preset sidecar factory defaults when
    available to sort by deviation-from-default rather than abs(value).
    # TODO(URI-helper): emit load_device_by_uri when a browser URI is resolved.
    """
    steps: list[dict] = []
    warnings: list[str] = []

    cls = device["class"]
    uname = device["user_name"] or ""
    macros = device["macros"]

    label = uname or cls or "unknown-device"

    # ── PluginDevice — third-party VST/AU, not insertable by class name ───────
    if cls in _PLUGIN_DEVICE_CLASSES:
        plugin_meta = device.get("plugin") or {}
        plugin_name = plugin_meta.get("name") or uname or "unknown plugin"
        manufacturer = plugin_meta.get("manufacturer") or ""
        plugin_format = plugin_meta.get("format") or "unknown"
        # Build a browser-search-hint the agent can pass to search_browser
        # to locate the plugin in Live's plugins folder. The plugin's display
        # name (from PluginDesc) is more reliable than the rack's user_name
        # since the user might have renamed the rack but not the plugin.
        load_step = {
            "action": "manual_rebuild",
            "device_class": cls,
            "device_name": uname or plugin_name,
            "plugin": plugin_meta if plugin_meta else None,
            "browser_search_hint": {
                "name_filter": plugin_name,
                "suggested_path": "plugins",
            },
            "note": (
                f"'{uname or plugin_name}' is a {plugin_format} plugin"
                + (f" by {manufacturer}" if manufacturer else "")
                + ". Cannot be inserted via insert_device(class='PluginDevice'). "
                "Use search_browser(**browser_search_hint) to locate it under "
                "the plugins/ category, then load_browser_item with the resolved URI. "
                "Parameter values are stored in an opaque per-plugin binary buffer "
                "and aren't recoverable from the .als — agent must re-dial by ear."
            ),
            "device_index": device_index,
        }
        # Drop the plugin field if empty — keeps step shape clean for old corpora
        if not plugin_meta:
            load_step.pop("plugin")
        steps.append(load_step)
        warnings.append(
            f"Device {device_index} '{uname or plugin_name}' is a "
            f"{plugin_format} plugin"
            + (f" ({manufacturer})" if manufacturer else "")
            + ". manual_rebuild step emitted; param values opaque."
        )
        return steps, warnings

    # ── Group device (rack) ───────────────────────────────────────────────────
    if _is_group_device(cls):
        # Look up preset sidecar for deviation-from-default macro sorting
        preset_defaults: dict[int, float] | None = None
        if fidelity == "approximate" and uname and pack_name:
            preset_defaults = _load_preset_defaults(pack_name, uname)

        # BUG-INT#2: surface inner chain devices via chain_summary so the agent
        # has visibility into nested devices without emitting nested steps.
        inner_classes: list[str] = device.get("inner_chain_classes") or []
        inner_chain_summary: str | None = (
            " → ".join(inner_classes) if inner_classes else None
        )

        if uname:
            # Resolve matching preset sidecar → producer-assigned macro names + URI hint.
            # BUG-E2#1 (Macro N labeling) + BUG-E2#4 (load_browser_item URI hint).
            preset_match = (
                resolve_preset_for_device(pack_name, cls, uname)
                if pack_name else {"found": False, "macro_names": {}, "browser_search_hint": None}
            )
            macro_names: dict[int, str] = preset_match.get("macro_names") or {}

            load_step = {
                "action": "load_browser_item",
                "name": uname,
                "device_class": cls,
                "comment": (
                    f"Load '{uname}' rack from browser. "
                    "Resolve URI via search_browser(**browser_search_hint) "
                    "before calling load_browser_item. "
                    "If not found, use manual_rebuild steps below."
                ),
                "device_index": device_index,
            }
            if inner_chain_summary:
                load_step["chain_summary"] = inner_chain_summary
            if preset_match.get("found") and preset_match.get("browser_search_hint"):
                load_step["browser_search_hint"] = preset_match["browser_search_hint"]
                load_step["preset_match"] = preset_match.get("match_type")
            else:
                load_step["browser_search_hint"] = {
                    "name_filter": uname,
                    "suggested_path": "sounds",
                }
                load_step["preset_match"] = "none"
            steps.append(load_step)

            # Emit macro set steps based on fidelity
            if fidelity != "structure-only":
                macro_subset = (
                    _get_nonzero_macros(macros)
                    if fidelity == "exact"
                    else _top_k_macros_by_deviation(
                        macros, k=5, preset_defaults=preset_defaults
                    )
                )
                for m in macro_subset:
                    macro_idx = m["index"]
                    # Prefer producer-assigned macro name from preset sidecar; fall back
                    # to "Macro N" when no name was recorded for that index.
                    resolved_name = macro_names.get(macro_idx) or f"Macro {macro_idx + 1}"
                    val = round(_safe_float(m.get("value", "0")), 2)
                    steps.append({
                        "action": "set_device_parameter",
                        "device_index": device_index,
                        "parameter_name": resolved_name,
                        "parameter_index": macro_idx + 1,  # fallback addressing
                        "value": val,
                        "comment": (
                            f"Set {resolved_name} (idx {macro_idx + 1}) = {val} "
                            f"[SOURCE: als-parse{'+adg-parse' if resolved_name != f'Macro {macro_idx + 1}' else ''}]"
                        ),
                    })
        else:
            # No user_name — structural rack with no named preset
            # Emit manual_rebuild with macro values as structured data
            nonzero = _get_nonzero_macros(macros)
            macro_data = [
                {"index": m["index"], "value": round(_safe_float(m.get("value", "0")), 2)}
                for m in nonzero
            ]
            unnamed_step: dict = {
                "action": "manual_rebuild",
                "device_class": cls,
                "note": (
                    f"Unnamed {cls} rack — no browser-loadable preset available. "
                    "Rebuild manually using the macro values below."
                ),
                "macro_values": macro_data,
                "device_index": device_index,
            }
            if inner_chain_summary:
                unnamed_step["chain_summary"] = inner_chain_summary
            steps.append(unnamed_step)
            if nonzero:
                warnings.append(
                    f"Device {device_index} is an unnamed {cls} rack — "
                    "no browser URI available. "
                    f"Macro values ({len(nonzero)} non-default) documented in manual_rebuild step."
                )
        return steps, warnings

    # ── Max device (.amxd) ────────────────────────────────────────────────────
    if _is_max_device(cls):
        name_for_load = uname or cls
        steps.append({
            "action": "load_browser_item",
            "name": name_for_load,
            "device_class": cls,
            "comment": (
                f"Load M4L device '{name_for_load}' from browser. "
                "Search in Max for Live category."
            ),
            "device_index": device_index,
        })
        if fidelity != "structure-only" and macros:
            macro_subset = (
                _get_nonzero_macros(macros)
                if fidelity == "exact"
                else _top_k_macros_by_deviation(macros, k=5)
            )
            for m in macro_subset:
                steps.append({
                    "action": "set_device_parameter",
                    "device_index": device_index,
                    "parameter_name": f"Macro {m['index'] + 1}",
                    "value": round(_safe_float(m.get("value", "0")), 2),
                    "comment": f"M4L macro {m['index'] + 1} [SOURCE: als-parse]",
                })
        return steps, warnings

    # ── Native Live device ────────────────────────────────────────────────────
    if _is_native_device(cls) or cls:
        device_name = uname or cls
        steps.append({
            "action": "insert_device",
            "device_class": cls,
            "device_name": device_name,
            "comment": f"Insert {device_name}",
            "device_index": device_index,
        })
        if fidelity != "structure-only" and macros:
            macro_subset = (
                _get_nonzero_macros(macros)
                if fidelity == "exact"
                else _top_k_macros_by_deviation(macros, k=5)
            )
            for m in macro_subset:
                steps.append({
                    "action": "set_device_parameter",
                    "device_index": device_index,
                    "parameter_name": f"Macro {m['index'] + 1}",
                    "value": round(_safe_float(m.get("value", "0")), 2),
                    "comment": f"[SOURCE: als-parse]",
                })

        if not _is_native_device(cls):
            warnings.append(
                f"Device class '{cls}' is not a recognised native Live device. "
                "insert_device step is best-effort — verify in Live."
            )
        return steps, warnings

    # Unknown class
    warnings.append(f"Unknown device class '{cls}' — skipped.")
    return steps, warnings


# ─── Execution plan builder ───────────────────────────────────────────────────

def _build_execution_plan(
    track: dict,
    target_track_index: int,
    fidelity: str,
    demo_entity_id: str,
    track_name: str,
    pack_name: str = "",
) -> tuple[list[dict], list[str]]:
    """Build the full execution plan for extracting one track's device chain.

    Returns (steps_list, warnings_list).
    The plan is a DRY-RUN — executed: false always from this function.

    Track-type → create action mapping (BUG-E2#3+#7 fix):
      MidiTrack   → create_midi_track
      GroupTrack  → manual_step (no create_group_track MCP tool exists)
      ReturnTrack → create_return_track
      AudioTrack  → create_audio_track  (default)
    """
    steps: list[dict] = []
    warnings: list[str] = []

    t_name = track.get("name", track_name)
    t_type = track.get("type", "")

    # Step 0 (conditional): create a new track if target_track_index < 0
    if target_track_index < 0:
        if t_type == "MidiTrack":
            steps.append({
                "action": "create_midi_track",
                "name": f"{t_name} (extracted from {demo_entity_id})",
                "comment": "Create new MIDI track for extracted chain",
            })
        elif t_type == "GroupTrack":
            # LivePilot has no create_group_track MCP tool — manual step required
            steps.append({
                "action": "manual_step",
                "note": (
                    f"Source track '{t_name}' is a GroupTrack. "
                    "LivePilot does not have a create_group_track tool. "
                    "Manually group the target tracks in Ableton (Cmd+G / Ctrl+G), "
                    "then re-run extract_chain with target_track_index pointing at "
                    "the new group track."
                ),
                "name": f"{t_name} (extracted from {demo_entity_id})",
                "comment": "GroupTrack requires manual creation — no MCP tool available",
            })
            warnings.append(
                f"Track '{t_name}' is a GroupTrack. No create_group_track MCP tool "
                "exists in LivePilot. A manual_step was emitted — create the group "
                "in Ableton manually, then pass its index via target_track_index."
            )
        elif t_type == "ReturnTrack":
            steps.append({
                "action": "create_return_track",
                "name": f"{t_name} (extracted from {demo_entity_id})",
                "comment": "Create new return track for extracted chain",
            })
        else:
            # AudioTrack and any unknown type default to audio
            steps.append({
                "action": "create_audio_track",
                "name": f"{t_name} (extracted from {demo_entity_id})",
                "comment": "Create new audio track for extracted chain",
            })
    else:
        steps.append({
            "action": "target_existing_track",
            "track_index": target_track_index,
            "comment": f"Write chain to existing track {target_track_index}",
        })

    # Walk device chain and emit steps
    device_chain = _walk_device_chain(track)
    for i, dev in enumerate(device_chain):
        dev_steps, dev_warnings = _emit_execution_steps(
            dev, fidelity, t_name, i, pack_name=pack_name
        )
        steps.extend(dev_steps)
        warnings.extend(dev_warnings)

    if not device_chain:
        warnings.append(f"Track '{t_name}' has no devices — only a track creation step emitted.")

    return steps, warnings


# ─── Main entry point ─────────────────────────────────────────────────────────

def extract_chain(
    demo_entity_id: str,
    track_name: str,
    target_track_index: int = -1,
    parameter_fidelity: str = "exact",
) -> dict:
    """Build a dry-run device-chain extraction plan for a demo track.

    Called by the MCP tool wrapper in tools.py.

    Parameters
    ----------
    demo_entity_id : str
        Entity ID, e.g. "drone_lab__emergent_planes".
    track_name : str
        Name of the track to extract (fuzzy matched).
    target_track_index : int
        Target track index in the live project. -1 = create new track (dry-run).
        Phase E ships dry-run only; execution against live project is Phase F.
    parameter_fidelity : str
        "exact" | "approximate" | "structure-only"

    Returns
    -------
    dict matching the spec Extract Chain return shape.
    """
    # ── 0. Guard: track_name must not be empty ────────────────────────────────
    # BUG-EDGE#8: "" matches every track via the fuzzy pass-2 (`"" in any_string`
    # is always True), silently returning the first track.  Reject before loading.
    if not track_name or not track_name.strip():
        # Load sidecar to return available_tracks in the error (best-effort).
        _sidecar_for_avail = _load_demo_sidecar(demo_entity_id)
        _available: list[str] = []
        if _sidecar_for_avail is not None:
            _available = [t.get("name", "") for t in (_sidecar_for_avail.get("tracks") or [])]
        return {
            "error": "track_name is required and cannot be empty.",
            "status": "error",
            "entity_id": demo_entity_id,
            "available_tracks": _available,
            "executed": False,
            "sources": [],
        }

    # ── 1. Load sidecar ───────────────────────────────────────────────────────
    sidecar = _load_demo_sidecar(demo_entity_id)
    if sidecar is None:
        return {
            "error": (
                f"Demo sidecar not found for entity_id='{demo_entity_id}'. "
                "Check ~/.livepilot/atlas-overlays/packs/_demo_parses/."
            ),
            "entity_id": demo_entity_id,
            "executed": False,
            "sources": [],
        }

    sidecar_path = _resolve_demo_slug(demo_entity_id)

    # ── 2. Find track ─────────────────────────────────────────────────────────
    track, fuzzy_other_candidates = _find_track_by_name(sidecar, track_name)
    if track is None:
        available = [t.get("name", "") for t in (sidecar.get("tracks") or [])]
        return {
            "error": (
                f"Track '{track_name}' not found in demo '{demo_entity_id}'. "
                "Fuzzy match (substring, token) also failed."
            ),
            "available_tracks": available,
            "entity_id": demo_entity_id,
            "executed": False,
            "sources": [f"als-parse: {sidecar_path} [SOURCE: als-parse]"],
        }

    resolved_track_name = track.get("name", track_name)
    # BUG-extract_chain-fuzzy: surface ambiguity when multiple candidates matched
    ambiguity_warning: str | None = None
    if fuzzy_other_candidates:
        ambiguity_warning = (
            f"Fuzzy match picked '{resolved_track_name}' but {len(fuzzy_other_candidates)} "
            f"other candidate(s) also matched: {fuzzy_other_candidates}. "
            "Use an exact track name to disambiguate."
        )

    # ── 3. Walk device chain ──────────────────────────────────────────────────
    device_chain = _walk_device_chain(track)

    # Build device_chain summary for return shape
    device_chain_summary = []
    for dev in device_chain:
        cls = dev["class"]
        uname = dev["user_name"]
        macros = dev["macros"]
        nonzero = [m for m in macros if _safe_float(m.get("value", "0")) != 0.0]
        entry: dict[str, Any] = {
            "class": cls,
            "user_name": uname,
            "chain_depth": dev["depth"],
        }
        if nonzero:
            entry["macros"] = [
                {"index": m["index"], "value": round(_safe_float(m.get("value", "0")), 2)}
                for m in nonzero
            ]
        # BUG-INT#2: include inner_chain_classes in device_chain_summary so the
        # agent can see nested devices (e.g. Erosion inside InstrumentGroupDevice)
        inner = dev.get("inner_chain_classes") or []
        if inner:
            entry["inner_chain_classes"] = inner
        device_chain_summary.append(entry)

    # ── 4. Build execution plan ───────────────────────────────────────────────
    # Derive pack_name from demo_entity_id (first segment before "__")
    # e.g. "drone_lab__emergent_planes" → "drone-lab" (match preset_parses dir)
    pack_slug = demo_entity_id.split("__")[0].replace("_", "-")

    steps, warnings = _build_execution_plan(
        track=track,
        target_track_index=target_track_index,
        fidelity=parameter_fidelity,
        demo_entity_id=demo_entity_id,
        track_name=resolved_track_name,
        pack_name=pack_slug,
    )

    result: dict = {
        "source": {
            "demo": demo_entity_id,
            "track": resolved_track_name,
            "track_type": track.get("type", ""),
            "device_count": len(device_chain),
            "device_chain": device_chain_summary,
        },
        "execution_plan": steps,
        "executed": False,  # Phase E is dry-run only
        "parameter_fidelity": parameter_fidelity,
        "warnings": warnings,
        "sources": [
            f"als-parse: {sidecar_path} [SOURCE: als-parse]",
            "agent-inference: execution step generation [SOURCE: agent-inference]",
        ],
    }

    # BUG-extract_chain-fuzzy: include ambiguity fields when fuzzy match was ambiguous
    if ambiguity_warning:
        result["matched_track"] = resolved_track_name
        result["ambiguity_warning"] = ambiguity_warning

    return result
