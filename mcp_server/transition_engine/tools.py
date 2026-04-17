"""Transition Engine MCP tools — 3 tools for boundary analysis and planning.

Each tool fetches section data from Ableton via the shared connection,
builds TransitionBoundary objects, then delegates to pure-computation modules.
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from ..tools import _composition_engine as comp_engine

from .archetypes import TRANSITION_ARCHETYPES, select_archetype
from .critics import run_all_transition_critics
from .models import TransitionBoundary, TransitionPlan, TransitionScore
import logging

logger = logging.getLogger(__name__)



# ── Helpers ───────────────────────────────────────────────────────────


def _build_sections_from_ableton(ctx: Context) -> list[comp_engine.SectionNode]:
    """Fetch session data and build section graph."""
    ableton = ctx.lifespan_context["ableton"]
    session = ableton.send_command("get_session_info")
    scenes = session.get("scenes", [])
    track_count = session.get("track_count", 0)

    try:
        matrix_data = ableton.send_command("get_scene_matrix")
        clip_matrix = matrix_data.get("matrix", [])
    except Exception as exc:
        logger.debug("_build_sections_from_ableton failed: %s", exc)
        clip_matrix = [[] for _ in range(len(scenes))]

    return comp_engine.build_section_graph_from_scenes(
        scenes, clip_matrix, track_count,
    )


def _find_section_pair(
    sections: list[comp_engine.SectionNode],
    from_section: str,
    to_section: str,
) -> tuple[comp_engine.SectionNode | None, comp_engine.SectionNode | None]:
    """Find two sections by ID or name."""
    from_node = None
    to_node = None
    for s in sections:
        sid = s.section_id.lower()
        sname = (s.name or "").lower()
        if sid == from_section.lower() or sname == from_section.lower():
            from_node = s
        if sid == to_section.lower() or sname == to_section.lower():
            to_node = s
    return from_node, to_node


def _build_boundary(
    from_node: comp_engine.SectionNode,
    to_node: comp_engine.SectionNode,
) -> TransitionBoundary:
    """Build a TransitionBoundary from two adjacent SectionNodes."""
    return TransitionBoundary(
        from_section_id=from_node.section_id,
        to_section_id=to_node.section_id,
        boundary_bar=to_node.start_bar,
        from_type=from_node.section_type.value,
        to_type=to_node.section_type.value,
        energy_delta=to_node.energy - from_node.energy,
        density_delta=to_node.density - from_node.density,
    )


def _score_boundary(boundary: TransitionBoundary) -> TransitionScore:
    """Compute a TransitionScore from boundary data.

    Pure heuristic scoring — no I/O.
    """
    abs_energy = abs(boundary.energy_delta)
    abs_density = abs(boundary.density_delta)

    # Boundary clarity: how obvious is the section change?
    boundary_clarity = min(1.0, abs_energy * 2.0 + abs_density * 1.5)

    # Payoff strength: does a high-energy arrival feel earned?
    if boundary.energy_delta > 0.2:
        # Rising energy — payoff depends on contrast magnitude
        payoff_strength = min(1.0, boundary.energy_delta * 1.5)
    elif boundary.energy_delta < -0.2:
        # Falling energy — payoff is the breath/relief
        payoff_strength = min(1.0, abs(boundary.energy_delta) * 1.2)
    else:
        # Flat — low payoff unless density compensates
        payoff_strength = min(1.0, abs_density * 1.5)

    # Energy redirection: how much does energy actually shift?
    energy_redirection = min(1.0, abs_energy * 2.5)

    # Identity preservation (heuristic: same density = same character)
    identity_preservation = max(0.0, 1.0 - abs_density * 2.0)

    # Cliche risk: common pairs with standard archetypes are higher risk
    _common_pairs = {
        ("build", "drop"), ("verse", "chorus"), ("pre_chorus", "chorus"),
    }
    pair = (boundary.from_type, boundary.to_type)
    cliche_risk = 0.5 if pair in _common_pairs else 0.2

    # Overall: weighted average (cliche_risk is inverted — lower is better)
    overall = (
        boundary_clarity * 0.25
        + payoff_strength * 0.30
        + energy_redirection * 0.20
        + identity_preservation * 0.10
        + (1.0 - cliche_risk) * 0.15
    )

    return TransitionScore(
        boundary_clarity=round(boundary_clarity, 3),
        payoff_strength=round(payoff_strength, 3),
        energy_redirection=round(energy_redirection, 3),
        identity_preservation=round(identity_preservation, 3),
        cliche_risk=round(cliche_risk, 3),
        overall=round(overall, 3),
    )


def _build_plan(
    boundary: TransitionBoundary,
    archetype=None,
) -> TransitionPlan:
    """Build a TransitionPlan for a boundary using the selected archetype."""
    if archetype is None:
        archetype = select_archetype(boundary)

    # Map archetype gestures to lead-in and arrival
    lead_in_gestures = []
    arrival_gestures = []

    for gesture_name in archetype.gestures:
        gesture = {"intent": gesture_name, "archetype": archetype.name}
        if gesture_name in ("inhale", "conceal", "lift", "punctuate"):
            lead_in_gestures.append({
                **gesture,
                "offset_bars": -2,
                "duration_bars": 2,
            })
        else:
            arrival_gestures.append({
                **gesture,
                "offset_bars": 0,
                "duration_bars": 2,
            })

    # Payoff estimate from energy delta and archetype risk
    risk_penalty = {"low": 0.0, "medium": 0.1, "high": 0.2}.get(
        archetype.risk_profile, 0.0,
    )
    payoff_estimate = min(1.0, max(0.0,
        abs(boundary.energy_delta) * 1.5 + 0.3 - risk_penalty
    ))

    return TransitionPlan(
        boundary=boundary,
        archetype=archetype,
        lead_in_gestures=lead_in_gestures,
        arrival_gestures=arrival_gestures,
        payoff_estimate=round(payoff_estimate, 3),
    )


# ── MCP Tools ─────────────────────────────────────────────────────────


@mcp.tool()
def analyze_transition(
    ctx: Context,
    from_section: str,
    to_section: str,
) -> dict:
    """Analyze the transition boundary between two sections.

    Builds a TransitionBoundary, selects an archetype, scores the
    boundary, and runs all 5 transition critics.

    Args:
        from_section: Name or ID of the outgoing section.
        to_section: Name or ID of the arriving section.

    Returns: boundary, archetype, score, issues, and recommended moves.
    """
    sections = _build_sections_from_ableton(ctx)
    from_node, to_node = _find_section_pair(sections, from_section, to_section)

    if not from_node:
        return {"error": f"Section '{from_section}' not found",
                "available": [s.name or s.section_id for s in sections]}
    if not to_node:
        return {"error": f"Section '{to_section}' not found",
                "available": [s.name or s.section_id for s in sections]}

    boundary = _build_boundary(from_node, to_node)
    archetype = select_archetype(boundary)
    score = _score_boundary(boundary)
    plan = _build_plan(boundary, archetype)
    issues = run_all_transition_critics(boundary, plan, score)

    return {
        "boundary": boundary.to_dict(),
        "archetype": archetype.to_dict(),
        "score": score.to_dict(),
        "issues": [i.to_dict() for i in issues],
        "issue_count": len(issues),
    }


@mcp.tool()
def plan_transition(
    ctx: Context,
    from_section: str,
    to_section: str,
) -> dict:
    """Plan a transition between two sections with concrete gestures.

    Selects the best archetype for the boundary and generates
    lead-in and arrival gesture sequences.

    Args:
        from_section: Name or ID of the outgoing section.
        to_section: Name or ID of the arriving section.

    Returns: plan with archetype, gestures, payoff estimate, and issues.
    """
    sections = _build_sections_from_ableton(ctx)
    from_node, to_node = _find_section_pair(sections, from_section, to_section)

    if not from_node:
        return {"error": f"Section '{from_section}' not found",
                "available": [s.name or s.section_id for s in sections]}
    if not to_node:
        return {"error": f"Section '{to_section}' not found",
                "available": [s.name or s.section_id for s in sections]}

    boundary = _build_boundary(from_node, to_node)
    plan = _build_plan(boundary)
    score = _score_boundary(boundary)
    issues = run_all_transition_critics(boundary, plan, score)

    return {
        "plan": plan.to_dict(),
        "score": score.to_dict(),
        "issues": [i.to_dict() for i in issues],
        "issue_count": len(issues),
        "available_archetypes": list(TRANSITION_ARCHETYPES.keys()),
    }


@mcp.tool()
def score_transition(
    ctx: Context,
    from_section: str,
    to_section: str,
) -> dict:
    """Score the transition quality between two sections.

    Returns a multi-dimensional score: boundary clarity, payoff strength,
    energy redirection, identity preservation, and cliche risk.

    Args:
        from_section: Name or ID of the outgoing section.
        to_section: Name or ID of the arriving section.

    Returns: score breakdown and overall rating.
    """
    sections = _build_sections_from_ableton(ctx)
    from_node, to_node = _find_section_pair(sections, from_section, to_section)

    if not from_node:
        return {"error": f"Section '{from_section}' not found",
                "available": [s.name or s.section_id for s in sections]}
    if not to_node:
        return {"error": f"Section '{to_section}' not found",
                "available": [s.name or s.section_id for s in sections]}

    boundary = _build_boundary(from_node, to_node)
    score = _score_boundary(boundary)

    return {
        "boundary": boundary.to_dict(),
        "score": score.to_dict(),
    }
