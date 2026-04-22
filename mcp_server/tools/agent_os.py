"""Agent OS V1 MCP tools — goal compilation, world model, and evaluation.

3 tools that connect the pure-computation engine (_agent_os_engine.py) to the
live Ableton session via the existing MCP infrastructure.

These tools power the Agent OS cyclical loop:
  compile_goal_vector → build_world_model → [agent acts] → evaluate_move
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastmcp import Context

from ..server import mcp
from ..memory.technique_store import TechniqueStore
from . import _agent_os_engine as engine

logger = logging.getLogger(__name__)

_memory_store = TechniqueStore()


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _get_spectral(ctx: Context):
    return ctx.lifespan_context.get("spectral")


def _parse_json_param(value, name: str) -> dict:
    """Parse a dict, JSON string, or None parameter."""
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {name}: {exc}") from exc
    if isinstance(value, dict):
        return value
    raise ValueError(f"{name} must be a dict or JSON string")


# ── compile_goal_vector ───────────────────────────────────────────────


@mcp.tool()
def compile_goal_vector(
    ctx: Context,
    request_text: str,
    targets: dict | str,
    protect: dict | str = "{}",
    mode: str = "improve",
    aggression: float = 0.5,
    research_mode: str = "none",
) -> dict:
    """Compile a user request into a validated GoalVector.

    The agent interprets the user's natural language into quality dimensions,
    then this tool validates the schema and normalizes weights.

    targets: dict of dimension → weight (e.g., {"punch": 0.4, "weight": 0.3, "energy": 0.3}).
             Weights are normalized to sum to 1.0.
    protect: dict of dimension → minimum threshold (e.g., {"clarity": 0.8}).
             If a dimension drops below this value after a move, the move is undone.
    mode: observe | improve | explore | finish | diagnose
    aggression: 0.0 (subtle) to 1.0 (bold)
    research_mode: none | targeted | deep

    Valid dimensions: energy, punch, weight, density, brightness, warmth,
    width, depth, motion, contrast, clarity, cohesion, groove, tension,
    novelty, polish, emotion.
    """
    targets_dict = _parse_json_param(targets, "targets")
    protect_dict = _parse_json_param(protect, "protect")

    gv = engine.validate_goal_vector(
        request_text=request_text,
        targets=targets_dict,
        protect=protect_dict,
        mode=mode,
        aggression=float(aggression),
        research_mode=research_mode,
    )

    return {
        "goal_vector": gv.to_dict(),
        "measurable_dimensions": [
            d for d in gv.targets if d in engine.MEASURABLE_PROXIES
        ],
        "unmeasurable_dimensions": [
            d for d in gv.targets if d not in engine.MEASURABLE_PROXIES
        ],
    }


# ── build_world_model ─────────────────────────────────────────────────


@mcp.tool()
def build_world_model(ctx: Context) -> dict:
    """Build a WorldModel snapshot of the current Ableton session.

    Reads session info, spectral data (if analyzer available), per-track
    device health, and infers track roles from names. Degrades gracefully
    if M4L Analyzer is not loaded.

    Returns topology (tracks, devices, scenes), sonic state (spectrum, RMS, key),
    technical state (analyzer/FluCoMa availability, plugin health), and
    inferred track roles.
    """
    ableton = _get_ableton(ctx)
    spectral = _get_spectral(ctx)

    # Fetch session info (always available)
    session_info = ableton.send_command("get_session_info")

    # Fetch per-track device info for plugin health checks (I2 fix)
    track_infos = []
    for track in session_info.get("tracks", []):
        try:
            ti = ableton.send_command("get_track_info", {
                "track_index": track["index"]
            })
            track_infos.append(ti)
        except Exception as exc:
            # Skip tracks that fail — don't block world model build
            logger.debug("world-model track %s skipped: %s", track.get("index"), exc)

    # Fetch spectral data (may be unavailable)
    spectrum = None
    rms = None
    detected_key = None
    flucoma_status = None

    if spectral and spectral.is_connected:
        spec_data = spectral.get("spectrum")
        if spec_data:
            spectrum = {"bands": spec_data["value"]}

        rms_data = spectral.get("rms")
        if rms_data:
            rms = rms_data["value"] if isinstance(rms_data["value"], dict) else {"rms": rms_data["value"]}

        key_data = spectral.get("key")
        if key_data:
            detected_key = key_data["value"] if isinstance(key_data["value"], dict) else {"key": key_data["value"]}

        # BUG-E6 fix: derive flucoma_available from the same 6-stream probe
        # that check_flucoma uses. Previously we read a dedicated
        # "flucoma_status" key that the M4L bridge doesn't emit, so the
        # fallback `{"flucoma_available": False}` always won even when all
        # 6 FluCoMa streams were actively delivering data.
        _flu_streams = ("spectral_shape", "mel_bands", "chroma",
                        "onset", "novelty", "loudness")
        active = sum(1 for k in _flu_streams if spectral.get(k) is not None)
        flucoma_status = {
            "flucoma_available": active > 0,
            "active_streams": active,
        }
        # Keep any explicit flucoma_status payload the bridge may emit
        # alongside as extra metadata — without letting it override the
        # stream-based truth.
        flucoma_data = spectral.get("flucoma_status")
        if flucoma_data and isinstance(flucoma_data.get("value"), dict):
            extras = {k: v for k, v in flucoma_data["value"].items()
                      if k not in flucoma_status}
            flucoma_status.update(extras)
    else:
        flucoma_status = {"flucoma_available": False, "active_streams": 0}

    # Build model
    wm = engine.build_world_model_from_data(
        session_info=session_info,
        spectrum=spectrum,
        rms=rms,
        detected_key=detected_key,
        flucoma_status=flucoma_status,
        track_infos=track_infos,
    )

    # Run critics with all-dimensions stub goal to surface all issues.
    # The agent should filter these against its actual GoalVector.
    goal_stub = engine.GoalVector(
        request_text="world_model_build",
        targets={d: 1.0 / len(engine.QUALITY_DIMENSIONS) for d in engine.QUALITY_DIMENSIONS},
        mode="observe",
    )
    sonic_issues = engine.run_sonic_critic(wm.sonic, goal_stub, wm.track_roles)
    technical_issues = engine.run_technical_critic(wm.technical)

    # Round 1: Wire structural critic (composition engine) into world model
    structural_issues = []
    try:
        from . import _composition_engine as comp_engine
        # Build lightweight section graph for structural analysis
        scenes = session_info.get("scenes", [])
        track_count = session_info.get("track_count", 0)
        clip_matrix = []
        try:
            matrix_data = ableton.send_command("get_scene_matrix")
            clip_matrix = matrix_data.get("matrix", [])
        except Exception as exc:
            logger.debug("scene_matrix fetch for structural critic skipped: %s", exc)

        sections = comp_engine.build_section_graph_from_scenes(scenes, clip_matrix, track_count)
        structural_issues = comp_engine.run_form_critic(sections)
    except Exception as exc:
        # Composition engine unavailable — degrade gracefully
        logger.warning("structural critic unavailable: %s", exc)

    result = wm.to_dict()
    result["issues"] = {
        "sonic": [i.to_dict() for i in sonic_issues],
        "technical": [i.to_dict() for i in technical_issues],
        "structural": [i.to_dict() for i in structural_issues],
        "total_count": len(sonic_issues) + len(technical_issues) + len(structural_issues),
        "note": "Issues are unfiltered — filter against your GoalVector targets before acting.",
    }
    return result


# ── evaluate_move ─────────────────────────────────────────────────────


@mcp.tool()
def evaluate_move(
    ctx: Context,
    goal_vector: dict | str,
    before_snapshot: dict | str,
    after_snapshot: dict | str,
) -> dict:
    """Evaluate whether a production move improved the mix toward the goal.

    Takes before/after sonic snapshots and the active GoalVector.
    Returns a score and keep/undo recommendation.

    Snapshots should contain: spectrum (9-band dict sub_low → air, or
    8-band from pre-v1.16 .amxd builds), rms, peak. Get these from
    get_master_spectrum + get_master_rms before and after making changes.

    Hard rules enforce undo when:
    - No measurable improvement (delta <= 0)
    - Protected dimension dropped below its threshold or by > 0.15
    - Total score < 0.40

    When all target dimensions are unmeasurable (e.g., groove, tension),
    the tool defers keep/undo to the agent's musical judgment.

    Returns consecutive_undo_hint=true when keep_change=false — the agent
    should track consecutive undos and switch to observe mode after 3.
    """
    gv_dict = _parse_json_param(goal_vector, "goal_vector")
    before = _parse_json_param(before_snapshot, "before_snapshot")
    after = _parse_json_param(after_snapshot, "after_snapshot")

    # I6 fix: validate the GoalVector to catch malformed input
    gv = engine.validate_goal_vector(
        request_text=gv_dict.get("request_text", "evaluate"),
        targets=gv_dict.get("targets", {}),
        protect=gv_dict.get("protect", {}),
        mode=gv_dict.get("mode", "improve"),
        aggression=float(gv_dict.get("aggression", 0.5)),
        research_mode=gv_dict.get("research_mode", "none"),
    )

    return engine.compute_evaluation_score(gv, before, after)


# ── analyze_outcomes (Round 1) ────────────────────────────────────────


@mcp.tool()
def analyze_outcomes(
    ctx: Context,
    limit: int = 50,
) -> dict:
    """Analyze accumulated outcome memories to identify user taste patterns.

    Reads outcome-type memories from the technique library and returns:
    - keep_rate: what percentage of moves does this user keep?
    - dimension_success: which quality dimensions improve most often?
    - common_kept_moves: which action types work best?
    - common_undone_moves: which action types fail most?
    - taste_vector: inferred dimension preferences from history

    Use this before choosing moves to align with user taste.
    The more outcomes stored (via memory_learn type="outcome"),
    the better the taste analysis becomes.
    """
    # Fetch outcome memories directly from TechniqueStore
    try:
        techniques = _memory_store.list_techniques(
            type_filter="outcome", sort_by="updated_at", limit=limit,
        )
    except Exception as exc:
        logger.warning("analyze_outcomes list_techniques failed: %s", exc)
        techniques = []

    # Extract payloads from full technique records
    outcomes = []
    for t in techniques:
        # list_techniques returns compact summaries; get full record for payload
        try:
            full = _memory_store.get(t["id"])
            payload = full.get("payload", {})
            if isinstance(payload, dict):
                outcomes.append(payload)
        except Exception as exc:
            logger.debug("outcome payload %s skipped: %s", t.get("id"), exc)

    return engine.analyze_outcome_history(outcomes)


# ── get_technique_card (Round 2) ──────────────────────────────────────


@mcp.tool()
def get_technique_card(
    ctx: Context,
    query: str,
    limit: int = 5,
) -> dict:
    """Search for technique cards — structured production recipes.

    Technique cards are reusable recipes saved from successful production
    outcomes. Each card has: problem, context, devices, method, verification.

    query: search term (e.g., "wider pad", "punchy kick", "sidechain bass")
    limit: max results
    """
    # Search technique cards directly from TechniqueStore
    try:
        techniques = _memory_store.search(
            query=query, type_filter="technique_card", limit=limit,
        )
    except Exception as exc:
        logger.warning("technique_card search(%r) failed: %s", query, exc)
        techniques = []

    cards = []
    for t in techniques:
        # search() returns summaries without payload; get full record
        try:
            full = _memory_store.get(t["id"])
            payload = full.get("payload", {})
            if isinstance(payload, dict):
                cards.append({
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "card": payload,
                    "rating": t.get("rating", 0),
                    "replay_count": t.get("replay_count", 0),
                })
        except Exception as exc:
            logger.debug("technique_card %s payload skipped: %s", t.get("id"), exc)

    return {
        "query": query,
        "cards": cards,
        "count": len(cards),
    }


# ── get_taste_profile (Round 4) ────────────────────────────────────


@mcp.tool()
def get_taste_profile(
    ctx: Context,
    limit: int = 50,
) -> dict:
    """Get the user's production taste profile from outcome history.

    Analyzes kept vs undone moves to identify: preferred dimensions,
    avoided dimensions, taste vector weights, and overall keep rate.
    Use this to understand what this user values in production.

    limit: how many outcomes to analyze (default: 50)

    Returns: {taste_vector, preferred_dimensions, avoided_dimensions,
              keep_rate, sample_size}
    """
    # Fetch outcome memories directly from TechniqueStore
    try:
        techniques = _memory_store.list_techniques(
            type_filter="outcome", sort_by="updated_at", limit=limit,
        )
    except Exception as exc:
        logger.warning("taste_profile list_techniques failed: %s", exc)
        techniques = []

    outcomes = []
    for t in techniques:
        try:
            full = _memory_store.get(t["id"])
            payload = full.get("payload", {})
            if isinstance(payload, dict):
                outcomes.append(payload)
        except Exception as exc:
            logger.debug("taste_profile outcome %s skipped: %s", t.get("id"), exc)

    return engine.get_taste_profile(outcomes)


# ── get_turn_budget (Conductor Budget) ────────────────────────────


@mcp.tool()
def get_turn_budget(
    ctx: Context,
    mode: str = "improve",
    aggression: float = 0.5,
) -> dict:
    """Get a resource budget for the current agent turn.

    Returns six resource pools that prevent overcommitting:
    - latency_ms: time budget for this turn
    - risk_points: how much risk is allowed (0-1)
    - novelty_points: how much novelty is allowed (0-1)
    - change_count: max production moves this turn
    - undo_count: max consecutive undos before switching to observe
    - research_calls: max research lookups this turn

    mode: observe | improve | explore | finish | diagnose | performance
      - observe: very low risk, zero changes, read-only
      - improve: balanced defaults
      - explore: high novelty, high risk, more moves
      - finish: conservative, low novelty, few changes
      - diagnose: zero changes, research-focused
      - performance: very low latency, minimal risk
    aggression: 0.0 (subtle) to 1.0 (bold) — scales risk and change limits

    Use spend functions via the conductor to track consumption during the turn.
    """
    from . import _conductor_budgets as budgets

    budget = budgets.create_budget(mode=mode, aggression=float(aggression))
    summary = budgets.get_budget_summary(budget)
    summary["budget"] = budget.to_dict()
    summary["mode"] = mode
    summary["aggression"] = float(aggression)
    return summary


# ── route_request (Conductor) ──────────────────────────────────────


@mcp.tool()
def route_request(
    ctx: Context,
    request: str,
) -> dict:
    """Route a production request to the right engine(s).

    Analyzes natural language to determine which engines should handle
    the request, in what priority order, with what entry tools.

    request: what the user wants (e.g., "make this punchier", "turn the
             loop into a song", "make it sound like Burial")

    Returns: routing plan with engine priorities, entry tools, and
    capability requirements.
    """
    from . import _conductor as conductor

    plan = conductor.classify_request(request)
    return plan.to_dict()
