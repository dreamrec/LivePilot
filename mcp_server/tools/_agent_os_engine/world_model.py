"""Part of the _agent_os_engine package — extracted from the single-file engine.

Pure-computation core. Callers should import from the package facade
(`from mcp_server.tools._agent_os_engine import X`), which re-exports from
these sub-modules.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .models import QUALITY_DIMENSIONS, MEASURABLE_PROXIES, VALID_MODES, VALID_RESEARCH_MODES, _ROLE_PATTERNS, GoalVector, WorldModel

def validate_goal_vector(
    request_text: str,
    targets: dict[str, float],
    protect: dict[str, float],
    mode: str,
    aggression: float,
    research_mode: str,
) -> GoalVector:
    """Validate and construct a GoalVector. Raises ValueError on invalid input."""
    if not request_text or not request_text.strip():
        raise ValueError("request_text cannot be empty")

    # Validate dimensions
    for dim in targets:
        if dim not in QUALITY_DIMENSIONS:
            raise ValueError(
                f"Unknown target dimension '{dim}'. "
                f"Valid: {sorted(QUALITY_DIMENSIONS)}"
            )
    for dim in protect:
        if dim not in QUALITY_DIMENSIONS:
            raise ValueError(
                f"Unknown protect dimension '{dim}'. "
                f"Valid: {sorted(QUALITY_DIMENSIONS)}"
            )

    # Validate weights are non-negative
    for dim, w in targets.items():
        if w < 0.0:
            raise ValueError(f"Target weight for '{dim}' must be >= 0.0, got {w}")
    for dim, w in protect.items():
        if not 0.0 <= w <= 1.0:
            raise ValueError(f"Protect threshold for '{dim}' must be 0.0-1.0, got {w}")

    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {sorted(VALID_MODES)}, got '{mode}'")
    if research_mode not in VALID_RESEARCH_MODES:
        raise ValueError(
            f"research_mode must be one of {sorted(VALID_RESEARCH_MODES)}, "
            f"got '{research_mode}'"
        )
    if not 0.0 <= aggression <= 1.0:
        raise ValueError(f"aggression must be 0.0-1.0, got {aggression}")

    # Normalize target weights to sum to ~1.0 if they don't already
    total = sum(targets.values())
    if targets and total > 0:
        if abs(total - 1.0) > 0.01:
            targets = {k: v / total for k, v in targets.items()}

    return GoalVector(
        request_text=request_text.strip(),
        targets=targets,
        protect=protect,
        mode=mode,
        aggression=aggression,
        research_mode=research_mode,
    )

def infer_track_role(track_name: str) -> str:
    """Infer a track's musical role from its name. Returns 'unknown' if no match."""
    name_lower = track_name.lower().strip()
    for pattern, role in _ROLE_PATTERNS:
        if re.search(pattern, name_lower):
            return role
    return "unknown"

def build_world_model_from_data(
    session_info: dict,
    spectrum: Optional[dict] = None,
    rms: Optional[dict] = None,
    detected_key: Optional[dict] = None,
    flucoma_status: Optional[dict] = None,
    track_infos: Optional[list[dict]] = None,
) -> WorldModel:
    """Assemble a WorldModel from raw tool outputs.

    All parameters are optional — the model degrades gracefully when
    analyzer data is unavailable.
    """
    # Topology
    tracks = session_info.get("tracks", [])
    topology = {
        "tempo": session_info.get("tempo"),
        "time_signature": f"{session_info.get('signature_numerator', 4)}/{session_info.get('signature_denominator', 4)}",
        "track_count": session_info.get("track_count", 0),
        "return_count": session_info.get("return_track_count", 0),
        "scene_count": session_info.get("scene_count", 0),
        "is_playing": session_info.get("is_playing", False),
        "tracks": [
            {
                "index": t.get("index"),
                "name": t.get("name", ""),
                "has_midi": t.get("has_midi_input", False),
                "has_audio": t.get("has_audio_input", False),
                "mute": t.get("mute", False),
                "solo": t.get("solo", False),
                "arm": t.get("arm", False),
            }
            for t in tracks
        ],
    }

    # Track roles
    track_roles = {}
    for t in tracks:
        idx = t.get("index", 0)
        name = t.get("name", "")
        track_roles[idx] = infer_track_role(name)

    # Sonic state (None if analyzer unavailable)
    sonic = None
    if spectrum and spectrum.get("bands"):
        sonic = {
            "spectrum": spectrum.get("bands", {}),
            "rms": rms.get("rms") if rms else None,
            "peak": rms.get("peak") if rms else None,
            "key": detected_key.get("key") if detected_key else None,
            "scale": detected_key.get("scale") if detected_key else None,
            "key_confidence": detected_key.get("confidence") if detected_key else None,
        }

    # Technical state
    analyzer_available = spectrum is not None and bool(spectrum.get("bands"))
    flucoma_available = (
        flucoma_status is not None
        and flucoma_status.get("flucoma_available", False)
    )

    # Check plugin health from track_infos if provided
    unhealthy_devices = []
    if track_infos:
        for ti in track_infos:
            for dev in ti.get("devices", []):
                flags = dev.get("health_flags", [])
                if "opaque_or_failed_plugin" in flags:
                    unhealthy_devices.append({
                        "track": ti.get("index"),
                        "device": dev.get("name"),
                        "flag": "opaque_or_failed_plugin",
                    })

    technical = {
        "analyzer_available": analyzer_available,
        "flucoma_available": flucoma_available,
        "unhealthy_devices": unhealthy_devices,
    }

    return WorldModel(
        topology=topology,
        sonic=sonic,
        technical=technical,
        track_roles=track_roles,
    )

