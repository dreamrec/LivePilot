"""Test music21 theory tools — bridge function and analysis accuracy."""

import pytest
from mcp_server.tools.theory import (
    _notes_to_stream, _detect_key, _pitch_name,
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

# Parallel fifths: C-G → D-A (both voices move up by step, interval stays P5)
PARALLEL_FIFTHS = [
    {"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100},  # C4
    {"pitch": 67, "start_time": 0.0, "duration": 1.0, "velocity": 100},  # G4
    {"pitch": 62, "start_time": 1.0, "duration": 1.0, "velocity": 100},  # D4
    {"pitch": 69, "start_time": 1.0, "duration": 1.0, "velocity": 100},  # A4
]

D_DORIAN_MELODY = [
    {"pitch": 62, "start_time": 0.0, "duration": 0.5, "velocity": 100},   # D
    {"pitch": 64, "start_time": 0.5, "duration": 0.5, "velocity": 100},   # E
    {"pitch": 65, "start_time": 1.0, "duration": 0.5, "velocity": 100},   # F
    {"pitch": 67, "start_time": 1.5, "duration": 0.5, "velocity": 100},   # G
    {"pitch": 69, "start_time": 2.0, "duration": 0.5, "velocity": 100},   # A
    {"pitch": 71, "start_time": 2.5, "duration": 0.5, "velocity": 100},   # B (nat)
    {"pitch": 72, "start_time": 3.0, "duration": 1.0, "velocity": 100},   # C
]


# -- Bridge tests ------------------------------------------------------------

class TestNotesToStream:
    def test_single_note(self):
        notes = [{"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100}]
        s = _notes_to_stream(notes)
        elements = list(s.recurse().getElementsByClass('Note'))
        assert len(elements) == 1
        assert elements[0].pitch.midi == 60

    def test_simultaneous_notes_become_chord(self):
        s = _notes_to_stream(C_MAJOR_TRIAD)
        chords = list(s.recurse().getElementsByClass('Chord'))
        assert len(chords) == 1
        assert len(chords[0].pitches) == 3

    def test_muted_notes_excluded(self):
        notes = [
            {"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100, "mute": False},
            {"pitch": 64, "start_time": 0.0, "duration": 1.0, "velocity": 100, "mute": True},
        ]
        s = _notes_to_stream(notes)
        # Should have 1 note, not a chord
        m21_notes = list(s.recurse().getElementsByClass('Note'))
        assert len(m21_notes) == 1

    def test_key_hint_applied(self):
        from music21 import key
        s = _notes_to_stream(C_MAJOR_TRIAD, key_hint="A minor")
        keys = list(s.recurse().getElementsByClass(key.Key))
        assert len(keys) == 1
        assert keys[0].tonic.name == 'A'

    def test_quantization_groups_near_times(self):
        """Notes within 1/32 should group into same chord."""
        notes = [
            {"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100},
            {"pitch": 64, "start_time": 0.01, "duration": 1.0, "velocity": 100},  # ~1ms late
        ]
        s = _notes_to_stream(notes)
        chords = list(s.recurse().getElementsByClass('Chord'))
        assert len(chords) == 1, "Near-simultaneous notes should group as chord"

    def test_empty_notes(self):
        s = _notes_to_stream([])
        notes = list(s.recurse().getElementsByClass('GeneralNote'))
        assert len(notes) == 0


# -- Key detection tests -----------------------------------------------------

class TestKeyDetection:
    def test_c_major_progression(self):
        s = _notes_to_stream(I_VI_IV_V_IN_C)
        k = _detect_key(s)
        assert str(k) == "C major"

    def test_confidence_score(self):
        s = _notes_to_stream(I_VI_IV_V_IN_C)
        k = _detect_key(s)
        assert hasattr(k, 'correlationCoefficient')
        assert k.correlationCoefficient > 0.7

    def test_key_hint_overrides(self):
        from music21 import key
        s = _notes_to_stream(I_VI_IV_V_IN_C, key_hint="G major")
        k = _detect_key(s)
        # Should use the hint, not auto-detect
        assert str(k) == "G major"


# -- Roman numeral analysis tests -------------------------------------------

class TestRomanNumerals:
    def test_i_vi_iv_v(self):
        from music21 import roman
        s = _notes_to_stream(I_VI_IV_V_IN_C)
        k = _detect_key(s)
        chordified = s.chordify()
        figures = []
        for c in chordified.recurse().getElementsByClass('Chord'):
            rn = roman.romanNumeralFromChord(c, k)
            figures.append(rn.figure)
        assert figures == ['I', 'vi', 'IV', 'V']


# -- Utility tests -----------------------------------------------------------

class TestPitchName:
    def test_middle_c(self):
        assert _pitch_name(60) == "C4"

    def test_a440(self):
        assert _pitch_name(69) == "A4"


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
