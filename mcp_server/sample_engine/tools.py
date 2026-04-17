"""Sample Engine MCP tools — intelligence-layer tools.

Wraps analyzer, critics, planner, technique library, and (as of v1.10.5)
direct Splice online catalog hunt/download via the gRPC client.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastmcp import Context

from ..server import mcp

logger = logging.getLogger(__name__)
from .models import SampleProfile, SampleIntent, SampleFitReport
from .analyzer import build_profile_from_filename
from .critics import run_all_sample_critics
from .planner import select_technique, compile_sample_plan
from .techniques import find_techniques, list_techniques, get_technique
from .sources import BrowserSource, FilesystemSource, SpliceSource, build_search_queries


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
        except Exception as exc:
            logger.warning("m4l get_clip_file_path failed: %s", exc)

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
            except Exception as exc:
                logger.debug("get_track_info(%d) skipped: %s", i, exc)
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
                except Exception as exc:
                    logger.debug("key detection on track %d skipped: %s", i, exc)
                    continue
        except ImportError:
            pass
    except Exception as exc:
        logger.warning("session context for evaluate_sample_fit failed: %s", exc)

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
async def search_samples(
    ctx: Context,
    query: str,
    material_type: Optional[str] = None,
    key: Optional[str] = None,
    bpm_range: Optional[str] = None,
    source: Optional[str] = None,
    max_results: int = 10,
) -> dict:
    """Search for samples across Splice library, Ableton browser, and local filesystem.

    Searches all enabled sources in parallel and ranks results.
    Splice results include rich metadata (key, BPM, genre, tags, pack info).

    When the Splice desktop app is running AND grpcio is installed, this
    searches Splice's ONLINE catalog (19,690+ hits for a generic query)
    and returns un-downloaded items alongside local files. When gRPC is
    unavailable, it falls back to the local SQLite index and only returns
    already-downloaded samples.

    query: search text like "dark vocal", "breakbeat", "foley metal"
    material_type: filter by type (vocal, drum_loop, texture, etc.)
    key: prefer samples in this key (e.g., "Cm", "F#")
    bpm_range: "min-max" BPM range (e.g., "120-130")
    source: "splice", "browser", "filesystem", or None for all
    max_results: maximum results to return (default 10)
    """
    results: list[dict] = []

    # Parse BPM range
    bpm_min, bpm_max = None, None
    if bpm_range:
        parts = bpm_range.replace(" ", "").split("-")
        if len(parts) == 2:
            try:
                bpm_min, bpm_max = float(parts[0]), float(parts[1])
            except ValueError:
                pass

    # Splice search — prefer gRPC online catalog when available, fall back
    # to local SQLite index. See docs/2026-04-14-bugs-discovered.md — P0-2.
    if source in (None, "splice"):
        grpc_client = None
        try:
            grpc_client = ctx.lifespan_context.get("splice_client")
        except AttributeError:
            grpc_client = None

        used_grpc = False
        if grpc_client is not None and getattr(grpc_client, "connected", False):
            try:
                grpc_result = await grpc_client.search_samples(
                    query=query,
                    key=(key or "").lower().rstrip("m") if key else "",
                    bpm_min=int(bpm_min) if bpm_min else 0,
                    bpm_max=int(bpm_max) if bpm_max else 0,
                    per_page=max_results,
                    page=1,
                    purchased_only=False,
                )
                for s in grpc_result.samples[:max_results]:
                    results.append({
                        "source": "splice",
                        "name": s.filename,
                        "file_path": s.local_path or None,
                        "uri": None,
                        "freesound_id": None,
                        "relevance_score": 0,
                        "source_priority": 1,
                        "splice_catalog": True,
                        "downloaded": bool(s.local_path),
                        "file_hash": s.file_hash,
                        "metadata": {
                            "key": s.audio_key,
                            "bpm": s.bpm,
                            "tags": ",".join(s.tags) if s.tags else "",
                            "genre": s.genre or None,
                            "sample_type": s.sample_type,
                            "material_type": "vocal" if "vocal" in (s.tags or []) else "unknown",
                            "pack": s.provider_name,
                            "pack_uuid": s.pack_uuid,
                            "duration": s.duration_ms / 1000.0 if s.duration_ms else 0.0,
                            "is_premium": s.is_premium,
                            "chord_type": s.chord_type,
                        },
                    })
                used_grpc = True
            except Exception as exc:
                logger.warning("Splice gRPC search failed, falling back to SQL: %s", exc)
                used_grpc = False

        # Also query local index (if not already covered by gRPC) to surface
        # downloaded-only samples that might not appear in catalog results.
        if not used_grpc:
            splice = SpliceSource()
            if splice.enabled:
                splice_results = splice.search(
                    query=query,
                    max_results=max_results,
                    key=key,
                    bpm_min=bpm_min,
                    bpm_max=bpm_max,
                )
                for candidate in splice_results:
                    d = candidate.to_dict()
                    d["source_priority"] = 1
                    results.append(d)

    # Browser search
    if source in (None, "browser"):
        try:
            ableton = ctx.lifespan_context["ableton"]
            browser = BrowserSource()
            for category in browser.DEFAULT_CATEGORIES:
                try:
                    search_result = ableton.send_command("search_browser", {
                        "path": category,
                        "name_filter": query,
                        "loadable_only": True,
                        "max_results": max_results,
                    })
                    raw = search_result.get("results", [])
                    parsed = browser.parse_results(raw, category)
                    for candidate in parsed:
                        d = candidate.to_dict()
                        d["source_priority"] = 2
                        results.append(d)
                except Exception as exc:
                    logger.debug("browser search %s skipped: %s", category, exc)
                    continue
        except Exception as exc:
            logger.warning("browser search unavailable: %s", exc)

    # Filesystem search
    if source in (None, "filesystem"):
        fs = FilesystemSource(scan_paths=[
            "~/Music", "~/Documents/Samples",
            "~/Documents/LivePilot/downloads",
        ])
        fs_results = fs.search(query, max_results=max_results)
        for candidate in fs_results:
            d = candidate.to_dict()
            d["source_priority"] = 3
            results.append(d)

    # Sort by source priority (Splice first), then by relevance
    results.sort(key=lambda r: r.get("source_priority", 9))

    # Build summary
    source_counts = {}
    for r in results:
        src = r.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    return {
        "query": query,
        "result_count": len(results[:max_results]),
        "source_counts": source_counts,
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
    section_type: Optional[str] = None,
    desired_role: Optional[str] = None,
) -> dict:
    """Full end-to-end sample workflow: analyze, critique, select technique, compile plan.

    Provide file_path for a known sample, or search_query to find one.
    Returns a complete compiled plan ready for execution.

    intent: rhythm, texture, layer, melody, vocal, atmosphere, transform
    philosophy: surgeon, alchemist, auto
    target_track: existing track index, or None for new track
    section_type: optional section context (intro, verse, chorus, drop, etc.)
    desired_role: optional sample role (hook_sample, texture_bed, break_layer, etc.)
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
    except Exception as exc:
        logger.warning("get_sample_opportunities: Ableton not reachable: %s", exc)
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
        except Exception as exc:
            logger.debug("track scan idx=%d skipped: %s", i, exc)
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


