"""Composition Engine V1 MCP tools — structural and musical intelligence.

5 tools that connect the pure-computation engine (_composition_engine.py) to the
live Ableton session via the existing MCP infrastructure.

These tools power the composition intelligence layer:
  analyze_composition — full structural analysis (sections, phrases, roles, issues)
  get_section_graph — lightweight section inference only
  get_phrase_grid — phrase boundaries for a section
  plan_gesture — map musical intent to concrete automation plan
  evaluate_composition_move — composition-specific keep/undo scoring
"""

from __future__ import annotations

import json
from typing import Optional

from fastmcp import Context

from ..server import mcp
from . import _composition_engine as engine


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


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


def _build_clip_matrix(ableton, scene_count: int, track_count: int) -> list[list]:
    """Build the clip matrix from scene_matrix data."""
    try:
        matrix_data = ableton.send_command("get_scene_matrix")
        raw_matrix = matrix_data.get("matrix", [])
        return raw_matrix
    except Exception:
        return [[] for _ in range(scene_count)]


# ── analyze_composition ───────────────────────────────────────────────


@mcp.tool()
def analyze_composition(ctx: Context) -> dict:
    """Run full composition analysis on the current Ableton session.

    Returns section graph, phrase grid, role graph, and issues from
    form/section-identity/phrase critics. This is the "one call to
    understand the arrangement structure."

    Uses scene names + clip activity to infer sections, note data for
    phrases, and track names + note patterns for role assignment.

    The issues section contains actionable structural recommendations.
    """
    ableton = _get_ableton(ctx)

    # 1. Get session info
    session = ableton.send_command("get_session_info")
    scenes = session.get("scenes", [])
    tracks = session.get("tracks", [])
    track_count = session.get("track_count", 0)

    # 2. Get clip matrix for section inference
    clip_matrix = _build_clip_matrix(ableton, len(scenes), track_count)

    # 3. Build section graph (from scenes)
    sections = engine.build_section_graph_from_scenes(
        scenes, clip_matrix, track_count,
    )

    # 4. Try arrangement clips as supplement
    arr_clips = {}
    for track in tracks:
        try:
            arr = ableton.send_command("get_arrangement_clips", {
                "track_index": track["index"]
            })
            clips = arr.get("clips", [])
            if clips:
                arr_clips[track["index"]] = clips
        except Exception:
            pass

    if not sections and arr_clips:
        sections = engine.build_section_graph_from_arrangement(
            arr_clips, track_count,
        )

    # 5. Get per-track info for role inference
    track_data = []
    for track in tracks:
        try:
            ti = ableton.send_command("get_track_info", {
                "track_index": track["index"]
            })
            track_data.append(ti)
        except Exception:
            track_data.append({"index": track["index"], "name": track.get("name", ""),
                               "devices": []})

    # 6. Get notes for phrase detection + role inference
    notes_by_section_track: dict[str, dict[int, list]] = {}
    all_notes_by_track: dict[int, list] = {}

    for track in tracks:
        t_idx = track["index"]
        # Collect notes from all clips
        track_notes = []
        for s_idx in range(len(scenes)):
            try:
                result = ableton.send_command("get_notes", {
                    "track_index": t_idx, "clip_index": s_idx
                })
                notes = result.get("notes", [])
                track_notes.extend(notes)
            except Exception:
                pass
        all_notes_by_track[t_idx] = track_notes

    # Map notes to sections
    for section in sections:
        notes_by_section_track[section.section_id] = {}
        for t_idx in section.tracks_active:
            notes_by_section_track[section.section_id][t_idx] = (
                all_notes_by_track.get(t_idx, [])
            )

    # 7. Build phrase grid
    all_phrases = []
    for section in sections:
        section_notes = {t: all_notes_by_track.get(t, []) for t in section.tracks_active}
        phrases = engine.detect_phrases(section, section_notes)
        all_phrases.extend(phrases)

    # 8. Build role graph
    roles = engine.build_role_graph(sections, track_data, notes_by_section_track)

    # 9. Run critics
    form_issues = engine.run_form_critic(sections)
    identity_issues = engine.run_section_identity_critic(sections, roles)
    phrase_issues = engine.run_phrase_critic(all_phrases)
    all_issues = form_issues + identity_issues + phrase_issues

    # 10. Assemble result
    analysis = engine.CompositionAnalysis(
        sections=sections,
        phrases=all_phrases,
        roles=roles,
        issues=all_issues,
    )
    return analysis.to_dict()


# ── get_section_graph ─────────────────────────────────────────────────


@mcp.tool()
def get_section_graph(ctx: Context) -> dict:
    """Get just the section graph — lightweight structural overview.

    Infers sections from scene names and clip activity. Returns
    section types, energy levels, density, and active tracks per section.
    Faster than analyze_composition when you only need structure.
    """
    ableton = _get_ableton(ctx)
    session = ableton.send_command("get_session_info")
    scenes = session.get("scenes", [])
    track_count = session.get("track_count", 0)

    clip_matrix = _build_clip_matrix(ableton, len(scenes), track_count)
    sections = engine.build_section_graph_from_scenes(
        scenes, clip_matrix, track_count,
    )

    return {
        "sections": [s.to_dict() for s in sections],
        "section_count": len(sections),
        "has_energy_arc": _has_energy_arc(sections),
    }


