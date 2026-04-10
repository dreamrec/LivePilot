"""Compilers for transition-domain semantic moves."""

from __future__ import annotations

from .compiler import CompiledPlan, CompiledStep, register_compiler
from .models import SemanticMove
from . import resolvers


def _compile_increase_forward_motion(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'increase_forward_motion': rising filter + rhythm push."""
    steps = []
    descriptions = []

    melodic = resolvers.find_tracks_by_role(kernel, ["chords", "lead", "pad"])
    drums = resolvers.find_tracks_by_role(kernel, ["drums", "percussion"])

    for mt in melodic[:1]:
        steps.append(CompiledStep(
            tool="apply_automation_shape",
            params={
                "track_index": mt["index"],
                "clip_index": 0,
                "parameter_type": "device",
                "device_index": 0,
                "parameter_index": 0,
                "curve_type": "exponential",
                "start": 0.2,
                "end": 0.7,
                "duration": 4,
            },
            description=f"Rising filter sweep on {mt['name']} over 4 bars",
        ))
        descriptions.append(f"Rising filter on {mt['name']}")

    for dt in drums[:1]:
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": dt["index"], "volume": 0.75},
            description=f"Push {dt['name']} to 0.75 for forward drive",
        ))
        descriptions.append(f"Push {dt['name']} forward")

    for mt in melodic[:1]:
        steps.append(CompiledStep(
            tool="set_track_send",
            params={"track_index": mt["index"], "send_index": 0, "value": 0.30},
            description=f"Build reverb wash on {mt['name']}",
        ))
        descriptions.append(f"Reverb wash on {mt['name']}")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify forward momentum — energy increasing",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="low",
        summary="; ".join(descriptions) if descriptions else "No melodic tracks for motion",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
    )


def _compile_open_chorus(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'open_chorus': maximize width, energy, brightness."""
    steps = []
    descriptions = []

    melodic = resolvers.find_tracks_by_role(kernel, ["chords", "lead", "pad"])
    drums = resolvers.find_tracks_by_role(kernel, ["drums"])

    # Push all melodic tracks
    for mt in melodic:
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": mt["index"], "volume": 0.75},
            description=f"Push {mt['name']} to 0.75 for chorus energy",
        ))
        descriptions.append(f"Push {mt['name']}")

    # Widen chords
    for ct in resolvers.find_tracks_by_role(kernel, ["chords"])[:1]:
        steps.append(CompiledStep(
            tool="set_track_pan",
            params={"track_index": ct["index"], "pan": -0.30},
            description=f"Pan {ct['name']} left for width",
        ))

    for lt in resolvers.find_tracks_by_role(kernel, ["lead"])[:1]:
        steps.append(CompiledStep(
            tool="set_track_pan",
            params={"track_index": lt["index"], "pan": 0.25},
            description=f"Pan {lt['name']} right for width",
        ))

    # Increase sends for spaciousness
    for mt in melodic[:2]:
        steps.append(CompiledStep(
            tool="set_track_send",
            params={"track_index": mt["index"], "send_index": 0, "value": 0.30},
            description=f"Add reverb space to {mt['name']}",
        ))

    descriptions.append("Widen stereo + add space")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify chorus energy — all tracks at high level",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="medium",
        summary="; ".join(descriptions) if descriptions else "No tracks for chorus",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
    )


def _compile_create_breakdown(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'create_breakdown': strip to minimal elements."""
    steps = []
    descriptions = []

    drums = resolvers.find_tracks_by_role(kernel, ["drums", "percussion"])
    bass = resolvers.find_tracks_by_role(kernel, ["bass"])
    pads = resolvers.find_tracks_by_role(kernel, ["pad"])

    for dt in drums:
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": dt["index"], "volume": 0.25},
            description=f"Strip {dt['name']} to 0.25 for breakdown",
        ))
        descriptions.append(f"Strip {dt['name']}")

    for bt in bass[:1]:
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": bt["index"], "volume": 0.30},
            description=f"Reduce {bt['name']} to 0.30",
        ))
        descriptions.append(f"Reduce {bt['name']}")

    # Increase reverb on remaining pads for depth
    for pt in pads[:1]:
        steps.append(CompiledStep(
            tool="set_track_send",
            params={"track_index": pt["index"], "send_index": 0, "value": 0.50},
            description=f"Deep reverb on {pt['name']} for breakdown atmosphere",
        ))
        descriptions.append(f"Deep reverb on {pt['name']}")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify breakdown — energy low, atmosphere present",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="medium",
        summary="; ".join(descriptions) if descriptions else "No tracks for breakdown",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
    )


def _compile_bridge_sections(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'bridge_sections': gentle filter motion + volume crossfade."""
    steps = []
    descriptions = []

    melodic = resolvers.find_tracks_by_role(kernel, ["chords", "lead", "pad"])

    for mt in melodic[:1]:
        steps.append(CompiledStep(
            tool="apply_automation_shape",
            params={
                "track_index": mt["index"],
                "clip_index": 0,
                "parameter_type": "send",
                "send_index": 0,
                "curve_type": "cosine",
                "center": 0.25,
                "amplitude": 0.15,
                "duration": 4,
                "density": 8,
            },
            description=f"Gentle reverb motion on {mt['name']} across bridge",
        ))
        descriptions.append(f"Bridge motion on {mt['name']}")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify smooth bridge — no dropouts",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="low",
        summary="; ".join(descriptions) if descriptions else "No tracks for bridge",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
    )


# ── Register ────────────────────────────────────────────────────────────────

register_compiler("increase_forward_motion", _compile_increase_forward_motion)
register_compiler("open_chorus", _compile_open_chorus)
register_compiler("create_breakdown", _compile_create_breakdown)
register_compiler("bridge_sections", _compile_bridge_sections)
