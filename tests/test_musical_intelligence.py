"""Tests for musical intelligence detectors."""

import pytest

from mcp_server.musical_intelligence.detectors import (
    detect_repetition_fatigue,
    detect_role_conflicts,
    infer_section_purposes,
    score_emotional_arc,
    FatigueReport,
    RoleConflict,
    SectionPurpose,
    ArcScore,
)


# ═══ Repetition Fatigue ═══════════════════════════════════════════════

def test_no_fatigue_with_unique_clips():
    scenes = [
        {"name": "A", "clips": [{"name": "Clip 1", "state": "stopped"}]},
        {"name": "B", "clips": [{"name": "Clip 2", "state": "stopped"}]},
        {"name": "C", "clips": [{"name": "Clip 3", "state": "stopped"}]},
    ]
    report = detect_repetition_fatigue(scenes)
    assert report.fatigue_level < 0.3


def test_fatigue_with_overused_clips():
    clip = {"name": "Same Loop", "state": "stopped"}
    scenes = [
        {"name": "A", "clips": [clip]},
        {"name": "B", "clips": [clip]},
        {"name": "C", "clips": [clip]},
        {"name": "D", "clips": [clip]},
    ]
    report = detect_repetition_fatigue(scenes)
    assert report.fatigue_level > 0.2
    assert any(i["type"] == "clip_overuse" for i in report.issues)


def test_fatigue_with_motif_graph():
    scenes = [{"name": "A", "clips": []}]
    motif_graph = {
        "motifs": [
            {"motif_id": "motif_001", "fatigue_risk": 0.8},
            {"motif_id": "motif_002", "fatigue_risk": 0.3},
        ]
    }
    report = detect_repetition_fatigue(scenes, motif_graph)
    assert any(i["type"] == "motif_overuse" for i in report.issues)


def test_fatigue_empty_scenes():
    report = detect_repetition_fatigue([])
    assert report.fatigue_level == 0.0


def test_fatigue_recommendations():
    clip = {"name": "Loop", "state": "stopped"}
    scenes = [{"name": f"S{i}", "clips": [clip]} for i in range(5)]
    report = detect_repetition_fatigue(scenes)
    assert len(report.recommendations) > 0


# ═══ Role Conflicts ═══════════════════════════════════════════════════

def test_no_conflicts_clean_session():
    tracks = [
        {"index": 0, "name": "Drums"},
        {"index": 1, "name": "Sub Bass"},
        {"index": 2, "name": "Rhodes"},
        {"index": 3, "name": "Lead Synth"},
    ]
    conflicts = detect_role_conflicts(tracks)
    # Should have no conflicts (each role is unique)
    real_conflicts = [c for c in conflicts if len(c.tracks) > 1]
    assert len(real_conflicts) == 0


def test_bass_conflict():
    tracks = [
        {"index": 0, "name": "Sub Bass"},
        {"index": 1, "name": "808 Bass"},
        {"index": 2, "name": "Drums"},
    ]
    conflicts = detect_role_conflicts(tracks)
    bass_conflicts = [c for c in conflicts if c.role == "bass"]
    assert len(bass_conflicts) == 1
    assert len(bass_conflicts[0].tracks) == 2


def test_missing_essential_role():
    tracks = [
        {"index": 0, "name": "Synth Pad"},
        {"index": 1, "name": "Lead Melody"},
    ]
    conflicts = detect_role_conflicts(tracks)
    missing = [c for c in conflicts if len(c.tracks) == 0]
    assert len(missing) >= 1  # Missing bass and/or drums


def test_conflict_severity():
    tracks = [
        {"index": 0, "name": "Lead A"},
        {"index": 1, "name": "Lead B"},
        {"index": 2, "name": "Lead C"},
    ]
    conflicts = detect_role_conflicts(tracks)
    lead_conflict = [c for c in conflicts if c.role == "lead"]
    assert len(lead_conflict) == 1
    assert lead_conflict[0].severity > 0.5  # 3 leads = high severity


# ═══ Section Purpose Inference ═══════════════════════════════════════

def _make_scene(name, active_clips, total=6):
    clips = [{"name": f"clip_{i}", "state": "stopped"} for i in range(active_clips)]
    clips += [{"state": "empty"} for _ in range(total - active_clips)]
    return {"name": name, "clips": clips}


def test_intro_detection():
    scenes = [
        _make_scene("Intro", 2),
        _make_scene("Full", 6),
    ]
    purposes = infer_section_purposes(scenes, total_tracks=6)
    assert purposes[0].purpose == "setup"


def test_payoff_detection():
    scenes = [
        _make_scene("Intro", 2),
        _make_scene("Build", 4),
        _make_scene("Drop", 6),
        _make_scene("Break", 2),
        _make_scene("Outro", 1),
    ]
    purposes = infer_section_purposes(scenes, total_tracks=6)
    # The full-density scene should be payoff
    high_energy = [p for p in purposes if p.energy >= 0.8]
    assert len(high_energy) >= 1


def test_contrast_detection():
    scenes = [
        _make_scene("Full", 6),
        _make_scene("Breakdown", 2),
        _make_scene("Return", 6),
    ]
    purposes = infer_section_purposes(scenes, total_tracks=6)
    contrasts = [p for p in purposes if p.purpose == "contrast"]
    assert len(contrasts) >= 1


def test_empty_scenes():
    purposes = infer_section_purposes([], total_tracks=6)
    assert len(purposes) == 0


# ═══ Emotional Arc Scoring ═══════════════════════════════════════════

def test_good_arc():
    sections = [
        SectionPurpose(name="Intro", purpose="setup", energy=0.3),
        SectionPurpose(name="Build", purpose="tension", energy=0.6),
        SectionPurpose(name="Drop", purpose="payoff", energy=0.9),
        SectionPurpose(name="Break", purpose="contrast", energy=0.4),
        SectionPurpose(name="Outro", purpose="release", energy=0.2),
    ]
    arc = score_emotional_arc(sections)
    assert arc.overall > 0.5
    assert arc.arc_clarity > 0.5
    assert arc.contrast > 0.5
    assert arc.resolution > 0.5


def test_flat_arc():
    sections = [
        SectionPurpose(name="A", purpose="development", energy=0.5),
        SectionPurpose(name="B", purpose="development", energy=0.5),
        SectionPurpose(name="C", purpose="development", energy=0.5),
    ]
    arc = score_emotional_arc(sections)
    assert arc.contrast < 0.3
    assert len(arc.issues) > 0
    assert any("contrast" in i.lower() for i in arc.issues)


def test_no_resolution():
    sections = [
        SectionPurpose(name="Build", purpose="tension", energy=0.6),
        SectionPurpose(name="Peak", purpose="payoff", energy=0.9),
        SectionPurpose(name="Still Peak", purpose="payoff", energy=0.9),
    ]
    arc = score_emotional_arc(sections)
    assert arc.resolution < 0.5
    assert any("resolution" in i.lower() for i in arc.issues)


def test_arc_empty():
    arc = score_emotional_arc([])
    assert arc.overall == 0.0
    assert len(arc.issues) > 0
