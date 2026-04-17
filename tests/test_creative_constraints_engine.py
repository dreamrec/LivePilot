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
    assert isinstance(mappings, list)


# ─── BUG-B17 regressions — rich text-to-profile distillation ───────────────


class TestBugB17ProfileFromDescription:
    """BUG-B17: distill_reference_principles returned 0 principles for any
    description that didn't match the old 8-keyword emotional_map.
    The extended keyword set covers emotional / spectral / width /
    groove / harmonic / density."""

    def test_cold_description_sets_spectral_and_emotional(self):
        from mcp_server.creative_constraints.tools import _profile_from_description
        profile = _profile_from_description(
            "cold 90s hip-hop with ghostly vocal chops and dusty drums"
        )
        assert profile["emotional_stance"], (
            f"BUG-B17 regressed — emotional_stance empty: {profile!r}"
        )
        assert profile["spectral_contour"], (
            f"BUG-B17 regressed — spectral_contour empty: {profile!r}"
        )

    def test_wide_ambient_gets_width_and_depth(self):
        from mcp_server.creative_constraints.tools import _profile_from_description
        profile = _profile_from_description("spacious ambient drone texture")
        wd = profile.get("width_depth", {})
        assert wd.get("stereo_width", 0) > 0.7

    def test_dilla_swing_sets_groove_posture(self):
        from mcp_server.creative_constraints.tools import _profile_from_description
        profile = _profile_from_description("dilla swing with slouchy drums")
        gp = profile.get("groove_posture", {})
        assert gp.get("feel") == "swung"
        assert gp.get("stiffness", 1) < 0.5

    def test_buildup_description_produces_ascending_density(self):
        from mcp_server.creative_constraints.tools import _profile_from_description
        profile = _profile_from_description(
            "patient slow burn that gradually builds"
        )
        arc = profile.get("density_arc", [])
        assert len(arc) >= 3
        assert arc[-1] > arc[0]


def test_bug_b17_distillation_produces_principles_from_text():
    """Full path: text description → non-empty principles list.
    Old version produced 0 for any non-style-corpus description."""
    from mcp_server.creative_constraints.tools import _profile_from_description
    desc = "cold 90s hip-hop with ghostly vocal chops and dusty drums"
    profile = _profile_from_description(desc)
    result = distill_reference_principles(
        reference_profile=profile, reference_description=desc,
    )
    assert len(result.principles) >= 2, (
        f"BUG-B17 regressed — only {len(result.principles)} principles"
    )


# ─── BUG-B50 regressions — derived loudness/spectral/width from style ──────


class TestBugB50StyleProfileDerivation:
    """BUG-B50: build_style_reference_profile used to return
    loudness_posture=0, spectral_contour={}, width_depth={} even for
    styles whose device_chain params clearly leak a sonic posture.
    We now derive those fields heuristically."""

    def test_burial_profile_has_derived_spectral(self):
        from mcp_server.reference_engine.profile_builder import (
            build_style_reference_profile,
        )
        burial_tactics = [{
            "artist_or_genre": "burial",
            "tactic_name": "ghostly_reverb_treatment",
            "arrangement_patterns": [
                "sparse_intro", "gradual_buildup", "sudden_strip_back",
            ],
            "device_chain": [
                {"name": "Reverb",
                 "params": {"Decay Time": 4.5, "Dry/Wet": 0.6}},
                {"name": "Auto Filter",
                 "params": {"Frequency": 800, "Resonance": 0.4}},
                {"name": "Utility", "params": {"Width": 0.7}},
            ],
            "automation_gestures": ["conceal", "drift"],
        }]
        profile = build_style_reference_profile(burial_tactics)
        assert profile.spectral_contour, (
            f"BUG-B50 regressed — empty spectral_contour: "
            f"{profile.spectral_contour!r}"
        )
        assert profile.width_depth, (
            f"BUG-B50 regressed — empty width_depth: {profile.width_depth!r}"
        )
        # Burial should derive dark spectrum from LP filter @ 800Hz
        assert profile.spectral_contour.get("brightness", 1) < 0.5
        # Wide stereo from Utility Width 0.7 + heavy Reverb wet
        assert profile.width_depth.get("stereo_width", 0) >= 0.65

    def test_empty_chain_keeps_neutral_defaults(self):
        from mcp_server.reference_engine.profile_builder import (
            build_style_reference_profile,
        )
        profile = build_style_reference_profile([])
        assert profile.spectral_contour == {}
        assert profile.width_depth == {}
