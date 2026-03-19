"""Tests for the offline audio perception engine (_perception_engine.py).

Run with: .venv/bin/python -m pytest tests/test_perception_engine.py -v
"""

from __future__ import annotations

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Test fixtures helpers
# ---------------------------------------------------------------------------

def _make_sine_wav(path, freq=440.0, duration=2.0, sr=44100, amplitude=0.5):
    import soundfile as sf
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    mono = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    sf.write(path, stereo, sr)
    return path


def _make_silence_wav(path, duration=2.0, sr=44100):
    import soundfile as sf
    stereo = np.zeros((int(sr * duration), 2), dtype=np.float32)
    sf.write(path, stereo, sr)
    return path


# ---------------------------------------------------------------------------
# compute_loudness tests
# ---------------------------------------------------------------------------

class TestComputeLoudness:
    def test_sine_loudness_is_negative(self, tmp_path):
        from mcp_server.tools._perception_engine import compute_loudness
        wav = _make_sine_wav(str(tmp_path / "sine.wav"))
        result = compute_loudness(wav)
        lufs = result["integrated_lufs"]
        assert -40 <= lufs <= 0, f"Expected LUFS between -40 and 0, got {lufs}"

    def test_silence_returns_floor(self, tmp_path):
        from mcp_server.tools._perception_engine import compute_loudness
        wav = _make_silence_wav(str(tmp_path / "silence.wav"))
        result = compute_loudness(wav)
        lufs = result["integrated_lufs"]
        assert lufs <= -70, f"Expected LUFS <= -70 for silence, got {lufs}"

    def test_streaming_targets_present(self, tmp_path):
        from mcp_server.tools._perception_engine import compute_loudness
        wav = _make_sine_wav(str(tmp_path / "sine.wav"))
        result = compute_loudness(wav)
        assert "meets_streaming" in result
        assert "spotify" in result["meets_streaming"]

    def test_sample_peak_present(self, tmp_path):
        from mcp_server.tools._perception_engine import compute_loudness
        wav = _make_sine_wav(str(tmp_path / "sine.wav"))
        result = compute_loudness(wav)
        assert "sample_peak_dbfs" in result
        assert isinstance(result["sample_peak_dbfs"], float)

    def test_short_term_in_full_mode(self, tmp_path):
        from mcp_server.tools._perception_engine import compute_loudness
        wav = _make_sine_wav(str(tmp_path / "sine.wav"), duration=5.0)
        result = compute_loudness(wav, detail="full")
        assert "short_term_lufs" in result
        assert isinstance(result["short_term_lufs"], list)
        assert len(result["short_term_lufs"]) > 0

    def test_file_not_found(self):
        from mcp_server.tools._perception_engine import compute_loudness
        with pytest.raises(FileNotFoundError):
            compute_loudness("/tmp/does_not_exist_12345.wav")


# ---------------------------------------------------------------------------
# compute_spectral tests
# ---------------------------------------------------------------------------

class TestComputeSpectral:
    def test_sine_centroid_near_frequency(self, tmp_path):
        from mcp_server.tools._perception_engine import compute_spectral
        # 1000 Hz sine — centroid should be between 800 and 1200 Hz
        wav = _make_sine_wav(str(tmp_path / "sine1k.wav"), freq=1000.0, duration=2.0)
        result = compute_spectral(wav)
        centroid = result["centroid_hz"]
        assert 800 <= centroid <= 1200, f"Expected centroid near 1000 Hz, got {centroid}"

    def test_five_band_balance(self, tmp_path):
        from mcp_server.tools._perception_engine import compute_spectral
        wav = _make_sine_wav(str(tmp_path / "sine.wav"))
        result = compute_spectral(wav)
        balance = result["band_balance"]
        for key in ("sub_60hz", "low_250hz", "mid_2khz", "high_8khz", "air_16khz"):
            assert key in balance, f"Missing band key: {key}"

    def test_flatness_near_zero_for_sine(self, tmp_path):
        from mcp_server.tools._perception_engine import compute_spectral
        wav = _make_sine_wav(str(tmp_path / "sine.wav"), freq=440.0)
        result = compute_spectral(wav)
        flatness = result["spectral_flatness"]
        assert flatness < 0.1, f"Expected flatness < 0.1 for pure sine, got {flatness}"

    def test_file_not_found(self):
        from mcp_server.tools._perception_engine import compute_spectral
        with pytest.raises(FileNotFoundError):
            compute_spectral("/tmp/does_not_exist_12345.wav")


# ---------------------------------------------------------------------------
# compare_to_reference tests
# ---------------------------------------------------------------------------

class TestCompareToReference:
    def test_identical_files_zero_delta(self, tmp_path):
        from mcp_server.tools._perception_engine import compare_to_reference
        wav = _make_sine_wav(str(tmp_path / "ref.wav"), amplitude=0.5, duration=3.0)
        result = compare_to_reference(wav, wav)
        assert abs(result["loudness_delta_lufs"]) < 0.5, (
            f"Identical file loudness delta should be ~0, got {result['loudness_delta_lufs']}"
        )
        assert abs(result["centroid_delta_hz"]) < 50, (
            f"Identical file centroid delta should be ~0, got {result['centroid_delta_hz']}"
        )

    def test_different_amplitude_shows_delta(self, tmp_path):
        from mcp_server.tools._perception_engine import compare_to_reference
        loud = _make_sine_wav(str(tmp_path / "loud.wav"), amplitude=0.9, duration=3.0)
        quiet = _make_sine_wav(str(tmp_path / "quiet.wav"), amplitude=0.05, duration=3.0)
        result = compare_to_reference(quiet, loud)
        # quiet vs loud — loudness_delta should be significantly negative
        assert result["loudness_delta_lufs"] < -5, (
            f"Expected loudness_delta < -5 for quiet vs loud, got {result['loudness_delta_lufs']}"
        )

    def test_suggestions_is_list(self, tmp_path):
        from mcp_server.tools._perception_engine import compare_to_reference
        wav = _make_sine_wav(str(tmp_path / "ref.wav"), duration=3.0)
        result = compare_to_reference(wav, wav)
        assert "suggestions" in result
        assert isinstance(result["suggestions"], list)


# ---------------------------------------------------------------------------
# read_audio_metadata tests
# ---------------------------------------------------------------------------

class TestReadAudioMetadata:
    def test_wav_basic_info(self, tmp_path):
        from mcp_server.tools._perception_engine import read_audio_metadata
        wav = _make_sine_wav(str(tmp_path / "sine.wav"), sr=44100)
        result = read_audio_metadata(wav)
        assert result["format"] in ("WAV", "wav", "PCM_16", "PCM_32", "FLOAT")
        assert result["sample_rate"] == 44100
        assert result["channels"] == 2

    def test_file_not_found(self):
        from mcp_server.tools._perception_engine import read_audio_metadata
        with pytest.raises(FileNotFoundError):
            read_audio_metadata("/tmp/does_not_exist_12345.wav")
