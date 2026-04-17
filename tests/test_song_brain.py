"""Unit tests for SongBrain builder — pure computation, no Ableton needed."""

from mcp_server.song_brain.builder import (
    build_song_brain,
    detect_identity_drift,
)
from mcp_server.song_brain.models import SacredElement, SongBrain


# ── Identity core inference ──────────────────────────────────────


def test_identity_core_prefers_high_salience_motif():
    """Recurring motif with high salience should beat genre cues."""
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 4},
        tracks=[{"name": "808", "index": 0}, {"name": "Pad", "index": 1}],
        motif_data={
            "motifs": [
                {"name": "main_hook", "salience": 0.8, "description": "Rising synth arpeggio"},
            ]
        },
    )
    assert "arpeggio" in brain.identity_core.lower() or "motif" in brain.identity_core.lower()
    # Evidence-weighted: with only motif+tracks (no composition/roles/scenes),
    # adjusted confidence = raw * (0.4 + 0.6 * evidence_score)
    assert brain.identity_confidence >= 0.4


def test_identity_core_fallback_to_genre_cues():
    """Without motifs, fall back to genre detection from track names."""
    brain = build_song_brain(
        session_info={"tempo": 140, "track_count": 6},
        tracks=[
            {"name": "808 Kick", "index": 0},
            {"name": "808 Sub", "index": 1},
            {"name": "Hi Hat", "index": 2},
        ],
    )
    assert brain.identity_core  # Should produce something
    assert brain.identity_confidence > 0


def test_identity_core_empty_inputs():
    """All-empty inputs should degrade gracefully."""
    brain = build_song_brain(session_info={})
    assert "not yet established" in brain.identity_core.lower()
    assert brain.identity_confidence < 0.3


# ── Sacred elements ──────────────────────────────────────────────


def test_sacred_elements_only_high_salience_motifs():
    """Only motifs with salience > 0.5 should be sacred."""
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 2},
        motif_data={
            "motifs": [
                {"name": "hook", "salience": 0.7, "description": "Main melody"},
                {"name": "filler", "salience": 0.2, "description": "Background pad"},
            ]
        },
    )
    sacred_descriptions = [e.description for e in brain.sacred_elements]
    assert any("melody" in d.lower() or "hook" in d.lower() for d in sacred_descriptions)
    # Low-salience motif should NOT be sacred
    assert not any("filler" in d.lower() or "background pad" in d.lower() for d in sacred_descriptions)


def test_sacred_elements_includes_groove():
    """Primary groove tracks should be detected as sacred."""
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 3},
        tracks=[
            {"name": "Drums", "index": 0},
            {"name": "Bass", "index": 1},
            {"name": "Synth", "index": 2},
        ],
    )
    groove_sacred = [e for e in brain.sacred_elements if e.element_type == "groove"]
    assert len(groove_sacred) >= 1


def test_no_sacred_elements_when_empty():
    """Empty session should have no sacred elements."""
    brain = build_song_brain(session_info={"tempo": 120, "track_count": 0})
    assert len(brain.sacred_elements) == 0


# ── Drift detection ──────────────────────────────────────────────


def test_drift_zero_when_identical():
    """Identical brains should have 0 drift."""
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 3},
        tracks=[{"name": "Kick", "index": 0}],
    )
    drift = detect_identity_drift(brain, brain)
    assert drift.drift_score == 0.0
    assert drift.recommendation == "safe"


def test_drift_high_when_sacred_elements_lost():
    """Losing sacred elements should increase drift."""
    before = SongBrain(
        brain_id="before",
        identity_core="Rising arpeggio",
        sacred_elements=[
            SacredElement(description="Main hook", salience=0.8),
            SacredElement(description="Bass groove", salience=0.6),
        ],
        energy_arc=[0.3, 0.5, 0.8],
    )
    after = SongBrain(
        brain_id="after",
        identity_core="Rising arpeggio",
        sacred_elements=[],  # Lost all sacred elements
        energy_arc=[0.3, 0.5, 0.8],
    )
    drift = detect_identity_drift(before, after)
    assert drift.drift_score > 0.3
    assert len(drift.sacred_damage) == 2
    assert drift.recommendation in ("caution", "rollback_suggested")


def test_drift_detects_identity_core_change():
    """Changing identity core should register as drift."""
    before = SongBrain(brain_id="a", identity_core="Dark techno groove")
    after = SongBrain(brain_id="b", identity_core="Ambient soundscape")
    drift = detect_identity_drift(before, after)
    assert "identity_core" in drift.changed_elements
    assert drift.drift_score > 0


