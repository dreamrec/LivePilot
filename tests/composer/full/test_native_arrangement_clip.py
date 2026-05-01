"""Tests for v1.24 Phase 4 Task 23 — native arrangement clip flow.

BUG-FULL-MODE-23: apply_full_plan_v2 was calling create_arrangement_clip
(session-clip duplication), which tiles separate arrangement-clip objects
every source-clip-length beats. Result: 32 4-beat clips per section instead
of ONE 64-beat arrangement clip.

Fix: call create_native_arrangement_clip (Live 12.1.10+ API) to create ONE
long arrangement clip per section, then write notes into it via
add_arrangement_notes and set internal loop via set_clip_loop.
"""

import pytest
from unittest.mock import MagicMock
from mcp_server.composer.full.apply import apply_full_plan_v2


def _mock_ctx_recording_native():
    """Mock ctx tracking native-arrangement-clip + notes + loop calls."""
    ableton = MagicMock()
    ableton._calls = []
    ableton._track_count = 0
    ableton._next_arr_clip_index = 0

    def send_command(cmd, args):
        ableton._calls.append((cmd, args))
        if cmd == "get_session_info":
            return {"tempo": 120.0, "track_count": ableton._track_count, "scene_count": 8, "tracks": []}
        if cmd == "get_track_info":
            return {"devices": [], "clip_slots": []}
        if cmd == "create_midi_track":
            ti = ableton._track_count
            ableton._track_count += 1
            return {"index": ti}
        if cmd == "create_clip":
            return {"track_index": args["track_index"], "clip_index": args["clip_index"]}
        if cmd == "add_notes":
            return {"notes_added": len(args.get("notes", []))}
        if cmd == "create_native_arrangement_clip":
            ci = ableton._next_arr_clip_index
            ableton._next_arr_clip_index += 1
            return {
                "track_index": args["track_index"],
                "clip_index": ci,
                "start_time": args["start_time"],
                "length": args["length"],
                "name": args.get("name", ""),
                "has_envelope_support": True,
                "native": True,
            }
        if cmd == "add_arrangement_notes":
            return {"notes_added": len(args.get("notes", []))}
        if cmd == "set_clip_loop":
            return {"ok": True}
        if cmd == "set_arrangement_clip_name":
            return {"name": args.get("name", "")}
        if cmd == "load_browser_item":
            return {"loaded": True}
        return {"ok": True}

    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}
    return ctx


@pytest.mark.asyncio
async def test_arrangement_uses_native_clip_not_session_duplicate():
    """The new flow uses create_native_arrangement_clip, NOT create_arrangement_clip.

    Old flow tiled separate session-clip duplicates every source-length beats
    (resulting in N tiny clips per section). New flow creates ONE long native
    clip per section.
    """
    ctx = _mock_ctx_recording_native()
    plan = {
        "scope": "full",
        "form": [{"name": "verse", "start_bar": 0, "bars": 16}],  # 16 bars = 64 beats
        "tracks": [{
            "role": "kick",
            "instrument": {"uri": "query:Drums#Drum%20Hits:Kick:FileId_30458"},
            "variants": [{"id": "main", "notes": [
                {"pitch": 36, "start_time": 0, "duration": 0.5, "velocity": 100},
                {"pitch": 36, "start_time": 2, "duration": 0.5, "velocity": 100},
            ]}],
            "arrangement_clips": [{"section_index": 0, "variant_id": "main"}],
        }],
        "events": [],
    }
    result = await apply_full_plan_v2(ctx, plan)
    cmds = [c[0] for c in ctx.lifespan_context["ableton"]._calls]
    # CRITICAL: should call native-arrangement-clip path, NOT session-duplicate path
    assert cmds.count("create_native_arrangement_clip") >= 1, (
        "Expected create_native_arrangement_clip for the new flow"
    )
    assert cmds.count("create_arrangement_clip") == 0, (
        "Old session-duplicate path should NOT be used (it tiles)"
    )


