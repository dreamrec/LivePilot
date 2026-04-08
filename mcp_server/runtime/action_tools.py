"""MCP tool wrappers for the Action Ledger.

Tools:
  get_action_ledger_summary — recent moves, counts, memory candidates
  get_last_move             — most recent semantic move
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from .action_ledger import SessionLedger


def _get_ledger(ctx: Context) -> SessionLedger:
    """Return the session-scoped ledger singleton."""
    return ctx.lifespan_context.setdefault(
        "action_ledger", SessionLedger()
    )


@mcp.tool()
def get_action_ledger_summary(
    ctx: Context, limit: int = 10, engine: str = ""
) -> dict:
    """Return a summary of recent semantic moves from the action ledger.

    Includes move count, last move, recent moves (newest first),
    and number of memory promotion candidates.
    """
    ledger = _get_ledger(ctx)
    eng = engine if engine else None
    recent = ledger.get_recent_moves(limit=limit, engine=eng)
    last = ledger.get_last_move()
    candidates = ledger.get_memory_candidates()

    return {
        "total_moves": len(ledger._entries),
        "memory_candidate_count": len(candidates),
        "last_move": last.to_dict() if last else None,
        "recent_moves": [e.to_dict() for e in recent],
    }


@mcp.tool()
def get_last_move(ctx: Context) -> dict:
    """Return the most recent semantic move from the action ledger.

    Returns the full ledger entry including intent, scope, actions,
    evaluation, and undo scope.  Returns an empty dict if no moves exist.
    """
    ledger = _get_ledger(ctx)
    entry = ledger.get_last_move()
    if entry is None:
        return {}
    return entry.to_dict()
