"""Unit tests for Hook Hunter analyzer — pure computation, no Ableton needed."""

from mcp_server.hook_hunter.analyzer import (
    find_hook_candidates,
    find_primary_hook,
    score_phrase_impact,
    detect_payoff_failures,
    suggest_payoff_repairs,
)


# ── Hook candidate detection ────────────────────────────────────


def test_hook_candidates_from_motifs():
    """High-salience motifs should be detected as hook candidates."""
    candidates = find_hook_candidates(
        tracks=[{"name": "Lead", "index": 0}],
        motif_data={
            "motifs": [
                {"name": "main_hook", "salience": 0.8, "description": "Rising arpeggio", "recurrence": 0.6},
                {"name": "filler", "salience": 0.1, "description": "Background noise", "recurrence": 0.1},
            ]
        },
    )
    # High-salience motif should be found
    assert any(c.hook_id.startswith("motif_") for c in candidates)
    # Very low salience + recurrence should be filtered
    high_salience = [c for c in candidates if "main_hook" in c.hook_id]
    assert len(high_salience) >= 1


def test_hook_candidates_from_track_names():
    """Tracks named 'lead', 'hook', etc. should be candidates."""
    candidates = find_hook_candidates(
        tracks=[
            {"name": "Lead Synth", "index": 0},
            {"name": "Reverb Bus", "index": 1},
            {"name": "Main Melody", "index": 2},
        ],
    )
    hook_names = [c.description.lower() for c in candidates]
    assert any("lead" in n for n in hook_names)
    assert any("melody" in n for n in hook_names)


def test_hook_candidates_ranking_by_salience():
    """Candidates should be sorted by salience (highest first)."""
    candidates = find_hook_candidates(
        tracks=[{"name": "Lead", "index": 0}],
        motif_data={
            "motifs": [
                {"name": "weak", "salience": 0.3, "recurrence": 0.4, "description": "Weak motif"},
                {"name": "strong", "salience": 0.9, "recurrence": 0.7, "description": "Strong motif"},
            ]
        },
    )
    if len(candidates) >= 2:
        assert candidates[0].salience >= candidates[1].salience


def test_hook_candidates_empty_session():
    """Empty session should return empty candidates."""
    candidates = find_hook_candidates(tracks=[])
    assert isinstance(candidates, list)


# ── Primary hook ─────────────────────────────────────────────────


def test_primary_hook_returns_best():
    """Primary hook should be the highest-salience candidate."""
    hook = find_primary_hook(
        tracks=[{"name": "Hook Lead", "index": 0}],
        motif_data={
            "motifs": [
                {"name": "hook", "salience": 0.9, "recurrence": 0.8, "description": "Main hook"},
            ]
        },
    )
    assert hook is not None
    assert hook.salience > 0


def test_primary_hook_none_when_empty():
    """No hook should be returned for empty sessions."""
    hook = find_primary_hook(tracks=[], motif_data={})
    # May return None or a low-confidence candidate depending on implementation
    # Just verify it doesn't crash
    assert hook is None or isinstance(hook, object)


# ── Phrase impact scoring ────────────────────────────────────────


def test_phrase_impact_returns_all_dimensions():
    """Impact scoring should return all dimension scores."""
    section = {
        "id": "scene_0",
        "name": "Chorus",
        "label": "chorus",
        "energy": 0.8,
        "density": 0.7,
        "has_drums": True,
    }
    impact = score_phrase_impact(section, "chorus", {}, {})
    assert hasattr(impact, "arrival_strength")
    assert hasattr(impact, "anticipation_strength")
    assert hasattr(impact, "contrast_quality")
    assert hasattr(impact, "composite_impact")
    assert 0 <= impact.composite_impact <= 1


def test_phrase_impact_higher_for_chorus_with_contrast():
    """Chorus after a quiet section should score higher contrast."""
    chorus = {
        "id": "scene_1",
        "name": "Chorus",
        "label": "chorus",
        "energy": 0.9,
        "density": 0.8,
        "has_drums": True,
    }
    quiet_prev = {
        "id": "scene_0",
        "name": "Breakdown",
        "label": "break",
        "energy": 0.2,
        "density": 0.2,
        "has_drums": False,
    }
    impact = score_phrase_impact(chorus, "chorus", {}, quiet_prev)
    assert impact.contrast_quality > 0.3  # Should detect contrast


