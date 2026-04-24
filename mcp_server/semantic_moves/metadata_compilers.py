"""Compilers for metadata-family semantic moves (v1.20).

Pure functions. Each compiler emits one step per *provided* optional
field — the move lets the director collapse multiple one-line raw tool
calls into a single named intent without forcing the caller to fill in
fields they don't care about.
"""

from __future__ import annotations

from .compiler import CompiledPlan, CompiledStep, register_compiler
from .models import SemanticMove


def _empty_plan(move: SemanticMove, warnings: list[str]) -> CompiledPlan:
    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=[],
        risk_level=move.risk_level,
        summary="; ".join(warnings) if warnings else "No plan compiled",
        requires_approval=True,
        warnings=warnings,
    )


# ── configure_groove ──────────────────────────────────────────────────────────


def _compile_configure_groove(move: SemanticMove, kernel: dict) -> CompiledPlan:
    args = kernel.get("seed_args") or {}
    track_index = args.get("track_index")
    clip_indices = args.get("clip_indices")
    groove_id = args.get("groove_id")
    timing_amount = args.get("timing_amount")  # optional

    if track_index is None or clip_indices is None or groove_id is None:
        return _empty_plan(move, [
            "configure_groove requires seed_args.track_index + clip_indices + groove_id"
        ])
    if not isinstance(track_index, int) or not isinstance(groove_id, int):
        return _empty_plan(move, ["track_index and groove_id must be ints"])
    if not isinstance(clip_indices, (list, tuple)) or not clip_indices:
        return _empty_plan(move, ["clip_indices must be a non-empty list of ints"])
    if not all(isinstance(ci, int) and ci >= 0 for ci in clip_indices):
        return _empty_plan(move, [
            "clip_indices entries must be non-negative ints"
        ])

    warnings: list[str] = []
    clamped_timing: float | None = None
    if timing_amount is not None:
        try:
            t = float(timing_amount)
        except (TypeError, ValueError):
            return _empty_plan(move, [f"timing_amount must be numeric, got {timing_amount!r}"])
        clamped_timing = max(0.0, min(1.0, t))
        if clamped_timing != t:
            warnings.append(
                f"Clamped timing_amount {t} → {clamped_timing} (must be 0.0-1.0)"
            )

    steps: list[CompiledStep] = []
    for ci in clip_indices:
        steps.append(CompiledStep(
            tool="assign_clip_groove",
            params={
                "track_index": track_index,
                "clip_index": ci,
                "groove_id": groove_id,
            },
            description=f"Assign groove_id={groove_id} to track {track_index} clip {ci}",
            verify_after=True,
            backend="remote_command",
        ))
    if clamped_timing is not None:
        steps.append(CompiledStep(
            tool="set_groove_params",
            params={
                "groove_id": groove_id,
                "timing_amount": clamped_timing,
            },
            description=f"Set groove {groove_id} timing_amount to {clamped_timing}",
            verify_after=True,
            backend="remote_command",
        ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level=move.risk_level,
        summary=(
            f"Assign groove {groove_id} to {len(clip_indices)} clip(s) on track {track_index}"
            + (f"; timing={clamped_timing}" if clamped_timing is not None else "")
        ),
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=warnings,
    )


# ── set_scene_metadata ────────────────────────────────────────────────────────


def _compile_set_scene_metadata(move: SemanticMove, kernel: dict) -> CompiledPlan:
    args = kernel.get("seed_args") or {}
    scene_index = args.get("scene_index")
    name = args.get("name")
    color_index = args.get("color_index")
    tempo = args.get("tempo")

    if scene_index is None:
        return _empty_plan(move, ["set_scene_metadata requires seed_args.scene_index"])
    if not isinstance(scene_index, int) or scene_index < 0:
        return _empty_plan(move, [
            f"scene_index must be a non-negative int, got {scene_index!r}"
        ])
    if name is None and color_index is None and tempo is None:
        return _empty_plan(move, [
            "set_scene_metadata requires at least one of: name, color_index, tempo"
        ])

    steps: list[CompiledStep] = []
    summary_parts: list[str] = []
    if name is not None:
        if not isinstance(name, str):
            return _empty_plan(move, ["name must be a string"])
        steps.append(CompiledStep(
            tool="set_scene_name",
            params={"scene_index": scene_index, "name": name},
            description=f"Rename scene {scene_index} → '{name}'",
            verify_after=True,
            backend="remote_command",
        ))
        summary_parts.append(f"name='{name}'")
    if color_index is not None:
        if not isinstance(color_index, int):
            return _empty_plan(move, ["color_index must be int"])
        steps.append(CompiledStep(
            tool="set_scene_color",
            params={"scene_index": scene_index, "color_index": color_index},
            description=f"Color scene {scene_index} → index {color_index}",
            verify_after=True,
            backend="remote_command",
        ))
        summary_parts.append(f"color={color_index}")
    if tempo is not None:
        try:
            tempo_f = float(tempo)
        except (TypeError, ValueError):
            return _empty_plan(move, [f"tempo must be numeric, got {tempo!r}"])
        steps.append(CompiledStep(
            tool="set_scene_tempo",
            params={"scene_index": scene_index, "tempo": tempo_f},
            description=f"Set scene {scene_index} tempo → {tempo_f}",
            verify_after=True,
            backend="remote_command",
        ))
        summary_parts.append(f"tempo={tempo_f}")

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level=move.risk_level,
        summary=f"Scene {scene_index} metadata: {', '.join(summary_parts)}",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=[],
    )


# ── set_track_metadata ────────────────────────────────────────────────────────


def _compile_set_track_metadata(move: SemanticMove, kernel: dict) -> CompiledPlan:
    args = kernel.get("seed_args") or {}
    track_index = args.get("track_index")
    name = args.get("name")
    color_index = args.get("color_index")

    if track_index is None:
        return _empty_plan(move, ["set_track_metadata requires seed_args.track_index"])
    if not isinstance(track_index, int):
        return _empty_plan(move, [f"track_index must be int, got {track_index!r}"])
    if name is None and color_index is None:
        return _empty_plan(move, [
            "set_track_metadata requires at least one of: name, color_index"
        ])

    steps: list[CompiledStep] = []
    summary_parts: list[str] = []
    if name is not None:
        if not isinstance(name, str):
            return _empty_plan(move, ["name must be a string"])
        steps.append(CompiledStep(
            tool="set_track_name",
            params={"track_index": track_index, "name": name},
            description=f"Rename track {track_index} → '{name}'",
            verify_after=True,
            backend="remote_command",
        ))
        summary_parts.append(f"name='{name}'")
    if color_index is not None:
        if not isinstance(color_index, int):
            return _empty_plan(move, ["color_index must be int"])
        steps.append(CompiledStep(
            tool="set_track_color",
            params={"track_index": track_index, "color_index": color_index},
            description=f"Color track {track_index} → index {color_index}",
            verify_after=True,
            backend="remote_command",
        ))
        summary_parts.append(f"color={color_index}")

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level=move.risk_level,
        summary=f"Track {track_index} metadata: {', '.join(summary_parts)}",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=[],
    )


# ── Register compilers ────────────────────────────────────────────────────────

register_compiler("configure_groove", _compile_configure_groove)
register_compiler("set_scene_metadata", _compile_set_scene_metadata)
register_compiler("set_track_metadata", _compile_set_track_metadata)
