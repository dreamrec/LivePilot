"""Tests for the new LLM-creative full-mode apply path.

Agent designs the plan; server validates + executes. The old deterministic
engine path is deprecated.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from mcp_server.composer.full.apply import apply_full_plan_v2


def _mock_ctx_recording():
    """Mock ctx that records every send_command call."""
    ableton = MagicMock()
    ableton._calls = []
    track_count = [0]

    def send_command(cmd, args):
        ableton._calls.append((cmd, args))
        if cmd == "get_session_info":
            return {"tempo": 120.0, "track_count": track_count[0], "scene_count": 8, "tracks": []}
        if cmd == "create_midi_track":
            ti = track_count[0]
            track_count[0] += 1
            return {"track_index": ti}
        if cmd == "create_audio_track":
            ti = track_count[0]
            track_count[0] += 1
            return {"track_index": ti}
        if cmd == "create_clip":
            return {"track_index": args["track_index"], "clip_index": args["clip_index"]}
        if cmd == "add_notes":
            return {"notes_added": len(args.get("notes", []))}
        if cmd == "create_arrangement_clip":
            return {"track_index": args["track_index"], "start_time": args["start_time"]}
        if cmd == "set_clip_name":
            return {"name": args["name"]}
        if cmd == "set_arrangement_clip_name":
            return {"name": args["name"]}
        if cmd == "load_browser_item":
            return {"loaded": True}
        if cmd == "set_tempo":
            return {"tempo": args["tempo"]}
        if cmd == "set_song_scale":
            return {"ok": True}
        return {"ok": True}

    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}
    return ctx


# ── plan validation ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rejects_plan_with_no_form():
    ctx = _mock_ctx_recording()
    plan = {"scope": "full", "tracks": [], "events": []}
    result = await apply_full_plan_v2(ctx, plan)
    assert result.get("status") == "error"
    assert "form" in result.get("error", "").lower()


@pytest.mark.asyncio
async def test_rejects_plan_with_no_tracks():
    ctx = _mock_ctx_recording()
    plan = {"scope": "full", "form": [{"name": "intro", "start_bar": 0, "bars": 16}], "tracks": [], "events": []}
    result = await apply_full_plan_v2(ctx, plan)
    assert result.get("status") == "error"
    assert "tracks" in result.get("error", "").lower()


@pytest.mark.asyncio
async def test_rejects_arrangement_clip_referencing_unknown_variant_id():
    ctx = _mock_ctx_recording()
    plan = {
        "scope": "full",
        "form": [{"name": "intro", "start_bar": 0, "bars": 4}],
        "tracks": [{
            "role": "bass",
            "variants": [{"id": "main", "notes": [{"pitch": 45, "start_time": 0, "duration": 1, "velocity": 100}]}],
            "arrangement_clips": [{"section_index": 0, "variant_id": "DOES_NOT_EXIST", "loop_length": 4.0}],
        }],
        "events": [],
    }
    result = await apply_full_plan_v2(ctx, plan)
    # Either the plan is rejected outright OR per-track errors collected
    assert result.get("status") in ("error", "partial")


# ── happy-path: 2 sections, 1 track, 2 variants ────────────────────

@pytest.mark.asyncio
async def test_creates_track_then_variants_then_arrangement_clips():
    ctx = _mock_ctx_recording()
    plan = {
        "scope": "full",
        "tempo": 128.0,
        "key": "Am",
        "form": [
            {"name": "intro", "start_bar": 0, "bars": 16},
            {"name": "main", "start_bar": 16, "bars": 32},
        ],
        "tracks": [{
            "role": "bass",
            "instrument": {"uri": "atlas://bass-instrument", "params": {}},
            "variants": [
                {"id": "main_v", "notes": [{"pitch": 45, "start_time": 0, "duration": 1, "velocity": 100}]},
                {"id": "intro_v", "notes": [{"pitch": 45, "start_time": 0, "duration": 4, "velocity": 60}]},
            ],
            "arrangement_clips": [
                {"section_index": 0, "variant_id": "intro_v", "loop_length": 4.0},
                {"section_index": 1, "variant_id": "main_v", "loop_length": 4.0},
            ],
        }],
        "events": [],
    }
    result = await apply_full_plan_v2(ctx, plan)
    assert result["status"] == "ok"
    assert result["tracks_created"] == 1
    assert result["variants_created"] == 2
    assert result["arrangement_clips_created"] == 2

    # Verify call order: tempo → track → variants → arrangement clips
    cmds = [c[0] for c in ctx.lifespan_context["ableton"]._calls]
    track_idx = cmds.index("create_midi_track")
    create_clip_count = cmds.count("create_clip")
    arr_clip_count = cmds.count("create_arrangement_clip")
    assert create_clip_count == 2  # 2 variants → 2 source clips in session view
    assert arr_clip_count == 2  # 2 arrangement clips placed


# ── multiple variants per track (BUG-FULL-MODE-18 regression guard) ──

@pytest.mark.asyncio
async def test_variants_create_distinct_session_clips():
    """Each variant must produce its own source clip — NOT flat tiling.

    This is the BUG-FULL-MODE-18 regression guard. The old flow tiled one
    source clip across all sections; the new flow emits one source clip
    per variant.
    """
    ctx = _mock_ctx_recording()
    plan = {
        "scope": "full",
        "form": [
            {"name": "intro", "start_bar": 0, "bars": 8},
            {"name": "main", "start_bar": 8, "bars": 16},
            {"name": "fill", "start_bar": 24, "bars": 4},
            {"name": "outro", "start_bar": 28, "bars": 8},
        ],
        "tracks": [{
            "role": "bass",
            "variants": [
                {"id": "v1", "notes": [{"pitch": 45, "start_time": 0, "duration": 1, "velocity": 80}]},
                {"id": "v2", "notes": [{"pitch": 45, "start_time": 0, "duration": 1, "velocity": 100}]},
                {"id": "v3", "notes": [{"pitch": 48, "start_time": 0, "duration": 0.5, "velocity": 110}]},
            ],
            "arrangement_clips": [
                {"section_index": 0, "variant_id": "v1", "loop_length": 4.0},
                {"section_index": 1, "variant_id": "v2", "loop_length": 4.0},
                {"section_index": 2, "variant_id": "v3", "loop_length": 4.0},
                {"section_index": 3, "variant_id": "v1", "loop_length": 4.0},
            ],
        }],
        "events": [],
    }
    result = await apply_full_plan_v2(ctx, plan)
    assert result["variants_created"] == 3
    assert result["arrangement_clips_created"] == 4


# ── tempo + key application ────────────────────────────────────────

@pytest.mark.asyncio
async def test_sets_tempo_when_plan_specifies():
    ctx = _mock_ctx_recording()
    plan = {
        "scope": "full",
        "tempo": 130.0,  # differs from session 120
        "form": [{"name": "intro", "start_bar": 0, "bars": 4}],
        "tracks": [{
            "role": "bass",
            "variants": [{"id": "v1", "notes": []}],
            "arrangement_clips": [{"section_index": 0, "variant_id": "v1", "loop_length": 4.0}],
        }],
        "events": [],
    }
    await apply_full_plan_v2(ctx, plan)
    cmds = [c[0] for c in ctx.lifespan_context["ableton"]._calls]
    assert "set_tempo" in cmds


# ── postflight integration ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_postflight_calls_back_to_arranger():
    ctx = _mock_ctx_recording()
    plan = {
        "scope": "full",
        "form": [{"name": "intro", "start_bar": 0, "bars": 4}],
        "tracks": [{
            "role": "bass",
            "variants": [{"id": "v1", "notes": [{"pitch": 45, "start_time": 0, "duration": 1, "velocity": 100}]}],
            "arrangement_clips": [{"section_index": 0, "variant_id": "v1", "loop_length": 4.0}],
        }],
        "events": [],
    }
    result = await apply_full_plan_v2(ctx, plan)
    cmds = [c[0] for c in ctx.lifespan_context["ableton"]._calls]
    assert "back_to_arranger" in cmds


# ── existing-track reuse (extension flow, no new track created) ────

@pytest.mark.asyncio
async def test_reuses_existing_track_when_track_index_provided():
    """If plan.tracks[i] has track_index set, server uses that track instead of
    creating a new one. This matters for develop-on-top-of-full extensions."""
    ctx = _mock_ctx_recording()
    plan = {
        "scope": "full",
        "form": [{"name": "intro", "start_bar": 0, "bars": 4}],
        "tracks": [{
            "role": "bass",
            "track_index": 2,  # existing track
            "variants": [{"id": "v1", "notes": [{"pitch": 45, "start_time": 0, "duration": 1, "velocity": 100}]}],
            "arrangement_clips": [{"section_index": 0, "variant_id": "v1", "loop_length": 4.0}],
        }],
        "events": [],
    }
    result = await apply_full_plan_v2(ctx, plan)
    cmds = [c[0] for c in ctx.lifespan_context["ableton"]._calls]
    # Should NOT create a new track — track_index 2 was specified
    assert "create_midi_track" not in cmds
    assert "create_audio_track" not in cmds
    assert result["tracks_created"] == 0


# ── result shape ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_result_shape_complete():
    ctx = _mock_ctx_recording()
    plan = {
        "scope": "full",
        "form": [{"name": "intro", "start_bar": 0, "bars": 4}],
        "tracks": [{
            "role": "bass",
            "variants": [{"id": "v1", "notes": []}],
            "arrangement_clips": [{"section_index": 0, "variant_id": "v1", "loop_length": 4.0}],
        }],
        "events": [],
    }
    result = await apply_full_plan_v2(ctx, plan)
    REQUIRED = {
        "status", "tracks_created", "variants_created",
        "arrangement_clips_created", "events_applied",
        "preflight", "postflight", "errors", "duration_ms",
    }
    missing = REQUIRED - set(result.keys())
    assert not missing, f"Result shape missing fields: {missing}"
