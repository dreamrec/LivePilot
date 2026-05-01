"""Full compose Phase-3 executor — applies engine-generated plan to live session."""

from __future__ import annotations

import logging
import re as _re
import time

from fastmcp import Context

from ..framework.applier import Applier

logger = logging.getLogger(__name__)

# Magic ratios for "smart" mode — common polyrhythmic + half/double-time
# relationships that produce musically interesting results when a loop
# plays un-warped against a project at a different tempo.
_MEANINGFUL_TEMPO_RATIOS: tuple[float, ...] = (
    0.5,    # half-time (project is 2× source)
    0.667,  # 2:3 polyrhythm (project is 1.5× source)
    0.75,   # 3:4 cross-rhythm (project is 1.333× source)
    0.8,    # 4:5
    1.25,   # 5:4
    1.333,  # 4:3 cross-rhythm (source is 1.333× project)
    1.5,    # 3:2 polyrhythm
    2.0,    # double-time
)
_MEANINGFUL_RATIO_TOLERANCE = 0.02  # ±2%

# BPM hint pattern — matches the same naming conventions as
# `_LOOP_FILENAME_RE` in `_analyzer_engine/sample.py`. Splice files use
# `_125_` or `_125bpm` or `125 BPM` style.
_BPM_FROM_FILENAME_RE = _re.compile(
    r"(?:_|\b)(\d{2,3})\s*(?:_|bpm|\b)",
    _re.IGNORECASE,
)


def _extract_bpm_from_filename(file_path: str) -> int | None:
    """Pull a plausible BPM (60-200) from a sample's filename.

    Splice files embed BPM in the basename: `lfh_drums_125_hubble.wav`
    → 125. Returns None if no plausible BPM hint exists (one-shots,
    tonal samples named by key only, etc.). The 60-200 range filters
    out catalog IDs that happen to be 3-digit numbers.
    """
    if not file_path:
        return None
    import os as _os
    stem = _os.path.splitext(_os.path.basename(file_path))[0]
    for match in _BPM_FROM_FILENAME_RE.findall(stem):
        try:
            n = int(match)
        except (ValueError, TypeError):
            continue
        if 60 <= n <= 200:
            return n
    return None


def _is_meaningful_ratio(
    source_bpm: int | float | None,
    project_bpm: int | float | None,
    tolerance: float = _MEANINGFUL_RATIO_TOLERANCE,
) -> bool:
    """Return True when source/project BPM ratio is in the magic set ±tol.

    Used by 'smart' warp strategy to decide when to leave a loop
    un-warped (because the tempo mismatch creates interesting chopping)
    versus warping it to project tempo (the production-safe default).

    Defensive on None / 0 inputs — returns False rather than blowing up
    on missing BPM data.
    """
    if not source_bpm or not project_bpm:
        return False
    try:
        ratio = float(source_bpm) / float(project_bpm)
    except (ZeroDivisionError, ValueError, TypeError):
        return False
    for magic in _MEANINGFUL_TEMPO_RATIOS:
        if abs(ratio - magic) / magic <= tolerance:
            return True
    return False


# Roles whose layers should ALWAYS warp regardless of ratio. Tonal /
# harmonic content sounds wrong when un-warped — only drums benefit
# from intentional chopping.
_TONAL_ROLES_ALWAYS_WARP: frozenset[str] = frozenset({
    "pad", "bass", "lead", "vocal", "texture", "fx",
})


def _decide_warp_loops(
    role: str,
    file_path: str,
    project_tempo: int | float | None,
    strategy: str,
) -> bool:
    """Decide whether to warp this loop based on strategy + role + ratio.

    Strategy semantics:
      - "always" → always True (production-safe default)
      - "chop"   → always False (creative chopping mode)
      - "smart"  → True for tonal roles; for drum/perc, False if the
                   source/project BPM ratio lands on a magic ratio.

    Returns the boolean to pass as `warp_loops` to load_sample_to_simpler.
    """
    s = (strategy or "always").lower().strip()
    if s == "chop":
        return False
    if s == "always":
        return True
    if s == "smart":
        # Tonal roles always warp — chopping a pad sounds glitchy bad
        if (role or "").lower() in _TONAL_ROLES_ALWAYS_WARP:
            return True
        # Drum/perc with no project tempo → can't compute ratio → warp
        if not project_tempo:
            return True
        source_bpm = _extract_bpm_from_filename(file_path)
        if not source_bpm:
            return True  # no BPM hint → can't be sure → safe default
        # Meaningful ratio → leave un-warped for creative chopping
        if _is_meaningful_ratio(source_bpm, project_tempo):
            return False
        return True
    # Unknown strategy → default to always
    return True