@mcp.tool()
def plan_slice_workflow(
    ctx: Context,
    file_path: Optional[str] = None,
    track_index: Optional[int] = None,
    device_index: int = 0,
    intent: str = "rhythm",
    target_section: Optional[str] = None,
    target_track: Optional[int] = None,
    bars: int = 4,
    style_hint: str = "",
) -> dict:
    """Plan an end-to-end slice workflow for a sample.

    Generates a Simpler slice strategy, MIDI note mapping, and starter
    pattern based on musical intent. Returns a compiled workflow plan —
    does NOT execute. The agent steps through each tool call in sequence.

    Provide either file_path (new sample to load) or track_index +
    device_index (existing Simpler with loaded sample).

    intent: rhythm | hook | texture | percussion | melodic
    bars: number of bars for the pattern (default 4)
    target_section: optional section name for arrangement hints
    style_hint: optional genre/style context (e.g. "dilla", "burial")
    """
    from .slice_workflow import plan_slice_steps

    # Determine slice count — default 8 for file-based, or would come from
    # get_simpler_slices in a real execution
    # Read tempo from session if connected, otherwise default
    tempo = 120.0
    try:
        ableton = ctx.lifespan_context.get("ableton")
        if ableton:
            info = ableton.send_command("get_session_info", {})
            tempo = float(info.get("tempo", 120.0))
    except Exception as exc:
        logger.debug("plan_slice_workflow tempo fetch failed (using 120): %s", exc)

    # Read slice count from existing Simpler if track provided
    slice_count = 8  # Default transient slice count
    if track_index is not None:
        try:
            ableton = ctx.lifespan_context.get("ableton")
            if ableton:
                slices = ableton.send_command("get_simpler_slices", {
                    "track_index": track_index, "device_index": device_index,
                })
                if isinstance(slices, dict) and slices.get("slice_count"):
                    slice_count = slices["slice_count"]
        except Exception as exc:
            logger.debug("get_simpler_slices failed (using default 8): %s", exc)

    # Build the plan
    plan = plan_slice_steps(
        slice_count=slice_count,
        intent=intent,
        bars=bars,
        tempo=tempo,
        track_index=target_track if target_track is not None else 0,
    )

    # Prepend sample loading steps if file_path provided
    if file_path:
        load_steps = [
            {
                "tool": "create_midi_track",
                "params": {"name": f"Slice {intent.title()}"},
                "description": "Create track for sliced sample",
            },
            {
                "tool": "load_sample_to_simpler",
                "params": {"track_index": target_track or 0, "file_path": file_path},
                "description": f"Load sample into Simpler: {file_path}",
            },
            {
                "tool": "set_simpler_playback_mode",
                "params": {"track_index": target_track or 0, "device_index": 0, "playback_mode": 2},
                "description": "Set Simpler to Slice mode",
            },
        ]
        plan["steps"] = load_steps + plan["steps"]

    # Add arrangement hints if section provided
    if target_section:
        plan["arrangement_hints"] = {
            "target_section": target_section,
            "suggested_placement": f"Place slice pattern in {target_section}",
        }

    plan["file_path"] = file_path
    plan["track_index"] = track_index
    plan["device_index"] = device_index
    plan["style_hint"] = style_hint

    return plan


