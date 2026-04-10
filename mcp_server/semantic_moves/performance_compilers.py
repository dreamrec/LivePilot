"""Compilers for performance-safe semantic moves.

Critical rule: NEVER compile to blocked actions (delete, create, device load).
Only volume, pan, send, and automation are allowed.
"""

from __future__ import annotations

from .compiler import CompiledPlan, CompiledStep, register_compiler
from .models import SemanticMove
from . import resolvers


def _compile_recover_energy(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'recover_energy': bring drums+bass back gradually."""
    steps = []
    descriptions = []

    drum_tracks = resolvers.find_tracks_by_role(kernel, ["drums", "percussion"])
    bass_tracks = resolvers.find_tracks_by_role(kernel, ["bass"])

    for dt in drum_tracks[:1]:
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": dt["index"], "volume": 0.70},
            description=f"Restore {dt['name']} to 0.70 for energy recovery",
        ))
        descriptions.append(f"Restore {dt['name']} to 0.70")

    for bt in bass_tracks[:1]:
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": bt["index"], "volume": 0.60},
            description=f"Restore {bt['name']} to 0.60",
        ))
        descriptions.append(f"Restore {bt['name']} to 0.60")

    # Pull reverb back to tighten
    pad_tracks = resolvers.find_tracks_by_role(kernel, ["pad", "chords"])
    for pt in pad_tracks[:1]:
        steps.append(CompiledStep(
            tool="set_track_send",
            params={"track_index": pt["index"], "send_index": 0, "value": 0.15},
            description=f"Tighten reverb on {pt['name']} to 0.15",
        ))
        descriptions.append(f"Tighten reverb on {pt['name']}")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify energy recovered",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="low",
        summary="; ".join(descriptions) if descriptions else "No rhythm tracks found",
        requires_approval=False,  # Performance moves execute immediately
    )


def _compile_decompress_tension(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'decompress_tension': pull back energy, open space."""
    steps = []
    descriptions = []

    lead_tracks = resolvers.find_tracks_by_role(kernel, ["lead", "chords"])
    pad_tracks = resolvers.find_tracks_by_role(kernel, ["pad"])

    for lt in lead_tracks[:2]:
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": lt["index"], "volume": 0.35},
            description=f"Pull {lt['name']} to 0.35 for decompression",
        ))
        descriptions.append(f"Pull {lt['name']} to 0.35")

    for pt in pad_tracks[:1]:
        steps.append(CompiledStep(
            tool="set_track_send",
            params={"track_index": pt["index"], "send_index": 0, "value": 0.40},
            description=f"Open reverb on {pt['name']} to 0.40 for spaciousness",
        ))
        descriptions.append(f"Open reverb on {pt['name']}")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify decompression — energy lower, space wider",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="low",
        summary="; ".join(descriptions) if descriptions else "No tracks to decompress",
        requires_approval=False,
    )


def _compile_safe_spotlight(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'safe_spotlight': pull non-spotlight tracks, push one."""
    steps = []
    descriptions = []
    warnings = []

    all_tracks = kernel.get("session_info", {}).get("tracks", [])
    if not all_tracks:
        warnings.append("No tracks found")
        return CompiledPlan(
            move_id=move.move_id, intent=move.intent, warnings=warnings,
            summary="No tracks to spotlight",
        )

    # Spotlight the first lead or melodic track; pull everything else
    lead_tracks = resolvers.find_tracks_by_role(kernel, ["lead", "chords"])
    spotlight = lead_tracks[0] if lead_tracks else all_tracks[0]
    spotlight_idx = spotlight.get("index", 0)
    spotlight_name = spotlight.get("name", f"Track {spotlight_idx}")

    # Pull non-spotlight audio tracks
    for track in all_tracks:
        idx = track.get("index", 0)
        name = track.get("name", "")
        if idx == spotlight_idx:
            continue
        if track.get("type") in ("return", "master"):
            continue
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": idx, "volume": 0.30},
            description=f"Pull {name} to 0.30 (background)",
        ))

    # Push spotlight
    steps.append(CompiledStep(
        tool="set_track_volume",
        params={"track_index": spotlight_idx, "volume": 0.82},
        description=f"Push spotlight {spotlight_name} to 0.82",
    ))
    descriptions.append(f"Spotlight {spotlight_name}")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify spotlight dominant, others still audible",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="low",
        summary="; ".join(descriptions),
        requires_approval=False,
    )


def _compile_emergency_simplify(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'emergency_simplify': strip to drums+bass only."""
    steps = []
    descriptions = []

    all_tracks = kernel.get("session_info", {}).get("tracks", [])
    drum_tracks = resolvers.find_tracks_by_role(kernel, ["drums", "percussion"])
    bass_tracks = resolvers.find_tracks_by_role(kernel, ["bass"])
    keep_indices = {t["index"] for t in drum_tracks + bass_tracks}

    for track in all_tracks:
        idx = track.get("index", 0)
        name = track.get("name", "")
        if track.get("type") in ("return", "master"):
            continue
        if idx in keep_indices:
            continue
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": idx, "volume": 0.10},
            description=f"Strip {name} to 0.10 (emergency simplify)",
        ))

    descriptions.append("Strip to drums+bass only")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify drums+bass dominant, others at background level",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="low",
        summary="; ".join(descriptions),
        requires_approval=False,
    )


# ── Register ────────────────────────────────────────────────────────────────

register_compiler("recover_energy", _compile_recover_energy)
register_compiler("decompress_tension", _compile_decompress_tension)
register_compiler("safe_spotlight", _compile_safe_spotlight)
register_compiler("emergency_simplify", _compile_emergency_simplify)