def _resolve_from_step(value, step_results: dict):
    """Recursively substitute ``$from_step`` placeholders inside plan params.

    The plan emits cross-step references for things like the device_index
    of a freshly inserted device:

        {"$from_step": "layer_0_dev_0", "path": "device_index"}

    The walker captures every step's response keyed by its ``step_id``.
    This helper walks the params tree and replaces those placeholders
    with the actual values before dispatching the call.
    """
    if isinstance(value, dict):
        if "$from_step" in value:
            ref_id = value["$from_step"]
            path = str(value.get("path", "") or "")
            if ref_id not in step_results:
                raise ValueError(
                    f"$from_step references unknown step '{ref_id}' "
                    f"(known: {sorted(step_results.keys())})"
                )
            current = step_results[ref_id]
            if path:
                for key in path.split("."):
                    if not key:
                        continue
                    if not isinstance(current, dict) or key not in current:
                        raise ValueError(
                            f"$from_step path '{path}' not found in step "
                            f"'{ref_id}' result keys={list(current.keys()) if isinstance(current, dict) else type(current).__name__}"
                        )
                    current = current[key]
            return current
        return {k: _resolve_from_step(v, step_results) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_from_step(v, step_results) for v in value]
    return value


# Plan tools that aren't direct Remote-Script TCP commands — they need
# special dispatch (either a Python function call or a multi-step bridge
# routine like `load_sample_to_simpler` which itself does multiple TCP
# operations under the hood).
_FULL_PLAN_TCP_TOOLS = {
    "set_tempo",
    "create_midi_track",
    "create_audio_track",
    "create_return_track",
    "create_scene",
    "set_track_name",
    "set_track_volume",
    "set_track_pan",
    "set_track_send",
    "insert_device",
    "set_device_parameter",
    "create_clip",
    "add_notes",
    "create_arrangement_clip",
    "set_clip_color",
    "set_track_color",
    "set_clip_name",
    "set_clip_loop",
}


