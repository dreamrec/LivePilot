"""Resolve a demo track's device → matching preset sidecar.

Demo sidecars record device class + user_name but NOT macro names. Preset
sidecars carry the producer-assigned macro names. This module bridges the
two so plan emitters can output executable set_device_parameter steps with
real names (e.g. "Rift Rate") instead of generic "Macro N" labels, AND can
suggest a search_browser query for load_browser_item URI resolution.

Demo macro shape (no name):
    [{"index": 0, "value": "1"}, ...]
Preset macro shape (with producer-assigned name):
    [{"index": 0, "value": "1", "name": "Rift Rate"}, ...]

Live's browser URIs are FileId-keyed and require a runtime browser query —
there's no static URI we can derive from the sidecar alone, so this module
returns a search_browser HINT that the agent uses to resolve to a concrete
URI before calling load_browser_item.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

PRESET_PARSES_ROOT = (
    Path.home() / ".livepilot" / "atlas-overlays" / "packs" / "_preset_parses"
)


@lru_cache(maxsize=64)
def _load_pack_index(pack_slug: str) -> tuple[tuple[str, str, str], ...]:
    """Return tuple of (preset_name, rack_class, sidecar_path) for the pack.

    Cached. Returns empty tuple if pack dir doesn't exist.
    """
    pack_dir = PRESET_PARSES_ROOT / pack_slug
    if not pack_dir.is_dir():
        # Try hyphen/underscore swap as a safety net
        alt = PRESET_PARSES_ROOT / pack_slug.replace("_", "-")
        if alt.is_dir():
            pack_dir = alt
        else:
            return ()
    entries: list[tuple[str, str, str]] = []
    for sidecar in pack_dir.glob("*.json"):
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = (data.get("name") or "").strip()
        rack_class = (data.get("rack_class") or "").strip()
        if name:
            entries.append((name, rack_class, str(sidecar)))
    return tuple(entries)


def resolve_preset_for_device(
    pack_slug: str,
    device_class: str,
    device_user_name: str,
) -> dict:
    """Find the matching preset sidecar for a demo track's device.

    Match priority:
      1. Exact name match (case-insensitive) within the pack
      2. Exact name match with matching rack_class
      3. Substring match (preset_name in user_name OR vice versa)
      4. None found → empty result

    Args:
        pack_slug: pack identifier, e.g. "drone-lab"
        device_class: Live device class, e.g. "InstrumentGroupDevice"
                      (used as a tiebreaker; pass empty string to skip)
        device_user_name: rack's user-visible name, e.g. "Pioneer Drone"

    Returns dict:
        found: bool
        match_type: "exact" | "exact_with_class" | "partial" | "none"
        sidecar_path: str | None
        preset_name: str | None
        macro_names: dict[int, str]  # {macro_index: producer-assigned name}
        browser_search_hint: dict | None
            {name_filter: str, suggested_path: str}
        preset_file: str | None  # original .adg path for logging
    """
    if not device_user_name or not pack_slug:
        return _empty_result()

    target = device_user_name.strip().lower()
    pack_index = _load_pack_index(pack_slug)
    if not pack_index:
        return _empty_result()

    # Pass 1: exact name + rack_class match (strongest)
    if device_class:
        for name, rack_class, sidecar_path in pack_index:
            if name.lower() == target and rack_class == device_class:
                return _build_result(sidecar_path, name, "exact_with_class")

    # Pass 2: exact name match (any class)
    for name, _rc, sidecar_path in pack_index:
        if name.lower() == target:
            return _build_result(sidecar_path, name, "exact")

    # Pass 3: substring fallback
    for name, _rc, sidecar_path in pack_index:
        nlow = name.lower()
        if (nlow and (nlow in target or target in nlow)
                and abs(len(nlow) - len(target)) < max(len(nlow), len(target))):
            return _build_result(sidecar_path, name, "partial")

    return _empty_result()


def lookup_macro_name(
    pack_slug: str, device_user_name: str, macro_index: int
) -> Optional[str]:
    """Convenience: get a single macro name without re-resolving every time."""
    res = resolve_preset_for_device(pack_slug, "", device_user_name)
    return res["macro_names"].get(macro_index)


# ─── internals ────────────────────────────────────────────────────────────────


def _build_result(sidecar_path: str, preset_name: str, match_type: str) -> dict:
    try:
        data = json.loads(Path(sidecar_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_result()

    macros = data.get("macros") or []
    macro_names: dict[int, str] = {}
    for m in macros:
        try:
            idx = int(m.get("index", -1))
            name = (m.get("name") or "").strip()
            if idx >= 0 and name:
                macro_names[idx] = name
        except (ValueError, TypeError):
            continue

    preset_file = data.get("file") or ""
    return {
        "found": True,
        "match_type": match_type,
        "sidecar_path": sidecar_path,
        "preset_name": preset_name,
        "macro_names": macro_names,
        "browser_search_hint": {
            "name_filter": preset_name,
            "suggested_path": _infer_browser_path(preset_file),
        },
        "preset_file": preset_file,
    }


def _empty_result() -> dict:
    return {
        "found": False,
        "match_type": "none",
        "sidecar_path": None,
        "preset_name": None,
        "macro_names": {},
        "browser_search_hint": None,
        "preset_file": None,
    }


def _infer_browser_path(file_path: str) -> str:
    """Map a preset sidecar 'file' field to a search_browser path category.

    Examples:
      "Drone Lab/Sounds/Synth Pad/Pioneer Drone.adg"  → "sounds"
      "Beat Tools/Drums/Kicks/Foo.adg"                → "drums"
      "Inspired by Nature/Instruments/Tree Tone.adg"  → "instruments"

    Defaults to "sounds" for unknown layouts (the broadest factory-pack
    category for instrument racks).
    """
    parts = [p.lower() for p in file_path.split("/") if p]
    if len(parts) < 2:
        return "sounds"
    second = parts[1]
    if "sound" in second or "synth" in second:
        return "sounds"
    if "drum" in second:
        return "drums"
    if "instrument" in second:
        return "instruments"
    if "audio effect" in second or "fx" in second or "effect" in second:
        return "audio_effects"
    if "midi" in second:
        return "midi_effects"
    return "sounds"


def emit_load_step(
    pack_slug: str,
    device_class: str,
    device_user_name: str,
    track_index: int,
) -> dict:
    """Build a load_browser_item plan step with embedded search-resolution hint.

    Returns a dict matching the shape downstream callers (extract_chain,
    pack_aware_compose) emit into their executable_steps lists. The agent
    is expected to call search_browser(**browser_search_hint) first, then
    load_browser_item(track_index=track_index, uri=<resolved_uri>).
    """
    res = resolve_preset_for_device(pack_slug, device_class, device_user_name)
    step: dict = {
        "action": "load_browser_item",
        "track_index": track_index,
        "name": device_user_name,
        "device_class": device_class,
        "comment": (
            "Resolve URI via search_browser before calling load_browser_item. "
            "The browser_search_hint provides the recommended path + name_filter."
        ),
    }
    if res["found"]:
        step["browser_search_hint"] = res["browser_search_hint"]
        step["preset_name"] = res["preset_name"]
        step["preset_file"] = res["preset_file"]
        step["match_type"] = res["match_type"]
    else:
        step["browser_search_hint"] = {
            "name_filter": device_user_name,
            "suggested_path": "sounds",
        }
        step["match_type"] = "none"
        step["comment"] += (
            f" (no preset sidecar found in pack '{pack_slug}'; using user_name as fallback)"
        )
    return step
