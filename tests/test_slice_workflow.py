"""Tests for plan_slice_workflow tool (Phase 4)."""
import pytest
from mcp_server.sample_engine.slice_workflow import plan_slice_steps


def test_rhythm_intent_produces_notes():
    result = plan_slice_steps(slice_count=8, intent="rhythm", bars=4, tempo=120)
    assert "steps" in result
    assert "note_map" in result
    notes_step = [s for s in result["steps"] if s["tool"] == "add_notes"]
    assert len(notes_step) > 0
    notes = notes_step[0]["params"]["notes"]
    assert len(notes) > 0


def test_texture_intent_produces_sparse_notes():
    result = plan_slice_steps(slice_count=4, intent="texture", bars=4, tempo=120)
    notes_step = [s for s in result["steps"] if s["tool"] == "add_notes"]
    notes = notes_step[0]["params"]["notes"]
    assert len(notes) <= 8  # Texture = sparse


def test_hook_intent_produces_repeated_motif():
    result = plan_slice_steps(slice_count=16, intent="hook", bars=4, tempo=120)
    notes_step = [s for s in result["steps"] if s["tool"] == "add_notes"]
    notes = notes_step[0]["params"]["notes"]
    assert len(notes) >= 4


def test_percussion_intent():
    result = plan_slice_steps(slice_count=8, intent="percussion", bars=2, tempo=140)
    notes_step = [s for s in result["steps"] if s["tool"] == "add_notes"]
    assert len(notes_step) > 0


def test_melodic_intent():
    result = plan_slice_steps(slice_count=6, intent="melodic", bars=4, tempo=90)
    notes_step = [s for s in result["steps"] if s["tool"] == "add_notes"]
    assert len(notes_step) > 0


def test_note_map_matches_slice_count():
    result = plan_slice_steps(slice_count=8, intent="rhythm", bars=4, tempo=120)
    assert len(result["note_map"]) == 8


def test_all_notes_have_required_fields():
    result = plan_slice_steps(slice_count=8, intent="rhythm", bars=4, tempo=120)
    notes_step = [s for s in result["steps"] if s["tool"] == "add_notes"]
    for note in notes_step[0]["params"]["notes"]:
        assert "pitch" in note
        assert "start_time" in note
        assert "duration" in note
        assert "velocity" in note


def test_suggested_techniques_returned():
    result = plan_slice_steps(slice_count=8, intent="rhythm", bars=4, tempo=120)
    assert "suggested_techniques" in result
    assert isinstance(result["suggested_techniques"], list)


def test_steps_include_create_clip():
    result = plan_slice_steps(slice_count=8, intent="rhythm", bars=4, tempo=120)
    create_steps = [s for s in result["steps"] if s["tool"] == "create_clip"]
    assert len(create_steps) == 1


def test_unknown_intent_defaults_to_rhythm():
    result = plan_slice_steps(slice_count=4, intent="unknown_xyz", bars=2, tempo=120)
    notes_step = [s for s in result["steps"] if s["tool"] == "add_notes"]
    assert len(notes_step) > 0  # Falls back to rhythm
