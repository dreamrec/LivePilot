"""Grader MCP tools — Phases 2c-α (light) + 2c-β (heavy).

Tools:
- `grader_list_rubrics()` — names of registered rubrics
- `grader_evaluate(rubric_id, heavy=False)` — fetches session state and
  runs rubric. Light state covers `layer_accumulation`,
  `default_preset_check`, plus the role+volume parts of every rubric.
  Heavy state adds per-clip notes, per-clip automation, wavetable
  mod-matrix, and session-level masking — required for `layer_precision`
  to produce non-n/a verdicts on `sequence_per_track`,
  `modulation_per_track`, and `masking_per_track`, and for
  `modulation_presence` to leave the n/a state.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastmcp import Context

from ..server import mcp
from ..audit.state import (
    safe_call as _safe_call,
    fetch_notes_for_clips as _fetch_notes_for_clips,
    has_clip_automation as _has_clip_automation,
    count_wavetable_routings as _count_wavetable_routings,
)
from . import client
from . import iterator

logger = logging.getLogger(__name__)


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _maybe_get_masking_report(ctx: Context) -> dict | None:
    """Session-level masking report. Same pattern as audit_layer — calls
    the mix_engine MCP tool's python function directly because masking
    isn't a Remote Script command."""
    try:
        from ..mix_engine.tools import get_masking_report as _impl
        return _impl(ctx)  # type: ignore[arg-type]
    except Exception as exc:
        logger.debug("grader heavy: masking fetch failed: %s", exc)
        return None


def _build_light_state(ctx: Context) -> dict[str, Any]:
    """Light state — `get_session_info` + per-track `get_track_info`.

    Sufficient for rubrics that only need track count, names, mixer,
    devices. Skips per-clip and session-level heavy fetches.
    """
    ableton = _get_ableton(ctx)
    session = _safe_call(ableton, "get_session_info") or {}
    track_count = int(session.get("track_count") or 0)

    tracks: list[dict[str, Any]] = []
    for idx in range(track_count):
        info = _safe_call(ableton, "get_track_info", {"track_index": idx})
        if not info:
            continue
        if info.get("is_foldable") and info.get("is_master"):
            continue
        if info.get("is_return"):
            continue
        tracks.append({
            "index": idx,
            "name": info.get("name") or f"track_{idx}",
            "mixer": info.get("mixer") or {},
            "devices": info.get("devices") or [],
            "clip_slots": info.get("clip_slots") or [],
        })
    return {"tracks": tracks, "fetched_at": time.time()}


def _build_heavy_state(ctx: Context, include_masking: bool = True) -> dict[str, Any]:
    """Heavy state — light + per-clip notes + per-clip automation +
    wavetable mod-matrix + (optionally) session-level masking report.

    Cost: O(tracks × clips) for notes/automation. Realistic budget per
    evaluation: 5–15s on a 4-track session, 30–60s on a populated arrangement.
    """
    ableton = _get_ableton(ctx)
    state = _build_light_state(ctx)
    for t in state["tracks"]:
        idx = t["index"]
        clip_slots = t.get("clip_slots") or []
        t["notes_per_clip"] = _fetch_notes_for_clips(ableton, idx, clip_slots)
        t["has_clip_automation"] = _has_clip_automation(ableton, idx, clip_slots)
        t["wavetable_mod_routings"] = _count_wavetable_routings(ableton, idx, t.get("devices") or [])

    if include_masking:
        masking_report = _maybe_get_masking_report(ctx)
        if masking_report:
            state["masking_report"] = masking_report

    state["heavy"] = True
    return state


@mcp.tool()
def grader_list_rubrics(ctx: Context) -> dict:
    """List the rubrics the grader can evaluate.

    Returns the rubric names registered in `mcp_server.grader.client`. Each
    rubric corresponds to a binding rule from CLAUDE.md (§7.3, §1, §4, §5,
    §2). See `livepilot/rubrics/<rubric_id>.md` for criteria detail.
    """
    return {
        "rubrics": client.list_rubrics(),
        "light_state_sufficient": [
            "layer_accumulation",
            "default_preset_check",
        ],
        "heavy_state_recommended": [
            "modulation_presence",
            "layer_precision",
            "sound_design_depth",
        ],
    }


