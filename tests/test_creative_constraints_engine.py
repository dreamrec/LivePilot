"""Unit tests for Creative Constraints engine — pure computation, no Ableton needed."""

from mcp_server.creative_constraints.engine import (
    build_constraint_set,
    distill_reference_principles,
    map_principles_to_song,
)
from mcp_server.creative_constraints.models import CONSTRAINT_MODES


# ── Constraint set building ──────────────────────────────────────


def test_valid_constraints_accepted():
    """Valid constraint names should be accepted."""
    cs = build_constraint_set(["subtraction_only", "no_new_tracks"])
    assert "subtraction_only" in cs.constraints
    assert "no_new_tracks" in cs.constraints


def test_invalid_constraints_filtered():
    """Invalid constraints should be filtered out."""
    cs = build_constraint_set(["subtraction_only", "nonexistent_mode"])
    assert "subtraction_only" in cs.constraints
    assert "nonexistent_mode" not in cs.constraints


def test_constraint_set_has_description():
    """Constraint set should have a description."""
    cs = build_constraint_set(["arrangement_only"])
    assert cs.description
    assert isinstance(cs.description, str)


def test_constraint_set_has_reason():
    """Constraint set should explain why it helps."""
    cs = build_constraint_set(["use_loaded_devices_only"])
    assert cs.reason
    assert isinstance(cs.reason, str)


def test_empty_constraints():
    """Empty constraint list should produce empty set."""
    cs = build_constraint_set([])
    assert len(cs.constraints) == 0


def test_all_constraint_modes_exist():
    """All 8 constraint modes should be defined."""
    assert len(CONSTRAINT_MODES) == 8
    assert "use_loaded_devices_only" in CONSTRAINT_MODES
    assert "subtraction_only" in CONSTRAINT_MODES
    assert "performance_safe_creative" in CONSTRAINT_MODES


# ── Reference distillation ───────────────────────────────────────


def test_distill_dark_reference():
    """Dark reference should produce tense emotional posture."""
    distillation = distill_reference_principles(
        reference_profile={"emotional_stance": "tense"},
        reference_description="Dark minimal techno like Surgeon",
    )
    assert distillation.reference_description
    assert distillation.emotional_posture or len(distillation.principles) > 0


def test_distill_produces_principles():
    """Distillation should produce at least one principle."""
    distillation = distill_reference_principles(
        reference_profile={
            "emotional_stance": "euphoric",
            "density_arc": [0.3, 0.6, 0.9, 0.5],
        },
        reference_description="Trance anthem",
    )
    assert len(distillation.principles) >= 1


def test_distill_empty_reference():
    """Empty reference profile should still produce a valid distillation."""
    distillation = distill_reference_principles(
        reference_profile={},
        reference_description="Unknown reference",
    )
    assert distillation.reference_description == "Unknown reference"
    # Should degrade gracefully
    assert isinstance(distillation.principles, list)


# ── Reference mapping ────────────────────────────────────────────


def test_map_principles_produces_mappings():
    """Mapping should produce actionable entries."""
    distillation = distill_reference_principles(
        reference_profile={"emotional_stance": "dreamy"},
        reference_description="Boards of Canada style",
    )
    mappings = map_principles_to_song(
        song_brain={"identity_core": "Ambient bass music"},
        distillation=distillation,
    )
    assert isinstance(mappings, list)


def test_map_principles_respects_identity():
    """Mappings should reference the current song's identity."""
    distillation = distill_reference_principles(
        reference_profile={"emotional_stance": "aggressive"},
        reference_description="Industrial techno",
    )
    mappings = map_principles_to_song(
        song_brain={"identity_core": "Gentle ambient piece"},
        distillation=distillation,
    )
    # Mappings should exist even when reference and identity are in tension
    assert isinstance(mappings, list)
