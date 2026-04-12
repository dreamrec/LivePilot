"""Sample Engine MCP tools — 6 intelligence-layer tools.

No new Ableton communication — these orchestrate existing tools
through the analyzer, critics, planner, and technique library.
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp
from .models import SampleProfile, SampleIntent, SampleFitReport
from .analyzer import build_profile_from_filename
from .critics import run_all_sample_critics
from .planner import select_technique, compile_sample_plan
from .techniques import find_techniques, list_techniques, get_technique
from .sources import BrowserSource, FilesystemSource, FreesoundSource, build_search_queries


@mcp.tool()
async def analyze_sample(
    ctx: Context,
    file_path: Optional[str] = None,
    track_index: Optional[int] = None,
    clip_index: Optional[int] = None,
) -> dict:
    """Analyze a sample and build a complete SampleProfile.

    Detects material type, key, BPM, spectral character, and recommends
    Simpler mode, slice method, and warp mode. Provide either file_path
    OR track_index + clip_index to analyze a clip in the session.

    Falls back to filename-only analysis if M4L bridge unavailable.
    """
    if file_path is None and track_index is None:
        return {"error": "Provide either file_path or track_index + clip_index"}

    if track_index is not None and file_path is None:
        try:
            bridge = ctx.lifespan_context.get("m4l")
            if bridge:
                result = await bridge.send_command(
                    "get_clip_file_path", track_index, clip_index or 0
                )
                if not result.get("error"):
                    file_path = result.get("file_path")
        except Exception:
            pass

    if file_path is None:
        return {"error": "Could not determine file path — provide file_path directly"}

    source = "session_clip" if track_index is not None else "filesystem"
    profile = build_profile_from_filename(file_path, source=source)
    return profile.to_dict()


@mcp.tool()
def evaluate_sample_fit(
    ctx: Context,
    file_path: str,
    intent: str = "layer",
    philosophy: str = "auto",
) -> dict:
    """Run the 6-critic battery to evaluate how well a sample fits the current song.

    Returns overall score, per-critic scores, recommendations, and
    both surgeon (precise) and alchemist (transformative) plans.

    intent: rhythm, texture, layer, melody, vocal, atmosphere, transform
    philosophy: surgeon, alchemist, auto (context-decides)
    """
    profile = build_profile_from_filename(file_path)
    sample_intent = SampleIntent(
        intent_type=intent, philosophy=philosophy,
        description=f"Evaluate fitness for {intent}",
    )

    # Gather song context
    song_key = None
    session_tempo = 120.0
    existing_roles: list[str] = []

    try:
        ableton = ctx.lifespan_context["ableton"]
        info = ableton.send_command("get_session_info", {})
        session_tempo = info.get("tempo", 120.0)

        # Get track names as roles
        track_count = info.get("track_count", 0)
        for i in range(min(track_count, 16)):
            try:
                track_info = ableton.send_command("get_track_info", {"track_index": i})
                name = track_info.get("name", "").lower()
                if name:
                    existing_roles.append(name)
            except Exception:
                continue

        # Detect key from MIDI tracks
        try:
            from ..tools._theory_engine import detect_key
            for i in range(min(track_count, 8)):
                try:
                    clip_info = ableton.send_command("get_clip_info", {
                        "track_index": i, "clip_index": 0,
                    })
                    if clip_info.get("is_midi"):
                        notes_result = ableton.send_command("get_notes", {
                            "track_index": i, "clip_index": 0,
                        })
                        notes = notes_result.get("notes", [])
                        if notes:
                            key_result = detect_key(notes)
                            mode = key_result.get("mode", "")
                            mode_suffix = "m" if "minor" in mode else ""
                            song_key = f"{key_result['tonic_name']}{mode_suffix}"
                            break
                except Exception:
                    continue
        except ImportError:
            pass
    except Exception:
        pass

    critics = run_all_sample_critics(
        profile=profile,
        intent=sample_intent,
        song_key=song_key,
        session_tempo=session_tempo,
        existing_roles=existing_roles,
    )

    # Build both plans
    surgeon_plan = compile_sample_plan(
        profile,
        SampleIntent(intent_type=intent, philosophy="surgeon", description=""),
    )
    alchemist_plan = compile_sample_plan(
        profile,
        SampleIntent(intent_type=intent, philosophy="alchemist", description=""),
    )

    report = SampleFitReport(
        sample=profile,
        critics=critics,
        recommended_intent=intent,
        surgeon_plan=surgeon_plan,
        alchemist_plan=alchemist_plan,
        warnings=[c.recommendation for c in critics.values() if c.score < 0.5],
    )
    return report.to_dict()


@mcp.tool()
def search_samples(
    ctx: Context,
    query: str,
    material_type: Optional[str] = None,
    source: Optional[str] = None,
    max_results: int = 10,
) -> dict:
    """Search for samples across Ableton browser, local filesystem, and Freesound.

    query: search text like "dark vocal", "breakbeat", "foley metal"
    material_type: filter by type (vocal, drum_loop, texture, etc.)
    source: "browser", "filesystem", "freesound", or None for all
    max_results: maximum results to return (default 10)
    """
    results: list[dict] = []

    # Browser search
    if source in (None, "browser"):
        try:
            ableton = ctx.lifespan_context["ableton"]
            for path in ["samples", "drums", "user_library"]:
                try:
                    search_result = ableton.send_command("search_browser", {
                        "path": path,
                        "name_filter": query,
                        "loadable_only": True,
                        "max_results": max_results,
                    })
                    for item in search_result.get("results", []):
                        results.append({
                            "source": "browser",
                            "name": item.get("name", ""),
                            "uri": item.get("uri", ""),
                            "path": f"{path}/{item.get('name', '')}",
                        })
                except Exception:
                    continue
        except Exception:
            pass

    # Filesystem search
    if source in (None, "filesystem"):
        fs = FilesystemSource(scan_paths=[
            "~/Music", "~/Documents/Samples",
            "~/Documents/LivePilot/downloads",
        ])
        fs_results = fs.search(query, max_results=max_results)
        for candidate in fs_results:
            results.append(candidate.to_dict())

    # Freesound (metadata only — no download yet)
    if source in (None, "freesound"):
        fs_source = FreesoundSource()
        if fs_source.enabled:
            params = fs_source.build_search_params(query, max_results)
            results.append({
                "source": "freesound",
                "note": "Freesound search available — use API params below",
                "search_params": params,
            })

    return {
        "query": query,
        "result_count": len(results),
        "results": results[:max_results],
    }


@mcp.tool()
def suggest_sample_technique(
    ctx: Context,
    file_path: str,
    intent: str = "rhythm",
    philosophy: str = "auto",
    max_suggestions: int = 3,
) -> dict:
    """Suggest sample manipulation techniques from the technique library.

    Returns ranked techniques with executable step outlines for the
    given sample + intent combination.

    file_path: path to the sample
    intent: rhythm, texture, layer, melody, vocal, atmosphere, transform, challenge
    philosophy: surgeon, alchemist, auto
    """
    profile = build_profile_from_filename(file_path)
    sample_intent = SampleIntent(
        intent_type=intent, philosophy=philosophy, description="",
    )

    candidates = find_techniques(
        material_type=profile.material_type,
        intent=intent,
        philosophy=philosophy if philosophy != "auto" else None,
    )

    if not candidates:
        candidates = find_techniques(intent=intent)

    suggestions = []
    for t in candidates[:max_suggestions]:
        steps = compile_sample_plan(profile, sample_intent, technique=t)
        suggestions.append({
            "technique_id": t.technique_id,
            "name": t.name,
            "philosophy": t.philosophy,
            "difficulty": t.difficulty,
            "description": t.description,
            "inspiration": t.inspiration,
            "step_count": len(steps),
            "steps_preview": [s["description"] for s in steps[:5]],
        })

    return {
        "sample": profile.name,
        "material_type": profile.material_type,
        "intent": intent,
        "suggestion_count": len(suggestions),
        "suggestions": suggestions,
    }


@mcp.tool()
def plan_sample_workflow(
    ctx: Context,
    file_path: Optional[str] = None,
    search_query: Optional[str] = None,
    intent: str = "rhythm",
    philosophy: str = "auto",
    target_track: Optional[int] = None,
) -> dict:
    """Full end-to-end sample workflow: analyze, critique, select technique, compile plan.

    Provide file_path for a known sample, or search_query to find one.
    Returns a complete compiled plan ready for execution.

    intent: rhythm, texture, layer, melody, vocal, atmosphere, transform
    philosophy: surgeon, alchemist, auto
    target_track: existing track index, or None for new track
    """
    if file_path is None and search_query is None:
        return {"error": "Provide either file_path or search_query"}

    profile = None
    if file_path:
        profile = build_profile_from_filename(file_path)

    sample_intent = SampleIntent(
        intent_type=intent, philosophy=philosophy,
        description=search_query or f"Process {file_path} for {intent}",
        target_track=target_track,
    )

    if profile is None:
        # No file yet — return search guidance
        queries = build_search_queries(search_query or "", material_type=None)
        return {
            "status": "search_needed",
            "search_queries": queries,
            "intent": intent,
            "note": "Use search_samples to find a sample, then call again with file_path",
        }

    technique = select_technique(profile, sample_intent)
    plan = compile_sample_plan(profile, sample_intent, target_track=target_track,
                               technique=technique)

    return {
        "sample": profile.to_dict(),
        "intent": intent,
        "philosophy": philosophy,
        "technique": technique.name if technique else "fallback",
        "technique_id": technique.technique_id if technique else "",
        "step_count": len(plan),
        "compiled_plan": plan,
    }


@mcp.tool()
def get_sample_opportunities(ctx: Context) -> dict:
    """Analyze current song and identify where samples could improve it.

    Returns opportunities with suggested material types and techniques.
    Used by Wonder Mode diagnosis for sample-aware creative rescue.
    """
    opportunities: list[dict] = []

    try:
        ableton = ctx.lifespan_context["ableton"]
        info = ableton.send_command("get_session_info", {})
    except Exception:
        return {"opportunities": [], "note": "Cannot read session — Ableton not connected"}

    track_count = info.get("track_count", 0)
    track_names: list[str] = []
    has_sampler = False

    for i in range(min(track_count, 16)):
        try:
            track_info = ableton.send_command("get_track_info", {"track_index": i})
            name = track_info.get("name", "").lower()
            track_names.append(name)
            devices = track_info.get("devices", [])
            for d in devices:
                if d.get("class_name") in ("OriginalSimpler", "MultiSampler"):
                    has_sampler = True
        except Exception:
            continue

    # No organic texture
    has_organic = any(
        kw in name for name in track_names
        for kw in ("vocal", "sample", "foley", "field", "organic", "found")
    )
    if not has_organic and track_count >= 3:
        opportunities.append({
            "type": "no_organic_texture",
            "description": "No organic/sampled textures — all tracks appear synthesized",
            "suggested_material": ["vocal", "foley", "texture"],
            "suggested_techniques": ["vocal_chop_rhythm", "phone_recording_texture", "tail_harvest"],
            "confidence": 0.6,
        })

    # Limited drum variety
    drum_tracks = [n for n in track_names if any(
        kw in n for kw in ("drum", "beat", "perc", "kick", "snare")
    )]
    if len(drum_tracks) <= 1 and track_count >= 4:
        opportunities.append({
            "type": "drum_variety_needed",
            "description": "Limited percussion variety — layer a break or add ghost notes",
            "suggested_material": ["drum_loop"],
            "suggested_techniques": ["break_layering", "ghost_note_texture"],
            "confidence": 0.5,
        })

    # No Simpler/Sampler devices
    if not has_sampler and track_count >= 2:
        opportunities.append({
            "type": "no_sample_instruments",
            "description": "No Simpler/Sampler devices — samples could add character",
            "suggested_material": ["vocal", "instrument_loop", "one_shot"],
            "suggested_techniques": ["syllable_instrument", "slice_and_sequence"],
            "confidence": 0.4,
        })

    return {
        "opportunity_count": len(opportunities),
        "opportunities": opportunities,
        "track_count": track_count,
    }
