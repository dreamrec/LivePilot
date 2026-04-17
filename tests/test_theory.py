"""Test theory tools — engine integration and tool registration."""

import pytest
from mcp_server.tools._theory_engine import (
    pitch_name, detect_key, chordify, roman_numeral, chord_name,
)


# -- Test data ---------------------------------------------------------------

C_MAJOR_TRIAD = [
    {"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100},
    {"pitch": 64, "start_time": 0.0, "duration": 1.0, "velocity": 100},
    {"pitch": 67, "start_time": 0.0, "duration": 1.0, "velocity": 100},
]

I_VI_IV_V_IN_C = [
    # C major (I)
    {"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100},
    {"pitch": 64, "start_time": 0.0, "duration": 1.0, "velocity": 100},
    {"pitch": 67, "start_time": 0.0, "duration": 1.0, "velocity": 100},
    # A minor (vi)
    {"pitch": 57, "start_time": 1.0, "duration": 1.0, "velocity": 100},
    {"pitch": 60, "start_time": 1.0, "duration": 1.0, "velocity": 100},
    {"pitch": 64, "start_time": 1.0, "duration": 1.0, "velocity": 100},
    # F major (IV)
    {"pitch": 53, "start_time": 2.0, "duration": 1.0, "velocity": 100},
    {"pitch": 57, "start_time": 2.0, "duration": 1.0, "velocity": 100},
    {"pitch": 60, "start_time": 2.0, "duration": 1.0, "velocity": 100},
    # G major (V)
    {"pitch": 55, "start_time": 3.0, "duration": 1.0, "velocity": 100},
    {"pitch": 59, "start_time": 3.0, "duration": 1.0, "velocity": 100},
    {"pitch": 62, "start_time": 3.0, "duration": 1.0, "velocity": 100},
]

PARALLEL_FIFTHS = [
    {"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100},  # C4
    {"pitch": 67, "start_time": 0.0, "duration": 1.0, "velocity": 100},  # G4
    {"pitch": 62, "start_time": 1.0, "duration": 1.0, "velocity": 100},  # D4
    {"pitch": 69, "start_time": 1.0, "duration": 1.0, "velocity": 100},  # A4
]


# -- Chordify tests (replaces _notes_to_stream tests) -----------------------

class TestChordify:
    def test_single_note(self):
        notes = [{"pitch": 60, "start_time": 0.0, "duration": 1.0}]
        result = chordify(notes)
        assert len(result) == 1
        assert result[0]["pitches"] == [60]

    def test_simultaneous_notes_become_chord(self):
        result = chordify(C_MAJOR_TRIAD)
        assert len(result) == 1
        assert len(result[0]["pitches"]) == 3

    def test_muted_notes_excluded(self):
        notes = [
            {"pitch": 60, "start_time": 0.0, "duration": 1.0, "mute": False},
            {"pitch": 64, "start_time": 0.0, "duration": 1.0, "mute": True},
        ]
        result = chordify(notes)
        assert result[0]["pitches"] == [60]

    def test_quantization_groups_near_times(self):
        notes = [
            {"pitch": 60, "start_time": 0.0, "duration": 1.0},
            {"pitch": 64, "start_time": 0.01, "duration": 1.0},
        ]
        result = chordify(notes)
        assert len(result) == 1, "Near-simultaneous notes should group as chord"

    def test_empty_notes(self):
        result = chordify([])
        assert len(result) == 0


# -- Key detection tests -----------------------------------------------------

class TestKeyDetection:
    def test_c_major_progression(self):
        result = detect_key(I_VI_IV_V_IN_C)
        assert result["tonic_name"] == "C"
        assert result["mode"] in ("major", "lydian", "mixolydian")

    def test_confidence_score(self):
        result = detect_key(I_VI_IV_V_IN_C)
        assert result["confidence"] > 0.7


# -- Roman numeral analysis tests -------------------------------------------

class TestRomanNumerals:
    def test_i_vi_iv_v(self):
        key_info = detect_key(I_VI_IV_V_IN_C)
        tonic = key_info["tonic"]
        mode = key_info["mode"]
        groups = chordify(I_VI_IV_V_IN_C)
        figures = []
        for g in groups:
            rn = roman_numeral(g["pitch_classes"], tonic, mode)
            figures.append(rn["figure"])
        assert figures == ['I', 'vi', 'IV', 'V']


# -- Utility tests -----------------------------------------------------------

class TestPitchName:
    def test_middle_c(self):
        assert pitch_name(60) == "C4"

    def test_a440(self):
        assert pitch_name(69) == "A4"


# -- Tool registration tests ------------------------------------------------

class TestTheoryToolsRegistered:
    def test_all_tools_exist(self):
        from mcp_server.tools import theory
        expected = [
            'analyze_harmony', 'suggest_next_chord', 'detect_theory_issues',
            'identify_scale', 'harmonize_melody', 'generate_countermelody',
            'transpose_smart',
        ]
        for name in expected:
            assert hasattr(theory, name), f"Missing tool: {name}"
            assert callable(getattr(theory, name)), f"Not callable: {name}"


# ─── BUG-B26 / B27 regressions — harmonize_melody ──────────────────────────


def _fake_ctx_with_melody(melody_notes):
    """Return a fake MCP context whose Ableton serves a fixed melody."""
    from types import SimpleNamespace
    def send(cmd, params=None):
        if cmd == "get_notes":
            return {"notes": melody_notes}
        return {}
    return SimpleNamespace(
        lifespan_context={"ableton": SimpleNamespace(send_command=send)}
    )


class TestBugB26BassVariety:
    """BUG-B26: harmonize_melody bass stuck on tonic pedal — 5/6 notes
    were D2 on the Pad Lush reproducer. Fix: chord selection scores
    away from immediate repetition and rewards functional progression."""

    def _pad_lush_melody(self):
        """Mirror the real Pad Lush data that reproduced the bug."""
        return [
            {"pitch": 50, "start_time": 0, "duration": 2, "velocity": 70},
            {"pitch": 53, "start_time": 2, "duration": 2, "velocity": 70},
            {"pitch": 57, "start_time": 4, "duration": 2, "velocity": 70},
            {"pitch": 50, "start_time": 6, "duration": 2, "velocity": 70},
            {"pitch": 53, "start_time": 8, "duration": 2, "velocity": 70},
            {"pitch": 60, "start_time": 10, "duration": 2, "velocity": 70},
        ]

    def test_bass_has_multiple_unique_pitches(self):
        """Regression guard: 4-voice harmonization of the Pad Lush melody
        must produce at least 2 distinct bass pitches."""
        from mcp_server.tools.theory import harmonize_melody
        ctx = _fake_ctx_with_melody(self._pad_lush_melody())
        result = harmonize_melody(ctx, track_index=3, clip_index=0, voices=4)
        bass_pitches = [n["pitch"] for n in result["bass"]]
        unique = set(bass_pitches)
        assert len(unique) >= 2, (
            f"BUG-B26 regressed — bass has only {len(unique)} unique pitch(es): "
            f"{bass_pitches}"
        )

    def test_bass_not_dominated_by_single_pitch(self):
        """No single bass pitch should occupy >80% of the line (the old
        bug produced 5/6 = 83% tonic pedal)."""
        from mcp_server.tools.theory import harmonize_melody
        ctx = _fake_ctx_with_melody(self._pad_lush_melody())
        result = harmonize_melody(ctx, track_index=3, clip_index=0, voices=4)
        bass_pitches = [n["pitch"] for n in result["bass"]]
        from collections import Counter
        counts = Counter(bass_pitches)
        most_common_count = counts.most_common(1)[0][1]
        ratio = most_common_count / len(bass_pitches)
        assert ratio <= 0.8, (
            f"BUG-B26 regressed — single bass pitch dominates {ratio:.0%}: "
            f"{counts}"
        )


class TestBugB27MelodyField:
    """BUG-B27: the response used to only expose 'soprano' and it was
    unclear whether that was the input or a new harmonization layer.
    Fix adds an explicit 'melody' alias so callers don't have to guess."""

    def test_melody_field_is_alias_of_soprano(self):
        from mcp_server.tools.theory import harmonize_melody
        melody = [
            {"pitch": 60, "start_time": 0, "duration": 1, "velocity": 80},
            {"pitch": 64, "start_time": 1, "duration": 1, "velocity": 80},
            {"pitch": 67, "start_time": 2, "duration": 1, "velocity": 80},
        ]
        ctx = _fake_ctx_with_melody(melody)
        result = harmonize_melody(ctx, track_index=0, clip_index=0, voices=4)
        assert "melody" in result, "BUG-B27: 'melody' field missing"
        assert result["melody"] == result["soprano"], (
            "melody should be identical to soprano (hymn-style convention)"
        )


class TestBugB28CountermelodyVariety:
    """BUG-B28: generate_countermelody returned a near-static pedal
    (3 unique pitches on a 6-note melody). Fix rewards imperfect
    consonances (3rds/6ths), penalizes exact repetition, and adds a
    sliding-window range-exploration bonus."""

    def _pad_lush_melody(self):
        return [
            {"pitch": 50, "start_time": 0, "duration": 2, "velocity": 70},
            {"pitch": 53, "start_time": 2, "duration": 2, "velocity": 70},
            {"pitch": 57, "start_time": 4, "duration": 2, "velocity": 70},
            {"pitch": 50, "start_time": 6, "duration": 2, "velocity": 70},
            {"pitch": 53, "start_time": 8, "duration": 2, "velocity": 70},
            {"pitch": 60, "start_time": 10, "duration": 2, "velocity": 70},
        ]

    def test_counter_has_at_least_4_unique_pitches(self):
        """With the sliding-window bonus, a 6-note melody should produce
        at least 4 distinct counter pitches under a fixed seed."""
        from mcp_server.tools.theory import generate_countermelody
        ctx = _fake_ctx_with_melody(self._pad_lush_melody())
        result = generate_countermelody(
            ctx, track_index=3, clip_index=0, species=1, seed=42
        )
        pitches = [n["pitch"] for n in result["counter_notes"]]
        unique = set(pitches)
        assert len(unique) >= 4, (
            f"BUG-B28 regressed — only {len(unique)} unique pitches: {pitches}"
        )

    def test_counter_spans_at_least_5_semitones(self):
        """Range-exploration test: the counter should walk through the pool,
        not hover on a single narrow window."""
        from mcp_server.tools.theory import generate_countermelody
        ctx = _fake_ctx_with_melody(self._pad_lush_melody())
        result = generate_countermelody(
            ctx, track_index=3, clip_index=0, species=1, seed=7
        )
        pitches = [n["pitch"] for n in result["counter_notes"]]
        span = max(pitches) - min(pitches)
        assert span >= 5, (
            f"BUG-B28 regressed — counter span only {span} semitones: {pitches}"
        )
