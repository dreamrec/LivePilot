"""Tests for develop-mode Seed Introspector."""

import pytest
from unittest.mock import MagicMock
from mcp_server.composer.develop.seed_introspector import (
    classify_track,
    infer_role_from_name,
    introspect_seed,
)


# ── classify_track ──────────────────────────────────────────────────

def test_classify_sample_trigger_canonical():
    """Single C3 note spanning the full clip = sample-trigger."""
    notes = [{"pitch": 60, "start_time": 0, "duration": 4, "velocity": 100}]
    assert classify_track(notes, clip_length=4.0) == "sample_trigger"


def test_classify_sample_trigger_with_overshoot_duration():
    """Duration >= clip_length still counts as sample-trigger."""
    notes = [{"pitch": 60, "start_time": 0, "duration": 8, "velocity": 100}]
    assert classify_track(notes, clip_length=4.0) == "sample_trigger"


def test_classify_midi_riff_multiple_notes():
    """Multiple notes = MIDI riff."""
    notes = [
        {"pitch": 45, "start_time": 0, "duration": 1, "velocity": 105},
        {"pitch": 48, "start_time": 1, "duration": 0.5, "velocity": 90},
        {"pitch": 45, "start_time": 2, "duration": 2, "velocity": 100},
    ]
    assert classify_track(notes, clip_length=4.0) == "midi_riff"


def test_classify_midi_riff_single_short_note():
    """Single note shorter than clip is still a riff (not a trigger pattern)."""
    notes = [{"pitch": 45, "start_time": 0, "duration": 1, "velocity": 100}]
    assert classify_track(notes, clip_length=4.0) == "midi_riff"


def test_classify_midi_riff_single_non_c3_note():
    """Single note at non-C3 pitch is NOT a sample-trigger pattern (despite spanning the clip)."""
    notes = [{"pitch": 45, "start_time": 0, "duration": 4, "velocity": 100}]
    assert classify_track(notes, clip_length=4.0) == "midi_riff"


def test_classify_empty_clip():
    """No notes = empty (track exists but no content yet)."""
    assert classify_track([], clip_length=4.0) == "empty"


# ── infer_role_from_name ────────────────────────────────────────────

@pytest.mark.parametrize("name,expected", [
    ("Drums", "drums"),
    ("DRUMS", "drums"),
    ("Kick", "drums"),
    ("Hi-Hat", "drums"),
    ("Perc", "drums"),
    ("Bass", "bass"),
    ("Sub Bass", "bass"),
    ("Lead", "lead"),
    ("Melody", "lead"),
    ("Pad", "pad"),
    ("Strings", "pad"),
    ("Texture", "texture"),
    ("Atmos", "texture"),
    ("FX", "fx"),
    ("Vocal", "vocal"),
    ("Chops", "vocal"),
])
def test_infer_role_from_name_known(name, expected):
    assert infer_role_from_name(name) == expected


def test_infer_role_from_name_unknown_returns_unknown():
    """Unrecognized name → 'unknown' (caller can fall back to register heuristic)."""
    assert infer_role_from_name("MyCustomTrack") == "unknown"


# ── introspect_seed (integration) ───────────────────────────────────

