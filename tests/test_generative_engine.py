"""Unit tests for the generative engine."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._generative_engine import (
    bjorklund, rotate_pattern, identify_rhythm,
    tintinnabuli_voice,
)


class TestBjorklund:
    def test_tresillo(self):
        assert bjorklund(3, 8) == [1, 0, 0, 1, 0, 0, 1, 0]

    def test_cinquillo(self):
        assert bjorklund(5, 8) == [1, 0, 1, 1, 0, 1, 1, 0]

    def test_two_of_five(self):
        assert bjorklund(2, 5) == [1, 0, 1, 0, 0]

    def test_cumbia(self):
        assert bjorklund(3, 4) == [1, 0, 1, 1]

    def test_all_hits(self):
        assert bjorklund(8, 8) == [1, 1, 1, 1, 1, 1, 1, 1]

    def test_no_hits(self):
        assert bjorklund(0, 8) == [0, 0, 0, 0, 0, 0, 0, 0]

    def test_single_hit(self):
        assert bjorklund(1, 1) == [1]

    def test_one_of_four(self):
        assert bjorklund(1, 4) == [1, 0, 0, 0]

    def test_length_matches_steps(self):
        for steps in range(1, 17):
            for pulses in range(0, steps + 1):
                result = bjorklund(pulses, steps)
                assert len(result) == steps
                assert sum(result) == pulses


class TestRotatePattern:
    def test_rotate_zero(self):
        assert rotate_pattern([1, 0, 0, 1, 0], 0) == [1, 0, 0, 1, 0]

    def test_rotate_one(self):
        assert rotate_pattern([1, 0, 0, 1, 0], 1) == [0, 0, 1, 0, 1]

    def test_rotate_wraps(self):
        assert rotate_pattern([1, 0, 0], 3) == [1, 0, 0]


class TestIdentifyRhythm:
    def test_tresillo(self):
        assert identify_rhythm(3, 8) == "tresillo"

    def test_cinquillo(self):
        assert identify_rhythm(5, 8) == "cinquillo"

    def test_west_african_bell(self):
        assert identify_rhythm(7, 12) == "west african bell"

    def test_unknown(self):
        assert identify_rhythm(6, 13) is None


class TestTintinnabuli:
    def test_nearest_c_major(self):
        # C major triad = pitch classes [0, 4, 7]
        melody = [60, 62, 64, 65]
        triad_pcs = [0, 4, 7]  # C major
        result = tintinnabuli_voice(melody, triad_pcs, "nearest")
        assert len(result) == 4
        for p in result:
            assert p % 12 in triad_pcs

    def test_above(self):
        melody = [60]  # C4
        triad_pcs = [0, 4, 7]  # C major
        result = tintinnabuli_voice(melody, triad_pcs, "above")
        # Next triad tone above C4(60) is E4(64)
        assert result[0] == 64

    def test_below(self):
        melody = [64]  # E4
        triad_pcs = [0, 4, 7]  # C major
        result = tintinnabuli_voice(melody, triad_pcs, "below")
        # Next triad tone below E4(64) is C4(60)
        assert result[0] == 60

    def test_different_triad(self):
        melody = [69]  # A4
        triad_pcs = [9, 0, 4]  # A minor (A, C, E)
        result = tintinnabuli_voice(melody, triad_pcs, "above")
        # Above A4(69): C5(72)
        assert result[0] == 72
