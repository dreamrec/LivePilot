"""BUG-2026-04-24 regression: ensure every v1.20 semantic-move compiler
emits its steps using the WIRE-FORMAT param names — the exact keys
``ableton.send_command()`` expects, not the ergonomic MCP tool
input-field names.

Background: the execution router's ``remote_command`` backend calls
``ableton.send_command(tool, params)`` directly, bypassing the MCP
tool's input-normalization layer. Two v1.20 compilers initially
emitted MCP-input keys (``parameter_name``, ``output_routing_type``)
that the MCP tool renames to the wire format; compiled plans skipped
that rename and Ableton got unknown keys → silent failures / obscure
errors.

This suite locks the wire-format contract at the compiler boundary
for each v1.20 move. It does NOT test the Remote Script handler
itself — just that compiler output stays in sync with the handler's
expected keys.
"""

from __future__ import annotations

from typing import Iterable

import pytest

import mcp_server.semantic_moves  # noqa: F401
from mcp_server.semantic_moves import compiler as move_compiler
from mcp_server.semantic_moves.registry import get_move


# ── Wire-format key inventory (authoritative per remote_script/LivePilot) ─────
#
# For each tool a v1.20 compiler emits, list the param keys the Remote
# Script handler reads. Steps must contain these keys; they must NOT
# contain MCP-tool-layer ergonomic aliases that the MCP tool renames
# before send_command.

_WIRE_FORMAT: dict[str, dict[str, object]] = {
    # tool_name -> {"required": {k,...}, "forbidden_aliases": {k: "expected_name"}}
    "batch_set_parameters": {
        "required_param_keys_per_entry": {"name_or_index", "value"},
        "forbidden_aliases_in_entries": {"parameter_name": "name_or_index"},
    },
    "set_track_routing": {
        "required_keys": {"track_index"},
        "wire_format_fields": {"output_type", "output_channel", "input_type", "input_channel"},
        "forbidden_aliases": {
            "output_routing_type": "output_type",
            "output_routing_channel": "output_channel",
            "input_routing_type": "input_type",
            "input_routing_channel": "input_channel",
        },
    },
    "find_and_load_device": {
        "required_keys": {"track_index", "device_name"},
    },
    "get_track_info": {
        "required_keys": {"track_index"},
    },
    "delete_device": {
        "required_keys": {"track_index", "device_index"},
    },
    "set_track_send": {
        "required_keys": {"track_index", "send_index", "value"},
    },
    "create_clip": {
        "required_keys": {"track_index", "clip_index", "length"},
    },
    "add_notes": {
        "required_keys": {"track_index", "clip_index", "notes"},
    },
    "set_clip_name": {
        "required_keys": {"track_index", "clip_index", "name"},
    },
    "assign_clip_groove": {
        "required_keys": {"track_index", "clip_index", "groove_id"},
    },
    "set_groove_params": {
        "required_keys": {"groove_id"},
    },
    "set_scene_name": {
        "required_keys": {"scene_index", "name"},
    },
    "set_scene_color": {
        "required_keys": {"scene_index", "color_index"},
    },
    "set_scene_tempo": {
        "required_keys": {"scene_index", "tempo"},
    },
    "set_track_name": {
        "required_keys": {"track_index", "name"},
    },
    "set_track_color": {
        "required_keys": {"track_index", "color_index"},
    },
    "add_drum_rack_pad": {
        "required_keys": {"track_index", "pad_note", "file_path"},
    },
    "add_session_memory": {
        "required_keys": {"category", "content"},
    },
}


# ── Fixtures: one valid seed_args per v1.20 move ──────────────────────────────

