"""Tests for the Planner Engine — loop-to-song arrangement planning."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._planner_engine import (
    ArrangementPlan,
    LoopIdentity,
    SectionPlan,
    STYLE_TEMPLATES,
    VALID_STYLES,
    analyze_loop_identity,
    plan_arrangement_from_loop,
)
from mcp_server.tools._composition_engine import (
    RoleNode,
    RoleType,
    SectionNode,
    SectionType,
)


# ── Test Helpers ─────────────────────────────────────────────────────


def _make_section(
    section_id: str = "sec_00",
    start_bar: int = 0,
    end_bar: int = 8,
    energy: float = 0.5,
    density: float = 0.5,
    tracks_active: list[int] = None,
) -> SectionNode:
    return SectionNode(
        section_id=section_id,
        start_bar=start_bar,
        end_bar=end_bar,
        section_type=SectionType.LOOP,
        confidence=0.8,
        energy=energy,
        density=density,
        tracks_active=tracks_active or [0, 1, 2, 3],
    )


def _make_roles(section_id: str = "sec_00") -> list[RoleNode]:
    return [
        RoleNode(0, "Kick", section_id, RoleType.KICK_ANCHOR, 0.9, True),
        RoleNode(1, "Bass", section_id, RoleType.BASS_ANCHOR, 0.85, False),
        RoleNode(2, "Lead", section_id, RoleType.LEAD, 0.8, True),
        RoleNode(3, "Pad", section_id, RoleType.HARMONY_BED, 0.75, False),
        RoleNode(4, "HiHat", section_id, RoleType.RHYTHMIC_TEXTURE, 0.8, False),
        RoleNode(5, "FX", section_id, RoleType.TEXTURE_WASH, 0.6, False),
    ]


def _make_loop_identity() -> LoopIdentity:
    return LoopIdentity(
        track_count=6,
        foreground_tracks=[2],
        rhythm_tracks=[0, 4],
        harmonic_tracks=[1, 3],
        texture_tracks=[5],
        energy=0.6,
        density=0.5,
        estimated_bars=8,
    )


# ── Loop Identity Analysis ──────────────────────────────────────────


class TestAnalyzeLoopIdentity:
    def test_classifies_track_roles(self):
        section = _make_section(tracks_active=[0, 1, 2, 3, 4, 5])
        roles = _make_roles()
        identity = analyze_loop_identity(roles, [section])

        assert identity.track_count == 6
        assert 0 in identity.rhythm_tracks  # kick
        assert 1 in identity.harmonic_tracks  # bass
        assert 2 in identity.foreground_tracks  # lead
        assert 3 in identity.harmonic_tracks  # pad

    def test_empty_sections(self):
        identity = analyze_loop_identity([], [])
        assert identity.track_count == 0
        assert identity.foreground_tracks == []

    def test_single_track(self):
        section = _make_section(tracks_active=[0])
        roles = [RoleNode(0, "Kick", "sec_00", RoleType.KICK_ANCHOR, 0.9, True)]
        identity = analyze_loop_identity(roles, [section])
        assert identity.track_count == 1
        assert identity.rhythm_tracks == [0]


# ── Arrangement Planning ─────────────────────────────────────────────


class TestPlanArrangement:
    def test_basic_electronic_plan(self):
        loop = _make_loop_identity()
        plan = plan_arrangement_from_loop(loop, target_duration_bars=128, style="electronic")

        assert isinstance(plan, ArrangementPlan)
        assert plan.style == "electronic"
        assert len(plan.sections) > 0
        assert plan.total_bars > 0

    def test_all_styles_valid(self):
        loop = _make_loop_identity()
        for style in VALID_STYLES:
            plan = plan_arrangement_from_loop(loop, target_duration_bars=64, style=style)
            assert plan.style == style
            assert len(plan.sections) > 0

    def test_invalid_style_raises(self):
        loop = _make_loop_identity()
        with pytest.raises(ValueError, match="Unknown style"):
            plan_arrangement_from_loop(loop, style="jazz_fusion_prog")

    def test_sections_are_contiguous(self):
        loop = _make_loop_identity()
        plan = plan_arrangement_from_loop(loop, target_duration_bars=128)

        for i in range(1, len(plan.sections)):
            prev = plan.sections[i - 1]
            curr = plan.sections[i]
            assert curr.start_bar == prev.end_bar, (
                f"Gap between section {i-1} (end {prev.end_bar}) and {i} (start {curr.start_bar})"
            )

    def test_sections_have_bar_multiples_of_4(self):
        loop = _make_loop_identity()
        plan = plan_arrangement_from_loop(loop, target_duration_bars=128)

        for section in plan.sections:
            length = section.length_bars()
            assert length % 4 == 0, f"Section {section.section_type.value} has {length} bars (not multiple of 4)"

    def test_reveal_order_exists(self):
        loop = _make_loop_identity()
        plan = plan_arrangement_from_loop(loop, target_duration_bars=128)

        assert len(plan.reveal_order) > 0
        # Every track from the loop should appear in reveal order
        all_loop_tracks = set(
            loop.rhythm_tracks + loop.harmonic_tracks
            + loop.foreground_tracks + loop.texture_tracks
        )
        revealed_tracks = {r["track_index"] for r in plan.reveal_order}
        assert all_loop_tracks == revealed_tracks

    def test_gesture_plan_at_transitions(self):
        loop = _make_loop_identity()
        plan = plan_arrangement_from_loop(loop, target_duration_bars=128)

        # Should have gesture suggestions for transitions
        assert len(plan.gesture_plan) == len(plan.sections) - 1
        for g in plan.gesture_plan:
            assert "transition" in g
            assert "templates" in g
            assert "boundary_bar" in g

    def test_breakdown_strips_elements(self):
        loop = _make_loop_identity()
        plan = plan_arrangement_from_loop(loop, target_duration_bars=128, style="electronic")

        breakdowns = [s for s in plan.sections if s.section_type == SectionType.BREAKDOWN]
        if breakdowns:
            bd = breakdowns[0]
            # Breakdown should have fewer active tracks than the preceding section
            bd_idx = plan.sections.index(bd)
            if bd_idx > 0:
                prev_section = plan.sections[bd_idx - 1]
                assert len(bd.tracks_active) <= len(prev_section.tracks_active)

    def test_scaling_to_target_duration(self):
        loop = _make_loop_identity()
        short = plan_arrangement_from_loop(loop, target_duration_bars=64)
        long = plan_arrangement_from_loop(loop, target_duration_bars=256)

        assert long.total_bars > short.total_bars

    def test_notes_for_missing_elements(self):
        empty_loop = LoopIdentity(
            track_count=1,
            foreground_tracks=[],
            rhythm_tracks=[],
            harmonic_tracks=[0],
            texture_tracks=[],
            energy=0.3,
            density=0.2,
            estimated_bars=8,
        )
        plan = plan_arrangement_from_loop(empty_loop, target_duration_bars=64)
        # Should note missing foreground and rhythm
        assert any("foreground" in n.lower() for n in plan.notes)
        assert any("rhythm" in n.lower() for n in plan.notes)


# ── Section Plan ─────────────────────────────────────────────────────


class TestSectionPlan:
    def test_to_dict(self):
        sp = SectionPlan(
            section_type=SectionType.DROP,
            start_bar=32,
            end_bar=48,
            energy_target=0.9,
            density_target=0.9,
            tracks_active=[0, 1, 2],
            tracks_entering=[2],
            tracks_exiting=[],
        )
        d = sp.to_dict()
        assert d["section_type"] == "drop"
        assert d["length_bars"] == 16
        assert d["start_bar"] == 32

    def test_length_bars(self):
        sp = SectionPlan(
            section_type=SectionType.INTRO,
            start_bar=0, end_bar=16,
            energy_target=0.2, density_target=0.2,
            tracks_active=[], tracks_entering=[], tracks_exiting=[],
        )
        assert sp.length_bars() == 16


# ── ArrangementPlan ──────────────────────────────────────────────────


class TestArrangementPlan:
    def test_to_dict(self):
        plan = ArrangementPlan(
            style="electronic",
            total_bars=128,
            sections=[],
            gesture_plan=[],
            reveal_order=[],
            notes=["test note"],
        )
        d = plan.to_dict()
        assert d["style"] == "electronic"
        assert d["total_bars"] == 128
        assert d["section_count"] == 0
        assert d["notes"] == ["test note"]


# ── Style Templates ──────────────────────────────────────────────────


class TestStyleTemplates:
    def test_all_templates_have_intro_and_outro(self):
        for style, template in STYLE_TEMPLATES.items():
            types = [t[0] for t in template]
            assert types[0] == SectionType.INTRO, f"{style} doesn't start with INTRO"
            assert types[-1] == SectionType.OUTRO, f"{style} doesn't end with OUTRO"

    def test_all_templates_have_energy_arc(self):
        for style, template in STYLE_TEMPLATES.items():
            energies = [t[1] for t in template]
            energy_range = max(energies) - min(energies)
            assert energy_range >= 0.4, f"{style} has flat energy arc ({energy_range:.2f})"

    def test_valid_styles_matches_templates(self):
        assert VALID_STYLES == frozenset(STYLE_TEMPLATES.keys())
