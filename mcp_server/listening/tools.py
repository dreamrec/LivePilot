"""Listening Engine MCP tools.

Tools:
- ``listen_capture(file, bpm)`` — full perceptual report for one capture
- ``listen_ab(before_file, after_file, bpm)`` — what changed between two
  captures of the same musical span, with evaluate_move-ready snapshots

Workflow (the perception loop):
    capture_audio(filename="before") -> apply the creative move ->
    capture_audio(filename="after") -> listen_ab("before", "after",
    bpm=<session tempo>) -> evaluate_move(goal_vector=...,
    before_snapshot=result["before_snapshot"],
    after_snapshot=result["after_snapshot"])
"""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, Optional

from ..server import mcp
from . import engine

CAPTURE_DIR = os.path.expanduser("~/Documents/LivePilot/captures")
_AUDIO_EXTS = (".wav", ".aiff", ".aif")


def _resolve_capture_path(file: str) -> str:
    """Accept an absolute path, or a bare capture name (with or without
    extension) resolved against ~/Documents/LivePilot/captures/."""
    expanded = os.path.expanduser(file)
    if os.path.isabs(expanded):
        if os.path.isfile(expanded):
            return expanded
        raise ValueError(f"Audio file not found: {expanded}")

    candidates = [os.path.join(CAPTURE_DIR, file)]
    if not file.lower().endswith(_AUDIO_EXTS):
        candidates += [os.path.join(CAPTURE_DIR, file + ext)
                       for ext in _AUDIO_EXTS]
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise ValueError(
        f"Capture '{file}' not found in {CAPTURE_DIR} "
        f"(tried extensions {_AUDIO_EXTS}). Record one with capture_audio."
    )


def _analyze(file: str, bpm: Optional[float],
             seconds: Optional[float]) -> engine.ClipFeatures:
    """Feature-only view. Kept as the narrow entry point callers already use."""
    features, _audio, _sr = _analyze_ex(file, bpm, seconds)
    return features


def _analyze_ex(file: str, bpm: Optional[float], seconds: Optional[float]):
    """Features plus the decoded audio, so an optional embedding pass does not
    re-read and re-decode the same file (and cannot drift from what was
    measured)."""
    try:
        import soundfile as sf
    except ImportError as exc:  # pragma: no cover
        raise ValueError(
            "soundfile is required for listening tools — pip install soundfile"
        ) from exc
    try:
        import librosa  # noqa: F401
    except ImportError as exc:
        raise ValueError(
            "librosa is required for listening tools — pip install librosa"
        ) from exc

    path = _resolve_capture_path(file)
    try:
        audio, sr = sf.read(path, dtype="float32", always_2d=True)
    except Exception as exc:
        raise ValueError(
            f"Could not read audio file {path}: {exc}. A 0-byte or "
            "truncated-header file usually means the capture is still being "
            "written (capture_audio can take up to ~480ms to finish); wait "
            "briefly and retry."
        ) from exc
    if seconds:
        audio = audio[: int(sr * float(seconds))]
    if len(audio) == 0:
        raise ValueError(f"Audio file is empty: {path}")
    features = engine.extract_features(audio, sr, bpm=float(bpm) if bpm else None)
    return features, audio, sr


def _embedding_block(audio, sr, include_vector: bool) -> dict:
    """Optional CLAP block. Never raises — absent deps degrade to a reason."""
    from . import embedding  # noqa: PLC0415 — optional, import at call time

    if not embedding.is_available():
        return {
            "available": False,
            "reason": (
                "Optional embedding backend not installed. "
                "pip install torch transformers  (~2 GB; weights download from "
                "HuggingFace on first use and are not redistributed by LivePilot)"
            ),
            "detail": embedding.last_error(),
        }
    vec = embedding.embed_audio(audio, sr)
    if vec is None:
        return {"available": False,
                "reason": "embedding backend present but returned nothing",
                "detail": embedding.last_error()}
    block = {"available": True, "model": embedding.DEFAULT_MODEL, "dim": int(vec.shape[0])}
    if include_vector:
        block["vector"] = [round(float(x), 6) for x in vec]
    return block