@pytest.mark.asyncio
async def test_native_clip_has_section_length():
    """The native arrangement clip's length matches the section length in beats."""
    ctx = _mock_ctx_recording_native()
    plan = {
        "scope": "full",
        "form": [{"name": "verse", "start_bar": 0, "bars": 16}],  # 16 bars = 64 beats
        "tracks": [{
            "role": "kick",
            "instrument": {"uri": "query:Drums#Drum%20Hits:Kick:FileId_30458"},
            "variants": [{"id": "main", "notes": [{"pitch": 36, "start_time": 0, "duration": 0.5, "velocity": 100}]}],
            "arrangement_clips": [{"section_index": 0, "variant_id": "main"}],
        }],
        "events": [],
    }
    await apply_full_plan_v2(ctx, plan)
    native_calls = [c[1] for c in ctx.lifespan_context["ableton"]._calls if c[0] == "create_native_arrangement_clip"]
    assert len(native_calls) == 1
    assert native_calls[0]["length"] == 64.0
    assert native_calls[0]["start_time"] == 0.0


@pytest.mark.asyncio
async def test_native_clip_has_internal_loop_region():
    """After creating the native clip and writing notes, set_clip_loop is called
    to enable internal looping at the source pattern length."""
    ctx = _mock_ctx_recording_native()
    plan = {
        "scope": "full",
        "form": [{"name": "verse", "start_bar": 0, "bars": 16}],
        "tracks": [{
            "role": "kick",
            "instrument": {"uri": "query:Drums#Drum%20Hits:Kick:FileId_30458"},
            "variants": [{"id": "main", "notes": [
                {"pitch": 36, "start_time": 0, "duration": 0.5, "velocity": 100},
                {"pitch": 36, "start_time": 2, "duration": 0.5, "velocity": 100},
            ]}],
            "arrangement_clips": [{"section_index": 0, "variant_id": "main"}],
        }],
        "events": [],
    }
    await apply_full_plan_v2(ctx, plan)
    cmds = [c for c in ctx.lifespan_context["ableton"]._calls if c[0] == "set_clip_loop"]
    assert len(cmds) == 1
    args = cmds[0][1]
    assert args["enabled"] is True
    # Source pattern is 4 beats (last note at 2, dur 0.5, end 2.5; snapped up to bar boundary = 4)
    assert args["loop_end"] == 4.0
    assert args["loop_start"] == 0.0


@pytest.mark.asyncio
async def test_notes_written_via_add_arrangement_notes():
    """Variant's notes go into the native clip via add_arrangement_notes."""
    ctx = _mock_ctx_recording_native()
    plan = {
        "scope": "full",
        "form": [{"name": "verse", "start_bar": 0, "bars": 4}],
        "tracks": [{
            "role": "kick",
            "instrument": {"uri": "query:Drums#Drum%20Hits:Kick:FileId_30458"},
            "variants": [{"id": "main", "notes": [
                {"pitch": 36, "start_time": 0, "duration": 0.5, "velocity": 100},
                {"pitch": 36, "start_time": 2, "duration": 0.5, "velocity": 100},
            ]}],
            "arrangement_clips": [{"section_index": 0, "variant_id": "main"}],
        }],
        "events": [],
    }
    await apply_full_plan_v2(ctx, plan)
    add_calls = [c[1] for c in ctx.lifespan_context["ableton"]._calls if c[0] == "add_arrangement_notes"]
    assert len(add_calls) == 1
    assert len(add_calls[0]["notes"]) == 2  # two kick notes in the variant


@pytest.mark.asyncio
async def test_multiple_sections_create_multiple_native_clips():
    """Each (track, section) pair creates ONE native arrangement clip — no tiling.

    Plan with 3 sections × 1 track should produce exactly 3 native clips
    (NOT 3 × N tiles per section).
    """
    ctx = _mock_ctx_recording_native()
    plan = {
        "scope": "full",
        "form": [
            {"name": "intro", "start_bar": 0, "bars": 8},
            {"name": "verse", "start_bar": 8, "bars": 16},
            {"name": "outro", "start_bar": 24, "bars": 8},
        ],
        "tracks": [{
            "role": "kick",
            "instrument": {"uri": "query:Drums#Drum%20Hits:Kick:FileId_30458"},
            "variants": [{"id": "main", "notes": [{"pitch": 36, "start_time": 0, "duration": 0.5, "velocity": 100}]}],
            "arrangement_clips": [
                {"section_index": 0, "variant_id": "main"},
                {"section_index": 1, "variant_id": "main"},
                {"section_index": 2, "variant_id": "main"},
            ],
        }],
        "events": [],
    }
    await apply_full_plan_v2(ctx, plan)
    cmds = [c[0] for c in ctx.lifespan_context["ableton"]._calls]
    # 3 sections → 3 native arrangement clips, NOT 32+ tiled session-clip duplicates
    assert cmds.count("create_native_arrangement_clip") == 3
    assert cmds.count("create_arrangement_clip") == 0
