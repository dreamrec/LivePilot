"""Per-track signal fetchers — shared between audit_layer + grader heavy mode.

Centralises the network-side fetch helpers that both `audit/tools.py` and
`grader/tools.py` need: per-clip notes, per-clip automation flag, and
wavetable mod-matrix routing count. Keeping them in one place avoids
the duplication that crept in during Phase 2c-β.

These functions take a raw `ableton` connection (NOT an MCP `Context`)
so they're decoupled from the MCP framework and easy to test.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def safe_call(ableton, command: str, params: dict | None = None) -> dict | None:
    """Send a command to the Remote Script, swallow errors, return None on failure."""
    try:
        return ableton.send_command(command, params or {})
    except Exception as exc:
        logger.debug("audit/state safe_call: %s failed: %s", command, exc)
        return None


def fetch_notes_for_clips(ableton, track_index: int, clip_slots: list[dict]) -> list[list[dict]]:
    """Pull notes for every populated clip slot. Skips empty/audio clips."""
    out: list[list[dict]] = []
    for slot in clip_slots or []:
        if not slot.get("has_clip"):
            continue
        clip_index = slot.get("index")
        if clip_index is None:
            continue
        result = safe_call(ableton, "get_notes", {
            "track_index": track_index,
            "clip_index": clip_index,
            "from_pitch": 0,
            "pitch_span": 128,
            "from_time": 0.0,
        })
        if result and "notes" in result:
            out.append(result["notes"])
    return out


def has_clip_automation(ableton, track_index: int, clip_slots: list[dict]) -> bool:
    """Check if any clip on this track has automation envelopes."""
    for slot in clip_slots or []:
        if not slot.get("has_clip"):
            continue
        clip_index = slot.get("index")
        if clip_index is None:
            continue
        result = safe_call(ableton, "get_clip_automation", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        if not result:
            continue
        envelopes = result.get("envelopes") or result.get("automation") or []
        if envelopes:
            return True
    return False


def count_wavetable_routings(ableton, track_index: int, devices: list[dict]) -> int:
    """Sum non-zero mod-matrix routings across any Wavetable on the track."""
    total = 0
    for i, dev in enumerate(devices or []):
        if dev.get("class_name") != "Wavetable":
            continue
        mod = safe_call(ableton, "get_wavetable_mod_matrix", {
            "track_index": track_index,
            "device_index": i,
        })
        if not mod:
            continue
        entries = mod.get("matrix") or mod.get("entries") or []
        for e in entries:
            try:
                if abs(float(e.get("amount", 0.0))) > 0.001:
                    total += 1
            except (TypeError, ValueError):
                continue
    return total
