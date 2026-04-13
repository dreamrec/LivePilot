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


# Singleton engine — stateless, safe to reuse
_engine = ComposerEngine()


@mcp.tool()
async def compose(
    ctx: Context,
    prompt: str,
    max_credits: int = 50,
    dry_run: bool = False,
) -> dict:
    """Create a full multi-layer composition from a text prompt.

    Searches Splice's catalog, selects matching samples with critic scoring,
    downloads them, loads into Ableton, applies processing techniques, and
    arranges into genre-appropriate sections.

    prompt: "dark minimal techno 128bpm with industrial textures and ghostly vocals"
    max_credits: maximum Splice credits to spend (default 50, 0 = use only downloaded)
    dry_run: if True, return the plan without executing (same as get_composition_plan)

    Returns a compiled plan with all execution steps. When dry_run is False,
    the plan is ready for step-by-step execution by the agent.
    """
    # Parse the prompt into structured intent
    intent = parse_prompt(prompt)

    # Credit safety check
    splice_client = None
    credits_remaining = None
    try:
        lifespan = ctx.lifespan_context
        if lifespan and "splice" in lifespan:
            splice_client = lifespan["splice"]
            if splice_client and splice_client.connected:
                credits_remaining = await splice_client.get_credits_remaining()
    except Exception:
        pass

    warnings: list[str] = []

    if credits_remaining is not None:
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

    if splice_client is None or not getattr(splice_client, "connected", False):
        warnings.append(
            "Splice not connected. Plan will use browser/filesystem fallback "
            "for sample search."
        )

    # Compose
    result = _engine.compose(intent, dry_run=dry_run, max_credits=max_credits)

    # Merge warnings
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
    """Add sample-based layers to the existing session.

    Analyzes the request, searches Splice for complementary samples,
    and creates a plan to add new tracks with appropriate processing.

    request: "add organic textures" or "layer a vocal chop over the verse"
    max_credits: maximum Splice credits to spend (default 10)
    max_layers: maximum number of new tracks to add (default 3)

    Returns a compiled plan for adding new layers to the session.
    """
    # Credit safety
    splice_client = None
    credits_remaining = None
    try:
        lifespan = ctx.lifespan_context
        if lifespan and "splice" in lifespan:
            splice_client = lifespan["splice"]
            if splice_client and splice_client.connected:
                credits_remaining = await splice_client.get_credits_remaining()
    except Exception:
        pass

    warnings: list[str] = []

    if credits_remaining is not None:
        if credits_remaining <= 5:
            warnings.append(
                f"Splice credits critically low ({credits_remaining}). "
                f"Using downloaded samples only."
            )
            max_credits = 0
        elif max_credits > credits_remaining - 5:
            safe_budget = max(0, credits_remaining - 5)
            max_credits = safe_budget

    if splice_client is None or not getattr(splice_client, "connected", False):
        warnings.append(
            "Splice not connected. Will use browser/filesystem fallback."
        )

    # Get current session info for context
    session_context: dict = {}
    try:
        ableton = ctx.lifespan_context.get("ableton")
        if ableton:
            info = ableton.send_command("get_session_info", {})
            session_context["tempo"] = info.get("tempo", 120)
            session_context["track_count"] = info.get("track_count", 0)
    except Exception:
        pass

    # Augment
    result = _engine.augment(
        request=request,
        max_credits=max_credits,
        max_layers=max_layers,
    )

    # Override tempo from session if available
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
    plan = _engine.get_plan(intent)
    plan["prompt"] = prompt
    plan["note"] = (
        "This is a dry run. No samples searched, downloaded, or loaded. "
        "Use compose() to execute this plan."
    )
    return plan
