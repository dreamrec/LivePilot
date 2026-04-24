"""Compilers for routing-domain semantic moves (v1.20).

Each compiler is pure — reads ``kernel["seed_args"]`` for user targets and
``kernel["session_info"]`` for topology, emits a CompiledPlan of concrete
tool calls the execution router can dispatch. No I/O, no MCP calls.

Rejection policy: when seed_args are missing/invalid, emit a plan with
``executable=False`` (empty steps) and a clear warning. This is the v1.20
contract — see docs/plans/v1.20-structural-plan.md §7.
"""

from __future__ import annotations

from .compiler import CompiledPlan, CompiledStep, register_compiler
from .models import SemanticMove


def _return_track_index_to_abs(return_track_index: int) -> int:
    """Map a 0-based return index to Ableton's negative-track convention.

    Return A (return_track_index=0) → track_index=-1
    Return B (return_track_index=1) → track_index=-2
    (See mcp_server/tools/mixing.py:227 — "-1=A, -2=B".)
    """
    return -(return_track_index + 1)


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


# ── build_send_chain ──────────────────────────────────────────────────────────


def _compile_build_send_chain(move: SemanticMove, kernel: dict) -> CompiledPlan:
    args = kernel.get("seed_args") or {}
    return_idx = args.get("return_track_index")
    device_chain = args.get("device_chain")
    warnings: list[str] = []

    if return_idx is None or device_chain is None:
        return _empty_plan(move, [
            "build_send_chain requires seed_args.return_track_index + device_chain"
        ])
    if not isinstance(return_idx, int) or return_idx < 0:
        return _empty_plan(move, [
            f"return_track_index must be a non-negative int, got {return_idx!r}"
        ])
    if not isinstance(device_chain, (list, tuple)) or not device_chain:
        return _empty_plan(move, [
            "device_chain is empty — nothing to load onto the return"
        ])
    if not all(isinstance(d, str) and d.strip() for d in device_chain):
        return _empty_plan(move, [
            "device_chain entries must be non-empty strings (device names)"
        ])

    abs_track_index = _return_track_index_to_abs(return_idx)

    steps: list[CompiledStep] = []
    for device_name in device_chain:
        steps.append(CompiledStep(
            tool="find_and_load_device",
            params={
                "track_index": abs_track_index,
                "device_name": device_name,
                # Return chains legitimately may hold two of the same device
                # (Echo feedback stacking, parallel reverbs). Don't block it.
                "allow_duplicate": True,
            },
            description=f"Load {device_name} onto return {chr(ord('A') + return_idx)}",
            verify_after=True,
            backend="remote_command",
        ))

    # Verify-only read at the end (caller uses this to confirm ordering).
    steps.append(CompiledStep(
        tool="get_track_info",
        params={"track_index": abs_track_index},
        description="Verify return-track device order after load",
        verify_after=False,
        backend="remote_command",
    ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level=move.risk_level,
        summary=(
            f"Load {len(device_chain)} device(s) onto return "
            f"{chr(ord('A') + return_idx)}: {', '.join(device_chain)}"
        ),
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=warnings,
    )


# ── configure_send_architecture ───────────────────────────────────────────────


def _compile_configure_send_architecture(move: SemanticMove, kernel: dict) -> CompiledPlan:
    args = kernel.get("seed_args") or {}
    track_indices = args.get("source_track_indices")
    send_index = args.get("send_index")
    levels = args.get("levels")

    if track_indices is None or send_index is None or levels is None:
        return _empty_plan(move, [
            "configure_send_architecture requires seed_args.source_track_indices + send_index + levels"
        ])
    if not isinstance(track_indices, (list, tuple)) or not track_indices:
        return _empty_plan(move, ["source_track_indices must be a non-empty list"])
    if not isinstance(levels, (list, tuple)):
        return _empty_plan(move, ["levels must be a list"])
    if len(track_indices) != len(levels):
        return _empty_plan(move, [
            f"source_track_indices ({len(track_indices)}) and levels "
            f"({len(levels)}) must have the same length"
        ])
    if not isinstance(send_index, int) or send_index < 0:
        return _empty_plan(move, [f"send_index must be a non-negative int, got {send_index!r}"])

    warnings: list[str] = []
    steps: list[CompiledStep] = []
    for track_i, level in zip(track_indices, levels):
        if not isinstance(track_i, int):
            return _empty_plan(move, [f"track_index must be int, got {track_i!r}"])
        try:
            level_f = float(level)
        except (TypeError, ValueError):
            return _empty_plan(move, [f"level must be numeric, got {level!r}"])
        clamped = max(0.0, min(1.0, level_f))
        if clamped != level_f:
            warnings.append(
                f"Clamped level {level_f} → {clamped} for track {track_i} "
                "(send values must be in [0.0, 1.0])"
            )
        steps.append(CompiledStep(
            tool="set_track_send",
            params={
                "track_index": track_i,
                "send_index": send_index,
                "value": clamped,
            },
            description=(
                f"Set track {track_i} send {send_index} to {clamped:.2f}"
            ),
            verify_after=True,
            backend="remote_command",
        ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level=move.risk_level,
        summary=f"Set {len(steps)} send levels on send {send_index}",
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=warnings,
    )


# ── set_track_routing ─────────────────────────────────────────────────────────


def _compile_set_track_routing(move: SemanticMove, kernel: dict) -> CompiledPlan:
    args = kernel.get("seed_args") or {}
    track_index = args.get("track_index")
    # Seed_args keeps the ergonomic ``output_routing_type`` /
    # ``output_routing_channel`` names (matching the MCP tool's public
    # surface, so the director can type them naturally). But compiled
    # steps must use the wire-format names — the remote_command backend
    # bypasses the MCP tool's rename at mcp_server/tools/mixing.py:230
    # (output_routing_type → output_type). Ableton's Remote Script at
    # remote_script/LivePilot/mixing.py:227 keys on the wire format.
    out_type = args.get("output_routing_type")
    out_channel = args.get("output_routing_channel")

    if track_index is None:
        return _empty_plan(move, ["set_track_routing requires seed_args.track_index"])
    if out_type is None and out_channel is None:
        return _empty_plan(move, [
            "set_track_routing requires at least output_routing_type or output_routing_channel"
        ])
    if not isinstance(track_index, int):
        return _empty_plan(move, [f"track_index must be int, got {track_index!r}"])

    params: dict = {"track_index": track_index}
    if out_type is not None:
        params["output_type"] = str(out_type)
    if out_channel is not None:
        params["output_channel"] = str(out_channel)

    step = CompiledStep(
        tool="set_track_routing",
        params=params,
        description=(
            f"Set track {track_index} output routing → "
            f"{out_type or '(unchanged)'} / {out_channel or '(unchanged)'}"
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


# ── Register compilers ────────────────────────────────────────────────────────

register_compiler("build_send_chain", _compile_build_send_chain)
register_compiler("configure_send_architecture", _compile_configure_send_architecture)
register_compiler("set_track_routing", _compile_set_track_routing)
