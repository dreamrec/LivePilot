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
import logging
from typing import Optional

from fastmcp import Context

from ..server import mcp
from ..memory.technique_store import TechniqueStore
from . import _composition_engine as engine

logger = logging.getLogger(__name__)

_memory_store = TechniqueStore()


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
    except Exception as exc:
        logger.warning("get_scene_matrix failed, using empty matrix: %s", exc)
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
        except Exception as exc:
            logger.debug("arrangement_clips track=%s skipped: %s", track.get("index"), exc)

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
        except Exception as exc:
            logger.debug("get_track_info track=%s fallback: %s", track.get("index"), exc)
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
            except Exception as exc:
                logger.debug("get_notes t=%d s=%d skipped: %s", t_idx, s_idx, exc)
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

    # Collect notes for active tracks — use the section's scene_index
    # (which maps to the actual clip slot), not the section_index
    # (which is a position in the section graph)
    notes_by_track: dict[int, list] = {}
    scene_idx = section.scene_index if hasattr(section, "scene_index") else section_index
    for t_idx in section.tracks_active:
        try:
            result = ableton.send_command("get_notes", {
                "track_index": t_idx,
                "clip_index": scene_idx,
            })
            notes_by_track[t_idx] = result.get("notes", [])
        except Exception as exc:
            logger.debug("get_notes t=%d s=%d empty: %s", t_idx, scene_idx, exc)
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


# ── get_harmony_field (Round 1) ───────────────────────────────────────


