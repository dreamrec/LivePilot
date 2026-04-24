"""Wire-format parity guard: ensure every semantic-move compiler emits
steps using the WIRE-FORMAT param names — the exact keys
``ableton.send_command()`` expects, not the ergonomic MCP tool
input-field names.

v1.20 origin: commit 8bdf8bf fixed two v1.20 compilers that emitted
MCP-input keys (``parameter_name``, ``output_routing_type``) which the
MCP tool renames to the wire format; compiled plans skipped that rename
and Ableton got unknown keys → silent failures / obscure errors.

v1.21 extension: the guard now covers all 43 pre-v1.21 moves (10 v1.20
+ 33 pre-v1.20) so any latent drift that shipped silently across
pre-v1.20 compilers surfaces as a fixable gate failure rather than a
runtime error. See ``docs/plans/v1.21-structural-plan.md §4.4`` for
the rationale (test-first discovery gate, variant-B' escape hatch if
>3 drift bugs are surfaced).

This suite locks the wire-format contract at the compiler boundary
for every registered move. It does NOT test the Remote Script handler
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
# For each tool a compiler emits, list the param keys the Remote Script
# handler reads. Steps must contain these keys; they must NOT contain
# MCP-tool-layer ergonomic aliases that the MCP tool renames before
# send_command.

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

    # ── v1.21 additions: tools emitted by pre-v1.20 compilers. ───────────────
    # Required-key sets derived from Remote Script handler signatures
    # (remote_script/LivePilot/mixing.py, devices.py) and MCP tool signatures
    # (mcp_server/device_forge/tools.py).
    "set_track_volume": {
        # handler: track_index = int(params["track_index"]); volume = float(params["volume"])
        "required_keys": {"track_index", "volume"},
    },
    "set_master_volume": {
        # handler: volume = float(params["volume"])
        "required_keys": {"volume"},
    },
    "get_track_meters": {
        # handler: track_index = params.get("track_index")  — optional
        # handler: include_stereo = bool(params.get("include_stereo", False)) — optional
        "required_keys": set(),
    },
    "get_master_meters": {
        # handler reads master directly, no params consumed
        "required_keys": set(),
    },
    "get_master_spectrum": {
        # bridge-backed read; no params required at compile time
        "required_keys": set(),
    },
    "generate_m4l_effect": {
        # Compiler injects gen_code (v1.20.2 BUG #1 fix); name + device_type
        # come from the move's plan_template.
        "required_keys": {"name", "device_type", "gen_code"},
    },

    # Tools emitted by sample/automation compilers — signatures from
    # mcp_server/tools/analyzer.py + tools/devices.py + tools/mixing.py
    # + tools/automation.py (mcp_tool backend) and
    # remote_script/LivePilot/tracks.py (remote_command backend).
    "create_midi_track": {
        # handler: index = int(params.get("index", -1)) — all optional
        "required_keys": set(),
    },
    "set_track_pan": {
        # MCP tool signature: (track_index, pan) — both required
        "required_keys": {"track_index", "pan"},
    },
    "load_sample_to_simpler": {
        # MCP tool signature: (track_index, file_path, device_index=0)
        "required_keys": {"track_index", "file_path"},
    },
    "set_simpler_playback_mode": {
        # handler: track_index, device_index, playback_mode required;
        # slice_by + sensitivity optional
        "required_keys": {"track_index", "device_index", "playback_mode"},
    },
    "reverse_simpler": {
        # MCP tool signature: (track_index, device_index=0)
        "required_keys": {"track_index"},
    },
    "crop_simpler": {
        # MCP tool signature: (track_index, device_index=0)
        "required_keys": {"track_index"},
    },
    "apply_automation_shape": {
        # MCP tool signature: (track_index, clip_index, parameter_type,
        # curve_type, duration=4.0, density=16, device_index=Optional)
        "required_keys": {"track_index", "clip_index", "parameter_type", "curve_type"},
    },
    "warp_simpler": {
        # MCP tool signature: (track_index, device_index=0, beats=4)
        "required_keys": {"track_index"},
    },

    # v1.21 — configure_record_readiness emissions. The Remote Script
    # handlers (tracks.py:263 + transport.py:183) read specific keys
    # that differ from the MCP tool's ergonomic kwargs; pin both the
    # required set AND the forbidden-alias mapping.
    "set_track_arm": {
        # handler: track_index = int(params["track_index"]);
        # arm = bool(params["arm"]) — NOT "armed"
        "required_keys": {"track_index", "arm"},
        "forbidden_aliases": {"armed": "arm"},
    },
    "set_exclusive_arm": {
        # handler: song.exclusive_arm = bool(params["enabled"])
        # Global mode toggle — no track_index.
        "required_keys": {"enabled"},
        "forbidden_aliases": {"track_index": "enabled"},
    },
}


# ── Session-info injection for session-info-dependent compilers ───────────────
#
# Three pre-v1.20 compilers return a non-executable plan when session_info
# is empty: safe_spotlight, shape_transients, tighten_low_end. They
# inspect session_info["tracks"] for specific role_tags and decline to
# emit steps otherwise. To exercise their wire-format emissions, the
# parity test injects a rich session_info (below) when compiling them.
#
# Not a scope change — the parity test's contract is "emitted steps match
# wire format"; session_info is the input that makes them executable in
# the first place.

_SESSION_INFO_DEPENDENT: set[str] = {
    "safe_spotlight",
    "shape_transients",
    "tighten_low_end",
}

_RICH_SESSION_INFO: dict = {
    "tracks": [
        {"index": 0, "name": "Kick", "role_tags": ["drums", "kick"],        "type": "midi"},
        {"index": 1, "name": "Bass", "role_tags": ["bass"],                 "type": "midi"},
        {"index": 2, "name": "Hats", "role_tags": ["drums", "percussion"],  "type": "midi"},
        {"index": 3, "name": "Lead", "role_tags": ["lead", "chords"],       "type": "midi"},
    ],
}


# ── Fixtures: one valid seed_args per registered move ─────────────────────────

_ALL_MOVE_SCENARIOS: list[tuple[str, dict]] = [
    # ── v1.20 moves (seed_args carried forward from v1.20's suite) ──────────
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

    # ── v1.21 retroactive: pre-v1.20 moves (33 entries) ──────────────────────
    # Most compile with seed_args={}. Exceptions:
    #   - sample_* family (6 moves): v1.20.2 BUG #2 fix mandates seed_args.file_path
    #   - tighten_low_end / shape_transients / safe_spotlight (3 moves): need
    #     populated session_info — injected via _SESSION_INFO_DEPENDENT in _compile()

    # mix family (6)
    ("tighten_low_end", {}),
    ("widen_stereo", {}),
    ("make_punchier", {}),
    ("darken_without_losing_width", {}),
    ("reduce_repetition_fatigue", {}),
    ("make_kick_bass_lock", {}),

    # arrangement family (2)
    ("create_buildup_tension", {}),
    ("smooth_scene_handoff", {}),

    # transition family (4)
    ("increase_forward_motion", {}),
    ("open_chorus", {}),
    ("create_breakdown", {}),
    ("bridge_sections", {}),

    # sound_design family (4)
    ("add_warmth", {}),
    ("add_texture", {}),
    ("shape_transients", {}),
    ("add_space", {}),

    # performance family (4)
    ("recover_energy", {}),
    ("decompress_tension", {}),
    ("safe_spotlight", {}),
    ("emergency_simplify", {}),

    # device_creation family (7 Device Forge moves).
    # Post-v1.21 parity-gate fix: the compiler threads track_index from
    # seed_args into the find_and_load_device step (pre-fix, plan_templates
    # emitted {"query": ...} with no track_index — broken at runtime).
    ("create_chaos_modulator",   {"track_index": 0}),
    ("create_feedback_resonator", {"track_index": 0}),
    ("create_wavefolder_effect",  {"track_index": 0}),
    ("create_bitcrusher_effect",  {"track_index": 0}),
    ("create_karplus_string",     {"track_index": 0}),
    ("create_stochastic_texture", {"track_index": 0}),
    ("create_fdn_reverb",         {"track_index": 0}),

    # sample family (6) — file_path required per v1.20.2 BUG #2 fix
    ("sample_chop_rhythm",      {"file_path": "/tmp/test_sample.wav"}),
    ("sample_texture_layer",    {"file_path": "/tmp/test_sample.wav"}),
    ("sample_vocal_ghost",      {"file_path": "/tmp/test_sample.wav"}),
    ("sample_break_layer",      {"file_path": "/tmp/test_sample.wav"}),
    ("sample_resample_destroy", {"file_path": "/tmp/test_sample.wav"}),
    ("sample_one_shot_accent",  {"file_path": "/tmp/test_sample.wav"}),

    # ── v1.21 new moves ───────────────────────────────────────────────────
    # configure_record_readiness — performance family. Exercises the
    # non-exclusive single-step path. The exclusive-mode 2-step variant
    # is pinned separately in tests/test_performance_moves.py.
    ("configure_record_readiness", {"track_index": 0, "armed": True, "exclusive": False}),
]


def _compile(move_id: str, seed_args: dict):
    move = get_move(move_id)
    assert move is not None, f"move {move_id} not registered"
    session_info = _RICH_SESSION_INFO if move_id in _SESSION_INFO_DEPENDENT else {}
    return move_compiler.compile(
        move,
        {"seed_args": seed_args, "session_info": session_info, "mode": "improve"},
    )


@pytest.mark.parametrize(
    "move_id,seed_args",
    _ALL_MOVE_SCENARIOS,
    ids=[s[0] for s in _ALL_MOVE_SCENARIOS],
)
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
