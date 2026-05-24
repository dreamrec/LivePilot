"""Develop compose Phase-3 executor — applies agent-designed variant plan to session.

Receives a plan dict from the agent (free-form variant set: agent decides
count, names, scenes, MIDI), then materializes each variant as a session
clip. Uses the shared Applier for pre-flight (analyzer/bridge) and
post-flight (back_to_arranger) so develop benefits from the same fixes
as fast and full modes.

Develop mode does NOT create new tracks — it only writes session clips
to existing tracks. So postflight passes an empty applied_track_indices
list (skips per-track monitoring set, but still calls back_to_arranger).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastmcp import Context

from ..framework.applier import Applier

logger = logging.getLogger(__name__)


# ── Applier wiring helpers ─────────────────────────────────────────

async def _ensure_analyzer_stub(ctx: Any) -> dict:
    """Develop mode is read-mostly; analyzer is nice-to-have, not required.

    We still call ensure_analyzer_on_master if available, but failures are
    non-fatal (unlike full mode where the analyzer is integral).
    """
    try:
        from ...tools.analyzer import ensure_analyzer_on_master  # type: ignore
        result = ensure_analyzer_on_master(ctx)
        if isinstance(result, dict):
            return result
        return {"status": "unknown"}
    except Exception as exc:
        logger.debug("apply_develop: ensure_analyzer non-fatal failure: %s", exc)
        return {"status": "skipped"}


async def _reconnect_bridge_stub(ctx: Any) -> dict:
    """Reconnect bridge if available; non-fatal failure for develop."""
    try:
        from ...tools.analyzer import reconnect_bridge  # type: ignore
        result = await reconnect_bridge(ctx)
        if isinstance(result, dict):
            connected = bool(result.get("connected") or result.get("ok"))
            return {"connected": connected}
        return {"connected": False}
    except Exception as exc:
        logger.debug("apply_develop: reconnect_bridge non-fatal failure: %s", exc)
        return {"connected": False}


async def _bridge_ping_stub(ctx: Any) -> dict:
    """Lightweight bridge ping — develop doesn't need bridge for clip writes."""
    bridge = None
    if hasattr(ctx, "lifespan_context"):
        bridge = ctx.lifespan_context.get("m4l_bridge")
    if bridge is None:
        raise RuntimeError("bridge not available")
    return await bridge.send_command("ping", timeout=0.5)


async def _back_to_arranger(ctx: Any) -> dict:
    """Call the back_to_arranger MCP primitive."""
    ableton = ctx.lifespan_context.get("ableton") if hasattr(ctx, "lifespan_context") else None
    if ableton is None:
        return {"ok": False}
    try:
        return ableton.send_command("back_to_arranger", {})
    except Exception as exc:
        logger.warning("apply_develop: back_to_arranger failed: %s", exc)
        return {"ok": False}


def _build_applier() -> Applier:
    return Applier(
        ensure_analyzer_fn=_ensure_analyzer_stub,
        reconnect_bridge_fn=_reconnect_bridge_stub,
        bridge_ping_fn=_bridge_ping_stub,
        set_track_input_monitoring_fn=None,  # develop creates no new tracks
        back_to_arranger_fn=_back_to_arranger,
        handshake_max_attempts=2,  # develop is bridge-non-critical; short retry
        handshake_gap_seconds=0.1,
    )


# ── plan validation ────────────────────────────────────────────────

def _validate_plan(plan: dict) -> str | None:
    """Return error message if plan is invalid, else None."""
    if not isinstance(plan, dict):
        return "plan must be a dict"
    if plan.get("scope") not in (None, "develop"):
        return f"plan scope must be 'develop' (got {plan.get('scope')!r})"
    variants = plan.get("variants")
    if not isinstance(variants, list) or len(variants) == 0:
        return "plan.variants must be a non-empty list"
    for i, v in enumerate(variants):
        if not isinstance(v, dict):
            return f"variants[{i}] must be a dict"
        for required in ("track_index", "scene_index"):
            if required not in v:
                return f"variants[{i}] missing required field '{required}'"
        if "notes" in v and not isinstance(v["notes"], list):
            return f"variants[{i}].notes must be a list (or omitted)"
    return None


# ── main entry point ───────────────────────────────────────────────

async def apply_develop_plan(ctx: Context, plan: dict) -> dict:
    """Apply an agent-designed develop plan to the live session.

    See module docstring for plan shape. Returns:
    {
      "status": "ok" | "partial" | "error",
      "clips_created": int,
      "scenes_populated": list[int],
      "sample_swaps": int,
      "preflight": dict,         # Applier.preflight() result
      "postflight": dict,        # Applier.postflight() result
      "errors": list[dict],      # per-variant failures (variant index + reason)
      "duration_ms": int,
    }
    """
    started = time.time()

    err = _validate_plan(plan)
    if err:
        return {"status": "error", "error": err, "phase": "validate"}

    ableton = ctx.lifespan_context.get("ableton") if hasattr(ctx, "lifespan_context") else None
    if ableton is None:
        return {"status": "error", "error": "ableton client not available", "phase": "setup"}

    applier = _build_applier()
    preflight_result = await applier.preflight(ctx)
    # Develop is bridge-non-critical; do NOT abort on bridge failure

    # Tempo override (only if plan specifies a different tempo)
    plan_tempo = plan.get("tempo")
    if plan_tempo is not None:
        try:
            session = ableton.send_command("get_session_info", {})
            current_tempo = float(session.get("tempo", 0.0))
            if abs(current_tempo - float(plan_tempo)) > 0.01:
                ableton.send_command("set_tempo", {"tempo": float(plan_tempo)})
        except Exception as exc:
            logger.warning("apply_develop: tempo set failed: %s", exc)

    clip_length = float(plan.get("clip_length_beats", 4.0))
    clips_created = 0
    sample_swaps = 0
    scenes_populated: set[int] = set()
    errors: list[dict] = []

    for i, v in enumerate(plan["variants"]):
        track_index = int(v["track_index"])
        scene_index = int(v["scene_index"])
        name = v.get("name") or f"v{i}"
        notes = v.get("notes", [])
        sample_uri = v.get("sample_uri")

        try:
            # Optional sample swap (sample-trigger layers only)
            if sample_uri:
                ableton.send_command(
                    "load_browser_item",
                    {"track_index": track_index, "uri": sample_uri},
                )
                sample_swaps += 1

            # Create clip
            ableton.send_command(
                "create_clip",
                {"track_index": track_index, "clip_index": scene_index, "length": clip_length},
            )

            # Add notes (skip if empty — empty clip is a valid drum-dropout pattern)
            if notes:
                ableton.send_command(
                    "add_notes",
                    {"track_index": track_index, "clip_index": scene_index, "notes": notes},
                )

            # Name the clip
            ableton.send_command(
                "set_clip_name",
                {"track_index": track_index, "clip_index": scene_index, "name": name},
            )

            clips_created += 1
            scenes_populated.add(scene_index)
        except Exception as exc:
            logger.warning("apply_develop: variant[%d] failed: %s", i, exc)
            errors.append({"variant_index": i, "reason": str(exc)})

    # Postflight — develop creates no tracks, but still call back_to_arranger
    postflight_result = await applier.postflight(ctx, applied_track_indices=[])

    return {
        "status": "ok" if not errors else "partial",
        "clips_created": clips_created,
        "scenes_populated": sorted(scenes_populated),
        "sample_swaps": sample_swaps,
        "preflight": preflight_result,
        "postflight": postflight_result,
        "errors": errors,
        "duration_ms": int((time.time() - started) * 1000),
    }
