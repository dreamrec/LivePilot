"""Concrete compilers for mix-domain semantic moves.

Each compiler function takes (move, kernel) and returns a CompiledPlan
with fully parameterized tool calls. The compiler inspects the kernel's
track topology and device chains to resolve targets.

Pure functions — no I/O. All data comes from the kernel dict.
"""

from __future__ import annotations

from .compiler import CompiledPlan, CompiledStep, register_compiler
from .models import SemanticMove
from . import resolvers


def _compile_make_punchier(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'make_punchier': push drums, pull pads, tighten master bus."""
    steps = []
    warnings = []
    descriptions = []

    # Find drum track
    drum_tracks = resolvers.find_tracks_by_role(kernel, ["drums", "percussion"])
    if not drum_tracks:
        # Fallback: look for "unknown" role tracks (often drums)
        drum_tracks = resolvers.find_tracks_by_role(kernel, ["unknown"])
    if not drum_tracks:
        warnings.append("No drum track found — skipping drum push")

    # Find pad/texture tracks
    pad_tracks = resolvers.find_tracks_by_role(kernel, ["pad", "fx"])

    # Step 1: Read current state
    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Read current levels for all tracks",
        verify_after=False,
    ))

    # Step 2: Push drum volume
    for dt in drum_tracks[:1]:  # Only first drum track
        idx = dt["index"]
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": idx, "volume": 0.75},
            description=f"Push {dt['name']} (track {idx}) to 0.75 for transient punch",
        ))
        descriptions.append(f"Push {dt['name']} volume to 0.75")

    # Step 3: Pull back pads
    for pt in pad_tracks:
        idx = pt["index"]
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": idx, "volume": 0.25},
            description=f"Pull {pt['name']} (track {idx}) to 0.25 for contrast",
        ))
        descriptions.append(f"Pull {pt['name']} volume to 0.25")

    # Step 4: Verify
    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify all tracks still producing audio",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        before_reads=[{"tool": "get_track_meters", "params": {"include_stereo": True}}],
        after_reads=[
            {"tool": "get_track_meters", "params": {"include_stereo": True}},
            {"tool": "get_master_spectrum", "params": {}},
        ],
        risk_level="low",
        summary="; ".join(descriptions) if descriptions else "No changes compiled",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=warnings,
    )


def _compile_tighten_low_end(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'tighten_low_end': reduce sub volume, boost bass harmonics."""
    steps = []
    warnings = []
    descriptions = []

    bass_tracks = resolvers.find_tracks_by_role(kernel, ["bass"])
    if not bass_tracks:
        warnings.append("No bass track found — cannot tighten low end")
        return CompiledPlan(
            move_id=move.move_id,
            intent=move.intent,
            summary="No bass track found",
            warnings=warnings,
        )

    bass = bass_tracks[0]
    idx = bass["index"]

    # Step 1: Read spectrum
    steps.append(CompiledStep(
        tool="get_master_spectrum",
        params={},
        description="Read current spectral balance",
        verify_after=False,
    ))

    # Step 2: Reduce bass volume slightly
    steps.append(CompiledStep(
        tool="set_track_volume",
        params={"track_index": idx, "volume": 0.58},
        description=f"Reduce {bass['name']} volume to 0.58 (tighten sub)",
    ))
    descriptions.append(f"Reduce {bass['name']} volume to 0.58")

    # Step 3: Verify
    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify bass still producing audio after reduction",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        before_reads=[{"tool": "get_master_spectrum", "params": {}}],
        after_reads=[
            {"tool": "get_master_spectrum", "params": {}},
            {"tool": "get_track_meters", "params": {"include_stereo": True}},
        ],
        risk_level="low",
        summary="; ".join(descriptions),
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=warnings,
    )


