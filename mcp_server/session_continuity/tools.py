"""Session Continuity MCP tools — 4 tools for collaborative memory.

  get_session_story — what the track was becoming, what changed, what's open
  resume_last_intent — pick up where you left off
  record_turn_resolution — log what happened in a creative turn
  rank_by_taste_and_identity — rank candidates with separated taste/identity
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from . import tracker


@mcp.tool()
def get_session_story(ctx: Context) -> dict:
    """Get the narrative of the current session.

    At the start of a resumed session, the agent can say what the track
    was trying to become, what changed last time, and what still feels open.

    Returns identity summary, recent turns, open creative threads,
    and mood arc.
    """
    song_brain = _get_song_brain_dict()
    story = tracker.get_session_story(song_brain)
    return story.to_dict()


@mcp.tool()
def resume_last_intent(ctx: Context) -> dict:
    """Resume the most recent unresolved creative intent.

    Finds the latest open creative thread and suggests continuing it.
    Stale threads (untouched for >30 minutes) are excluded.
    """
    return tracker.resume_last_intent()


@mcp.tool()
def record_turn_resolution(
    ctx: Context,
    request_text: str,
    outcome: str = "accepted",
    move_applied: str = "",
    identity_effect: str = "",
    user_sentiment: str = "neutral",
) -> dict:
    """Record what happened in a creative turn.

    Call this after each significant creative action to build the
    session story. Tracks outcomes, identity effects, and user sentiment.

    request_text: what was requested
    outcome: "accepted", "rejected", "modified", or "undone"
    move_applied: which semantic move was used (if any)
    identity_effect: "preserves", "evolves", "contrasts", or "resets"
    user_sentiment: "loved", "liked", "neutral", "disliked", or "hated"
    """
    turn = tracker.record_turn_resolution(
        request_text=request_text,
        outcome=outcome,
        move_applied=move_applied,
        identity_effect=identity_effect,
        user_sentiment=user_sentiment,
    )
    return turn.to_dict()


@mcp.tool()
def rank_by_taste_and_identity(
    ctx: Context,
    candidates: list[dict] | None = None,
) -> dict:
    """Rank candidates with separated taste and identity scoring.

    Taste (cross-session preference) ranks options.
    Identity (in-song) constrains/shapes options.
    Explicit user instructions override both.

    candidates: list of dicts with at least "id", "novelty_level",
                and "identity_effect" fields

    Returns ranked list with taste_score, identity_score, composite,
    and explanations for each.
    """
    if not candidates:
        return {"error": "No candidates provided", "rankings": []}

    taste_graph = _get_taste_graph()
    song_brain = _get_song_brain_dict()

    rankings = tracker.rank_by_taste_and_identity(
        candidates=candidates,
        taste_graph=taste_graph,
        song_brain=song_brain,
    )

    return {
        "rankings": [r.to_dict() for r in rankings],
        "note": "Identity has stronger weight inside a session; taste has stronger weight when choosing among viable options",
    }


# ── Helpers ───────────────────────────────────────────────────────


def _get_song_brain_dict() -> dict:
    try:
        from ..song_brain.tools import _current_brain
        if _current_brain is not None:
            return _current_brain.to_dict()
    except Exception:
        pass
    return {}


def _get_taste_graph() -> dict:
    try:
        from ..memory.taste_memory import TasteMemoryStore
        return TasteMemoryStore().to_dict()
    except Exception:
        pass
    return {}
