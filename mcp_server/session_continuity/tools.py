"""Session Continuity MCP tools — 7 tools for collaborative memory.

  get_session_story — what the track was becoming, what changed, what's open
  resume_last_intent — pick up where you left off
  record_turn_resolution — log what happened in a creative turn
  rank_by_taste_and_identity — rank candidates with separated taste/identity
  open_creative_thread — open a new creative thread for exploration
  list_open_creative_threads — list all open non-stale creative threads
  explain_preference_vs_identity — explain taste vs identity tension
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from . import tracker
import logging

logger = logging.getLogger(__name__)


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

    taste_graph = _get_taste_graph(ctx)
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


@mcp.tool()
def open_creative_thread(
    ctx: Context,
    description: str,
    domain: str = "",
    priority: float = 0.5,
) -> dict:
    """Open a new creative thread — an unresolved creative goal.

    Use this to track intentions that span multiple actions, like
    "develop the chorus hook" or "fix the transition energy."
    Threads are surfaced by get_session_story and resume_last_intent.

    description: what the creative goal is
    domain: "arrangement", "sound_design", "mix", "harmony", "identity"
    priority: 0-1 importance level
    """
    if not description.strip():
        return {"error": "description cannot be empty"}

    thread = tracker.open_thread(description, domain=domain, priority=priority)
    return thread.to_dict()


@mcp.tool()
def list_open_creative_threads(ctx: Context) -> dict:
    """List all open (non-stale) creative threads in the session.

    Returns unresolved creative goals, abandoned directions worth
    revisiting, and what the next best unresolved question is.
    Stale threads (untouched for >30 minutes) are excluded.
    """
    threads = tracker.list_open_threads()

    return {
        "threads": [t.to_dict() for t in threads],
        "thread_count": len(threads),
        "next_best": threads[0].to_dict() if threads else None,
        "note": "Threads decay after 30 minutes of inactivity",
    }


@mcp.tool()
def explain_preference_vs_identity(
    ctx: Context,
    candidate_id: str = "",
    novelty_level: float = 0.5,
    identity_effect: str = "preserves",
) -> dict:
    """Explain how taste preference and song identity score a candidate.

    Shows the tension between what the user tends to like (taste)
    and what the current song needs (identity). Useful for understanding
    why a variant was ranked the way it was.

    candidate_id: the candidate to explain
    novelty_level: 0-1 how novel the candidate is
    identity_effect: "preserves", "evolves", "contrasts", or "resets"
    """
    taste_graph = _get_taste_graph(ctx)
    song_brain = _get_song_brain_dict()

    candidates = [{
        "id": candidate_id,
        "novelty_level": novelty_level,
        "identity_effect": identity_effect,
    }]

    rankings = tracker.rank_by_taste_and_identity(
        candidates=candidates,
        taste_graph=taste_graph,
        song_brain=song_brain,
    )

    if not rankings:
        return {"error": "Could not rank candidate"}

    r = rankings[0]
    return {
        "candidate_id": candidate_id,
        "taste_score": r.taste_score,
        "identity_score": r.identity_score,
        "composite_score": r.composite_score,
        "taste_explanation": r.taste_explanation,
        "identity_explanation": r.identity_explanation,
        "recommendation": r.recommendation,
        "tension": (
            "aligned" if abs(r.taste_score - r.identity_score) < 0.2
            else "in tension — taste and identity disagree"
        ),
        "note": "Identity has stronger weight inside a session (0.65 vs 0.35)",
    }

# ── Helpers ───────────────────────────────────────────────────────


def _get_song_brain_dict() -> dict:
    try:
        from ..song_brain.tools import _current_brain
        if _current_brain is not None:
            return _current_brain.to_dict()
    except Exception as _e:
        if __debug__:
            import sys
            print(f"LivePilot: SongBrain unavailable in session_continuity: {_e}", file=sys.stderr)
    return {}


def _get_taste_graph(ctx: Context) -> dict:
    """Session-scoped taste graph — matches preview_studio pattern."""
    try:
        from ..memory.taste_graph import build_taste_graph
        from ..memory.taste_memory import TasteMemoryStore
        from ..memory.anti_memory import AntiMemoryStore

        taste_store = ctx.lifespan_context.setdefault("taste_memory", TasteMemoryStore())
        anti_store = ctx.lifespan_context.setdefault("anti_memory", AntiMemoryStore())
        return build_taste_graph(taste_store=taste_store, anti_store=anti_store).to_dict()
    except Exception as exc:
        logger.debug("_get_taste_graph failed: %s", exc)

    return {}
