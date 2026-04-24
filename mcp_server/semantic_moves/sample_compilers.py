"""Compilers for sample-domain semantic moves.

These compile sample manipulation intents into concrete tool call sequences
using the session kernel to find appropriate tracks and devices.

v1.20.2 (BUG #2 fix): sample moves now resolve ``file_path`` from
``kernel["seed_args"]["file_path"]`` (v1.20 convention). Pre-fix, the
resolver returned a literal ``"{sample_file_path}"`` placeholder when
no path was in the kernel — which leaked into ``load_sample_to_simpler``
at execution and failed with a non-existent-file error. Now the
resolver returns ``None`` on miss and each compiler rejects with a
non-executable plan + clear warning.

Legacy fallback: wonder_mode/tools.py writes ``kernel["sample_file_path"]``
directly (pre-v1.20 path). Still honored for back-compat, just after
seed_args.
"""

from __future__ import annotations

from typing import Optional

from .compiler import CompiledPlan, CompiledStep, register_compiler
from .models import SemanticMove
from . import resolvers


def _resolve_sample_path(kernel: dict) -> Optional[str]:
    """Get the sample file path from kernel, or None if not set.

    Resolution order (v1.20.2 BUG #2 fix):
      1. kernel["seed_args"]["file_path"]  — v1.20 seed_args convention
      2. kernel["sample_file_path"]         — legacy wonder_mode setter

    Returns None when neither is present. Callers must check for None
    and reject the plan with an actionable warning; do NOT substitute a
    placeholder (which was the original bug).
    """
    seed = kernel.get("seed_args") or {}
    path = seed.get("file_path")
    if isinstance(path, str) and path.strip():
        return path
    legacy = kernel.get("sample_file_path")
    if isinstance(legacy, str) and legacy.strip():
        return legacy
    return None


def _empty_sample_plan(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Return a non-executable plan indicating a sample path is required.

    Used by every sample-family compiler when _resolve_sample_path returns
    None. Caller should still inspect the warnings for the actionable text.
    """
    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=[],
        risk_level="low",
        summary=(
            f"{move.move_id} requires a sample file_path. Pass via "
            f"apply_semantic_move(..., args={{\"file_path\": \"/abs/path/to.wav\"}})"
        ),
        requires_approval=True,
        warnings=[
            f"{move.move_id} requires seed_args.file_path (absolute path to the "
            "audio file). Not provided; plan not executable. Example: "
            "apply_semantic_move(\"" + move.move_id + "\", mode=\"explore\", "
            "args={\"file_path\": \"/path/to/sample.wav\"})"
        ],
    )


def _compile_sample_chop_rhythm(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'sample_chop_rhythm': load, slice, and chop a sample for rhythm."""
    file_path = _resolve_sample_path(kernel)
    if file_path is None:
        return _empty_sample_plan(move, kernel)

    steps = []
    descriptions = []
    warnings = []

    # Find drum/percussion tracks to layer alongside
    drums = resolvers.find_tracks_by_role(kernel, ["drums", "percussion"])

    # Create a new track for the chopped sample
    steps.append(CompiledStep(
        tool="create_midi_track",
        params={"name": "Chop"},
        description="Create track for chopped sample",
    ))
    descriptions.append("Create chop track")

    # Load into Simpler — track index will be last + 1
    tracks = kernel.get("session_info", {}).get("tracks", [])
    new_idx = len(tracks)

    steps.append(CompiledStep(
        tool="load_sample_to_simpler",
        params={"track_index": new_idx, "file_path": file_path},
        description="Load sample into Simpler for slicing",
    ))

    steps.append(CompiledStep(
        tool="set_simpler_playback_mode",
        params={"track_index": new_idx, "device_index": 0, "playback_mode": 2},
        description="Switch to slice mode for rhythmic chopping",
    ))
    descriptions.append("Slice sample")

    # Balance against existing drums
    if drums:
        steps.append(CompiledStep(
            tool="set_track_volume",
            params={"track_index": new_idx, "volume": 0.55},
            description="Set chop volume below main drums",
        ))
    else:
        warnings.append("No drum tracks found — chop will be the primary rhythm")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify chopped sample producing audio",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="medium",
        summary="; ".join(descriptions) if descriptions else "Chop sample for rhythm",
        requires_approval=True,
        warnings=warnings,
    )


