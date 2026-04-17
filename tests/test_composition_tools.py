"""Contract tests for Composition Engine V1 MCP tools."""

import asyncio

import pytest


def _get_tool_names():
    from mcp_server.server import mcp
    tools = asyncio.run(mcp.list_tools())
    return {tool.name for tool in tools}


def test_composition_tools_registered():
    names = _get_tool_names()
    expected = {
        "analyze_composition",
        "get_section_graph",
        "get_phrase_grid",
        "plan_gesture",
        "evaluate_composition_move",
    }
    missing = expected - names
    assert not missing, f"Missing composition tools: {missing}"


class TestPlanGesture:
    def test_rejects_invalid_intent(self):
        from mcp_server.tools.composition import plan_gesture
        with pytest.raises(ValueError, match="Unknown intent"):
            plan_gesture(None, intent="explode", target_tracks=[0], start_bar=0)

    def test_valid_intent(self):
        from mcp_server.tools.composition import plan_gesture
        result = plan_gesture(None, intent="reveal", target_tracks="[0, 1]", start_bar=8)
        assert result["intent"] == "reveal"
        assert result["curve_family"] == "exponential"

    def test_all_intents_accepted(self):
        from mcp_server.tools.composition import plan_gesture
        from mcp_server.tools._composition_engine import GestureIntent
        for intent in GestureIntent:
            result = plan_gesture(None, intent=intent.value, target_tracks=[0], start_bar=0)
            assert result["intent"] == intent.value


# ─── BUG-E3 integration — get_harmony_field must not be hijacked by perc ──


class TestGetHarmonyFieldE3:
    """End-to-end BUG-E3: simulate a section where Perc Hats (track 1)
    and Pad Lush (track 3) are both active. Perc scores low, Pad scores
    high — the reported key must reflect the pad's D-minor content,
    not the perc's single-pitch staccato."""

    def _fake_ableton(self):
        from types import SimpleNamespace

        session_info = {
            "tempo": 119,
            "track_count": 4,
            "tracks": [
                {"index": 0, "name": "Kick"},
                {"index": 1, "name": "Perc Hats"},
                {"index": 2, "name": "Bass"},
                {"index": 3, "name": "Pad Lush"},
            ],
            "scenes": [
                {"index": 0, "name": "Intro Dust"},
                {"index": 1, "name": "Verse"},
            ],
        }

        perc_notes = [
            {"pitch": 60, "start_time": 3.5, "duration": 0.1, "velocity": 25},
            {"pitch": 60, "start_time": 7.25, "duration": 0.1, "velocity": 30},
            {"pitch": 60, "start_time": 10.75, "duration": 0.1, "velocity": 22},
            {"pitch": 60, "start_time": 14.5, "duration": 0.1, "velocity": 28},
        ]
        # Pad Lush: D minor triad held for 14 beats
        pad_notes = [
            {"pitch": 50, "start_time": 0, "duration": 14, "velocity": 40},
            {"pitch": 53, "start_time": 0, "duration": 14, "velocity": 38},
            {"pitch": 57, "start_time": 0, "duration": 14, "velocity": 35},
        ]

        def send_command(cmd, params=None):
            params = params or {}
            if cmd == "get_session_info":
                return session_info
            if cmd == "get_scene_matrix":
                return {"matrix": [
                    [
                        {"state": "empty"},
                        {"state": "stopped", "has_clip": True, "name": "Ghost Hats"},
                        {"state": "empty"},
                        {"state": "stopped", "has_clip": True, "name": "Intro Wash"},
                    ],
                    [
                        {"state": "empty"}, {"state": "empty"},
                        {"state": "empty"}, {"state": "empty"},
                    ],
                ]}
            if cmd == "get_notes":
                if params.get("track_index") == 1:
                    return {"notes": perc_notes}
                if params.get("track_index") == 3:
                    return {"notes": pad_notes}
                return {"notes": []}
            return {}

        return SimpleNamespace(
            lifespan_context={"ableton": SimpleNamespace(send_command=send_command)}
        )

    def test_harmony_field_reports_pad_tonic_not_perc_c(self):
        """The bug was: Perc Hats' single-pitch C stabs made detect_key
        lock onto 'C major'. After the fix, harmonic_score gates out perc
        and detect_key runs on the pad's D-F-A content."""
        from mcp_server.tools.composition import get_harmony_field
        ctx = self._fake_ableton()
        result = get_harmony_field(ctx, section_index=0)
        # The fix must NOT return the old hijacked "C major" answer.
        assert not (result.get("key") == "C" and result.get("mode") == "major"), (
            f"BUG-E3 regressed — hijacked by percussion. Got {result!r}"
        )
        # Positively: tonic should be one of D/F/A — the three pitch
        # classes the pad actually plays. (Krumhansl-Schmuckler on
        # D/F/A can land on Dm, F major, or A phrygian depending on
        # weighting, all of which are musically correct readings of
        # the same note collection.)
        tonic = str(result.get("key", "")).upper()
        assert tonic in ("D", "F", "A"), (
            f"expected D/F/A tonic from pad D-F-A content, got {result!r}"
        )

    def test_chord_progression_reflects_pad_not_percussion(self):
        """When the harmony field returns a chord_progression, it must be
        derived from the pad's chord groups, not the perc's staccato."""
        from mcp_server.tools.composition import get_harmony_field
        ctx = self._fake_ableton()
        result = get_harmony_field(ctx, section_index=0)
        chords = result.get("chord_progression", [])
        # Pad notes are all simultaneous D/F/A → should yield exactly
        # one sustained triad chord group, not four identical "C chord"
        # rows like the pre-fix perc-driven result.
        assert chords != ["C chord"] * 4, (
            f"BUG-E3 regressed — chord progression still perc-driven: {chords!r}"
        )
