"""v1.20.2 BUG #2 regression: sample family compilers must resolve
``file_path`` from ``seed_args`` (v1.20 convention) — not leak a
literal ``{sample_file_path}`` template placeholder to the compiled
plan.

Pre-fix state: ``sample_compilers._resolve_sample_path`` returned
``kernel.get("sample_file_path", "{sample_file_path}")``. Direct
``apply_semantic_move("sample_vocal_ghost", ...)`` calls — which build
the kernel without ``sample_file_path`` — got the literal placeholder,
which would fail at step 2 (load_sample_to_simpler) in explore mode
because the path doesn't exist.

Fix: read from ``seed_args["file_path"]`` first (v1.20 convention),
fall back to legacy ``kernel["sample_file_path"]`` (wonder_mode
setter), reject the plan with a warning if neither is present.

Campaign source: ~/Desktop/DREAM AI/demo Project/REPORT.md §BUG #2.
"""

from __future__ import annotations

import pytest

import mcp_server.semantic_moves  # noqa: F401
from mcp_server.semantic_moves import compiler as move_compiler
from mcp_server.semantic_moves.registry import get_move


_SAMPLE_MOVES = [
    "sample_chop_rhythm",
    "sample_texture_layer",
    "sample_vocal_ghost",
    "sample_break_layer",
    "sample_resample_destroy",
    "sample_one_shot_accent",
]


class TestSampleFamilySeedArgs:
    @pytest.mark.parametrize("move_id", _SAMPLE_MOVES)
    def test_missing_file_path_produces_non_executable_plan(self, move_id):
        """Calling a sample move without seed_args.file_path must reject
        with executable=False + clear warning, NOT leak a template
        placeholder into the compiled plan."""
        move = get_move(move_id)
        assert move is not None
        plan = move_compiler.compile(
            move,
            {"seed_args": {}, "session_info": {}, "mode": "improve"},
        )
        assert not plan.executable, (
            f"{move_id}: compiler must reject when file_path is missing, "
            f"not silently emit a plan with placeholder path"
        )
        assert plan.warnings, f"{move_id}: missing file_path must surface a warning"
        joined = " ".join(plan.warnings).lower()
        assert "file_path" in joined or "sample" in joined

    @pytest.mark.parametrize("move_id", _SAMPLE_MOVES)
    def test_no_load_sample_step_leaks_template_placeholder(self, move_id):
        """Even if the compiler emits steps, NO step should have
        file_path set to the literal placeholder '{sample_file_path}'."""
        move = get_move(move_id)
        plan = move_compiler.compile(
            move,
            {"seed_args": {}, "session_info": {}, "mode": "improve"},
        )
        for step in plan.steps:
            file_path = step.params.get("file_path")
            assert file_path != "{sample_file_path}", (
                f"{move_id} step {step.tool}: leaked template placeholder "
                f"'{{sample_file_path}}' into compiled plan params"
            )

    @pytest.mark.parametrize("move_id", _SAMPLE_MOVES)
    def test_seed_args_file_path_is_used(self, move_id):
        """When seed_args.file_path is provided, it must propagate into
        the compiled plan's load_sample_to_simpler step."""
        move = get_move(move_id)
        test_path = "/tmp/test_vocal_sample.wav"
        plan = move_compiler.compile(
            move,
            {
                "seed_args": {"file_path": test_path},
                "session_info": {"tracks": [{"name": "Drums", "index": 0}]},
                "mode": "improve",
            },
        )
        # Find the load_sample_to_simpler step (every sample move has one)
        load_steps = [s for s in plan.steps if s.tool == "load_sample_to_simpler"]
        assert load_steps, f"{move_id}: emits no load_sample_to_simpler step"
        assert load_steps[0].params.get("file_path") == test_path, (
            f"{move_id}: seed_args.file_path={test_path!r} did not reach "
            f"compiled step (got {load_steps[0].params.get('file_path')!r})"
        )

    @pytest.mark.parametrize("move_id", _SAMPLE_MOVES)
    def test_legacy_kernel_sample_file_path_still_works(self, move_id):
        """Backwards compat: wonder_mode/tools.py sets
        ``sample_context['sample_file_path']`` directly. That path
        should still propagate through the compiler."""
        move = get_move(move_id)
        test_path = "/tmp/legacy_path.wav"
        plan = move_compiler.compile(
            move,
            {
                "seed_args": {},
                "sample_file_path": test_path,   # legacy key
                "session_info": {"tracks": [{"name": "Drums", "index": 0}]},
                "mode": "improve",
            },
        )
        load_steps = [s for s in plan.steps if s.tool == "load_sample_to_simpler"]
        assert load_steps, f"{move_id}: emits no load_sample_to_simpler step"
        assert load_steps[0].params.get("file_path") == test_path