def _has_energy_arc(sections: list[engine.SectionNode]) -> bool:
    if len(sections) < 2:
        return False
    energies = [s.energy for s in sections]
    return (max(energies) - min(energies)) >= 0.15


# ── get_phrase_grid ───────────────────────────────────────────────────


@mcp.tool()
def get_phrase_grid(
    ctx: Context,
    section_index: int = 0,
) -> dict:
    """Get phrase boundaries for a specific section.

    section_index: which section to analyze (0-based, from get_section_graph).
    Returns phrase boundaries, cadence strengths, and note densities.
    """
    ableton = _get_ableton(ctx)
    session = ableton.send_command("get_session_info")
    scenes = session.get("scenes", [])
    tracks = session.get("tracks", [])
    track_count = session.get("track_count", 0)

    clip_matrix = _build_clip_matrix(ableton, len(scenes), track_count)
    sections = engine.build_section_graph_from_scenes(
        scenes, clip_matrix, track_count,
    )

    if section_index < 0 or section_index >= len(sections):
        return {"error": f"section_index {section_index} out of range (0-{len(sections) - 1})"}

    section = sections[section_index]

    # Collect notes for active tracks
    notes_by_track: dict[int, list] = {}
    for t_idx in section.tracks_active:
        try:
            result = ableton.send_command("get_notes", {
                "track_index": t_idx,
                "clip_index": section_index,
            })
            notes_by_track[t_idx] = result.get("notes", [])
        except Exception:
            notes_by_track[t_idx] = []

    phrases = engine.detect_phrases(section, notes_by_track)
    return {
        "section": section.to_dict(),
        "phrases": [p.to_dict() for p in phrases],
        "phrase_count": len(phrases),
    }


# ── plan_gesture ──────────────────────────────────────────────────────


@mcp.tool()
def plan_gesture(
    ctx: Context,
    intent: str,
    target_tracks: list | str = "[]",
    start_bar: int = 0,
    duration_bars: int = 0,
    foreground: bool = False,
) -> dict:
    """Plan a musical gesture — map abstract intent to concrete automation.

    intent: reveal | conceal | handoff | inhale | release | lift | sink | punctuate | drift
    target_tracks: list of track indices the gesture applies to
    start_bar: where the gesture begins
    duration_bars: how long (0 = use gesture default)
    foreground: is this a focal point or background motion?

    Returns a GesturePlan with: curve_family, parameter_hints, direction,
    and timing — ready for use with apply_automation_shape.

    Example: plan_gesture(intent="reveal", target_tracks=[6], start_bar=8)
    → exponential curve on filter_cutoff, sweep up over 4 bars
    """
    # Parse intent
    try:
        gesture_intent = engine.GestureIntent(intent)
    except ValueError:
        valid = [g.value for g in engine.GestureIntent]
        raise ValueError(f"Unknown intent '{intent}'. Valid: {valid}")

    # Parse target_tracks
    if isinstance(target_tracks, str):
        try:
            target_tracks = json.loads(target_tracks)
        except json.JSONDecodeError:
            target_tracks = []

    duration = duration_bars if duration_bars > 0 else None
    gesture = engine.plan_gesture(
        intent=gesture_intent,
        target_tracks=target_tracks,
        start_bar=start_bar,
        duration_bars=duration,
        foreground=foreground,
    )
    return gesture.to_dict()


# ── evaluate_composition_move ─────────────────────────────────────────


@mcp.tool()
def evaluate_composition_move(
    ctx: Context,
    before_issues: list | str,
    after_issues: list | str,
    target_dimensions: dict | str = "{}",
    protect: dict | str = "{}",
) -> dict:
    """Evaluate whether a composition move improved the arrangement.

    Takes before/after issue lists (from analyze_composition) and compares
    severity and count. Returns a score and keep/undo recommendation.

    before_issues: issues list from analyze_composition BEFORE the move
    after_issues: issues list from analyze_composition AFTER the move
    target_dimensions: optional composition dimensions being targeted
    protect: optional dimensions to preserve

    Returns: {score, keep_change, issue_delta, severity_improvement, notes}
    """
    # Parse inputs
    if isinstance(before_issues, str):
        before_issues = json.loads(before_issues)
    if isinstance(after_issues, str):
        after_issues = json.loads(after_issues)

    targets = _parse_json_param(target_dimensions, "target_dimensions")
    prot = _parse_json_param(protect, "protect")

    # Convert raw dicts back to CompositionIssue objects
    before = [engine.CompositionIssue(**{k: v for k, v in i.items()
              if k in ("issue_type", "critic", "severity", "confidence",
                       "scope", "recommended_moves", "evidence")})
              for i in before_issues]
    after = [engine.CompositionIssue(**{k: v for k, v in i.items()
             if k in ("issue_type", "critic", "severity", "confidence",
                      "scope", "recommended_moves", "evidence")})
             for i in after_issues]

    return engine.evaluate_composition_move(before, after, targets, prot)
