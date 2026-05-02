"""Fast compose Phase-3 executor — applies agent-designed plan to live session."""

from __future__ import annotations

import logging
import time

from fastmcp import Context

from .. import fast as fast_compose
from ..framework.applier import Applier

logger = logging.getLogger(__name__)

# ── v1.24 Phase 4 Tasks 18b + 18d: post-load repair helpers ────────

DRUM_ROLES = frozenset({"kick", "snare", "hat", "perc", "clap", "tom", "drum"})


def _is_drum_role(role: str) -> bool:
    """True if the role belongs to the drum family — gets role-default repair."""
    return role.lower() in DRUM_ROLES


def _detect_silent_load(ableton, track_index: int, device_index: int = 0) -> tuple:
    """Detect if the loaded device is silently misconfigured (empty container).

    Returns (is_silent: bool, reason: str).
    """
    try:
        device_info = ableton.send_command("get_device_info", {
            "track_index": track_index, "device_index": device_index,
        })
    except Exception:
        return False, ""

    class_name = device_info.get("class_name", "")
    name = device_info.get("name", "")

    # DrumCell with no sample loaded — bare "Drum Sampler" container URI
    if class_name == "DrumCell" and name == "Drum Sampler":
        return True, "DrumCell loaded as bare 'Drum Sampler' container — needs sample inside"

    # Simpler with Sample Length near zero
    if class_name == "OriginalSimpler":
        try:
            params_resp = ableton.send_command("get_device_parameters", {
                "track_index": track_index, "device_index": device_index,
            })
            for p in params_resp.get("parameters", []):
                if p["name"] == "Sample Length" and p["value"] < 0.001:
                    return True, "Simpler has no sample loaded (Sample Length=0)"
        except Exception:
            pass

    # Drum Rack loaded as bare container
    if class_name == "DrumGroupDevice" and name == "Drum Rack":
        return True, "Drum Rack loaded as bare container — no kit pads"

    return False, ""


def _apply_drum_role_repair(ableton, track_index: int, device_index: int = 0) -> dict:
    """Apply role-default repair to a drum-role layer's instrument.

    Defense in depth: load_browser_item's role='drum' silently fails to
    apply these defaults when the track has audio effects. This function
    re-applies them deterministically post-load.

    Device-class-aware:
    - For OriginalSimpler (sample-trigger): set Volume=0, Snap=Off, Transpose=+24
      (Transpose compensates for Simpler's default C3=60 root vs drum-rack convention C1=36).
    - For other drum devices (DS Kick, Drum Rack, Impulse, etc.): only attempt Volume=0
      since they don't have Snap/Transpose params (would error otherwise).

    BUG-FIX (post-Task-18d live test): Remote Script's batch_set_parameters
    accepts `name_or_index` (legacy field), NOT `parameter_name`. Wrapper
    docs claim both are supported but actual Remote Script reads only
    name_or_index. Using parameter_name caused "Parameter 'None' not found"
    errors. Always use name_or_index for compatibility.

    Returns the repair result dict with per-param status.
    """
    # Detect device class so we apply class-appropriate params
    try:
        device_info = ableton.send_command("get_device_info", {
            "track_index": track_index, "device_index": device_index,
        })
        class_name = device_info.get("class_name", "")
    except Exception as exc:
        return {"applied": False, "error": f"get_device_info failed: {exc}"}

    # Build the param list — Volume always; Snap+Transpose only for Simpler
    params_to_set = [{"name_or_index": "Volume", "value": 0}]
    if class_name == "OriginalSimpler":
        params_to_set.extend([
            {"name_or_index": "Snap", "value": 0},
            {"name_or_index": "Transpose", "value": 24},
        ])

    try:
        result = ableton.send_command("batch_set_parameters", {
            "track_index": track_index,
            "device_index": device_index,
            "parameters": params_to_set,
        })
        return {
            "applied": True,
            "device_class": class_name,
            "params": result.get("parameters", []),
        }
    except Exception as exc:
        return {"applied": False, "device_class": class_name, "error": str(exc)}


