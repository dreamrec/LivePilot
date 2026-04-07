from __future__ import annotations

import sys

import numpy as np
import pytest

from mcp_server.tools.perception import analyze_loudness, read_audio_metadata


def _make_sine_wav(path, freq=440.0, duration=1.0, sr=44100, amplitude=0.5):
    import soundfile as sf

    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    mono = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    sf.write(path, stereo, sr)
    return path


@pytest.mark.skipif(sys.platform == "win32", reason="Macintosh HD: paths are macOS-only")
def test_perception_tools_accept_max_style_macos_paths(tmp_path):
    wav = str(tmp_path / "capture.wav")
    _make_sine_wav(wav)
    max_style_path = "Macintosh HD:" + wav

    loudness = analyze_loudness(max_style_path)
    metadata = read_audio_metadata(max_style_path)

    assert "integrated_lufs" in loudness
    assert metadata["sample_rate"] == 44100