async def apply_full_plan(
    ctx: Context,
    plan_response: dict,
    warp_strategy: str = "always",
) -> dict:
    """DEPRECATED in v1.24 — use apply_full_plan_v2 instead.

    The old deterministic engine path (compose → step_plan → apply_full_plan)
    was prone to flat single-pattern arrangements (BUG-FULL-MODE-18). v1.24
    replaces it with an LLM-creative two-phase flow:
    compose(mode="full") → brief → agent designs plan → compose_full_apply
    → apply_full_plan_v2.

    This function is preserved for any test that exercises the old shape but
    new code should not call it.

    Phase-3 full mode: server-side execute the planner's tool sequence.

    Pre-flight handles the same fresh-project cleanup fast mode does
    (BUG-FULL-MODE-4): detects default tracks, deletes them down to one
    survivor, loads the LivePilot Analyzer on master, sets the project
    tempo. Then walks the plan's `plan` array sequentially, resolving
    `$from_step` references against accumulated step results. After the
    walk, deletes the leftover default track if it's still empty
    (BUG-FULL-MODE-5).

    BUG-FULL-MODE-14 fix: bridge handshake uses Applier's retry loop
    (up to 3 attempts with 200ms gaps) so load_sample_to_simpler doesn't
    race against the M4L JS listener still binding its UDP socket.

    BUG-FULL-MODE-17 fix: Applier.postflight() sets monitoring=In on
    every newly-created track and calls back_to_arranger so arrangement
    clips play without requiring manual arm-button toggle.

    `warp_strategy` (BUG-FULL-MODE-12, 2026-05-01) controls per-step
    Simpler warping behavior:
      - "always" (default): every loop warps to project tempo
      - "smart": tonal layers always warp; drum/perc loops un-warped
        when source/project ratio is musically meaningful (creates
        creative tempo-mismatch chopping — J Dilla / Madlib territory)
      - "chop": no warping anywhere (pure creative chopping)
    """
    from .. import fast as fast_compose

    started = time.time()
    ableton = ctx.lifespan_context.get("ableton") if hasattr(ctx, "lifespan_context") else None
    if ableton is None:
        return {"error": "Ableton connection not available", "phase": "apply"}

    plan_steps = plan_response.get("plan") or []
    if not plan_steps:
        return {"error": "plan.plan is empty — nothing to apply", "phase": "apply"}

    # ── Pre-flight: Applier handles analyzer load + bridge handshake ────
    # Fixes BUG-FULL-MODE-14 (bridge race): the Applier's retry loop pings
    # the bridge with up to 3 attempts / 200ms gap so the M4L JS listener
    # has time to bind its UDP socket before load_sample_to_simpler runs.
    fresh_actions: list[str] = []

    from ...tools.analyzer import (
        ensure_analyzer_on_master as _ensure_analyzer,
        reconnect_bridge as _reconnect_bridge,
    )
    from ...tools._analyzer_engine.context import _get_m4l
    from ...tools.arrangement import back_to_arranger as _back_to_arranger
    from ...tools.tracks import set_track_input_monitoring as _set_track_input_monitoring

    async def _ensure_analyzer_async(c):
        return _ensure_analyzer(c)

    async def _reconnect_bridge_async(c):
        resp = await _reconnect_bridge(c)
        # reconnect_bridge returns {"ok": True} on success; normalize to
        # {"connected": True} so Applier.preflight can use a unified key.
        if isinstance(resp, dict) and resp.get("ok"):
            resp = dict(resp)
            resp["connected"] = True
        return resp

    async def _bridge_ping_async(c):
        bridge = _get_m4l(c)
        return await bridge.send_command("ping", timeout=0.5)

    async def _set_monitoring_async(c, *, track_index, state):
        return _set_track_input_monitoring(c, track_index=track_index, state=state)

    async def _back_to_arranger_async(c):
        return _back_to_arranger(c)

    applier = Applier(
        ensure_analyzer_fn=_ensure_analyzer_async,
        reconnect_bridge_fn=_reconnect_bridge_async,
        bridge_ping_fn=_bridge_ping_async,
        set_track_input_monitoring_fn=_set_monitoring_async,
        back_to_arranger_fn=_back_to_arranger_async,
    )

    preflight_result = await applier.preflight(ctx)
    if preflight_result.get("analyzer_status") in ("loaded", "already_loaded"):
        fresh_actions.append("analyzer_loaded_on_master")
    if preflight_result.get("bridge_connected"):
        fresh_actions.append("bridge_connected")
    else:
        logger.debug(
            "full apply: bridge handshake failed after %d attempt(s): %s",
            preflight_result.get("handshake_attempts", 0),
            preflight_result.get("handshake_error", "unknown"),
        )

    # ── Detect + clean default tracks ──────────────────────────────────
    session = ableton.send_command("get_session_info", {})
    starting_track_count = int(session.get("track_count", 0))

    fresh_project = fast_compose.detect_fresh_project(session)
    if fresh_project:
        candidates: list[int] = []
        for i in range(starting_track_count):
            try:
                ti = ableton.send_command("get_track_info", {"track_index": i})
                if fast_compose.track_is_empty(ti):
                    candidates.append(i)
            except Exception as exc:
                logger.debug("full apply: fresh-check get_track_info(%s) failed: %s", i, exc)

        if len(candidates) == starting_track_count and starting_track_count > 0:
            fresh_actions.append(f"detected_fresh_project_{starting_track_count}_default_tracks")
            # Leave one survivor — Ableton requires ≥1 track at all times
            deletable = sorted(candidates, reverse=True)[:-1]
            deleted = 0
            for idx in deletable:
                try:
                    ableton.send_command("delete_track", {"track_index": idx})
                    deleted += 1
                except Exception as exc:
                    logger.debug("full apply: delete_track(%s) failed: %s", idx, exc)
            if deleted:
                fresh_actions.append(f"deleted_{deleted}_default_tracks_preflight")

    # ── Walk plan steps ────────────────────────────────────────────────
    step_results: dict[str, dict] = {}
    step_outcomes: list[dict] = []
    failed_count = 0
    # Track indices of newly-created tracks for postflight monitoring fix
    created_track_indices: list[int] = []

    for i, step in enumerate(plan_steps):
        tool_name = (step.get("tool") or "").strip()
        params = step.get("params") or {}
        step_id = step.get("step_id")
        description = step.get("description") or ""
        role = step.get("role")

        # Resolve $from_step refs inside params
        try:
            resolved_params = _resolve_from_step(params, step_results)
        except Exception as exc:
            failed_count += 1
            step_outcomes.append({
                "index": i, "tool": tool_name, "step_id": step_id,
                "description": description, "role": role,
                "ok": False, "error": f"$from_step resolution failed: {exc}",
            })
            continue

        # Dispatch
        result: dict = {}
        ok = True
        err_msg: str | None = None
        try:
            if tool_name == "load_sample_to_simpler":
                # Special-case: this is an MCP tool that wraps multi-step
                # bridge work (verify, replace, hygiene). Call it as a
                # Python function rather than a single TCP command.
                #
                # BUG-FULL-MODE-12: translate warp_strategy → per-step
                # warp_loops bool, based on this layer's role + the
                # source loop's BPM ratio against project tempo.
                project_tempo = (plan_response.get("intent") or {}).get("tempo")
                warp_loops_decision = _decide_warp_loops(
                    role=role or "",
                    file_path=str(resolved_params.get("file_path", "")),
                    project_tempo=project_tempo,
                    strategy=warp_strategy,
                )
                # Don't override an explicit warp_loops in the plan
                # params (lets the planner — or a manual edit — pin a
                # specific layer's warp setting regardless of strategy).
                if "warp_loops" not in resolved_params:
                    resolved_params["warp_loops"] = warp_loops_decision

                from ...tools.analyzer import load_sample_to_simpler as _load_sample
                # The MCP tool is async — await it with the resolved kwargs.
                result = await _load_sample(ctx, **resolved_params)
            elif tool_name in ("create_midi_track", "create_audio_track"):
                # Track the index so postflight can set monitoring on them
                result = ableton.send_command(tool_name, resolved_params) or {}
                if ok and isinstance(result, dict):
                    track_idx = result.get("track_index")
                    if track_idx is not None:
                        created_track_indices.append(int(track_idx))
            elif tool_name in _FULL_PLAN_TCP_TOOLS:
                # Direct Remote-Script TCP command
                result = ableton.send_command(tool_name, resolved_params) or {}
            else:
                # Unknown tool — try generic TCP send (most LivePilot tools
                # have a 1:1 Remote-Script handler with the same name).
                result = ableton.send_command(tool_name, resolved_params) or {}
        except Exception as exc:
            ok = False
            err_msg = str(exc)
            failed_count += 1
            logger.debug("full apply step %s (%s) failed: %s", i, tool_name, exc)

        if step_id and ok:
            step_results[step_id] = result if isinstance(result, dict) else {}

        step_outcomes.append({
            "index": i,
            "tool": tool_name,
            "step_id": step_id,
            "description": description,
            "role": role,
            "ok": ok,
            "error": err_msg,
        })

    # ── Post-flight cleanup (Item 5) ───────────────────────────────────
    # BUG-FULL-MODE-8 (2026-05-01): the original implementation only
    # checked tracks[0] for a default-name leftover. That worked for
    # fast mode where new tracks are appended at the end (so the
    # survivor stays at index 0), but full mode's planner creates
    # tracks at SPECIFIC indices (0, 1, 2, 3, 4...) which pushes the
    # survivor to index N. Fix: scan ALL tracks and prune every empty
    # default-named one. Walk highest-to-lowest so deletions don't
    # invalidate the indices below.
    final_cleanup_actions: list[str] = []
    try:
        post_session = ableton.send_command("get_session_info", {})
        tracks = post_session.get("tracks", []) or []
        if tracks and len(tracks) > 1:
            default_indices: list[int] = []
            for i, t in enumerate(tracks):
                if fast_compose.is_default_track_name(t.get("name", "")):
                    try:
                        ti = ableton.send_command("get_track_info", {"track_index": i})
                        if fast_compose.track_is_empty(ti):
                            default_indices.append(i)
                    except Exception as exc:
                        logger.debug("full apply: cleanup get_track_info(%s) failed: %s", i, exc)
            # Delete highest-to-lowest so earlier deletions don't shift
            # the indices we still need to delete.
            for idx in sorted(default_indices, reverse=True):
                # Don't delete if we'd end up with zero tracks
                if len(tracks) - len(final_cleanup_actions) <= 1:
                    break
                try:
                    ableton.send_command("delete_track", {"track_index": idx})
                    final_cleanup_actions.append(f"deleted_leftover_default_track_at_{idx}")
                except Exception as exc:
                    logger.debug("full apply: final cleanup delete_track(%s) failed: %s", idx, exc)
    except Exception as exc:
        logger.debug("full apply: post-session read failed: %s", exc)

    # ── Applier post-flight: monitoring + back_to_arranger ────────────
    # Fixes BUG-FULL-MODE-17: set current_monitoring_state=In on every
    # newly-created track so arrangement clips play without manual toggle.
    postflight_result = await applier.postflight(ctx, applied_track_indices=created_track_indices)

    duration_ms = int((time.time() - started) * 1000)
    return {
        "phase": "apply",
        "mode": "full",
        "steps_executed": len(step_outcomes),
        "steps_failed": failed_count,
        "step_outcomes": step_outcomes,
        "fresh_project_actions": fresh_actions,
        "final_cleanup_actions": final_cleanup_actions,
        "postflight": postflight_result,
        "duration_ms": duration_ms,
        "summary": (
            f"{len(step_outcomes)} steps walked, "
            f"{failed_count} failed, "
            f"{len(fresh_actions)} pre-flight action(s), "
            f"{len(final_cleanup_actions)} cleanup action(s), "
            f"{postflight_result.get('tracks_set', 0)} tracks monitoring=In"
        ),
    }