# ── Open questions ───────────────────────────────────────────────


def test_open_questions_no_payoff():
    """Should detect when no section is a payoff."""
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 4},
        scenes=[
            {"name": "Intro", "clips": [1, 0, 0, 0]},
            {"name": "Verse", "clips": [1, 1, 0, 0]},
            {"name": "Bridge", "clips": [1, 1, 1, 0]},
        ],
    )
    questions = [q.question for q in brain.open_questions]
    assert any("payoff" in q.lower() or "arrival" in q.lower() for q in questions)


def test_open_questions_single_loop():
    """Single section with multiple tracks should flag loop question."""
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 5},
        tracks=[{"name": f"Track {i}", "index": i} for i in range(5)],
        scenes=[{"name": "Loop", "clips": [1, 1, 1, 1, 1]}],
    )
    questions = [q.question for q in brain.open_questions]
    assert any("loop" in q.lower() or "form" in q.lower() for q in questions)


# ── Section purposes ────────────────────────────────────────────


def test_section_purposes_from_scene_names():
    """Should classify sections from scene names."""
    brain = build_song_brain(
        session_info={"tempo": 128, "track_count": 4},
        scenes=[
            {"name": "Intro", "clips": [1, 0, 0, 0]},
            {"name": "Drop", "clips": [1, 1, 1, 1]},
            {"name": "Outro", "clips": [1, 0, 0, 0]},
        ],
    )
    labels = [s.label for s in brain.section_purposes]
    assert "intro" in labels
    assert "drop" in labels
    assert "outro" in labels


def test_energy_arc_matches_sections():
    """Energy arc length should match section count."""
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 4},
        scenes=[
            {"name": "A", "clips": [1, 0, 0, 0]},
            {"name": "B", "clips": [1, 1, 0, 0]},
            {"name": "C", "clips": [1, 1, 1, 1]},
        ],
    )
    assert len(brain.energy_arc) == len(brain.section_purposes)


# ── Summary ──────────────────────────────────────────────────────


def test_identity_core_from_role_graph():
    """Role graph with a lead track should contribute to identity."""
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 4},
        tracks=[{"name": "Lead Synth", "index": 0}],
        role_graph={
            "Lead Synth": {"index": 0, "role": "lead"},
            "Bass": {"index": 1, "role": "bass"},
        },
    )
    assert brain.identity_confidence > 0


def test_sacred_elements_include_lead_from_role_graph():
    """Lead tracks from role graph should be detected as sacred."""
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 3},
        tracks=[
            {"name": "Lead Synth", "index": 0},
            {"name": "Bass", "index": 1},
        ],
        role_graph={
            "Lead Synth": {"index": 0, "role": "lead"},
            "Bass": {"index": 1, "role": "bass"},
        },
    )
    lead_sacred = [e for e in brain.sacred_elements if "lead" in e.description.lower()]
    assert len(lead_sacred) >= 1


def test_summary_readable():
    """Summary should be human-readable."""
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 3},
        motif_data={"motifs": [{"name": "hook", "salience": 0.7, "description": "Lead melody"}]},
        scenes=[{"name": "Intro", "clips": [1, 0, 0]}],
    )
    assert brain.summary  # Not empty
    assert isinstance(brain.summary, str)


# ── Regression tests for BUG-B11 / B12 / B14 ─────────────────────


def test_bug_b11_is_payoff_derived_from_intent():
    """BUG-B11: is_payoff must be TRUE when emotional_intent == 'payoff'
    even if the explicit flag isn't set. Composition engine returns
    intent='drop'/'chorus'/'hook'/'payoff' — all are arrival moments.
    """
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 4},
        composition_analysis={
            "sections": [
                {"name": "Intro", "id": "sec_00", "intent": "tension", "energy": 0.5},
                {"name": "Drop", "id": "sec_01", "intent": "payoff", "energy": 0.9},
                {"name": "Chorus", "id": "sec_02", "intent": "chorus", "energy": 0.9},
                {"name": "Verse", "id": "sec_03", "intent": "verse", "energy": 0.6},
                {"name": "Hook", "id": "sec_04", "intent": "hook", "energy": 0.85},
                {"name": "Build", "id": "sec_05", "intent": "drop", "energy": 0.95},
            ],
        },
    )
    purposes = {s.section_id: s for s in brain.section_purposes}
    assert purposes["sec_00"].is_payoff is False, "intro with intent='tension' is not payoff"
    assert purposes["sec_01"].is_payoff is True, "intent='payoff' must mark is_payoff"
    assert purposes["sec_02"].is_payoff is True, "intent='chorus' is a payoff moment"
    assert purposes["sec_03"].is_payoff is False, "intent='verse' is not payoff"
    assert purposes["sec_04"].is_payoff is True, "intent='hook' is a payoff moment"
    assert purposes["sec_05"].is_payoff is True, "intent='drop' is a payoff moment"


