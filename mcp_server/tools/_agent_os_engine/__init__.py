"""Agent OS engine — goal compilation, world model, evaluation.

This package replaces the former single-file `_agent_os_engine.py`.
Public surface unchanged — callers import the same names.

Internal organization:
    models.py       — Dataclasses + module-level constants
    world_model.py  — Goal validation, role inference, world-model build
    critics.py      — Sonic + technical critics
    evaluation.py   — Scoring, dimension extraction, clamp helpers
    techniques.py   — TechniqueCard mining + building
    taste.py        — Outcome analysis, taste fit, taste profile
"""
from __future__ import annotations

from .models import (
    QUALITY_DIMENSIONS, MEASURABLE_PROXIES,
    VALID_MODES, VALID_RESEARCH_MODES,
    GoalVector, WorldModel, Issue, TechniqueCard,
)
from .world_model import (
    validate_goal_vector,
    infer_track_role,
    build_world_model_from_data,
)
from .critics import run_sonic_critic, run_technical_critic
from .evaluation import compute_evaluation_score, _extract_dimension_value
from .techniques import (
    build_technique_card_from_outcome,
    should_mine_technique,
    mine_technique_from_outcome,
)
from .taste import (
    analyze_outcome_history,
    compute_taste_fit,
    get_taste_profile,
)

__all__ = [
    "QUALITY_DIMENSIONS", "MEASURABLE_PROXIES",
    "VALID_MODES", "VALID_RESEARCH_MODES",
    "GoalVector", "WorldModel", "Issue", "TechniqueCard",
    "validate_goal_vector", "infer_track_role", "build_world_model_from_data",
    "run_sonic_critic", "run_technical_critic",
    "compute_evaluation_score",
    "build_technique_card_from_outcome",
    "should_mine_technique",
    "mine_technique_from_outcome",
    "analyze_outcome_history",
    "compute_taste_fit",
    "get_taste_profile",
]
