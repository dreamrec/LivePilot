"""Composer Engine MCP tools — 3 tools for auto-composition.

compose: full multi-layer composition from text prompt
augment_with_samples: add layers to existing session
get_composition_plan: dry run preview
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp
from .prompt_parser import parse_prompt
from .engine import ComposerEngine
import logging

logger = logging.getLogger(__name__)



# Singleton engine — stateless, safe to reuse
_engine = ComposerEngine()


def _get_search_roots(ctx: Context) -> list:
    """Pull sample-search roots from ctx (if the server wired any) plus
    environment fallbacks.
    """
    roots = []
    try:
        cfg = ctx.lifespan_context.get("sample_search_roots") if hasattr(ctx, "lifespan_context") else None
        if cfg:
            roots.extend(cfg)
    except Exception as exc:
        logger.debug("_get_search_roots failed: %s", exc)
    return roots


async def _credit_safety_prelude(splice_client, max_credits: int) -> tuple[int, int | None, list[str]]:
    """Apply the hard floor / budget trimming rules upfront.

    Returns (adjusted_max_credits, credits_remaining_or_None, warnings).
    """
    warnings: list[str] = []
    credits_remaining: int | None = None

    if splice_client is None or not getattr(splice_client, "connected", False):
        warnings.append(
            "Splice not connected. Plan will use browser/filesystem fallback "
            "for sample search."
        )
        return max_credits, None, warnings

    try:
        info = await splice_client.get_credits()
        credits_remaining = getattr(info, "credits", None)
    except Exception as exc:
        logger.debug("_credit_safety_prelude failed: %s", exc)
        credits_remaining = None

    if credits_remaining is None:
        return max_credits, None, warnings

    if credits_remaining <= 5:
        warnings.append(
            f"Splice credits critically low ({credits_remaining}). "
            f"Using downloaded samples only."
        )
        max_credits = 0
    elif max_credits > credits_remaining - 5:
        safe_budget = max(0, credits_remaining - 5)
        warnings.append(
            f"Budget capped at {safe_budget} credits "
            f"(remaining: {credits_remaining}, floor: 5)."
        )
        max_credits = safe_budget

    return max_credits, credits_remaining, warnings


@mcp.tool()
async def compose(
    ctx: Context,
    prompt: str,
    max_credits: int = 50,
    dry_run: bool = False,
) -> dict:
    """Plan a full multi-layer composition from a text prompt.

    Parses the prompt into genre/mood/tempo/key, plans layers using role
    templates, and compiles an executable plan of tool calls. Does NOT
    execute — returns the plan for the agent to step through.

    prompt: "dark minimal techno 128bpm with industrial textures and ghostly vocals"
    max_credits: maximum Splice credits budget for the plan (default 50, 0 = downloaded only)
    dry_run: if True, return the plan without credit checks

    Returns a compiled plan with step-by-step tool calls. The agent
    executes each step by calling the referenced tools in sequence.
    """
    intent = parse_prompt(prompt)

    splice_client = ctx.lifespan_context.get("splice_client") if hasattr(ctx, "lifespan_context") else None
    search_roots = _get_search_roots(ctx)

    max_credits, credits_remaining, warnings = await _credit_safety_prelude(splice_client, max_credits)

    result = await _engine.compose(
        intent,
        dry_run=dry_run,
        max_credits=max_credits,
        search_roots=search_roots,
        splice_client=splice_client,
    )
    result.warnings.extend(warnings)

    output = result.to_dict()
    output["prompt"] = prompt

    if credits_remaining is not None:
        output["credits_remaining"] = credits_remaining
        output["credits_budget"] = max_credits

    return output


@mcp.tool()
async def augment_with_samples(
    ctx: Context,
    request: str,
    max_credits: int = 10,
    max_layers: int = 3,
) -> dict:
    """Plan sample-based layers to add to the existing session.

    Parses the request and builds a plan for new tracks with sample
    search queries, processing techniques, and volume/pan settings.
    Does NOT execute — returns the plan for the agent to step through.

    request: "add organic textures" or "layer a vocal chop over the verse"
    max_credits: maximum Splice credits budget for the plan (default 10)
    max_layers: maximum number of new tracks in the plan (default 3)

    Returns a compiled plan with step-by-step tool calls.
    """
    splice_client = ctx.lifespan_context.get("splice_client") if hasattr(ctx, "lifespan_context") else None
    search_roots = _get_search_roots(ctx)

    max_credits, credits_remaining, warnings = await _credit_safety_prelude(splice_client, max_credits)

    # Pull current session info for tempo context
    session_context: dict = {}
    try:
        ableton = ctx.lifespan_context.get("ableton")
        if ableton:
            info = ableton.send_command("get_session_info", {})
            session_context["tempo"] = info.get("tempo", 120)
            session_context["track_count"] = info.get("track_count", 0)
    except Exception as exc:
        logger.debug("augment_with_samples failed: %s", exc)
    result = await _engine.augment(
        request=request,
        max_credits=max_credits,
        max_layers=max_layers,
        search_roots=search_roots,
        splice_client=splice_client,
    )

    if session_context.get("tempo"):
        result.intent.tempo = int(session_context["tempo"])

    result.warnings.extend(warnings)

    output = result.to_dict()
    output["request"] = request

    if session_context:
        output["session_context"] = session_context
    if credits_remaining is not None:
        output["credits_remaining"] = credits_remaining
        output["credits_budget"] = max_credits

    return output


@mcp.tool()
async def get_composition_plan(
    ctx: Context,
    prompt: str,
) -> dict:
    """Preview what compose would do without executing or spending credits.

    Returns the full layer plan with search queries, technique selections,
    processing chains, and arrangement sections. Use to review before
    committing to a full composition.

    prompt: "dark minimal techno 128bpm with industrial textures"
    """
    intent = parse_prompt(prompt)
    splice_client = ctx.lifespan_context.get("splice_client") if hasattr(ctx, "lifespan_context") else None
    search_roots = _get_search_roots(ctx)
    plan = await _engine.get_plan(
        intent,
        search_roots=search_roots,
        splice_client=splice_client,
    )
    plan["prompt"] = prompt
    plan["note"] = (
        "This is a dry run. No samples searched or loaded. "
        "Use compose() to get the full plan with credit checks, "
        "then step through each tool call in sequence."
    )
    return plan
