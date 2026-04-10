"""Stuckness Detector MCP tools — 2 tools for momentum rescue.

  detect_stuckness — identify whether the session is losing momentum
  suggest_momentum_rescue — get strategic rescue suggestions
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from . import detector


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _get_action_history(ctx: Context) -> list[dict]:
    """Get recent action history from the session-scoped action ledger.

    Returns move entries as dicts for stuckness pattern analysis:
    repeated undos, local-tweaking, loop-without-structure detection.
    Falls back to empty list when no ledger data exists (graceful degradation).
    """
    try:
        from ..runtime.action_ledger import SessionLedger
        ledger = ctx.lifespan_context.get("action_ledger")
        if isinstance(ledger, SessionLedger):
            recent = ledger.get_recent_moves(limit=20)
            return [e.to_dict() for e in recent]
    except Exception:
        pass
    return []


def _get_session_and_brain(ctx: Context) -> tuple[dict, dict, int]:
    """Fetch session info, song brain, and section count."""
    ableton = _get_ableton(ctx)
    session_info: dict = {}
    song_brain: dict = {}
    section_count = 0

    try:
        session_info = ableton.send_command("get_session_info", {})
        section_count = session_info.get("scene_count", 0)
    except Exception:
        pass

    try:
        from ..song_brain.tools import _current_brain
        if _current_brain is not None:
            song_brain = _current_brain.to_dict()
    except Exception:
        pass

    return session_info, song_brain, section_count


@mcp.tool()
def detect_stuckness(ctx: Context) -> dict:
    """Detect whether the session is losing momentum.

    Analyzes action history for stuckness signals:
    - repeated undos
    - many low-impact parameter changes in one area
    - long loop time with no structural edits
    - repeated requests without acceptance
    - too many decorative layers without role clarity
    - unclear song identity

    Returns confidence level, diagnosis, and recommended rescue type.
    Use this proactively when the user seems to be going in circles.
    """
    history = _get_action_history(ctx)
    session_info, song_brain, section_count = _get_session_and_brain(ctx)

    report = detector.detect_stuckness(
        action_history=history,
        session_info=session_info,
        song_brain=song_brain,
        section_count=section_count,
    )

    return report.to_dict()


@mcp.tool()
def suggest_momentum_rescue(
    ctx: Context,
    mode: str = "gentle",
) -> dict:
    """Suggest strategic moves to restore session momentum.

    First detects stuckness, then generates rescue suggestions.
    In "gentle" mode, provides the top suggestion. In "direct" mode,
    provides up to 3 rescue strategies.

    mode: "gentle" (one suggestion) or "direct" (up to 3 suggestions)

    Returns rescue suggestions with strategies and identity effects.
    """
    if mode not in ("gentle", "direct"):
        mode = "gentle"

    history = _get_action_history(ctx)
    session_info, song_brain, section_count = _get_session_and_brain(ctx)

    report = detector.detect_stuckness(
        action_history=history,
        session_info=session_info,
        song_brain=song_brain,
        section_count=section_count,
    )

    if report.level == "flowing":
        return {
            "stuckness": report.to_dict(),
            "note": "Session is flowing well — no rescue needed",
            "suggestions": [],
        }

    suggestions = detector.suggest_rescue(report, mode)

    return {
        "stuckness": report.to_dict(),
        "suggestions": [s.to_dict() for s in suggestions],
        "suggestion_count": len(suggestions),
    }
