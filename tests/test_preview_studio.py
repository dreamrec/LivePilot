"""Unit tests for Preview Studio engine — pure computation, no Ableton needed."""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.m4l_bridge import SpectralCache
from mcp_server.preview_studio.engine import (
    commit_variant,
    compare_variants,
    create_preview_set,
    discard_set,
    get_preview_set,
)


# ── Triptych creation ────────────────────────────────────────────


def test_triptych_creates_three_variants():
    """Creative triptych should produce exactly 3 variants."""
    ps = create_preview_set(
        request_text="make this more magical",
        kernel_id="test_kern",
        strategy="creative_triptych",
    )
    assert len(ps.variants) == 3


def test_triptych_labels():
    """Variants should be labeled safe, strong, unexpected."""
    ps = create_preview_set(
        request_text="add energy",
        kernel_id="test_kern",
    )
    labels = {v.label for v in ps.variants}
    assert labels == {"safe", "strong", "unexpected"}


def test_triptych_novelty_ordering():
    """Safe should be lowest novelty, unexpected highest."""
    ps = create_preview_set(
        request_text="improve the chorus",
        kernel_id="test_kern",
    )
    by_label = {v.label: v for v in ps.variants}
    assert by_label["safe"].novelty_level < by_label["strong"].novelty_level
    assert by_label["strong"].novelty_level < by_label["unexpected"].novelty_level


def test_triptych_identity_effects():
    """Each variant should have different identity effects."""
    ps = create_preview_set(
        request_text="test",
        kernel_id="test_kern",
    )
    effects = {v.identity_effect for v in ps.variants}
    assert "preserves" in effects
    assert "evolves" in effects
    assert "contrasts" in effects


# ── Binary strategy ──────────────────────────────────────────────


def test_binary_creates_two_variants():
    """Binary strategy should produce exactly 2 variants."""
    ps = create_preview_set(
        request_text="test binary",
        kernel_id="test_kern",
        strategy="binary",
    )
    assert len(ps.variants) == 2


# ── Comparison ───────────────────────────────────────────────────


def test_comparison_ranks_preserves_highest():
    """With default identity weight, preserves should rank highest."""
    ps = create_preview_set(
        request_text="test ranking",
        kernel_id="test_kern",
    )
    comparison = compare_variants(ps)
    rankings = comparison["rankings"]
    assert len(rankings) == 3
    # First should be the one with highest score
    assert rankings[0]["score"] >= rankings[-1]["score"]


def test_comparison_returns_recommended():
    """Comparison should include a recommended variant."""
    ps = create_preview_set(
        request_text="test recommend",
        kernel_id="test_kern",
    )
    comparison = compare_variants(ps)
    assert comparison.get("recommended")


def test_comparison_with_custom_weights():
    """Custom weights should change ranking."""
    ps = create_preview_set(
        request_text="test weights",
        kernel_id="test_kern",
    )
    # Strongly favor novelty
    comparison = compare_variants(ps, {
        "taste_weight": 0.1,
        "novelty_weight": 0.8,
        "identity_weight": 0.1,
    })
    rankings = comparison["rankings"]
    assert len(rankings) == 3


# ── Commit and discard ───────────────────────────────────────────


def test_commit_marks_chosen():
    """Committing should mark the chosen variant and discard others."""
    ps = create_preview_set(
        request_text="test commit",
        kernel_id="test_kern",
    )
    chosen_id = ps.variants[1].variant_id
    result = commit_variant(ps, chosen_id)

    assert result is not None
    assert result.status == "committed"

    # Others should be discarded
    for v in ps.variants:
        if v.variant_id != chosen_id:
            assert v.status == "discarded"

    assert ps.status == "committed"
    assert ps.committed_variant_id == chosen_id


def test_commit_unknown_variant():
    """Committing an unknown variant should return None."""
    ps = create_preview_set(
        request_text="test bad commit",
        kernel_id="test_kern",
    )
    result = commit_variant(ps, "nonexistent_id")
    assert result is None