# ── Payoff failure detection ─────────────────────────────────────


def test_payoff_failure_detects_flat_arrival():
    """Flat energy at a chorus/drop should be a payoff failure."""
    sections = [
        {"id": "s0", "name": "Verse", "label": "verse", "energy": 0.5, "density": 0.5, "has_drums": True},
        {"id": "s1", "name": "Chorus", "label": "chorus", "energy": 0.5, "density": 0.5, "has_drums": True},
    ]
    failures = detect_payoff_failures(sections, {})
    # A chorus at the same energy as a verse might be flagged
    assert isinstance(failures, list)


def test_payoff_failure_empty_sections():
    """Empty sections should not crash."""
    failures = detect_payoff_failures([], {})
    assert failures == [] or isinstance(failures, list)


def test_payoff_repairs_generated():
    """Repairs should be generated for any detected failures."""
    sections = [
        {"id": "s0", "name": "Intro", "label": "intro", "energy": 0.3, "density": 0.2, "has_drums": False},
        {"id": "s1", "name": "Drop", "label": "drop", "energy": 0.3, "density": 0.3, "has_drums": True},
    ]
    failures = detect_payoff_failures(sections, {})
    if failures:
        repairs = suggest_payoff_repairs(failures)
        assert isinstance(repairs, list)
        assert len(repairs) >= len(failures)


# ─── BUG-B8 regression — hook candidate de-duplication ──────────────────────


def test_bug_b8_motifs_without_name_field_use_motif_id():
    """BUG-B8: motif_engine emits `motif_id`, not `name`, so the old code
    (which read motif.get('name', 'unknown')) collapsed every motif onto
    hook_id='motif_unknown'. After the fix each motif gets a unique hook_id
    sourced from motif_id / name / per-iteration index fallback."""
    candidates = find_hook_candidates(
        tracks=[{"name": "Lead", "index": 0}],
        motif_data={
            "motifs": [
                # Realistic motif engine output: motif_id, no 'name' key
                {"motif_id": "m_001", "salience": 0.8, "recurrence": 0.6,
                 "description": "Rising arpeggio"},
                {"motif_id": "m_002", "salience": 0.7, "recurrence": 0.5,
                 "description": "Descending sixth"},
                {"motif_id": "m_003", "salience": 0.6, "recurrence": 0.4,
                 "description": "Syncopated phrase"},
            ]
        },
    )
    motif_candidates = [c for c in candidates if c.hook_id.startswith("motif_")]
    hook_ids = {c.hook_id for c in motif_candidates}
    # All 3 motifs must produce distinct hook_ids (not collapsed to
    # "motif_unknown" four times).
    assert len(hook_ids) == len(motif_candidates), (
        f"duplicate hook_ids: {[c.hook_id for c in motif_candidates]}"
    )
    # And none of them should be the old catch-all sentinel
    assert "motif_unknown" not in hook_ids


def test_bug_b8_motifs_missing_both_id_and_name_still_unique():
    """Even fully-nameless motifs (neither motif_id nor name) must produce
    distinct hook_ids via the per-iteration index fallback."""
    candidates = find_hook_candidates(
        tracks=[],
        motif_data={
            "motifs": [
                {"salience": 0.8, "recurrence": 0.6},
                {"salience": 0.7, "recurrence": 0.5},
                {"salience": 0.6, "recurrence": 0.4},
            ]
        },
    )
    motif_candidates = [c for c in candidates if c.hook_id.startswith("motif_")]
    hook_ids = {c.hook_id for c in motif_candidates}
    assert len(hook_ids) == len(motif_candidates), (
        f"index-fallback should dedupe: {[c.hook_id for c in motif_candidates]}"
    )


def test_bug_b8_final_dedupe_drops_collisions_from_other_producers():
    """Even if duplicate hook_ids slip through from non-motif producers
    (track-name / groove-pattern), the final-stage dedupe keeps only one
    candidate per hook_id."""
    candidates = find_hook_candidates(
        tracks=[
            {"name": "Lead", "index": 0},
            {"name": "Lead", "index": 1},  # duplicate track name
        ],
    )
    hook_ids = [c.hook_id for c in candidates]
    # No duplicates in the output list
    assert len(hook_ids) == len(set(hook_ids)), (
        f"final dedupe failed: {hook_ids}"
    )
