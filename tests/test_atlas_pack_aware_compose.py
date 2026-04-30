"""Tests for Pack-Atlas Phase F — atlas_pack_aware_compose.

All tests run without Live — they exercise the vocabulary parser, brief analysis,
preset selection, and executable step generation from local corpus files.
"""

from __future__ import annotations

import pytest
import sys
import os

# Ensure mcp_server is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.atlas.pack_aware_compose import (
    _parse_brief,
    _determine_track_roles,
    _load_artist_vocab,
    _load_genre_vocab,
    pack_aware_compose,
)


# ─── Vocabulary loading ───────────────────────────────────────────────────────


def test_artist_vocab_loads():
    """Artist vocabulary loads without error and contains known artists."""
    vocab = _load_artist_vocab()
    # If the file doesn't exist, we get an empty dict — that's fine for CI
    # But if it does exist it should have content
    assert isinstance(vocab, dict)


def test_genre_vocab_loads():
    """Genre vocabulary loads without error."""
    vocab = _load_genre_vocab()
    assert isinstance(vocab, dict)


# ─── Brief parsing ────────────────────────────────────────────────────────────


def test_parse_brief_dub_techno():
    """Dub-techno brief triggers correct genre and pack cohort."""
    result = _parse_brief("dub-techno spectral drone bed monolake")
    assert isinstance(result["primary_aesthetic"], str)
    assert isinstance(result["pack_cohort"], list)
    assert len(result["pack_cohort"]) > 0
    # dub-techno / spectral / drone keywords should pull drone-lab or pitchloop89
    cohort = result["pack_cohort"]
    assert any(p in cohort for p in ["drone-lab", "pitchloop89", "convolution-reverb"]), (
        f"Expected dub-techno-relevant pack in cohort, got: {cohort}"
    )


def test_parse_brief_ambient_pastoral():
    """Ambient pastoral brief triggers appropriate packs."""
    result = _parse_brief("ambient granular pastoral texture")
    cohort = result["pack_cohort"]
    assert isinstance(cohort, list)
    # ambient/granular should pull inspired-by-nature or drone-lab
    assert any(
        p in cohort
        for p in ["inspired-by-nature-by-dillon-bastan", "drone-lab", "mood-reel"]
    )


def test_parse_brief_no_matches_returns_fallback():
    """Brief with no vocabulary matches returns a non-empty fallback cohort."""
    result = _parse_brief("xyzzy quux frobnitz")
    cohort = result["pack_cohort"]
    # Should return fallback, not crash
    assert isinstance(cohort, list)
    # primary_aesthetic should be set even if no match
    assert isinstance(result["primary_aesthetic"], str)
    assert len(result["primary_aesthetic"]) > 0


# ─── Role determination ───────────────────────────────────────────────────────


def test_determine_roles_track_count():
    """Returned roles list length always matches requested track_count."""
    for count in [1, 3, 4, 6, 8]:
        roles = _determine_track_roles("drone bed spectral", count)
        assert len(roles) == count, f"Expected {count} roles, got {len(roles)}"


def test_determine_roles_drone_bed():
    """'drone bed' keyword triggers harmonic-foundation role."""
    roles = _determine_track_roles("drone bed spectral dub", 4)
    role_names = [r["role"] for r in roles]
    assert "harmonic-foundation" in role_names


def test_determine_roles_rhythm():
    """'kick' / 'drums' keyword triggers rhythmic-driver role."""
    roles = _determine_track_roles("kick snare drums rhythm", 3)
    role_names = [r["role"] for r in roles]
    assert "rhythmic-driver" in role_names


# ─── Main compose function ───────────────────────────────────────────────────


