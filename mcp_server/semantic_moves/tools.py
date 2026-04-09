"""Semantic move MCP tools — propose, preview, and apply musical intents.

3 tools:
  list_semantic_moves — discover available moves by domain
  preview_semantic_move — see what a move will do before applying
  propose_next_best_move — AI-ranked suggestions based on current session state
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp
from . import registry


@mcp.tool()
def list_semantic_moves(
    ctx: Context,
    domain: str = "",
    style: str = "",
) -> dict:
    """List available semantic moves — high-level musical intents.

    Semantic moves express WHAT to achieve musically, not HOW parametrically.
    Each move compiles into a sequence of existing deterministic tools.

    domain: filter by family (mix, arrangement, transition, sound_design, performance)
    style: filter by genre/style (reserved for future use)

    Returns: list of moves with move_id, family, intent, targets, risk_level.
    """
    moves = registry.list_moves(domain=domain, style=style)
    return {"moves": moves, "count": len(moves), "available_domains": ["mix", "arrangement"]}


@mcp.tool()
def preview_semantic_move(
    ctx: Context,
    move_id: str,
) -> dict:
    """Preview what a semantic move will do before applying it.

    Returns the full compile plan (tool sequence), verification plan,
    targets, protection constraints, and risk level. Use this to understand
    the impact before committing.
    """
    move = registry.get_move(move_id)
    if not move:
        available = [m["move_id"] for m in registry.list_moves()]
        return {
            "error": f"Unknown move_id: {move_id}",
            "available_moves": available,
        }

    return move.to_full_dict()


@mcp.tool()
def propose_next_best_move(
    ctx: Context,
    request_text: str,
    limit: int = 3,
) -> dict:
    """Propose the best semantic moves for a natural language request.

    Analyzes the request text and ranks available semantic moves by
    relevance. Returns up to `limit` suggestions with confidence scores.

    request_text: what the user wants (e.g., "make this punchier",
                  "tighten the low end", "reduce repetition")
    limit: max suggestions to return (default 3)
    """
    if not request_text.strip():
        return {"error": "request_text cannot be empty"}

    # Simple keyword matching for now — will be replaced by conductor
    # routing + taste ranking in V2 Step 7
    request_lower = request_text.lower()
    all_moves = list(registry._REGISTRY.values())

    scored = []
    for move in all_moves:
        score = 0.0
        # Match keywords from intent and move_id
        intent_lower = move.intent.lower()
        move_words = set(move.move_id.replace("_", " ").split())
        intent_words = set(intent_lower.split())
        request_words = set(request_lower.split())

        # Word overlap scoring
        overlap = request_words & (move_words | intent_words)
        score += len(overlap) * 0.3

        # Dimension matching
        for dim in move.targets:
            if dim in request_lower:
                score += 0.2

        # Boost exact intent matches
        if move.move_id.replace("_", " ") in request_lower:
            score += 1.0

        if score > 0:
            scored.append((move, min(score, 1.0)))

    # Sort by score descending
    scored.sort(key=lambda x: -x[1])
    top = scored[:limit]

    suggestions = []
    for move, score in top:
        d = move.to_dict()
        d["match_score"] = round(score, 3)
        suggestions.append(d)

    return {
        "request": request_text,
        "suggestions": suggestions,
        "count": len(suggestions),
    }