async def apply_fast_plan(
    ctx: Context,
    plan: dict,
) -> dict:
    """Phase-3 fast mode: server-side execute the agent's creative plan.

    Plan shape:
        {
          "layers": [
            {
              "role": "kick" | "snare" | ...,
              "uri": "atlas URI",
              "track_name": "optional display name",
              "notes": [{"pitch": int, "start_time": float, "duration": float, "velocity": int}, ...]
            },
            ...
          ],
          "scene_index": int | null,
          "bars": int (optional, defaults to inferred from notes),
          "tempo": int (optional, sets tempo if not already set),
        }

    Returns: tracks_created, scene_fired, per-layer load+note status.
    """
    started = time.time()
    ableton = ctx.lifespan_context.get("ableton") if hasattr(ctx, "lifespan_context") else None
    if ableton is None:
        return {"error": "Ableton connection not available", "phase": "apply"}

    layers = plan.get("layers") or []
    if not layers:
        return {"error": "plan.layers is empty — nothing to apply", "phase": "apply"}

    # ── Pre-flight: bridge handshake (BUG-FULL-MODE-14 parity) ────────
    # Fast mode doesn't use the bridge directly, but running preflight
    # ensures the bridge is warm for any tools that run afterward in the
    # same session. Non-fatal: if bridge isn't available, we log and continue
    # since the fast-mode layer loop uses only direct TCP commands.
    try:
        from ...tools.analyzer import (
            ensure_analyzer_on_master as _ensure_analyzer,
            reconnect_bridge as _reconnect_bridge,
        )
        from ...tools._analyzer_engine.context import _get_m4l

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

        applier = Applier(
            ensure_analyzer_fn=_ensure_analyzer_async,
            reconnect_bridge_fn=_reconnect_bridge_async,
            bridge_ping_fn=_bridge_ping_async,
        )
        preflight_result = await applier.preflight(ctx)
        if not preflight_result.get("bridge_connected"):
            logger.debug(
                "fast apply: bridge not ready (attempts=%d) — continuing without bridge",
                preflight_result.get("handshake_attempts", 0),
            )
    except Exception as exc:
        logger.debug("fast apply: preflight failed (bridge unavailable): %s", exc)

    # Pre-flight: where do new tracks go, and which scene?
    session = ableton.send_command("get_session_info", {})
    starting_track_count = int(session.get("track_count", 0))
    scene_count = int(session.get("scene_count", 0))

    # Optional tempo override
    if plan.get("tempo"):
        try:
            ableton.send_command("set_tempo", {"tempo": float(plan["tempo"])})
        except Exception as exc:
            logger.debug("apply: set_tempo failed: %s", exc)

    # Pick the target scene
    target_scene = plan.get("scene_index")
    if target_scene is None:
        scenes = session.get("scenes", []) or []
        target_scene = next(
            (i for i, s in enumerate(scenes) if not s.get("name")),
            None,
        )
        if target_scene is None or target_scene >= scene_count:
            target_scene = max(0, scene_count - 1)
    target_scene = int(target_scene)

    # Phase B: build return-name → send_index map up front so layers can name
    # returns ("A-Reverb") instead of remembering integer send indices.
    return_name_to_send_index: dict[str, int] = {}
    try:
        returns_resp = ableton.send_command("get_return_tracks", {}) or {}
        for i, rt in enumerate(returns_resp.get("return_tracks", []) or []):
            name = (rt.get("name") or "").strip()
            if name:
                return_name_to_send_index[name.lower()] = i
    except Exception as exc:
        logger.debug("apply: get_return_tracks failed: %s", exc)

    layer_results: list[dict] = []
    new_track_indices: list[int] = []

    for layer in layers:
        role = (layer.get("role") or "").strip()
        uri = (layer.get("uri") or "").strip()
        # BUG-N normalization (2026-05-01): search_browser returns URIs with
        # literal `&` (e.g. "Sounds#Ambient & Evolving"), but agents may
        # double-encode it to %26 thinking it's URL-spec — which makes the
        # exact-match URI walk in load_browser_item miss the file. Normalize
        # %26 → & and %2526 → & so URIs always match the form Live's browser
        # exposes, regardless of how the agent encoded them.
        if uri:
            uri = uri.replace("%2526", "&").replace("%26", "&")
        track_name = layer.get("track_name") or role.upper() or f"Layer {len(new_track_indices) + 1}"
        notes = layer.get("notes") or []

        new_track_idx = starting_track_count + len(new_track_indices)
        try:
            ableton.send_command("create_midi_track", {"index": -1, "name": track_name})
        except Exception as exc:
            logger.warning("apply: create_midi_track(%s) failed: %s", track_name, exc)
            layer_results.append({
                "role": role, "track_name": track_name, "ok": False,
                "error": f"create_midi_track failed: {exc}",
            })
            continue
        new_track_indices.append(new_track_idx)

        loaded = False
        silent_load_warning: str | None = None
        role_repair: dict | None = None

        if uri:
            simpler_role = fast_compose.simpler_role_for(role)
            try:
                load_params: dict = {"track_index": new_track_idx, "uri": uri}
                if simpler_role:
                    load_params["role"] = simpler_role
                ableton.send_command("load_browser_item", load_params)
                loaded = True
            except Exception as exc:
                logger.debug("apply: load_browser_item(%s, %s) failed: %s", new_track_idx, uri, exc)

            if loaded:
                # v1.24 Phase 4 Task 18b: detect empty containers post-load
                is_silent, silent_reason = _detect_silent_load(ableton, new_track_idx, device_index=0)
                if is_silent:
                    silent_load_warning = silent_reason
                    logger.warning(
                        "apply: silent load detected for role=%s track=%s: %s",
                        role, new_track_idx, silent_reason,
                    )

                # v1.24 Phase 4 Task 18d: drum role-default repair (defense in depth)
                # load_browser_item role='drum' silently skips Vol/Snap/root fixes
                # when the track already has FX. Re-apply deterministically.
                if _is_drum_role(role):
                    role_repair = _apply_drum_role_repair(ableton, new_track_idx, device_index=0)
                    if not role_repair.get("applied"):
                        logger.debug(
                            "apply: drum role repair failed for track %s: %s",
                            new_track_idx, role_repair.get("error"),
                        )

        # Determine clip length: max of (4 bars × 4 beats, end of last note + 1)
        max_end = 0.0
        for n in notes:
            try:
                end = float(n.get("start_time", 0)) + float(n.get("duration", 0))
                max_end = max(max_end, end)
            except (TypeError, ValueError):
                pass
        bars = int(plan.get("bars") or 4)
        clip_length_beats = max(bars * 4, int(max_end) + 1) if notes else bars * 4

        try:
            ableton.send_command("create_clip", {
                "track_index": new_track_idx,
                "clip_index": target_scene,
                "length": float(clip_length_beats),
            })
        except Exception as exc:
            logger.warning("apply: create_clip(%s) failed: %s", role, exc)
            layer_results.append({
                "role": role, "track_index": new_track_idx, "uri": uri, "loaded": loaded,
                "ok": False, "error": f"create_clip failed: {exc}",
            })
            continue

        notes_added = 0
        if notes:
            try:
                ableton.send_command("add_notes", {
                    "track_index": new_track_idx,
                    "clip_index": target_scene,
                    "notes": notes,
                })
                notes_added = len(notes)
            except Exception as exc:
                logger.warning("apply: add_notes(%s) failed: %s", role, exc)

        # Phase B (2026-05-01): per-layer effect chain. Each effect inserts
        # one native Live device on the track and (optionally) sets a few
        # of its parameters. Failures are logged per-effect — the layer
        # still succeeds even if one effect doesn't load.
        effects_applied: list[dict] = []
        for fx in layer.get("effects") or []:
            device_name = (fx.get("device") or "").strip()
            if not device_name:
                continue
            try:
                ins_resp = ableton.send_command("insert_device", {
                    "track_index": new_track_idx,
                    "device_name": device_name,
                }) or {}
                device_index = ins_resp.get("device_index")
                params_set: list[dict] = []
                params_failed: list[dict] = []
                if device_index is not None:
                    for pname, pvalue in (fx.get("params") or {}).items():
                        try:
                            ableton.send_command("set_device_parameter", {
                                "track_index": new_track_idx,
                                "device_index": int(device_index),
                                "parameter_name": str(pname),
                                "value": float(pvalue),
                            })
                            params_set.append({"name": str(pname), "value": float(pvalue)})
                        except Exception as exc:
                            logger.debug(
                                "apply: set_device_parameter(%s.%s=%s) failed: %s",
                                device_name, pname, pvalue, exc,
                            )
                            params_failed.append({"name": str(pname), "error": str(exc)})
                effects_applied.append({
                    "device": device_name,
                    "device_index": device_index,
                    "params_set": params_set,
                    "params_failed": params_failed,
                    "ok": True,
                })
            except Exception as exc:
                logger.warning("apply: insert_device(%s) on track %s failed: %s",
                               device_name, new_track_idx, exc)
                effects_applied.append({
                    "device": device_name,
                    "ok": False,
                    "error": str(exc),
                })

        # Phase B: per-layer sends. Each entry is {return_name | send_index, value}.
        # Names are case-insensitive; if the return doesn't exist, we record
        # the miss and continue.
        sends_applied: list[dict] = []
        for snd in layer.get("sends") or []:
            try:
                value = float(snd.get("value", 0.0))
            except (TypeError, ValueError):
                continue
            send_index = snd.get("send_index")
            return_name = (snd.get("return_name") or "").strip()
            if send_index is None and return_name:
                send_index = return_name_to_send_index.get(return_name.lower())
            if send_index is None:
                sends_applied.append({
                    "return_name": return_name or None,
                    "ok": False,
                    "error": "return track not found",
                })
                continue
            try:
                ableton.send_command("set_track_send", {
                    "track_index": new_track_idx,
                    "send_index": int(send_index),
                    "value": value,
                })
                sends_applied.append({
                    "return_name": return_name or None,
                    "send_index": int(send_index),
                    "value": value,
                    "ok": True,
                })
            except Exception as exc:
                logger.debug("apply: set_track_send(%s, %s, %s) failed: %s",
                             new_track_idx, send_index, value, exc)
                sends_applied.append({
                    "return_name": return_name or None,
                    "send_index": int(send_index) if send_index is not None else None,
                    "value": value,
                    "ok": False,
                    "error": str(exc),
                })

        # Tier-1C: pass through any applied_technique attribution from the
        # agent's plan — surfaced in the response's techniques_used array
        # so the user sees provenance per layer.
        applied_technique = layer.get("applied_technique") or None

        layer_entry: dict = {
            "role": role,
            "track_name": track_name,
            "track_index": new_track_idx,
            "uri": uri,
            "loaded": loaded,
            "notes_added": notes_added,
            "clip_length_beats": clip_length_beats,
            "effects_applied": effects_applied,
            "sends_applied": sends_applied,
            "applied_technique": applied_technique,
            "ok": True,
        }
        if silent_load_warning:
            layer_entry["silent_load_warning"] = silent_load_warning
            layer_entry["warnings"] = [silent_load_warning]
        if role_repair is not None:
            layer_entry["role_repair"] = role_repair
        layer_results.append(layer_entry)

    # Fire the scene
    fired = False
    try:
        ableton.send_command("fire_scene", {"scene_index": target_scene})
        fired = True
    except Exception as exc:
        logger.warning("apply: fire_scene(%s) failed: %s", target_scene, exc)

    # Final fresh-project cleanup: delete the leftover default track if
    # the brief left one in place to satisfy Ableton's "≥1 track" guard.
    final_cleanup_actions: list[str] = []
    new_session = ableton.send_command("get_session_info", {})
    final_tracks = new_session.get("tracks", []) or []
    # If track 0 is still default-named and empty, AND we just added new
    # tracks, prune it now (we have ≥2 tracks total, safe to delete).
    if final_tracks and len(final_tracks) > 1:
        first = final_tracks[0]
        if fast_compose.is_default_track_name(first.get("name", "")):
            try:
                ti0 = ableton.send_command("get_track_info", {"track_index": 0})
                if fast_compose.track_is_empty(ti0):
                    ableton.send_command("delete_track", {"track_index": 0})
                    final_cleanup_actions.append("deleted_leftover_default_track")
                    # All track indices shift down by 1
                    new_track_indices = [i - 1 for i in new_track_indices]
                    for r in layer_results:
                        if r.get("ok") and isinstance(r.get("track_index"), int):
                            r["track_index"] = r["track_index"] - 1
            except Exception as exc:
                logger.debug("apply: final cleanup failed: %s", exc)

    # Tier-1C: aggregate per-layer applied_technique attributions into a
    # top-level techniques_used summary the user sees alongside the build.
    techniques_used = [
        {
            "role": r.get("role"),
            "track_index": r.get("track_index"),
            "snippet": (r.get("applied_technique") or {}).get("snippet"),
            "source": (r.get("applied_technique") or {}).get("source"),
            "source_url": (r.get("applied_technique") or {}).get("source_url"),
            "applied_in": (r.get("applied_technique") or {}).get("applied_in"),
        }
        for r in layer_results
        if r.get("applied_technique")
    ]

    # Phase B: aggregate effect + send totals across layers for the summary.
    total_effects_loaded = sum(
        1
        for r in layer_results
        for fx in (r.get("effects_applied") or [])
        if fx.get("ok")
    )
    total_effects_failed = sum(
        1
        for r in layer_results
        for fx in (r.get("effects_applied") or [])
        if not fx.get("ok")
    )
    total_sends_set = sum(
        1
        for r in layer_results
        for s in (r.get("sends_applied") or [])
        if s.get("ok")
    )

    duration_ms = int((time.time() - started) * 1000)
    return {
        "phase": "apply",
        "tracks_created": len(new_track_indices),
        "track_indices": new_track_indices,
        "scene_fired": target_scene if fired else None,
        "layers": layer_results,
        "techniques_used": techniques_used,
        "effects_loaded": total_effects_loaded,
        "effects_failed": total_effects_failed,
        "sends_set": total_sends_set,
        "final_cleanup_actions": final_cleanup_actions,
        "duration_ms": duration_ms,
        "summary": (
            f"{len(new_track_indices)} tracks created, "
            f"{sum(1 for r in layer_results if r.get('loaded'))} instruments loaded, "
            f"{total_effects_loaded} effects loaded, "
            f"{total_sends_set} sends set, "
            f"scene {target_scene} {'fired' if fired else 'NOT fired'}, "
            f"{len(techniques_used)} technique(s) attributed"
        ),
    }
