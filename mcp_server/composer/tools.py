"""Composer Engine MCP tools — 4 tools for auto-composition.

compose: full multi-layer composition from text prompt
augment_with_samples: add layers to existing session
get_composition_plan: dry run preview
propose_composer_branches (PR5/v2): multi-strategy branch hypotheses for
    exploratory workflows (feeds create_experiment(seeds=...))
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp
from .prompt_parser import parse_prompt
from .engine import ComposerEngine
from . import fast as fast_compose
import logging
import time

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


def _build_fast_brief(
    ctx: Context, intent, bars: int, reference: str | None = None,
) -> dict:
    """Phase-1 fast mode (2026-05-01 redesign per user feedback).

    Returns a CREATIVE BRIEF for the agent to read and design a layer plan
    around. Does fresh-project cleanup (analyzer load + default-track
    delete) and tempo set up front so the agent can focus on creative
    content. Does NOT generate any patterns or load any instruments — the
    agent picks instruments from instruments_by_role and writes notes
    inline, then submits the plan to compose_fast_apply.

    `reference` (Tier 2): when set (e.g. "Ricardo Villalobos"), the brief
    includes artist-specific search queries the agent fires against the
    Ableton Knowledge MCP to design USING that artist's techniques.
    """
    started = time.time()
    ableton = ctx.lifespan_context.get("ableton") if hasattr(ctx, "lifespan_context") else None
    if ableton is None:
        return {"error": "Ableton connection not available", "phase": "brief"}

    # Pre-flight: read the session
    session = ableton.send_command("get_session_info", {})
    starting_track_count = int(session.get("track_count", 0))

    # Fresh-project detection + cleanup. Identify default tracks; load the
    # analyzer on master proactively; queue defaults for deletion. We
    # delete BEFORE returning the brief so the agent's apply-step lands
    # cleanly without leftover MIDI 1 / Audio 1 tracks.
    fresh_project = False
    fresh_actions: list[str] = []
    if fast_compose.detect_fresh_project(session):
        candidates: list[int] = []
        for i in range(starting_track_count):
            try:
                ti = ableton.send_command("get_track_info", {"track_index": i})
                if fast_compose.track_is_empty(ti):
                    candidates.append(i)
            except Exception as exc:
                logger.debug("fast: fresh-check get_track_info(%s) failed: %s", i, exc)
        if len(candidates) == starting_track_count and starting_track_count > 0:
            fresh_project = True
            fresh_actions.append(f"detected_fresh_project_{starting_track_count}_default_tracks")
            # Load analyzer on master proactively
            try:
                from ..tools.analyzer import ensure_analyzer_on_master as _ensure_analyzer
                _ensure_analyzer(ctx)
                fresh_actions.append("analyzer_loaded_on_master")
            except Exception as exc:
                logger.debug("fast: ensure_analyzer_on_master failed: %s", exc)
            # Delete defaults in reverse order. We can't delete the LAST
            # track (Ableton requires ≥1), so leave one default in place;
            # the agent's compose_fast_apply will add new tracks first,
            # then we'll prune the leftover survivor in apply.
            deletable = sorted(candidates, reverse=True)[:-1]   # leave 1
            deleted_count = 0
            for idx in deletable:
                try:
                    ableton.send_command("delete_track", {"track_index": idx})
                    deleted_count += 1
                except Exception as exc:
                    logger.debug("fast: delete_track(%s) failed: %s", idx, exc)
            if deleted_count:
                fresh_actions.append(f"deleted_{deleted_count}_default_tracks")

    # Set tempo proactively (so the agent's plan plays at the right BPM)
    tempo_set = False
    if intent.tempo and intent.tempo > 0:
        try:
            ableton.send_command("set_tempo", {"tempo": float(intent.tempo)})
            tempo_set = True
        except Exception as exc:
            logger.debug("fast: set_tempo failed: %s", exc)

    # Atlas access for instrument candidates
    atlas_obj = None
    try:
        from ..atlas import tools as atlas_module
        atlas_obj = atlas_module._get_atlas()
    except Exception as exc:
        logger.debug("fast: atlas access failed: %s", exc)

    # Anti-repeat: read all currently-loaded device names from the session
    # so the brief picker can bias candidates AWAY from already-used devices.
    # User feedback 2026-05-01: Tree Tone always wins for pad → boring.
    post_cleanup_session = ableton.send_command("get_session_info", {})
    loaded_device_names: set[str] = set()
    track_count_after_cleanup = int(post_cleanup_session.get("track_count", 0))
    for i in range(track_count_after_cleanup):
        try:
            ti = ableton.send_command("get_track_info", {"track_index": i})
            for dev in (ti.get("devices") or []):
                n = dev.get("name") or ""
                if n:
                    loaded_device_names.add(n)
        except Exception as exc:
            logger.debug("fast: anti-repeat read failed for track %s: %s", i, exc)

    fresh_state = {
        "detected": fresh_project,
        "actions_taken": fresh_actions,
        "tempo_set": tempo_set,
        "starting_track_count_after_cleanup": track_count_after_cleanup,
    }

    brief = fast_compose.build_creative_brief(
        intent=intent,
        atlas=atlas_obj,
        fresh_project_state=fresh_state,
        bars=bars,
        reference=reference,
        exclude_loaded_device_names=loaded_device_names,
    )
    brief["duration_ms"] = int((time.time() - started) * 1000)
    return brief


def _apply_fast_plan(
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

        layer_results.append({
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
        })

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


@mcp.tool()
async def compose(
    ctx: Context,
    prompt: str,
    mode: str = "full",
    bars: int = 4,
    target_scene: Optional[int] = None,
    max_credits: int = 50,
    dry_run: bool = False,
    reference: Optional[str] = None,
) -> dict:
    """Plan, brief, or execute a multi-layer composition from a text prompt.

    Two modes:

    ``mode="full"`` (default) — plan-only. Parses prompt into genre/mood/
    tempo/key, plans layers using role templates, returns an executable
    plan of tool calls for the agent to step through. This is the rich
    composition path.

    ``mode="fast"`` — **LLM-creative two-phase flow** (2026-05-01 redesign):
        Phase 1 (this call): returns a CREATIVE BRIEF with parsed intent,
        atlas-filtered instrument candidates per role, scale-pitch context,
        genre creative guidance. Does NOT generate any musical content.
        Pre-flight handles fresh-project detection, analyzer load, default-
        track cleanup, and tempo set so the agent can focus on creativity.

        Phase 2 (agent's job): read the brief, pick instruments creatively
        from instruments_by_role, design MIDI notes inline (genuinely fresh
        per call, not from templates), submit a complete plan to
        ``compose_fast_apply``.

        Phase 3 (compose_fast_apply): server-side execute the plan — create
        tracks, load instruments, populate clips with the agent's notes,
        fire scene.

    prompt: "dark minimal techno 128bpm" / "downtempo lo-fi Cm" / "trap"
    mode: "full" | "fast"
    bars: clip length in bars (fast mode only — default 4)
    target_scene: scene index to populate (full mode legacy param; fast
                  mode now lets the agent pick via compose_fast_apply)
    max_credits: max Splice credits budget for full-mode plans (default 50)
    dry_run: full-mode only — skip credit checks

    Fast mode returns: a brief dict with creative context. Call
    compose_fast_apply with your designed plan to actually create tracks.
    Full mode returns the existing plan dict.
    """
    intent = parse_prompt(prompt)

    if mode == "fast":
        brief = _build_fast_brief(
            ctx, intent, bars=int(bars), reference=reference,
        )
        brief["prompt"] = prompt
        return brief

    # mode == "full" — preserve original behavior
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
    output["mode"] = "full"

    if credits_remaining is not None:
        output["credits_remaining"] = credits_remaining
        output["credits_budget"] = max_credits

    return output


@mcp.tool()
def compose_fast_apply(ctx: Context, plan: dict) -> dict:
    """Phase-3 of the LLM-creative fast mode (2026-05-01).

    Receives a complete layer plan designed by the agent (informed by
    the brief returned from ``compose(mode="fast")``) and bulk-executes
    it server-side: creates MIDI tracks, loads instruments by URI,
    creates clips, populates them with the agent's notes, fires the
    scene. ALL underlying TCP commands run in this single call so the
    agent doesn't pay round-trip cost between create_track / load /
    clip / notes.

    Plan shape:
        {
          "layers": [
            {
              "role": "kick" | "snare" | "hat" | "perc" | "clap" | "bass" |
                      "pad" | "lead" | "atmos" | "vox" | "fx",
              "uri": "atlas URI from brief.instruments_by_role[role]",
              "track_name": "optional display name (defaults to ROLE)",
              "notes": [
                {"pitch": int 0-127, "start_time": float beats from clip start,
                 "duration": float beats, "velocity": int 0-127},
                ...
              ],
              # Phase B (2026-05-01): native-device effect chain on this
              # track, applied AFTER the instrument loads. Each entry
              # inserts one device (insert_device — 12.3+ API) and
              # optionally sets a few of its parameters.
              # Brief.creative_guidance.effect_chain_hints[role] is a
              # canonical starting point, but the agent should adapt
              # values to fit the prompt's mood (subtler in ambient,
              # heavier in trap, etc.).
              "effects": [
                {"device": "Saturator", "params": {"Drive": 0.4}},
                {"device": "EQ Eight", "params": {}},
                ...
              ],
              # Phase B: track sends. return_name is case-insensitive;
              # if no return matches, the entry is skipped (no fail).
              "sends": [
                {"return_name": "A-Reverb", "value": 0.25},
                {"send_index": 1, "value": 0.10},
                ...
              ]
            },
            ...
          ],
          "scene_index": int or null  (auto-pick first empty if null),
          "bars": int  (clip length, default 4),
          "tempo": int or null  (skip if already set in brief)
        }

    The agent should design notes creatively per call — don't reuse a
    template. Variation is the whole point of this two-phase flow.

    Returns: tracks_created, scene_fired, per-layer load+note status,
    effects_loaded + sends_set totals, plus techniques_used aggregating
    each layer's applied_technique (Tier-1C) so the user sees per-layer
    provenance: what producer-voice snippet from which Ableton tutorial
    informed each layer's design.
    """
    return _apply_fast_plan(ctx, plan)


@mcp.tool()
def consult_ableton_knowledge(
    ctx: Context,
    question: str,
    session_context: Optional[dict] = None,
) -> dict:
    """Tier-3: Ableton Knowledge consultation orchestrator.

    Takes a free-text production question + optional session context,
    returns a structured consultation plan: which Ableton Knowledge MCP
    tools to fire (search_transcripts / search_live_manual / search_videos /
    search_knowledge_base), with what queries, in what order, plus a
    synthesis template for the agent to combine the results into a
    direct answer for the user.

    The agent runs the recommended searches inline, synthesizes per the
    template, and surfaces sources alongside the answer.

    Examples:
      consult_ableton_knowledge("how do I make my kick punchier?")
        → plan: [search_live_manual("Saturator"), search_transcripts("kick punch"),
                 search_videos("kick design tutorial")] + synthesis template
      consult_ableton_knowledge("what's the difference between Operator and Wavetable?")
        → plan: [search_live_manual("Operator"), search_live_manual("Wavetable"),
                 search_transcripts("Operator vs Wavetable")]

    session_context (optional): {
        "current_genre": "techno",
        "current_key": "Am",
        "tracks": [{role, instrument}, ...]
    } — informs query specificity (e.g. "kick punch" becomes "techno kick punch").

    Returns:
        {
            "question": str,
            "intent_classification": "sound_design" | "arrangement" | "mixing" | "device" | "general",
            "search_plan": [{tool, query, why}, ...],
            "synthesis_template": str,
            "expected_response_shape": dict,
        }
    """
    q = (question or "").strip()
    if not q:
        return {
            "error": "question is empty",
            "question": question,
        }

    sc = session_context or {}
    genre = (sc.get("current_genre") or "").strip().lower()

    # Lightweight intent classification — keyword-based, deliberately
    # simple so this tool is fast and predictable.
    q_lower = q.lower()
    intent_class = _classify_consultation_intent(q_lower)

    # Build a search plan keyed off intent + question keywords + genre context
    plan = _build_consultation_plan(q, q_lower, intent_class, genre)

    synthesis_template = (
        "After firing the searches in `search_plan`, synthesize a 2-3 paragraph answer that:\n"
        "1. Directly answers the question (lead with the answer, not history).\n"
        "2. Cites 1-2 specific snippets from the search results inline.\n"
        "3. Lists the source URLs/sections alongside the answer.\n"
        "4. If session_context is given, tailor the answer to that genre/key/setup.\n"
        "5. Suggest 1 concrete next experiment the user could try in their session."
    )

    return {
        "question": q,
        "intent_classification": intent_class,
        "session_context_used": bool(session_context),
        "genre_context": genre or None,
        "search_plan": plan,
        "synthesis_template": synthesis_template,
        "expected_response_shape": {
            "answer": "2-3 paragraph synthesis",
            "sources": [{"title": "...", "url": "...", "snippet": "..."}],
            "next_experiment": "concrete suggestion",
        },
        "next_step": (
            "Run each search in `search_plan` in order via the Ableton Knowledge "
            "MCP tools. Synthesize per `synthesis_template`. Surface sources to "
            "the user. If session_context was given, tailor the answer to it."
        ),
    }


# Lightweight keyword classifier for the consultation tool. Deliberately
# simple — Ableton Knowledge MCP does the heavy lifting; this just routes
# the question to the right starting tool set.
_CONSULTATION_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sound_design": (
        "kick", "snare", "hat", "drum", "bass", "pad", "lead", "808",
        "saturate", "saturation", "compress", "sidechain", "punch",
        "warm", "bright", "thick", "thin",
    ),
    "device": (
        "operator", "wavetable", "drift", "analog", "simpler", "sampler",
        "auto filter", "echo", "reverb", "compressor", "saturator",
        "eq eight", "frequency shifter", "redux", "corpus", "tension",
        "max for live", "m4l",
    ),
    "arrangement": (
        "arrangement", "structure", "verse", "chorus", "drop", "build",
        "transition", "intro", "outro", "section",
    ),
    "mixing": (
        "mix", "balance", "level", "pan", "stereo", "width", "loud",
        "loudness", "lufs", "master", "mastering", "headroom",
    ),
    "rhythm": (
        "swing", "groove", "humanize", "shuffle", "syncopat", "polyrhythm",
        "ghost note",
    ),
    "harmony": (
        "chord", "progression", "scale", "mode", "minor", "major",
        "voice lead", "voicing",
    ),
}


def _classify_consultation_intent(q_lower: str) -> str:
    """Return the most likely intent class for a consultation question.

    Uses whole-word matching for single-word keywords to avoid the
    classic substring-trap (e.g. "hat" matching inside "what"). Multi-
    word keywords like "auto filter" use plain substring match because
    whitespace already provides word boundaries.
    """
    import re
    scores: dict[str, int] = {}
    words = set(re.findall(r"\b[\w-]+\b", q_lower))
    for cls, keywords in _CONSULTATION_INTENT_KEYWORDS.items():
        for kw in keywords:
            kw_lower = kw.lower()
            if " " in kw_lower:
                # Multi-word keyword: substring match is safe
                if kw_lower in q_lower:
                    scores[cls] = scores.get(cls, 0) + 1
            else:
                # Single-word keyword: whole-word match avoids "hat" in "what"
                if kw_lower in words:
                    scores[cls] = scores.get(cls, 0) + 1
    if not scores:
        return "general"
    return max(scores.items(), key=lambda kv: kv[1])[0]


def _build_consultation_plan(
    q: str, q_lower: str, intent_class: str, genre: str,
) -> list[dict]:
    """Build the ordered search plan based on intent classification.

    Returns a list of {tool, query, why} entries the agent fires in
    sequence to gather evidence before synthesizing.
    """
    plan: list[dict] = []
    genre_prefix = f"{genre} " if genre else ""

    if intent_class == "device":
        plan.append({
            "tool": "search_live_manual",
            "query": q,
            "why": "device-specific question — official manual is authoritative",
        })
        plan.append({
            "tool": "search_videos",
            "query": q,
            "why": "Ableton's tutorial videos cover device usage in depth",
        })
        plan.append({
            "tool": "search_transcripts",
            "query": q,
            "why": "transcript semantic search may surface specific use cases",
        })
    elif intent_class == "sound_design":
        plan.append({
            "tool": "search_transcripts",
            "query": f"{genre_prefix}{q}",
            "why": "producer-voice technique snippets are the most useful here",
        })
        plan.append({
            "tool": "search_videos",
            "query": f"{genre_prefix}{q} tutorial",
            "why": "tutorial videos for hands-on technique",
        })
        plan.append({
            "tool": "search_knowledge_base",
            "query": q,
            "why": "support articles often have step-by-step recipes",
        })
    elif intent_class == "arrangement":
        plan.append({
            "tool": "search_transcripts",
            "query": f"{genre_prefix}{q} arrangement",
            "why": "arrangement is often discussed in long-form video content",
        })
        plan.append({
            "tool": "search_videos",
            "query": f"{genre_prefix}arrangement structure",
            "why": "arrangement-specific tutorials",
        })
    elif intent_class == "mixing":
        plan.append({
            "tool": "search_transcripts",
            "query": q,
            "why": "mixing techniques live in producer videos",
        })
        plan.append({
            "tool": "search_live_manual",
            "query": q,
            "why": "manual covers Live's mixing tools (EQ Eight, Compressor, etc.)",
        })
        plan.append({
            "tool": "search_knowledge_base",
            "query": q,
            "why": "support articles have mixing tips",
        })
    elif intent_class == "rhythm":
        plan.append({
            "tool": "search_transcripts",
            "query": f"{genre_prefix}{q}",
            "why": "groove/rhythm techniques are best from producer voices",
        })
        plan.append({
            "tool": "search_live_manual",
            "query": "groove pool",
            "why": "Live has a Groove Pool — manual is authoritative",
        })
    elif intent_class == "harmony":
        plan.append({
            "tool": "search_transcripts",
            "query": f"{genre_prefix}{q}",
            "why": "harmonic techniques from real producer examples",
        })
        plan.append({
            "tool": "search_videos",
            "query": "music theory chord progression",
            "why": "Ableton's theory-adjacent tutorials",
        })
    else:
        # General fallback
        plan.append({
            "tool": "search_transcripts",
            "query": q,
            "why": "general semantic search across producer voice content",
        })
        plan.append({
            "tool": "search_knowledge_base",
            "query": q,
            "why": "support articles for direct answers",
        })

    return plan


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


@mcp.tool()
def propose_composer_branches(
    ctx: Context,
    request_text: str,
    count: int = 2,
    freshness: float = 0.65,
) -> dict:
    """Emit N distinct compositional hypotheses for a single prompt (PR5/v2).

    Branch-native companion to compose(): instead of one deterministic
    layer plan, produces up to ``count`` BranchSeeds with different
    strategic angles the user can audition via create_experiment +
    run_experiment. Each seed carries a pre-compiled scaffolding plan
    (set_tempo + create_midi_track per layer + create_scene per section)
    that gets escalated to a fully resolved plan by commit_experiment
    when the winning branch is chosen.

    Strategies (gated on freshness):
      canonical      — intent unchanged, genre defaults
                       (shipped at every freshness level)
      energy_shift   — intent.energy inverted around 0.5
                       (freshness >= 0.4)
      layer_contrast — one role swapped (pad-anchor instead of bass)
                       (freshness >= 0.7)

    Returns:
      {
        "request_text": str,
        "branch_count": int,
        "seeds": [BranchSeed.to_dict(), ...],
        "compiled_plans": [plan_dict, ...]   (parallel to seeds; scaffold),
      }

    Each seed's producer_payload carries {strategy, intent,
    request_text, reason} so commit_experiment can rehydrate the
    CompositionIntent and run the full ComposerEngine.compose() for
    the winner.
    """
    from .branch_producer import propose_composer_branches as _propose

    pairs = _propose(
        request_text=request_text,
        kernel={"freshness": float(freshness)},
        count=int(count),
    )
    seeds = [s.to_dict() for s, _ in pairs]
    plans = [p for _, p in pairs]
    return {
        "request_text": request_text,
        "branch_count": len(seeds),
        "seeds": seeds,
        "compiled_plans": plans,
    }


# ── Creative chop-mode helpers (2026-05-01) ───────────────────────
#
# Auto-warping every loop to project tempo is production-safe but kills
# the creative latitude of intentional tempo mismatch (J Dilla / Madlib /
# IDM territory — a 90-bpm loop in a 122-bpm project produces interesting
# rhythmic chopping when the source/project ratio is musically meaningful).
#
# These helpers + the `warp_strategy` parameter on compose_full_apply
# give the user three modes:
#   "always" (default): warp every loop — production-safe.
#   "smart":            warp tonal layers (pad/bass/lead/vocal) always;
#                       leave drum/perc loops un-warped IF source/project
#                       ratio is in the magic set ±2%. Detected ratios:
#                       0.5 (half-time), 0.667 (2:3), 0.75 (3:4 cross),
#                       0.8 (4:5), 1.25 (5:4), 1.333 (4:3), 1.5 (3:2),
#                       2.0 (double-time).
#   "chop":             never warp — full creative chopping mode.

import re as _re

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


# ── Full-mode apply (2026-05-01) ──────────────────────────────────
#
# Walks a `compose(mode="full")` plan and executes every step server-side
# in a single call, mirroring `compose_fast_apply` but for the older
# plan-based composer that produces 60-step Splice-sample arrangements.
#
# Includes pre-flight (analyzer load + fresh-project default cleanup +
# tempo set) and post-flight (leftover default-track cleanup) so the
# user gets the same hygiene fast mode delivers.


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


async def _apply_full_plan(
    ctx: Context,
    plan_response: dict,
    warp_strategy: str = "always",
) -> dict:
    """Phase-3 full mode: server-side execute the planner's tool sequence.

    Pre-flight handles the same fresh-project cleanup fast mode does
    (BUG-FULL-MODE-4): detects default tracks, deletes them down to one
    survivor, loads the LivePilot Analyzer on master, sets the project
    tempo. Then walks the plan's `plan` array sequentially, resolving
    `$from_step` references against accumulated step results. After the
    walk, deletes the leftover default track if it's still empty
    (BUG-FULL-MODE-5).

    `warp_strategy` (BUG-FULL-MODE-12, 2026-05-01) controls per-step
    Simpler warping behavior:
      - "always" (default): every loop warps to project tempo
      - "smart": tonal layers always warp; drum/perc loops un-warped
        when source/project ratio is musically meaningful (creates
        creative tempo-mismatch chopping — J Dilla / Madlib territory)
      - "chop": no warping anywhere (pure creative chopping)
    """
    started = time.time()
    ableton = ctx.lifespan_context.get("ableton") if hasattr(ctx, "lifespan_context") else None
    if ableton is None:
        return {"error": "Ableton connection not available", "phase": "apply"}

    plan_steps = plan_response.get("plan") or []
    if not plan_steps:
        return {"error": "plan.plan is empty — nothing to apply", "phase": "apply"}

    # ── Pre-flight (Item 4) ─────────────────────────────────────────
    # Mirror fast mode's fresh-project cleanup: load analyzer, detect
    # default tracks, delete all-but-one (Ableton requires ≥1 track).
    fresh_actions: list[str] = []

    # 1. Ensure analyzer on master so load_sample_to_simpler can succeed
    try:
        from ..tools.analyzer import ensure_analyzer_on_master as _ensure_analyzer
        analyzer_resp = _ensure_analyzer(ctx)
        if analyzer_resp.get("status") in ("loaded", "already_loaded"):
            fresh_actions.append("analyzer_loaded_on_master")
    except Exception as exc:
        logger.debug("full apply: ensure_analyzer_on_master failed: %s", exc)

    # 1b. Reconnect M4L UDP bridge (BUG-FULL-MODE-7, 2026-05-01).
    # When the analyzer was just freshly loaded by step 1, its M4L UDP
    # listener may not have registered yet — load_sample_to_simpler's
    # bridge-driven steps (replace_sample, hygiene) will fail with
    # "bridge is not connected" until the listener bootstraps. Forcing a
    # reconnect_bridge call here ensures the bridge is alive before the
    # plan walk reaches any sample-loading steps. Idempotent: returns
    # "already connected" when the bridge is healthy.
    try:
        from ..tools.analyzer import reconnect_bridge as _reconnect_bridge_fn
        bridge_resp = await _reconnect_bridge_fn(ctx)
        if bridge_resp.get("ok"):
            fresh_actions.append("bridge_connected")
    except Exception as exc:
        logger.debug("full apply: reconnect_bridge failed: %s", exc)

    # 2. Detect + clean default tracks
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

    # ── Walk plan steps ────────────────────────────────────────────
    step_results: dict[str, dict] = {}
    step_outcomes: list[dict] = []
    failed_count = 0

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

                from ..tools.analyzer import load_sample_to_simpler as _load_sample
                # The MCP tool is async — await it with the resolved kwargs.
                result = await _load_sample(ctx, **resolved_params)
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

    # ── Post-flight cleanup (Item 5) ───────────────────────────────
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

    duration_ms = int((time.time() - started) * 1000)
    return {
        "phase": "apply",
        "mode": "full",
        "steps_executed": len(step_outcomes),
        "steps_failed": failed_count,
        "step_outcomes": step_outcomes,
        "fresh_project_actions": fresh_actions,
        "final_cleanup_actions": final_cleanup_actions,
        "duration_ms": duration_ms,
        "summary": (
            f"{len(step_outcomes)} steps walked, "
            f"{failed_count} failed, "
            f"{len(fresh_actions)} pre-flight action(s), "
            f"{len(final_cleanup_actions)} cleanup action(s)"
        ),
    }


@mcp.tool()
async def compose_full_apply(
    ctx: Context,
    plan_response: dict,
    warp_strategy: str = "always",
) -> dict:
    """Server-side execution helper for ``compose(mode="full")`` plans.

    Pass the full output dict from a prior ``compose(prompt, mode="full")``
    call and this tool walks every step in the plan: creates tracks,
    loads Splice samples (with the same post-load hygiene fast mode uses —
    Volume=0, Ve Mode active, Classic playback, warp on for loops),
    inserts effects, sets parameters (with `$from_step` device-index
    resolution baked in), creates source clips with trigger notes, and
    builds the section-by-section arrangement.

    `warp_strategy` (BUG-FULL-MODE-12, 2026-05-01) controls whether
    Splice loops snap to the project tempo:

      - ``"always"`` (default) — every loop warps to project tempo.
        Production-safe: a 90-bpm drum loop in a 122-bpm project will
        play in tempo via Simpler's Beats warp algorithm.

      - ``"smart"`` — tonal layers (pad/bass/lead/vocal) always warp;
        drum/perc loops are left UN-warped when source/project ratio
        lands on a magic polyrhythmic value (0.5, 0.667, 0.75, 0.8,
        1.25, 1.333, 1.5, 2.0) within ±2%. The 90→122 case scores 0.738
        which is within tolerance of 0.75 (3:4 cross-rhythm) → un-warped
        → produces the J Dilla / Madlib intentional-tempo-mismatch
        chopping where each clip iteration retriggers the source loop
        from the start, creating off-grid stutter rhythms.

      - ``"chop"`` — never warp anything (full creative chopping mode).

    Pre-flight (BUG-FULL-MODE-4): loads the LivePilot Analyzer on master,
    detects fresh-project default tracks, deletes them down to one
    survivor before the plan starts creating tracks at indices 0+.

    Post-flight (BUG-FULL-MODE-5): prunes the leftover default-track
    survivor if it remained empty after the plan finished.

    Plan-side bug-fix (2026-05-01) — the planner's effect-param table at
    `mcp_server/composer/layer_planner.py::_ROLE_TEMPLATES` was emitting
    legacy-Compressor / dB-direct values that fail on modern Compressor 2
    + Saturator + EQ Eight (which all use 0-1 normalized params). That
    table has been corrected to match `fast.py`'s convention. As a result,
    full-mode plans now apply cleanly without unit-conversion gymnastics.

    Returns: per-step outcomes (with the original `step_id` / `description`
    preserved for diagnostics), pre-flight + post-flight action logs,
    total wall time. Failed steps are reported individually but do not
    abort the walk — full-mode plans are tolerant of partial failure.
    """
    return await _apply_full_plan(ctx, plan_response, warp_strategy=warp_strategy)
