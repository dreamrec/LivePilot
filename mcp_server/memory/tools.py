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
    ledger = ctx.lifespan_context.get("action_ledger")
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


# ── Taste Graph (V2) ────────────────────────────────────────────────


@mcp.tool()
def get_taste_graph(ctx: Context) -> dict:
    """Get the full TasteGraph — extended preferences including move families,
    device affinities, novelty tolerance, and dimension weights.

    The TasteGraph combines taste dimensions, anti-preferences, and
    move/device tracking into a single model for personalized ranking.
    """
    from .taste_graph import build_taste_graph

    taste_store = _get_taste_memory(ctx)
    anti_store = _get_anti_memory(ctx)
    graph = build_taste_graph(taste_store=taste_store, anti_store=anti_store)
    return graph.to_dict()


@mcp.tool()
def explain_taste_inference(ctx: Context) -> dict:
    """Explain why the system thinks the user prefers certain approaches.

    Returns human-readable explanations of inferred taste based on
    evidence from kept moves, undone moves, device usage, and anti-preferences.
    """
    from .taste_graph import build_taste_graph

    taste_store = _get_taste_memory(ctx)
    anti_store = _get_anti_memory(ctx)
    graph = build_taste_graph(taste_store=taste_store, anti_store=anti_store)
    return graph.explain()


@mcp.tool()
def rank_moves_by_taste(
    ctx: Context,
    move_specs: list,
) -> dict:
    """Rank semantic moves by taste fit for the current user.

    move_specs: list of dicts with {move_id, family, targets, risk_level}
    Returns: the same moves sorted by taste_score (descending).

    Use this after propose_next_best_move to personalize the ranking.
    """
    from .taste_graph import build_taste_graph

    taste_store = _get_taste_memory(ctx)
    anti_store = _get_anti_memory(ctx)
    graph = build_taste_graph(taste_store=taste_store, anti_store=anti_store)

    if isinstance(move_specs, str):
        import json
        move_specs = json.loads(move_specs)

    ranked = graph.rank_moves(move_specs)
    return {"ranked_moves": ranked, "count": len(ranked)}


@mcp.tool()
def record_positive_preference(
    ctx: Context,
    dimension: str,
    direction: str,
    evidence: str = "",
) -> dict:
    """Record a user preference for more/less of a dimension.

    dimension: quality axis (e.g., "warmth", "width", "punch")
    direction: "increase" or "decrease"
    evidence: optional note about what triggered this preference

    Complements record_anti_preference — this records what users LIKE,
    not just what they dislike.
    """
    taste_store = _get_taste_memory(ctx)
    # Find matching outcome signals for this dimension+direction
    from ..memory.taste_memory import _OUTCOME_SIGNALS
    matching_signals = []
    dim_signals = _OUTCOME_SIGNALS.get(dimension, {})
    for sig_name, adjustment in dim_signals.items():
        # "increase" preference → match positive-adjustment signals (kept)
        # "decrease" preference → match negative-adjustment signals (undone/less)
        if direction == "increase" and adjustment > 0:
            matching_signals.append(sig_name)
        elif direction == "decrease" and adjustment < 0:
            matching_signals.append(sig_name)
    if matching_signals:
        taste_store.update_from_outcome({"signals": matching_signals})
    return {
        "recorded": bool(matching_signals),
        "dimension": dimension,
        "direction": direction,
        "signals_matched": matching_signals,
        "evidence": evidence,
    }
