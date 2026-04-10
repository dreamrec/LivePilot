"""Wonder Mode MCP tools — 2 tools for controlled surprise.

  enter_wonder_mode — activate wonder mode for a creative request
  generate_wonder_variants — generate and rank surprise-oriented variants
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from . import engine


@mcp.tool()
def enter_wonder_mode(
    ctx: Context,
    request_text: str,
    kernel_id: str = "",
) -> dict:
    """Activate Wonder Mode for a creative request.

    Generates safe / strong / unexpected variants with elevated novelty.
    Each variant is conceptually distinct — not just different in magnitude.
    Sacred elements are respected unless explicitly allowed to break.

    Trigger this for prompts like "surprise me," "make it magical,"
    "take it somewhere," "give me options," or "what if."

    request_text: the creative request
    kernel_id: optional session kernel reference

    Returns ranked variants with musical explanations.
    """
    if not request_text.strip():
        return {"error": "request_text cannot be empty"}

    # Gather context
    song_brain = _get_song_brain_dict()
    taste_graph = _get_taste_graph()
    available_moves = _get_available_moves(request_text)

    variants = engine.generate_wonder_variants(
        request_text=request_text,
        kernel_id=kernel_id,
        song_brain=song_brain,
        taste_graph=taste_graph,
        available_moves=available_moves,
    )

    rankings = engine.rank_wonder_variants(
        variants=variants,
        song_brain=song_brain,
        taste_graph=taste_graph,
    )

    return {
        "mode": "wonder",
        "request": request_text,
        "variants": rankings,
        "recommended": rankings[0]["variant_id"] if rankings else "",
        "note": "Strong is the default recommended pick — unexpected may unlock new directions",
    }


@mcp.tool()
def generate_wonder_variants(
    ctx: Context,
    request_text: str,
    kernel_id: str = "",
) -> dict:
    """Generate wonder-mode variants without entering full wonder mode.

    Like enter_wonder_mode but lighter — returns variants without
    full ranking. Good for quick creative exploration.
    """
    if not request_text.strip():
        return {"error": "request_text cannot be empty"}

    song_brain = _get_song_brain_dict()
    taste_graph = _get_taste_graph()
    available_moves = _get_available_moves(request_text)

    variants = engine.generate_wonder_variants(
        request_text=request_text,
        kernel_id=kernel_id,
        song_brain=song_brain,
        taste_graph=taste_graph,
        available_moves=available_moves,
    )

    return {
        "variants": [v.to_dict() for v in variants],
        "variant_count": len(variants),
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


def _get_available_moves(request_text: str) -> list[dict]:
    try:
        from ..semantic_moves import registry
        return registry.list_moves()[:3]
    except Exception:
        pass
    return []