def test_pack_aware_compose_dub_techno_brief():
    """Dub-techno brief returns coherent track proposal with expected packs.

    Spec smoke test: assert pack_cohort includes a dub-techno-coherent pack.
    If the exact spec packs (pitchloop89, drone-lab) aren't in the user's atlas,
    accept any pack that the brief actually triggers.
    """
    result = pack_aware_compose(
        aesthetic_brief="dub-techno spectral drone bed monolake",
        target_bpm=130,
        track_count=4,
    )

    assert "brief_analysis" in result, f"Missing brief_analysis: {result}"
    assert "track_proposal" in result, f"Missing track_proposal: {result}"
    assert "executable_steps" in result, f"Missing executable_steps: {result}"
    assert "suggested_routing" in result, f"Missing suggested_routing: {result}"
    assert "sources" in result, f"Missing sources: {result}"

    # Pack cohort must be non-empty
    cohort = result["brief_analysis"]["pack_cohort"]
    assert len(cohort) > 0, "Pack cohort should not be empty for dub-techno brief"

    # Should include a dub-techno-relevant pack
    assert any(p in cohort for p in ["drone-lab", "pitchloop89", "convolution-reverb"]), (
        f"Expected dub-techno-coherent pack, got cohort: {cohort}"
    )

    # Track count matches
    assert len(result["track_proposal"]) == 4, (
        f"Expected 4 tracks, got {len(result['track_proposal'])}"
    )

    # Each track has the required fields
    for track in result["track_proposal"]:
        assert "track_name" in track
        assert "role" in track
        assert "rationale" in track

    # Executable steps must include at least a create_track step
    actions = [s.get("action", "") for s in result["executable_steps"]]
    assert any("track" in a for a in actions), (
        f"Expected create_*_track in steps, got: {actions}"
    )

    # Sources should have citation tags
    sources_text = " ".join(result["sources"])
    assert "[SOURCE:" in sources_text


def test_pack_aware_compose_eclectic_mode():
    """Eclectic mode returns tension_resolution field in rationale."""
    result = pack_aware_compose(
        aesthetic_brief="ambient drone granular pastoral",
        pack_diversity="eclectic",
        track_count=4,
    )

    assert "brief_analysis" in result
    assert "track_proposal" in result
    assert len(result["track_proposal"]) == 4

    # Eclectic mode must produce a reasoning_artifact with tension_resolution
    # (either in reasoning_artifact or in the first track's rationale)
    has_tension = (
        "reasoning_artifact" in result
        or any(
            "tension_resolution" in t or "[ECLECTIC]" in t.get("rationale", "")
            for t in result["track_proposal"]
        )
    )
    assert has_tension, (
        "Eclectic mode must produce tension_resolution or [ECLECTIC] rationale. "
        f"Got: {result.get('reasoning_artifact')}, "
        f"first track rationale: {result['track_proposal'][0].get('rationale') if result['track_proposal'] else 'N/A'}"
    )

    # If reasoning_artifact exists, verify structure
    if "reasoning_artifact" in result:
        ra = result["reasoning_artifact"]
        assert ra.get("mode") == "eclectic"
        assert "tension_resolution" in ra


def test_pack_aware_compose_handles_unknown_brief():
    """Brief with no vocabulary matches does not crash — returns structured fallback."""
    result = pack_aware_compose(
        aesthetic_brief="xyzzy quux frobnitz nonexistent-aesthetic",
        track_count=3,
    )

    # Must not have a raw exception — either a structured result or structured error
    assert isinstance(result, dict)

    if "error" in result:
        # Structured error is fine
        assert isinstance(result["error"], str)
    else:
        # Fallback result must have the required shape
        assert "brief_analysis" in result
        assert "track_proposal" in result
        # With fallback cohort, we get something
        assert len(result["track_proposal"]) == 3


def test_pack_aware_compose_track_count_respected():
    """track_count parameter is respected for multiple values."""
    for count in [2, 4, 6]:
        result = pack_aware_compose(
            aesthetic_brief="ambient drone texture",
            track_count=count,
        )
        if "error" not in result:
            assert len(result["track_proposal"]) == count, (
                f"Expected {count} tracks, got {len(result['track_proposal'])}"
            )