def test_discard_removes_from_store():
    """Discarding should remove the set from the store."""
    ps = create_preview_set(
        request_text="test discard",
        kernel_id="test_kern_discard",
    )
    set_id = ps.set_id
    assert get_preview_set(set_id) is not None

    result = discard_set(set_id)
    assert result is True
    assert get_preview_set(set_id) is None


def test_discard_unknown_set():
    """Discarding an unknown set should return False."""
    result = discard_set("nonexistent_set_id")
    assert result is False


# ── Song brain integration ───────────────────────────────────────


def test_variants_include_preservation_notes():
    """Variants should include what_preserved text."""
    ps = create_preview_set(
        request_text="test preservation",
        kernel_id="test_kern",
        song_brain={"sacred_elements": [{"description": "Main hook melody"}]},
    )
    for v in ps.variants:
        assert v.what_preserved  # Should be non-empty
        assert "hook" in v.what_preserved.lower() or "element" in v.what_preserved.lower()


def test_set_id_deterministic():
    """Same request + kernel should produce same set_id."""
    ps1 = create_preview_set(
        request_text="deterministic test",
        kernel_id="kern_fixed",
    )
    ps2 = create_preview_set(
        request_text="deterministic test",
        kernel_id="kern_fixed",
    )
    assert ps1.set_id == ps2.set_id


# ── Wonder-awareness ─────────────────────────────────────────────


def test_analytical_refusal_in_wonder_context():
    """Wonder-linked analytical variant should be refused by render."""
    from mcp_server.preview_studio.tools import _should_refuse_analytical
    assert _should_refuse_analytical(compiled_plan=None, wonder_linked=True) is True
    assert _should_refuse_analytical(compiled_plan=None, wonder_linked=False) is False
    assert _should_refuse_analytical(compiled_plan=[{"tool": "x"}], wonder_linked=True) is False
    assert _should_refuse_analytical(compiled_plan=[{"tool": "x"}], wonder_linked=False) is False


def test_render_variant_uses_lifespan_spectral_cache_for_audible_preview(monkeypatch):
    """Audible preview should use the shared spectral cache from lifespan_context."""
    import asyncio
    from mcp_server.preview_studio.tools import render_preview_variant
    import mcp_server.runtime.execution_router as execution_router

    ps = create_preview_set(
        request_text="test render",
        kernel_id="test_kern_render",
        available_moves=[{"move_id": "make_punchier", "plan_template": [{"tool": "set_track_volume", "params": {}}]}],
    )
    variant_id = ps.variants[0].variant_id

    class _Ableton:
        def __init__(self):
            self.calls = []

        def send_command(self, cmd, params=None):
            self.calls.append(cmd)
            if cmd == "get_session_info":
                return {"tempo": 120, "track_count": 4}
            return {"ok": True}

    cache = SpectralCache()
    cache.update("spectrum", {"sub": 0.1})

    async def _fake_exec_async(steps, ableton=None, bridge=None, mcp_registry=None, ctx=None, stop_on_failure=True):
        return [SimpleNamespace(
            ok=True, tool="set_track_volume",
            backend="remote_command", result={"ok": True}, error="",
        )]

    monkeypatch.setattr(execution_router, "execute_plan_steps_async", _fake_exec_async)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton(), "spectral": cache})
    result = asyncio.run(render_preview_variant(ctx, set_id=ps.set_id, variant_id=variant_id, bars=2))

    assert result["preview_mode"] == "audible_preview"


