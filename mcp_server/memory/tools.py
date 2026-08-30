"""Memory Fabric V2 MCP tools — anti-memory, promotion, session, and taste endpoints.

6 tools: get_anti_preferences, record_anti_preference, get_promotion_candidates,
         get_session_memory, add_session_memory, get_taste_dimensions.
"""

from __future__ import annotations

import logging

from fastmcp import Context

from ..server import mcp
from .anti_memory import AntiMemoryStore
from .promotion import batch_evaluate_promotions
from .session_memory import SessionMemoryStore
from .taste_memory import TasteMemoryStore

logger = logging.getLogger(__name__)


def _get_anti_memory(ctx: Context) -> AntiMemoryStore:
    """Get or create the session-scoped AntiMemoryStore."""
    return ctx.lifespan_context.setdefault("anti_memory", AntiMemoryStore())


def _get_persistent_taste_store(ctx: Context):
    """Return the persistent taste store from the live server context, or None.

    Only the live server lifespan injects "persistent_taste" (the same key the
    wonder/runtime/preview_studio tools use, so all share ONE instance); tests
    build their own context without it, so taste tools stay session-only
    (hermetic) there. When present, taste write-backs and reads persist across
    restarts (P2-29).
    """
    try:
        return ctx.lifespan_context.get("persistent_taste")
    except AttributeError:
        return None


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
        return {"error": "direction must be 'increase' or 'decrease'",
                "code": "INVALID_PARAM"}
    store = _get_anti_memory(ctx)
    pref = store.record_dislike(dimension, direction)
    # P2-29: persist to the taste store so the anti-preference survives a
    # server restart (best-effort — the session store above is authoritative
    # for the in-session response).
    persistent = _get_persistent_taste_store(ctx)
    persisted = False
    if persistent is not None:
        try:
            persistent.record_anti_preference(dimension, direction)
            persisted = True
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("persist anti_preference failed: %s", exc)
    return {
        "recorded": pref.to_dict(),
        "should_caution": store.should_caution(dimension, direction),
        "persisted": persisted,
    }


@mcp.tool()
def get_promotion_candidates(ctx: Context, limit: int = 10) -> dict:
    """Check the session ledger for entries eligible for memory promotion."""
    # store_purpose: audit_readonly
    # Reads the ledger to find entries already flagged as
    # memory-promotion candidates — an audit/export surface, NOT an
    # anti-repetition recency read.
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


# store_purpose: mcp_tool_definition
# get_session_memory is the MCP tool that surfaces session-scoped
# ephemeral observations/decisions. It is NOT the action ledger and
# NOT the persistent technique library — use the right tool for
# recency (SessionLedger.get_recent_moves / get_action_ledger_summary)
# or for learned techniques (memory_list).
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
    """Add an ephemeral session memory entry.

    Categories:
      - observation / hypothesis / decision / issue (pre-v1.20)
      - move_executed, tech_debt, override (v1.20 director Phase 6 —
        escape-hatch discipline + anti-pattern override logging)
    """
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
    graph = build_taste_graph(
        taste_store=taste_store, anti_store=anti_store,
        persistent_store=_get_persistent_taste_store(ctx),
    )
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
    graph = build_taste_graph(
        taste_store=taste_store, anti_store=anti_store,
        persistent_store=_get_persistent_taste_store(ctx),
    )
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
    graph = build_taste_graph(
        taste_store=taste_store, anti_store=anti_store,
        persistent_store=_get_persistent_taste_store(ctx),
    )

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
    if direction not in ("increase", "decrease"):
        return {
            "error": "direction must be 'increase' or 'decrease'",
            "code": "INVALID_PARAM",
        }
    taste_store = _get_taste_memory(ctx)
    try:
        preference = taste_store.record_preference(dimension, direction)
    except ValueError as exc:
        return {"error": str(exc), "code": "INVALID_PARAM"}
    # P2-29 (dimension-weight half): persist the updated dimension weight so it
    # survives a server restart — symmetric with record_anti_preference. Without
    # this the persisted dimension_weights hydration branch in build_taste_graph
    # stayed dead (no production writer). Best-effort; session store is
    # authoritative for the in-session response.
    persisted = False
    persistent = _get_persistent_taste_store(ctx)
    if persistent is not None:
        try:
            persistent.record_dimension_weight(preference.name, preference.value)
            persisted = True
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("persist dimension_weight failed: %s", exc)
    return {
        "recorded": True,
        "dimension": preference.name,
        "direction": direction,
        "value": round(preference.value, 3),
        "evidence_count": preference.evidence_count,
        "evidence": evidence,
        "persisted": persisted,
    }
