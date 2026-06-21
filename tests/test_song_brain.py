"""Unit tests for SongBrain builder — pure computation, no Ableton needed."""

from mcp_server.song_brain.builder import (
    build_song_brain,
    detect_identity_drift,
    _infer_identity_core,
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


# ─── BUG-B10 regressions — richer identity inference ──────────────────────


def test_bug_b10_drums_dominant_texture_no_longer_wins():
    """BUG-B10: 'Dominant texture: drums' used to win at confidence 0.5
    on virtually every session. After the fix, drums are excluded from
    that signal stream — the caller gets a more meaningful identity
    (e.g. vocal hook / pad-led atmosphere / aesthetic keyword)."""
    # Session where drums are the most-roled tracks, but a clear vocal
    # track is present — expect vocal hook to win over "drums".
    identity, conf = _infer_identity_core(
        tracks=[
            {"name": "Kick", "index": 0},
            {"name": "Snare", "index": 1},
            {"name": "Hi-Hat", "index": 2},
            {"name": "VOX Hook", "index": 3},
        ],
        motif_data={},
        composition={},
        role_graph={
            "Kick": {"role": "drums"},
            "Snare": {"role": "drums"},
            "Hi-Hat": {"role": "drums"},
            "VOX Hook": {"role": "lead"},
        },
    )
    # The drum-texture candidate is now explicitly skipped
    assert "drums" not in identity.lower(), (
        f"BUG-B10 regressed — drums still claimed identity: {identity!r}"
    )
    # And vocal-featured element should win
    assert "vocal" in identity.lower()


def test_bug_b10_blends_top_two_when_no_clear_winner():
    """When no candidate crosses the 0.6 confidence threshold, the
    builder blends the top 2 into a compound identity."""
    identity, conf = _infer_identity_core(
        tracks=[{"name": "Pad Lush", "index": 0}],
        motif_data={},
        composition={"sections": [{"name": "Intro Dust"}, {"name": "Outro Dust"}]},
        role_graph={},
    )
    # Pad-led (0.55) + dust aesthetic (0.55) should blend
    assert " + " in identity, (
        f"BUG-B10 regressed — weak candidates should blend: {identity!r}"
    )
    # Confidence of the blend should be boosted above the raw max
    assert conf > 0.55


def test_bug_b10_fallback_when_no_signals():
    """No data at all — fall back to 'Emerging piece' at low confidence."""
    identity, conf = _infer_identity_core(
        tracks=[], motif_data={}, composition={}, role_graph={},
    )
    assert "Emerging" in identity or "not yet" in identity
    assert conf < 0.3


# ─── BUG-B13 regressions — energy shape classifier ───────────────────────


def test_bug_b13_dual_peak_not_labeled_front_loaded():
    """BUG-B13: [0.7, 0.9, 0.9, 0.5, 0.6, 0.9, 0.4, 0] has peaks at
    positions 1, 2, AND 5 — that's a dual-peak shape, not front-loaded.
    The old classifier only checked max's first occurrence and mislabeled
    it 'front-loaded — peaks early'."""
    from mcp_server.song_brain.tools import classify_energy_shape
    result = classify_energy_shape([0.7, 0.9, 0.9, 0.5, 0.6, 0.9, 0.4, 0])
    assert "dual-peak" in result["shape"].lower(), (
        f"BUG-B13 regressed — dual-peak arc still labeled '{result['shape']}'"
    )


def test_bug_b13_genuinely_front_loaded_stays_front_loaded():
    """[0.9, 0.9, 0.5, 0.3, 0.2] — true front-loaded arc, should stay
    labeled as such."""
    from mcp_server.song_brain.tools import classify_energy_shape
    result = classify_energy_shape([0.9, 0.9, 0.5, 0.3, 0.2])
    assert result["shape"].startswith("front-loaded")


def test_bug_b13_slow_burn_detected():
    """[0.2, 0.3, 0.4, 0.6, 0.9, 0.9] — slow burn to late peak."""
    from mcp_server.song_brain.tools import classify_energy_shape
    result = classify_energy_shape([0.2, 0.3, 0.4, 0.6, 0.9, 0.9])
    assert result["shape"].startswith("slow burn")


def test_bug_b13_plateau_detected():
    """[0.7, 0.8, 0.8, 0.75, 0.8, 0.75, 0.8] — tight dynamic range,
    sustained energy → plateau."""
    from mcp_server.song_brain.tools import classify_energy_shape
    result = classify_energy_shape([0.7, 0.8, 0.8, 0.75, 0.8, 0.75, 0.8])
    assert result["shape"].startswith("plateau")


def test_bug_b13_peak_positions_returned():
    """The classifier must expose peak positions so downstream tools
    can reason about arrangement structure without re-computing."""
    from mcp_server.song_brain.tools import classify_energy_shape
    result = classify_energy_shape([0.7, 0.9, 0.9, 0.5, 0.6, 0.9, 0.4])
    assert result["peak_positions"] is not None
    assert len(result["peak_positions"]) >= 2


def test_bug_b13_short_arc_falls_back_gracefully():
    """Arcs of fewer than 3 points can't be classified meaningfully."""
    from mcp_server.song_brain.tools import classify_energy_shape
    assert "short form" in classify_energy_shape([0.5]).get("shape", "").lower()
    assert "short form" in classify_energy_shape([0.5, 0.7]).get("shape", "").lower()


# ─── BUG-B16 regressions — session_story wiring to song_brain ─────────────


def test_bug_b16_session_story_includes_song_brain_id():
    """BUG-B16: get_session_story used to leave song_brain_id empty —
    users couldn't tell which brain generated the identity_summary.
    The fix populates song_brain_id from the passed brain dict."""
    from mcp_server.session_continuity.tracker import (
        get_session_story, reset_story,
    )
    reset_story()
    brain = {
        "brain_id": "brain_abc123",
        "identity_core": "vocal hook + dust aesthetic",
    }
    story = get_session_story(song_brain=brain)
    assert story.song_brain_id == "brain_abc123"
    assert story.identity_summary == "vocal hook + dust aesthetic"
    # to_dict exposes the field so MCP clients see it
    d = story.to_dict()
    assert d.get("song_brain_id") == "brain_abc123"


def test_bug_b16_empty_brain_leaves_song_brain_id_blank():
    """When no brain is available, song_brain_id stays empty (not None)."""
    from mcp_server.session_continuity.tracker import (
        get_session_story, reset_story,
    )
    reset_story()
    story = get_session_story(song_brain={})
    assert story.song_brain_id == ""


# ─── BUG-B22 regressions — phrase note_density accounts for clip looping ───


def test_bug_b22_looped_clip_fills_whole_section():
    """BUG-B22: a 4-bar looping clip in an 8-bar section used to leave
    bars 4-7 with note_density=0 because the algorithm positioned notes
    at absolute bars section.start_bar + clip_bar only. After the fix
    notes repeat across the section via modulo projection."""
    from mcp_server.tools._composition_engine import (
        SectionNode,
        SectionType,
        detect_phrases,
    )
    # Section: bars 8..16 (8 bars), density 0.9
    section = SectionNode(
        section_id="sec_01",
        start_bar=8,
        end_bar=16,
        section_type=SectionType.BUILD,
        confidence=0.85,
        energy=0.9,
        density=0.9,
        tracks_active=[0],
        name="Groove Build",
    )
    # Single 4-bar clip with notes on beats 0, 4, 8, 12 (one per bar)
    notes_by_track = {
        0: [
            {"pitch": 60, "start_time": 0.0, "duration": 0.5},
            {"pitch": 60, "start_time": 4.0, "duration": 0.5},
            {"pitch": 60, "start_time": 8.0, "duration": 0.5},
            {"pitch": 60, "start_time": 12.0, "duration": 0.5},
        ],
    }
    phrases = detect_phrases(section, notes_by_track)
    # Every phrase inside an 8-bar section with a 4-bar looping clip
    # should have non-zero note_density — the loop fills both halves.
    densities = [p.note_density for p in phrases]
    assert all(d > 0 for d in densities), (
        f"BUG-B22 regressed — some phrase has zero density: {densities}"
    )
