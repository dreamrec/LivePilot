"""Atlas MCP tools — search, suggest, compare, and scan the device database.

6 tools for the atlas domain.
"""

from __future__ import annotations

import json
import os
import time

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _get_atlas():
    """Get the global AtlasManager instance, loading lazily if needed.

    Uses the thread-safe singleton helper — concurrent FastMCP tool calls no
    longer race on the check-then-set, and the atlas auto-reloads from disk
    if device_atlas.json's mtime advanced (e.g. after scan_full_library).
    """
    from . import get_atlas
    try:
        return get_atlas()
    except FileNotFoundError:
        return None


@mcp.tool()
def atlas_search(ctx: Context, query: str, category: str = "all", limit: int = 10) -> dict:
    """Search the device atlas for instruments, effects, kits, or plugins.

    query:    natural language search — name, sonic character, use case, or genre
              Examples: "warm analog bass", "reverb", "808 kit", "granular"
    category: filter by category (all, instruments, audio_effects, midi_effects,
              max_for_live, drum_kits, plugins)
    limit:    max results (default 10)
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first.", "results": []}

    results = atlas.search(query, category=category, limit=limit)
    return {
        "query": query,
        "category": category,
        "count": len(results),
        "results": [
            {
                "id": r["device"].get("id", ""),
                "name": r["device"].get("name", ""),
                "uri": r["device"].get("uri", ""),
                "category": r["device"].get("category", ""),
                "sonic_description": r["device"].get("sonic_description", "")[:120],
                "character_tags": r["device"].get("character_tags", [])[:5],
                "enriched": r["device"].get("enriched", False),
                "score": r.get("score", 0),
            }
            for r in results
        ],
    }


@mcp.tool()
def atlas_device_info(ctx: Context, device_id: str) -> dict:
    """Get complete atlas knowledge about a device — parameters, recipes, pairings, gotchas.

    device_id: the atlas ID or device name (e.g., "drift", "Compressor", "808_core_kit")
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    entry = atlas.lookup(device_id)
    if entry is None:
        return {"error": f"Device '{device_id}' not found in atlas", "suggestion": "Use atlas_search to find devices"}
    return entry


@mcp.tool()
def atlas_suggest(
    ctx: Context,
    intent: str,
    genre: str = "",
    energy: str = "medium",
    key: str = "",
) -> dict:
    """Suggest devices for a production intent.

    intent: what you're trying to achieve — "warm bass", "crispy hi-hats", "evolving texture"
    genre:  target genre for better recommendations
    energy: low/medium/high — affects sonic character suggestions
    key:    musical key context (e.g., "Cm") for tuned percussion suggestions
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    results = atlas.suggest(intent, genre=genre, energy=energy)
    return {
        "intent": intent,
        "genre": genre,
        "energy": energy,
        "suggestions": [
            {
                "device_id": r["device"]["id"],
                "device_name": r["device"]["name"],
                "uri": r["device"].get("uri", ""),
                "rationale": r["rationale"],
                "recipe": r.get("recipe"),
            }
            for r in results
        ],
    }


@mcp.tool()
def atlas_chain_suggest(ctx: Context, role: str, genre: str = "") -> dict:
    """Suggest a full device chain for a track role.

    role:  the musical role — "bass", "lead", "pad", "drums", "percussion", "texture"
    genre: target genre for style-appropriate choices
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    return atlas.chain_suggest(role, genre=genre)


@mcp.tool()
def atlas_compare(ctx: Context, device_a: str, device_b: str, role: str = "") -> dict:
    """Compare two devices — strengths, weaknesses, and recommendation for a role.

    device_a: first device name or ID
    device_b: second device name or ID
    role:     optional role context (e.g., "bass", "pad")
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    return atlas.compare(device_a, device_b, role=role)


@mcp.tool()
def scan_full_library(ctx: Context, force: bool = False) -> dict:
    """Scan the full Ableton browser and rebuild the device atlas.

    Walks every category (instruments, audio_effects, midi_effects, max_for_live,
    drums, plugins, packs) and records every loadable item with its URI.
    Results are merged with curated enrichments and saved to device_atlas.json.

    force: if True, rescan even if atlas already exists (default False)
    """
    from .scanner import normalize_scan_results
    from .enrichments import load_enrichments, merge_enrichments
    from . import AtlasManager

    atlas_dir = os.path.dirname(os.path.abspath(__file__))
    atlas_path = os.path.join(atlas_dir, "device_atlas.json")
    enrichments_dir = os.path.join(atlas_dir, "enrichments")

    if not force and os.path.exists(atlas_path):
        age = time.time() - os.path.getmtime(atlas_path)
        if age < 86400:
            # Reload if not already loaded
            import mcp_server.atlas as atlas_mod
            if atlas_mod._atlas_instance is None:
                atlas_mod._atlas_instance = AtlasManager(atlas_path)
            return {
                "status": "already_exists",
                "age_hours": round(age / 3600, 1),
                "device_count": atlas_mod._atlas_instance.device_count,
                "message": "Atlas is recent. Use force=True to rescan.",
            }

    # Scan browser
    ableton = _get_ableton(ctx)
    raw = ableton.send_command("scan_browser_deep", {"max_per_category": 1000})

    # Normalize
    devices = normalize_scan_results(raw)

    # Load and merge enrichments
    enrichments = load_enrichments(enrichments_dir)
    devices = merge_enrichments(devices, enrichments)

    # Count stats
    stats: dict = {"total_devices": len(devices)}
    for device in devices:
        cat = device.get("category", "other")
        stats[cat] = stats.get(cat, 0) + 1
    stats["enriched_devices"] = sum(1 for d in devices if d.get("enriched"))

    # Read the actual running Live version from the session rather than
    # hardcoding "12.3.6" — the hardcoded string was baking last year's
    # version into every new user's atlas until they forced a rescan.
    try:
        session_info = ableton.send_command("get_session_info", {}) or {}
        live_version = session_info.get("live_version", "unknown")
    except Exception:
        live_version = "unknown"

    # Build atlas
    atlas_data = {
        "version": "2.0.0",
        "live_version": live_version,
        "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stats": stats,
        "devices": devices,
        "packs": [],
    }

    # Atomic write: tmp + rename. Same pattern as PersistentJsonStore. Previous
    # version used open(atlas_path, "w") + json.dump with no fsync, so a crash
    # mid-write produced a truncated JSON file that the next AtlasManager init
    # silently read as empty-dict — devices vanished from memory.
    tmp_path = atlas_path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(atlas_data, f, indent=2)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            # fsync may be unavailable on some filesystems/Windows paths —
            # best-effort; the rename below is still atomic on POSIX.
            pass
    os.replace(tmp_path, atlas_path)

    # Invalidate singleton so next get_atlas() picks up the new file.
    import mcp_server.atlas as atlas_mod
    atlas_mod.invalidate_atlas()

    return {
        "status": "scanned",
        "device_count": len(devices),
        "enriched_count": stats["enriched_devices"],
        "stats": stats,
        "atlas_path": atlas_path,
    }


@mcp.tool()
def reload_atlas(ctx: Context) -> dict:
    """Force the atlas to re-read device_atlas.json from disk.

    Useful after an out-of-band rebuild (e.g. a manual edit to the JSON file,
    or a scan that crashed before invalidating the cache). The next search /
    suggest / compare call will see the fresh data. No-op if the atlas has
    never been loaded — the first real call will load it fresh anyway.
    """
    from . import invalidate_atlas, get_atlas
    invalidate_atlas()
    atlas = get_atlas()
    return {
        "reloaded": True,
        "device_count": atlas.device_count if atlas else 0,
    }
