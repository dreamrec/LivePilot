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

        # Detect key from MIDI tracks.
        # BUG-B37 fix: the old code checked clip_info.get("is_midi") but
        # the Remote Script returns is_midi_clip (different field name),
        # so the check always failed and song_key stayed None —
        # key_fit then reported "Song key unknown" even on obvious
        # Dm sessions. Now we check both field names for safety AND
        # aggregate notes from all harmonic tracks via harmonic_score
        # (Batch 5 helper), so key detection uses the richest signal.
        try:
            from ..tools._theory_engine import detect_key
            from ..tools._composition_engine.harmony import harmonic_score

            # Collect all tracks' notes, scored by harmonic-ness
            harmonic_pool: list[dict] = []
            for i in range(min(track_count, 16)):
                try:
                    clip_info = ableton.send_command("get_clip_info", {
                        "track_index": i, "clip_index": 0,
                    })
                except Exception as exc:
                    logger.debug("get_clip_info(%d) skipped: %s", i, exc)
                    continue
                # Accept either the new is_midi_clip field or the legacy
                # is_midi (in case some install combines versions)
                is_midi = (
                    clip_info.get("is_midi_clip")
                    or clip_info.get("is_midi")
                    or False
                )
                if not is_midi:
                    continue
                try:
                    notes_result = ableton.send_command("get_notes", {
                        "track_index": i, "clip_index": 0,
                    })
                except Exception as exc:
                    logger.debug("get_notes(%d) skipped: %s", i, exc)
                    continue
                notes = notes_result.get("notes", []) if isinstance(
                    notes_result, dict
                ) else []
                if not notes:
                    continue
                track_name = (
                    existing_roles[i] if i < len(existing_roles) else ""
                )
                if harmonic_score(notes, track_name) >= 0.3:
                    harmonic_pool.extend(notes)

            if harmonic_pool:
                key_result = detect_key(harmonic_pool)
                mode = key_result.get("mode", "")
                mode_suffix = "m" if "minor" in mode else ""
                song_key = f"{key_result['tonic_name']}{mode_suffix}"
        except ImportError:
            pass
        except Exception as exc:
            logger.debug("key aggregation failed: %s", exc)
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
    free_only: bool = False,
    q: Optional[str] = None,
    collection_uuid: str = "",
) -> dict:
    """Search for samples across Splice library, Ableton browser, and local filesystem.

    Searches all enabled sources in parallel and ranks results.
    Splice results include rich metadata (key, BPM, genre, tags, pack info,
    is_premium, price, is_free, preview_url).

    When the Splice desktop app is running AND grpcio is installed, this
    searches Splice's ONLINE catalog (19,690+ hits for a generic query)
    and returns un-downloaded items alongside local files. When gRPC is
    unavailable, it falls back to the local SQLite index and only returns
    already-downloaded samples.

    query: search text like "dark vocal", "breakbeat", "foley metal"
    q: alias for `query` (accepts either name for ergonomics)
    material_type: filter by type (vocal, drum_loop, texture, etc.)
    key: prefer samples in this key (e.g., "Cm", "F#")
    bpm_range: "min-max" BPM range (e.g., "120-130")
    source: "splice", "browser", "filesystem", or None for all
    collection_uuid: scope Splice results to a user collection (Likes,
      bass, keys, etc.). Obtain via splice_list_collections. When set,
      browser/filesystem sources are skipped — this is taste-scoped search.
    max_results: maximum results to return (default 10)
    free_only: if True, only return samples that cost nothing to license
      (IsPremium=False or Price=0). Under the Ableton Live plan these
      don't deplete the daily quota; under credit-metered plans they
      bypass the credit floor.
    """
    # Accept `q` as an alias for `query` — BUG-FIX #4 from 2026-04-22 bug doc.
    if not query and q:
        query = q
    if not query:
        return {"error": "query is required (or use `q` alias)"}
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

    # When scoped to a Splice collection, force source=splice and skip
    # browser/filesystem since those don't carry collection metadata.
    if collection_uuid and source is None:
        source = "splice"

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
                    collection_uuid=collection_uuid,
                )
                for s in grpc_result.samples[:max_results]:
                    if free_only and not s.is_free:
                        continue
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
                        "preview_url": s.preview_url,
                        "is_free": s.is_free,
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
                            "price": s.price,
                            "is_free": s.is_free,
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
# Credit model (corrected 2026-04-22 — see project_splice_subscription_model.md):
# Splice has a TWO-POCKET model that our earlier code conflated:
#
#   1. Daily sample quota — 100/day unmetered on the Splice x Ableton Live plan
#      ($12.99/mo). Sample downloads deplete this counter, NOT credits.
#      Resets at UTC midnight. We track locally in ~/.livepilot/splice_quota.json
#      (see splice_client/quota.py) and warn at 90/100.
#
#   2. Splice.com credits — used for presets, MIDI, Splice Instrument content.
#      ALL plans have some credits (100 intro on Ableton Live, or monthly
#      allotment on Creator/Sounds+). CREDIT_HARD_FLOOR = 5 keeps a safety
#      reserve so agents can't drain you to zero.
#
# Free samples (Sample.IsPremium=False or Price=0) bypass BOTH gates — they're
# free under any plan.
#
# `SpliceGRPCClient.decide_download()` runs the full gating logic and returns
# a DownloadDecision with plan_kind and gating_mode. Use that, not the raw
# credit check, for any new download path.