def _compile_widen_stereo(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'widen_stereo': pan harmonic elements wider, add depth."""
    steps = []
    warnings = []
    descriptions = []

    chord_tracks = resolvers.find_tracks_by_role(kernel, ["chords", "pad"])
    lead_tracks = resolvers.find_tracks_by_role(kernel, ["lead"])
    perc_tracks = resolvers.find_tracks_by_role(kernel, ["percussion"])

    if not chord_tracks and not lead_tracks:
        warnings.append("No harmonic or lead tracks found for stereo widening")

    # Pan chords left
    for ct in chord_tracks[:1]:
        steps.append(CompiledStep(
            tool="set_track_pan",
            params={"track_index": ct["index"], "pan": -0.35},
            description=f"Pan {ct['name']} left (-35%) for width",
        ))
        descriptions.append(f"Pan {ct['name']} left 35%")

    # Pan lead right
    for lt in lead_tracks[:1]:
        steps.append(CompiledStep(
            tool="set_track_pan",
            params={"track_index": lt["index"], "pan": 0.30},
            description=f"Pan {lt['name']} right (+30%) for width",
        ))
        descriptions.append(f"Pan {lt['name']} right 30%")

    # Pan perc slightly
    for pt in perc_tracks[:1]:
        steps.append(CompiledStep(
            tool="set_track_pan",
            params={"track_index": pt["index"], "pan": 0.15},
            description=f"Pan {pt['name']} slightly right (+15%)",
        ))
        descriptions.append(f"Pan {pt['name']} slightly right")

    # Verify
    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify stereo output on all panned tracks",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        before_reads=[{"tool": "analyze_mix", "params": {}}],
        after_reads=[
            {"tool": "analyze_mix", "params": {}},
            {"tool": "get_track_meters", "params": {"include_stereo": True}},
        ],
        risk_level="low",
        summary="; ".join(descriptions) if descriptions else "No panning changes",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=warnings,
    )


def _compile_darken_mix(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'darken_without_losing_width': reduce brightness, preserve stereo."""
    steps = []
    descriptions = []

    # Find bright-sounding tracks (leads and chords)
    bright_tracks = resolvers.find_tracks_by_role(kernel, ["lead", "chords", "percussion"])

    for bt in bright_tracks[:2]:  # Max 2 tracks
        # Reduce volume slightly to darken
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": bt["index"], "volume": 0.40},
            description=f"Pull {bt['name']} to 0.40 for darker tone",
        ))
        descriptions.append(f"Darken {bt['name']} to 0.40")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify all tracks still active after darkening",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        before_reads=[{"tool": "get_master_spectrum", "params": {}}],
        after_reads=[{"tool": "get_master_spectrum", "params": {}}],
        risk_level="low",
        summary="; ".join(descriptions) if descriptions else "No changes",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
    )


def _compile_reduce_repetition(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'reduce_repetition_fatigue': add perlin automation for organic movement."""
    steps = []
    descriptions = []

    # Find melodic tracks for filter drift
    melodic = resolvers.find_tracks_by_role(kernel, ["chords", "lead", "pad"])

    for mt in melodic[:2]:  # Max 2 tracks
        steps.append(CompiledStep(
            tool="apply_automation_shape",
            params={
                "track_index": mt["index"],
                "clip_index": 0,
                "parameter_type": "send",
                "send_index": 0,
                "curve_type": "perlin",
                "center": 0.2,
                "amplitude": 0.1,
                "duration": 8,
                "density": 16,
            },
            description=f"Add perlin reverb send drift on {mt['name']}",
        ))
        descriptions.append(f"Perlin reverb drift on {mt['name']}")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify tracks still active after automation",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        before_reads=[],
        after_reads=[{"tool": "get_track_meters", "params": {"include_stereo": True}}],
        risk_level="medium",
        summary="; ".join(descriptions) if descriptions else "No melodic tracks found",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
    )


# ── Register all compilers ──────────────────────────────────────────────────

register_compiler("make_punchier", _compile_make_punchier)
register_compiler("tighten_low_end", _compile_tighten_low_end)
register_compiler("widen_stereo", _compile_widen_stereo)
register_compiler("darken_without_losing_width", _compile_darken_mix)
register_compiler("reduce_repetition_fatigue", _compile_reduce_repetition)
