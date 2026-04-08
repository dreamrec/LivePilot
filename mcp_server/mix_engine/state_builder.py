"""State builder — construct MixState from session data.

Pure computation, zero I/O.  MCP tool wrappers fetch data from Ableton
and pass it here.
"""

from __future__ import annotations

import math
from typing import Optional

from .models import (
    BalanceState,
    DepthState,
    DynamicsState,
    MaskingEntry,
    MaskingMap,
    MixState,
    StereoState,
    TrackMixState,
)


# Roles considered "anchor" — should be prominent in the mix.
_ANCHOR_ROLES = frozenset({"kick", "bass", "vocal", "lead", "drums"})

# Frequency bands where masking is most problematic.
_MASKING_BANDS = ("sub", "low", "low_mid", "mid", "high_mid", "presence", "high")


# ── Balance ─────────────────────────────────────────────────────────


def build_balance_state(
    track_infos: list[dict],
    role_hints: Optional[dict[int, str]] = None,
) -> BalanceState:
    """Build BalanceState from track info dicts.

    Args:
        track_infos: list of dicts with at least "index", "name", "volume",
                     "pan", "mute", "solo", and optionally "send_levels".
        role_hints: optional {track_index: role_name} overrides.
    """
    role_hints = role_hints or {}
    states: list[TrackMixState] = []
    anchor_indices: list[int] = []
    loudest_idx = -1
    quietest_idx = -1
    loudest_vol = -math.inf
    quietest_vol = math.inf

    for info in track_infos:
        idx = info.get("index", 0)
        role = role_hints.get(idx, info.get("role", "unknown"))
        vol = info.get("volume", 0.0)

        ts = TrackMixState(
            track_index=idx,
            name=info.get("name", ""),
            role=role,
            volume=vol,
            pan=info.get("pan", 0.0),
            mute=info.get("mute", False),
            solo=info.get("solo", False),
            send_levels=info.get("send_levels", []),
        )
        states.append(ts)

        if role in _ANCHOR_ROLES:
            anchor_indices.append(idx)

        if not ts.mute:
            if vol > loudest_vol:
                loudest_vol = vol
                loudest_idx = idx
            if vol < quietest_vol:
                quietest_vol = vol
                quietest_idx = idx

    return BalanceState(
        track_states=states,
        anchor_tracks=anchor_indices,
        loudest_track=loudest_idx,
        quietest_track=quietest_idx,
    )


# ── Masking ─────────────────────────────────────────────────────────


def build_masking_map(
    spectrum: Optional[dict],
    track_roles: Optional[dict[int, str]] = None,
) -> MaskingMap:
    """Build MaskingMap from spectrum data.

    Uses per-track spectrum bands if available, otherwise returns empty.
    Spectrum shape: {"tracks": {track_idx_str: {band: value, ...}, ...}}
    or flat {"bands": {band: value}} for master-only.

    For Phase 1 we detect masking heuristically from role collisions
    in known problem bands (kick/bass in sub/low, bass/chords in low_mid).
    """
    entries: list[MaskingEntry] = []
    track_roles = track_roles or {}

    if not spectrum or not track_roles:
        return MaskingMap(entries=[], worst_pair=None)

    # Build role->indices mapping
    role_to_indices: dict[str, list[int]] = {}
    for idx, role in track_roles.items():
        role_to_indices.setdefault(role, []).append(idx)

    # Known problematic role pairs and their collision bands
    collision_rules: list[tuple[str, str, str, float]] = [
        ("kick", "bass", "sub", 0.7),
        ("kick", "bass", "low", 0.6),
        ("bass", "chords", "low_mid", 0.5),
        ("bass", "keys", "low_mid", 0.5),
        ("vocal", "lead", "presence", 0.4),
        ("vocal", "lead", "high_mid", 0.4),
        ("lead", "synth", "mid", 0.3),
        ("chords", "pad", "mid", 0.3),
    ]

    for role_a, role_b, band, base_severity in collision_rules:
        indices_a = role_to_indices.get(role_a, [])
        indices_b = role_to_indices.get(role_b, [])
        for ia in indices_a:
            for ib in indices_b:
                if ia != ib:
                    entries.append(MaskingEntry(
                        track_a=ia,
                        track_b=ib,
                        overlap_band=band,
                        severity=base_severity,
                    ))

    worst = None
    if entries:
        worst_entry = max(entries, key=lambda e: e.severity)
        worst = (worst_entry.track_a, worst_entry.track_b)

    return MaskingMap(entries=entries, worst_pair=worst)


# ── Dynamics ────────────────────────────────────────────────────────


