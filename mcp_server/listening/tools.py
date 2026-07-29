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
        if os.path.exists(expanded):
            return expanded
        raise ValueError(f"Audio file not found: {expanded}")

    candidates = [os.path.join(CAPTURE_DIR, file)]
    if not file.lower().endswith(_AUDIO_EXTS):
        candidates += [os.path.join(CAPTURE_DIR, file + ext)
                       for ext in _AUDIO_EXTS]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise ValueError(
        f"Capture '{file}' not found in {CAPTURE_DIR} "
        f"(tried extensions {_AUDIO_EXTS}). Record one with capture_audio."
    )


def _analyze(file: str, bpm: Optional[float],
             seconds: Optional[float]) -> engine.ClipFeatures:
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
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    if seconds:
        audio = audio[: int(sr * float(seconds))]
    if len(audio) == 0:
        raise ValueError(f"Audio file is empty: {path}")
    return engine.extract_features(audio, sr, bpm=float(bpm) if bpm else None)


@mcp.tool()
def listen_capture(
    file: str,
    bpm: Optional[float] = None,
    seconds: Optional[float] = None,
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

    ``seconds`` caps analysis to the first N seconds of the file.
    """
    report = _analyze(file, bpm, seconds)
    return asdict(report)


@mcp.tool()
def listen_ab(
    before_file: str,
    after_file: str,
    bpm: Optional[float] = None,
    seconds: Optional[float] = None,
) -> dict[str, Any]:
    """Compare two captures of the same musical span — what actually
    changed in the sound after a creative move.

    This is the perception loop's reflex arc: capture before a move,
    capture after, and this tool reports the empirical perceptual delta.
    Pass ``bpm`` = session tempo for reliable groove metrics.

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
    session position (loop the section, capture, move, capture).
    """
    before = _analyze(before_file, bpm, seconds)
    after = _analyze(after_file, bpm, seconds)
    result = engine.compare(before, after)
    result["verdict"] = engine.format_verdict(result)
    result["before_extended"] = before.extended
    result["after_extended"] = after.extended
    result["before_dimensions"] = before.dimensions
    result["after_dimensions"] = after.dimensions
    return result
