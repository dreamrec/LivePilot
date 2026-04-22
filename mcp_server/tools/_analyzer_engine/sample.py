"""Simpler post-load hygiene + filename heuristics.

Extracted from ``analyzer.py`` as part of BUG-C1. Covers:

  * BPM-in-filename detection (used to tell warped loops from one-shots)
  * Post-load verification + Snap=0 + warped-loop defaults for Simpler

Context (docs/2026-04-14-bugs-discovered.md):

The M4L bridge's ``replace_simpler_sample`` command can report success
even when the sample is still the bootstrap placeholder. Simpler's
display name also doesn't refresh after a replace. After loading, the
``Snap`` parameter is ON by default which causes the Sample Start
position to snap to a location outside the new sample's valid audio —
resulting in silent playback. The hygiene here fixes both.
"""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)


_BPM_IN_FILENAME_RE = re.compile(r"(\d{2,3})\s*bpm", re.IGNORECASE)


# Drum material keywords → MIDI root pitch (Live Drum Rack convention).
# BUG-2026-04-22#18: loading a kick and triggering at note 36 previously
# played 24 semitones down because the Simpler root defaulted to C3 (60).
# Auto-detecting the intended trigger note from the filename fixes that
# without forcing the caller to know the magic number.
_DRUM_ROOT_MAP = {
    # Order matters — most specific first so "hi_hat" beats "hat".
    "kick": 36,        # C1
    "bd": 36,
    "808": 36,
    "snare": 38,       # D1
    "sd": 38,
    "clap": 39,        # D#1
    "rim": 37,         # C#1
    "tom_low": 41,     # F1
    "tom": 45,         # A1
    "closed_hat": 42,  # F#1
    "closed_hh": 42,
    "hihat_closed": 42,
    "hh_closed": 42,
    "hihat_open": 46,  # common naming pattern: prefix-then-modifier
    "hh_open": 46,
    "open_hat": 46,    # A#1
    "open_hh": 46,
    "hi_hat": 42,
    "hihat": 42,
    "hat_closed": 42,
    "hat": 42,         # default closed
    "hh": 42,
    "ride": 51,        # D#2
    "crash": 49,       # C#2
    "cymbal": 49,
    "perc": 60,        # C3 — neutral for generic percussion
    "shaker": 70,
    "tamb": 54,
    "cowbell": 56,
}


def _is_warped_loop(file_path: str) -> bool:
    """Return True if the filename contains a BPM marker (likely a tempo-locked loop)."""
    stem = os.path.splitext(os.path.basename(file_path))[0]
    return bool(_BPM_IN_FILENAME_RE.search(stem))


def _filename_stem(file_path: str) -> str:
    return os.path.splitext(os.path.basename(file_path))[0]


def _detect_drum_root_note(file_path: str) -> int | None:
    """Guess the intended MIDI trigger pitch for a sample by filename.

    Returns a MIDI note (0-127) when the filename contains a drum-material
    hint (kick, snare, hat, ride, etc.), else None.

    Why: Live's default Simpler root is C3 (60). A kick triggered from a
    Drum Rack pad at C1 (36) plays 24 semitones down — 4× slower, sounds
    like a broken airhorn. Setting the sample's root note to match the
    trigger pad (36 for a kick) fixes playback without any pitch-matching
    math. BUG-2026-04-22#18.
    """
    stem = _filename_stem(file_path).lower()
    # Normalize common separators so "Kick-Hard" and "kick_hard" both match.
    normalized = stem.replace("-", "_").replace(" ", "_")
    # Sort keys by length so "closed_hat" matches before "hat".
    for key in sorted(_DRUM_ROOT_MAP.keys(), key=len, reverse=True):
        if key in normalized:
            return _DRUM_ROOT_MAP[key]
    return None


async def _simpler_post_load_hygiene(
    bridge,
    ableton,
    track_index: int,
    device_index: int,
    file_path: str,
) -> dict:
    """Apply post-load hygiene to a newly loaded Simpler and verify success.

    Steps:
      1. Read track info to verify the device's actual name matches the
         expected sample stem. If it doesn't, return an error.
      2. Set Snap=0 (Off) — required so sample playback works.
      3. If filename indicates a warped loop, set S Start=0, S Length=1,
         S Loop On=1 so the loop plays fully instead of being cropped.
      4. Return a verified response dict.
    """
    expected_stem = _filename_stem(file_path)

    # Step 1: verify device name matches expected file
    try:
        track_info = ableton.send_command(
            "get_track_info", {"track_index": track_index}
        )
    except Exception as exc:
        return {"error": f"Verification read failed: {exc}"}

    devices = track_info.get("devices", []) or []
    if device_index < 0 or device_index >= len(devices):
        return {
            "error": (
                f"Device index {device_index} out of range after load "
                f"(track has {len(devices)} devices)"
            ),
            "verified": False,
        }
    device = devices[device_index]
    actual_name = str(device.get("name") or "")
    verified = expected_stem in actual_name or actual_name in expected_stem
    if not verified:
        return {
            "error": (
                f"Sample verification FAILED — Simpler name '{actual_name}' "
                f"does not match requested file '{expected_stem}'. The bridge "
                f"reported success but the actual sample is different. "
                f"Try `load_browser_item` with a user_library URI instead."
            ),
            "verified": False,
            "actual_device_name": actual_name,
            "expected_stem": expected_stem,
        }

    # Step 2: turn Snap OFF — required for reliable playback after replace
    hygiene_params: list[dict] = [
        {"name_or_index": "Snap", "value": 0},
    ]

    # Step 3: smart defaults for warped loops
    if _is_warped_loop(file_path):
        hygiene_params.extend([
            {"name_or_index": "S Start", "value": 0.0},
            {"name_or_index": "S Length", "value": 1.0},
            {"name_or_index": "S Loop On", "value": 1},
        ])

    # Step 4: auto-detect drum root note from filename (BUG-2026-04-22#18).
    # Only applied for one-shots — warped loops keep Live's default root
    # because their root note is irrelevant at loop playback speeds.
    drum_root = None
    if not _is_warped_loop(file_path):
        drum_root = _detect_drum_root_note(file_path)
        if drum_root is not None:
            hygiene_params.append(
                {"name_or_index": "Sample Pitch Coarse", "value": drum_root}
            )

    try:
        ableton.send_command("batch_set_parameters", {
            "track_index": track_index,
            "device_index": device_index,
            "parameters": hygiene_params,
        })
    except Exception as exc:
        logger.debug("_simpler_post_load_hygiene failed: %s", exc)
        # non-fatal — verification already succeeded
        pass

    return {
        "verified": True,
        "device_name": actual_name,
        "track_index": track_index,
        "device_index": device_index,
        "warped_loop_defaults_applied": _is_warped_loop(file_path),
        "auto_root_note": drum_root,
    }
