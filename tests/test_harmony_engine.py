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

    def test_step_motion_classified_as_s2u(self):
        """BUG-B24: whole-step root motion with same quality used to return
        '?'. The extended alphabet now labels it S2u (whole-step up)
        so callers don't lose information about this common progression."""
        chords = [(0, "major"), (2, "major")]
        result = classify_transform_sequence(chords)
        assert result == ["S2u"]

    def test_truly_unknown_returns_question_mark(self):
        """Some transformations still lie outside the extended vocabulary —
        e.g. a major→diminished leap on an unusual root. Those must still
        surface as '?' so downstream classification can annotate properly."""
        # C major → C# diminished is neither PRL, nor step-same-quality,
        # nor any 2/3-step compound → still '?'.
        chords = [(0, "major"), (1, "diminished")]
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


# ─── BUG-B24 regressions — transform classification extensions ──────────────


class TestBugB24StepPrimitives:
    """BUG-B24: classify_transform_sequence used to return '?' for any
    progression not expressible via 1-step or 2-step PRL compounds —
    including Gm → Am (iv → v in Dm, a whole-step root shift).
    Fix adds 3-step compounds and S1/S2 step primitives."""

    def test_gm_to_am_is_step_motion(self):
        """Gm (7, minor) → Am (9, minor): whole-step up, same quality → S2u."""
        from mcp_server.tools._harmony_engine import classify_transform_sequence
        result = classify_transform_sequence([(7, "minor"), (9, "minor")])
        assert result == ["S2u"], f"expected ['S2u'], got {result!r}"

    def test_dm_to_gm_to_am_to_dm_has_no_unknown(self):
        """The full Dm iv-v progression has one step in it — should no
        longer produce '?' with the extended vocabulary."""
        from mcp_server.tools._harmony_engine import classify_transform_sequence
        progression = [(2, "minor"), (7, "minor"), (9, "minor"), (2, "minor")]
        result = classify_transform_sequence(progression)
        assert "?" not in result, f"unknown transitions in {result!r}"
        # Middle transform is the step; flanks are diatonic (LR-family)
        assert result[1].startswith("S2"), result

    def test_step_primitives_by_interval(self):
        """Verify all four S primitives at the interval level."""
        from mcp_server.tools._harmony_engine import classify_transform_sequence
        cases = [
            ((0, "major"), (1, "major"), "S1u"),
            ((0, "major"), (11, "major"), "S1d"),
            ((0, "major"), (2, "major"), "S2u"),
            ((0, "major"), (10, "major"), "S2d"),
        ]
        for a, b, expected in cases:
            result = classify_transform_sequence([a, b])
            assert result == [expected], (
                f"{a}→{b}: expected [{expected}], got {result!r}"
            )


class TestBugB24ClassifyProgressionHonesty:
    """classify_progression used to strip '?' before alphabet-purity check,
    so 'LR?LR' was labeled 'diatonic cycle fragment' even though a middle
    transform was unclassified. The fix tokenizes properly and annotates
    the result when non-core transforms are present."""

    def test_diatonic_with_step_gets_annotated(self):
        """Dm → Gm → Am → Dm has one step in the middle. Classification
        should still identify the diatonic framing but note the step."""
        from mcp_server.tools.harmony import classify_progression

        result = classify_progression(None, chords=["Dm", "Gm", "Am", "Dm"])
        assert "diatonic" in result["classification"].lower(), result
        # Must annotate the step motion so callers know it's not pure LR
        assert "step" in result["classification"].lower(), result

    def test_pure_lr_cycle_stays_unadorned(self):
        """C → Am → F → Dm (pure LR motion) should not be annotated."""
        from mcp_server.tools.harmony import classify_progression
        result = classify_progression(None, chords=["C", "Am", "F", "Dm"])
        assert "step" not in result["classification"].lower()
        assert "unclassified" not in result["classification"].lower()


# ─── BUG-B25 regressions — voice leading optimization ───────────────────────


class TestBugB25VoiceOptimization:
    """find_voice_leading_path used to return naive root-position voicings
    that jumped 6+ semitones per voice. _optimize_voicing picks the
    permutation + octave layout that minimizes total voice movement."""

    def test_dm_to_bb_keeps_common_tones(self):
        """Dm → Bb: D and F are common tones; only A needs to move 1 semi
        up to Bb."""
        from mcp_server.tools.harmony import _optimize_voicing
        prev = [62, 65, 69]
        target = [58, 62, 65]
        result = _optimize_voicing(prev, target)
        cost = sum(abs(t - f) for f, t in zip(prev, result))
        assert cost <= 1, (
            f"expected ≤1 semi total movement, got {cost} (voicing {result})"
        )

    def test_optimization_never_worse_than_naive(self):
        """The optimizer must never return a voicing WORSE than the input."""
        from mcp_server.tools.harmony import _optimize_voicing
        prev = [60, 64, 67]
        target = [65, 69, 72]
        result = _optimize_voicing(prev, target)
        naive_cost = sum(abs(t - f) for f, t in zip(prev, target))
        optimized_cost = sum(abs(t - f) for f, t in zip(prev, result))
        assert optimized_cost <= naive_cost

    def test_same_chord_stays_identity(self):
        """If target == prev, optimizer should not move anything."""
        from mcp_server.tools.harmony import _optimize_voicing
        prev = [60, 64, 67]
        result = _optimize_voicing(prev, [60, 64, 67])
        assert sum(abs(t - f) for f, t in zip(prev, result)) == 0

    def test_pitch_class_content_preserved(self):
        """Optimization must never change WHICH pitch classes are in the
        voicing — only their octave + voice assignment."""
        from mcp_server.tools.harmony import _optimize_voicing
        prev = [62, 65, 69]
        target = [58, 62, 65]
        target_pcs = {10, 2, 5}
        result = _optimize_voicing(prev, target)
        assert {p % 12 for p in result} == target_pcs