def test_bug_b11_explicit_is_payoff_flag_still_respected():
    """Explicit is_payoff=true should always win, regardless of intent."""
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 2},
        composition_analysis={
            "sections": [
                {"name": "Oddball", "id": "sec_00", "intent": "tension",
                 "energy": 0.6, "is_payoff": True},
            ],
        },
    )
    purposes = {s.section_id: s for s in brain.section_purposes}
    assert purposes["sec_00"].is_payoff is True


def test_bug_b12_empty_placeholder_sections_filtered():
    """BUG-B12: empty-name sections with zero energy pollute the energy_arc
    and section_purposes list. They should be filtered out.
    """
    brain = build_song_brain(
        session_info={"tempo": 119, "track_count": 3},
        composition_analysis={
            "sections": [
                {"name": "Intro", "id": "sec_00", "intent": "tension", "energy": 0.7},
                {"name": "Drop", "id": "sec_01", "intent": "payoff", "energy": 0.9},
                {"name": "", "id": "", "intent": "contrast", "energy": 0},  # empty
            ],
        },
    )
    # Only 2 sections should remain (the empty one is filtered)
    assert len(brain.section_purposes) == 2
    assert all(s.label for s in brain.section_purposes), \
        "No section should have empty label after filtering"
    # Energy arc shouldn't have a trailing zero from the empty section
    assert brain.energy_arc == [0.7, 0.9]


def test_bug_b12_fallback_path_filters_empty_scene_names():
    """Fallback path (no composition data) should also skip empty scenes."""
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 2},
        scenes=[
            {"name": "Intro Dust", "clips": [1, 1]},
            {"name": "Groove", "clips": [1, 1]},
            {"name": "", "clips": []},  # empty placeholder scene
        ],
    )
    # No composition data → falls back to scene-based, empty scene filtered
    assert len(brain.section_purposes) == 2


def test_bug_b14_intro_detected_via_label_substring():
    """BUG-B14: 'No intro section' should NOT fire when a section has
    'intro' in its label, even when the intent is something else.
    E.g., 'Intro Dust' with intent='tension' still has an intro.
    """
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 6},
        composition_analysis={
            "sections": [
                {"name": "Intro Dust", "id": "sec_00", "intent": "tension",
                 "energy": 0.7},
                {"name": "Build", "id": "sec_01", "intent": "tension",
                 "energy": 0.8},
                {"name": "Drop", "id": "sec_02", "intent": "payoff",
                 "energy": 0.9},
                {"name": "Break", "id": "sec_03", "intent": "contrast",
                 "energy": 0.5},
                {"name": "Outro", "id": "sec_04", "intent": "contrast",
                 "energy": 0.3},
            ],
        },
    )
    questions = [q.question for q in brain.open_questions]
    assert not any("No intro section" in q for q in questions), \
        f"'Intro Dust' label should satisfy the intro check. Got: {questions}"


def test_bug_b14_no_intro_still_flags_when_truly_missing():
    """When no section name or intent mentions intro, the check should fire."""
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 6},
        composition_analysis={
            "sections": [
                {"name": "Groove", "id": "sec_00", "intent": "tension",
                 "energy": 0.7},
                {"name": "Build", "id": "sec_01", "intent": "tension",
                 "energy": 0.8},
                {"name": "Drop", "id": "sec_02", "intent": "payoff",
                 "energy": 0.9},
                {"name": "Break", "id": "sec_03", "intent": "contrast",
                 "energy": 0.5},
                {"name": "Outro", "id": "sec_04", "intent": "contrast",
                 "energy": 0.3},
            ],
        },
    )
    questions = [q.question for q in brain.open_questions]
    assert any("No intro section" in q for q in questions), \
        "Without an intro label/intent, the check SHOULD fire."
