"""Compilers for sound-design-domain semantic moves.

These prefer native Ableton devices. Volume/send adjustments are used
as safe fallbacks when device chain details aren't in the kernel.
"""

from __future__ import annotations

from .compiler import CompiledPlan, CompiledStep, register_compiler
from .models import SemanticMove
from . import resolvers


def _compile_add_warmth(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'add_warmth': volume boost + reverb send for perceived warmth.

    SAFETY: Never blindly set device parameters — device_index=0, parameter_index=0
    can kill audio if the first device isn't a Saturator. Only adjust device params
    when find_device_on_track confirms a Saturator is present.
    """
    steps = []
    descriptions = []
    warnings = []

    # Target melodic or bass tracks for warmth
    targets = resolvers.find_tracks_by_role(kernel, ["bass", "chords", "pad"])
    if not targets:
        targets = resolvers.find_tracks_by_role(kernel, ["lead"])

    for t in targets[:2]:
        idx = t["index"]
        name = t["name"]

        # Try to find a Saturator on the track (safe device adjustment)
        saturator = resolvers.find_device_on_track(kernel, idx, "Saturator")
        if saturator:
            steps.append(CompiledStep(
                tool="set_device_parameter",
                params={
                    "track_index": idx,
                    "device_index": saturator["device_index"],
                    "parameter_index": 0,
                    "value": 0.3,
                },
                description=f"Gentle Saturator drive on {name}",
            ))
            descriptions.append(f"Saturate {name}")
        else:
            # No Saturator found — use volume + send instead of risky device params
            warnings.append(f"No Saturator on {name} — using volume+reverb for warmth")

        # Boost volume slightly for perceived warmth
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": idx, "volume": 0.65},
            description=f"Boost {name} slightly for warmth",
        ))

        # Add reverb send for depth/warmth perception
        steps.append(CompiledStep(
            tool="set_track_send",
            params={"track_index": idx, "send_index": 0, "value": 0.25},
            description=f"Add reverb warmth to {name}",
        ))
        descriptions.append(f"Warm {name}")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify warmth — tracks producing audio, no distortion",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        before_reads=[{"tool": "get_master_spectrum", "params": {}}],
        after_reads=[{"tool": "get_master_spectrum", "params": {}}],
        risk_level="low",
        summary="; ".join(descriptions) if descriptions else "No tracks for warmth",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=warnings,
    )


def _compile_add_texture(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'add_texture': perlin filter motion + delay send."""
    steps = []
    descriptions = []

    targets = resolvers.find_tracks_by_role(kernel, ["pad", "chords", "lead"])

    for t in targets[:1]:
        idx = t["index"]
        name = t["name"]
        steps.append(CompiledStep(
            tool="apply_automation_shape",
            params={
                "track_index": idx,
                "clip_index": 0,
                "parameter_type": "device",
                "device_index": 0,
                "parameter_index": 0,
                "curve_type": "perlin",
                "center": 0.4,
                "amplitude": 0.2,
                "duration": 8,
                "density": 16,
            },
            description=f"Perlin filter motion on {name} for organic texture",
        ))
        descriptions.append(f"Perlin filter on {name}")

        # Add delay send
        steps.append(CompiledStep(
            tool="set_track_send",
            params={"track_index": idx, "send_index": 1, "value": 0.20},
            description=f"Add delay send on {name} for spatial texture",
        ))
        descriptions.append(f"Delay texture on {name}")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify texture — track active with variation",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="medium",
        summary="; ".join(descriptions) if descriptions else "No tracks for texture",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
    )


def _compile_shape_transients(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'shape_transients': push drum volume for punch, adjust sends.

    SAFETY: Never blindly set device parameters. Only adjust Compressor params
    when find_device_on_track confirms one exists. Otherwise use volume for punch.
    """
    steps = []
    descriptions = []
    warnings = []

    drums = resolvers.find_tracks_by_role(kernel, ["drums", "percussion"])
    if not drums:
        return CompiledPlan(
            move_id=move.move_id,
            intent=move.intent,
            summary="No drum/percussion tracks found",
            warnings=["No rhythm tracks for transient shaping"],
        )

    for dt in drums[:1]:
        idx = dt["index"]
        name = dt["name"]

        # Try to find a Compressor on the track
        compressor = resolvers.find_device_on_track(kernel, idx, "Compressor")
        if compressor:
            steps.append(CompiledStep(
                tool="set_device_parameter",
                params={
                    "track_index": idx,
                    "device_index": compressor["device_index"],
                    "parameter_index": 0,
                    "value": 0.2,
                },
                description=f"Faster Compressor attack on {name} for snap",
            ))
            descriptions.append(f"Shape {name} compressor")
        else:
            warnings.append(f"No Compressor on {name} — using volume push for punch")

        # Push volume for transient punch regardless
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": idx, "volume": 0.75},
            description=f"Push {name} to 0.75 for transient punch",
        ))
        descriptions.append(f"Push {name} for punch")

        # Reduce reverb send to tighten transients
        steps.append(CompiledStep(
            tool="set_track_send",
            params={"track_index": idx, "send_index": 0, "value": 0.10},
            description=f"Tighten reverb on {name} for cleaner transients",
        ))

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify transient character after shaping",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="low",
        summary="; ".join(descriptions),
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=warnings,
    )


def _compile_add_space(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'add_space': reverb + delay + pan widening."""
    steps = []
    descriptions = []

    targets = resolvers.find_tracks_by_role(kernel, ["chords", "lead", "pad"])

    for t in targets[:2]:
        idx = t["index"]
        name = t["name"]
        steps.append(CompiledStep(
            tool="set_track_send",
            params={"track_index": idx, "send_index": 0, "value": 0.30},
            description=f"Add reverb depth to {name}",
        ))
        descriptions.append(f"Reverb on {name}")

    # Widen one element
    for t in targets[:1]:
        steps.append(CompiledStep(
            tool="set_track_pan",
            params={"track_index": t["index"], "pan": -0.20},
            description=f"Pan {t['name']} slightly left for spatial width",
        ))
    for t in targets[1:2]:
        steps.append(CompiledStep(
            tool="set_track_pan",
            params={"track_index": t["index"], "pan": 0.20},
            description=f"Pan {t['name']} slightly right for spatial width",
        ))

    descriptions.append("Widen spatial field")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify spatial depth — stereo present, no phase issues",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        before_reads=[{"tool": "analyze_mix", "params": {}}],
        after_reads=[{"tool": "analyze_mix", "params": {}}],
        risk_level="low",
        summary="; ".join(descriptions) if descriptions else "No tracks for space",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
    )


# ── Register ────────────────────────────────────────────────────────────────

register_compiler("add_warmth", _compile_add_warmth)
register_compiler("add_texture", _compile_add_texture)
register_compiler("shape_transients", _compile_shape_transients)
register_compiler("add_space", _compile_add_space)
