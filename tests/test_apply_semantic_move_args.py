"""Tests for v1.20's args-threading extension on apply_semantic_move /
preview_semantic_move.

Context: pre-v1.20, ``apply_semantic_move(ctx, move_id, mode)`` passed only
``session_info + mode + capability_state`` to the compiler. That's insufficient
for the v1.20 routing/content/metadata moves, which take user-supplied targets
like ``return_track_index`` / ``device_chain`` / ``notes``. This suite locks
in the extension contract:

  * ``args: dict`` is an optional kwarg (backward compatible when omitted).
  * When provided, it surfaces inside the kernel as ``kernel["seed_args"]``.
  * preview_semantic_move mirrors the same contract for dry-run inspection.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from mcp_server.semantic_moves import compiler as move_compiler
from mcp_server.semantic_moves.models import SemanticMove
from mcp_server.semantic_moves.registry import register, _REGISTRY
from mcp_server.semantic_moves.compiler import CompiledPlan, CompiledStep


_CAPTURED_KERNELS: list[dict] = []
_PROBE_ID = "_test_seed_args_probe"


def _seed_args_probe_compiler(move: SemanticMove, kernel: dict) -> CompiledPlan:
    _CAPTURED_KERNELS.append(kernel)
    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=[CompiledStep(
            tool="get_session_info",
            params={},
            description="probe — should never execute in improve mode",
            backend="mcp_tool",
        )],
        summary="probe",
    )


@pytest.fixture(autouse=True)
def _register_probe_move():
    """Register a throwaway probe move so we can observe what the compiler saw."""
    _CAPTURED_KERNELS.clear()
    probe = SemanticMove(
        move_id=_PROBE_ID,
        family="mix",
        intent="test-only probe for seed_args threading",
    )
    register(probe)
    move_compiler.register_compiler(_PROBE_ID, _seed_args_probe_compiler)
    yield
    _REGISTRY.pop(_PROBE_ID, None)
    move_compiler._COMPILERS.pop(_PROBE_ID, None)


class _MinimalAbleton:
    def send_command(self, cmd, params=None):
        return {"tempo": 120, "track_count": 0, "tracks": [], "scenes": []}


def _make_ctx():
    return SimpleNamespace(lifespan_context={"ableton": _MinimalAbleton()})


# ── preview_semantic_move ─────────────────────────────────────────────────────


class TestPreviewSemanticMoveArgs:
    def test_preview_threads_args_into_kernel_as_seed_args(self):
        from mcp_server.semantic_moves.tools import preview_semantic_move
        ctx = _make_ctx()
        preview_semantic_move(
            ctx,
            move_id=_PROBE_ID,
            args={"return_track_index": 0, "device_chain": ["Echo"]},
        )
        assert _CAPTURED_KERNELS, "compiler was never called"
        kernel = _CAPTURED_KERNELS[-1]
        assert kernel.get("seed_args") == {
            "return_track_index": 0,
            "device_chain": ["Echo"],
        }

    def test_preview_without_args_is_backward_compatible(self):
        from mcp_server.semantic_moves.tools import preview_semantic_move
        ctx = _make_ctx()
        preview_semantic_move(ctx, move_id=_PROBE_ID)
        assert _CAPTURED_KERNELS, "compiler was never called"
        # Either missing entirely or empty-dict — both fine. Critical is that
        # pre-v1.20 callers (no args kwarg) don't error.
        kernel = _CAPTURED_KERNELS[-1]
        assert kernel.get("seed_args", {}) == {}

    def test_preview_with_empty_args_dict_same_as_omitted(self):
        from mcp_server.semantic_moves.tools import preview_semantic_move
        ctx = _make_ctx()
        preview_semantic_move(ctx, move_id=_PROBE_ID, args={})
        kernel = _CAPTURED_KERNELS[-1]
        assert kernel.get("seed_args", {}) == {}


# ── apply_semantic_move ────────────────────────────────────────────────────────


class TestApplySemanticMoveArgs:
    def test_apply_threads_args_in_improve_mode(self):
        from mcp_server.semantic_moves.tools import apply_semantic_move
        ctx = _make_ctx()
        result = asyncio.run(apply_semantic_move(
            ctx,
            move_id=_PROBE_ID,
            mode="improve",
            args={"track_index": 2, "volume": 0.6},
        ))
        assert _CAPTURED_KERNELS, "compiler was never called"
        kernel = _CAPTURED_KERNELS[-1]
        assert kernel["seed_args"] == {"track_index": 2, "volume": 0.6}
        # improve mode: compile only, don't execute
        assert result.get("executed") is False

    def test_apply_without_args_is_backward_compatible(self):
        from mcp_server.semantic_moves.tools import apply_semantic_move
        ctx = _make_ctx()
        asyncio.run(apply_semantic_move(
            ctx,
            move_id=_PROBE_ID,
            mode="improve",
        ))
        assert _CAPTURED_KERNELS
        kernel = _CAPTURED_KERNELS[-1]
        assert kernel.get("seed_args", {}) == {}

    def test_apply_threads_args_in_observe_mode(self):
        """observe mode is the safest way an agent audits args → plan shape."""
        from mcp_server.semantic_moves.tools import apply_semantic_move
        ctx = _make_ctx()
        asyncio.run(apply_semantic_move(
            ctx,
            move_id=_PROBE_ID,
            mode="observe",
            args={"sentinel": "observed"},
        ))
        kernel = _CAPTURED_KERNELS[-1]
        assert kernel["seed_args"] == {"sentinel": "observed"}

    def test_apply_unknown_move_still_errors_even_with_args(self):
        from mcp_server.semantic_moves.tools import apply_semantic_move
        ctx = _make_ctx()
        result = asyncio.run(apply_semantic_move(
            ctx,
            move_id="nonexistent_xyz",
            mode="improve",
            args={"anything": 1},
        ))
        assert "error" in result
