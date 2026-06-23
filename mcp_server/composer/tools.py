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
from .full.engine import ComposerEngine
from . import fast as fast_compose
from .fast.apply import apply_fast_plan
from .full.apply import apply_full_plan
import logging
import time

logger = logging.getLogger(__name__)

# Backward-compatible alias — tests import _apply_fast_plan from this module.
_apply_fast_plan = apply_fast_plan

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


@mcp.tool()
async def compose(
    ctx: Context,
    prompt: str,
    mode: str = "full",
    bars: int = 4,
    target_scene: Optional[int] = None,
    seed_scene_index: int = 0,
    max_credits: int = 50,
    dry_run: bool = False,
    reference: Optional[str] = None,
) -> dict:
    """Plan, brief, or execute a multi-layer composition from a text prompt
    or an existing seed loop.

    Three modes:

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

    ``mode="develop"`` — extend an existing 8-bar loop into a fuller
        arrangement. Reads the seed at seed_scene_index (default 0),
        builds a brief with identity + vocabulary, returns it. Agent
        designs the variant set, calls develop_apply.

    prompt: "dark minimal techno 128bpm" / "downtempo lo-fi Cm" / "trap"
    mode: "full" | "fast" | "develop"
    bars: clip length in bars (fast mode only — default 4)
    target_scene: scene index to populate (full mode legacy param; fast
                  mode now lets the agent pick via compose_fast_apply)
    seed_scene_index: scene to read as the seed (develop mode only,
                      default 0)
    max_credits: max Splice credits budget for full-mode plans (default 50)
    dry_run: full-mode only — skip credit checks

    Fast mode returns: a brief dict with creative context. Call
    compose_fast_apply with your designed plan to actually create tracks.
    Develop mode returns: a brief dict with seed_state + design_targets.
    Call develop_apply with your designed variant plan.
    Full mode returns the existing plan dict.
    """
    intent = parse_prompt(prompt)

    if mode == "develop":
        from .develop.seed_introspector import introspect_seed
        from .develop.brief_builder import build_develop_brief
        seed = introspect_seed(ctx, scene_index=seed_scene_index)
        if seed.get("error"):
            return {"status": "error", "error": seed["error"], "phase": "introspect_seed"}
        brief = build_develop_brief(ctx, seed, prompt_directive=prompt or None)
        brief["prompt"] = prompt
        return brief

    if mode == "fast":
        brief = _build_fast_brief(
            ctx, intent, bars=int(bars), reference=reference,
        )
        brief["prompt"] = prompt
        return brief

    # mode == "full" — v1.24 LLM-creative two-phase flow
    # Phase 1: return a FullBrief vocabulary so the agent can design form +
    # variants + events. Phase 3: agent submits the designed plan to
    # compose_full_apply → apply_full_plan_v2.
    # The old deterministic engine path (step_plan) is deprecated
    # (BUG-FULL-MODE-18: flat single-pattern arrangements).
    from .full.brief_builder import build_full_brief
    brief = build_full_brief(ctx, prompt=prompt, seed_state=None)
    brief["prompt"] = prompt
    return brief


@mcp.tool()
async def compose_fast_apply(ctx: Context, plan: dict) -> dict:
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
    return await apply_fast_plan(ctx, plan)


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
      consult_ableton_knowledge("what does the Saturator Drive knob do?")
        → intent: device
        → plan: [search_live_manual("what does the Saturator Drive knob do?"),
                 search_videos("what does the Saturator Drive knob do?"),
                 search_transcripts("what does the Saturator Drive knob do?")]
                 + synthesis template
      consult_ableton_knowledge("how do I make my kick punchier?", {"current_genre": "techno"})
        → intent: sound_design
        → plan: [search_transcripts("techno how do I make my kick punchier?"),
                 search_videos("techno how do I make my kick punchier? tutorial"),
                 search_knowledge_base("how do I make my kick punchier?")]
                 + synthesis template

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

# Backward-compatible aliases — tests import these from this module.
_apply_full_plan = apply_full_plan
from .full.apply import (  # noqa: E402
    _resolve_from_step,
    _extract_bpm_from_filename,
    _is_meaningful_ratio,
)

@mcp.tool()
async def compose_full_apply(
    ctx: Context,
    plan: dict,
) -> dict:
    """Phase-3 of full mode (v1.24 LLM-creative): execute the agent-designed plan.

    compose(mode="full") returns a FullBrief with genre/artist vocabulary,
    the 42-event structural lexicon, and atlas instrument candidates. The
    agent reads the brief, designs the song's form (section sequence, bar
    counts, drop placement, variant per track per section), and submits
    that designed plan here.

    See mcp_server.composer.full.apply.apply_full_plan_v2 for the full
    plan shape. Required fields: form (list of section dicts), tracks
    (list of track specs with variants + arrangement_clips).

    Replaces the deterministic engine path (BUG-FULL-MODE-18 fix):
    the old flow tiled one source clip across all sections; the new flow
    emits one source clip per variant so each section can have a genuinely
    different pattern.
    """
    from .full.apply import apply_full_plan_v2
    return await apply_full_plan_v2(ctx, plan)


# ── v1.24 develop mode ─────────────────────────────────────────────


@mcp.tool()
async def analyze_loop_for_extension(
    ctx: Context,
    scene_index: int = 0,
) -> dict:
    """Read-only analyzer for develop mode — returns SeedState for a scene.

    Inspects the scene's clips, classifies each track as sample_trigger
    or midi_riff, infers role from track name, and reports key/tempo/
    time signature. The agent uses this BEFORE calling compose(mode='develop')
    to verify the loop is extendable, OR as a standalone diagnostic.

    Returns: dict per mcp_server.composer.develop.seed_introspector.introspect_seed.
    No writes to the session.
    """
    from .develop.seed_introspector import introspect_seed
    return introspect_seed(ctx, scene_index=scene_index)


@mcp.tool()
async def develop_apply(
    ctx: Context,
    plan: dict,
) -> dict:
    """Phase-3 develop mode: server-side execute the agent's variant plan.

    Receives a plan with the agent-designed variant set:
        {
          "scope": "develop",
          "clip_length_beats": float (default 4.0),
          "tempo": float (optional override),
          "variants": [
            {
              "track_index": int,
              "scene_index": int,
              "name": str,
              "notes": [{"pitch": int, "start_time": float, "duration": float,
                         "velocity": int}, ...]
              "sample_uri": str (optional — for sample-trigger swaps)
            },
            ...
          ]
        }

    The agent decides variant count, names, scenes, MIDI per call — no
    fixed taxonomy. Empty notes list creates an empty clip (drum-dropout
    pattern).

    Returns: status, clips_created, scenes_populated, sample_swaps,
    preflight result, postflight result, errors list.
    """
    from .develop.apply import apply_develop_plan
    return await apply_develop_plan(ctx, plan)