# ── v1.24 LLM-creative two-phase flow ─────────────────────────────


def _validate_v2_plan(plan: dict) -> str | None:
    """Return error message if plan is invalid, else None."""
    if not isinstance(plan, dict):
        return "plan must be a dict"
    if plan.get("scope") not in (None, "full"):
        return f"plan scope must be 'full' (got {plan.get('scope')!r})"
    form = plan.get("form")
    if not isinstance(form, list) or len(form) == 0:
        return "plan.form must be a non-empty list of section descriptors"
    tracks = plan.get("tracks")
    if not isinstance(tracks, list) or len(tracks) == 0:
        return "plan.tracks must be a non-empty list"
    for ti, t in enumerate(tracks):
        if not isinstance(t, dict):
            return f"tracks[{ti}] must be a dict"
        variants = t.get("variants", [])
        if not isinstance(variants, list):
            return f"tracks[{ti}].variants must be a list"
        for vi, v in enumerate(variants):
            if not isinstance(v, dict):
                return f"tracks[{ti}].variants[{vi}] must be a dict"
            if "id" not in v:
                return f"tracks[{ti}].variants[{vi}] missing 'id'"
        arr_clips = t.get("arrangement_clips", [])
        if not isinstance(arr_clips, list):
            return f"tracks[{ti}].arrangement_clips must be a list"
        variant_ids = {v["id"] for v in variants}
        for ci, ac in enumerate(arr_clips):
            if "variant_id" in ac and ac["variant_id"] not in variant_ids:
                return (
                    f"tracks[{ti}].arrangement_clips[{ci}] references unknown "
                    f"variant_id {ac['variant_id']!r} (known: {sorted(variant_ids)})"
                )
    return None


