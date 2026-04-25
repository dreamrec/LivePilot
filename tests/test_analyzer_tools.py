"""Tests for mcp_server/tools/analyzer.py — pure-Python helpers.

These tests cover the helper functions that don't require a live M4L
bridge or Ableton connection. They guard against the silent-failure
bugs caught in the 2026-04-18 creative session.
"""
from __future__ import annotations

import pytest

from mcp_server.tools.analyzer import (
    SIMPLER_SLICE_BASE_PITCH,
    _enrich_slice_response,
    _sanitize_pitch,
)


# ---------------------------------------------------------------------------
# BUG-F1: get_master_rms was emitting impossible MIDI notes (319.15, 89.55, 0)
# when the polyphonic pitch detector couldn't latch on. amplitude == 0 is the
# reliable signal; midi_note outside [0, 127] is always garbage.
# ---------------------------------------------------------------------------


def test_sanitize_pitch_clamps_out_of_range_midi_note():
    """Pitch detector can emit impossible MIDI values (319, -50) when confused by polyphony."""
    pitch = {"midi_note": 319.15, "amplitude": 0.0}
    result = _sanitize_pitch(pitch)
    assert result is None, "Zero-amplitude pitch should be dropped, not returned"


def test_sanitize_pitch_drops_zero_amplitude():
    """When amplitude is 0, the pitch reading is garbage — return None."""
    pitch = {"midi_note": 60.0, "amplitude": 0.0}
    assert _sanitize_pitch(pitch) is None


def test_sanitize_pitch_keeps_valid_reading():
    """A real pitch reading (reasonable MIDI, non-zero amplitude) passes through."""
    pitch = {"midi_note": 60.5, "amplitude": 0.25}
    result = _sanitize_pitch(pitch)
    assert result == {"midi_note": 60.5, "amplitude": 0.25}


def test_sanitize_pitch_handles_negative_midi_note():
    """Negative MIDI from failed pitch detection is clearly invalid."""
    pitch = {"midi_note": -50.0, "amplitude": 0.1}
    assert _sanitize_pitch(pitch) is None


def test_sanitize_pitch_handles_midi_above_127():
    """MIDI > 127 is impossible (MIDI spec uses 0-127 for note numbers)."""
    pitch = {"midi_note": 128.0, "amplitude": 0.4}
    assert _sanitize_pitch(pitch) is None


def test_sanitize_pitch_handles_midi_at_boundaries():
    """0 and 127 are valid MIDI notes — keep them."""
    assert _sanitize_pitch({"midi_note": 0.0, "amplitude": 0.1}) is not None
    assert _sanitize_pitch({"midi_note": 127.0, "amplitude": 0.1}) is not None


def test_sanitize_pitch_handles_missing_amplitude():
    """Defensive: if amplitude is missing, treat as invalid."""
    pitch = {"midi_note": 60.0}
    assert _sanitize_pitch(pitch) is None


def test_sanitize_pitch_handles_missing_midi_note():
    """Defensive: if midi_note is missing, treat as invalid."""
    pitch = {"amplitude": 0.5}
    assert _sanitize_pitch(pitch) is None


def test_sanitize_pitch_passes_none():
    """None input → None output, no crash."""
    assert _sanitize_pitch(None) is None


def test_sanitize_pitch_passes_empty_dict():
    """Empty dict → None."""
    assert _sanitize_pitch({}) is None


# ---------------------------------------------------------------------------
# BUG-F2: get_simpler_slices returned slice indices without disclosing that
# slice N plays at MIDI pitch 36+N. Users assumed C3 (60) and programmed
# silent MIDI.
# ---------------------------------------------------------------------------


def test_simpler_slice_base_pitch_is_c1():
    """Live 12 Simpler Slice mode uses C1 (MIDI 36) as slice 0. This is NOT C3."""
    assert SIMPLER_SLICE_BASE_PITCH == 36


def test_enrich_slice_response_adds_base_pitch():
    bridge_response = {
        "track": 0,
        "device": 0,
        "slice_count": 3,
        "slices": [
            {"index": 0, "frame": 0, "seconds": 0.0},
            {"index": 1, "frame": 13774, "seconds": 0.312},
            {"index": 2, "frame": 28944, "seconds": 0.656},
        ],
    }
    enriched = _enrich_slice_response(bridge_response)
    assert enriched["base_midi_pitch"] == 36


def test_enrich_slice_response_adds_slice_to_pitch_mapping():
    """Each slice gets a 'midi_pitch' field — no arithmetic for callers."""
    bridge_response = {
        "slice_count": 3,
        "slices": [
            {"index": 0, "frame": 0, "seconds": 0.0},
            {"index": 1, "frame": 13774, "seconds": 0.312},
            {"index": 2, "frame": 28944, "seconds": 0.656},
        ],
    }
    enriched = _enrich_slice_response(bridge_response)
    pitches = [s["midi_pitch"] for s in enriched["slices"]]
    assert pitches == [36, 37, 38]


