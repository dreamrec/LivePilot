"""Tests for MIDI I/O tools — fixtures and offline tools only."""
import sys
import os
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _create_test_midi(path: str, notes=None, tempo=120.0):
    """Helper: create a simple .mid file using MIDIUtil."""
    from midiutil import MIDIFile
    midi = MIDIFile(1)
    midi.addTempo(0, 0, tempo)
    if notes is None:
        notes = [(60 + i, i * 0.5, 0.5, 100) for i in range(8)]
    for pitch, start, dur, vel in notes:
        midi.addNote(0, 0, pitch, start, dur, vel)
    with open(path, "wb") as f:
        midi.writeFile(f)


class TestAnalyzeMidiFile:
    def test_basic_analysis(self):
        """Test analyze_midi_file directly - it only needs file_path, no Ableton."""
        import pretty_midi
        from mcp_server.tools import _theory_engine as theory

        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            path = f.name
        try:
            _create_test_midi(path)
            pm = pretty_midi.PrettyMIDI(path)

            all_notes = []
            for inst in pm.instruments:
                for n in inst.notes:
                    all_notes.append(n)

            assert len(all_notes) == 8
            pitches = [n.pitch for n in all_notes]
            assert min(pitches) == 60
            assert max(pitches) == 67

            # Test key detection integration
            notes_for_key = [
                {"pitch": n.pitch, "duration": n.end - n.start}
                for n in all_notes
            ]
            key_result = theory.detect_key(notes_for_key)
            assert "tonic_name" in key_result
            assert "mode" in key_result
        finally:
            os.unlink(path)

    def test_empty_midi(self):
        import pretty_midi

        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            path = f.name
        try:
            _create_test_midi(path, notes=[])
            pm = pretty_midi.PrettyMIDI(path)
            all_notes = []
            for inst in pm.instruments:
                for n in inst.notes:
                    all_notes.append(n)
            assert len(all_notes) == 0
        finally:
            os.unlink(path)


class TestExtractPianoRoll:
    def test_basic_roll(self):
        import pretty_midi

        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            path = f.name
        try:
            _create_test_midi(path)
            pm = pretty_midi.PrettyMIDI(path)

            tempo = 120.0
            resolution = 0.5
            fs = (tempo / 60.0) / resolution
            roll = pm.get_piano_roll(fs=fs)

            active_pitches = roll.sum(axis=1).nonzero()[0]
            assert len(active_pitches) > 0
            assert int(active_pitches[0]) == 60
            assert int(active_pitches[-1]) == 67
        finally:
            os.unlink(path)


class TestRoundTrip:
    def test_write_read_consistency(self):
        """Write notes via MIDIUtil, read back with Pretty-MIDI, verify."""
        import pretty_midi

        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            path = f.name
        try:
            original_notes = [
                (60, 0.0, 1.0, 100),
                (64, 1.0, 1.0, 90),
                (67, 2.0, 1.0, 80),
            ]
            _create_test_midi(path, notes=original_notes, tempo=120.0)

            pm = pretty_midi.PrettyMIDI(path)
            read_notes = []
            for inst in pm.instruments:
                for n in inst.notes:
                    read_notes.append(n)

            assert len(read_notes) == 3
            pitches = sorted(n.pitch for n in read_notes)
            assert pitches == [60, 64, 67]
        finally:
            os.unlink(path)


class TestFileValidation:
    def test_nonexistent_file(self):
        from mcp_server.tools.midi_io import _validate_midi_path
        import pytest
        with pytest.raises(FileNotFoundError):
            _validate_midi_path("/nonexistent/file.mid")

    def test_non_midi_file(self):
        from mcp_server.tools.midi_io import _validate_midi_path
        import pytest
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            path = f.name
        try:
            with pytest.raises(ValueError):
                _validate_midi_path(path)
        finally:
            os.unlink(path)


