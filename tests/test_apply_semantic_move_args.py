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
            # remote_command so the minimal _MinimalAbleton.send_command
            # mock handles it without needing a real mcp_dispatch registry.
            backend="remote_command",
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


# ── Ledger write contract (v1.20) ─────────────────────────────────────────────
#
# v1.20's director SKILL promises apply_semantic_move populates the action
# ledger automatically in explore mode. This suite enforces that — caller
# should see get_last_move() return a non-empty entry after an explore-mode
# apply, WITHOUT having to call add_session_memory themselves.


class TestApplySemanticMoveLedgerWrite:
    def test_explore_mode_populates_action_ledger(self):
        """After apply_semantic_move in explore mode, get_last_move() must
        return the entry. v1.20 director SKILL relies on this for
        anti-repetition recency detection."""
        from mcp_server.semantic_moves.tools import apply_semantic_move
        from mcp_server.runtime.action_ledger import SessionLedger

        ctx = _make_ctx()
        result = asyncio.run(apply_semantic_move(
            ctx,
            move_id=_PROBE_ID,
            mode="explore",
            args={"track_index": 0, "something": "value"},
        ))
        assert result.get("executed") is True, result

        ledger: SessionLedger = ctx.lifespan_context["action_ledger"]
        last = ledger.get_last_move()
        assert last is not None, "ledger should contain the just-applied move"
        assert last.engine == "semantic_moves"
        assert last.move_class == "mix", f"expected family mix, got {last.move_class}"
        assert _PROBE_ID in last.intent, (
            f"expected move_id {_PROBE_ID} in intent, got {last.intent!r}"
        )

    def test_explore_mode_ledger_records_each_successful_step(self):
        from mcp_server.semantic_moves.tools import apply_semantic_move
        ctx = _make_ctx()
        asyncio.run(apply_semantic_move(
            ctx,
            move_id=_PROBE_ID,
            mode="explore",
            args={"x": 1},
        ))
        ledger = ctx.lifespan_context["action_ledger"]
        last = ledger.get_last_move()
        assert len(last.actions) >= 1

    def test_explore_mode_sets_kept_and_score_provisionally(self):
        from mcp_server.semantic_moves.tools import apply_semantic_move
        ctx = _make_ctx()
        asyncio.run(apply_semantic_move(
            ctx,
            move_id=_PROBE_ID,
            mode="explore",
            args={"x": 1},
        ))
        ledger = ctx.lifespan_context["action_ledger"]
        last = ledger.get_last_move()
        assert last.kept is True
        assert 0.0 <= last.score <= 1.0

    def test_explore_mode_returns_ledger_entry_id_in_response(self):
        """Callers can correlate the MCP response with the ledger entry
        for post-hoc evaluation via the returned ledger_entry_id."""
        from mcp_server.semantic_moves.tools import apply_semantic_move
        ctx = _make_ctx()
        result = asyncio.run(apply_semantic_move(
            ctx,
            move_id=_PROBE_ID,
            mode="explore",
            args={"x": 1},
        ))
        assert "ledger_entry_id" in result
        ledger = ctx.lifespan_context["action_ledger"]
        assert ledger.get_entry(result["ledger_entry_id"]) is not None

    def test_improve_mode_does_NOT_write_to_ledger(self):
        """improve mode compiles without executing — no ledger entry should
        be written, otherwise anti-repetition would see 'moves' the user
        never approved."""
        from mcp_server.semantic_moves.tools import apply_semantic_move
        from mcp_server.runtime.action_ledger import SessionLedger
        ctx = _make_ctx()
        asyncio.run(apply_semantic_move(
            ctx,
            move_id=_PROBE_ID,
            mode="improve",
            args={"x": 1},
        ))
        ledger = ctx.lifespan_context.get("action_ledger") or SessionLedger()
        assert ledger.get_last_move() is None

    def test_observe_mode_does_NOT_write_to_ledger(self):
        from mcp_server.semantic_moves.tools import apply_semantic_move
        from mcp_server.runtime.action_ledger import SessionLedger
        ctx = _make_ctx()
        asyncio.run(apply_semantic_move(
            ctx,
            move_id=_PROBE_ID,
            mode="observe",
            args={"x": 1},
        ))
        ledger = ctx.lifespan_context.get("action_ledger") or SessionLedger()
        assert ledger.get_last_move() is None