_SPLICE_USER_LIB_DEST = "~/Music/Ableton/User Library/Samples/Splice"
_SPLICE_PREVIEW_CACHE = "~/Library/Caches/LivePilot/splice_previews"


@mcp.tool()
async def get_splice_credits(ctx: Context) -> dict:
    """Get the user's current Splice plan, credits, and daily sample quota.

    Returns both pockets of the Splice subscription model:
      - `credits_remaining`: Splice.com credits for presets/MIDI/Instrument
      - `daily_quota`: sample-download counter (Ableton Live plan only)

    Example (Ableton Live plan):
      {
        "connected": true,
        "username": "user-1367453956",
        "plan_raw": "subscribed",
        "plan_kind": "ableton_live",
        "sounds_plan_id": 12,
        "features": {"ableton_unmetered": true, ...},
        "credits_remaining": 80,
        "credit_floor": 5,
        "daily_quota": {
            "used_today": 3, "remaining_today": 97, "daily_limit": 100,
            "near_limit": false, "at_limit": false,
        },
        "can_download_sample": true,
        "download_gating": "daily_quota",  # or "credit_floor"
      }

    Returns connected=False (with zero credits) when the Splice desktop app
    isn't running or grpcio isn't installed.
    """
    from ..splice_client.client import CREDIT_HARD_FLOOR
    from ..splice_client.models import PlanKind
    from ..splice_client.quota import get_tracker

    client = None
    try:
        client = ctx.lifespan_context.get("splice_client")
    except AttributeError:
        pass

    quota_summary = get_tracker().summary()

    if client is None or not getattr(client, "connected", False):
        return {
            "connected": False,
            "username": "",
            "plan_raw": "",
            "plan_kind": PlanKind.UNKNOWN.value,
            "credits_remaining": 0,
            "credit_floor": CREDIT_HARD_FLOOR,
            "daily_quota": quota_summary,
            "can_download_sample": False,
            "download_gating": "blocked",
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
            "daily_quota": quota_summary,
        }

    remaining = int(info.credits)
    plan = info.plan_kind

    # Compute `can_download_sample` using the same logic decide_download uses.
    if plan == PlanKind.ABLETON_LIVE:
        gating = "daily_quota"
        can_download = not quota_summary["at_limit"]
    else:
        gating = "credit_floor"
        can_download = remaining > CREDIT_HARD_FLOOR

    return {
        "connected": True,
        "username": info.username,
        "plan_raw": info.plan,
        "plan_kind": plan.value,
        "sounds_plan_id": info.sounds_plan_id,
        "features": info.features,
        "user_uuid": info.user_uuid,
        "credits_remaining": remaining,
        "credit_floor": CREDIT_HARD_FLOOR,
        "daily_quota": quota_summary,
        "can_download_sample": can_download,
        "download_gating": gating,
        "note": (
            "This plan gets 100 samples/day unmetered via drag-drop; "
            "the 80 credits are for presets/MIDI only."
            if plan == PlanKind.ABLETON_LIVE
            else None
        ),
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
    free_only: bool = False,
    collection_uuid: str = "",
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
            collection_uuid=collection_uuid,
        )
    except Exception as exc:
        return {
            "connected": False,
            "error": f"Splice search failed: {exc}",
            "samples": [],
        }

    samples_out = []
    for s in result.samples:
        if free_only and not s.is_free:
            continue
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
            "price": int(s.price),
            "is_free": s.is_free,
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
    force: bool = False,
) -> dict:
    """Download a Splice sample by file_hash — plan-aware gating.

    Use `splice_catalog_hunt` or `search_samples` first to find samples
    and their `file_hash`. The gating logic runs BEFORE any network call:

    - Ableton Live plan: uses your 100/day unmetered quota (not credits).
      Tracked locally in ~/.livepilot/splice_quota.json so repeated runs
      warn at 90/100 and refuse at 100 (resets at UTC midnight).
    - Credit-metered plans (Sounds+/Creator): enforces CREDIT_HARD_FLOOR=5
      so the agent can't drain your monthly allotment.
    - Free samples (IsPremium=False or Price=0): bypass both gates.

    Arguments:
      file_hash: the sample identifier from search results
      copy_to_user_library: if True (default), also copies to
        ~/Music/Ableton/User Library/Samples/Splice/ so Ableton's browser
        can reach it via `load_browser_item` with a `query:UserLibrary#...`
        URI.
      force: bypass local quota checks (still honors server-side limits).
        Use for deterministic tests — NOT for production flows.

    Returns: {
      "ok": bool,
      "local_path": str,              # Splice's own download path
      "user_library_path": str,       # if copy_to_user_library=True
      "browser_uri": str,             # ready for load_browser_item
      "decision": {...},              # plan-aware gating summary
      "credits_remaining": int,
      "daily_quota": {...},           # post-download quota snapshot
    }
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

    # Try to fetch the sample metadata so we can detect free samples and
    # bypass gating when Price=0. This is one extra round-trip but saves
    # credits/quota for catalog items marked free.
    sample = None
    try:
        sample = await client.get_sample_info(file_hash)
    except Exception as exc:
        logger.debug("get_sample_info failed pre-gating: %s", exc)

    # Run the full gating logic before touching the network.
    if not force:
        try:
            decision = await client.decide_download(file_hash, sample=sample)
        except Exception as exc:
            return {"ok": False, "error": f"Gating check failed: {exc}"}
        if not decision.allowed:
            return {
                "ok": False,
                "error": decision.reason,
                "decision": decision.to_dict(),
            }
    else:
        decision = None

    # Trigger download (client.download_sample also re-runs the gate defensively)
    try:
        local_path = await client.download_sample(
            file_hash, timeout=30.0, sample=sample,
        )
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
        "decision": decision.to_dict() if decision else None,
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

    # Post-download state
    try:
        from ..splice_client.quota import get_tracker
        response["daily_quota"] = get_tracker().summary()
    except Exception as exc:
        logger.debug("post-download quota snapshot failed: %s", exc)
    try:
        info = await client.get_credits()
        response["credits_remaining"] = int(info.credits)
    except Exception as exc:
        logger.warning("post-download credit check failed: %s", exc)

    return response


# ────────────────────────────────────────────────────────────────────────
# Zero-cost preview — fetches Sample.PreviewURL which is always free.
# ────────────────────────────────────────────────────────────────────────


@mcp.tool()
async def splice_preview_sample(
    ctx: Context,
    file_hash: str,
    cache: bool = True,
) -> dict:
    """Fetch a Splice sample's preview audio — ZERO credits, ZERO quota cost.

    Every catalog sample has a `PreviewURL` (low-bitrate MP3) that Splice
    streams freely. Use this to audition before calling
    `splice_download_sample`. Perfect for:
      - Quickly hearing 10 candidates before committing to one download
      - Staying under the daily sample quota on the Ableton Live plan
      - Letting agents judge fit without spending anything

    Arguments:
      file_hash: the sample identifier from search results
      cache: if True (default), write the preview to
        ~/Library/Caches/LivePilot/splice_previews/ for Ableton to load

    Returns: {
      "ok": bool,
      "preview_url": str,
      "local_preview_path": str,   # if cache=True and download succeeded
      "filename": str,
      "duration_sec": float,
      "cost": "free",              # always, for every plan
    }
    """
    import hashlib
    import urllib.request
    import urllib.error

    client = None
    try:
        client = ctx.lifespan_context.get("splice_client")
    except AttributeError:
        pass

    if client is None or not getattr(client, "connected", False):
        return {"ok": False, "error": "Splice gRPC not connected"}

    sample = None
    try:
        sample = await client.get_sample_info(file_hash)
    except Exception as exc:
        return {"ok": False, "error": f"SampleInfo failed: {exc}"}

    if sample is None or not sample.preview_url:
        return {
            "ok": False,
            "error": "No preview URL available for this sample",
            "file_hash": file_hash,
        }

    response: dict = {
        "ok": True,
        "preview_url": sample.preview_url,
        "filename": sample.filename,
        "duration_sec": round(sample.duration_seconds, 2),
        "cost": "free",
        "file_hash": file_hash,
        "is_free_sample": sample.is_free,
        "key": sample.key_display,
        "bpm": sample.bpm,
        "tags": sample.tags,
    }

    if cache:
        cache_dir = os.path.expanduser(_SPLICE_PREVIEW_CACHE)
        try:
            os.makedirs(cache_dir, exist_ok=True)
            # Short deterministic filename based on file_hash
            digest = hashlib.md5(file_hash.encode()).hexdigest()[:12]
            ext = os.path.splitext(sample.preview_url.split("?")[0])[1] or ".mp3"
            dest = os.path.join(cache_dir, f"preview_{digest}{ext}")
            if not os.path.isfile(dest):
                def _download():
                    req = urllib.request.Request(
                        sample.preview_url,
                        headers={"User-Agent": "LivePilot/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=15) as r:
                        data = r.read()
                    with open(dest, "wb") as f:
                        f.write(data)
                    return dest
                # Run sync urllib in a thread to avoid blocking the event loop
                import asyncio as _aio
                await _aio.get_running_loop().run_in_executor(None, _download)
            response["local_preview_path"] = dest
        except (urllib.error.URLError, OSError, ValueError) as exc:
            response["cache_warning"] = f"Preview cache write failed: {exc}"

    return response


# ────────────────────────────────────────────────────────────────────────
# Collections — user's personal sample organization (Likes, bass, keys, …).
# These call the gRPC Collection* RPCs already wrapped in AppStub.
# ────────────────────────────────────────────────────────────────────────


def _require_splice_client(ctx: Context) -> tuple[object, Optional[dict]]:
    """Fetch the Splice client from context, or return an error dict."""
    client = None
    try:
        client = ctx.lifespan_context.get("splice_client")
    except AttributeError:
        pass
    if client is None or not getattr(client, "connected", False):
        return None, {"ok": False, "error": "Splice gRPC not connected"}
    return client, None


@mcp.tool()
async def splice_list_collections(
    ctx: Context, page: int = 1, per_page: int = 50,
) -> dict:
    """List the user's Splice Collections (Likes, custom folders, Daily Picks…).

    Collections are user-curated sample/preset/pack bookmarks. They are
    the strongest available taste signal: each one represents the user's
    deliberate grouping. Use `splice_search_in_collection` to scope a
    search to one collection's samples — better than keyword-only search.

    Returns: {
      "ok": true,
      "total_count": int,
      "collections": [
        {"uuid": "...", "name": "Likes", "sample_count": 47, ...},
      ],
    }
    """
    client, err = _require_splice_client(ctx)
    if err:
        return err
    total, collections = await client.list_collections(
        page=max(1, int(page)), per_page=max(1, min(int(per_page), 100)),
    )
    return {
        "ok": True,
        "total_count": total,
        "returned": len(collections),
        "page": page,
        "collections": [c.to_dict() for c in collections],
    }


@mcp.tool()
async def splice_search_in_collection(
    ctx: Context,
    collection_uuid: str,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """List samples inside a Splice Collection by UUID.

    Get the UUID from `splice_list_collections`. The returned samples
    carry full metadata (key, BPM, is_free, preview_url) identical to
    `splice_catalog_hunt` — you can feed them straight into
    `splice_preview_sample` or `splice_download_sample`.
    """
    client, err = _require_splice_client(ctx)
    if err:
        return err
    total, samples = await client.collection_samples(
        uuid=collection_uuid,
        page=max(1, int(page)),
        per_page=max(1, min(int(per_page), 100)),
    )
    return {
        "ok": True,
        "collection_uuid": collection_uuid,
        "total_hits": total,
        "returned": len(samples),
        "samples": [s.to_dict() for s in samples],
    }


@mcp.tool()
async def splice_add_to_collection(
    ctx: Context, collection_uuid: str, file_hashes: list[str],
) -> dict:
    """Add one or more samples to a user Collection.

    Persists server-side — the change appears in the Splice desktop app
    and web UI immediately. Use this to let LivePilot "save for later"
    items it finds during composition work.
    """
    client, err = _require_splice_client(ctx)
    if err:
        return err
    if not file_hashes:
        return {"ok": False, "error": "file_hashes must be a non-empty list"}
    success = await client.add_to_collection(collection_uuid, list(file_hashes))
    return {
        "ok": success,
        "collection_uuid": collection_uuid,
        "added_count": len(file_hashes) if success else 0,
    }


@mcp.tool()
async def splice_remove_from_collection(
    ctx: Context, collection_uuid: str, file_hashes: list[str],
) -> dict:
    """Remove one or more samples from a user Collection (server-side)."""
    client, err = _require_splice_client(ctx)
    if err:
        return err
    if not file_hashes:
        return {"ok": False, "error": "file_hashes must be a non-empty list"}
    success = await client.remove_from_collection(
        collection_uuid, list(file_hashes),
    )
    return {
        "ok": success,
        "collection_uuid": collection_uuid,
        "removed_count": len(file_hashes) if success else 0,
    }


@mcp.tool()
async def splice_create_collection(ctx: Context, name: str) -> dict:
    """Create a new user Collection. Returns the new UUID on success."""
    client, err = _require_splice_client(ctx)
    if err:
        return err
    name = (name or "").strip()
    if not name:
        return {"ok": False, "error": "Collection name cannot be empty"}
    collection = await client.create_collection(name)
    if collection is None:
        return {"ok": False, "error": "Collection create returned no result"}
    return {"ok": True, "collection": collection.to_dict()}


# ────────────────────────────────────────────────────────────────────────
# Presets — Splice Instrument / VST presets the user has purchased.
# ────────────────────────────────────────────────────────────────────────


@mcp.tool()
async def splice_list_presets(
    ctx: Context,
    page: int = 1,
    per_page: int = 50,
    sort: str = "",
    sort_order: str = "",
) -> dict:
    """List presets the user has purchased from Splice.

    Covers Splice Instrument and Rent-to-Own plugin presets. Each entry
    includes `plugin_name` so the agent can route loading to the right
    plugin — e.g., a Serum preset vs. a Splice Instrument preset.

    Returns: {
      "ok": true,
      "total_hits": int,
      "presets": [
        {"uuid": "...", "filename": "Deep House Pluck.fxp",
         "plugin_name": "Serum", "local_path": "...", ...},
      ],
    }
    """
    client, err = _require_splice_client(ctx)
    if err:
        return err
    total, presets = await client.list_purchased_presets(
        page=max(1, int(page)),
        per_page=max(1, min(int(per_page), 100)),
        sort=sort, sort_order=sort_order,
    )
    return {
        "ok": True,
        "total_hits": total,
        "returned": len(presets),
        "presets": [p.to_dict() for p in presets],
    }


@mcp.tool()
async def splice_preset_info(
    ctx: Context,
    uuid: str = "",
    file_hash: str = "",
    plugin_name: str = "",
) -> dict:
    """Fetch metadata for a single preset (uuid, file_hash, or plugin_name)."""
    client, err = _require_splice_client(ctx)
    if err:
        return err
    if not (uuid or file_hash or plugin_name):
        return {"ok": False, "error": "Provide at least one of uuid, file_hash, plugin_name"}
    info = await client.get_preset_info(
        uuid=uuid, file_hash=file_hash, plugin_name=plugin_name,
    )
    if info is None:
        return {"ok": False, "error": "Preset not found"}
    return {"ok": True, **info}


@mcp.tool()
async def splice_download_preset(ctx: Context, uuid: str) -> dict:
    """Trigger a preset download (uses Splice.com credits, not the sample quota).

    Splice credits ARE used for presets under every plan — this is the
    "second pocket" of the subscription model. We still honor
    CREDIT_HARD_FLOOR=5 so the agent can't drain the monthly allotment.
    """
    from ..splice_client.client import CREDIT_HARD_FLOOR

    client, err = _require_splice_client(ctx)
    if err:
        return err
    if not uuid:
        return {"ok": False, "error": "uuid is required"}

    try:
        can, remaining = await client.can_afford(1, budget=1)
    except Exception as exc:
        return {"ok": False, "error": f"Credit check failed: {exc}"}
    if not can:
        return {
            "ok": False,
            "error": (
                f"Credit floor hit (remaining={remaining}, "
                f"floor={CREDIT_HARD_FLOOR}). Preset download refused."
            ),
            "credits_remaining": remaining,
        }

    success = await client.download_preset(uuid)
    result: dict = {"ok": success, "uuid": uuid}
    try:
        info = await client.get_credits()
        result["credits_remaining"] = int(info.credits)
    except Exception as exc:
        logger.debug("post-preset-download credit check failed: %s", exc)
    return result


# ────────────────────────────────────────────────────────────────────────
# Sample packs — pack metadata (rich descriptions, genre, cover art, etc.).
# ────────────────────────────────────────────────────────────────────────


@mcp.tool()
async def splice_pack_info(ctx: Context, pack_uuid: str) -> dict:
    """Fetch full metadata for a Splice sample pack by UUID.

    Pack UUIDs come from search results (each sample carries `pack_uuid`).
    Useful for discovering related samples by pack, or surfacing pack-level
    genre/provider info that search results omit.
    """
    client, err = _require_splice_client(ctx)
    if err:
        return err
    if not pack_uuid:
        return {"ok": False, "error": "pack_uuid is required"}
    pack = await client.get_pack_info(pack_uuid)
    if pack is None:
        return {"ok": False, "error": "Pack not found or gRPC call failed"}
    return {"ok": True, "pack": pack.to_dict()}


# ────────────────────────────────────────────────────────────────────────
# HTTPS bridge — Describe a Sound / Variations (plugin-exclusive features).
# These hit api.splice.com over HTTPS with the session token from gRPC.
# Scaffolding ships today; real endpoints wire in once captured.
# ────────────────────────────────────────────────────────────────────────


def _build_http_bridge(ctx: Context):
    """Construct the HTTPS bridge with the current gRPC client attached.

    Returns (bridge, err_dict). On success err_dict is None.
    """
    from ..splice_client.http_bridge import SpliceHTTPBridge

    client = None
    try:
        client = ctx.lifespan_context.get("splice_client")
    except AttributeError:
        pass
    if client is None or not getattr(client, "connected", False):
        return None, {
            "ok": False,
            "error": "Splice gRPC not connected — session token unreachable",
        }
    return SpliceHTTPBridge(grpc_client=client), None


@mcp.tool()
async def splice_describe_sound(
    ctx: Context,
    description: str,
    bpm: Optional[int] = None,
    key: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """Natural-language sample search — the Sounds Plugin's "Describe a Sound".

    Splice's AI matches free-form descriptions like "dark ambient pad with
    shimmer" or "tight 90s house hi-hat" to catalog samples. This is NOT
    on the local gRPC — the bridge proxies to api.splice.com using your
    session token.

    **Status: scaffolding complete, endpoint pending real-traffic capture.**
    Until `SPLICE_DESCRIBE_ENDPOINT` env var is set (or
    `SPLICE_ALLOW_UNVERIFIED_ENDPOINTS=1`), this tool returns a structured
    ENDPOINT_NOT_CONFIGURED error with actionable setup steps.

    description: free-text prompt ("warm analog bass under 80bpm")
    bpm:         optional BPM filter
    key:         optional musical key ("Dm", "F#")
    limit:       max results (default 20)
    """
    bridge, err = _build_http_bridge(ctx)
    if err:
        return err
    from ..splice_client.http_bridge import SpliceHTTPError
    if not description or not description.strip():
        return {"ok": False, "error": "description is required"}
    try:
        result = await bridge.describe_sound(
            description=description.strip(),
            bpm=bpm, key=key, limit=int(limit),
        )
    except SpliceHTTPError as exc:
        return exc.to_dict()
    except Exception as exc:
        return {"ok": False, "error": f"describe_sound failed: {exc}"}
    return {"ok": True, "query": description, **(result if isinstance(result, dict) else {"raw": result})}


@mcp.tool()
async def splice_generate_variation(
    ctx: Context,
    file_hash: str,
    target_key: Optional[str] = None,
    target_bpm: Optional[int] = None,
    count: int = 1,
) -> dict:
    """Generate AI variations of a Splice sample — the Sounds Plugin's "Variations".

    Splice's AI produces unique re-keyed / re-tempo'd versions of any
    sample. Costs additional credits per variation (on top of the base
    license). NOT on the local gRPC — bridged via api.splice.com.

    **Status: scaffolding complete, endpoint pending real-traffic capture.**
    Until `SPLICE_VARIATION_ENDPOINT` env var is set (or
    `SPLICE_ALLOW_UNVERIFIED_ENDPOINTS=1`), this tool returns a structured
    ENDPOINT_NOT_CONFIGURED error with actionable setup steps.

    file_hash:  sample identifier (from search results)
    target_key: desired key (e.g. "Am")
    target_bpm: desired tempo
    count:      number of variations to generate (1-5)

    WARNING: this WILL spend credits when the endpoint is live.
    Consider previewing the source sample with splice_preview_sample first.
    """
    bridge, err = _build_http_bridge(ctx)
    if err:
        return err
    from ..splice_client.http_bridge import SpliceHTTPError
    if not file_hash or not file_hash.strip():
        return {"ok": False, "error": "file_hash is required"}
    if count < 1 or count > 5:
        return {"ok": False, "error": "count must be 1-5"}
    try:
        result = await bridge.generate_variation(
            file_hash=file_hash.strip(),
            target_key=target_key,
            target_bpm=target_bpm,
            count=int(count),
        )
    except SpliceHTTPError as exc:
        return exc.to_dict()
    except Exception as exc:
        return {"ok": False, "error": f"generate_variation failed: {exc}"}
    return {"ok": True, "file_hash": file_hash, **(result if isinstance(result, dict) else {"raw": result})}


@mcp.tool()
async def splice_search_with_sound(
    ctx: Context,
    audio_path: str,
    limit: int = 20,
) -> dict:
    """Reference-audio search — the Sounds Plugin's "Search with Sound".

    Uploads a local audio file to Splice's AI and returns catalog samples
    with similar character. Complements `splice_describe_sound` (text)
    and `search_samples` (keyword).

    **Status: scaffolding complete, wiring pending real-traffic capture
    (multipart upload shape is the most uncertain part of the bridge).**
    Until `SPLICE_SEARCH_WITH_SOUND_ENDPOINT` is set, returns a structured
    NOT_YET_IMPLEMENTED error.

    audio_path: absolute path to a local audio file (.wav, .mp3, .flac)
    limit:      max results (default 20)
    """
    bridge, err = _build_http_bridge(ctx)
    if err:
        return err
    from ..splice_client.http_bridge import SpliceHTTPError
    if not audio_path or not os.path.isfile(audio_path):
        return {"ok": False, "error": f"audio_path not found: {audio_path}"}
    try:
        result = await bridge.search_with_sound(
            audio_path=audio_path, limit=int(limit),
        )
    except SpliceHTTPError as exc:
        return exc.to_dict()
    except Exception as exc:
        return {"ok": False, "error": f"search_with_sound failed: {exc}"}
    return {"ok": True, "audio_path": audio_path, **(result if isinstance(result, dict) else {"raw": result})}
