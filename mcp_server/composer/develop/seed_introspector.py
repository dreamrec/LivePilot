"""SeedIntrospector — read-only classifier for the existing loop in a live session.

Takes the project's current state (focused on a single scene, scene 0 by
default) and produces a SeedState dict describing what's there. Callers
(DevelopBrief builder, develop_apply) consume this to know what to extend.

Role classification:
- Name-match first: track.name lower-cased matches against role keyword sets
- Fallback to register heuristic when name is unrecognized

Sample-trigger vs MIDI-riff:
- A track is sample_trigger if ALL of: exactly 1 note, pitch == 60, duration >= clip_length
- Otherwise: midi_riff (multiple notes OR pitch != 60 OR duration < clip_length)
- Empty clip returns 'empty'
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Role-keyword maps. Order matters within each list — check more specific names first
_ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "drums": ("drum", "kick", "snare", "hat", "hi-hat", "hihat", "cymbal", "perc", "percussion", "clap", "ride", "tom"),
    "bass": ("bass", "sub", "808"),
    "lead": ("lead", "melody", "synth lead", "arp"),
    "pad": ("pad", "string", "chord", "harm"),
    "texture": ("texture", "atmos", "ambient", "noise", "drone"),
    "fx": ("fx", "riser", "impact", "swell", "sweep"),
    "vocal": ("vocal", "voice", "vox", "chop", "ad-lib", "adlib"),
}


def infer_role_from_name(name: str) -> str:
    """Match track name (case-insensitive) against role keywords.

    Returns one of: drums, bass, lead, pad, texture, fx, vocal, unknown.
    Caller may fall back to register heuristic when this returns 'unknown'.
    """
    if not name:
        return "unknown"
    lower = name.lower()
    for role, keywords in _ROLE_KEYWORDS.items():
        for kw in keywords:
            # Use prefix word-boundary to avoid false positives (e.g. "tom" in "MyCustomTrack")
            # but still match "drum" in "drums", "string" in "strings", "chop" in "chops"
            if re.search(r'\b' + re.escape(kw), lower):
                return role
    return "unknown"


def classify_track(notes: list[dict], clip_length: float) -> str:
    """Classify a track as sample_trigger / midi_riff / empty.

    Heuristic per v1.24 spec:
    - empty: no notes
    - sample_trigger: exactly 1 note, pitch == 60, duration >= clip_length
    - midi_riff: anything else
    """
    if not notes:
        return "empty"
    if len(notes) == 1:
        n = notes[0]
        if int(n.get("pitch", -1)) == 60 and float(n.get("duration", 0.0)) >= clip_length:
            return "sample_trigger"
    return "midi_riff"


def introspect_seed(ctx: Any, scene_index: int = 0) -> dict:
    """Build a SeedState dict from the live session.

    Reads tempo, time signature, song scale, and per-track clip content
    for the given scene. Returns dict shape:

    {
      "scene_index": int,
      "tempo": float,
      "clip_length": float,        # bars-in-beats; 4.0 = 1 bar at 4/4
      "time_signature": str,        # e.g. "4/4"
      "key": str | None,
      "scale_mode": str | None,
      "tracks": [
        {
          "index": int,
          "name": str,
          "role": str,              # from name-match
          "classification": str,    # sample_trigger | midi_riff | empty
          "notes": list[dict],
          "muted": bool,
        },
        ...
      ],
      "status": str | None,         # "no_seed_found" if scene has no clips
      "error": str | None,
    }

    On missing ableton context: returns {"error": "..."}.
    """
    ableton = ctx.lifespan_context.get("ableton") if hasattr(ctx, "lifespan_context") else None
    if ableton is None:
        return {"error": "ableton client not available in ctx"}

    try:
        session = ableton.send_command("get_session_info", {})
    except Exception as exc:
        return {"error": f"get_session_info failed: {exc}"}

    seed: dict = {
        "scene_index": scene_index,
        "tempo": float(session.get("tempo", 120.0)),
        "tracks": [],
    }
    sig_num = session.get("signature_numerator")
    sig_den = session.get("signature_denominator")
    if sig_num and sig_den:
        seed["time_signature"] = f"{sig_num}/{sig_den}"

    # Try to read song scale (Live 12.4)
    try:
        scale_result = ableton.send_command("get_song_scale", {})
        if scale_result and not scale_result.get("error"):
            seed["key"] = scale_result.get("root_note") or scale_result.get("key")
            seed["scale_mode"] = scale_result.get("scale_name") or scale_result.get("mode")
    except Exception as exc:
        logger.debug("introspect_seed: get_song_scale unavailable: %s", exc)

    track_descriptors = session.get("tracks", []) or []
    clip_length_seen: Optional[float] = None
    populated_track_count = 0

    for td in track_descriptors:
        ti = int(td.get("index", -1))
        name = td.get("name", "")
        muted = bool(td.get("mute", False))

        # Read the clip in this scene
        try:
            clip_info = ableton.send_command(
                "get_clip_info",
                {"track_index": ti, "clip_index": scene_index},
            )
        except Exception as exc:
            logger.debug("introspect_seed: get_clip_info(%d, %d) failed: %s", ti, scene_index, exc)
            continue

        if clip_info.get("error"):
            # No clip in this slot — skip but include the track stub for completeness
            seed["tracks"].append({
                "index": ti,
                "name": name,
                "role": infer_role_from_name(name),
                "classification": "empty",
                "notes": [],
                "muted": muted,
            })
            continue

        clip_length = float(clip_info.get("length", 0.0))
        if clip_length_seen is None and clip_length > 0:
            clip_length_seen = clip_length

        try:
            notes_result = ableton.send_command(
                "get_notes",
                {"track_index": ti, "clip_index": scene_index},
            )
            notes = notes_result.get("notes", []) if isinstance(notes_result, dict) else []
        except Exception as exc:
            logger.debug("introspect_seed: get_notes(%d, %d) failed: %s", ti, scene_index, exc)
            notes = []

        classification = classify_track(notes, clip_length) if clip_length > 0 else "empty"
        if classification != "empty":
            populated_track_count += 1

        seed["tracks"].append({
            "index": ti,
            "name": name,
            "role": infer_role_from_name(name),
            "classification": classification,
            "notes": notes,
            "muted": muted,
        })

    seed["clip_length"] = clip_length_seen if clip_length_seen is not None else 0.0

    if populated_track_count == 0:
        seed["status"] = "no_seed_found"
        seed["tracks"] = []  # Per spec: empty result tracks list

    return seed
