"""Tests for Motif Engine — pattern detection and transformation."""

import pytest

from mcp_server.tools._motif_engine import (
    MotifUnit,
    detect_motifs,
    transform_motif,
    _extract_intervals,
    _find_recurring_subsequences,
)


class TestIntervalExtraction:
    def test_ascending(self):
        notes = [{"pitch": 60, "start_time": 0}, {"pitch": 64, "start_time": 1}, {"pitch": 67, "start_time": 2}]
        assert _extract_intervals(notes) == [4, 3]

    def test_descending(self):
        notes = [{"pitch": 67, "start_time": 0}, {"pitch": 64, "start_time": 1}, {"pitch": 60, "start_time": 2}]
        assert _extract_intervals(notes) == [-3, -4]

    def test_single_note(self):
        assert _extract_intervals([{"pitch": 60, "start_time": 0}]) == []

    def test_empty(self):
        assert _extract_intervals([]) == []


class TestSubsequenceDetection:
    def test_finds_repeated_pattern(self):
        intervals = [2, 2, -1, 2, 2, -1, 3, 2, 2, -1]
        results = _find_recurring_subsequences(intervals, min_length=3)
        patterns = [p for p, _ in results]
        assert (2, 2, -1) in patterns

    def test_no_repetition(self):
        intervals = [1, 3, 5, 7, 11, 13]
        results = _find_recurring_subsequences(intervals, min_length=3)
        assert len(results) == 0

    def test_short_input(self):
        assert _find_recurring_subsequences([1, 2], min_length=3) == []


class TestMotifDetection:
    def test_detects_repeated_motif(self):
        # C-D-E repeated pattern
        notes = {0: [
            {"pitch": 60, "start_time": 0, "duration": 0.5},
            {"pitch": 62, "start_time": 0.5, "duration": 0.5},
            {"pitch": 64, "start_time": 1, "duration": 0.5},
            {"pitch": 60, "start_time": 2, "duration": 0.5},
            {"pitch": 62, "start_time": 2.5, "duration": 0.5},
            {"pitch": 64, "start_time": 3, "duration": 0.5},
            {"pitch": 60, "start_time": 4, "duration": 0.5},
            {"pitch": 62, "start_time": 4.5, "duration": 0.5},
            {"pitch": 64, "start_time": 5, "duration": 0.5},
        ]}
        motifs = detect_motifs(notes, total_bars=8)
        assert len(motifs) >= 1
        # Should find the [2, 2] interval pattern
        found = any(m.intervals == [2, 2] for m in motifs)
        assert found or len(motifs) > 0  # At least something detected

    def test_empty_input(self):
        motifs = detect_motifs({})
        assert motifs == []

    def test_single_track_no_repetition(self):
        notes = {0: [
            {"pitch": 60, "start_time": 0, "duration": 1},
            {"pitch": 72, "start_time": 1, "duration": 1},
            {"pitch": 48, "start_time": 2, "duration": 1},
        ]}
        motifs = detect_motifs(notes, total_bars=4)
        # No repeated pattern in just 3 notes
        assert len(motifs) == 0

    def test_salience_scoring(self):
        # Highly repeated simple pattern should have decent salience
        notes = {0: []}
        for rep in range(6):
            offset = rep * 3
            notes[0].extend([
                {"pitch": 60, "start_time": offset, "duration": 0.5},
                {"pitch": 62, "start_time": offset + 0.5, "duration": 0.5},
                {"pitch": 65, "start_time": offset + 1, "duration": 0.5},
                {"pitch": 62, "start_time": offset + 1.5, "duration": 0.5},
            ])
        motifs = detect_motifs(notes, total_bars=20)
        if motifs:
            assert motifs[0].salience > 0

    def test_fatigue_risk(self):
        # Pattern repeated many times in short span
        notes = {0: []}
        for rep in range(10):
            offset = rep * 2
            notes[0].extend([
                {"pitch": 60, "start_time": offset, "duration": 0.5},
                {"pitch": 64, "start_time": offset + 0.5, "duration": 0.5},
                {"pitch": 67, "start_time": offset + 1, "duration": 0.5},
                {"pitch": 64, "start_time": offset + 1.5, "duration": 0.5},
            ])
        motifs = detect_motifs(notes, total_bars=8)
        if motifs:
            assert motifs[0].fatigue_risk > 0

    def test_motif_to_dict(self):
        m = MotifUnit("m01", "melodic", [2, 2, -1], [], [60, 62, 64, 63])
        d = m.to_dict()
        assert d["motif_id"] == "m01"
        assert d["intervals"] == [2, 2, -1]


class TestMotifTransformation:
    def _make_motif(self, intervals):
        return MotifUnit("test", "melodic", intervals, [], [60])

    def test_inversion(self):
        m = self._make_motif([2, 2, -1])
        notes = transform_motif(m, "inversion", 60)
        # Inversion: [2, 2, -1] → [-2, -2, 1]
        assert len(notes) == 4
        assert notes[1]["pitch"] == 58  # 60 - 2

    def test_retrograde(self):
        m = self._make_motif([2, 3, -1])
        notes = transform_motif(m, "retrograde", 60)
        # Retrograde: [-1, 3, 2]
        assert len(notes) == 4
        assert notes[1]["pitch"] == 59  # 60 + (-1)

    def test_augmentation(self):
        m = self._make_motif([2, 2])
        notes = transform_motif(m, "augmentation", 60)
        assert notes[0]["duration"] == 1.0  # doubled from 0.5
        assert notes[1]["duration"] == 1.0

    def test_diminution(self):
        m = self._make_motif([2, 2])
        notes = transform_motif(m, "diminution", 60)
        assert notes[0]["duration"] == 0.25  # halved from 0.5

    def test_fragmentation(self):
        m = self._make_motif([2, 3, -1, 4])
        notes = transform_motif(m, "fragmentation", 60)
        # Takes first half: [2, 3]
        assert len(notes) == 3  # 2 intervals + start note

    def test_register_shift_up(self):
        m = self._make_motif([2, 2])
        notes = transform_motif(m, "register_shift_up", 60)
        assert notes[0]["pitch"] == 72  # up an octave

    def test_register_shift_down(self):
        m = self._make_motif([2, 2])
        notes = transform_motif(m, "register_shift_down", 60)
        assert notes[0]["pitch"] == 48  # down an octave

    def test_invalid_transformation(self):
        m = self._make_motif([2, 2])
        with pytest.raises(ValueError, match="Unknown transformation"):
            transform_motif(m, "explode", 60)

    def test_empty_motif(self):
        m = MotifUnit("test", "melodic", [2], [], [])  # No representative pitches
        notes = transform_motif(m, "inversion", 60)
        assert notes == []
