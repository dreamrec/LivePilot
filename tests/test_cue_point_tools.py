"""Tests for named locators — `create_cue_point` / `set_cue_point_name`.

The interesting behaviour lives in the MCP tool, not the Remote Script
handler, and for a reason that is easy to undo by accident.

Live's Song exposes exactly one way to make a locator: `set_or_delete_cue()`,
which acts at `song.current_song_time` and *toggles*. `CuePoint.time` has no
setter. So reaching a chosen beat means moving the playhead there first — and
`song.current_song_time = X` does not take effect until control returns to
Live's main loop. A seek-then-toggle performed inside one Remote Script
handler therefore toggles at the OLD playhead: asking for beats 0 and 64 both
produced a locator at beat 20, where the playhead already sat.

`create_cue_point` is consequently composed from separate round trips. The
fake below models toggle-at-playhead semantics faithfully, so an "optimisation"
that stops seeking first, or that toggles blind on an existing locator, fails
here rather than in a live set.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


class FakeArrangement:
    """Minimal Song stand-in: a playhead and a time-ordered locator list.

    Mirrors the real semantics that matter:
      - toggle acts at the CURRENT playhead, and DELETES when one is there
      - cue_points stays sorted by time, so indices shift on insert/delete
      - Live names new locators "1", "2", ... by creation ordinal
    """

    def __init__(self, playhead: float = 20.0, cues=None):
        self.playhead = playhead
        self.cues = list(cues or [])
        self.created = 0
        self.calls: list[str] = []

    # -- command surface ---------------------------------------------------
    def get_cue_points(self, params):
        self.calls.append("get_cue_points")
        ordered = sorted(self.cues, key=lambda c: c["time"])
        return {"cue_points": [
            {"index": i, "name": c["name"], "time": c["time"]}
            for i, c in enumerate(ordered)
        ]}

    def get_session_info(self, params):
        self.calls.append("get_session_info")
        return {"current_song_time": self.playhead}

    def jump_to_time(self, params):
        self.calls.append("jump_to_time")
        self.playhead = float(params["beat_time"])
        return {"current_song_time": self.playhead}

    def toggle_cue_point(self, params):
        self.calls.append("toggle_cue_point")
        for cue in self.cues:
            if abs(cue["time"] - self.playhead) < 1e-9:
                self.cues.remove(cue)          # toggle DELETES
                return {"toggled": True}
        self.created += 1
        self.cues.append({"name": str(self.created), "time": self.playhead})
        return {"toggled": True}

    def set_cue_point_name(self, params):
        self.calls.append("set_cue_point_name")
        ordered = sorted(self.cues, key=lambda c: c["time"])
        index = int(params["cue_index"])
        if index < 0 or index >= len(ordered):
            raise IndexError("Cue point index %d out of range" % index)
        ordered[index]["name"] = str(params["name"])
        return {"cue_index": index, "name": params["name"], "time": ordered[index]["time"]}

    def overrides(self):
        return {
            "get_cue_points": self.get_cue_points,
            "get_session_info": self.get_session_info,
            "jump_to_time": self.jump_to_time,
            "toggle_cue_point": self.toggle_cue_point,
            "set_cue_point_name": self.set_cue_point_name,
        }


def _payload(result):
    return result.data if hasattr(result, "data") else result


async def test_creates_named_locator_at_requested_beat(mcp_client_factory):
    arr = FakeArrangement(playhead=20.0)
    async with mcp_client_factory(arr.overrides()) as client:
        out = _payload(await client.call_tool(
            "create_cue_point", {"time": 64.0, "name": "MAIN A"}))

    assert out["created"] is True
    assert out["name"] == "MAIN A"
    assert out["time"] == 64.0
    assert [(c["name"], c["time"]) for c in arr.cues] == [("MAIN A", 64.0)]


async def test_seeks_before_toggling(mcp_client_factory):
    """The regression guard for the deferred-playhead bug.

    If the seek is dropped, or reordered after the toggle, the locator lands
    at the pre-existing playhead (20.0) instead of the requested beat.
    """
    arr = FakeArrangement(playhead=20.0)
    async with mcp_client_factory(arr.overrides()) as client:
        await client.call_tool("create_cue_point", {"time": 64.0, "name": "MAIN A"})

    assert arr.calls.index("jump_to_time") < arr.calls.index("toggle_cue_point")
    assert all(c["time"] != 20.0 for c in arr.cues), "locator landed at the old playhead"


async def test_is_idempotent_and_renames_rather_than_deleting(mcp_client_factory):
    """Toggling on an existing locator DELETES it, so a re-run must not toggle."""
    arr = FakeArrangement(playhead=0.0, cues=[{"name": "old", "time": 64.0}])
    async with mcp_client_factory(arr.overrides()) as client:
        out = _payload(await client.call_tool(
            "create_cue_point", {"time": 64.0, "name": "MAIN A"}))

    assert out["created"] is False
    assert "toggle_cue_point" not in arr.calls, "re-run toggled and would have deleted"
    assert [(c["name"], c["time"]) for c in arr.cues] == [("MAIN A", 64.0)]


async def test_restores_the_playhead(mcp_client_factory):
    arr = FakeArrangement(playhead=17.5)
    async with mcp_client_factory(arr.overrides()) as client:
        await client.call_tool("create_cue_point", {"time": 192.0, "name": "BREAKDOWN 1"})

    assert arr.playhead == 17.5


async def test_names_the_new_locator_not_a_neighbour(mcp_client_factory):
    """Indices are positional; inserting renumbers. The tool must resolve the
    new locator by beat, or it renames whichever one happens to share its old
    index."""
    arr = FakeArrangement(playhead=0.0, cues=[
        {"name": "INTRO", "time": 0.0},
        {"name": "OUTRO", "time": 448.0},
    ])
    async with mcp_client_factory(arr.overrides()) as client:
        await client.call_tool("create_cue_point", {"time": 192.0, "name": "BREAKDOWN 1"})

    assert sorted((c["name"], c["time"]) for c in arr.cues) == [
        ("BREAKDOWN 1", 192.0), ("INTRO", 0.0), ("OUTRO", 448.0),
    ]


async def test_rejects_negative_beat(mcp_client_factory):
    arr = FakeArrangement()
    async with mcp_client_factory(arr.overrides()) as client:
        with pytest.raises(Exception, match="time must be >= 0"):
            await client.call_tool("create_cue_point", {"time": -1.0, "name": "nope"})


async def test_set_cue_point_name_rejects_negative_index(mcp_client_factory):
    arr = FakeArrangement()
    async with mcp_client_factory(arr.overrides()) as client:
        with pytest.raises(Exception, match="cue_index must be >= 0"):
            await client.call_tool("set_cue_point_name", {"cue_index": -1, "name": "nope"})