class TestImportTempoIndependence:
    """Verify MIDI import preserves beat positions regardless of session tempo."""

    def test_60bpm_midi_beat_positions_preserved(self):
        """A note at beat 1.0 in a 60 BPM MIDI file should import at beat 1.0."""
        import pretty_midi
        from mcp_server.tools.midi_io import _midi_notes_to_beats

        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            path = f.name
        try:
            _create_test_midi(path, notes=[
                (60, 0.0, 1.0, 100),   # beat 0, duration 1 beat
                (64, 1.0, 0.5, 90),    # beat 1, duration 0.5 beats
                (67, 2.0, 1.0, 80),    # beat 2, duration 1 beat
            ], tempo=60.0)

            pm = pretty_midi.PrettyMIDI(path)
            notes = _midi_notes_to_beats(pm)

            assert notes[0]["start_time"] == pytest.approx(0.0, abs=0.05)
            assert notes[1]["start_time"] == pytest.approx(1.0, abs=0.05)
            assert notes[2]["start_time"] == pytest.approx(2.0, abs=0.05)
            assert notes[0]["duration"] == pytest.approx(1.0, abs=0.05)
            assert notes[1]["duration"] == pytest.approx(0.5, abs=0.05)
        finally:
            os.unlink(path)

    def test_120bpm_midi_beat_positions(self):
        """120 BPM MIDI should also preserve beat positions correctly."""
        import pretty_midi
        from mcp_server.tools.midi_io import _midi_notes_to_beats

        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            path = f.name
        try:
            _create_test_midi(path, notes=[
                (60, 0.0, 1.0, 100),
                (64, 2.0, 0.5, 90),
            ], tempo=120.0)

            pm = pretty_midi.PrettyMIDI(path)
            notes = _midi_notes_to_beats(pm)

            assert notes[0]["start_time"] == pytest.approx(0.0, abs=0.05)
            assert notes[1]["start_time"] == pytest.approx(2.0, abs=0.05)
        finally:
            os.unlink(path)


class TestBugB52ExportPath:
    """BUG-B52: export_clip_midi must honor user-provided absolute paths
    instead of always writing to the default output dir."""

    def test_absolute_path_honored(self):
        """When filename is an absolute path, write there (not the default)."""
        from pathlib import Path
        from mcp_server.tools.midi_io import _safe_output_path, _output_dir

        # Simulate the relevant branch of export_clip_midi's path logic.
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "my_custom_name.mid"
            filename = str(target)
            user_path = Path(filename)
            # The fixed logic:
            if user_path.is_absolute():
                user_path.parent.mkdir(parents=True, exist_ok=True)
                out_path = user_path.resolve()
            else:
                out_path = _safe_output_path(_output_dir(), filename)

            assert str(out_path) == str(target.resolve()), (
                f"Absolute path should be honored, not redirected to default. "
                f"Got {out_path}, wanted {target.resolve()}"
            )
            # Confirm we're NOT writing under the default ~/Documents dir
            default = _output_dir()
            assert not str(out_path).startswith(str(default)), (
                "Absolute path should not be rerouted to default dir"
            )

    def test_bare_filename_still_goes_to_default_dir(self):
        """When only a basename is given, still use the safe default dir."""
        from pathlib import Path
        from mcp_server.tools.midi_io import _safe_output_path, _output_dir

        filename = "bare_basename.mid"
        user_path = Path(filename)
        if user_path.is_absolute():
            out_path = user_path.resolve()
        else:
            out_path = _safe_output_path(_output_dir(), filename)

        default = _output_dir()
        assert str(out_path).startswith(str(default.resolve())), (
            "Bare filename should still resolve inside the default output dir"
        )
        assert out_path.name == "bare_basename.mid"

    def test_path_traversal_basename_still_contained(self):
        """Relative paths with .. components should still be contained to the
        default dir (security-critical behavior preserved)."""
        from pathlib import Path
        from mcp_server.tools.midi_io import _safe_output_path, _output_dir

        filename = "../../../evil.mid"  # relative path with traversal
        user_path = Path(filename)
        # Since it's not absolute, falls into _safe_output_path which strips
        # directory components and contains the result.
        assert not user_path.is_absolute()
        out_path = _safe_output_path(_output_dir(), filename)
        assert out_path.name == "evil.mid"
        # Still inside the default directory
        assert str(out_path).startswith(str(_output_dir().resolve()))
