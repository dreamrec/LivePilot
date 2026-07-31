"""Optional learned-embedding backend for the Listening Engine (CLAP).

WHAT THIS ADDS
--------------
``engine.py`` measures hand-designed DSP features — bands, LUFS, groove,
stereo, transients. Those answer "what changed, numerically". They cannot
answer "do these two renders sound like *different things*", because that is a
holistic perceptual judgement no single hand-picked feature captures.

A learned audio embedding does. Two captures go to vectors; the cosine distance
between them is one number for perceptual difference, complementary to (not a
replacement for) the DSP deltas.

WHY CLAP, AND WHY AUDIO-ONLY
----------------------------
Benchmarked against MERT on real capture families (2026-07-31,
``spikes/embedding-benchmark/``). Metric: between-iteration cosine distance
divided by within-take spread — i.e. how far apart two versions sit relative to
how much the embedding wobbles across different seconds of the *same* take.

    laion/clap-htsat-fused    mean SNR 2.96   min 2.71   Apache-2.0 / CC0
    laion/clap-htsat-unfused  mean SNR 2.63   min 2.19   Apache-2.0 / CC0
    MERT-v1-95M               mean SNR 3.71   min 1.07   CC-BY-NC-4.0
    MERT-v1-330M              mean SNR 3.55   min 1.57   CC-BY-NC-4.0

MERT wins the mean and loses the minimum. On the subtlest family (four
iterations of one bass pocket — the realistic kept-vs-superseded case) MERT-95M
scored 1.07: the gap between two different versions was only 7% above its own
within-take noise. CLAP-fused scored 3.00 there and stayed in a 2.71-3.17 band
across every family where MERT swung 1.07-6.36. A taste head has to work on the
*subtle* pairs, so the consistent model wins regardless of the average. CLAP is
also license-clean, where MERT is CC-BY-NC and LivePilot's own grant permits
end-user commercial use.

**Audio-audio only, deliberately.** CLAP is a joint text-audio model, but its
text tower was verified unreliable on this material: given the literal prompt
"white noise hiss" it ranked an actual white-noise capture 4th of 5, and
"a pure sine wave test tone" ranked the actual sine 3rd. It is trained on
general audio captions, not mastered music mixes at this subtlety. No
text-query surface is exposed here — a confidently wrong answer is worse than
no answer.

OPTIONAL BY DESIGN
------------------
torch + transformers are ~2 GB and most LivePilot users never need them, so
they are NOT in requirements.txt. Everything degrades exactly like the Splice
gRPC client: absent deps means ``is_available()`` is False and the DSP path is
untouched. Enable with::

    pip install torch transformers

Weights are downloaded by the user from HuggingFace on first use and are never
redistributed by LivePilot.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Benchmarked best of the license-clean options. htsat-unfused is ~2x faster
# with a lower floor (min SNR 2.19 vs 2.71) — switch only if latency dominates.
DEFAULT_MODEL = "laion/clap-htsat-fused"
CLAP_SR = 48000

# Analysis window. Captures are commonly 8-16 s; a bounded window keeps latency
# predictable and matches how the benchmark measured.
DEFAULT_SECONDS = 8.0

_lock = threading.Lock()
_state: dict = {"loaded": False, "model": None, "proc": None, "torch": None,
                "device": None, "model_id": None, "error": None}


def _try_import():
    """Import torch/transformers lazily. Returns None when unavailable."""
    try:
        import torch  # noqa: PLC0415
        from transformers import ClapModel, ClapProcessor  # noqa: PLC0415
        return torch, ClapModel, ClapProcessor
    except Exception as exc:  # noqa: BLE001 — any import failure means "off"
        _state["error"] = f"{type(exc).__name__}: {exc}"
        return None


def is_available() -> bool:
    """True if the optional embedding deps are importable."""
    return _try_import() is not None


def _pick_device(torch) -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _ensure_model(model_id: str = DEFAULT_MODEL):
    """Load the model once, under a lock. Returns None if unavailable."""
    with _lock:
        if _state["loaded"] and _state["model_id"] == model_id:
            return _state["model"]
        mods = _try_import()
        if mods is None:
            return None
        torch, ClapModel, ClapProcessor = mods
        try:
            device = _pick_device(torch)
            proc = ClapProcessor.from_pretrained(model_id)
            model = ClapModel.from_pretrained(model_id).to(device)
            model.train(False)  # inference mode
        except Exception as exc:  # noqa: BLE001 — download/OOM/etc
            _state["error"] = f"{type(exc).__name__}: {exc}"
            logger.warning("CLAP model load failed (%s); embeddings disabled", exc)
            return None
        _state.update(loaded=True, model=model, proc=proc, torch=torch,
                      device=device, model_id=model_id, error=None)
        return model


def last_error() -> Optional[str]:
    """Why embeddings are unavailable, if they are."""
    return _state["error"]


def _resample(mono: np.ndarray, sr: int) -> np.ndarray:
    if sr == CLAP_SR:
        return mono
    from scipy.signal import resample_poly  # noqa: PLC0415
    g = int(np.gcd(int(sr), CLAP_SR))
    return resample_poly(mono, CLAP_SR // g, sr // g)


def embed_audio(audio: np.ndarray, sr: int,
                seconds: float = DEFAULT_SECONDS,
                model_id: str = DEFAULT_MODEL) -> Optional[np.ndarray]:
    """L2-normalised CLAP audio embedding, or None if unavailable.

    ``audio`` is (n,) or (n, channels) float; channels are averaged to mono
    because CLAP is a mono model — stereo information is already covered by
    the DSP stereo metrics in engine.py.
    """
    model = _ensure_model(model_id)
    if model is None:
        return None
    torch, proc = _state["torch"], _state["proc"]

    mono = audio.mean(axis=1) if getattr(audio, "ndim", 1) == 2 else audio
    mono = np.asarray(mono, dtype=np.float32)
    if mono.size == 0:
        return None
    mono = _resample(mono, sr)
    if seconds:
        mono = mono[: int(seconds * CLAP_SR)]
    if mono.size < CLAP_SR // 10:  # < 100 ms is not worth embedding
        return None

    try:
        # transformers >=5 renamed the kwarg audios -> audio.
        try:
            inputs = proc(audio=mono, sampling_rate=CLAP_SR, return_tensors="pt")
        except (TypeError, ValueError):
            inputs = proc(audios=mono, sampling_rate=CLAP_SR, return_tensors="pt")
        inputs = {k: v.to(_state["device"]) for k, v in inputs.items()}
        with torch.no_grad():
            out = model.get_audio_features(**inputs)
        # <5 returned a tensor; >=5 returns BaseModelOutputWithPooling whose
        # pooler_output is the projected joint-space embedding.
        if not torch.is_tensor(out):
            out = getattr(out, "pooler_output", None)
            if out is None:
                return None
        vec = out.squeeze(0).float().cpu().numpy()
    except Exception as exc:  # noqa: BLE001 — never break the DSP path
        logger.warning("CLAP embedding failed: %s", exc)
        return None

    norm = float(np.linalg.norm(vec))
    return (vec / norm) if norm > 0 else None


def similarity(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> Optional[float]:
    """Cosine similarity of two L2-normalised embeddings, or None."""
    if a is None or b is None:
        return None
    return float(np.dot(a, b))


def distance(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> Optional[float]:
    """Cosine distance (1 - similarity), or None.

    Interpreting the number: the benchmark's within-take spread for
    clap-htsat-fused averaged ~0.045, and genuinely different iterations of one
    idea averaged ~0.136. So roughly:

        < 0.05   indistinguishable from re-rendering the same take
        0.05-0.1 a real but modest perceptual change
        > 0.1    clearly a different version

    These are calibration hints from a 3-family sample, not thresholds to
    branch on blindly.
    """
    sim = similarity(a, b)
    return None if sim is None else float(1.0 - sim)
