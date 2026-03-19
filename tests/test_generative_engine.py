"""Unit tests for the generative engine."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._generative_engine import (
    bjorklund, rotate_pattern, identify_rhythm,
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
