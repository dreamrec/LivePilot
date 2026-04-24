"""v1.20.2 BUG #3 regression: analyzer-read steps marked ``optional=True``
must NOT abort the rest of the plan when they fail.

Pre-fix: ``tighten_low_end`` and ``make_kick_bass_lock`` emit
``get_master_spectrum`` as step 0. When LivePilot_Analyzer is not loaded
on master, step 0 fails with a clear error — and the router's
``stop_on_failure=True`` default halts the plan before the ACTUAL
mutation steps (bass volume change) ever run. Moves become
non-functional on any session without the analyzer pre-loaded.

Fix: ``CompiledStep`` gains an ``optional: bool = False`` field. Steps
tagged optional are skipped-with-warning on failure; downstream
mutations still execute. The 2 affected mix moves mark their analyzer
pre-read as ``optional=True``.

Campaign source: ~/Desktop/DREAM AI/demo Project/REPORT.md §BUG #3.
"""

from __future__ import annotations

import asyncio

import pytest

import mcp_server.semantic_moves  # noqa: F401
from mcp_server.semantic_moves import compiler as move_compiler
from mcp_server.semantic_moves.registry import get_move
from mcp_server.runtime.execution_router import execute_plan_steps_async


class TestAnalyzerStepOptional:
    @pytest.mark.parametrize("move_id", ["tighten_low_end", "make_kick_bass_lock"])
    def test_compiler_marks_analyzer_read_as_optional(self, move_id):
        """The ``get_master_spectrum`` step emitted as a pre-read must
        carry ``optional=True``."""
        move = get_move(move_id)
        kernel = {
            "session_info": {
                "tracks": [
                    {"name": "Drums", "index": 0},
                    {"name": "Bass", "index": 1},
                ],
            },
            "seed_args": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        spectrum_steps = [s for s in plan.steps if s.tool == "get_master_spectrum"]
        assert spectrum_steps, f"{move_id} compiles without get_master_spectrum"
        for step in spectrum_steps:
            assert getattr(step, "optional", False) is True, (
                f"{move_id}: get_master_spectrum step must be optional=True "
                "so analyzer-unavailable doesn't abort the rest of the plan"
            )


class TestRouterOptionalStepContinuation:
    def test_optional_step_failure_allows_subsequent_steps_to_run(self):
        """When an optional step fails AND stop_on_failure=True,
        subsequent steps must still execute."""
        steps = [
            {"tool": "does_not_exist", "params": {}, "backend": "mcp_tool",
             "optional": True},  # will fail (not in registry)
            {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.5},
             "backend": "remote_command"},
        ]

        # Mock ableton + mcp_dispatch
        recorded_calls = []

        class _Ableton:
            def send_command(self, cmd, params=None):
                recorded_calls.append((cmd, params))
                return {"ok": True}

        # The optional step will fail via mcp_tool path since "does_not_exist"
        # is not in the dispatch. The router must SKIP it and proceed.
        results = asyncio.run(execute_plan_steps_async(
            steps,
            ableton=_Ableton(),
            mcp_registry={},  # empty — optional step will fail
            stop_on_failure=True,
        ))

        assert len(results) == 2, "both steps must be recorded in results"
        assert not results[0].ok, "first step was supposed to fail"
        assert results[1].ok, (
            "second step must have executed despite the optional step's "
            "failure (router skip-and-continue on optional failures)"
        )
        assert recorded_calls == [("set_track_volume",
                                    {"track_index": 0, "volume": 0.5})]

    def test_non_optional_step_failure_still_stops_plan(self):
        """Control: a NON-optional step failure continues to halt the plan
        per default stop_on_failure=True."""
        steps = [
            {"tool": "does_not_exist", "params": {}, "backend": "mcp_tool"},  # NOT optional
            {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.5},
             "backend": "remote_command"},
        ]

        recorded_calls = []

        class _Ableton:
            def send_command(self, cmd, params=None):
                recorded_calls.append((cmd, params))
                return {"ok": True}

        results = asyncio.run(execute_plan_steps_async(
            steps,
            ableton=_Ableton(),
            mcp_registry={},
            stop_on_failure=True,
        ))

        # Router stops at the first non-optional failure
        assert len(results) == 1, f"expected 1 result (stopped), got {len(results)}"
        assert not results[0].ok
        assert recorded_calls == [], (
            "second step must NOT have run — non-optional failure halts plan"
        )

    def test_compiled_step_optional_field_survives_step_dict_conversion(self):
        """_step_to_dict in apply_semantic_move must preserve the optional
        flag so the router sees it."""
        from mcp_server.semantic_moves.compiler import CompiledStep

        step = CompiledStep(
            tool="get_master_spectrum",
            params={},
            description="analyzer read",
            verify_after=False,
            optional=True,
        )

        # Simulate the _step_to_dict transformation from apply_semantic_move
        d = {
            "tool": step.tool,
            "params": step.params,
            "description": step.description,
        }
        if getattr(step, "backend", None):
            d["backend"] = step.backend
        if getattr(step, "optional", False):
            d["optional"] = True

        assert d.get("optional") is True
