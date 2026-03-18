"""
LivePilot - Session diagnostics handler (1 command).

Analyzes the current session and flags potential issues:
armed tracks, mute/solo leftovers, empty clips, unnamed tracks,
empty scenes, and device-less instrument tracks.
"""

from .router import register


# Default track names that indicate the user hasn't renamed them.
# Ableton auto-names tracks like "1-MIDI", "2-Audio", "3-MIDI", etc.
_DEFAULT_NAME_PATTERNS = frozenset([
    "MIDI", "Audio", "Inst", "Return",
])


def _looks_default_name(name):
    """Check if a track name looks like an Ableton default."""
    stripped = name.strip()
    # Pattern: "N-Type" or just "Type" (e.g., "1-MIDI", "MIDI", "2-Audio")
    for part in stripped.split("-"):
        part = part.strip()
        if part.isdigit():
            continue
        if part in _DEFAULT_NAME_PATTERNS:
            return True
    return False


@register("get_session_diagnostics")
def get_session_diagnostics(song, params):
    """Analyze the session and return a diagnostic report."""
    issues = []
    stats = {
        "track_count": 0,
        "return_track_count": 0,
        "scene_count": 0,
        "total_clips": 0,
        "empty_scenes": 0,
    }

    tracks = list(song.tracks)
    scenes = list(song.scenes)
    return_tracks = list(song.return_tracks)

    stats["track_count"] = len(tracks)
    stats["return_track_count"] = len(return_tracks)
    stats["scene_count"] = len(scenes)

    # ── Track-level checks ─────────────────────────────────────────────

    armed_tracks = []
    soloed_tracks = []
    muted_tracks = []
    unnamed_tracks = []
    empty_tracks = []  # no clips at all
    no_device_midi_tracks = []  # MIDI tracks with no instruments
    track_slots = []  # cached clip_slots per track (avoid re-evaluating LOM tuple)

    for i, track in enumerate(tracks):
        # Armed check
        if track.arm:
            armed_tracks.append({"index": i, "name": track.name})

        # Solo check
        if track.solo:
            soloed_tracks.append({"index": i, "name": track.name})

        # Muted tracks (informational, only flag if many)
        if track.mute:
            muted_tracks.append({"index": i, "name": track.name})

        # Unnamed / default name check
        if _looks_default_name(track.name):
            unnamed_tracks.append({"index": i, "name": track.name})

        # Cache clip_slots once per track
        slots = list(track.clip_slots)
        track_slots.append(slots)

        # Clip count
        clip_count = 0
        for slot in slots:
            if slot.has_clip:
                clip_count += 1
        stats["total_clips"] += clip_count

        if clip_count == 0:
            empty_tracks.append({"index": i, "name": track.name})

        # MIDI track with no devices (no instrument loaded)
        if track.has_midi_input and len(list(track.devices)) == 0:
            no_device_midi_tracks.append({"index": i, "name": track.name})

    # Build issues from checks
    if armed_tracks:
        issues.append({
            "type": "armed_tracks",
            "severity": "warning",
            "message": "%d track(s) left armed" % len(armed_tracks),
            "details": armed_tracks,
        })

    if soloed_tracks:
        issues.append({
            "type": "soloed_tracks",
            "severity": "warning",
            "message": "%d track(s) soloed — other tracks are silenced" % len(soloed_tracks),
            "details": soloed_tracks,
        })

    if len(muted_tracks) > len(tracks) * 0.5 and len(muted_tracks) > 2:
        issues.append({
            "type": "many_muted",
            "severity": "info",
            "message": "%d of %d tracks muted — consider cleaning up unused tracks" % (
                len(muted_tracks), len(tracks)
            ),
            "details": muted_tracks,
        })

    if unnamed_tracks:
        issues.append({
            "type": "unnamed_tracks",
            "severity": "info",
            "message": "%d track(s) have default names" % len(unnamed_tracks),
            "details": unnamed_tracks,
        })

    if empty_tracks:
        issues.append({
            "type": "empty_tracks",
            "severity": "info",
            "message": "%d track(s) have no clips" % len(empty_tracks),
            "details": empty_tracks,
        })

    if no_device_midi_tracks:
        issues.append({
            "type": "no_instrument",
            "severity": "warning",
            "message": "%d MIDI track(s) have no instrument loaded" % len(no_device_midi_tracks),
            "details": no_device_midi_tracks,
        })

    # ── Scene-level checks ──────────────────────────────────────────────

    empty_scenes = []
    for i, scene in enumerate(scenes):
        has_any_clip = False
        for slots in track_slots:
            if i < len(slots) and slots[i].has_clip:
                has_any_clip = True
                break
        if not has_any_clip:
            empty_scenes.append({"index": i, "name": scene.name})

    stats["empty_scenes"] = len(empty_scenes)

    if empty_scenes and len(empty_scenes) > 1:
        issues.append({
            "type": "empty_scenes",
            "severity": "info",
            "message": "%d scene(s) have no clips across any track" % len(empty_scenes),
            "details": empty_scenes[:10],  # Cap at 10 to avoid huge payloads
        })

    # ── Return track checks ─────────────────────────────────────────────

    soloed_returns = []
    for i, track in enumerate(return_tracks):
        if track.solo:
            soloed_returns.append({"index": i, "name": track.name})

    if soloed_returns:
        issues.append({
            "type": "soloed_returns",
            "severity": "warning",
            "message": "%d return track(s) soloed" % len(soloed_returns),
            "details": soloed_returns,
        })

    # ── Summary ─────────────────────────────────────────────────────────

    severity_counts = {"warning": 0, "info": 0}
    for issue in issues:
        severity_counts[issue["severity"]] = severity_counts.get(issue["severity"], 0) + 1

    return {
        "healthy": len(issues) == 0,
        "issue_count": len(issues),
        "warnings": severity_counts.get("warning", 0),
        "info": severity_counts.get("info", 0),
        "issues": issues,
        "stats": stats,
    }