def test_render_preview_variant_captures_audible_before_undo(monkeypatch):
    """Regression: audible capture must happen while the variant is applied.

    Previously the finally block ran undo before the audible capture section,
    so "audible_preview" was a lie — it captured pre-variant audio and labeled
    it as the variant's sound. This test asserts ordering via a call log.
    """
    import asyncio
    from mcp_server.preview_studio.tools import render_preview_variant
    from mcp_server.preview_studio.engine import create_preview_set
    import mcp_server.runtime.execution_router as execution_router

    ps = create_preview_set(
        request_text="ordering test",
        kernel_id="test_kern_order",
        available_moves=[{"move_id": "make_punchier", "plan_template": [{"tool": "set_track_volume", "params": {}}]}],
    )
    variant_id = ps.variants[0].variant_id

    calls = []

    class _Ableton:
        def send_command(self, cmd, params=None):
            calls.append(cmd)
            if cmd == "get_session_info":
                return {"tempo": 120, "track_count": 4}
            return {"ok": True}

    class _Spectral(SpectralCache):
        def get_all(self):
            calls.append("spectral_snapshot")
            return super().get_all()

    cache = _Spectral()
    cache.update("spectrum", {"sub": 0.1})

    async def _fake_exec_async(steps, ableton=None, bridge=None, mcp_registry=None, ctx=None, stop_on_failure=True):
        calls.append("apply_plan")
        return [SimpleNamespace(
            ok=True, tool="set_track_volume",
            backend="remote_command", result={"ok": True}, error="",
        )]

    monkeypatch.setattr(execution_router, "execute_plan_steps_async", _fake_exec_async)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton(), "spectral": cache})
    result = asyncio.run(render_preview_variant(ctx, set_id=ps.set_id, variant_id=variant_id, bars=2))

    assert result["preview_mode"] == "audible_preview"

    # Ordering: apply must precede spectral snapshots; snapshots + start_playback
    # must precede undo.
    assert "apply_plan" in calls
    assert "start_playback" in calls
    assert "undo" in calls, "undo should eventually run in cleanup"

    apply_idx = calls.index("apply_plan")
    undo_idx = calls.index("undo")
    play_idx = calls.index("start_playback")
    snapshot_indices = [i for i, c in enumerate(calls) if c == "spectral_snapshot"]

    assert apply_idx < play_idx < undo_idx, f"Apply before play before undo required; got {calls}"
    for si in snapshot_indices:
        assert si < undo_idx, f"Spectral snapshot at {si} must precede undo at {undo_idx}; got {calls}"

    # There should be exactly one spectral_comparison in the result (before + after)
    assert "spectral_comparison" in result


# ── v1.10.3 Truth Release: commit_preview_variant actually executes ──

def test_commit_preview_variant_actually_executes_compiled_plan(monkeypatch):
    """v1.10.3: commit used to mark the variant as committed in memory and
    return committed=True without running anything. Users expected commit
    to apply the chosen variant. It now runs the compiled plan through the
    async router and reports per-step results.
    """
    import asyncio
    from mcp_server.preview_studio.tools import commit_preview_variant
    from mcp_server.preview_studio.engine import create_preview_set, store_preview_set
    from mcp_server.preview_studio.models import PreviewSet, PreviewVariant
    import mcp_server.runtime.execution_router as execution_router
    import time

    # Build a preview set containing a variant with a real compiled plan
    variant = PreviewVariant(
        variant_id="v_commit_test",
        label="safe",
        intent="test commit",
        compiled_plan=[
            {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.5}},
            {"tool": "set_track_pan", "params": {"track_index": 0, "pan": 0.3}},
        ],
        identity_effect="preserves",
        what_preserved="everything",
        move_id="test_move",
    )
    ps = PreviewSet(
        set_id="ps_commit_test",
        request_text="commit test",
        strategy="binary",
        source_kernel_id="k",
        variants=[variant],
        created_at_ms=int(time.time() * 1000),
    )
    store_preview_set(ps)

    executed_tools = []

    async def _fake_exec_async(steps, ableton=None, bridge=None, mcp_registry=None,
                                ctx=None, stop_on_failure=True):
        for s in steps:
            executed_tools.append(s.get("tool"))
        return [
            SimpleNamespace(
                ok=True, tool=s.get("tool"),
                backend="remote_command", result={"ok": True}, error="",
            )
            for s in steps
        ]

    monkeypatch.setattr(execution_router, "execute_plan_steps_async", _fake_exec_async)

    class _Ableton:
        def send_command(self, cmd, params=None):
            return {"ok": True}

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton()})
    result = asyncio.run(commit_preview_variant(
        ctx, set_id="ps_commit_test", variant_id="v_commit_test",
    ))

    # The compiled plan must have actually been executed
    assert executed_tools == ["set_track_volume", "set_track_pan"], \
        f"commit should have executed both plan steps; got {executed_tools}"

    # Response should reflect real execution
    assert result["committed"] is True
    assert result["status"] == "committed"
    assert result["steps_ok"] == 2
    assert result["steps_failed"] == 0
    assert "execution_log" in result
    assert len(result["execution_log"]) == 2


