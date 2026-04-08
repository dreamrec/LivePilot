"""Translation Engine MCP tools — 2 tools for playback robustness.

Each tool fetches data from Ableton via the shared connection,
then delegates to pure-computation critics.
"""

from __future__ import annotations

from mcp.server.fastmcp import Context

from ..server import mcp
from .critics import build_translation_report, run_all_translation_critics


# ── Helpers ─────────────────────────────────────────────────────────


async def _fetch_translation_data(ctx: Context) -> dict:
    """Fetch mix snapshot data needed for translation analysis."""
    ableton = ctx.lifespan_context["ableton"]

    # Get mix snapshot — contains spectral and stereo info
    snapshot = {}
    try:
        snapshot = await ableton.send_command("get_mix_snapshot", {})
    except Exception:
        pass

    # Extract spectral bands from snapshot
    spectrum = snapshot.get("spectrum", {})
    stereo = snapshot.get("stereo", {})

    return {
        "stereo_width": stereo.get("side_activity", 0.0),
        "center_strength": stereo.get("center_strength", 0.5),
        "sub_energy": spectrum.get("sub", 0.0),
        "low_energy": spectrum.get("low", 0.0),
        "low_mid_energy": spectrum.get("low_mid", 0.0),
        "high_energy": spectrum.get("high", 0.0),
        "presence_energy": spectrum.get("presence", 0.0),
        "has_foreground": snapshot.get("has_foreground", True),
        "foreground_masked": snapshot.get("foreground_masked", False),
    }


# ── MCP Tools ───────────────────────────────────────────────────────


@mcp.tool()
async def check_translation(ctx: Context) -> dict:
    """Check playback robustness — mono safety, small speakers, harshness.

    Returns a full translation report with robustness classification
    (robust/fragile/critical), boolean safety flags, and suggested
    corrective moves.
    """
    mix_snapshot = await _fetch_translation_data(ctx)
    report = build_translation_report(mix_snapshot)
    return report.to_dict()


@mcp.tool()
async def get_translation_issues(ctx: Context) -> dict:
    """Get just the translation issues without the full report.

    Lighter than check_translation — returns only detected issues
    from the 5 playback robustness critics.
    """
    mix_snapshot = await _fetch_translation_data(ctx)
    issues = run_all_translation_critics(mix_snapshot)
    return {
        "issues": [i.to_dict() for i in issues],
        "issue_count": len(issues),
    }