# ── v1.10.5 Splice online catalog tools ───────────────────────────────────
#
# These expose the SpliceGRPCClient's catalog capabilities as first-class MCP
# tools so the agent can drive hunt→download→load without a standalone helper
# script. See docs/2026-04-14-bugs-discovered.md — P0-2.
#
# Prerequisites:
#   - Splice desktop app running (port.conf present in ~/Library/Application
#     Support/com.splice.Splice/)
#   - grpcio and protobuf installed (added to requirements.txt in v1.10.5)
#
# Credit model (as of 2026-04-14):
#   - Even with `SoundsStatus: subscribed`, the gRPC `DownloadSample` endpoint
#     always decrements a monthly credit counter (default 100/month on most
#     subscription plans).
#   - The "unlimited downloads in Ableton" the Splice marketing references
#     only applies to the Splice Sounds.vst3 plugin, which uses a different
#     HTTPS API that these tools cannot drive.
#   - `CREDIT_HARD_FLOOR = 5` in client.py reserves 5 credits as a safety
#     margin — downloads will refuse below the floor.


_SPLICE_USER_LIB_DEST = "~/Music/Ableton/User Library/Samples/Splice"


@mcp.tool()
async def get_splice_credits(ctx: Context) -> dict:
    """Get the user's current Splice credit balance and subscription tier.

    Returns: {
        "connected": bool,        # whether Splice desktop gRPC is reachable
        "username": str,
        "plan": str,              # e.g. "subscribed", "free"
        "credits_remaining": int,
        "credit_floor": int,      # safety reserve (typically 5)
        "can_download": bool,     # credits_remaining > credit_floor
    }

    Returns connected=False (with zero credits) when the Splice desktop app
    isn't running or grpcio isn't installed.
    """
    from ..splice_client.client import CREDIT_HARD_FLOOR

    client = None
    try:
        client = ctx.lifespan_context.get("splice_client")
    except AttributeError:
        pass

    if client is None or not getattr(client, "connected", False):
        return {
            "connected": False,
            "username": "",
            "plan": "",
            "credits_remaining": 0,
            "credit_floor": CREDIT_HARD_FLOOR,
            "can_download": False,
            "hint": (
                "Splice gRPC not connected. Ensure Splice desktop app is "
                "running and grpcio+protobuf are installed in the LivePilot "
                "venv (pip install grpcio protobuf)."
            ),
        }

    try:
        info = await client.get_credits()
    except Exception as exc:
        return {
            "connected": False,
            "error": f"get_credits failed: {exc}",
            "credit_floor": CREDIT_HARD_FLOOR,
        }

    remaining = int(info.credits)
    return {
        "connected": True,
        "username": info.username,
        "plan": info.plan,
        "credits_remaining": remaining,
        "credit_floor": CREDIT_HARD_FLOOR,
        "can_download": remaining > CREDIT_HARD_FLOOR,
    }