def test_enrich_slice_response_handles_empty_slices():
    bridge_response = {"slice_count": 0, "slices": []}
    enriched = _enrich_slice_response(bridge_response)
    assert enriched["base_midi_pitch"] == 36
    assert enriched["slices"] == []


def test_enrich_slice_response_preserves_other_fields():
    """sample_rate, playback_mode, etc. pass through unchanged."""
    bridge_response = {
        "track": 0,
        "device": 0,
        "playback_mode": 2,
        "playback_mode_name": "Slicing",
        "sample_rate": 44100,
        "sample_length_frames": 235201,
        "slice_count": 1,
        "slices": [{"index": 0, "frame": 0, "seconds": 0.0}],
    }
    enriched = _enrich_slice_response(bridge_response)
    assert enriched["track"] == 0
    assert enriched["playback_mode_name"] == "Slicing"
    assert enriched["sample_rate"] == 44100
    assert enriched["slices"][0]["midi_pitch"] == 36


def test_enrich_slice_response_passes_none():
    """Defensive: None input → None output (don't crash)."""
    assert _enrich_slice_response(None) is None


def test_enrich_slice_response_handles_missing_slices_key():
    """If the bridge response is missing 'slices', treat as empty."""
    bridge_response = {"slice_count": 0}
    enriched = _enrich_slice_response(bridge_response)
    assert enriched["base_midi_pitch"] == 36
    assert enriched["slices"] == []


def test_enrich_slice_response_handles_missing_index_field():
    """BUG-audit-M2: if a slice entry is missing the `index` field
    (bridge version skew), fall back to the position in the list
    rather than raising KeyError mid list-comprehension."""
    bridge_response = {
        "slice_count": 3,
        "slices": [
            # no 'index' field — bridge might rename or omit in a future version
            {"frame": 0, "seconds": 0.0},
            {"frame": 13774, "seconds": 0.312},
            {"frame": 28944, "seconds": 0.656},
        ],
    }
    enriched = _enrich_slice_response(bridge_response)
    # Should fall back to positional index (0, 1, 2) → pitches 36, 37, 38
    pitches = [s["midi_pitch"] for s in enriched["slices"]]
    assert pitches == [36, 37, 38]


# ---------------------------------------------------------------------------
# Task 6: classify_simpler_slices MCP tool — end-to-end with synthetic WAV.
# ---------------------------------------------------------------------------


def test_classify_simpler_slices_end_to_end(tmp_path):
    """Load a synthetic two-kick WAV via the MCP tool and verify labels.

    Mocks the bridge so no Ableton / M4L connection is needed.
    """
    import numpy as np
    import soundfile as sf
    from unittest.mock import AsyncMock, MagicMock, patch

    from mcp_server.tools.analyzer import classify_simpler_slices

    # Build a WAV containing two back-to-back synthetic kicks
    sr = 44100
    duration_s = 0.3
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    hit = np.sin(2 * np.pi * 60 * t) * np.exp(-t * 8)
    audio = np.tile(hit.astype(np.float32), 2)
    wav_path = tmp_path / "synthetic_two_kicks.wav"
    sf.write(wav_path, audio, sr)
    hit_frames = int(sr * duration_s)

    slice_response = {
        "track": 0,
        "device": 0,
        "sample_rate": sr,
        "sample_length_frames": len(audio),
        "slice_count": 2,
        "slices": [
            {"index": 0, "frame": 0, "seconds": 0.0},
            {"index": 1, "frame": hit_frames, "seconds": duration_s},
        ],
    }

    bridge = MagicMock()
    bridge.send_command = AsyncMock(
        side_effect=[
            slice_response,  # get_simpler_slices
        ]
    )

    ctx = MagicMock()
    with patch("mcp_server.tools.analyzer._get_m4l", return_value=bridge), patch(
        "mcp_server.tools.analyzer._get_spectral", return_value={"analyzer": True}
    ), patch("mcp_server.tools.analyzer._require_analyzer"):
        import asyncio

        result = asyncio.run(
            classify_simpler_slices(
                ctx,
                track_index=0,
                device_index=0,
                file_path=str(wav_path),
            )
        )

    assert "slices" in result
    assert len(result["slices"]) == 2
    labels = [s["label"] for s in result["slices"]]
    assert labels == ["KICK", "KICK"]
    pitches = [s["midi_pitch"] for s in result["slices"]]
    assert pitches == [36, 37]
    assert result["classifier_version"] == "v1.0"


