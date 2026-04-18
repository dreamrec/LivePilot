"""
LivePilot - Session diagnostics handler (3 commands).

Analyzes the current session and flags potential issues:
armed tracks, mute/solo leftovers, empty clips, unnamed tracks,
empty scenes, and device-less instrument tracks.

Also enumerates active ControlSurface instances (Push, APC, Launchkey,
etc.) so the agent can reason about user-facing hardware.
"""

from .router import register


# Default track names that indicate the user hasn't renamed them.
# Ableton auto-names tracks like "1-MIDI", "2-Audio", "3-MIDI", etc.
_DEFAULT_NAME_PATTERNS = frozenset([
    "MIDI", "Audio", "Inst", "Return",
])
_PLUGIN_CLASS_NAMES = frozenset(["PluginDevice", "AuPluginDevice"])
_SAMPLE_DEPENDENT_DEVICE_NAMES = frozenset([
    "idensity",
    "tardigrain",
    "koala sampler",
    "burns audio granular",
    "audiolayer",
    "segments",
    "segments (instr)",
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


def _sample_dependent_device(name):
    lowered = name.strip().lower()
    for candidate in _SAMPLE_DEPENDENT_DEVICE_NAMES:
        if candidate in lowered:
            return True
    return False


def _safe_attr(obj, name, default=None):
    """Read a Live attribute defensively — some track types omit properties."""
    try:
        return getattr(obj, name)
    except Exception:
        return default


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
    opaque_or_failed_plugins = []
    sample_dependent_devices = []
    track_slots = []  # cached clip_slots per track (avoid re-evaluating LOM tuple)

    for i, track in enumerate(tracks):
        # Armed check
        if _safe_attr(track, "arm", False):
            armed_tracks.append({"index": i, "name": track.name})

        # Solo check
        if _safe_attr(track, "solo", False):
            soloed_tracks.append({"index": i, "name": track.name})

        # Muted tracks (informational, only flag if many)
        if _safe_attr(track, "mute", False):
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
        if _safe_attr(track, "has_midi_input", False) and len(list(track.devices)) == 0:
            no_device_midi_tracks.append({"index": i, "name": track.name})

        for j, device in enumerate(track.devices):
            class_name = getattr(device, "class_name", "")
            try:
                parameter_count = len(list(device.parameters))
            except Exception:
                parameter_count = None

            if class_name in _PLUGIN_CLASS_NAMES and parameter_count is not None and parameter_count <= 1:
                opaque_or_failed_plugins.append({
                    "track_index": i,
                    "track_name": track.name,
                    "device_index": j,
                    "device_name": device.name,
                    "parameter_count": parameter_count,
                })

            if _sample_dependent_device(device.name):
                sample_dependent_devices.append({
                    "track_index": i,
                    "track_name": track.name,
                    "device_index": j,
                    "device_name": device.name,
                })

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

    if opaque_or_failed_plugins:
        issues.append({
            "type": "opaque_or_failed_plugins",
            "severity": "warning",
            "message": (
                "%d plugin(s) expose <=1 host parameter. If silent after auditioning, "
                "they likely failed to initialize. If audio is flowing, they are opaque to MCP control."
                % len(opaque_or_failed_plugins)
            ),
            "details": opaque_or_failed_plugins,
        })

    if sample_dependent_devices:
        issues.append({
            "type": "sample_dependent_devices",
            "severity": "info",
            "message": (
                "%d likely sample-dependent device(s) loaded — they may stay silent until source audio is loaded "
                "inside the plugin UI."
                % len(sample_dependent_devices)
            ),
            "details": sample_dependent_devices,
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
        if _safe_attr(track, "solo", False):
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


# ── ControlSurface enumeration ──────────────────────────────────────────
# Read-only listing of active control surfaces (Push, APC, Launchkey,
# Launchpad, etc.). Import Live lazily inside each handler — the rest of
# this module operates on the `song` passed in and doesn't need the Live
# package at import time. Keeping the import local preserves that.


@register("list_control_surfaces")
def list_control_surfaces(song, params):
    """Enumerate all active Live.ControlSurface instances."""
    from Live import Application
    app = Application.get_application()
    surfaces = list(getattr(app, "control_surfaces", []) or [])
    out = []
    for i, cs in enumerate(surfaces):
        out.append({
            "index": i,
            "name": str(getattr(cs, "name", "") or cs.__class__.__name__),
            "class_name": cs.__class__.__name__,
        })
    return {"surfaces": out}


@register("get_control_surface_info")
def get_control_surface_info(song, params):
    """Return detailed info about a single control surface by index."""
    from Live import Application
    app = Application.get_application()
    surfaces = list(getattr(app, "control_surfaces", []) or [])
    idx = int(params["index"])
    if not 0 <= idx < len(surfaces):
        upper = len(surfaces) - 1 if surfaces else -1
        raise IndexError("index %d out of range (0..%d)" % (idx, upper))
    cs = surfaces[idx]
    component_count = 0
    if hasattr(cs, "components"):
        try:
            component_count = len(list(cs.components))
        except Exception:
            component_count = 0
    return {
        "index": idx,
        "name": str(getattr(cs, "name", "") or cs.__class__.__name__),
        "class_name": cs.__class__.__name__,
        "component_count": component_count,
    }
