"""Composition engine — structural + musical intelligence for arrangement.

This package replaces the former single-file `_composition_engine.py`.
The public surface is unchanged — callers import the same names:

    from mcp_server.tools._composition_engine import (
        SectionType, RoleType, GestureIntent,
        build_section_graph_from_scenes, detect_phrases,
        run_form_critic, plan_gesture, ...,
    )

Internal organization:
    models.py     — Enums and dataclasses (shared types)
    sections.py   — Section graph, phrase grid, role inference
    critics.py    — Form / identity / phrase / transition / emotional / cross-section
    gestures.py   — Gesture planner and template library
    harmony.py    — Harmony field construction
    analysis.py   — Composition evaluation, outcomes, taste model, constants
"""
from __future__ import annotations

from .models import (
    SectionType, RoleType, GestureIntent,
    SectionNode, PhraseUnit, RoleNode, CompositionIssue,
    GesturePlan, CompositionAnalysis, HarmonyField,
)
from .sections import (
    build_section_graph_from_scenes,
    build_section_graph_from_arrangement,
    detect_phrases,
    infer_role_for_track,
    build_role_graph,
)
from .critics import (
    run_form_critic,
    run_section_identity_critic,
    run_phrase_critic,
    run_transition_critic,
    run_emotional_arc_critic,
    run_cross_section_critic,
)
from .gestures import (
    GESTURE_TEMPLATES,
    plan_gesture,
    resolve_gesture_template,
)
from .harmony import build_harmony_field
from .analysis import (
    COMPOSITION_DIMENSIONS,
    analyze_section_outcomes,
    evaluate_composition_move,
    build_composition_taste_model,
)

__all__ = [
    "SectionType", "RoleType", "GestureIntent",
    "SectionNode", "PhraseUnit", "RoleNode", "CompositionIssue",
    "GesturePlan", "CompositionAnalysis", "HarmonyField",
    "build_section_graph_from_scenes", "build_section_graph_from_arrangement",
    "detect_phrases", "infer_role_for_track", "build_role_graph",
    "run_form_critic", "run_section_identity_critic", "run_phrase_critic",
    "run_transition_critic", "run_emotional_arc_critic", "run_cross_section_critic",
    "GESTURE_TEMPLATES", "plan_gesture", "resolve_gesture_template",
    "build_harmony_field",
    "COMPOSITION_DIMENSIONS", "analyze_section_outcomes",
    "evaluate_composition_move", "build_composition_taste_model",
]
