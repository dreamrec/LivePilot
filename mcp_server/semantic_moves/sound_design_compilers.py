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

    SAFETY: Never target device parameters by raw index. Ableton's parameter
    index 0 is "Device On" on every device, so set_device_parameter(idx=0)
    with any fractional value rounds to 0 and DISABLES the device. Use sends
    and volume for warmth; device-param automation is only safe once the
    resolver can look parameters up by name.
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
    """Compile 'add_texture': delay send for spatial texture.

    Device-parameter automation (perlin filter motion) was removed because it
    targeted device_index=0, parameter_index=0 without a resolver check — that
    hits "Device On" on every Ableton device and would silently disable the
    first device. Re-enable once resolvers.find_device_parameter lands.
    """
    steps = []
    descriptions = []
    warnings = []

    targets = resolvers.find_tracks_by_role(kernel, ["pad", "chords", "lead"])

    for t in targets[:1]:
        idx = t["index"]
        name = t["name"]

        # Add delay send
        steps.append(CompiledStep(
            tool="set_track_send",
            params={"track_index": idx, "send_index": 1, "value": 0.20},
            description=f"Add delay send on {name} for spatial texture",
        ))
        descriptions.append(f"Delay texture on {name}")

    if not targets:
        warnings.append("No pad/chords/lead tracks — texture needs a melodic bed")

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
        warnings=warnings,
    )


def _compile_shape_transients(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'shape_transients': push drum volume for punch, adjust sends.

    SAFETY: Never target device parameters by raw index. Index 0 on every
    Ableton device is "Device On" — writing 0.2 rounds to 0 and disables the
    device. Punch is achieved via volume + send shaping; Compressor attack
    automation is only safe once the resolver can look parameters up by name.
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

        # Push volume for transient punch
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
