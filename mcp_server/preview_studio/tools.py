"""Preview Studio MCP tools — 5 tools for creative comparison.

  create_preview_set — generate safe/strong/unexpected variants
  compare_preview_variants — rank variants by taste + identity + impact
  commit_preview_variant — apply the chosen variant
  discard_preview_set — throw away all variants
  render_preview_variant — render a short preview via undo system
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp
from . import engine


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _should_refuse_analytical(compiled_plan, wonder_linked: bool) -> bool:
    """Check if an analytical variant should be refused in Wonder context."""
    if not wonder_linked:
        return False
    if compiled_plan is None:
        return True
    if isinstance(compiled_plan, dict):
        return len(compiled_plan.get("steps", [])) == 0
    if isinstance(compiled_plan, list):
        return len(compiled_plan) == 0
    return True


def _find_wonder_session_by_preview(set_id: str):
    """Find a WonderSession linked to this preview set."""
    try:
        from ..wonder_mode.session import find_session_by_preview_set
        return find_session_by_preview_set(set_id)
    except Exception:
        return None


@mcp.tool()
def create_preview_set(
    ctx: Context,
    request_text: str,
    kernel_id: str = "",
    strategy: str = "creative_triptych",
    wonder_session_id: str = "",
) -> dict:
    """Create a preview set with multiple creative options.

    Generates safe / strong / unexpected variants for comparison.
    Each variant includes what it changes, why it matters, and what
    it preserves from the song's identity.

    request_text: what the user wants (e.g., "make this more magical")
    kernel_id: optional session kernel reference
    strategy: "creative_triptych" (default) or "binary"
    wonder_session_id: optional — links to a WonderSession for lifecycle tracking

    Returns: preview set with variant summaries.
    """
    if not request_text.strip():
        return {"error": "request_text cannot be empty"}

    # Wonder-aware path: use variants from WonderSession
    if wonder_session_id:
        from ..wonder_mode.session import get_wonder_session
        ws = get_wonder_session(wonder_session_id)
        if not ws:
            return {"error": f"Wonder session {wonder_session_id} not found"}
        if not ws.variants:
            return {"error": f"Wonder session {wonder_session_id} has no variants"}

        from .models import PreviewVariant, PreviewSet
        import time

        # Filter to executable variants only
        exec_variants = [v for v in ws.variants if not v.get("analytical_only")]
        if not exec_variants:
            return {"error": "No executable variants in Wonder session — all are analytical-only"}

        now = int(time.time() * 1000)
        preview_variants = []
        for v in exec_variants:
            preview_variants.append(PreviewVariant(
                variant_id=v.get("variant_id", ""),
                label=v.get("label", ""),
                intent=v.get("intent", ""),
                novelty_level=v.get("novelty_level", 0.5),
                identity_effect=v.get("identity_effect", "preserves"),
                what_changed=v.get("what_changed", ""),
                what_preserved=v.get("what_preserved", ""),
                why_it_matters=v.get("why_it_matters", ""),
                move_id=v.get("move_id", ""),
                compiled_plan=v.get("compiled_plan"),
                taste_fit=v.get("taste_fit", 0.5),
                score=v.get("score", 0.0),
                summary=v.get("distinctness_reason", ""),
                created_at_ms=now,
            ))

        set_id = f"ps_wonder_{wonder_session_id[:12]}"
        ps = PreviewSet(
            set_id=set_id,
            request_text=request_text,
            strategy="wonder",
            source_kernel_id=kernel_id,
            variants=preview_variants,
            created_at_ms=now,
        )
        engine.store_preview_set(ps)

        # Update WonderSession
        ws.preview_set_id = set_id
        ws.transition_to("previewing")

        return ps.to_dict()

    # Get request-aware moves via propose_next_best_move logic
    # instead of arbitrary registry order
    available_moves = []
    try:
        from ..semantic_moves import registry
        from ..semantic_moves.tools import propose_next_best_move as _propose
        # Use the proposer's keyword+taste scoring to find relevant moves
        request_lower = request_text.lower()
        all_moves = list(registry._REGISTRY.values())
        scored = []
        for move in all_moves:
            score = 0.0
            move_words = set(move.move_id.replace("_", " ").split())
            intent_words = set(move.intent.lower().split())
            request_words = set(request_lower.split())
            overlap = request_words & (move_words | intent_words)
            score += len(overlap) * 0.3
            for dim in move.targets:
                if dim in request_lower:
                    score += 0.2
            if score > 0:
                scored.append((move.to_dict(), score))
        scored.sort(key=lambda x: -x[1])
        available_moves = [m for m, _ in scored[:3]]
        # Fallback: if no keyword match, take top 3 from full registry
        if not available_moves:
            available_moves = registry.list_moves()[:3]
    except Exception:
        pass

    # Get song brain if available
    song_brain: dict = {}
    try:
        from ..song_brain.tools import _current_brain
        if _current_brain is not None:
            song_brain = _current_brain.to_dict()
    except Exception as _e:
        if __debug__:
            import sys
            print(f"LivePilot: SongBrain unavailable in preview_studio: {_e}", file=sys.stderr)

    # Get taste graph — session + persistent stores
    taste_graph: dict = {}
    try:
        from ..memory.taste_graph import build_taste_graph
        from ..memory.taste_memory import TasteMemoryStore
        from ..memory.anti_memory import AntiMemoryStore
        from ..persistence.taste_store import PersistentTasteStore
        taste_store = ctx.lifespan_context.setdefault("taste_memory", TasteMemoryStore())
        anti_store = ctx.lifespan_context.setdefault("anti_memory", AntiMemoryStore())
        persistent = ctx.lifespan_context.setdefault("persistent_taste", PersistentTasteStore())
        graph = build_taste_graph(
            taste_store=taste_store, anti_store=anti_store,
            persistent_store=persistent,
        )
        taste_graph = graph.to_dict()
    except Exception:
        pass

    ps = engine.create_preview_set(
        request_text=request_text,
        kernel_id=kernel_id,
        strategy=strategy,
        available_moves=available_moves,
        song_brain=song_brain,
        taste_graph=taste_graph,
    )

    return ps.to_dict()


@mcp.tool()
def compare_preview_variants(
    ctx: Context,
    set_id: str,
    taste_weight: float = 0.3,
    novelty_weight: float = 0.2,
    identity_weight: float = 0.5,
) -> dict:
    """Compare and rank variants in a preview set.

    Rankings combine taste fit, novelty balance, and identity preservation.
    Returns ranked list with scores and a recommended pick.

    set_id: the preview set to compare
    taste_weight: how much to weight user taste fit (0-1)
    novelty_weight: how much to weight novelty balance (0-1)
    identity_weight: how much to weight identity preservation (0-1)
    """
    ps = engine.get_preview_set(set_id)
    if not ps:
        return {"error": f"Preview set {set_id} not found"}

    criteria = {
        "taste_weight": taste_weight,
        "novelty_weight": novelty_weight,
        "identity_weight": identity_weight,
    }

    comparison = engine.compare_variants(ps, criteria)
    return comparison


@mcp.tool()
def commit_preview_variant(
    ctx: Context,
    set_id: str,
    variant_id: str,
) -> dict:
    """Commit the chosen variant from a preview set.

    Marks the variant as committed and discards the others.
    The caller should then apply the variant's compiled plan.

    set_id: the preview set
    variant_id: the chosen variant to commit
    """
    ps = engine.get_preview_set(set_id)
    if not ps:
        return {"error": f"Preview set {set_id} not found"}

    chosen = engine.commit_variant(ps, variant_id)
    if not chosen:
        available = [v.variant_id for v in ps.variants]
        return {
            "error": f"Variant {variant_id} not found in set {set_id}",
            "available_variants": available,
        }

    result = {
        "committed": True,
        "variant_id": chosen.variant_id,
        "label": chosen.label,
        "intent": chosen.intent,
        "move_id": chosen.move_id,
        "identity_effect": chosen.identity_effect,
        "what_preserved": chosen.what_preserved,
    }

    # Wonder lifecycle hooks
    ws = _find_wonder_session_by_preview(set_id)
    if ws:
        ws.selected_variant_id = variant_id
        ws.outcome = "committed"
        ws.transition_to("resolved")

        # Record accepted turn resolution
        try:
            from ..session_continuity.tracker import record_turn_resolution, resolve_thread
            record_turn_resolution(
                request_text=ws.request_text,
                outcome="accepted",
                move_applied=chosen.move_id,
                identity_effect=chosen.identity_effect,
                user_sentiment="liked",
            )
            if ws.creative_thread_id:
                resolve_thread(ws.creative_thread_id)
        except Exception:
            pass

        # Update taste graph (with persistent backing)
        try:
            from ..memory.taste_graph import build_taste_graph
            from ..memory.taste_memory import TasteMemoryStore
            from ..memory.anti_memory import AntiMemoryStore
            from ..persistence.taste_store import PersistentTasteStore
            taste_store = ctx.lifespan_context.setdefault("taste_memory", TasteMemoryStore())
            anti_store = ctx.lifespan_context.setdefault("anti_memory", AntiMemoryStore())
            persistent = ctx.lifespan_context.setdefault("persistent_taste", PersistentTasteStore())
            graph = build_taste_graph(
                taste_store=taste_store, anti_store=anti_store,
                persistent_store=persistent,
            )
            # Look up family from WonderSession's variant list
            family = ""
            for v in ws.variants:
                if v.get("variant_id") == variant_id:
                    family = v.get("family", "")
                    break
            if chosen.move_id and family:
                graph.record_move_outcome(
                    move_id=chosen.move_id,
                    family=family,
                    kept=True,
                )
        except Exception:
            pass

        result["wonder_session_id"] = ws.session_id

    return result


@mcp.tool()
async def render_preview_variant(
    ctx: Context,
    set_id: str = "",
    variant_id: str = "",
    bars: int = 8,
) -> dict:
    """Render a short preview of a specific variant for evaluation.

    Captures a snapshot of what the variant would sound like if applied,
    without permanently changing the session. Uses Ableton's undo system
    to revert after capture.

    set_id: the preview set containing the variant
    variant_id: which variant to render
    bars: how many bars to capture (default 8)

    Returns the variant's snapshot data and summary.
    """
    ps = engine.get_preview_set(set_id)
    if not ps:
        return {"error": f"Preview set {set_id} not found"}

    variant = None
    for v in ps.variants:
        if v.variant_id == variant_id:
            variant = v
            break

    if not variant:
        available = [v.variant_id for v in ps.variants]
        return {
            "error": f"Variant {variant_id} not found in set {set_id}",
            "available_variants": available,
        }

    # Wonder-linked context: refuse analytical variants
    wonder_linked = _find_wonder_session_by_preview(set_id) is not None
    if _should_refuse_analytical(variant.compiled_plan, wonder_linked):
        return {
            "error": "This variant is analytical-only and cannot be previewed",
            "variant_id": variant_id,
            "analytical_only": True,
        }

    # If the variant has a compiled plan, apply -> capture audible -> undo.
    # Without a compiled plan, return the variant's analytical preview.
    if variant.compiled_plan:
        ableton = _get_ableton(ctx)
        # compiled_plan may be a list (from semantic moves) or a dict with "steps" key
        plan = variant.compiled_plan
        steps = plan if isinstance(plan, list) else plan.get("steps", [])

        from ..runtime.execution_router import execute_plan_steps_async

        applied_count = 0
        playback_started = False
        preview_mode = "metadata_only_preview"
        spectral_before: Optional[dict] = None
        spectral_after: Optional[dict] = None
        before_info: dict = {}
        after_info: dict = {}

        bridge = ctx.lifespan_context.get("m4l")
        mcp_registry = ctx.lifespan_context.get("mcp_dispatch", {})

        try:
            # ── 1. Capture BEFORE metadata ──
            before_info = ableton.send_command("get_session_info", {}) or {}

            # ── 2. Apply the variant ──
            exec_results = await execute_plan_steps_async(
                steps,
                ableton=ableton,
                bridge=bridge,
                mcp_registry=mcp_registry,
                ctx=ctx,
            )
            applied_count = sum(1 for r in exec_results if r.ok)
            if applied_count == 0 and steps:
                return {
                    "error": "Variant failed to apply any steps",
                    "variant_id": variant_id,
                    "step_errors": [r.error for r in exec_results if not r.ok],
                }

            # ── 3. Capture AFTER metadata (variant is live) ──
            after_info = ableton.send_command("get_session_info", {}) or {}

            # ── 4. Audible capture WHILE variant is still applied ──
            # This is the critical ordering fix: previously this block ran AFTER
            # the finally's undo loop, so "audible_preview" captured pre-variant
            # audio and lied about it. Now playback + spectrum sampling happens
            # while the variant is actually in effect, then the finally undoes it.
            try:
                from ..m4l_bridge import SpectralCache
                cache = ctx.lifespan_context.get("spectral")
                if cache and isinstance(cache, SpectralCache) and cache.is_connected:
                    spectral_before = cache.get_all()

                    tempo = before_info.get("tempo", 120) or 120
                    play_seconds = min(bars * (60.0 / tempo) * 4, 8.0)

                    ableton.send_command("start_playback", {})
                    playback_started = True

                    import time as _time
                    _time.sleep(play_seconds)

                    spectral_after = cache.get_all()

                    ableton.send_command("stop_playback", {})
                    playback_started = False

                    preview_mode = "audible_preview"
            except Exception:
                # Spectral capture is best-effort; keep preview_mode as metadata_only
                pass

        except Exception as e:
            return {"error": f"Render failed: {e}", "variant_id": variant_id}
        finally:
            # ── 5. Cleanup: stop playback if still running, then undo everything ──
            if playback_started:
                try:
                    ableton.send_command("stop_playback", {})
                except Exception:
                    pass
            for _ in range(applied_count):
                try:
                    ableton.send_command("undo")
                except Exception:
                    break

        variant.status = "rendered"
        variant.preview_mode = preview_mode
        variant.render_ref = f"render_{variant_id}_{bars}bars"

        result = {
            "rendered": True,
            "variant_id": variant_id,
            "label": variant.label,
            "bars": bars,
            "preview_mode": preview_mode,
            "before_summary": {"tempo": before_info.get("tempo"), "tracks": before_info.get("track_count")},
            "after_summary": {"tempo": after_info.get("tempo"), "tracks": after_info.get("track_count")},
            "identity_effect": variant.identity_effect,
            "what_changed": variant.what_changed,
            "what_preserved": variant.what_preserved,
        }

        if spectral_before and spectral_after:
            result["spectral_comparison"] = {
                "before": spectral_before,
                "after": spectral_after,
            }

        return result
    else:
        # Analytical preview — no live render
        variant.status = "rendered"
        variant.preview_mode = "analytical_preview"
        return {
            "rendered": True,
            "variant_id": variant_id,
            "label": variant.label,
            "bars": bars,
            "preview_mode": "analytical_preview",
            "intent": variant.intent,
            "novelty_level": variant.novelty_level,
            "identity_effect": variant.identity_effect,
            "what_changed": variant.what_changed,
            "what_preserved": variant.what_preserved,
            "why_it_matters": variant.why_it_matters,
            "note": "Analytical preview — no compiled plan available for live render",
        }


@mcp.tool()
def discard_preview_set(
    ctx: Context,
    set_id: str,
) -> dict:
    """Discard an entire preview set and all its variants.

    Use when the user doesn't want any of the options.
    """
    success = engine.discard_set(set_id)
    if not success:
        return {"error": f"Preview set {set_id} not found"}

    return {"discarded": True, "set_id": set_id}