def _compile_sample_texture_layer(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'sample_texture_layer': load and filter a sample as background texture."""
    file_path = _resolve_sample_path(kernel)
    if file_path is None:
        return _empty_sample_plan(move, kernel)

    steps = []
    descriptions = []

    tracks = kernel.get("session_info", {}).get("tracks", [])
    new_idx = len(tracks)

    steps.append(CompiledStep(
        tool="create_midi_track",
        params={"name": "Texture"},
        description="Create track for texture layer",
    ))

    steps.append(CompiledStep(
        tool="load_sample_to_simpler",
        params={"track_index": new_idx, "file_path": file_path},
        description="Load textural sample into Simpler",
    ))
    descriptions.append("Load texture sample")

    # Low volume for background placement
    steps.append(CompiledStep(
        tool="set_track_volume",
        params={"track_index": new_idx, "volume": 0.35},
        description="Set texture low in mix for background presence",
    ))
    descriptions.append("Set background level")

    # Add reverb send for spatial depth
    steps.append(CompiledStep(
        tool="set_track_send",
        params={"track_index": new_idx, "send_index": 0, "value": 0.40},
        description="Heavy reverb for spatial depth on texture",
    ))
    descriptions.append("Add reverb depth")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify texture layer producing audio at low level",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="low",
        summary="; ".join(descriptions),
        requires_approval=(kernel.get("mode", "improve") != "explore"),
    )


def _compile_sample_vocal_ghost(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'sample_vocal_ghost': reverse, pitch, and wash a vocal sample."""
    file_path = _resolve_sample_path(kernel)
    if file_path is None:
        return _empty_sample_plan(move, kernel)

    steps = []
    descriptions = []

    tracks = kernel.get("session_info", {}).get("tracks", [])
    new_idx = len(tracks)

    steps.append(CompiledStep(
        tool="create_midi_track",
        params={"name": "Ghost Vox"},
        description="Create track for ghost vocal",
    ))

    steps.append(CompiledStep(
        tool="load_sample_to_simpler",
        params={"track_index": new_idx, "file_path": file_path},
        description="Load vocal sample into Simpler",
    ))

    steps.append(CompiledStep(
        tool="reverse_simpler",
        params={"track_index": new_idx},
        description="Reverse vocal for ghostly character",
    ))
    descriptions.append("Reverse vocal")

    # Heavy reverb wash
    steps.append(CompiledStep(
        tool="set_track_send",
        params={"track_index": new_idx, "send_index": 0, "value": 0.55},
        description="Heavy reverb wash for ghostly depth",
    ))
    descriptions.append("Reverb wash")

    # Low volume — ghosts live in the background
    steps.append(CompiledStep(
        tool="set_track_volume",
        params={"track_index": new_idx, "volume": 0.30},
        description="Set ghost vocal low in mix",
    ))
    descriptions.append("Background level")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify ghost vocal producing audio with reverb tail",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="medium",
        summary="; ".join(descriptions),
        requires_approval=True,
    )