_V1_20_SCENARIOS: list[tuple[str, dict]] = [
    ("build_send_chain", {"return_track_index": 0, "device_chain": ["Echo", "Auto Filter"]}),
    ("configure_send_architecture", {"source_track_indices": [0, 1], "send_index": 0, "levels": [0.4, 0.2]}),
    ("set_track_routing", {"track_index": 0, "output_routing_type": "Sends Only", "output_routing_channel": "Post Mixer"}),
    ("configure_device", {"track_index": 0, "device_index": 0, "param_overrides": {"Decay Time": 0.85, "Dry/Wet": 0.35}}),
    ("remove_device", {"track_index": 0, "device_index": 1, "reason": "test"}),
    ("load_chord_source", {
        "track_index": 0, "clip_slot": 0,
        "notes": [{"pitch": 60, "start_time": 0.0, "duration": 4.0, "velocity": 80}],
        "name": "chord",
    }),
    ("create_drum_rack_pad", {"track_index": 0, "pad_note": 36, "file_path": "/tmp/kick.wav"}),
    ("configure_groove", {"track_index": 0, "clip_indices": [0], "groove_id": 1, "timing_amount": 0.6}),
    ("set_scene_metadata", {"scene_index": 0, "name": "Drop", "color_index": 5, "tempo": 128.0}),
    ("set_track_metadata", {"track_index": 0, "name": "Bass", "color_index": 7}),
]


def _compile(move_id: str, seed_args: dict):
    move = get_move(move_id)
    assert move is not None, f"move {move_id} not registered"
    return move_compiler.compile(
        move,
        {"seed_args": seed_args, "session_info": {}, "mode": "improve"},
    )


@pytest.mark.parametrize("move_id,seed_args", _V1_20_SCENARIOS, ids=[s[0] for s in _V1_20_SCENARIOS])
def test_compiler_steps_use_wire_format_keys(move_id: str, seed_args: dict):
    plan = _compile(move_id, seed_args)
    assert plan.executable, f"{move_id} compiled to non-executable plan; warnings={plan.warnings}"

    for i, step in enumerate(plan.steps):
        spec = _WIRE_FORMAT.get(step.tool)
        if spec is None:
            # Either the tool is read-only (no params Ableton requires) OR
            # it was added without updating _WIRE_FORMAT. Fail loudly so a
            # reviewer adds the entry.
            pytest.fail(
                f"{move_id} step {i}: emits tool {step.tool!r} which is not "
                f"in the wire-format inventory. Add an entry to "
                f"tests/test_compiler_wire_format_parity.py._WIRE_FORMAT."
            )

        # 1. All required top-level keys must be present.
        required: set = set(spec.get("required_keys", set()))  # type: ignore[arg-type]
        missing = required - set(step.params.keys())
        assert not missing, (
            f"{move_id} step {i} ({step.tool}): missing required keys "
            f"{sorted(missing)}; got {sorted(step.params.keys())}"
        )

        # 2. No forbidden ergonomic aliases must be present at the top level.
        forbidden: dict = spec.get("forbidden_aliases", {})  # type: ignore[assignment]
        for alias, expected_wire_name in forbidden.items():
            assert alias not in step.params, (
                f"{move_id} step {i} ({step.tool}): emitted ergonomic key "
                f"{alias!r} — must use wire-format key {expected_wire_name!r} "
                f"because the remote_command backend bypasses the MCP tool's "
                f"rename layer."
            )

        # 3. For steps carrying a 'parameters' list, check each entry's keys.
        per_entry_required: set = set(spec.get("required_param_keys_per_entry", set()))  # type: ignore[arg-type]
        per_entry_forbidden: dict = spec.get("forbidden_aliases_in_entries", {})  # type: ignore[assignment]
        if per_entry_required or per_entry_forbidden:
            entries = step.params.get("parameters", [])
            assert isinstance(entries, list) and entries, (
                f"{move_id} step {i} ({step.tool}): expected a 'parameters' "
                f"list, got {entries!r}"
            )
            for j, entry in enumerate(entries):
                missing = per_entry_required - set(entry.keys())
                assert not missing, (
                    f"{move_id} step {i}/{j} ({step.tool}): parameters entry "
                    f"missing keys {sorted(missing)}; got {sorted(entry.keys())}"
                )
                for alias, expected in per_entry_forbidden.items():
                    assert alias not in entry, (
                        f"{move_id} step {i}/{j} ({step.tool}): entry uses "
                        f"ergonomic key {alias!r} — must use wire-format key "
                        f"{expected!r} (remote_command bypasses MCP tool rename)"
                    )
