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


def _is_warped_loop(file_path: str) -> bool:
    """Return True if the filename contains a BPM marker (likely a tempo-locked loop)."""
    stem = os.path.splitext(os.path.basename(file_path))[0]
    return bool(_BPM_IN_FILENAME_RE.search(stem))


def _filename_stem(file_path: str) -> str:
    return os.path.splitext(os.path.basename(file_path))[0]


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
    }