def _compile_sample_break_layer(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'sample_break_layer': slice a break and layer over existing drums."""
    file_path = _resolve_sample_path(kernel)
    if file_path is None:
        return _empty_sample_plan(move, kernel)

    steps = []
    descriptions = []
    warnings = []

    drums = resolvers.find_tracks_by_role(kernel, ["drums", "percussion"])
    if not drums:
        warnings.append("No existing drum tracks — break will be the primary rhythm")

    tracks = kernel.get("session_info", {}).get("tracks", [])
    new_idx = len(tracks)

    steps.append(CompiledStep(
        tool="create_midi_track",
        params={"name": "Break"},
        description="Create track for breakbeat layer",
    ))

    steps.append(CompiledStep(
        tool="load_sample_to_simpler",
        params={"track_index": new_idx, "file_path": file_path},
        description="Load breakbeat into Simpler",
    ))

    steps.append(CompiledStep(
        tool="set_simpler_playback_mode",
        params={"track_index": new_idx, "device_index": 0, "playback_mode": 2},
        description="Slice break by transients for individual hits",
    ))
    descriptions.append("Slice break")

    # Sit below main drums
    steps.append(CompiledStep(
        tool="set_track_volume",
        params={"track_index": new_idx, "volume": 0.45},
        description="Set break layer below main drums",
    ))
    descriptions.append("Balance break level")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify break layer producing audio alongside drums",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="medium",
        summary="; ".join(descriptions) if descriptions else "Layer breakbeat",
        requires_approval=True,
        warnings=warnings,
    )


def _compile_sample_resample_destroy(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'sample_resample_destroy': warp and mangle a sample destructively.

    SAFETY: This is a high-risk move — always requires approval.
    Only adjusts device params when a known device is confirmed present.
    """
    file_path = _resolve_sample_path(kernel)
    if file_path is None:
        return _empty_sample_plan(move, kernel)

    steps = []
    descriptions = []
    warnings = ["High-risk: destructive processing — consider duplicating track first"]

    tracks = kernel.get("session_info", {}).get("tracks", [])
    new_idx = len(tracks)

    steps.append(CompiledStep(
        tool="create_midi_track",
        params={"name": "Destroy"},
        description="Create track for destructive resampling",
    ))

    steps.append(CompiledStep(
        tool="load_sample_to_simpler",
        params={"track_index": new_idx, "file_path": file_path},
        description="Load sample for destruction",
    ))
    descriptions.append("Load source")

    steps.append(CompiledStep(
        tool="warp_simpler",
        params={"track_index": new_idx},
        description="Apply extreme warp for time-stretch artifacts",
    ))
    descriptions.append("Warp for artifacts")

    # Use volume + send instead of blindly setting device params
    steps.append(CompiledStep(
        tool="set_track_send",
        params={"track_index": new_idx, "send_index": 0, "value": 0.30},
        description="Add reverb send for destroyed texture depth",
    ))

    steps.append(CompiledStep(
        tool="set_track_volume",
        params={"track_index": new_idx, "volume": 0.50},
        description="Set destroyed sample at moderate level",
    ))
    descriptions.append("Set level")

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify destroyed sample producing audio",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="high",
        summary="; ".join(descriptions),
        requires_approval=True,
        warnings=warnings,
    )


def _compile_sample_one_shot_accent(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile 'sample_one_shot_accent': load a one-shot for rhythmic punctuation."""
    file_path = _resolve_sample_path(kernel)
    if file_path is None:
        return _empty_sample_plan(move, kernel)

    steps = []
    descriptions = []

    tracks = kernel.get("session_info", {}).get("tracks", [])
    new_idx = len(tracks)

    steps.append(CompiledStep(
        tool="create_midi_track",
        params={"name": "Accent"},
        description="Create track for one-shot accent",
    ))

    steps.append(CompiledStep(
        tool="load_sample_to_simpler",
        params={"track_index": new_idx, "file_path": file_path},
        description="Load one-shot into Simpler",
    ))

    steps.append(CompiledStep(
        tool="set_simpler_playback_mode",
        params={"track_index": new_idx, "device_index": 0, "playback_mode": 1},
        description="One-shot mode for trigger playback",
    ))
    descriptions.append("One-shot mode")

    steps.append(CompiledStep(
        tool="crop_simpler",
        params={"track_index": new_idx},
        description="Tight crop around the transient",
    ))
    descriptions.append("Crop to transient")

    # Accent should be punchy but not dominating
    steps.append(CompiledStep(
        tool="set_track_volume",
        params={"track_index": new_idx, "volume": 0.60},
        description="Set accent at punchy but balanced level",
    ))

    steps.append(CompiledStep(
        tool="get_track_meters",
        params={"include_stereo": True},
        description="Verify one-shot accent triggers cleanly",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level="low",
        summary="; ".join(descriptions) if descriptions else "One-shot accent",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
    )


# ── Register ────────────────────────────────────────────────────────────────

register_compiler("sample_chop_rhythm", _compile_sample_chop_rhythm)
register_compiler("sample_texture_layer", _compile_sample_texture_layer)
register_compiler("sample_vocal_ghost", _compile_sample_vocal_ghost)
register_compiler("sample_break_layer", _compile_sample_break_layer)
register_compiler("sample_resample_destroy", _compile_sample_resample_destroy)
register_compiler("sample_one_shot_accent", _compile_sample_one_shot_accent)
