"""Preview Studio MCP tools — 4 tools for creative comparison.

  create_preview_set — generate safe/strong/unexpected variants
  compare_preview_variants — rank variants by taste + identity + impact
  commit_preview_variant — apply the chosen variant
  discard_preview_set — throw away all variants
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp
from . import engine


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


@mcp.tool()
def create_preview_set(
    ctx: Context,
    request_text: str,
    kernel_id: str = "",
    strategy: str = "creative_triptych",
) -> dict:
    """Create a preview set with multiple creative options.

    Generates safe / strong / unexpected variants for comparison.
    Each variant includes what it changes, why it matters, and what
    it preserves from the song's identity.

    request_text: what the user wants (e.g., "make this more magical")
    kernel_id: optional session kernel reference
    strategy: "creative_triptych" (default) or "binary"

    Returns: preview set with variant summaries.
    """
    if not request_text.strip():
        return {"error": "request_text cannot be empty"}

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
    except Exception:
        pass

    # Get taste graph — use session-scoped stores, extract numeric weights
    taste_graph: dict = {}
    try:
        from ..memory.taste_graph import build_taste_graph
        from ..memory.taste_memory import TasteMemoryStore
        from ..memory.anti_memory import AntiMemoryStore
        taste_store = ctx.lifespan_context.setdefault("taste_memory", TasteMemoryStore())
        anti_store = ctx.lifespan_context.setdefault("anti_memory", AntiMemoryStore())
        graph = build_taste_graph(taste_store=taste_store, anti_store=anti_store)
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

    return {
        "committed": True,
        "variant_id": chosen.variant_id,
        "label": chosen.label,
        "intent": chosen.intent,
        "move_id": chosen.move_id,
        "identity_effect": chosen.identity_effect,
        "what_preserved": chosen.what_preserved,
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
