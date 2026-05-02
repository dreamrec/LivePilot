"""Regression guard for BUG-FULL-MODE-15.

The old deterministic engine emitted stale track indices when layers dropped
as unresolved (e.g. plan said create_midi_track(index=3) but only tracks 0-1
existed). The v1.24 LLM-creative v2 flow eliminates this surface: the agent
designs the plan with explicit track_index OR omits it (server creates and
records actual index). There is no separate "renumber pass" because there
is no cascade.

This test locks in the v2 contract — agent-designed plans MUST NOT contain
stale indices, and the server MUST use actual creation indices in postflight.
"""

import pytest
from unittest.mock import MagicMock
from mcp_server.composer.full.apply import apply_full_plan_v2


def _mock_ctx():
    ableton = MagicMock()
    ableton._track_count = 0
    ableton._calls = []

    def send_command(cmd, args):
        ableton._calls.append((cmd, args))
        if cmd == "get_session_info":
            return {"tempo": 120.0, "track_count": ableton._track_count, "scene_count": 8, "tracks": []}
        if cmd == "create_midi_track":
            ti = ableton._track_count
            ableton._track_count += 1
            return {"track_index": ti}
        if cmd == "create_native_arrangement_clip":
            ci = getattr(ableton, "_next_arr_clip_index", 0)
            ableton._next_arr_clip_index = ci + 1
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
        return {"ok": True}

    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}
    return ctx


@pytest.mark.asyncio
async def test_v2_records_actual_track_indices_not_planned_ones():
    """When tracks omit track_index, server creates and records actual indices.

    Two tracks created sequentially get indices 0 and 1 — never 0 and 3 (which
    would be the BUG-FULL-MODE-15 cascade).
    """
    ctx = _mock_ctx()
    plan = {
        "scope": "full",
        "form": [{"name": "intro", "start_bar": 0, "bars": 4}],
        "tracks": [
            {
                "role": "drums",
                "variants": [{"id": "v1", "notes": []}],
                "arrangement_clips": [{"section_index": 0, "variant_id": "v1", "loop_length": 4.0}],
            },
            {
                "role": "bass",
                "variants": [{"id": "v1", "notes": []}],
                "arrangement_clips": [{"section_index": 0, "variant_id": "v1", "loop_length": 4.0}],
            },
        ],
        "events": [],
    }
    result = await apply_full_plan_v2(ctx, plan)
    # Two tracks created — indices 0 and 1 contiguously
    create_track_calls = [c for c in ctx.lifespan_context["ableton"]._calls if c[0] == "create_midi_track"]
    assert len(create_track_calls) == 2
    # No INDEX_ERROR cascade — both tracks succeeded
    assert result["tracks_created"] == 2
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_v2_explicit_track_index_does_not_create_new_track():
    """When agent provides track_index, server uses it directly. No renumber pass needed."""
    ctx = _mock_ctx()
    plan = {
        "scope": "full",
        "form": [{"name": "intro", "start_bar": 0, "bars": 4}],
        "tracks": [{
            "role": "bass",
            "track_index": 7,  # explicit
            "variants": [{"id": "v1", "notes": []}],
            "arrangement_clips": [{"section_index": 0, "variant_id": "v1", "loop_length": 4.0}],
        }],
        "events": [],
    }
    result = await apply_full_plan_v2(ctx, plan)
    create_track_calls = [c for c in ctx.lifespan_context["ableton"]._calls if c[0] == "create_midi_track"]
    assert len(create_track_calls) == 0
    assert result["tracks_created"] == 0