@mcp.tool()
def get_harmony_field(
    ctx: Context,
    section_index: int = 0,
) -> dict:
    """Analyze the harmonic content of a section — key, chords, voice-leading, tension.

    Combines identify_scale, analyze_harmony, classify_progression, and
    find_voice_leading_path into a single structured HarmonyField.

    section_index: which section to analyze (0-based, from get_section_graph).
    Returns: key, mode, chord_progression, voice_leading_quality, instability,
    resolution_potential.
    """
    ableton = _get_ableton(ctx)
    session = ableton.send_command("get_session_info")
    scenes = session.get("scenes", [])
    tracks = session.get("tracks", [])
    track_count = session.get("track_count", 0)

    clip_matrix = _build_clip_matrix(ableton, len(scenes), track_count)
    sections = engine.build_section_graph_from_scenes(scenes, clip_matrix, track_count)

    if section_index < 0 or section_index >= len(sections):
        return {"error": f"section_index {section_index} out of range (0-{len(sections) - 1})"}

    section = sections[section_index]

    # Find a track with notes to analyze harmony
    # Use theory engine functions directly instead of TCP calls to MCP tools
    from . import _theory_engine as theory_engine
    from . import _harmony_engine as harmony_engine

    scale_info = None
    harmony_analysis = None
    progression_info = None
    voice_leading_info = None

    for t_idx in section.tracks_active:
        try:
            # Get notes via TCP (valid Remote Script command)
            result = ableton.send_command("get_notes", {
                "track_index": t_idx, "clip_index": section_index,
            })
            notes = result.get("notes", [])
            if not notes:
                continue

            # identify_scale: run key detection directly
            if not scale_info:
                detected = theory_engine.detect_key(notes, mode_detection=True)
                top = {
                    "key": f"{detected['tonic_name']} {detected['mode'].replace('_', ' ')}",
                    "confidence": detected["confidence"],
                    "mode": detected["mode"].replace("_", " "),
                    "mode_id": detected["mode"],
                    "tonic": detected["tonic_name"],
                }
                scale_info = {"top_match": top}

            # analyze_harmony: chordify + roman numeral analysis directly
            if not harmony_analysis:
                key_info = theory_engine.detect_key(notes)
                tonic = key_info["tonic"]
                mode = key_info["mode"]
                chord_groups = theory_engine.chordify(notes)
                if chord_groups:
                    chords = []
                    for group in chord_groups:
                        pitches = group["pitches"]
                        pcs = group["pitch_classes"]
                        rn = theory_engine.roman_numeral(pcs, tonic, mode)
                        cn = theory_engine.chord_name(pitches)
                        chords.append({
                            "beat": group["beat"],
                            "duration": group["duration"],
                            "chord_name": cn,
                            "roman_numeral": rn["figure"],
                            "figure": rn["figure"],
                            "quality": rn["quality"],
                        })
                    if chords:
                        harmony_analysis = {
                            "key": f"{key_info['tonic_name']} {mode.replace('_', ' ')}",
                            "chords": chords,
                        }

                        # classify_progression directly
                        chord_names = [c["chord_name"] for c in chords if c.get("chord_name")]
                        if len(chord_names) >= 2:
                            try:
                                parsed = [harmony_engine.parse_chord(c) for c in chord_names[:8]]
                                transforms = harmony_engine.classify_transform_sequence(parsed)
                                pattern = "".join(transforms)
                                classification = "free neo-Riemannian progression"
                                clean = pattern.replace("?", "")
                                if len(clean) >= 2:
                                    pair = clean[:2]
                                    if pair in ("PL", "LP") and all(c in "PL" for c in clean):
                                        classification = "hexatonic cycle fragment"
                                    elif pair in ("PR", "RP") and all(c in "PR" for c in clean):
                                        classification = "octatonic cycle fragment"
                                    elif pair in ("LR", "RL") and all(c in "LR" for c in clean):
                                        classification = "diatonic cycle fragment"
                                progression_info = {
                                    "chords": chord_names[:8],
                                    "transforms": transforms,
                                    "pattern": pattern,
                                    "classification": classification,
                                }
                            except Exception as exc:
                                logger.warning("neo-Riemannian classify failed: %s", exc)

            # Populate voice_leading_info from chord groups
            if harmony_analysis and not voice_leading_info:
                try:
                    chord_groups_vl = theory_engine.chordify(notes)
                    if len(chord_groups_vl) >= 2:
                        all_vl_issues = []
                        for vi in range(1, min(len(chord_groups_vl), 9)):
                            prev_p = chord_groups_vl[vi - 1]["pitches"]
                            curr_p = chord_groups_vl[vi]["pitches"]
                            issues = theory_engine.check_voice_leading(prev_p, curr_p)
                            all_vl_issues.extend(issues)
                        voice_leading_info = {
                            "issues": all_vl_issues,
                            "issue_count": len(all_vl_issues),
                            "quality": "clean" if not all_vl_issues else "has_issues",
                        }
                except Exception as exc:
                    logger.warning("voice_leading analysis failed: %s", exc)

            if scale_info and harmony_analysis:
                break
        except Exception as exc:
            logger.debug("harmony scan on track %d skipped: %s", t_idx, exc)
            continue

    hf = engine.build_harmony_field(
        section_id=section.section_id,
        harmony_analysis=harmony_analysis,
        scale_info=scale_info,
        progression_info=progression_info,
        voice_leading_info=voice_leading_info,
    )
    result = hf.to_dict()
    result["section_name"] = section.name
    return result


# ── get_transition_analysis (Round 1) ─────────────────────────────────


