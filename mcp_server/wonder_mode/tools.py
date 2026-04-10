"""Wonder Mode MCP tools — 2 tools for controlled surprise.

  enter_wonder_mode — full pipeline: discover, build, rank creative variants
  rank_wonder_variants — standalone re-ranker for any variant list
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from . import engine


def _get_song_brain_dict() -> dict:
    try:
        from ..song_brain.tools import _current_brain
        if _current_brain is not None:
            return _current_brain.to_dict()
    except Exception:
        pass
    return {}


def _get_taste_graph(ctx: Context):
    """Return the TasteGraph object (not dict) for engine use."""
    try:
        from ..memory.taste_graph import build_taste_graph
        from ..memory.taste_memory import TasteMemoryStore
        from ..memory.anti_memory import AntiMemoryStore
        taste_store = ctx.lifespan_context.setdefault("taste_memory", TasteMemoryStore())
        anti_store = ctx.lifespan_context.setdefault("anti_memory", AntiMemoryStore())
        return build_taste_graph(taste_store=taste_store, anti_store=anti_store)
    except Exception:
        pass
    return None


def _get_active_constraints():
    """Read active constraints from creative_constraints module if set."""
    try:
        from ..creative_constraints.tools import _active_constraints
        return _active_constraints
    except Exception:
        return None


@mcp.tool()
def enter_wonder_mode(
    ctx: Context,
    request_text: str,
    kernel_id: str = "",
) -> dict:
    """Activate Wonder Mode for a creative request.

    Discovers relevant semantic moves, assigns them to safe / strong /
    unexpected tiers by risk profile, scores by taste fit, and ranks
    by identity + novelty + coherence.

    Each variant is conceptually distinct — built from a different move
    or a different novelty envelope. Sacred elements are respected
    unless the variant explicitly contrasts them.

    Trigger for: "surprise me," "make it magical," "give me options,"
    "take it somewhere," or "what if."

    request_text: the creative request
    kernel_id: optional session kernel reference

    Returns ranked variants with score breakdowns and a recommendation.
    """
    if not request_text.strip():
        return {"error": "request_text cannot be empty"}

    song_brain = _get_song_brain_dict()
    taste_graph = _get_taste_graph(ctx)
    active_constraints = _get_active_constraints()

    result = engine.generate_and_rank(
        request_text=request_text,
        kernel_id=kernel_id,
        song_brain=song_brain,
        taste_graph=taste_graph,
        active_constraints=active_constraints,
    )

    # Auto-record this creative turn for session continuity
    try:
        from ..session_continuity.tracker import record_turn_resolution
        recommended = result.get("recommended", "")
        rec_variant = next(
            (v for v in result.get("variants", []) if v.get("variant_id") == recommended),
            {},
        )
        record_turn_resolution(
            request_text=request_text,
            outcome="proposed",
            move_applied=rec_variant.get("move_id", ""),
            identity_effect=rec_variant.get("identity_effect", ""),
            user_sentiment="neutral",
        )
    except Exception:
        pass  # session continuity is optional

    return result


@mcp.tool()
def rank_wonder_variants(
    ctx: Context,
    variants: list[dict] | None = None,
) -> dict:
    """Rank wonder-mode variants by taste + identity + novelty + coherence.

    Standalone re-ranker for any list of variant dicts. Preserves ALL
    input fields (what_changed, compiled_plan, move_id, targets_snapshot).

    Uses the current SongBrain and session taste graph for scoring.
    When input dicts lack targets_snapshot, sacred element penalty
    is skipped gracefully.

    variants: list of variant dicts with at least variant_id,
              novelty_level, identity_effect, taste_fit fields

    Returns ranked list with composite scores, breakdowns, and recommendation.
    """
    if not variants:
        return {"error": "No variants provided", "rankings": []}

    song_brain = _get_song_brain_dict()
    taste_graph = _get_taste_graph(ctx)

    novelty_band = 0.5
    taste_evidence = 0
    if taste_graph is not None:
        novelty_band = taste_graph.novelty_band
        taste_evidence = taste_graph.evidence_count

    ranked = engine.rank_variants(
        variant_dicts=[dict(v) for v in variants],  # copy to avoid mutating input
        song_brain=song_brain,
        novelty_band=novelty_band,
        taste_evidence=taste_evidence,
    )

    return {
        "rankings": ranked,
        "recommended": ranked[0]["variant_id"] if ranked else "",
    }
