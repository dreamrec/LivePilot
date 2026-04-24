"""v1.20.2 BUG #5 regression: create_midi_track / create_audio_track
should warn when the requested name collides with an existing track
so downstream role-based resolvers (find_tracks_by_role) don't
silently match both.

Pre-fix (2026-04-24 live-test): setting track 2 to "Pad" via
set_track_name, then calling create_midi_track(index=2, name="Pad")
pushed the original audio track (now also named "Pad") to index 4.
The session ended up with two "Pad" tracks; widen_stereo and
darken_without_losing_width matched both and applied their mix
changes twice.

Fix: create_midi_track and create_audio_track emit a
``name_collision`` warning field in the response when another track
already carries the same name. Existing track indices listed in
``existing_tracks_with_same_name`` for caller visibility.

Campaign source: ~/Desktop/DREAM AI/demo Project/REPORT.md §BUG #4.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def _make_ctx(existing_tracks, create_response=None):
    """Build a minimal ctx where get_session_info returns the given tracks,
    and create_midi/audio_track returns the given response."""

    class _Ableton:
        def send_command(self, cmd, params=None):
            if cmd == "get_session_info":
                return {"tracks": existing_tracks}
            # create_midi_track / create_audio_track: return the index
            # of the new track + name
            return create_response or {
                "index": params.get("index", len(existing_tracks)),
                "name": params.get("name", ""),
            }

    return SimpleNamespace(lifespan_context={"ableton": _Ableton()})


class TestCreateTrackNameCollision:
    def test_create_midi_track_with_unique_name_no_warning(self):
        from mcp_server.tools.tracks import create_midi_track
        existing = [
            {"index": 0, "name": "Drums"},
            {"index": 1, "name": "Bass"},
        ]
        ctx = _make_ctx(
            existing,
            create_response={"index": 2, "name": "Pad"},
        )
        result = create_midi_track(ctx, index=2, name="Pad")
        assert result.get("name_collision") is False
        assert result.get("existing_tracks_with_same_name") == []

    def test_create_midi_track_with_colliding_name_warns(self):
        """When another track already has name='Pad', response should flag
        the collision and name the existing track indices."""
        from mcp_server.tools.tracks import create_midi_track
        existing = [
            {"index": 0, "name": "Drums"},
            {"index": 1, "name": "Bass"},
            {"index": 2, "name": "Pad"},  # existing collision
        ]
        ctx = _make_ctx(
            existing,
            create_response={"index": 3, "name": "Pad"},  # new track
        )
        result = create_midi_track(ctx, index=3, name="Pad")
        assert result.get("name_collision") is True, (
            f"expected name_collision=True, got response: {result}"
        )
        assert 2 in result.get("existing_tracks_with_same_name", []), (
            "must surface the index of the conflicting track"
        )

    def test_create_audio_track_colliding_name_also_warns(self):
        """Same behavior for audio tracks — shared codepath."""
        from mcp_server.tools.tracks import create_audio_track
        existing = [
            {"index": 0, "name": "Lead"},
            {"index": 1, "name": "Lead"},  # 2 existing "Lead"s
            {"index": 2, "name": "Drums"},
        ]
        ctx = _make_ctx(
            existing,
            create_response={"index": 3, "name": "Lead"},
        )
        result = create_audio_track(ctx, index=3, name="Lead")
        assert result.get("name_collision") is True
        existing_indices = sorted(result.get("existing_tracks_with_same_name", []))
        assert existing_indices == [0, 1]

    def test_no_name_provided_no_collision_check(self):
        """When name is None, no collision detection runs — Ableton assigns
        the default name like '5-MIDI'. We don't flag those as collisions."""
        from mcp_server.tools.tracks import create_midi_track
        existing = [{"index": 0, "name": "Drums"}]
        ctx = _make_ctx(existing, create_response={"index": 1, "name": "2-MIDI"})
        result = create_midi_track(ctx, index=1)
        # Response may or may not include name_collision field when no name given;
        # if it does, must be False.
        assert result.get("name_collision", False) is False

    def test_empty_name_rejected_existing_guard_unchanged(self):
        """Existing guard (empty string rejected) must still fire."""
        from mcp_server.tools.tracks import create_midi_track
        ctx = _make_ctx([])
        with pytest.raises(ValueError, match="cannot be empty"):
            create_midi_track(ctx, index=-1, name="   ")

    def test_collision_detection_is_case_sensitive(self):
        """'Pad' vs 'pad' are different names — don't warn on case mismatch.
        Ableton treats them as distinct and users may intentionally use case
        to disambiguate."""
        from mcp_server.tools.tracks import create_midi_track
        existing = [{"index": 0, "name": "pad"}]
        ctx = _make_ctx(existing, create_response={"index": 1, "name": "Pad"})
        result = create_midi_track(ctx, index=1, name="Pad")
        assert result.get("name_collision") is False