@mcp.tool()
async def splice_catalog_hunt(
    ctx: Context,
    query: str,
    bpm_min: int = 0,
    bpm_max: int = 0,
    key: str = "",
    sample_type: str = "",
    genre: str = "",
    per_page: int = 10,
    page: int = 1,
) -> dict:
    """Search Splice's ONLINE catalog via gRPC.

    Unlike `search_samples` which can fall back to the local SQLite index,
    this tool ONLY queries the online catalog — if Splice isn't connected
    it returns an error instead of local-only results. Use this when you
    specifically want fresh catalog content.

    query:       free-text search ("mellotron", "lofi chord", "soul vocal")
    bpm_min:     minimum BPM (0 = no lower bound)
    bpm_max:     maximum BPM (0 = no upper bound)
    key:         musical key (e.g. "cm", "f#", "a")
    sample_type: "loop", "oneshot", or "" for any
    genre:       genre filter (e.g. "hip hop", "ambient")
    per_page:    results per page (1-50)
    page:        page number (1-indexed)

    Returns: {
        "connected": bool,
        "total_hits": int,       # total catalog matches
        "samples": [...],        # sample metadata with file_hash for download
    }

    Each sample entry contains `file_hash` which you can pass to
    `splice_download_sample` to trigger a download.
    """
    client = None
    try:
        client = ctx.lifespan_context.get("splice_client")
    except AttributeError:
        pass

    if client is None or not getattr(client, "connected", False):
        return {
            "connected": False,
            "error": "Splice gRPC not connected",
            "hint": (
                "Ensure Splice desktop app is running. Also verify grpcio "
                "and protobuf are installed: `pip install grpcio protobuf`."
            ),
            "samples": [],
            "total_hits": 0,
        }

    try:
        result = await client.search_samples(
            query=query,
            key=key.lower().rstrip("m") if key else "",
            chord_type="minor" if key and key.lower().endswith("m") else "",
            bpm_min=int(bpm_min),
            bpm_max=int(bpm_max),
            sample_type=sample_type,
            genre=genre,
            per_page=max(1, min(per_page, 50)),
            page=max(1, int(page)),
            purchased_only=False,
        )
    except Exception as exc:
        return {
            "connected": False,
            "error": f"Splice search failed: {exc}",
            "samples": [],
        }

    samples_out = []
    for s in result.samples:
        samples_out.append({
            "file_hash": s.file_hash,
            "filename": s.filename,
            "key": s.audio_key,
            "chord_type": s.chord_type,
            "bpm": s.bpm,
            "duration_sec": round((s.duration_ms or 0) / 1000.0, 2),
            "genre": s.genre,
            "sample_type": s.sample_type,
            "tags": list(s.tags) if s.tags else [],
            "pack": s.provider_name,
            "pack_uuid": s.pack_uuid,
            "is_premium": bool(s.is_premium),
            "is_downloaded": bool(s.local_path),
            "local_path": s.local_path or None,
            "preview_url": s.preview_url,
        })

    return {
        "connected": True,
        "query": query,
        "total_hits": result.total_hits,
        "returned": len(samples_out),
        "samples": samples_out,
        "matching_tags": dict(result.matching_tags) if result.matching_tags else {},
    }


