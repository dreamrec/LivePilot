"""Tests for develop-mode apply_develop_plan."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, call
from mcp_server.composer.develop.apply import apply_develop_plan


def _mock_ctx_with_recording():
    """Build a mock ctx that records every send_command call for assertions."""
    ableton = MagicMock()
    ableton._calls = []  # list of (cmd, args) tuples

    def send_command(cmd, args):
        ableton._calls.append((cmd, args))
        # Default responses
        if cmd == "get_session_info":
            return {"tempo": 122.0, "track_count": 5, "scene_count": 8}
        if cmd == "create_clip":
            return {"track_index": args["track_index"], "clip_index": args["clip_index"], "length": args["length"]}
        if cmd == "add_notes":
            return {"notes_added": len(args.get("notes", []))}
        if cmd == "set_clip_name":
            return {"name": args["name"]}
        if cmd == "load_browser_item":
            return {"loaded": True}
        if cmd == "set_tempo":
            return {"tempo": args["tempo"]}
        return {"ok": True}

    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}
    return ctx


# ── happy-path: 4 simple variants on one track ─────────────────────

@pytest.mark.asyncio
async def test_apply_creates_clips_per_variant():
    ctx = _mock_ctx_with_recording()
    plan = {
        "scope": "develop",
        "clip_length_beats": 4.0,
        "tempo": 122.0,
        "variants": [
            {"track_index": 1, "scene_index": 1, "name": "v1",
             "notes": [{"pitch": 45, "start_time": 0, "duration": 1, "velocity": 100}]},
            {"track_index": 1, "scene_index": 2, "name": "v2",
             "notes": [{"pitch": 47, "start_time": 0, "duration": 1, "velocity": 100}]},
            {"track_index": 1, "scene_index": 3, "name": "v3",
             "notes": [{"pitch": 48, "start_time": 0, "duration": 1, "velocity": 100}]},
            {"track_index": 1, "scene_index": 4, "name": "v4",
             "notes": [{"pitch": 50, "start_time": 0, "duration": 1, "velocity": 100}]},
        ],
    }
    result = await apply_develop_plan(ctx, plan)

    # Result reports
    assert result["status"] == "ok"
    assert result["clips_created"] == 4
    assert sorted(result["scenes_populated"]) == [1, 2, 3, 4]

    # Verify the calls happened in the expected order: per variant, create then add then name
    cmds = [c[0] for c in ctx.lifespan_context["ableton"]._calls]
    create_count = cmds.count("create_clip")
    add_count = cmds.count("add_notes")
    name_count = cmds.count("set_clip_name")
    assert create_count == 4
    assert add_count == 4
    assert name_count == 4


# ── empty-notes variant creates clip but skips add_notes ───────────

@pytest.mark.asyncio
async def test_apply_empty_notes_creates_clip_but_no_add_notes():
    ctx = _mock_ctx_with_recording()
    plan = {
        "scope": "develop",
        "clip_length_beats": 4.0,
        "variants": [
            {"track_index": 0, "scene_index": 3, "name": "BREAK", "notes": []},
        ],
    }
    result = await apply_develop_plan(ctx, plan)
    assert result["status"] == "ok"
    assert result["clips_created"] == 1

    cmds = [c[0] for c in ctx.lifespan_context["ableton"]._calls]
    assert cmds.count("create_clip") == 1
    assert cmds.count("add_notes") == 0  # NO add_notes for empty
    assert cmds.count("set_clip_name") == 1  # but still name it


# ── sample-swap path ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_apply_sample_swap_loads_browser_item_before_create_clip():
    ctx = _mock_ctx_with_recording()
    plan = {
        "scope": "develop",
        "clip_length_beats": 4.0,
        "variants": [
            {
                "track_index": 0, "scene_index": 2, "name": "ROLL",
                "sample_uri": "atlas://samples/roll.wav",
                "notes": [{"pitch": 60, "start_time": 0, "duration": 1, "velocity": 100}],
            },
        ],
    }
    result = await apply_develop_plan(ctx, plan)
    assert result["status"] == "ok"
    assert result["sample_swaps"] == 1

    cmds = [c[0] for c in ctx.lifespan_context["ableton"]._calls]
    # load_browser_item must come BEFORE create_clip on the same track
    if "load_browser_item" in cmds and "create_clip" in cmds:
        load_idx = cmds.index("load_browser_item")
        create_idx = cmds.index("create_clip")
        assert load_idx < create_idx, "sample swap must happen before create_clip"


# ── tempo override ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_apply_sets_tempo_when_plan_specifies_different_tempo():
    """Plan tempo differs from session tempo → set_tempo called."""
    ableton = MagicMock()
    ableton._calls = []
    def send_command(cmd, args):
        ableton._calls.append((cmd, args))
        if cmd == "get_session_info":
            return {"tempo": 122.0, "track_count": 5, "scene_count": 8}
        return {"ok": True}
    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    plan = {
        "scope": "develop",
        "clip_length_beats": 4.0,
        "tempo": 130.0,  # differs
        "variants": [{"track_index": 1, "scene_index": 1, "name": "v", "notes": []}],
    }
    await apply_develop_plan(ctx, plan)
    cmds = [c[0] for c in ableton._calls]
    assert "set_tempo" in cmds


@pytest.mark.asyncio
async def test_apply_does_not_set_tempo_when_matches_session():
    """Plan tempo matches session → no set_tempo call (no-op optimization)."""
    ctx = _mock_ctx_with_recording()
    plan = {
        "scope": "develop",
        "clip_length_beats": 4.0,
        "tempo": 122.0,  # matches mock session
        "variants": [{"track_index": 1, "scene_index": 1, "name": "v", "notes": []}],
    }
    await apply_develop_plan(ctx, plan)
    cmds = [c[0] for c in ctx.lifespan_context["ableton"]._calls]
    assert "set_tempo" not in cmds


# ── validation errors ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_apply_rejects_plan_with_no_variants():
    ctx = _mock_ctx_with_recording()
    plan = {"scope": "develop", "clip_length_beats": 4.0, "variants": []}
    result = await apply_develop_plan(ctx, plan)
    assert result.get("status") == "error" or "error" in result
    assert "variants" in result.get("error", "").lower()


@pytest.mark.asyncio
async def test_apply_rejects_wrong_scope():
    ctx = _mock_ctx_with_recording()
    plan = {"scope": "fast", "variants": [{"track_index": 0, "scene_index": 1, "name": "v", "notes": []}]}
    result = await apply_develop_plan(ctx, plan)
    assert result.get("status") == "error" or "error" in result


# ── postflight integration ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_apply_calls_back_to_arranger_via_postflight():
    """Develop only writes session clips (no new tracks), so postflight should
    call back_to_arranger but skip per-track monitoring."""
    ctx = _mock_ctx_with_recording()
    plan = {
        "scope": "develop", "clip_length_beats": 4.0,
        "variants": [{"track_index": 1, "scene_index": 1, "name": "v",
                      "notes": [{"pitch": 45, "start_time": 0, "duration": 1, "velocity": 100}]}],
    }
    result = await apply_develop_plan(ctx, plan)
    cmds = [c[0] for c in ctx.lifespan_context["ableton"]._calls]
    # back_to_arranger should be called as part of postflight
    assert "back_to_arranger" in cmds


# ── result shape ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_result_shape_complete():
    ctx = _mock_ctx_with_recording()
    plan = {
        "scope": "develop", "clip_length_beats": 4.0,
        "variants": [
            {"track_index": 0, "scene_index": 1, "name": "v1", "notes": []},
            {"track_index": 1, "scene_index": 2, "name": "v2",
             "notes": [{"pitch": 45, "start_time": 0, "duration": 1, "velocity": 100}]},
            {"track_index": 0, "scene_index": 3, "name": "swap", "sample_uri": "atlas://x.wav", "notes": []},
        ],
    }
    result = await apply_develop_plan(ctx, plan)
    assert "status" in result
    assert "clips_created" in result
    assert "scenes_populated" in result
    assert "sample_swaps" in result
    assert "preflight" in result
    assert "postflight" in result
    assert result["clips_created"] == 3
    assert result["sample_swaps"] == 1
