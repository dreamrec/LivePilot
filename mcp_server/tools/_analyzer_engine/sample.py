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


_LOOP_PATH_HINTS = (
    "/loops/",
    "/drum_loops/",
    "/melodic_loops/",
    "/pad_loops/",
    "/bass_loops/",
    "/synth_loops/",
    "/perc_loops/",
    "/vocal_loops/",
    "/fx_loops/",
)
_ONESHOT_HINTS = (
    "oneshot",
    "one_shot",
    "one-shot",
    "_os_",
    "/oneshots/",
    "/one_shots/",
    "/one-shots/",
)
_LOOP_FILENAME_RE = re.compile(
    r"(?:_|\b)\d{2,3}(?:_|bpm|\b)|(?:_|\b)loop(?:_|\b)",
    re.IGNORECASE,
)


def _is_warped_loop(file_path: str) -> bool:
    """Return True if the file is likely a tempo-locked loop sample.

    2026-05-01 broadening (BUG-FULL-MODE-3): the original regex only matched
    "125bpm" / "125 bpm" literal patterns, which fails for the most common
    Splice naming where BPM is embedded as bare digits (e.g.
    `lfh_drums_125_hubble_hatclp.wav`). The broadened detection also looks
    at the path components (`/drum_loops/`, `/melodic_loops/`, etc.) and
    excludes explicit one-shots.

    Why it matters: the hygiene step that ran on a "false" verdict left
    Simplers without `S Loop On=1`, so the loop never actually loops — it
    plays once and stops. Combined with `Ve Mode=None` (also fixed below),
    every Splice loop loaded into Simpler was silent.
    """
    full_lower = file_path.lower()
    # One-shots are explicitly NOT warped loops, even when path also has loop hints
    if any(hint in full_lower for hint in _ONESHOT_HINTS):
        return False

    stem = os.path.splitext(os.path.basename(file_path))[0]
    if _BPM_IN_FILENAME_RE.search(stem):
        return True
    if _LOOP_FILENAME_RE.search(stem):
        return True
    # Append trailing slash so `/loops/` and `/drum_loops/` match the
    # last directory component cleanly (os.path.dirname strips trailing /).
    parent = os.path.dirname(file_path).lower() + "/"
    if any(seg in parent for seg in _LOOP_PATH_HINTS):
        return True
    return False


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
    warp_loops: bool = True,
) -> dict:
    """Apply post-load hygiene to a newly loaded Simpler and verify success.

    `warp_loops` (BUG-FULL-MODE-12, 2026-05-01): when True (default),
    tempo-locked loops get `simpler_set_warp(warping=1, mode=Beats|...)`
    so they play in sync with project tempo. Set False for creative
    chop mode where un-warped loops produce intentional rhythmic
    mismatches (J Dilla territory). compose_full_apply translates its
    `warp_strategy` parameter ("always" / "smart" / "chop") into the
    right per-step boolean before calling this.

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

    # Step 2: post-load defaults
    #
    # Hygiene applied unconditionally (BUG-FULL-MODE-3, 2026-05-01):
    #
    #   `Snap=0`     — required so non-quantized sample playback works.
    #   `Volume=0`   — load_browser_item / replace_sample come up at
    #                  -12 dB (the documented Simpler default) which makes
    #                  the sample audible-on-track-meter but inaudible on
    #                  the master meter. 0 dB is the right gain-staged
    #                  default for any newly loaded sample.
    #                  Ref: feedback_simpler_default_volume.md.
    #
    # NOTE on Ve Mode (2026-05-01 reconsidered): an earlier draft of this
    # hygiene set `Ve Mode = 4` ("Trigger" / AD-R envelope) so the sample
    # would play "in full" regardless of note duration. That choice was
    # wrong: AD-R retriggers the AD envelope continuously while held,
    # producing audible tremolo on long sustained notes (every 600ms at
    # default Ve Decay). Live's default `Ve Mode = 0` (None — standard
    # ADSR with sustain held until note-off) is the correct idiomatic
    # default, AS LONG AS the trigger note duration matches the clip
    # length. The companion fix is in `engine.py` where the planner now
    # emits `duration = SOURCE_BEATS` for sample-trigger notes.
    #
    # Empirical Ve Mode mapping (live-probed against Live 12.4):
    #     0 = None    (default; standard ADSR with sustain) ← keep this
    #     1 = Loop    (AD loops while held)
    #     2 = Beat    (envelope synced to beat divisions)
    #     3 = Sync    (envelope synced to host tempo)
    #     4 = Trigger (AD-R; cycles AD until note-off — caused tremolo bug)
    is_loop = _is_warped_loop(file_path)
    hygiene_params: list[dict] = [
        {"name_or_index": "Snap", "value": 0},
        {"name_or_index": "Volume", "value": 0.0},
    ]

    # Step 3: smart defaults for warped loops
    if is_loop:
        hygiene_params.extend([
            {"name_or_index": "S Start", "value": 0.0},
            {"name_or_index": "S Length", "value": 1.0},
            {"name_or_index": "S Loop On", "value": 1},
        ])

    # Step 4: auto-detect drum root note from filename (BUG-2026-04-22#18).
    # Only applied for one-shots — warped loops keep Live's default root
    # because their root note is irrelevant at loop playback speeds.
    drum_root = None
    if not is_loop:
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

    # Step 5: force Classic playback mode (BUG-FULL-MODE-3).
    # Live auto-slices drum loops into Slice mode on load, which means a
    # single C3 trigger note doesn't map to any slice → silence. Classic
    # mode is the correct default for sample playback; user can switch
    # to Slice/One-Shot explicitly if they want.
    playback_mode_set = False
    try:
        ableton.send_command("set_simpler_playback_mode", {
            "track_index": track_index,
            "device_index": device_index,
            "playback_mode": 0,  # 0 = Classic, 1 = One-Shot, 2 = Slice
        })
        playback_mode_set = True
    except Exception as exc:
        logger.debug("_simpler_post_load_hygiene: set_simpler_playback_mode failed: %s", exc)

    # Step 6: enable Simpler warp on tempo-locked loops (BUG-FULL-MODE-11,
    # 2026-05-01). Splice loops embed the source BPM in the filename
    # (e.g. `SO_SD_90_drum_loop_slippy.wav` = 90 BPM) but Simpler loads
    # them at NATIVE rate by default — a 90-BPM drum loop in a 122-BPM
    # project plays 35% slow.
    #
    # `simpler_set_warp` toggles `SimplerDevice.sample.warping` which
    # lives on the sample child object — only reachable via the M4L
    # bridge (Python LiveAPI can't step into the sample child). The
    # bridge call is positional, NOT a dict.
    #
    # warp_mode mapping (from Live's docs):
    #     0 = Beats        — drums / percussive (transient-preserving)
    #     1 = Tones        — mono harmonic material
    #     2 = Texture      — poly / ambient / vocals (smoothest)
    #     3 = Re-Pitch     — classic pitch-shift (NOT what we want here)
    #     4 = Complex      — full musical material (mid CPU)
    #     6 = Complex Pro  — highest quality (highest CPU)
    #
    # Choosing by file path hint mirrors the `_LOOP_PATH_HINTS` partition.
    # One-shots stay un-warped — warping a kick produces phasing.
    warp_set = False
    if is_loop and warp_loops:
        path_lower = file_path.lower()
        if any(seg in path_lower for seg in ("/drum_loops/", "drum_loop", "drumloop", "/breaks/", "/break_", "/perc_loops/")):
            warp_mode = 0  # Beats
        elif any(seg in path_lower for seg in ("/vocal_loops/", "vocal_loop", "/vox/", "vocal")):
            warp_mode = 2  # Texture — preserves vocal transients
        elif any(seg in path_lower for seg in ("/pad_loops/", "pad_loop", "/melodic_loops/", "melodic_loop", "/synth_loops/", "synth_loop", "/bass_loops/", "bass_loop")):
            warp_mode = 4  # Complex — best for harmonic material
        else:
            warp_mode = 0  # default to Beats — safest for unknown loops
        try:
            await bridge.send_command(
                "simpler_set_warp",
                int(track_index),
                int(device_index),
                1,                  # warping ON
                int(warp_mode),
                timeout=10.0,
            )
            warp_set = True
        except Exception as exc:
            logger.debug("_simpler_post_load_hygiene: simpler_set_warp failed: %s", exc)

    return {
        "verified": True,
        "device_name": actual_name,
        "track_index": track_index,
        "device_index": device_index,
        "warped_loop_defaults_applied": is_loop,
        "volume_set": True,
        "playback_mode_set": playback_mode_set,
        "warp_set": warp_set,
        "auto_root_note": drum_root,
    }