def build_dynamics_state(
    rms: Optional[float],
    peak: Optional[float],
) -> DynamicsState:
    """Build DynamicsState from RMS and peak values.

    Args:
        rms: master RMS level in linear (0-1) or dB.
        peak: master peak level in linear (0-1) or dB.
    """
    if rms is None or peak is None or rms <= 0:
        return DynamicsState(crest_factor_db=0.0, over_compressed=False, headroom=0.0)

    # If values look like they're in dB (negative), convert to linear
    if rms < 0:
        rms_linear = 10 ** (rms / 20.0)
        peak_linear = 10 ** ((peak or 0) / 20.0)
    else:
        rms_linear = rms
        peak_linear = peak if peak else rms

    if rms_linear <= 0:
        return DynamicsState(crest_factor_db=0.0, over_compressed=False, headroom=0.0)

    crest = 20 * math.log10(max(peak_linear, 1e-10) / max(rms_linear, 1e-10))

    # Over-compressed when crest factor < 6 dB (flat dynamics)
    over_compressed = crest < 6.0

    # Headroom = distance from peak to 0 dBFS
    if peak_linear > 0:
        headroom = -20 * math.log10(max(peak_linear, 1e-10))
    else:
        headroom = 100.0  # effectively infinite headroom

    return DynamicsState(
        crest_factor_db=round(crest, 2),
        over_compressed=over_compressed,
        headroom=round(headroom, 2),
    )


# ── Composite builder ──────────────────────────────────────────────


def build_mix_state(
    session_info: Optional[dict] = None,
    track_infos: Optional[list[dict]] = None,
    spectrum: Optional[dict] = None,
    rms_data: Optional[float] = None,
    role_hints: Optional[dict[int, str]] = None,
) -> MixState:
    """Build a full MixState from session data.

    Args:
        session_info: session-level info (tempo, etc.) — reserved for future.
        track_infos: per-track info dicts.
        spectrum: spectrum data (master or per-track).
        rms_data: master RMS value.
        role_hints: {track_index: role_str} overrides.
    """
    track_infos = track_infos or []
    role_hints = role_hints or {}

    balance = build_balance_state(track_infos, role_hints)
    masking = build_masking_map(spectrum, role_hints)

    # Extract peak from spectrum if available
    peak = None
    if spectrum:
        peak = spectrum.get("peak")

    dynamics = build_dynamics_state(rms_data, peak)

    # Stereo and depth require per-track analysis not yet available.
    # Build from track send levels as a proxy.
    stereo = _build_stereo_from_tracks(balance.track_states)
    depth = _build_depth_from_tracks(balance.track_states)

    return MixState(
        balance=balance,
        masking=masking,
        dynamics=dynamics,
        stereo=stereo,
        depth=depth,
    )


# ── Internal helpers ────────────────────────────────────────────────


def _build_stereo_from_tracks(tracks: list[TrackMixState]) -> StereoState:
    """Estimate stereo field from pan positions."""
    if not tracks:
        return StereoState(center_strength=1.0, side_activity=0.0, mono_risk=False)

    center_count = 0
    total_side = 0.0
    active = [t for t in tracks if not t.mute]

    if not active:
        return StereoState(center_strength=1.0, side_activity=0.0, mono_risk=False)

    for t in active:
        if abs(t.pan) < 0.1:
            center_count += 1
        total_side += abs(t.pan)

    center_strength = center_count / len(active)
    side_activity = total_side / len(active)

    # Mono risk: everything is centered
    mono_risk = center_strength > 0.85 and side_activity < 0.05

    return StereoState(
        center_strength=round(center_strength, 3),
        side_activity=round(side_activity, 3),
        mono_risk=mono_risk,
    )


def _build_depth_from_tracks(tracks: list[TrackMixState]) -> DepthState:
    """Estimate depth from send levels (reverb/delay sends)."""
    if not tracks:
        return DepthState(wet_dry_ratio=0.0, depth_separation=0.0, wash_risk=False)

    active = [t for t in tracks if not t.mute]
    if not active:
        return DepthState(wet_dry_ratio=0.0, depth_separation=0.0, wash_risk=False)

    total_send = 0.0
    send_values: list[float] = []

    for t in active:
        avg_send = sum(t.send_levels) / max(len(t.send_levels), 1) if t.send_levels else 0.0
        total_send += avg_send
        send_values.append(avg_send)

    avg_wet = total_send / len(active)

    # Depth separation: variance in send levels
    if len(send_values) > 1:
        mean = sum(send_values) / len(send_values)
        variance = sum((v - mean) ** 2 for v in send_values) / len(send_values)
        depth_sep = math.sqrt(variance)
    else:
        depth_sep = 0.0

    wash_risk = avg_wet > 0.6

    return DepthState(
        wet_dry_ratio=round(avg_wet, 3),
        depth_separation=round(depth_sep, 3),
        wash_risk=wash_risk,
    )
