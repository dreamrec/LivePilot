"""Compilers for content-family semantic moves (v1.20).

Pure functions. Validate seed_args rigorously and emit steps whose params
match the underlying tool signatures exactly (clip_index vs clip_slot
naming carefully preserved — mcp_server/tools/clips.py:117 uses
``clip_index``).
"""

from __future__ import annotations

from .compiler import CompiledPlan, CompiledStep, register_compiler
from .models import SemanticMove


_DEFAULT_CLIP_LENGTH_BEATS = 4.0


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


# ── load_chord_source ─────────────────────────────────────────────────────────


def _compile_load_chord_source(move: SemanticMove, kernel: dict) -> CompiledPlan:
    args = kernel.get("seed_args") or {}
    track_index = args.get("track_index")
    clip_slot = args.get("clip_slot")
    notes = args.get("notes")
    name = args.get("name")
    length_beats = args.get("length_beats", _DEFAULT_CLIP_LENGTH_BEATS)

    if track_index is None or clip_slot is None or notes is None or name is None:
        return _empty_plan(move, [
            "load_chord_source requires seed_args.track_index + clip_slot + notes + name"
        ])
    if not isinstance(track_index, int) or not isinstance(clip_slot, int):
        return _empty_plan(move, [
            "track_index and clip_slot must be ints"
        ])
    if clip_slot < 0:
        return _empty_plan(move, [f"clip_slot must be non-negative, got {clip_slot}"])
    if not isinstance(notes, (list, tuple)) or not notes:
        return _empty_plan(move, ["notes must be a non-empty list of note dicts"])
    if not isinstance(name, str) or not name.strip():
        return _empty_plan(move, ["name must be a non-empty string"])
    try:
        length_f = float(length_beats)
    except (TypeError, ValueError):
        return _empty_plan(move, [f"length_beats must be numeric, got {length_beats!r}"])
    if length_f <= 0:
        return _empty_plan(move, [f"length_beats must be > 0, got {length_f}"])

    # Step order matters: create_clip must land before add_notes, and the
    # name step runs last so mid-pass inspection sees the real name, not
    # a default "Clip" Live would assign.
    create_step = CompiledStep(
        tool="create_clip",
        params={
            "track_index": track_index,
            "clip_index": clip_slot,
            "length": length_f,
        },
        description=f"Create MIDI clip at track {track_index} slot {clip_slot} ({length_f} beats)",
        verify_after=True,
        backend="remote_command",
    )
    add_step = CompiledStep(
        tool="add_notes",
        params={
            "track_index": track_index,
            "clip_index": clip_slot,
            "notes": list(notes),
        },
        description=f"Add {len(notes)} note(s) to clip",
        verify_after=True,
        backend="remote_command",
    )
    name_step = CompiledStep(
        tool="set_clip_name",
        params={
            "track_index": track_index,
            "clip_index": clip_slot,
            "name": name.strip(),
        },
        description=f"Name clip '{name.strip()}'",
        verify_after=True,
        backend="remote_command",
    )

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=[create_step, add_step, name_step],
        risk_level=move.risk_level,
        summary=(
            f"Load chord source '{name.strip()}' at track {track_index} slot "
            f"{clip_slot} ({len(notes)} notes, {length_f} beats)"
        ),
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=[],
    )


# ── create_drum_rack_pad ──────────────────────────────────────────────────────


def _compile_create_drum_rack_pad(move: SemanticMove, kernel: dict) -> CompiledPlan:
    args = kernel.get("seed_args") or {}
    track_index = args.get("track_index")
    pad_note = args.get("pad_note")
    file_path = args.get("file_path")
    rack_device_index = args.get("rack_device_index")  # optional
    chain_name = args.get("chain_name")  # optional

    if track_index is None or pad_note is None or file_path is None:
        return _empty_plan(move, [
            "create_drum_rack_pad requires seed_args.track_index + pad_note + file_path"
        ])
    if not isinstance(track_index, int) or not isinstance(pad_note, int):
        return _empty_plan(move, ["track_index and pad_note must be ints"])
    if not 0 <= pad_note <= 127:
        return _empty_plan(move, [f"pad_note must be MIDI 0-127, got {pad_note}"])
    if not isinstance(file_path, str) or not file_path.strip():
        return _empty_plan(move, ["file_path must be a non-empty absolute path string"])
    if rack_device_index is not None and not isinstance(rack_device_index, int):
        return _empty_plan(move, ["rack_device_index (when provided) must be int"])
    if chain_name is not None and not isinstance(chain_name, str):
        return _empty_plan(move, ["chain_name (when provided) must be str"])

    params: dict = {
        "track_index": track_index,
        "pad_note": pad_note,
        "file_path": file_path,
    }
    if rack_device_index is not None:
        params["rack_device_index"] = rack_device_index
    if chain_name is not None:
        params["chain_name"] = chain_name

    step = CompiledStep(
        tool="add_drum_rack_pad",
        params=params,
        description=(
            f"Add drum rack pad on track {track_index}: MIDI note {pad_note} → "
            f"{file_path.rsplit('/', 1)[-1]}"
        ),
        verify_after=True,
        backend="mcp_tool",
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

register_compiler("load_chord_source", _compile_load_chord_source)
register_compiler("create_drum_rack_pad", _compile_create_drum_rack_pad)
