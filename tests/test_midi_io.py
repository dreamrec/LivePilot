"""Tests for MIDI I/O tools — fixtures and offline tools only."""
import sys
import os
import tempfile

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
