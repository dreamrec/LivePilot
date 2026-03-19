"""Unit tests for the pure Python theory engine."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._theory_engine import (
    pitch_name, parse_key, get_scale_pitches, build_chord, detect_key,
    roman_numeral, roman_figure_to_pitches, chord_name,
    check_voice_leading, chordify,
)


class TestPitchName:
    def test_middle_c(self):
        assert pitch_name(60) == "C4"

    def test_a440(self):
        assert pitch_name(69) == "A4"

    def test_sharp_spelling(self):
        assert pitch_name(70) == "A#4"

    def test_low_range(self):
        assert pitch_name(0) == "C-1"


class TestParseKey:
    def test_simple_major(self):
        assert parse_key("C") == {"tonic": 0, "tonic_name": "C", "mode": "major"}

    def test_minor(self):
        assert parse_key("A minor") == {"tonic": 9, "tonic_name": "A", "mode": "minor"}

    def test_flat_key(self):
        assert parse_key("Bb major") == {"tonic": 10, "tonic_name": "A#", "mode": "major"}

    def test_dorian(self):
        assert parse_key("D dorian") == {"tonic": 2, "tonic_name": "D", "mode": "dorian"}

    def test_case_insensitive(self):
        assert parse_key("f# minor") == {"tonic": 6, "tonic_name": "F#", "mode": "minor"}


class TestScalePitches:
    def test_c_major(self):
        assert get_scale_pitches(0, "major") == [0, 2, 4, 5, 7, 9, 11]

    def test_a_minor(self):
        assert get_scale_pitches(9, "minor") == [9, 11, 0, 2, 4, 5, 7]


class TestBuildChord:
    def test_c_major_triad(self):
        c = build_chord(0, 0, "major")
        assert c["root_pc"] == 0
        assert c["quality"] == "major"
        assert set(c["pitch_classes"]) == {0, 4, 7}

    def test_vi_chord(self):
        c = build_chord(5, 0, "major")
        assert c["root_pc"] == 9
        assert c["quality"] == "minor"


class TestDetectKey:
    def test_c_major_progression(self):
        # I-vi-IV-V in C major
        notes = [
            {"pitch": 60, "start_time": 0, "duration": 1},
            {"pitch": 64, "start_time": 0, "duration": 1},
            {"pitch": 67, "start_time": 0, "duration": 1},
            {"pitch": 57, "start_time": 1, "duration": 1},
            {"pitch": 60, "start_time": 1, "duration": 1},
            {"pitch": 64, "start_time": 1, "duration": 1},
            {"pitch": 53, "start_time": 2, "duration": 1},
            {"pitch": 57, "start_time": 2, "duration": 1},
            {"pitch": 60, "start_time": 2, "duration": 1},
            {"pitch": 55, "start_time": 3, "duration": 1},
            {"pitch": 59, "start_time": 3, "duration": 1},
            {"pitch": 62, "start_time": 3, "duration": 1},
        ]
        result = detect_key(notes)
        assert result["tonic"] == 0  # C
        assert result["mode"] in ("major", "lydian", "mixolydian")

    def test_confidence_range(self):
        notes = [{"pitch": 60, "start_time": 0, "duration": 1}]
        result = detect_key(notes)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_alternatives_sorted(self):
        notes = [
            {"pitch": 60, "start_time": 0, "duration": 1},
            {"pitch": 64, "start_time": 1, "duration": 1},
            {"pitch": 67, "start_time": 2, "duration": 1},
        ]
        result = detect_key(notes)
        confs = [a["confidence"] for a in result["alternatives"]]
        assert confs == sorted(confs, reverse=True)


class TestRomanNumeral:
    def test_I_chord(self):
        r = roman_numeral([0, 4, 7], 0, "major")
        assert r["figure"] == "I"
        assert r["quality"] == "major"
        assert r["degree"] == 0

    def test_vi_chord(self):
        r = roman_numeral([9, 0, 4], 0, "major")
        assert r["figure"] == "vi"

    def test_inversion(self):
        r = roman_numeral([4, 7, 0], 0, "major")
        assert r["inversion"] == 1


class TestRomanFigureToPitches:
    def test_IV(self):
        r = roman_figure_to_pitches("IV", 0, "major")
        pcs = set(p % 12 for p in r["midi_pitches"])
        assert 5 in pcs and 9 in pcs and 0 in pcs  # F, A, C

    def test_bVII7(self):
        r = roman_figure_to_pitches("bVII7", 0, "major")
        pcs = set(p % 12 for p in r["midi_pitches"])
        assert 10 in pcs  # Bb

    def test_ii7(self):
        r = roman_figure_to_pitches("ii7", 0, "major")
        pcs = set(p % 12 for p in r["midi_pitches"])
        assert 2 in pcs and 5 in pcs and 9 in pcs  # D, F, A


class TestChordName:
    def test_major_triad(self):
        assert chord_name([60, 64, 67]) == "C-major triad"

    def test_minor_seventh(self):
        result = chord_name([57, 60, 64, 67])
        assert "minor seventh" in result


class TestVoiceLeading:
    def test_parallel_fifths(self):
        issues = check_voice_leading([48, 67], [50, 69])
        types = [i["type"] for i in issues]
        assert "parallel_fifths" in types

    def test_no_issues(self):
        issues = check_voice_leading([48, 64], [47, 67])
        assert issues == []

    def test_voice_crossing(self):
        issues = check_voice_leading([48, 67], [67, 48])
        types = [i["type"] for i in issues]
        assert "voice_crossing" in types


class TestChordify:
    def test_groups_simultaneous(self):
        notes = [
            {"pitch": 60, "start_time": 0.0, "duration": 1.0},
            {"pitch": 64, "start_time": 0.0, "duration": 1.0},
            {"pitch": 67, "start_time": 0.0, "duration": 1.0},
        ]
        result = chordify(notes)
        assert len(result) == 1
        assert set(result[0]["pitches"]) == {60, 64, 67}

    def test_skips_muted(self):
        notes = [
            {"pitch": 60, "start_time": 0.0, "duration": 1.0, "mute": True},
            {"pitch": 64, "start_time": 0.0, "duration": 1.0},
        ]
        result = chordify(notes)
        assert result[0]["pitches"] == [64]

    def test_duration_is_max(self):
        notes = [
            {"pitch": 60, "start_time": 0.0, "duration": 0.5},
            {"pitch": 64, "start_time": 0.0, "duration": 2.0},
        ]
        result = chordify(notes)
        assert result[0]["duration"] == 2.0