def _mock_ctx_for_5_track_session():
    """Build a mock ctx mirroring the live session: 5 tracks, scene 0 has 1-bar clips."""
    ableton = MagicMock()

    def send_command(cmd, args):
        if cmd == "get_session_info":
            return {
                "tempo": 122.0,
                "signature_numerator": 4,
                "signature_denominator": 4,
                "track_count": 5,
                "scene_count": 8,
                "tracks": [
                    {"index": 0, "name": "Drums", "mute": False},
                    {"index": 1, "name": "Bass", "mute": False},
                    {"index": 2, "name": "Lead", "mute": False},
                    {"index": 3, "name": "Pad", "mute": True},
                    {"index": 4, "name": "Texture", "mute": False},
                ],
            }
        if cmd == "get_song_scale":
            return {"root_note": "Am", "scale_name": "minor"}
        if cmd == "get_clip_info":
            # All clips are 1-bar = 4 beats
            return {
                "track_index": args["track_index"],
                "clip_index": args["clip_index"],
                "length": 4.0,
                "is_midi_clip": True,
                "is_audio_clip": False,
            }
        if cmd == "get_notes":
            ti = args["track_index"]
            # Mirror the live test session
            if ti == 0:  # Drums sample-trigger
                return {"notes": [{"pitch": 60, "start_time": 0, "duration": 4, "velocity": 100}]}
            if ti == 1:  # Bass riff in Am
                return {"notes": [
                    {"pitch": 45, "start_time": 0, "duration": 1, "velocity": 105},
                    {"pitch": 48, "start_time": 1, "duration": 0.5, "velocity": 90},
                    {"pitch": 45, "start_time": 2, "duration": 2, "velocity": 100},
                ]}
            if ti == 2:  # Lead melody
                return {"notes": [
                    {"pitch": 69, "start_time": 0, "duration": 2, "velocity": 85},
                    {"pitch": 72, "start_time": 2.5, "duration": 1, "velocity": 75},
                    {"pitch": 76, "start_time": 3.5, "duration": 0.5, "velocity": 70},
                ]}
            if ti == 3:  # Pad sample-trigger
                return {"notes": [{"pitch": 60, "start_time": 0, "duration": 4, "velocity": 100}]}
            if ti == 4:  # Texture sample-trigger
                return {"notes": [{"pitch": 60, "start_time": 0, "duration": 4, "velocity": 100}]}
            return {"notes": []}
        return {}

    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}
    return ctx


def test_introspect_seed_5_track_session():
    """Integration: introspect the live-test session shape, expect correct classification per track."""
    ctx = _mock_ctx_for_5_track_session()
    seed = introspect_seed(ctx, scene_index=0)

    assert seed["scene_index"] == 0
    assert seed["tempo"] == 122.0
    assert seed["clip_length"] == 4.0
    assert seed["time_signature"] == "4/4"
    assert seed["key"] == "Am"
    assert seed["scale_mode"] == "minor"

    tracks = seed["tracks"]
    assert len(tracks) == 5

    # Per-track expectations
    drums = tracks[0]
    assert drums["name"] == "Drums"
    assert drums["role"] == "drums"
    assert drums["classification"] == "sample_trigger"
    assert drums["muted"] is False

    bass = tracks[1]
    assert bass["role"] == "bass"
    assert bass["classification"] == "midi_riff"
    assert len(bass["notes"]) == 3

    lead = tracks[2]
    assert lead["role"] == "lead"
    assert lead["classification"] == "midi_riff"

    pad = tracks[3]
    assert pad["role"] == "pad"
    assert pad["classification"] == "sample_trigger"
    assert pad["muted"] is True  # CRITICAL: muted state preserved

    texture = tracks[4]
    assert texture["role"] == "texture"
    assert texture["classification"] == "sample_trigger"


def test_introspect_seed_no_ableton_returns_error():
    """Missing ableton context → returns error dict, doesn't crash."""
    ctx = MagicMock()
    ctx.lifespan_context = {}
    seed = introspect_seed(ctx)
    assert "error" in seed


def test_introspect_seed_empty_scene_returns_no_seed_found():
    """Scene with no clips on any track → 'no_seed_found' result."""
    ableton = MagicMock()

    def send_command(cmd, args):
        if cmd == "get_session_info":
            return {
                "tempo": 120.0, "signature_numerator": 4, "signature_denominator": 4,
                "track_count": 2, "scene_count": 8,
                "tracks": [
                    {"index": 0, "name": "Track 1", "mute": False},
                    {"index": 1, "name": "Track 2", "mute": False},
                ],
            }
        if cmd == "get_clip_info":
            # No clip in slot — return error or empty clip indicator
            return {"error": "no_clip"}
        if cmd == "get_notes":
            return {"notes": []}
        return {}

    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}
    seed = introspect_seed(ctx, scene_index=0)
    assert seed.get("status") == "no_seed_found" or seed.get("tracks") == []
