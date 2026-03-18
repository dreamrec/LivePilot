"""Memory MCP tools — technique library for saving, recalling, and replaying patterns.

8 tools for the agent's long-term memory system.
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp
from ..memory.technique_store import TechniqueStore

_store = TechniqueStore()


def _get_store() -> TechniqueStore:
    return _store


@mcp.tool()
def memory_learn(
    ctx: Context,
    name: str,
    type: str,
    qualities: dict,
    payload: dict,
    tags: Optional[list] = None,
) -> dict:
    """Save a new technique to the memory library with stylistic qualities. type must be one of: beat_pattern, device_chain, mix_template, browser_pin, preference. qualities must include at minimum a 'summary' field."""
    return _get_store().save(name=name, type=type, qualities=qualities, payload=payload, tags=tags)


@mcp.tool()
def memory_recall(
    ctx: Context,
    query: Optional[str] = None,
    type: Optional[str] = None,
    tags: Optional[list] = None,
    limit: int = 10,
) -> dict:
    """Search the technique library by text query and/or filters. Returns summaries (no payload)."""
    results = _get_store().search(query=query, type_filter=type, tags=tags, limit=limit)
    return {"count": len(results), "techniques": results}


@mcp.tool()
def memory_get(ctx: Context, technique_id: str) -> dict:
    """Fetch a full technique by ID, including payload for replay."""
    return _get_store().get(technique_id)


@mcp.tool()
def memory_replay(ctx: Context, technique_id: str, adapt: bool = False) -> dict:
    """Retrieve a technique with a replay plan for the agent to execute. adapt=false: returns step-by-step replay plan for exact reconstruction. adapt=true: returns technique for creative adaptation."""
    store = _get_store()
    technique = store.get(technique_id)
    store.increment_replay(technique_id)

    mode = "adapt" if adapt else "exact"

    if adapt:
        steps = [
            "Read qualities and payload as inspiration",
            "Create something new that matches the stylistic palette",
        ]
    else:
        steps = _generate_replay_steps(technique)

    return {
        "technique": technique,
        "replay_plan": {
            "mode": mode,
            "type": technique["type"],
            "steps": steps,
        },
    }


def _generate_replay_steps(technique: dict) -> list[str]:
    """Generate human-readable replay steps based on technique type."""
    t_type = technique["type"]
    payload = technique.get("payload", {})

    if t_type == "beat_pattern":
        steps = []
        kit = payload.get("kit_name")
        if kit:
            steps.append(f"Load kit '{kit}' using search_browser + load_browser_item")
        steps.append(
            f"Create a MIDI clip using create_clip "
            f"(length={payload.get('clip_length', 4)} beats)"
        )
        notes = payload.get("notes", [])
        if notes:
            steps.append(f"Add {len(notes)} notes using add_notes with the stored note data")
        tempo = payload.get("tempo")
        if tempo:
            steps.append(f"Set tempo to {tempo} BPM using set_tempo")
        return steps or ["Replay the beat pattern from the stored payload"]

    elif t_type == "device_chain":
        steps = []
        devices = payload.get("devices", [])
        for i, dev in enumerate(devices):
            dev_name = dev.get("name", f"device {i + 1}")
            steps.append(f"Load '{dev_name}' using find_and_load_device")
            params = dev.get("params", {})
            if params:
                steps.append(
                    f"Set {len(params)} parameters on '{dev_name}' using batch_set_parameters"
                )
        return steps or ["Load the device chain from the stored payload"]

    elif t_type == "mix_template":
        steps = []
        returns = payload.get("returns", [])
        if returns:
            steps.append(
                f"Create {len(returns)} return tracks using create_return_track"
            )
            for ret in returns:
                devices = ret.get("devices", [])
                for dev in devices:
                    dev_name = dev if isinstance(dev, str) else dev.get("name", "device")
                    steps.append(
                        f"Load '{dev_name}' on return track using find_and_load_device"
                    )
        sends = payload.get("sends_pattern", {})
        if sends:
            steps.append(
                "Apply send levels from sends_pattern "
                "(note: role names must be resolved to track indices by the agent)"
            )
        return steps or ["Apply the mix template from the stored payload"]

    elif t_type == "browser_pin":
        uri = payload.get("uri", "")
        name = payload.get("name", "item")
        steps = [f"Load browser item '{name}' by URI '{uri}' using load_browser_item"]
        return steps

    elif t_type == "preference":
        key = payload.get("key", "preference")
        value = payload.get("value", "")
        steps = [f"Apply preference '{key}' = '{value}'"]
        return steps

    return ["Replay the technique from the stored payload"]


@mcp.tool()
def memory_list(
    ctx: Context,
    type: Optional[str] = None,
    tags: Optional[list] = None,
    sort_by: str = "updated_at",
    limit: int = 20,
) -> dict:
    """Browse the technique library with optional filtering."""
    results = _get_store().list_techniques(
        type_filter=type, tags=tags, sort_by=sort_by, limit=limit
    )
    return {"count": len(results), "techniques": results}


@mcp.tool()
def memory_favorite(
    ctx: Context,
    technique_id: str,
    favorite: Optional[bool] = None,
    rating: Optional[int] = None,
) -> dict:
    """Star and/or rate a technique (rating 0-5)."""
    return _get_store().favorite(
        technique_id=technique_id, favorite=favorite, rating=rating
    )


@mcp.tool()
def memory_update(
    ctx: Context,
    technique_id: str,
    name: Optional[str] = None,
    tags: Optional[list] = None,
    qualities: Optional[dict] = None,
) -> dict:
    """Update name, tags, or qualities on an existing technique. Qualities are merged (lists replace)."""
    return _get_store().update(
        technique_id=technique_id, name=name, tags=tags, qualities=qualities
    )


@mcp.tool()
def memory_delete(ctx: Context, technique_id: str) -> dict:
    """Delete a technique from the library (creates backup first)."""
    return _get_store().delete(technique_id)
