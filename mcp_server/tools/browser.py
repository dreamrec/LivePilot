"""Browser MCP tools — browse, search, and load instruments/effects.

4 tools matching the Remote Script browser domain.
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


def _validate_track_index(track_index: int):
    """Validate track index.

    0+ for regular tracks, -1/-2/... for return tracks (A/B/...),
    -1000 for master track.
    """
    if track_index < 0 and track_index != -1000 and track_index < -20:
        raise ValueError(
            "track_index must be >= 0 for regular tracks, "
            "-1/-2/... for return tracks, or -1000 for master"
        )


def _atlas_preflight_for_load(device_name: str) -> Optional[dict]:
    """Atlas-aware preflight check for a freshly-loaded device.

    Returns a dict with `self_contained: false` warning when the loaded
    device is in the enriched atlas AND declares it requires a source
    sample / capture. Returns None for self-contained devices, devices
    not in the atlas, or atlas lookup failures.

    Added 2026-05-08 after a Granulator III load silently produced no
    audio: instrument loaded fine, grain params programmed, BUT no sample
    in the source slot → silence. The atlas YAML for Granulator III has
    `self_contained: false` and signature_techniques all start with "Load
    a sample → ..." but neither was surfaced at load time. This preflight
    closes that gap by reading the atlas immediately after load and
    surfacing the requirement in the load response.
    """
    if not device_name:
        return None
    try:
        from ..atlas import get_atlas
        atlas = get_atlas()
    except Exception:
        return None
    if atlas is None:
        return None
    try:
        entry = atlas.lookup(device_name)
    except Exception:
        return None
    if not entry or not entry.get("enriched"):
        return None
    if entry.get("self_contained") is not False:
        return None  # self-contained or unspecified — no warning needed

    techniques = entry.get("signature_techniques") or []
    first_hint = ""
    if techniques and isinstance(techniques[0], dict):
        first_hint = (
            techniques[0].get("description")
            or techniques[0].get("name")
            or ""
        )

    return {
        "self_contained": False,
        "device_id": entry.get("id"),
        "warning": (
            f"{device_name} is not self-contained — it requires a source "
            "sample or real-time audio capture to produce sound. The "
            "instrument is loaded but will be silent until a sample is "
            "added. Either drag audio onto its waveform display, OR load "
            "a Sounds preset chain via search_browser(path='sounds', "
            f"name_filter='{device_name}') that ships with a sample baked in."
        ),
        "first_technique_hint": str(first_hint).strip()[:240],
    }


@mcp.tool()
def get_browser_tree(ctx: Context, category_type: str = "all") -> dict:
    """Get an overview of browser categories and their children."""
    return _get_ableton(ctx).send_command("get_browser_tree", {
        "category_type": category_type,
    })


@mcp.tool()
def get_browser_items(
    ctx: Context,
    path: str,
    limit: int = 500,
    offset: int = 0,
    filter_pattern: Optional[str] = None,
) -> dict:
    """List items at a browser path (e.g., 'instruments/Analog').

    BUG-2026-04-22#5 fix — the /drums folder returned 68KB+ of JSON on
    single calls, blowing past tool token caps. These params give agents
    a way to page and filter natively without dumping to temp files.

    path:            browser path (e.g., 'drums', 'samples/Packs/Foo')
    limit:           maximum items returned (default 500, max 5000)
    offset:          number of items to skip (default 0)
    filter_pattern:  case-insensitive substring to filter item names by
                     (applied server-side when possible, client-side fallback)
    """
    if not path.strip():
        raise ValueError("Path cannot be empty")
    if limit < 1:
        raise ValueError("limit must be >= 1")
    limit = min(limit, 5000)
    if offset < 0:
        raise ValueError("offset must be >= 0")
    params: dict = {
        "path": path,
        "limit": limit,
        "offset": offset,
    }
    if filter_pattern:
        params["filter_pattern"] = filter_pattern
    result = _get_ableton(ctx).send_command("get_browser_items", params)

    # Client-side fallback: if the remote script's handler doesn't know about
    # limit/offset/filter_pattern yet (older remote-script build), apply the
    # paging + filter here so the MCP contract still works. Returned payload
    # keeps `truncated`/`total_before_filter` for observability.
    if isinstance(result, dict) and "items" in result:
        items = result.get("items") or []
        total_before = len(items)
        if filter_pattern:
            needle = filter_pattern.lower()
            items = [i for i in items if needle in str(i.get("name", "")).lower()]
        total_filtered = len(items)
        paged = items[offset : offset + limit]
        result["items"] = paged
        result["total_before_filter"] = total_before
        result["total_after_filter"] = total_filtered
        result["returned"] = len(paged)
        result["offset"] = offset
        result["limit"] = limit
        result["truncated"] = (offset + limit) < total_filtered
    return result


_BROWSER_PATH_ALIASES: dict[str, str] = {
    "effects": "audio_effects",
    "fx": "audio_effects",
    "audio_fx": "audio_effects",
    "audiofx": "audio_effects",
    "midi_fx": "midi_effects",
    "midifx": "midi_effects",
}


def _normalize_browser_path(path: str) -> str:
    """Normalise common path aliases to their canonical browser category name."""
    return _BROWSER_PATH_ALIASES.get(path.strip().lower(), path)


@mcp.tool()
def search_browser(
    ctx: Context,
    path: str,
    name_filter: Optional[str] = None,
    loadable_only: bool = False,
    max_depth: int = 8,
    max_results: int = 100,
    query: Optional[str] = None,
) -> dict:
    """Search the browser tree under a path, optionally filtering by name.

    BUG-2026-04-22#4 fix — `query` is now accepted as an alias for
    `name_filter`, aligning this tool's schema with `search_samples`.
    Callers passing either keyword work.

    path:         top-level category to search under. Valid categories:
                  instruments, audio_effects, midi_effects, sounds, drums,
                  samples, packs, user_library, plugins, max_for_live, clips.
                  Common aliases are normalised automatically:
                  "effects" / "fx" → "audio_effects"
                  "midi_fx"        → "midi_effects"
    name_filter:  case-insensitive substring filter on item name
    query:        alias for name_filter (accepts either)
    max_depth:    how deep to recurse into subfolders (default 8)
    max_results:  maximum number of results to return (default 100)
    """
    if not path.strip():
        raise ValueError("Path cannot be empty")
    path = _normalize_browser_path(path)
    if max_depth < 1:
        raise ValueError("max_depth must be >= 1")
    if max_results < 1:
        raise ValueError("max_results must be >= 1")
    effective_filter = name_filter if name_filter is not None else query
    params: dict = {"path": path}
    if effective_filter is not None:
        params["name_filter"] = effective_filter
    if loadable_only:
        params["loadable_only"] = loadable_only
    if max_depth != 8:
        params["max_depth"] = max_depth
    if max_results != 100:
        params["max_results"] = max_results
    return _get_ableton(ctx).send_command("search_browser", params)


# M4L instrument post-load hygiene — 2026-05-02.
# Some Max-for-Live instruments load with defaults that immediately produce loud
# unwanted output (Harmonic Drone Generator from Drone Lab is the canonical
# example: Latch on + Density 80% + Volume −6 dB + all 8 voices active = a wall
# of sustained drone the moment any MIDI note touches it). Apply tames here so
# the device is workable on first load. Each entry maps a device-name match
# (substring) to a list of (parameter_name, value) pairs.
#
# Detection runs UNCONDITIONALLY (not gated on `role` like _SIMPLER_ROLE_DEFAULTS)
# because these M4L instruments are typically loaded without a role parameter.
_M4L_INSTRUMENT_HYGIENE: dict[str, list[tuple[str, float]]] = {
    "Harmonic Drone Generator": [
        ("Latch", 0),       # Off — prevents indefinite note sustain after one trigger
        ("Volume", -40),    # ≈ -20 dB display (default is -18 / -6 dB which is too loud)
        ("Density", 40),    # 40% (default 80% is too dense for a background bed)
    ],
}


# Role-aware Simpler defaults — BUG-2026-04-22 #17 + #18, plus 2026-05-02 fix.
# Each role maps to a list of (parameter_name, value) pairs applied after
# load via set_device_parameter. Trigger Mode polarity per BUG #9:
# 0 = Trigger (one-shot), 1 = Gate (held). Volume in dB. Transpose in semitones.
#
# 2026-05-02 — fixed pitch-shift bug:
# Earlier versions used "Sample Pitch Coarse" param name, which DOES NOT EXIST
# on OriginalSimpler — the call silently raised and was swallowed. Result: every
# drum-role Simpler played 24 semitones below original pitch ("super low" sound)
# because the Simpler's default sample root is C3 (60), but drum convention sends
# MIDI 36 (C1). The correct parameter is "Transpose" (range -48..+48 semitones);
# +24 compensates for the C3-vs-C1 mismatch so drum samples play at original
# recorded pitch when MIDI 36 is sent. Melodic/texture roles use Transpose=0
# because their default playback range centers on C3 (60) — no compensation needed.
_SIMPLER_ROLE_DEFAULTS = {
    "drum": [
        ("Snap", 0),
        ("Volume", 0.0),
        ("Trigger Mode", 0),  # Trigger / one-shot
        ("Transpose", 24),    # Compensate C3-default → C1-drum-convention root
    ],
    "melodic": [
        ("Snap", 1),
        ("Volume", 0.0),
        ("Trigger Mode", 1),  # Gate / held
        ("Transpose", 0),     # C3 default — melodic input range
    ],
    "texture": [
        ("Snap", 0),
        ("Volume", -6.0),
        ("Trigger Mode", 1),  # Gate
        ("Transpose", 0),     # C3 default — sustained-input range
    ],
}


@mcp.tool()
def load_browser_item(
    ctx: Context,
    track_index: int,
    uri: str,
    role: Optional[str] = None,
) -> dict:
    """Load a browser item (instrument/effect/sample) onto a track by URI.

    URI grammar — see livepilot/skills/livepilot-devices/references/
    load_browser_item-uri-grammar.md for the full reference. Three
    known forms produced by search_browser /
    get_browser_items / get_browser_tree:
      - query:Drums#FileId_29738       (pack content)
      - query:Synths#Operator          (native device by name)
      - query:UserLibrary#Samples:Splice:Filename.wav  (path-style)
    Always pass URIs verbatim from search results. Never construct them
    by hand — guessed names match greedily and can load the wrong item.

    Context-dependent behavior (BUG-2026-04-22 #16):
      - Empty track: creates a Simpler with the sample loaded.
      - Track with an instrument: drops the new device after the
        existing one.
      - Track with a Drum Rack: the FIRST call creates a chain on
        note 36; subsequent calls REPLACE that chain instead of
        appending to the next pad. Use add_drum_rack_pad for
        pad-by-pad kit construction.

    role (optional, BUG-2026-04-22 #17 + #18): apply role-aware Simpler
    defaults after load. Skips silently if no Simpler was created (e.g.,
    when loading a native synth or effect).
      - "drum"     : Snap=0, Vol=0dB, Trigger Mode=0 (Trigger), root=C1 (36)
      - "melodic"  : Snap=1, Vol=0dB, Trigger Mode=1 (Gate), root=C3 (60)
      - "texture"  : Snap=0, Vol=-6dB, Trigger Mode=1 (Gate), root=C3 (60)
    Omit role to keep Live's raw defaults (Volume=-12dB, Snap=1).

    NOTE on Trigger Mode polarity (BUG-2026-04-22 #9): the value is
    REVERSED from intuition. Trigger Mode=0 means Trigger (one-shot,
    drum-style), Trigger Mode=1 means Gate (held, melodic-style).
    """
    _validate_track_index(track_index)
    if not uri.strip():
        raise ValueError("URI cannot be empty")
    if role is not None and role not in _SIMPLER_ROLE_DEFAULTS:
        raise ValueError(
            f"role must be one of {sorted(_SIMPLER_ROLE_DEFAULTS)}, got {role!r}"
        )

    ableton = _get_ableton(ctx)
    result = ableton.send_command("load_browser_item", {
        "track_index": track_index,
        "uri": uri,
    })

    # Post-load: probe the loaded device once, then apply two layers of hygiene.
    #
    # 2026-05-02 — fixed device-detection bug. The TCP load_browser_item command
    # returns {loaded, name, device_count} with NO device_index and NO class_name,
    # so the previous detection (`result.get("device_index")` / `result.get("class_name")`)
    # always failed and the role-defaults branch was never entered. Resolution:
    # treat newly-loaded sample-on-empty-track as device_index=0 (Live places the
    # instrument at chain head) and verify class + name via get_device_info.
    #
    # Layer 1 (gated on `role`): Simpler role-aware defaults — Snap/Volume/
    # Trigger Mode/Transpose for drum/melodic/texture roles.
    # Layer 2 (unconditional): M4L instrument hygiene — name-matched tames for
    # known problem devices (Harmonic Drone Generator's Latch + loud defaults).
    device_index_resolved: Optional[int] = None
    device_class = ""
    device_name_loaded = ""
    if isinstance(result, dict) and result.get("loaded") and not result.get("error"):
        device_index_resolved = result.get("device_index")
        try:
            probe = ableton.send_command("get_device_info", {
                "track_index": track_index,
                "device_index": 0,
            })
            device_class = str(probe.get("class_name", "") or "")
            device_name_loaded = str(probe.get("name", "") or result.get("name", "") or "")
            if device_index_resolved is None:
                device_index_resolved = 0
        except Exception:
            pass

    # Layer 0 — atlas-aware preflight. Surface a follow-up hint when the
    # loaded device declares self_contained=false in its atlas enrichment
    # YAML (granular samplers, sample players). Prevents the silent-
    # Granulator-III failure mode where the instrument loads, params get
    # programmed, but no audio source has been added.
    if device_name_loaded:
        preflight = _atlas_preflight_for_load(device_name_loaded)
        if preflight is not None:
            result["atlas_preflight"] = preflight

    # Layer 1 — Simpler role-aware defaults
    if role and device_index_resolved is not None and "Simpler" in device_class:
        applied = []
        for name, value in _SIMPLER_ROLE_DEFAULTS[role]:
            try:
                ableton.send_command("set_device_parameter", {
                    "track_index": track_index,
                    "device_index": int(device_index_resolved),
                    "parameter_name": name,
                    "value": value,
                })
                applied.append({"parameter": name, "value": value})
            except Exception as exc:
                # Don't fail the whole load if one default doesn't apply
                # (parameter name might not exist on every Simpler variant).
                applied.append({"parameter": name, "skipped": str(exc)})
        result["role"] = role
        result["role_defaults_applied"] = applied
        result["device_class"] = device_class

    # Layer 2 — M4L instrument hygiene (unconditional, name-matched).
    # Detects Harmonic Drone Generator and other known problem M4L instruments
    # by name substring, applies tame defaults to prevent loud-on-load surprises.
    if device_index_resolved is not None and device_name_loaded:
        for hygiene_name, params in _M4L_INSTRUMENT_HYGIENE.items():
            if hygiene_name not in device_name_loaded:
                continue
            applied_hygiene = []
            for name, value in params:
                try:
                    ableton.send_command("set_device_parameter", {
                        "track_index": track_index,
                        "device_index": int(device_index_resolved),
                        "parameter_name": name,
                        "value": value,
                    })
                    applied_hygiene.append({"parameter": name, "value": value})
                except Exception as exc:
                    applied_hygiene.append({"parameter": name, "skipped": str(exc)})
            result["m4l_hygiene"] = {
                "device_name": hygiene_name,
                "applied": applied_hygiene,
            }
            result.setdefault("device_class", device_class)
            break  # one hygiene match per load

    return result
