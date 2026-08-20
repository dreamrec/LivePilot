"""
LivePilot - Cue point (locator) naming handler (1 command).

`get_cue_points` in arrangement.py already reads `cue.name`, but nothing in
the Remote Script could ever set it, so every locator created through
`toggle_cue_point` kept Live's default name -- "1", "2", "3". This supplies
the write half.

Creation deliberately lives in the MCP tool `create_cue_point`, not here.
Live's Song object offers exactly one way to make a locator:

    set_or_delete_cue()     acts at song.current_song_time, and toggles

There is no create-at-time API, and `CuePoint.time` has no setter (verified
on 12.4.3: "property of 'CuePoint' object has no setter"). So placing a
locator at a chosen beat means moving the playhead there first.

That cannot be done inside a single handler. Assigning `song.current_song_time`
does not take effect until control returns to Live's main loop, so a
seek-then-toggle in one handler toggles at the OLD playhead -- requesting beats
0 and 64 both produced a locator at beat 20, which was simply where the
playhead already sat. The MCP tool performs the seek and the toggle as separate
round trips, which gives Live the chance to apply the seek in between.
"""

from .router import register


@register("set_cue_point_name")
def set_cue_point_name(song, params):
    """Rename an existing cue point by its index.

    Indices are positional and unstable: `song.cue_points` is ordered by time,
    so adding or removing a locator renumbers everything after it while names
    stay attached to their locator. Re-read `get_cue_points` immediately
    before calling, or use the `create_cue_point` MCP tool, which addresses
    locators by beat instead.
    """
    cue_index = int(params["cue_index"])
    name = str(params["name"])
    cue_points = list(song.cue_points)
    if cue_index < 0 or cue_index >= len(cue_points):
        raise IndexError(
            "Cue point index %d out of range (0..%d)"
            % (cue_index, len(cue_points) - 1)
        )
    cue_points[cue_index].name = name
    return {
        "cue_index": cue_index,
        "name": name,
        "time": cue_points[cue_index].time,
    }
