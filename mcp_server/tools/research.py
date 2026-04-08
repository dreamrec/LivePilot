"""Research MCP tools — targeted and deep technique research.

2 tools that connect the research engine (_research_engine.py) to the
live session context via device atlas and memory.

  research_technique — search corpus + memory for production answers
  deep_research — multi-source synthesis (adds web if available)
"""

from __future__ import annotations

import json
from typing import Optional

from fastmcp import Context

from ..server import mcp
from . import _research_engine as research_engine


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


@mcp.tool()
def research_technique(
    ctx: Context,
    query: str,
    scope: str = "targeted",
) -> dict:
    """Research a production technique — search device atlas + memory for answers.

    Synthesizes findings from the device atlas (built-in device knowledge),
    technique memory (past session learnings), and reference corpus into
    a structured TechniqueCard with devices, method, and verification steps.

    query: what you want to learn (e.g., "how to sidechain bass to kick")
    scope: "targeted" (device atlas + memory) or "deep" (adds web search)

    Returns: findings ranked by relevance, synthesized technique card, confidence.
    """
    if not query or not query.strip():
        return {"error": "query cannot be empty"}

    if scope not in ("targeted", "deep"):
        return {"error": f"scope must be 'targeted' or 'deep', got '{scope}'"}

    ableton = _get_ableton(ctx)

    # 1. Analyze query to predict relevant devices
    query_info = research_engine.analyze_query(query)

    # 2. Search device atlas for relevant devices
    device_atlas_results = []
    for device_name in query_info.get("likely_devices", [])[:5]:
        try:
            ref = ableton.send_command("search_browser", {"query": device_name, "category": "instruments"})
            if ref and not ref.get("error"):
                device_atlas_results.append(ref)
        except Exception:
            pass

    # 3. Search memory for related techniques
    memory_results = []
    try:
        # Search technique cards
        mem = ableton.send_command("memory_list", {
            "type": "technique_card",
            "limit": 10,
            "sort_by": "updated_at",
        })
        memory_results.extend(mem.get("techniques", []))
    except Exception:
        pass

    try:
        # Also search research memories
        mem = ableton.send_command("memory_list", {
            "type": "research",
            "limit": 5,
            "sort_by": "updated_at",
        })
        memory_results.extend(mem.get("techniques", []))
    except Exception:
        pass

    if scope == "targeted":
        result = research_engine.targeted_research(
            query, device_atlas_results, memory_results,
        )
    else:
        # Deep research — try to get web results
        # Note: web search requires external integration (graceful degradation)
        result = research_engine.deep_research(
            query,
            web_results=[],  # Web search injected by agent if available
            device_atlas_results=device_atlas_results,
            memory_results=memory_results,
        )

    return result.to_dict()


@mcp.tool()
def get_emotional_arc(ctx: Context) -> dict:
    """Analyze the emotional arc of the arrangement — tension, climax, resolution.

    Checks for: monotone energy, all-climax (no rest), build without payoff,
    no resolution at the end, peak too early.

    Returns: tension curve and issues with recommended composition moves.
    """
    from . import _composition_engine as engine

    ableton = _get_ableton(ctx)
    session = ableton.send_command("get_session_info")
    scenes = session.get("scenes", [])
    tracks = session.get("tracks", [])
    track_count = session.get("track_count", 0)

    # Build section graph
    from .composition import _build_clip_matrix
    clip_matrix = _build_clip_matrix(ableton, len(scenes), track_count)
    sections = engine.build_section_graph_from_scenes(scenes, clip_matrix, track_count)

    if len(sections) < 3:
        return {
            "issues": [],
            "tension_curve": [],
            "note": "Need at least 3 sections for emotional arc analysis",
        }

    # Try to build harmony fields for richer analysis
    harmony_fields = []
    for i, section in enumerate(sections):
        hf = engine.HarmonyField(section_id=section.section_id)
        # Try to get harmony data
        for t_idx in section.tracks_active[:3]:
            try:
                si = ableton.send_command("identify_scale", {
                    "track_index": t_idx, "clip_index": i,
                })
                if si.get("top_match"):
                    hf.key = si["top_match"].get("tonic", "")
                    hf.mode = si["top_match"].get("mode", "")
                    hf.confidence = si["top_match"].get("confidence", 0.0)
                    break
            except Exception:
                continue
        harmony_fields.append(hf)

    issues = engine.run_emotional_arc_critic(sections, harmony_fields)

    # Build tension curve for visualization
    tension_curve = []
    for section in sections:
        hf_match = next((hf for hf in harmony_fields if hf.section_id == section.section_id), None)
        instability = hf_match.instability if hf_match else 0.3
        tension = round(section.energy * 0.5 + section.density * 0.3 + instability * 0.2, 3)
        tension_curve.append({
            "section": section.name or section.section_id,
            "section_type": section.section_type.value,
            "tension": tension,
            "energy": section.energy,
            "density": section.density,
        })

    return {
        "tension_curve": tension_curve,
        "issues": [i.to_dict() for i in issues],
        "issue_count": len(issues),
        "section_count": len(sections),
    }


# ── get_style_tactics (Round 4) ─────────────────────────────────────


@mcp.tool()
def get_style_tactics(
    ctx: Context,
    artist_or_genre: str,
) -> dict:
    """Get production tactics for a specific artist style or genre.

    Returns structured recipe cards with device chains, arrangement patterns,
    automation gestures, and verification steps.

    artist_or_genre: e.g., "burial", "techno", "daft punk", "ambient", "trap"

    Returns: list of StyleTactic cards with actionable production instructions.
    """
    if not artist_or_genre or not artist_or_genre.strip():
        return {"error": "artist_or_genre cannot be empty"}

    ableton = _get_ableton(ctx)

    # Search user memory for saved tactics
    memory_tactics = []
    try:
        mem = ableton.send_command("memory_list", {
            "type": "style_tactic",
            "limit": 10,
        })
        memory_tactics = mem.get("techniques", [])
    except Exception:
        pass

    tactics = research_engine.get_style_tactics(artist_or_genre, memory_tactics)

    if not tactics:
        return {
            "query": artist_or_genre,
            "tactics": [],
            "note": f"No tactics found for '{artist_or_genre}'. "
                    f"Available built-in styles: burial, daft punk, techno, ambient, trap, lo-fi",
        }

    return {
        "query": artist_or_genre,
        "tactics": [t.to_dict() for t in tactics],
        "tactic_count": len(tactics),
    }
