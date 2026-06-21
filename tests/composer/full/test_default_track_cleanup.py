"""Tests for default-track auto-cleanup in apply_full_plan_v2 preflight."""

import pytest
from unittest.mock import MagicMock
from mcp_server.composer.full.apply import apply_full_plan_v2


def _mock_ctx_with_default_tracks():
    """Mock a fresh-project session with 4 default tracks."""
    ableton = MagicMock()
    ableton._calls = []
    ableton._track_count = 4
    ableton._tracks = [
        {"index": 0, "name": "1-MIDI", "color_index": 1, "mute": False},
        {"index": 1, "name": "2-MIDI", "color_index": 2, "mute": False},
        {"index": 2, "name": "3-Audio", "color_index": 3, "mute": False},
        {"index": 3, "name": "4-Audio", "color_index": 4, "mute": False},
    ]

    def send_command(cmd, args):
        ableton._calls.append((cmd, args))
        if cmd == "get_session_info":
            return {
                "tempo": 120.0, "track_count": ableton._track_count,
                "scene_count": 8, "tracks": ableton._tracks,
            }
        if cmd == "delete_track":
            ableton._track_count -= 1
            return {"deleted": args["track_index"]}
        if cmd == "create_midi_track":
            ti = ableton._track_count
            ableton._track_count += 1
            return {"index": ti}
        if cmd == "load_browser_item":
            return {"loaded": True, "name": "Mock"}
        if cmd == "create_clip":
            return {"track_index": args["track_index"], "clip_index": args["clip_index"]}
        if cmd == "add_notes":
            return {"notes_added": len(args.get("notes", []))}
        if cmd == "create_arrangement_clip":
            return {"track_index": args["track_index"]}
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
        if cmd == "set_clip_name":
            return {"name": args.get("name", "")}
        if cmd == "set_arrangement_clip_name":
            return {"name": args.get("name", "")}
        return {"ok": True}

    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}
    return ctx


@pytest.mark.asyncio
async def test_full_apply_v2_deletes_default_tracks_on_fresh_project():
    """When session has 4 default-named tracks (1-MIDI, 2-MIDI, 3-Audio, 4-Audio),
    apply_full_plan_v2 detects fresh-project and deletes 3 of them in preflight
    (Ableton requires at least 1 track to remain).

    After the cleanup, when the new compose-created tracks are added, the final
    track count is sensible (no 8+ track sprawl)."""
    ctx = _mock_ctx_with_default_tracks()
    plan = {
        "scope": "full",
        "form": [{"name": "intro", "start_bar": 0, "bars": 4}],
        "tracks": [
            {
                "role": "bass",
                "instrument": {"uri": "query:Synths#Operator"},
                "variants": [{"id": "v1", "notes": []}],
                "arrangement_clips": [{"section_index": 0, "variant_id": "v1", "loop_length": 4}],
            },
        ],
        "events": [],
    }
    result = await apply_full_plan_v2(ctx, plan)
    cmds = [c[0] for c in ctx.lifespan_context["ableton"]._calls]
    delete_count = cmds.count("delete_track")
    # Should have deleted at least 3 of the 4 default tracks
    assert delete_count >= 3, f"Expected >=3 delete_track calls, got {delete_count}"
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_full_apply_v2_no_cleanup_on_non_fresh_project():
    """When session has user-modified tracks (named differently from defaults),
    apply does NOT delete them — only fresh-project state triggers cleanup."""
    ableton = MagicMock()
    ableton._calls = []
    ableton._track_count = 2
    ableton._tracks = [
        {"index": 0, "name": "MyKick", "color_index": 1, "mute": False},
        {"index": 1, "name": "MyBass", "color_index": 2, "mute": False},
    ]

    # BUG-FIX (post-live-test): user-named tracks with CONTENT (clips or
    # instruments) must be preserved. The zombie-detection should ONLY
    # delete empty tracks (no clips, no instruments) regardless of name.
    # This test makes both user-named tracks NON-empty by giving them
    # an instrument device.
    def send_command(cmd, args):
        ableton._calls.append((cmd, args))
        if cmd == "get_session_info":
            return {"tempo": 120.0, "track_count": ableton._track_count, "scene_count": 8, "tracks": ableton._tracks}
        if cmd == "get_track_info":
            # Tracks 0 and 1 (MyKick, MyBass) have an instrument loaded — NOT empty zombies
            ti = args["track_index"]
            if ti in (0, 1):
                return {
                    "devices": [{"class_name": "OriginalSimpler", "type": 1}],
                    "clip_slots": [{"has_clip": False}] * 8,
                }
            return {"devices": [], "clip_slots": []}
        if cmd == "create_midi_track":
            ti = ableton._track_count
            ableton._track_count += 1
            return {"index": ti}
        if cmd == "create_clip":
            return {"track_index": args["track_index"], "clip_index": args["clip_index"]}
        if cmd == "add_notes":
            return {"notes_added": len(args.get("notes", []))}
        if cmd == "create_arrangement_clip":
            return {"track_index": args["track_index"]}
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
        if cmd == "set_clip_name":
            return {"name": ""}
        if cmd == "set_arrangement_clip_name":
            return {"name": ""}
        if cmd == "load_browser_item":
            return {"loaded": True}
        return {"ok": True}

    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}

    plan = {
        "scope": "full",
        "form": [{"name": "intro", "start_bar": 0, "bars": 4}],
        "tracks": [{
            "role": "bass",
            "instrument": {"uri": "query:Synths#Operator"},
            "variants": [{"id": "v1", "notes": []}],
            "arrangement_clips": [{"section_index": 0, "variant_id": "v1", "loop_length": 4}],
        }],
        "events": [],
    }
    result = await apply_full_plan_v2(ctx, plan)
    cmds = [c[0] for c in ctx.lifespan_context["ableton"]._calls]
    # User-named tracks WITH content (instrument loaded) are preserved.
    # Only true zombies (empty + no devices) get cleaned by zombie-detection.
    assert cmds.count("delete_track") == 0, "User-named tracks WITH content should not be deleted"
    assert result["status"] == "ok"