def test_classify_simpler_slices_returns_error_on_missing_wav(tmp_path):
    """BUG-audit-C3: when file_path points to a non-existent file,
    return a structured error dict instead of raising soundfile.SoundFileError."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from mcp_server.tools.analyzer import classify_simpler_slices

    slice_response = {
        "track": 0,
        "device": 0,
        "sample_rate": 44100,
        "sample_length_frames": 10000,
        "slice_count": 1,
        "slices": [{"index": 0, "frame": 0, "seconds": 0.0}],
    }

    bridge = MagicMock()
    bridge.send_command = AsyncMock(side_effect=[slice_response])
    ctx = MagicMock()
    with patch("mcp_server.tools.analyzer._get_m4l", return_value=bridge), patch(
        "mcp_server.tools.analyzer._get_spectral", return_value={"analyzer": True}
    ), patch("mcp_server.tools.analyzer._require_analyzer"):
        import asyncio

        missing = tmp_path / "does_not_exist.wav"
        result = asyncio.run(
            classify_simpler_slices(
                ctx,
                track_index=0,
                device_index=0,
                file_path=str(missing),
            )
        )

    assert "error" in result, "Missing WAV should return error dict, not raise"
    # Slices still returned for caller inspection
    assert "slices" in result


def test_classify_simpler_slices_returns_error_on_corrupt_wav(tmp_path):
    """BUG-audit-C3: corrupt/non-audio files return structured error, don't raise."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from mcp_server.tools.analyzer import classify_simpler_slices

    corrupt = tmp_path / "not_actually_audio.wav"
    corrupt.write_bytes(b"this is not a WAV file at all, just random bytes" * 100)

    slice_response = {
        "track": 0,
        "device": 0,
        "sample_rate": 44100,
        "slice_count": 1,
        "slices": [{"index": 0, "frame": 0, "seconds": 0.0}],
    }

    bridge = MagicMock()
    bridge.send_command = AsyncMock(side_effect=[slice_response])
    ctx = MagicMock()
    with patch("mcp_server.tools.analyzer._get_m4l", return_value=bridge), patch(
        "mcp_server.tools.analyzer._get_spectral", return_value={"analyzer": True}
    ), patch("mcp_server.tools.analyzer._require_analyzer"):
        import asyncio

        result = asyncio.run(
            classify_simpler_slices(
                ctx,
                track_index=0,
                device_index=0,
                file_path=str(corrupt),
            )
        )

    assert "error" in result
    assert "slices" in result


def test_classify_simpler_slices_returns_error_when_no_file_path():
    """When neither Remote Script nor bridge can resolve a path, surface a clear error.

    v1.23.3 path order: try Remote Script `get_simpler_file_path` first (Python
    LOM direct read), fall back to M4L bridge case if Remote Script doesn't
    yield a path. If both fail, surface the Remote Script error (more
    informative than the silent-bridge failure mode).
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from mcp_server.tools.analyzer import classify_simpler_slices

    slice_response = {
        "track": 0,
        "device": 0,
        "sample_rate": 44100,
        "sample_length_frames": 10000,
        "slice_count": 1,
        "slices": [{"index": 0, "frame": 0, "seconds": 0.0}],
    }

    bridge = MagicMock()
    # Bridge: 1st call returns slices (the get_simpler_slices step), 2nd call
    # is the bridge fallback for file_path lookup which we make raise.
    bridge.send_command = AsyncMock(
        side_effect=[slice_response, Exception("no such command")]
    )

    # Remote Script TCP mock: returns an error dict (Simpler has no sample),
    # which triggers the bridge fallback. The fallback also fails, so the
    # Remote Script error message is what gets surfaced.
    ableton = MagicMock()
    ableton.send_command = MagicMock(
        return_value={"error": "Simpler.sample.file_path is empty", "code": "STATE_ERROR"}
    )

    ctx = MagicMock()
    ctx.request_context.lifespan_context.get = MagicMock(return_value=ableton)

    with patch("mcp_server.tools.analyzer._get_m4l", return_value=bridge), patch(
        "mcp_server.tools.analyzer._get_spectral", return_value={"analyzer": True}
    ), patch("mcp_server.tools.analyzer._require_analyzer"):
        import asyncio

        result = asyncio.run(
            classify_simpler_slices(ctx, track_index=0, device_index=0)
        )

    assert "error" in result
    # The Remote Script error message is surfaced when the bridge fallback
    # also can't resolve a path.
    assert "Simpler.sample.file_path is empty" in result["error"]
    # Slices still present (enriched with midi_pitch) for inspection
    assert "slices" in result
    assert result["slices"][0]["midi_pitch"] == 36
