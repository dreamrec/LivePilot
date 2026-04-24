"""Compilers for device-mutation semantic moves (v1.20).

Pure functions. Read ``kernel["seed_args"]`` for the user's target, emit
CompiledPlan steps matching the expected tool signatures
(``batch_set_parameters``, ``delete_device``, ``add_session_memory``).
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


# ── configure_device ──────────────────────────────────────────────────────────


def _compile_configure_device(move: SemanticMove, kernel: dict) -> CompiledPlan:
    args = kernel.get("seed_args") or {}
    track_index = args.get("track_index")
    device_index = args.get("device_index")
    overrides = args.get("param_overrides")

    if track_index is None or device_index is None or overrides is None:
        return _empty_plan(move, [
            "configure_device requires seed_args.track_index + device_index + param_overrides"
        ])
    if not isinstance(track_index, int) or not isinstance(device_index, int):
        return _empty_plan(move, [
            f"track_index and device_index must be ints, got "
            f"{type(track_index).__name__}/{type(device_index).__name__}"
        ])
    if device_index < 0:
        return _empty_plan(move, [f"device_index must be non-negative, got {device_index}"])
    if not isinstance(overrides, dict):
        return _empty_plan(move, [
            f"param_overrides must be a dict[str, Any], got {type(overrides).__name__}"
        ])
    if not overrides:
        return _empty_plan(move, [
            "param_overrides is empty — nothing to configure (delete_device "
            "is a different move)"
        ])

    # WIRE-FORMAT NOTE: compiled steps use the remote_command backend,
    # which calls ableton.send_command() directly — bypassing the MCP
    # tool's ergonomic rename at mcp_server/tools/devices.py:292
    # (_normalize_batch_entry). Ableton's Remote Script handler
    # (remote_script/LivePilot/devices.py:149) reads `name_or_index`
    # exclusively. Emit that key directly.
    parameters = [
        {"name_or_index": str(name), "value": value}
        for name, value in overrides.items()
    ]

    step = CompiledStep(
        tool="batch_set_parameters",
        params={
            "track_index": track_index,
            "device_index": device_index,
            "parameters": parameters,
        },
        description=(
            f"Configure device at track {track_index}, device_index {device_index} — "
            f"set {len(parameters)} parameter(s): "
            f"{', '.join(p['name_or_index'] for p in parameters)}"
        ),
        verify_after=True,
        backend="remote_command",
    )

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=[step],
        risk_level=move.risk_level,
        summary=step.description,
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=[],
    )


# ── remove_device ──────────────────────────────────────────────────────────────


def _compile_remove_device(move: SemanticMove, kernel: dict) -> CompiledPlan:
    args = kernel.get("seed_args") or {}
    track_index = args.get("track_index")
    device_index = args.get("device_index")
    reason = args.get("reason")

    if track_index is None or device_index is None:
        return _empty_plan(move, [
            "remove_device requires seed_args.track_index + device_index"
        ])
    if not isinstance(track_index, int) or not isinstance(device_index, int):
        return _empty_plan(move, [
            "track_index and device_index must be ints"
        ])
    if device_index < 0:
        return _empty_plan(move, [f"device_index must be non-negative, got {device_index}"])
    if not isinstance(reason, str) or not reason.strip():
        return _empty_plan(move, [
            "remove_device requires a non-empty seed_args.reason — "
            "destructive moves must be justified for the audit trail"
        ])

    delete_step = CompiledStep(
        tool="delete_device",
        params={"track_index": track_index, "device_index": device_index},
        description=(
            f"Delete device at track {track_index}, device_index {device_index}"
        ),
        verify_after=True,
        backend="remote_command",
    )

    memory_step = CompiledStep(
        tool="add_session_memory",
        params={
            "category": "device_removal",
            "content": (
                f"Removed track={track_index} device_index={device_index}: "
                f"{reason.strip()}"
            ),
        },
        description="Log removal reason to session memory for audit",
        verify_after=False,
        backend="mcp_tool",
    )

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=[delete_step, memory_step],
        risk_level=move.risk_level,
        summary=f"{delete_step.description} — reason: {reason.strip()}",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=[],
    )


# ── Register compilers ────────────────────────────────────────────────────────

register_compiler("configure_device", _compile_configure_device)
register_compiler("remove_device", _compile_remove_device)