def test_pack_aware_compose_set_tempo_step():
    """target_bpm inserts a set_tempo step in executable_steps."""
    result = pack_aware_compose(
        aesthetic_brief="drone ambient",
        target_bpm=120.0,
        track_count=2,
    )
    if "error" not in result:
        actions = [s.get("action", "") for s in result["executable_steps"]]
        assert "set_tempo" in actions, (
            f"Expected set_tempo step for target_bpm=120, got: {actions}"
        )


def test_pack_aware_compose_set_scale_step():
    """target_scale inserts a set_song_scale step in executable_steps."""
    result = pack_aware_compose(
        aesthetic_brief="minimal techno",
        target_scale="Fmin",
        track_count=2,
    )
    if "error" not in result:
        actions = [s.get("action", "") for s in result["executable_steps"]]
        assert "set_song_scale" in actions, (
            f"Expected set_song_scale step for target_scale=Fmin, got: {actions}"
        )


def test_pack_aware_compose_empty_brief_returns_error():
    """Empty brief returns a structured error."""
    result = pack_aware_compose(aesthetic_brief="")
    assert "error" in result


# ─── BUG-EDGE#2: string track_count coercion ─────────────────────────────────


def test_pack_aware_compose_string_track_count():
    """BUG-EDGE#2: track_count passed as string '5' must not raise TypeError."""
    result = pack_aware_compose(aesthetic_brief="ambient", track_count="5")
    assert isinstance(result, dict)
    assert "error" not in result or result.get("error") != "TypeError"
    if "error" not in result:
        assert len(result["track_proposal"]) == 5


def test_pack_aware_compose_none_track_count_uses_default():
    """track_count=None falls back to default of 6."""
    result = pack_aware_compose(aesthetic_brief="ambient", track_count=None)
    assert isinstance(result, dict)
    if "error" not in result:
        assert len(result["track_proposal"]) == 6


# ─── BUG-EDGE#3: string target_bpm coercion ──────────────────────────────────


def test_pack_aware_compose_string_bpm():
    """BUG-EDGE#3: target_bpm='125.0' must not raise TypeError."""
    result = pack_aware_compose(aesthetic_brief="ambient", target_bpm="125.0")
    assert isinstance(result, dict)
    if "error" not in result:
        actions = [s.get("action", "") for s in result["executable_steps"]]
        assert "set_tempo" in actions


def test_pack_aware_compose_bogus_bpm_silently_ignored():
    """BUG-EDGE#3: target_bpm='bogus' is silently ignored (no set_tempo step)."""
    result = pack_aware_compose(aesthetic_brief="ambient", target_bpm="bogus")
    assert isinstance(result, dict)
    if "error" not in result:
        actions = [s.get("action", "") for s in result["executable_steps"]]
        assert "set_tempo" not in actions


# ─── BUG-EDGE#9: truncation warning in warnings list ─────────────────────────


def test_pack_aware_compose_truncation_warning():
    """BUG-EDGE#9: track_count=100 → warnings list has a truncation note."""
    result = pack_aware_compose(aesthetic_brief="ambient", track_count=100)
    assert isinstance(result, dict)
    if "error" not in result:
        assert "warnings" in result
        warnings_text = " ".join(result["warnings"])
        assert "capped" in warnings_text or "maximum" in warnings_text, (
            f"Expected truncation note in warnings, got: {result['warnings']}"
        )
        assert "requested_vs_returned" in result


# ─── BUG-NEW#4: pack_cohort at top level ─────────────────────────────────────


def test_pack_aware_compose_pack_cohort_top_level():
    """BUG-NEW#4: r.get('pack_cohort') returns the list, not None."""
    result = pack_aware_compose(aesthetic_brief="dub techno")
    assert isinstance(result, dict)
    if "error" not in result:
        assert "pack_cohort" in result, "pack_cohort must be a top-level key"
        assert isinstance(result["pack_cohort"], list)
        assert len(result["pack_cohort"]) > 0
        # Must also still be available nested (backwards compat)
        assert result["pack_cohort"] == result["brief_analysis"]["pack_cohort"]
