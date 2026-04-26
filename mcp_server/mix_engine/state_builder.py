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

# BUG-2026-04-26#5: track-name substrings that explicitly mark a track
# as SUPPORT, even when its role-name maps to an anchor role. Without
# this filter, a track named "VOX-GHOST" infers role=vocal and gets
# auto-classified as an anchor, which then triggers `anchor_too_weak`
# from the balance critic for any volume below the session average —
# a guaranteed false positive on every ghost / wisp / texture layer.
#
# Substring-based (case-insensitive). Add new hints conservatively —
# any new entry de-promotes a previously-anchor track silently.
_NON_ANCHOR_NAME_HINTS = (
    "ghost",   # VOX-GHOST, ghost-snare
    "wisp",    # vocal-wisp
    "fx",      # fx-bus, fx-rain
    "atmos",   # ATMOS, atmosphere
    "atmosphere",
    "rain",    # rain-bed
    "texture",
    "drone",   # drone-bed
    "shimmer",
    "wash",    # reverb-wash, vocal-wash
    "ambient", # ambient-pad
    "sublayer",
    "sub-layer",
    "sub_layer",
    "ghosting",
    "back",    # back-vox, back-pad (background layers)
)


def _name_signals_non_anchor(track_name: str) -> bool:
    """Return True when the track name marks this layer as SUPPORT.

    Used in build_balance_state to exclude false anchors from the
    balance critic's `anchor_too_weak` signal. See BUG-2026-04-26#5.
    """
    if not track_name:
        return False
    name_lower = track_name.lower()
    return any(hint in name_lower for hint in _NON_ANCHOR_NAME_HINTS)


# Frequency bands where masking is most problematic.
_MASKING_BANDS = ("sub", "low", "low_mid", "mid", "high_mid", "presence", "high")


# ── Balance ─────────────────────────────────────────────────────────


def build_balance_state(
    track_infos: list[dict],
    role_hints: Optional[dict[int, str]] = None,
) -> BalanceState:
    """Build BalanceState from track info dicts.

    Args:
        track_infos: list of dicts from get_track_info (Remote Script format).
                     Volume/panning are nested under "mixer", sends under "sends".
        role_hints: optional {track_index: role_name} overrides.
    """
    from ..tools._agent_os_engine import infer_track_role

    role_hints = role_hints or {}
    states: list[TrackMixState] = []
    anchor_indices: list[int] = []
    loudest_idx = -1
    quietest_idx = -1
    loudest_vol = -math.inf
    quietest_vol = math.inf

    for info in track_infos:
        idx = info.get("index", 0)
        name = info.get("name", "")
        # Infer role from track name if no explicit hint
        role = role_hints.get(idx, infer_track_role(name))
        # Extract mixer values from nested Remote Script response
        mixer = info.get("mixer", {})
        vol = mixer.get("volume", 0.0) if mixer else info.get("volume", 0.0)
        pan = mixer.get("panning", 0.0) if mixer else info.get("pan", 0.0)
        # Extract send levels from sends array
        sends_raw = info.get("sends", [])
        send_levels = [s.get("value", 0.0) for s in sends_raw] if sends_raw else []

        ts = TrackMixState(
            track_index=idx,
            name=name,
            role=role,
            volume=vol,
            pan=pan,
            mute=info.get("mute", False),
            solo=info.get("solo", False),
            send_levels=send_levels,
        )
        states.append(ts)

        # BUG-2026-04-26#5: don't flag explicit support layers as anchors
        # even when their role inference returns an anchor-class role.
        if role in _ANCHOR_ROLES and not _name_signals_non_anchor(name):
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
        return DynamicsState(crest_factor_db=0.0, over_compressed=False, headroom=None)

    # If values look like they're in dB (negative), convert to linear
    if rms < 0:
        rms_linear = 10 ** (rms / 20.0)
        peak_linear = 10 ** ((peak or 0) / 20.0)
    else:
        rms_linear = rms
        peak_linear = peak if peak else rms

    if rms_linear <= 0:
        return DynamicsState(crest_factor_db=0.0, over_compressed=False, headroom=None)

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