@mcp.tool()
async def splice_download_sample(
    ctx: Context,
    file_hash: str,
    copy_to_user_library: bool = True,
) -> dict:
    """Download a Splice sample by file_hash (costs 1 credit).

    Use `splice_catalog_hunt` first to find samples and get their file_hash.
    This tool will:
      1. Check credit balance against the safety floor (refuses if < 5)
      2. Trigger the download via the Splice desktop gRPC
      3. Poll until the file appears on disk (up to 30s)
      4. Optionally copy the file into `~/Music/Ableton/User Library/Samples/
         Splice/` so Ableton's browser indexes it — this makes the sample
         loadable via `load_browser_item` with a `query:UserLibrary#Samples:...`
         URI.

    Returns: {
        "ok": bool,
        "local_path": str,              # Splice's own download path
        "user_library_path": str,       # if copy_to_user_library=True
        "browser_uri": str,             # ready for load_browser_item
        "credits_remaining": int,
    }

    Note: even with an "unlimited" subscription, this gRPC path always
    decrements credits (typically 100/month allotment). The unlimited
    downloads inside Ableton's Splice Sounds VST3 use a different API
    that LivePilot cannot drive programmatically yet.
    """
    import shutil

    client = None
    try:
        client = ctx.lifespan_context.get("splice_client")
    except AttributeError:
        pass

    if client is None or not getattr(client, "connected", False):
        return {
            "ok": False,
            "error": "Splice gRPC not connected",
        }

    # Credit safety check
    try:
        can, remaining = await client.can_afford(1, budget=10)
    except Exception as exc:
        return {"ok": False, "error": f"Credit check failed: {exc}"}
    if not can:
        return {
            "ok": False,
            "error": (
                f"Credit safety floor hit (remaining={remaining}, "
                f"hard floor=5). Skipping download."
            ),
            "credits_remaining": remaining,
        }

    # Trigger download
    try:
        local_path = await client.download_sample(file_hash, timeout=30.0)
    except Exception as exc:
        return {"ok": False, "error": f"Download failed: {exc}"}

    if not local_path:
        return {
            "ok": False,
            "error": "Download did not complete within 30s timeout",
        }

    response: dict = {
        "ok": True,
        "local_path": local_path,
        "filename": os.path.basename(local_path),
    }

    # Copy into User Library so Ableton's browser indexes it
    if copy_to_user_library:
        dest_dir = os.path.expanduser(_SPLICE_USER_LIB_DEST)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, os.path.basename(local_path))
            if not os.path.exists(dest_path):
                shutil.copy2(local_path, dest_path)
            response["user_library_path"] = dest_path
            # URI format Ableton uses for user_library samples
            response["browser_uri"] = (
                f"query:UserLibrary#Samples:Splice:{os.path.basename(local_path)}"
            )
        except Exception as exc:
            response["copy_warning"] = f"Failed to copy to User Library: {exc}"

    # Post-credit count
    try:
        info = await client.get_credits()
        response["credits_remaining"] = int(info.credits)
    except Exception as exc:
        logger.warning("post-download credit check failed: %s", exc)

    return response
