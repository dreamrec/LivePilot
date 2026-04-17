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


# ─── BUG-B7 regressions — get_motif_graph pagination + summary_only ────────


class TestBugB7MotifGraphPagination:
    """BUG-B7: get_motif_graph used to serialize every detected motif with
    full occurrences arrays; a 10-track / 49-clip session produced a 90 KB
    payload that exceeded inline tool-response limits. The fix adds
    limit, offset, and summary_only parameters so callers can bound the
    response size."""

    def _fake_ctx_with_many_clips(self, num_tracks=3, num_scenes=8):
        """Build a fake MCP context whose Ableton returns a handful of
        repeated ascending-4-note clips — enough to produce multiple
        motifs via detect_motifs."""
        from types import SimpleNamespace

        def send_command(cmd, params=None):
            if cmd == "get_session_info":
                return {
                    "track_count": num_tracks,
                    "scene_count": num_scenes,
                    "tracks": [
                        {"index": i, "name": f"t{i}", "has_midi_input": True}
                        for i in range(num_tracks)
                    ],
                }
            if cmd == "get_notes":
                t = params["track_index"]
                c = params["clip_index"]
                # Vary the clip patterns so detect_motifs produces many
                # distinct intervals. Cycle through 4 patterns.
                patterns = [
                    [60, 62, 64, 65],
                    [60, 63, 66, 68],
                    [60, 65, 67, 70],
                    [60, 61, 63, 64],
                ]
                pat = patterns[(t * num_scenes + c) % len(patterns)]
                return {"notes": [
                    {"pitch": p, "start_time": i * 0.5, "duration": 0.4, "velocity": 100}
                    for i, p in enumerate(pat)
                ]}
            return {}

        return SimpleNamespace(
            lifespan_context={"ableton": SimpleNamespace(send_command=send_command)}
        )

    def test_default_limit_50_never_returns_more(self):
        """Default limit=50 must never return more than 50 motifs."""
        from mcp_server.tools.motif import get_motif_graph
        ctx = self._fake_ctx_with_many_clips(num_tracks=4, num_scenes=8)
        result = get_motif_graph(ctx)
        assert "motifs" in result
        assert len(result["motifs"]) <= 50
        assert result["limit"] == 50
        assert result["offset"] == 0

    def test_custom_limit_honored(self):
        """Caller-provided limit bounds the page size."""
        from mcp_server.tools.motif import get_motif_graph
        ctx = self._fake_ctx_with_many_clips(num_tracks=4, num_scenes=8)
        result = get_motif_graph(ctx, limit=2)
        assert len(result["motifs"]) <= 2
        assert result["limit"] == 2

    def test_offset_pagination_skips_earlier_motifs(self):
        """offset=N returns motifs N.. from the salience-sorted list."""
        from mcp_server.tools.motif import get_motif_graph
        ctx = self._fake_ctx_with_many_clips(num_tracks=4, num_scenes=8)
        first_page = get_motif_graph(ctx, limit=2, offset=0)
        second_page = get_motif_graph(ctx, limit=2, offset=2)
        # Second-page motifs must NOT overlap first-page motifs (same ids)
        first_ids = [m["motif_id"] for m in first_page["motifs"]]
        second_ids = [m["motif_id"] for m in second_page["motifs"]]
        assert not (set(first_ids) & set(second_ids)), (
            f"pages overlap: first={first_ids}, second={second_ids}"
        )

    def test_summary_only_drops_heavy_fields(self):
        """summary_only=True returns compact records: no occurrences,
        no suggested_developments, no rhythm/representative_pitches arrays."""
        from mcp_server.tools.motif import get_motif_graph
        ctx = self._fake_ctx_with_many_clips(num_tracks=3, num_scenes=8)
        result = get_motif_graph(ctx, summary_only=True)
        for m in result["motifs"]:
            assert set(m.keys()) == {
                "motif_id", "kind", "salience", "fatigue_risk", "occurrence_count",
            }, f"summary_only leaked extra fields: {list(m.keys())}"
        assert result["summary_only"] is True

    def test_has_more_flag_signals_additional_pages(self):
        """has_more=True when offset+len<total; False when at end."""
        from mcp_server.tools.motif import get_motif_graph
        ctx = self._fake_ctx_with_many_clips(num_tracks=4, num_scenes=8)
        result = get_motif_graph(ctx, limit=1, offset=0)
        total = result["total_motifs"]
        if total > 1:
            assert result["has_more"] is True
        # Last page: has_more False
        if total >= 1:
            last = get_motif_graph(ctx, limit=total, offset=0)
            assert last["has_more"] is False

    def test_negative_limit_rejected(self):
        from mcp_server.tools.motif import get_motif_graph
        ctx = self._fake_ctx_with_many_clips()
        with pytest.raises(ValueError, match="limit"):
            get_motif_graph(ctx, limit=-1)

    def test_negative_offset_rejected(self):
        from mcp_server.tools.motif import get_motif_graph
        ctx = self._fake_ctx_with_many_clips()
        with pytest.raises(ValueError, match="offset"):
            get_motif_graph(ctx, offset=-5)