@mcp.tool()
def listen_capture(
    file: str,
    bpm: Optional[float] = None,
    seconds: Optional[float] = None,
    embed: bool = False,
) -> dict[str, Any]:
    """Full offline perceptual report for one master-bus capture.

    Analyzes a WAV/AIFF produced by ``capture_audio`` (pass the capture
    name or an absolute path). Returns:

    - ``snapshot`` — canonical sonic snapshot (9-band spectrum, rms, peak,
      spectral_shape, onset, novelty, loudness) directly usable as
      ``evaluate_move``'s before_snapshot/after_snapshot
    - ``extended`` — offline-only measurements: stereo width + correlation
      + bass-mono check, groove microtiming (pass ``bpm`` = session tempo
      for grid-based metrics; timing resolution ~4 ms), transient character,
      per-band loudness movement, technical polish (clipping, DC, headroom)
    - ``dimensions`` — 0..1 values; the nine canonical ones are computed by
      the evaluation stack's own extractor, extended ones (width, polish,
      motion_cv, groove_tightness) use non-canonical names

    ``seconds`` caps analysis to the first N seconds of the file
    (omitted/0 analyzes the full file); ``bpm`` omitted/0 falls back to
    tempo estimation. See livepilot-core references/perception.md
    #listen_capture--listen_ab--offline-perception-loop for the full
    offline-vs-real-time model.

    ``embed=True`` additionally returns an ``embedding`` block with a
    512-dim CLAP vector — the taste anchor to persist alongside a
    kept/undone outcome so a preference model can be trained on real
    outcomes later. Off by default: it needs the optional
    ``torch``+``transformers`` extra and adds ~6 KB to the response.
    Reports ``available: false`` with an install hint when absent — the
    DSP measurements above are unaffected either way.
    """
    report, audio, sr = _analyze_ex(file, bpm, seconds)
    out = asdict(report)
    if embed:
        out["embedding"] = _embedding_block(audio, sr, include_vector=True)
    return out


@mcp.tool()
def listen_ab(
    before_file: str,
    after_file: str,
    bpm: Optional[float] = None,
    seconds: Optional[float] = None,
    embed: bool = False,
) -> dict[str, Any]:
    """Compare two captures of the same musical span — what changed after a creative move.

    This is the perception loop's reflex arc: capture before a move,
    capture after, and this tool reports the empirical perceptual delta.
    Pass ``bpm`` = session tempo for reliable groove metrics (``bpm``
    omitted/0 falls back to tempo estimation; ``seconds`` omitted/0
    analyzes the full files).

    Returns:
    - ``verdict`` — human-readable summary of significant changes
    - ``dimension_deltas`` — per-dimension before/after/delta (canonical
      dimensions computed by the evaluation stack's own extractor)
    - ``significant_changes`` — feature changes above measurement-noise
      thresholds, ranked by magnitude
    - ``before_snapshot`` / ``after_snapshot`` — pass these directly to
      ``evaluate_move(goal_vector=..., before_snapshot=..., after_snapshot=...)``
      for a numeric keep/undo verdict against a goal
    - ``before_extended`` / ``after_extended`` — full offline measurements
      per side (groove, stereo, loudness, transients, motion, polish)

    Both captures should cover the same musical material at the same
    session position (loop the section, capture, move, capture). Note:
    reusing fixed names like "before"/"after" across rounds intentionally
    overwrites the previous round's captures — use distinct names if you
    need to keep earlier rounds. See
    livepilot-core references/perception.md
    #listen_capture--listen_ab--offline-perception-loop for the full
    offline-vs-real-time model.

    ``embed=True`` adds a ``perceptual_distance`` block: one learned
    cosine distance for "do these sound like different things", which the
    per-feature deltas above cannot express on their own. Calibration from
    the 2026-07-31 benchmark — <0.05 is indistinguishable from re-rendering
    the same take, 0.05-0.1 is a real but modest change, >0.1 is clearly a
    different version. Needs the optional ``torch``+``transformers`` extra;
    reports ``available: false`` with an install hint otherwise.
    """
    before, before_audio, before_sr = _analyze_ex(before_file, bpm, seconds)
    after, after_audio, after_sr = _analyze_ex(after_file, bpm, seconds)
    result = engine.compare(before, after)
    result["verdict"] = engine.format_verdict(result)
    result["before_extended"] = before.extended
    result["after_extended"] = after.extended
    result["before_dimensions"] = before.dimensions
    result["after_dimensions"] = after.dimensions
    if embed:
        result["perceptual_distance"] = _perceptual_distance(
            before_audio, before_sr, after_audio, after_sr)
    return result


def _perceptual_distance(a_audio, a_sr, b_audio, b_sr) -> dict:
    """Learned holistic distance between two captures. Never raises."""
    from . import embedding  # noqa: PLC0415 — optional, import at call time

    if not embedding.is_available():
        return {
            "available": False,
            "reason": (
                "Optional embedding backend not installed. "
                "pip install torch transformers  (~2 GB; weights download from "
                "HuggingFace on first use and are not redistributed by LivePilot)"
            ),
            "detail": embedding.last_error(),
        }
    va = embedding.embed_audio(a_audio, a_sr)
    vb = embedding.embed_audio(b_audio, b_sr)
    dist = embedding.distance(va, vb)
    if dist is None:
        return {"available": False, "reason": "embedding backend returned nothing",
                "detail": embedding.last_error()}
    # Calibration from spikes/embedding-benchmark (2026-07-31): within-take
    # spread averaged ~0.045, between-iteration ~0.136 on clap-htsat-fused.
    if dist < 0.05:
        reading = "indistinguishable from re-rendering the same take"
    elif dist < 0.10:
        reading = "a real but modest perceptual change"
    else:
        reading = "clearly a different version"
    return {
        "available": True,
        "model": embedding.DEFAULT_MODEL,
        "distance": round(dist, 5),
        "similarity": round(1.0 - dist, 5),
        "reading": reading,
    }
