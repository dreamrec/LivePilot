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


# Role-aware Simpler defaults — BUG-2026-04-22 #17 + #18.
# Each role maps to a list of (parameter_name, value) pairs applied after
# load via set_device_parameter. Trigger Mode polarity per BUG #9:
# 0 = Trigger (one-shot), 1 = Gate (held). Volume in dB. Root in MIDI pitch.
_SIMPLER_ROLE_DEFAULTS = {
    "drum": [
        ("Snap", 0),
        ("Volume", 0.0),
        ("Trigger Mode", 0),  # Trigger / one-shot
        ("Sample Pitch Coarse", 36),  # C1, matches drum-pad convention
    ],
    "melodic": [
        ("Snap", 1),
        ("Volume", 0.0),
        ("Trigger Mode", 1),  # Gate / held
        ("Sample Pitch Coarse", 60),  # C3
    ],
    "texture": [
        ("Snap", 0),
        ("Volume", -6.0),
        ("Trigger Mode", 1),  # Gate
        ("Sample Pitch Coarse", 60),  # C3
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

    # Post-load: apply role-aware defaults if the loaded device is a Simpler.
    if role and isinstance(result, dict) and not result.get("error"):
        device_index = result.get("device_index")
        device_class = str(result.get("class_name") or result.get("device_name") or "")
        if device_index is not None and "Simpler" in device_class:
            applied = []
            for name, value in _SIMPLER_ROLE_DEFAULTS[role]:
                try:
                    ableton.send_command("set_device_parameter", {
                        "track_index": track_index,
                        "device_index": int(device_index),
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

    return result
