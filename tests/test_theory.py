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