def test_commit_preview_variant_analytical_only_returns_honest_status(monkeypatch):
    """If the variant has no compiled_plan (analytical-only), commit must
    NOT pretend to apply anything — it returns status='analytical_only'
    with committed=False.
    """
    import asyncio
    from mcp_server.preview_studio.tools import commit_preview_variant
    from mcp_server.preview_studio.engine import store_preview_set
    from mcp_server.preview_studio.models import PreviewSet, PreviewVariant
    import time

    variant = PreviewVariant(
        variant_id="v_analytical",
        label="unexpected",
        intent="analytical",
        compiled_plan=None,  # analytical-only
        identity_effect="contrasts",
    )
    ps = PreviewSet(
        set_id="ps_analytical_test",
        request_text="analytical",
        strategy="binary",
        source_kernel_id="k",
        variants=[variant],
        created_at_ms=int(time.time() * 1000),
    )
    store_preview_set(ps)

    class _Ableton:
        def send_command(self, cmd, params=None):
            raise AssertionError("commit should NOT call any Ableton command for analytical variant")

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton()})
    result = asyncio.run(commit_preview_variant(
        ctx, set_id="ps_analytical_test", variant_id="v_analytical",
    ))

    assert result["committed"] is False
    assert result["status"] == "analytical_only"
    assert "note" in result
    # execution_log should not be present because nothing ran
    assert "execution_log" not in result


# ─── BUG-B44 / B45 regressions — variant description fields ────────────────


class TestBugB44B45VariantDescriptions:
    """BUG-B44: variants without a compiled_plan used to still be listed
    with status='pending' — committing them hit a missing-plan error.
    BUG-B45: variants had empty what_changed / summary, so users
    couldn't tell what each variant actually did."""

    def test_describe_variant_uses_move_intent(self):
        from mcp_server.preview_studio.engine import _describe_variant
        move = {"move_id": "make_punchier", "intent": "Tighten low end and boost punch"}
        compiled = {"move_id": "make_punchier", "steps": [
            {"description": "Read current levels"},
            {"description": "Apply compressor"},
        ]}
        profile = {"label": "strong", "novelty": 0.5}
        result = _describe_variant(move, compiled, profile)
        assert "Tighten" in result["what_changed"]
        assert result["summary"]

    def test_describe_variant_falls_back_to_plan_steps(self):
        """When the move has no intent/description, aggregate plan step
        descriptions into what_changed."""
        from mcp_server.preview_studio.engine import _describe_variant
        compiled = {"move_id": "x", "steps": [
            {"description": "Lower kick volume"},
            {"description": "Boost bass sub"},
        ]}
        profile = {"label": "safe", "novelty": 0.2}
        result = _describe_variant({}, compiled, profile)
        assert "Lower kick volume" in result["what_changed"]
        assert "Boost bass sub" in result["what_changed"]

    def test_describe_variant_final_fallback_when_no_plan(self):
        """No move, no plan — describe by profile so what_changed is
        never empty."""
        from mcp_server.preview_studio.engine import _describe_variant
        profile = {"label": "unexpected", "novelty": 0.8}
        result = _describe_variant(None, None, profile)
        assert result["what_changed"]
        assert "unexpected" in result["what_changed"].lower()

    def test_triptych_blocks_variants_without_compiled_plan(self):
        """BUG-B44: variants with compiled_plan=None should flip to
        status='blocked' so callers can skip commit attempts."""
        from mcp_server.preview_studio.engine import _build_triptych
        variants = _build_triptych(
            request_text="test",
            moves=[],  # no moves → all variants uncompilable
            song_brain={},
            taste_graph={},
            set_id="test_set",
            now=0,
            kernel=None,
        )
        assert len(variants) == 3
        for v in variants:
            assert v.compiled_plan is None
            assert v.status == "blocked", (
                f"BUG-B44 regressed — variant without plan still status="
                f"{v.status}"
            )
            assert v.what_changed  # no empty descriptions
