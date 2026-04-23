"""PR-A truth-gap regressions for Preview Studio.

Two compounding lies we're locking shut:

1. ``compare_variants`` used to score every variant without filtering for
   ``status == "blocked"`` or missing ``compiled_plan``. A blocked /
   analytical-only variant could win the recommendation.
2. ``commit_preview_variant`` flipped ``preview_set.status = "committed"``
   BEFORE checking whether the chosen variant has a ``compiled_plan``. An
   analytical-only choice therefore got recorded as committed, sibling
   variants were discarded, and the Wonder lifecycle advanced to
   ``resolved`` — all while nothing actually executed.

Each test asserts on the fix directly, with enough fixture context that
the failure mode is obvious if the code regresses.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.preview_studio.engine import (
    compare_variants,
    get_preview_set,
    store_preview_set,
)
from mcp_server.preview_studio.models import PreviewSet, PreviewVariant


# ── Helpers ──────────────────────────────────────────────────────


def _make_set(
    set_id: str,
    variants: list[PreviewVariant],
    *,
    request_text: str = "truth-gap repro",
    strategy: str = "creative_triptych",
    source_kernel_id: str = "k",
) -> PreviewSet:
    """Build and register a preview set with a caller-supplied variant list."""
    ps = PreviewSet(
        set_id=set_id,
        request_text=request_text,
        strategy=strategy,
        source_kernel_id=source_kernel_id,
        variants=variants,
        created_at_ms=int(time.time() * 1000),
    )
    store_preview_set(ps)
    return ps


def _blocked_variant(variant_id: str = "v_blocked") -> PreviewVariant:
    return PreviewVariant(
        variant_id=variant_id,
        label="unexpected",
        intent="analytical-only option",
        novelty_level=0.8,
        identity_effect="contrasts",
        compiled_plan=None,
        status="blocked",
        taste_fit=0.95,  # high taste fit so it would win on score alone
        what_preserved="identity intact",
        why_it_matters="if not filtered, score ranks it first",
    )


def _executable_variant(
    variant_id: str = "v_exec",
    *,
    move_id: str = "make_punchier",
    label: str = "strong",
    compiled_plan: list | dict | None = None,
) -> PreviewVariant:
    plan = compiled_plan if compiled_plan is not None else [
        {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.5}},
    ]
    return PreviewVariant(
        variant_id=variant_id,
        label=label,
        intent="executable plan",
        novelty_level=0.5,
        identity_effect="evolves",
        move_id=move_id,
        compiled_plan=plan,
        status="pending",
        taste_fit=0.55,
        what_preserved="core hook",
        why_it_matters="low-risk evolution",
    )


# ── Task A1: blocked variant cannot be recommended ──────────────


def test_blocked_variant_cannot_be_recommended():
    """A blocked/analytical-only variant must never be the ``recommended`` pick.

    The blocked variant here is given a HIGHER taste_fit than the executable
    one on purpose — the old scorer would rank it first. Post-fix, it's
    filtered out of the ranking entirely.
    """
    blocked = _blocked_variant()
    executable = _executable_variant()

    ps = _make_set("ps_truthgap_a1", [blocked, executable])

    result = compare_variants(ps)

    # Shape assertions (v2 plan: recommended stays a bare string).
    assert isinstance(result["recommended"], str), (
        f"recommended must be a bare variant_id string, got {type(result['recommended']).__name__}"
    )

    # Behavioral assertions.
    assert result["recommended"] == executable.variant_id, (
        f"executable variant must win; recommended={result['recommended']!r}, "
        f"expected={executable.variant_id!r}"
    )
    assert result["analytical_candidates"] == [blocked.variant_id], (
        f"blocked variant should be surfaced as analytical_candidates only; "
        f"got {result.get('analytical_candidates')!r}"
    )

    # Introspection: rankings still contains BOTH for debugging, but the
    # blocked one does not appear in the scored/sorted slot at position 0.
    ranked_ids = [r["variant_id"] for r in result["rankings"]]
    assert blocked.variant_id in ranked_ids, (
        "blocked variant should still be listed in rankings for introspection"
    )
    assert executable.variant_id in ranked_ids
    # Rankings are sorted by score with blocked variants dropped to the
    # bottom; the top slot must be the executable.
    assert result["rankings"][0]["variant_id"] == executable.variant_id


def test_recommended_is_none_when_no_executable_variants():
    """If every variant is blocked/analytical, ``recommended`` is None.

    Callers can then show a clear 'no executable option' message instead of
    silently committing a variant that will do nothing.
    """
    ps = _make_set(
        "ps_truthgap_a1_all_blocked",
        [
            _blocked_variant("v_b1"),
            _blocked_variant("v_b2"),
        ],
    )

    result = compare_variants(ps)

    assert result["recommended"] is None, (
        f"recommended must be None when no executable variants exist; "
        f"got {result['recommended']!r}"
    )
    assert set(result["analytical_candidates"]) == {"v_b1", "v_b2"}


# ── Task A2: commit on analytical variant does not flip state ────


def test_commit_analytical_variant_does_not_flip_state():
    """commit_preview_variant on an analytical variant must be a true no-op:

    * Response reports ``committed == False`` with ``reason == "analytical_only"``.
    * The preview_set is left in its pre-commit state (status unchanged,
      all variants still present, no variant flipped to discarded).
    * No Ableton command runs.
    """
    from mcp_server.preview_studio.tools import commit_preview_variant

    analytical = PreviewVariant(
        variant_id="v_truth_a2_analytical",
        label="unexpected",
        intent="analytical",
        compiled_plan=None,
        identity_effect="contrasts",
        status="blocked",
    )
    executable = _executable_variant("v_truth_a2_exec")

    ps = _make_set("ps_truthgap_a2", [analytical, executable])
    assert ps.status != "committed"

    class _Ableton:
        def send_command(self, cmd, params=None):  # pragma: no cover - must not be called
            raise AssertionError(
                f"commit must not call Ableton for analytical variant; "
                f"got cmd={cmd!r}"
            )

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton()})

    result = asyncio.run(
        commit_preview_variant(
            ctx,
            set_id="ps_truthgap_a2",
            variant_id="v_truth_a2_analytical",
        )
    )

    # Response honesty
    assert result["committed"] is False, result
    assert result.get("reason") == "analytical_only", (
        f"expected reason='analytical_only'; got {result!r}"
    )

    # State honesty — nothing was flipped
    ps_after = get_preview_set("ps_truthgap_a2")
    assert ps_after is not None
    assert ps_after.status != "committed", (
        f"preview_set.status must not be 'committed' after an analytical "
        f"commit; got {ps_after.status!r}"
    )
    assert ps_after.committed_variant_id == "", (
        f"committed_variant_id must be empty; got {ps_after.committed_variant_id!r}"
    )

    # Sibling variants untouched
    labels_by_id = {v.variant_id: v.status for v in ps_after.variants}
    assert labels_by_id["v_truth_a2_analytical"] != "committed"
    assert labels_by_id["v_truth_a2_exec"] != "discarded", (
        f"executable sibling must not be discarded on analytical commit; "
        f"got {labels_by_id}"
    )


# ── Task A3: Wonder lifecycle must not advance on analytical commit


def test_wonder_lifecycle_not_advanced_on_analytical_commit():
    """If the user commits an analytical variant, the linked WonderSession
    stays unresolved so the user can pick another variant.
    """
    from mcp_server.preview_studio.tools import commit_preview_variant
    from mcp_server.wonder_mode.session import (
        WonderSession,
        store_wonder_session,
        get_wonder_session,
    )

    set_id = "ps_truthgap_a3"

    analytical = PreviewVariant(
        variant_id="v_truth_a3_analytical",
        label="unexpected",
        intent="analytical",
        compiled_plan=None,
        identity_effect="contrasts",
        status="blocked",
    )
    executable = _executable_variant("v_truth_a3_exec")
    _make_set(set_id, [analytical, executable])

    ws = WonderSession(
        session_id="ws_truthgap_a3",
        request_text="wonder-linked repro",
        preview_set_id=set_id,
        status="previewing",
        variants=[
            {"variant_id": "v_truth_a3_analytical", "family": "rescue"},
            {"variant_id": "v_truth_a3_exec", "family": "evolve"},
        ],
    )
    store_wonder_session(ws)

    class _Ableton:
        def send_command(self, cmd, params=None):  # pragma: no cover
            raise AssertionError("analytical commit must not touch Ableton")

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton()})

    asyncio.run(
        commit_preview_variant(
            ctx,
            set_id=set_id,
            variant_id="v_truth_a3_analytical",
        )
    )

    ws_after = get_wonder_session("ws_truthgap_a3")
    assert ws_after is not None
    assert ws_after.status != "resolved", (
        f"Wonder lifecycle must not advance to 'resolved' on analytical "
        f"commit; got status={ws_after.status!r}"
    )
    assert ws_after.outcome != "committed", (
        f"Wonder outcome must not be 'committed' for analytical-only pick; "
        f"got outcome={ws_after.outcome!r}"
    )


# ── Task A4: auditor's end-to-end repro ─────────────────────────


def test_auditor_repro_blocked_variant_wins_bug(monkeypatch):
    """End-to-end auditor repro: 1 blocked variant + 1 executable.

    On pre-fix main, compare_variants would recommend the blocked variant
    (higher taste_fit), and commit would mark preview_set.status='committed'
    while applying nothing. Post-fix, the recommendation is the executable
    variant, commit actually runs its compiled plan, and the preview set is
    left in the correct ``committed`` state with execution evidence.
    """
    import mcp_server.runtime.execution_router as execution_router
    from mcp_server.preview_studio.tools import commit_preview_variant

    set_id = "ps_truthgap_a4"

    blocked = _blocked_variant("v_truth_a4_blocked")
    executable = _executable_variant(
        "v_truth_a4_exec",
        compiled_plan=[
            {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.5}},
            {"tool": "set_track_pan", "params": {"track_index": 0, "pan": 0.3}},
        ],
    )
    ps = _make_set(set_id, [blocked, executable])

    # Step 1: compare picks the executable, not the blocked one.
    comparison = compare_variants(ps)
    assert comparison["recommended"] == executable.variant_id, (
        f"auditor scenario: recommended must be the executable variant; "
        f"got {comparison['recommended']!r}"
    )
    assert comparison["analytical_candidates"] == [blocked.variant_id]

    # Step 2: commit the recommended variant; it actually executes.
    executed_tools: list[str] = []

    async def _fake_exec_async(
        steps,
        ableton=None,
        bridge=None,
        mcp_registry=None,
        ctx=None,
        stop_on_failure=True,
    ):
        for step in steps:
            executed_tools.append(step.get("tool"))
        return [
            SimpleNamespace(
                ok=True,
                tool=step.get("tool"),
                backend="remote_command",
                result={"ok": True},
                error="",
            )
            for step in steps
        ]

    monkeypatch.setattr(execution_router, "execute_plan_steps_async", _fake_exec_async)

    class _Ableton:
        def send_command(self, cmd, params=None):
            return {"ok": True}

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton()})
    result = asyncio.run(
        commit_preview_variant(
            ctx,
            set_id=set_id,
            variant_id=comparison["recommended"],
        )
    )

    # Commit actually ran the plan.
    assert executed_tools == ["set_track_volume", "set_track_pan"], (
        f"auditor scenario: commit must run the executable variant's plan; "
        f"got {executed_tools!r}"
    )
    assert result["committed"] is True
    assert result["status"] == "committed"
    assert result["steps_ok"] == 2
    assert result["steps_failed"] == 0

    # Step 3: preview_set is now legitimately committed to the executable.
    ps_after = get_preview_set(set_id)
    assert ps_after is not None
    assert ps_after.status == "committed"
    assert ps_after.committed_variant_id == executable.variant_id


# ── P1#2 truth-gap — executable variant whose plan fails at apply time ──
#
# Prior behavior: commit_preview_variant called engine.commit_variant()
# BEFORE execute_plan_steps_async ran. If every execution step then
# failed, the returned payload correctly said status="failed" /
# committed=False, but:
#   • preview_set.status was already "committed"
#   • preview_set.committed_variant_id was already set
#   • Wonder lifecycle was advanced to "resolved" / "committed"
# So the response said failure while the stored state said success.


def test_executable_variant_all_steps_fail_leaves_preview_set_uncommitted(monkeypatch):
    """If every step of an executable variant's plan fails, the preview set
    must NOT be flipped to status='committed'. The response already says
    committed=False / status='failed'; the stored state must agree.
    """
    import mcp_server.runtime.execution_router as execution_router
    from mcp_server.preview_studio.tools import commit_preview_variant

    set_id = "ps_truthgap_p1_2_allfail"

    exec_1 = _executable_variant(
        "v_exec_1",
        compiled_plan=[
            {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.5}},
            {"tool": "set_track_pan", "params": {"track_index": 0, "pan": 0.3}},
        ],
    )
    exec_2 = _executable_variant("v_exec_2")
    ps = _make_set(set_id, [exec_1, exec_2])
    original_status = ps.status

    async def _fake_exec_all_fail(
        steps, ableton=None, bridge=None, mcp_registry=None,
        ctx=None, stop_on_failure=True,
    ):
        # Every step returns ok=False — reproduces "plan runs, all steps fail"
        return [
            SimpleNamespace(
                ok=False,
                tool=step.get("tool"),
                backend="remote_command",
                result=None,
                error="simulated tool failure",
            )
            for step in steps
        ]

    monkeypatch.setattr(execution_router, "execute_plan_steps_async", _fake_exec_all_fail)

    class _Ableton:
        def send_command(self, cmd, params=None):
            return {"ok": True}

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton()})
    result = asyncio.run(
        commit_preview_variant(ctx, set_id=set_id, variant_id="v_exec_1")
    )

    # Response honesty — already correct pre-fix
    assert result["committed"] is False, result
    assert result["status"] == "failed"
    assert result["steps_ok"] == 0
    assert result["steps_failed"] == 2

    # State honesty — THIS is what the P1#2 fix enforces
    ps_after = get_preview_set(set_id)
    assert ps_after is not None
    assert ps_after.status != "committed", (
        f"preview_set.status must not be 'committed' when every step failed; "
        f"got {ps_after.status!r}"
    )
    assert ps_after.committed_variant_id == "", (
        f"committed_variant_id must be empty on failed commit; "
        f"got {ps_after.committed_variant_id!r}"
    )
    # Sibling must not be discarded either — the commit didn't happen
    labels_by_id = {v.variant_id: v.status for v in ps_after.variants}
    assert labels_by_id["v_exec_2"] != "discarded", (
        f"sibling variant must not be discarded on failed commit; "
        f"got {labels_by_id}"
    )


def test_executable_variant_all_steps_fail_does_not_advance_wonder_lifecycle(monkeypatch):
    """Companion to above: WonderSession must NOT be marked resolved when
    the committed variant's plan entirely failed.
    """
    import mcp_server.runtime.execution_router as execution_router
    from mcp_server.preview_studio.tools import commit_preview_variant
    from mcp_server.wonder_mode.session import (
        WonderSession,
        store_wonder_session,
        get_wonder_session,
    )

    set_id = "ps_truthgap_p1_2_wonder_allfail"

    exec_1 = _executable_variant("v_p12_wonder_exec")
    _make_set(set_id, [exec_1])

    ws = WonderSession(
        session_id="ws_truthgap_p1_2",
        request_text="wonder-linked failure repro",
        preview_set_id=set_id,
        status="previewing",
        variants=[{"variant_id": "v_p12_wonder_exec", "family": "evolve"}],
    )
    store_wonder_session(ws)

    async def _fake_exec_all_fail(
        steps, ableton=None, bridge=None, mcp_registry=None,
        ctx=None, stop_on_failure=True,
    ):
        return [
            SimpleNamespace(
                ok=False,
                tool=step.get("tool"),
                backend="remote_command",
                result=None,
                error="simulated failure",
            )
            for step in steps
        ]

    monkeypatch.setattr(execution_router, "execute_plan_steps_async", _fake_exec_all_fail)

    class _Ableton:
        def send_command(self, cmd, params=None):
            return {"ok": True}

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton()})
    asyncio.run(
        commit_preview_variant(ctx, set_id=set_id, variant_id="v_p12_wonder_exec")
    )

    ws_after = get_wonder_session("ws_truthgap_p1_2")
    assert ws_after is not None
    assert ws_after.status != "resolved", (
        f"Wonder lifecycle must not advance to 'resolved' when every step "
        f"failed; got status={ws_after.status!r}"
    )
    assert ws_after.outcome != "committed", (
        f"Wonder outcome must not be 'committed' for zero-step-success pick; "
        f"got outcome={ws_after.outcome!r}"
    )


def test_executable_variant_partial_success_commits_honestly(monkeypatch):
    """Partial success (some steps ok, some fail) IS a legitimate commit —
    state should reflect 'committed_with_errors'. Wonder advances to
    resolved because something actually applied.
    """
    import mcp_server.runtime.execution_router as execution_router
    from mcp_server.preview_studio.tools import commit_preview_variant

    set_id = "ps_truthgap_p1_2_partial"

    exec_1 = _executable_variant(
        "v_p12_partial",
        compiled_plan=[
            {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.5}},
            {"tool": "set_track_pan", "params": {"track_index": 0, "pan": 0.3}},
        ],
    )
    _make_set(set_id, [exec_1])

    async def _fake_exec_partial(
        steps, ableton=None, bridge=None, mcp_registry=None,
        ctx=None, stop_on_failure=True,
    ):
        # First step succeeds, second fails.
        outcomes = [True, False]
        return [
            SimpleNamespace(
                ok=ok,
                tool=step.get("tool"),
                backend="remote_command",
                result={"ok": True} if ok else None,
                error="" if ok else "simulated partial failure",
            )
            for step, ok in zip(steps, outcomes)
        ]

    monkeypatch.setattr(execution_router, "execute_plan_steps_async", _fake_exec_partial)

    class _Ableton:
        def send_command(self, cmd, params=None):
            return {"ok": True}

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton()})
    result = asyncio.run(
        commit_preview_variant(ctx, set_id=set_id, variant_id="v_p12_partial")
    )

    assert result["status"] == "committed_with_errors"
    assert result["steps_ok"] == 1
    assert result["steps_failed"] == 1

    # Partial success IS a commit — state agrees
    ps_after = get_preview_set(set_id)
    assert ps_after is not None
    assert ps_after.status == "committed"
    assert ps_after.committed_variant_id == "v_p12_partial"
