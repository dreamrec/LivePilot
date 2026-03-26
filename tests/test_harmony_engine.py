"""Unit tests for the neo-Riemannian harmony engine."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._harmony_engine import (
    parse_chord, parallel, leading_tone, relative,
    apply_transforms, chord_to_str,
)


class TestParseChord:
    def test_c_major(self):
        assert parse_chord("C major") == (0, "major")

    def test_f_sharp_minor(self):
        assert parse_chord("F# minor") == (6, "minor")

    def test_ab_major(self):
        assert parse_chord("Ab major") == (8, "major")

    def test_bb_minor(self):
        assert parse_chord("Bb minor") == (10, "minor")


class TestPRL:
    def test_parallel_c_major(self):
        assert parallel(0, "major") == (0, "minor")

    def test_parallel_c_minor(self):
        assert parallel(0, "minor") == (0, "major")

    def test_parallel_involution(self):
        for root in range(12):
            for q in ("major", "minor"):
                assert parallel(*parallel(root, q)) == (root, q)

    def test_leading_tone_c_major(self):
        assert leading_tone(0, "major") == (4, "minor")

    def test_leading_tone_e_minor(self):
        assert leading_tone(4, "minor") == (0, "major")

    def test_leading_tone_involution(self):
        for root in range(12):
            for q in ("major", "minor"):
                assert leading_tone(*leading_tone(root, q)) == (root, q)

    def test_relative_c_major(self):
        assert relative(0, "major") == (9, "minor")

    def test_relative_a_minor(self):
        assert relative(9, "minor") == (0, "major")

    def test_relative_involution(self):
        for root in range(12):
            for q in ("major", "minor"):
                assert relative(*relative(root, q)) == (root, q)


class TestApplyTransforms:
    def test_pl(self):
        result = apply_transforms(0, "major", "PL")
        assert result == (8, "major")

    def test_empty(self):
        assert apply_transforms(0, "major", "") == (0, "major")

    def test_single_r(self):
        assert apply_transforms(0, "major", "R") == (9, "minor")


class TestChordToStr:
    def test_c_major(self):
        assert chord_to_str(0, "major") == "C major"

    def test_ab_major(self):
        assert chord_to_str(8, "major") == "Ab major"

    def test_f_sharp_minor(self):
        assert chord_to_str(6, "minor") == "F# minor"


from mcp_server.tools._harmony_engine import (
    get_neighbors, find_shortest_path, classify_transform_sequence,
    get_chromatic_mediants,
)


class TestGetNeighbors:
    def test_c_major_depth1(self):
        result = get_neighbors(0, "major", depth=1)
        assert "P" in result
        assert result["P"] == (0, "minor")
        assert result["L"] == (4, "minor")
        assert result["R"] == (9, "minor")

    def test_depth2_has_compound(self):
        result = get_neighbors(0, "major", depth=2)
        assert "PL" in result
        assert result["PL"] == (8, "major")


class TestFindShortestPath:
    def test_c_to_ab(self):
        path = find_shortest_path((0, "major"), (8, "major"), max_depth=4)
        assert path["found"] is True
        assert path["steps"] == 2
        assert path["transforms"] == ["P", "L"]

    def test_same_chord(self):
        path = find_shortest_path((0, "major"), (0, "major"), max_depth=4)
        assert path["found"] is True
        assert path["steps"] == 0

    def test_unreachable_in_1(self):
        path = find_shortest_path((0, "major"), (8, "major"), max_depth=1)
        assert path["found"] is False


class TestClassifyTransformSequence:
    def test_pl_sequence(self):
        chords = [(0, "major"), (0, "minor"), (8, "major")]
        result = classify_transform_sequence(chords)
        assert result == ["P", "L"]

    def test_single_r(self):
        chords = [(0, "major"), (9, "minor")]
        result = classify_transform_sequence(chords)
        assert result == ["R"]

    def test_unknown_step(self):
        chords = [(0, "major"), (2, "major")]
        result = classify_transform_sequence(chords)
        assert result == ["?"]


class TestChromaticMediants:
    def test_c_major(self):
        result = get_chromatic_mediants(0, "major")
        assert result["upper_major_third"] == (4, "major")
        assert result["lower_major_third"] == (8, "major")


class TestChromaticMediantsPitchClass:
    def test_common_tones_use_pitch_classes(self):
        """Chromatic mediants should compare pitch classes, not absolute MIDI values."""
        from mcp_server.tools._harmony_engine import chord_to_midi
        c_major_pcs = {p % 12 for p in chord_to_midi(0, "major")}
        ab_major_pcs = {p % 12 for p in chord_to_midi(8, "major")}
        common = len(c_major_pcs & ab_major_pcs)
        assert common >= 1, "C major and Ab major should share at least 1 pitch class"
