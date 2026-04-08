"""Memory Fabric V2 MCP tools — anti-memory, promotion, session, and taste endpoints.

6 tools: get_anti_preferences, record_anti_preference, get_promotion_candidates,
         get_session_memory, add_session_memory, get_taste_dimensions.
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from .anti_memory import AntiMemoryStore
from .promotion import batch_evaluate_promotions
from .session_memory import SessionMemoryStore
from .taste_memory import TasteMemoryStore


def _get_anti_memory(ctx: Context) -> AntiMemoryStore:
    """Get or create the session-scoped AntiMemoryStore."""
    return ctx.lifespan_context.setdefault("anti_memory", AntiMemoryStore())


def _get_session_memory(ctx: Context) -> SessionMemoryStore:
    """Get or create the session-scoped SessionMemoryStore."""
    return ctx.lifespan_context.setdefault("session_memory", SessionMemoryStore())


def _get_taste_memory(ctx: Context) -> TasteMemoryStore:
    """Get or create the session-scoped TasteMemoryStore."""
    return ctx.lifespan_context.setdefault("taste_memory", TasteMemoryStore())


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


# ── Session Memory ──────────────────────────────────────────────────


@mcp.tool()
def get_session_memory(
    ctx: Context, limit: int = 10, category: str = ""
) -> dict:
    """Return recent session memory entries — ephemeral observations, hypotheses, decisions."""
    store = _get_session_memory(ctx)
    cat = category.strip() or None
    entries = store.get_recent(limit=limit, category=cat)
    return {
        "entries": [e.to_dict() for e in entries],
        "count": len(entries),
    }


@mcp.tool()
def add_session_memory(
    ctx: Context, category: str, content: str, engine: str = "agent_os"
) -> dict:
    """Add an ephemeral session memory entry (observation, hypothesis, decision, issue)."""
    store = _get_session_memory(ctx)
    try:
        entry_id = store.add(category=category, content=content, engine=engine)
    except ValueError as exc:
        return {"error": str(exc)}
    return {"id": entry_id, "status": "added"}


# ── Taste Memory ────────────────────────────────────────────────────


@mcp.tool()
def get_taste_dimensions(ctx: Context) -> dict:
    """Return all taste dimensions — user preferences inferred from kept/undone outcomes."""
    store = _get_taste_memory(ctx)
    return store.to_dict()