async def apply_full_plan_v2(ctx: Context, plan: dict) -> dict:
    """Apply an agent-designed full-mode plan to the live session.

    The agent designs form + variants + events from the brief returned by
    compose(mode="full"); this function validates + executes. Replaces the
    deterministic engine path that was prone to flat single-pattern
    arrangements (BUG-FULL-MODE-18).

    Plan shape:
    {
      "scope": "full",          # optional, must be "full" if present
      "tempo": 128.0,           # optional — applied if differs from session
      "key": "Am",              # optional — passed to set_song_scale
      "form": [                 # REQUIRED — list of section descriptors
        {"name": "intro", "start_bar": 0, "bars": 16},
        {"name": "main",  "start_bar": 16, "bars": 32},
        ...
      ],
      "tracks": [               # REQUIRED — list of track specs
        {
          "role": "bass",
          "track_index": 1,     # OPTIONAL — reuse existing; create new if absent
          "instrument": {"uri": "atlas://...", "params": {}},  # OPTIONAL
          "variants": [         # list of source clip definitions
            {"id": "main_v", "notes": [...]},
            {"id": "build",  "notes": [...]},
          ],
          "arrangement_clips": [
            {"section_index": 0, "variant_id": "main_v", "loop_length": 4.0},
            ...
          ],
        },
        ...
      ],
      "events": [...],          # Phase 4 structural events — accepted, not applied in Phase 3
    }

    Returns:
      {
        "status": "ok" | "partial" | "error",
        "tracks_created": int,
        "variants_created": int,
        "arrangement_clips_created": int,
        "events_applied": int,
        "preflight": dict,
        "postflight": dict,
        "errors": list[dict],
        "duration_ms": int,
      }
    """
    started = time.time()

    err = _validate_v2_plan(plan)
    if err:
        return {"status": "error", "error": err, "phase": "validate"}

    ableton = ctx.lifespan_context.get("ableton") if hasattr(ctx, "lifespan_context") else None
    if ableton is None:
        return {"status": "error", "error": "ableton client not available", "phase": "setup"}

    # ── Build Applier from develop stubs ──────────────────────────────
    from ..develop.apply import (
        _ensure_analyzer_stub,
        _reconnect_bridge_stub,
        _bridge_ping_stub,
        _back_to_arranger,
    )

    async def _set_track_input_monitoring(c, *, track_index, state):
        ab = c.lifespan_context.get("ableton") if hasattr(c, "lifespan_context") else None
        if ab is None:
            return {"ok": False}
        try:
            return ab.send_command(
                "set_track_input_monitoring",
                {"track_index": track_index, "state": state},
            )
        except Exception:
            return {"ok": False}

    applier = Applier(
        ensure_analyzer_fn=_ensure_analyzer_stub,
        reconnect_bridge_fn=_reconnect_bridge_stub,
        bridge_ping_fn=_bridge_ping_stub,
        set_track_input_monitoring_fn=_set_track_input_monitoring,
        back_to_arranger_fn=_back_to_arranger,
        handshake_max_attempts=3,
        handshake_gap_seconds=0.2,
    )

    preflight_result = await applier.preflight(ctx)

    # ── Tempo + key application ───────────────────────────────────────
    plan_tempo = plan.get("tempo")
    plan_key = plan.get("key")
    if plan_tempo is not None:
        try:
            session = ableton.send_command("get_session_info", {})
            current_tempo = float(session.get("tempo", 0.0))
            if abs(current_tempo - float(plan_tempo)) > 0.01:
                ableton.send_command("set_tempo", {"tempo": float(plan_tempo)})
        except Exception as exc:
            logger.warning("apply_full_v2: tempo set failed: %s", exc)
    if plan_key:
        try:
            ableton.send_command("set_song_scale", {"root_note": plan_key})
        except Exception as exc:
            logger.debug("apply_full_v2: set_song_scale skipped: %s", exc)

    form = plan["form"]
    tracks_created = 0
    variants_created = 0
    arrangement_clips_created = 0
    events_applied = 0
    errors: list[dict] = []
    applied_track_indices: list[int] = []

    for ti, track_spec in enumerate(plan["tracks"]):
        # Resolve track_index — create new if not provided
        track_index = track_spec.get("track_index")
        if track_index is None:
            try:
                result = ableton.send_command(
                    "create_midi_track",
                    {"index": -1, "name": track_spec.get("role", "")},
                )
                track_index = int(result.get("track_index", -1))
                if track_index >= 0:
                    tracks_created += 1
                    applied_track_indices.append(track_index)
            except Exception as exc:
                errors.append({"track_index": ti, "phase": "create_track", "reason": str(exc)})
                continue
        else:
            track_index = int(track_index)

        # Optional instrument load
        instrument = track_spec.get("instrument") or {}
        if instrument.get("uri"):
            try:
                ableton.send_command(
                    "load_browser_item",
                    {"track_index": track_index, "uri": instrument["uri"]},
                )
            except Exception as exc:
                errors.append({
                    "track_index": track_index,
                    "phase": "load_instrument",
                    "reason": str(exc),
                })

        # Variants → session source clips (slots 0..N)
        variant_id_to_slot: dict[str, int] = {}
        for vi, variant in enumerate(track_spec.get("variants", [])):
            slot = vi
            variant_id_to_slot[variant["id"]] = slot
            try:
                ableton.send_command("create_clip", {
                    "track_index": track_index,
                    "clip_index": slot,
                    "length": 4.0,
                })
                if variant.get("notes"):
                    ableton.send_command("add_notes", {
                        "track_index": track_index,
                        "clip_index": slot,
                        "notes": variant["notes"],
                    })
                ableton.send_command("set_clip_name", {
                    "track_index": track_index,
                    "clip_index": slot,
                    "name": variant["id"],
                })
                variants_created += 1
            except Exception as exc:
                errors.append({
                    "track_index": track_index,
                    "phase": f"variant_{variant['id']}",
                    "reason": str(exc),
                })

        # Arrangement clips
        for ac in track_spec.get("arrangement_clips", []):
            section_index = ac.get("section_index")
            if section_index is None or section_index >= len(form):
                errors.append({
                    "track_index": track_index,
                    "phase": "arrangement_clip",
                    "reason": f"invalid section_index {section_index}",
                })
                continue
            section = form[section_index]
            variant_id = ac.get("variant_id")
            slot = variant_id_to_slot.get(variant_id)
            if slot is None:
                errors.append({
                    "track_index": track_index,
                    "phase": "arrangement_clip",
                    "reason": f"unknown variant_id {variant_id!r}",
                })
                continue
            start_bar = float(section["start_bar"])
            bars = float(section["bars"])
            loop_length = float(ac.get("loop_length", 4.0))
            try:
                ableton.send_command("create_arrangement_clip", {
                    "track_index": track_index,
                    "clip_slot_index": slot,
                    "start_time": start_bar * 4.0,  # bars → beats at 4/4
                    "length": bars * 4.0,
                    "loop_length": loop_length,
                })
                arrangement_clips_created += 1
            except Exception as exc:
                errors.append({
                    "track_index": track_index,
                    "phase": "arrangement_clip",
                    "reason": str(exc),
                })

    # Events — Phase 4 will populate real apply paths; Phase 3 stubs this
    for _event in plan.get("events", []):
        pass  # Phase 3 no-op — events accepted but not applied

    # Postflight — sets monitoring=In on new tracks + back_to_arranger
    postflight_result = await applier.postflight(
        ctx,
        applied_track_indices=applied_track_indices,
    )

    ok_count = variants_created + arrangement_clips_created
    status = "ok" if not errors else ("partial" if ok_count > 0 else "error")

    return {
        "status": status,
        "tracks_created": tracks_created,
        "variants_created": variants_created,
        "arrangement_clips_created": arrangement_clips_created,
        "events_applied": events_applied,
        "preflight": preflight_result,
        "postflight": postflight_result,
        "errors": errors,
        "duration_ms": int((time.time() - started) * 1000),
    }