@mcp.tool()
def grader_evaluate(
    ctx: Context,
    rubric_id: str,
    heavy: bool = False,
    include_brief: bool = True,
    include_masking: bool = True,
) -> dict:
    """Run a rubric across the current session, return verdict + brief.

    State modes:
        - heavy=False (default): `get_session_info` + per-track
          `get_track_info`. ~3s on a 4-track session. Sufficient for
          `layer_accumulation` and `default_preset_check`.
        - heavy=True: adds per-clip `get_notes`, per-clip
          `get_clip_automation`, per-Wavetable `get_wavetable_mod_matrix`,
          and (when `include_masking=True`) session-level
          `get_masking_report`. Required for `layer_precision` to produce
          non-n/a verdicts on sequence/modulation/masking criteria, and
          for `modulation_presence` to leave n/a.

    Args:
        rubric_id: Name of a registered rubric (see `grader_list_rubrics`).
        heavy: When True, fetch per-clip + session-level signals. Slower
            but needed for §4/§5 criteria beyond `stereo_per_track`.
        include_brief: When True (default), attaches a markdown revision
            brief formatted for an orchestrating agent.
        include_masking: When True (default; only relevant when heavy=True),
            includes the session-level masking report. Adds ~200–600ms.

    Returns:
        {
            "rubric_id": str,
            "passed": bool,
            "criteria": [{id, severity, summary, issues, evidence}, ...],
            "revision_brief": str,        # present when include_brief=True
            "track_count_audited": int,
            "state_mode": "light" | "heavy",
            "elapsed_ms": int,
        }
    """
    started = time.time()

    if rubric_id not in client.list_rubrics():
        return {
            "error": f"unknown rubric_id '{rubric_id}'",
            "available": client.list_rubrics(),
        }

    state = _build_heavy_state(ctx, include_masking=include_masking) if heavy else _build_light_state(ctx)
    verdict = client.evaluate(rubric_id, state)

    elapsed_ms = int((time.time() - started) * 1000)
    response = {
        **verdict,
        "track_count_audited": len(state["tracks"]),
        "state_mode": "heavy" if heavy else "light",
        "elapsed_ms": elapsed_ms,
    }
    if include_brief:
        response["revision_brief"] = iterator.format_revision_brief(verdict)
    return response


@mcp.tool()
def grader_evaluate_all(
    ctx: Context,
    heavy: bool = True,
    include_brief: bool = True,
    include_masking: bool = True,
) -> dict:
    """Run ALL rubrics against the current session in one call.

    Builds session state once and evaluates every registered rubric
    against it. ~5× cheaper than calling `grader_evaluate` per rubric
    because state-fetching is the dominant cost.

    Default `heavy=True` — assumes a full audit. Pass `heavy=False`
    for a fast §1/§7.3-only sweep.

    Args:
        heavy: When True (default), uses heavy state. When False, only
            §1 default_preset_check and §7.3 layer_accumulation produce
            useful verdicts; the others return n/a.
        include_brief: Attach per-rubric revision_brief markdown.
        include_masking: Include session-level masking report (heavy only).

    Returns:
        {
            "rubrics": {
                "<rubric_id>": {<verdict + brief>},
                ...
            },
            "any_failed": bool,             # True if any rubric verdict is fail
            "any_advisory": bool,           # True if any rubric has warns
            "track_count_audited": int,
            "state_mode": "light" | "heavy",
            "elapsed_ms": int,
            "combined_brief": str,          # merged across rubrics
        }
    """
    started = time.time()
    state = _build_heavy_state(ctx, include_masking=include_masking) if heavy else _build_light_state(ctx)

    results: dict[str, Any] = {}
    any_failed = False
    any_advisory = False
    brief_parts: list[str] = []

    for rubric_id in client.list_rubrics():
        verdict = client.evaluate(rubric_id, state)
        if not verdict["passed"]:
            any_failed = True
        if any(c["severity"] == "warn" for c in verdict["criteria"]):
            any_advisory = True

        entry: dict[str, Any] = dict(verdict)
        if include_brief:
            brief = iterator.format_revision_brief(verdict)
            entry["revision_brief"] = brief
            if brief:
                brief_parts.append(brief)
        results[rubric_id] = entry

    elapsed_ms = int((time.time() - started) * 1000)
    response: dict[str, Any] = {
        "rubrics": results,
        "any_failed": any_failed,
        "any_advisory": any_advisory,
        "track_count_audited": len(state["tracks"]),
        "state_mode": "heavy" if heavy else "light",
        "elapsed_ms": elapsed_ms,
    }
    if include_brief:
        response["combined_brief"] = "\n\n---\n\n".join(brief_parts) if brief_parts else ""
    return response
