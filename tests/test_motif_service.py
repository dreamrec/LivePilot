"""Tests for shared motif service and SongBrain evidence weighting."""

from mcp_server.services.motif_service import get_motif_data
from mcp_server.song_brain.builder import build_song_brain


# ── Motif service ────────────────────────────────────────────────


def test_empty_notes_returns_empty():
    result = get_motif_data({})
    assert result["motif_count"] == 0
    assert result["tracks_analyzed"] == 0


def test_get_motif_data_returns_structure():
    """Even with no real engine data, the structure is correct."""
    result = get_motif_data({0: [{"pitch": 60, "start_time": 0, "duration": 0.5}]})
    assert "motifs" in result
    assert "motif_count" in result
    assert "tracks_analyzed" in result


# ── SongBrain evidence weighting ─────────────────────────────────


def test_full_evidence_gives_higher_confidence():
    """SongBrain with all data sources should have higher confidence."""
    brain_full = build_song_brain(
        session_info={"tempo": 120, "track_count": 4, "tracks": [
            {"name": "Drums", "index": 0}, {"name": "Bass", "index": 1},
        ]},
        scenes=[{"name": "Verse"}, {"name": "Chorus"}],
        tracks=[{"name": "Drums"}, {"name": "Bass"}],
        motif_data={"motifs": [{"salience": 0.7, "description": "Main riff"}]},
        composition_analysis={"arc_type": "build_release"},
        role_graph={"Drums": {"index": 0, "role": "drums"}},
        recent_moves=[{"intent": "mix", "kept": True}],
    )

    brain_partial = build_song_brain(
        session_info={"tempo": 120, "track_count": 4},
        # No scenes, no motif, no composition, no roles
    )

    assert brain_full.identity_confidence > brain_partial.identity_confidence


def test_evidence_breakdown_present():
    brain = build_song_brain(
        session_info={"tempo": 120, "track_count": 2},
        motif_data={"motifs": [{"salience": 0.6, "description": "test"}]},
    )
    assert "evidence_breakdown" in brain.to_dict()
    eb = brain.evidence_breakdown
    assert "evidence_score" in eb
    assert "sources" in eb
    assert eb["sources"]["motif_data"]["available"] is True


def test_missing_motif_lowers_confidence():
    brain_with = build_song_brain(
        session_info={"tempo": 120, "track_count": 2},
        motif_data={"motifs": [{"salience": 0.8, "name": "Hook"}]},
    )
    brain_without = build_song_brain(
        session_info={"tempo": 120, "track_count": 2},
    )
    # Motif is weight 0.4 — biggest single factor
    assert brain_with.evidence_breakdown["evidence_score"] > brain_without.evidence_breakdown["evidence_score"]
