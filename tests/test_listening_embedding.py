"""Optional CLAP embedding backend for the Listening Engine.

These run WITHOUT torch/transformers installed — that is the point. The backend
is optional (~2 GB of deps most users never need), so the contract under test is
that its absence is inert: the DSP path is untouched, the tools still return
their full report, and the caller gets an actionable install hint instead of a
traceback.

The numeric behaviour of the model itself is not unit-testable here (no weights
in CI); it is characterised in spikes/embedding-benchmark/ against real capture
families. What IS tested here is every line of glue around it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server.listening import embedding  # noqa: E402
from mcp_server.listening import tools as listening_tools  # noqa: E402


TORCH_PRESENT = embedding.is_available()


# --- pure math, no model needed ---------------------------------------------

def test_similarity_and_distance_are_complementary():
    a = np.array([1.0, 0.0, 0.0])
    b = np.array([0.0, 1.0, 0.0])
    assert embedding.similarity(a, a) == pytest.approx(1.0)
    assert embedding.distance(a, a) == pytest.approx(0.0)
    assert embedding.similarity(a, b) == pytest.approx(0.0)
    assert embedding.distance(a, b) == pytest.approx(1.0)


def test_similarity_tolerates_missing_embeddings():
    """A None on either side must yield None, not a TypeError — the whole
    point is that an absent backend cannot break a caller."""
    v = np.array([1.0, 0.0])
    assert embedding.similarity(None, v) is None
    assert embedding.similarity(v, None) is None
    assert embedding.distance(None, None) is None


# --- graceful degradation ----------------------------------------------------

def _force_unavailable(monkeypatch):
    monkeypatch.setattr(embedding, "_try_import", lambda: None)
    monkeypatch.setattr(embedding, "_state",
                        dict(embedding._state, loaded=False, model=None,
                             error="ModuleNotFoundError: No module named 'torch'"))


def test_embed_audio_returns_none_without_backend(monkeypatch):
    _force_unavailable(monkeypatch)
    out = embedding.embed_audio(np.zeros(48000, dtype=np.float32), 48000)
    assert out is None, "absent backend must return None, not raise"


def test_capture_reports_actionable_hint_when_backend_absent(monkeypatch, tmp_path):
    """The failure mode a user actually meets: they pass embed=True without the
    extra installed. They must get an install command, not a stack trace."""
    _force_unavailable(monkeypatch)
    block = listening_tools._embedding_block(
        np.zeros((48000, 2), dtype=np.float32), 48000, include_vector=True)
    assert block["available"] is False
    assert "pip install torch transformers" in block["reason"]
    assert "not redistributed" in block["reason"], (
        "the hint must say LivePilot does not redistribute the weights — that "
        "is the licensing posture, not a detail"
    )


def test_perceptual_distance_degrades_without_backend(monkeypatch):
    _force_unavailable(monkeypatch)
    z = np.zeros((48000, 2), dtype=np.float32)
    block = listening_tools._perceptual_distance(z, 48000, z, 48000)
    assert block["available"] is False
    assert "distance" not in block, "must not invent a distance it cannot measure"


# --- the tools stay whole ----------------------------------------------------

def _tone(path, sr=48000, secs=2.0, freq=220.0):
    import soundfile as sf
    t = np.linspace(0, secs, int(sr * secs), endpoint=False)
    x = (0.2 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sf.write(str(path), np.stack([x, x], axis=1), sr)
    return str(path)


def test_embed_false_adds_no_key(tmp_path):
    """Default path must be byte-for-byte what it was before this feature —
    no key, no import, no cost."""
    p = _tone(tmp_path / "a.wav")
    out = listening_tools.listen_capture(p)
    assert "embedding" not in out


def test_embed_true_never_breaks_the_dsp_report(monkeypatch, tmp_path):
    """With the backend absent, embed=True still returns the full DSP report."""
    _force_unavailable(monkeypatch)
    p = _tone(tmp_path / "a.wav")
    out = listening_tools.listen_capture(p, embed=True)
    assert out["embedding"]["available"] is False
    # the canonical snapshot evaluate_move consumes must be intact
    for key in ("spectrum", "rms", "peak", "loudness"):
        assert key in out["snapshot"], f"embed=True damaged the snapshot ({key} missing)"


def test_listen_ab_still_produces_a_verdict_with_embed(monkeypatch, tmp_path):
    _force_unavailable(monkeypatch)
    a = _tone(tmp_path / "a.wav", freq=220.0)
    b = _tone(tmp_path / "b.wav", freq=440.0)
    out = listening_tools.listen_ab(a, b, embed=True)
    assert out["verdict"]
    assert out["perceptual_distance"]["available"] is False
    assert "dimension_deltas" in out


# --- with the real backend (skipped unless the extra is installed) -----------

@pytest.mark.skipif(not TORCH_PRESENT,
                    reason="optional extra not installed (pip install torch transformers)")
def test_identical_audio_has_zero_distance(tmp_path):
    """Determinism guard: the same audio twice must sit at distance ~0, or the
    calibration thresholds in _perceptual_distance are meaningless."""
    import soundfile as sf
    p = _tone(tmp_path / "a.wav", secs=4.0)
    audio, sr = sf.read(p, dtype="float32", always_2d=True)
    v1 = embedding.embed_audio(audio, sr)
    v2 = embedding.embed_audio(audio, sr)
    assert v1 is not None
    assert embedding.distance(v1, v2) == pytest.approx(0.0, abs=1e-4)
    assert float(np.linalg.norm(v1)) == pytest.approx(1.0, abs=1e-4)
