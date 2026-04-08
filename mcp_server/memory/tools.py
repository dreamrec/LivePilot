"""Memory Fabric V2 MCP tools — anti-memory and promotion endpoints.

3 tools: get_anti_preferences, record_anti_preference, get_promotion_candidates.
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from .anti_memory import AntiMemoryStore
from .promotion import batch_evaluate_promotions


def _get_anti_memory(ctx: Context) -> AntiMemoryStore:
    """Get or create the session-scoped AntiMemoryStore."""
    return ctx.lifespan_context.setdefault("anti_memory", AntiMemoryStore())


@mcp.tool()
def get_anti_preferences(ctx: Context) -> dict:
    """Return all recorded anti-preferences — dimensions the user has repeatedly disliked."""
    store = _get_anti_memory(ctx)
    return store.to_dict()


@mcp.tool()
def record_anti_preference(
    ctx: Context, dimension: str, direction: str
) -> dict:
    """Record a user dislike for a dimension+direction. direction must be 'increase' or 'decrease'."""
    if direction not in ("increase", "decrease"):
        return {"error": "direction must be 'increase' or 'decrease'"}
    store = _get_anti_memory(ctx)
    pref = store.record_dislike(dimension, direction)
    return {
        "recorded": pref.to_dict(),
        "should_caution": store.should_caution(dimension, direction),
    }


@mcp.tool()
def get_promotion_candidates(ctx: Context, limit: int = 10) -> dict:
    """Check the session ledger for entries eligible for memory promotion."""
    ledger = ctx.lifespan_context.get("session_ledger")
    if ledger is None:
        return {"candidates": [], "count": 0, "note": "no session ledger active"}

    # Get memory candidates from ledger and evaluate
    raw_candidates = ledger.get_memory_candidates()
    entry_dicts = [e.to_dict() for e in raw_candidates]
    eligible = batch_evaluate_promotions(entry_dicts)

    # Apply limit
    eligible = eligible[:limit]
    return {
        "candidates": [c.to_dict() for c in eligible],
        "count": len(eligible),
    }