@mcp.tool()
def get_transition_analysis(ctx: Context) -> dict:
    """Analyze transition quality between all adjacent sections.

    Checks for: hard cuts, missing pre-arrival subtraction, groove breaks,
    harmonic non-sequiturs, and weak builds without role rotation.

    Returns issues with recommended composition moves for each boundary.
    """
    ableton = _get_ableton(ctx)
    session = ableton.send_command("get_session_info")
    scenes = session.get("scenes", [])
    tracks = session.get("tracks", [])
    track_count = session.get("track_count", 0)

    clip_matrix = _build_clip_matrix(ableton, len(scenes), track_count)
    sections = engine.build_section_graph_from_scenes(scenes, clip_matrix, track_count)

    if len(sections) < 2:
        return {"issues": [], "note": "Need at least 2 sections for transition analysis"}

    # Build role graph for transition critic
    track_data = []
    notes_map: dict[str, dict[int, list]] = {}
    for track in tracks:
        t_idx = track["index"]
        try:
            ti = ableton.send_command("get_track_info", {"track_index": t_idx})
            track_data.append(ti)
        except Exception as exc:
            logger.debug("get_track_info transition t=%d fallback: %s", t_idx, exc)
            track_data.append({"index": t_idx, "name": track.get("name", ""), "devices": []})

    for section in sections:
        notes_map[section.section_id] = {}
        for t_idx in section.tracks_active:
            notes_map[section.section_id][t_idx] = []

    roles = engine.build_role_graph(sections, track_data, notes_map)

    # Build harmony fields (lightweight — skip if tools fail)
    harmony_fields = []
    for i, section in enumerate(sections):
        hf = engine.HarmonyField(section_id=section.section_id)
        harmony_fields.append(hf)

    issues = engine.run_transition_critic(sections, roles, harmony_fields)

    return {
        "transition_count": len(sections) - 1,
        "issues": [i.to_dict() for i in issues],
        "issue_count": len(issues),
    }


# ── apply_gesture_template (Round 2) ──────────────────────────────────


@mcp.tool()
def apply_gesture_template(
    ctx: Context,
    template_name: str,
    target_tracks: list | str = "[]",
    anchor_bar: int = 0,
    foreground: bool = False,
) -> dict:
    """Apply a compound gesture template — multiple coordinated automation gestures.

    template_name: pre_arrival_vacuum | sectional_width_bloom | phrase_end_throw |
                   turnaround_accent | outro_decay_dissolve | bass_tuck_before_kick |
                   harmonic_tint_rise | response_echo | texture_drift_bed |
                   tension_ratchet | re_entry_spotlight
    target_tracks: list of track indices
    anchor_bar: reference point (section boundary bar number)
    foreground: is this a focal point?

    Returns: list of GesturePlans — execute each with apply_automation_shape.
    """
    if isinstance(target_tracks, str):
        try:
            target_tracks = json.loads(target_tracks)
        except json.JSONDecodeError:
            target_tracks = []

    plans = engine.resolve_gesture_template(
        template_name, target_tracks, anchor_bar, foreground,
    )
    return {
        "template": template_name,
        "description": engine.GESTURE_TEMPLATES[template_name]["description"],
        "gesture_count": len(plans),
        "gestures": [g.to_dict() for g in plans],
    }


# ── get_section_outcomes (Round 2) ────────────────────────────────────


@mcp.tool()
def get_section_outcomes(
    ctx: Context,
    section_type: str = "",
    limit: int = 50,
) -> dict:
    """Get composition move success rates grouped by section type.

    Analyzes stored composition outcomes to answer: which moves work
    best in which section types? Use before making structural changes
    to learn from past sessions.

    section_type: filter to a specific type (intro, verse, chorus, etc.)
                  Leave empty for all types.
    """
    # Fetch composition outcomes directly from TechniqueStore
    try:
        techniques = _memory_store.list_techniques(
            type_filter="composition_outcome", sort_by="updated_at", limit=limit,
        )
    except Exception as exc:
        logger.warning("list_techniques(composition_outcome) failed: %s", exc)
        techniques = []

    outcomes = []
    for t in techniques:
        try:
            full = _memory_store.get(t["id"])
            payload = full.get("payload", {})
            if isinstance(payload, dict):
                outcomes.append(payload)
        except Exception as exc:
            logger.debug("technique %s payload read failed: %s", t.get("id"), exc)

    result = engine.analyze_section_outcomes(outcomes)

    if section_type and section_type in result.get("outcomes_by_section", {}):
        result["filtered_section"] = section_type
        result["section_moves"] = result["outcomes_by_section"][section_type]

    return result
