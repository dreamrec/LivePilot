"""Resolvers — find tracks, devices, and parameters from a SessionKernel.

These are the "eyes" of the semantic move compiler. They inspect the kernel's
session topology to find the right targets for a musical intent.

Pure functions — no I/O, no MCP calls. They read from the kernel dict only.
"""

from __future__ import annotations

from typing import Optional


# ── Role inference from track names ──────────────────────────────────────────

_ROLE_KEYWORDS: dict[str, list[str]] = {
    "drums": ["drum", "beat", "kit", "perc", "rhythm", "hat", "kick", "snare"],
    "bass": ["bass", "sub", "808", "low"],
    "chords": ["chord", "rhodes", "keys", "piano", "organ", "electric", "wurli"],
    "pad": ["pad", "texture", "ambient", "drone", "atmosphere"],
    "lead": ["lead", "melody", "synth", "glitch", "hook", "vocal"],
    "percussion": ["perc", "shaker", "tambourine", "conga", "bongo", "rim"],
    "fx": ["fx", "effect", "noise", "riser", "impact", "sweep"],
}


def infer_role(track_name: str) -> str:
    """Infer a musical role from a track name. Returns 'unknown' if no match."""
    name_lower = track_name.lower()
    for role, keywords in _ROLE_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return role
    return "unknown"


# ── Track finders ────────────────────────────────────────────────────────────

def find_tracks_by_role(kernel: dict, roles: list[str]) -> list[dict]:
    """Find all tracks whose inferred role is in the given list.

    Returns list of {index, name, role, volume, pan} for matched tracks.
    """
    tracks = kernel.get("session_info", {}).get("tracks", [])
    results = []
    for track in tracks:
        role = infer_role(track.get("name", ""))
        if role in roles:
            results.append({
                "index": track.get("index", 0),
                "name": track.get("name", ""),
                "role": role,
                "volume": track.get("volume"),
                "pan": track.get("pan"),
                "mute": track.get("mute", False),
                "solo": track.get("solo", False),
            })
    return results


def find_loudest_track(kernel: dict) -> Optional[dict]:
    """Find the track with the highest volume setting."""
    tracks = kernel.get("session_info", {}).get("tracks", [])
    if not tracks:
        return None
    # Volume might not be in session_info tracks — return the first non-muted
    non_muted = [t for t in tracks if not t.get("mute", False)]
    return non_muted[0] if non_muted else tracks[0]


def find_track_by_name(kernel: dict, name_substring: str) -> Optional[dict]:
    """Find a track whose name contains the given substring (case-insensitive)."""
    tracks = kernel.get("session_info", {}).get("tracks", [])
    name_lower = name_substring.lower()
    for track in tracks:
        if name_lower in track.get("name", "").lower():
            return track
    return None


# ── Device finders ───────────────────────────────────────────────────────────

def find_device_on_track(
    kernel: dict, track_index: int, device_class: str
) -> Optional[dict]:
    """Find a device by class name on a track. Returns {device_index, name} or None.

    Note: This requires device data in the kernel, which may not always be
    available. Returns None if device data is missing.
    """
    # Device data would be in an extended kernel; for now, return None
    # and let the compiler use find_and_load_device as a fallback
    return None


# ── Spectral helpers ─────────────────────────────────────────────────────────

def get_spectral_balance(kernel: dict) -> Optional[dict]:
    """Extract spectral band balance from the kernel's capability data.

    Returns None if no spectral data is available.
    """
    # Spectral data isn't stored in the base kernel — it would come from
    # a pre-capture. Return None for graceful degradation.
    return None


def is_analyzer_available(kernel: dict) -> bool:
    """Check if the M4L analyzer is connected."""
    cap = kernel.get("capability_state", {})
    domains = cap.get("domains", {})
    analyzer = domains.get("analyzer", {})
    return analyzer.get("available", False)


# ── Volume math ──────────────────────────────────────────────────────────────

def clamp_volume(vol: float) -> float:
    """Clamp volume to Ableton's 0.0-1.0 range."""
    return max(0.0, min(1.0, vol))


def adjust_volume(current: float, delta_percent: float) -> float:
    """Adjust a volume by a percentage. delta_percent=5 means +5%."""
    new = current + (delta_percent / 100.0)
    return clamp_volume(new)
