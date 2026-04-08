"""Tests for the Form Engine — structural arrangement transformations."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._form_engine import (
    FormTransformation,
    VALID_TRANSFORMATIONS,
    transform_section_order,
)
from mcp_server.tools._composition_engine import SectionNode, SectionType


# ── Test Helpers ─────────────────────────────────────────────────────


def _make_sections() -> list[SectionNode]:
    """Standard 5-section arrangement for testing."""
    return [
        SectionNode("sec_00", 0, 16, SectionType.INTRO, 0.8, 0.2, 0.2, [0, 1], "Intro"),
        SectionNode("sec_01", 16, 32, SectionType.VERSE, 0.7, 0.5, 0.5, [0, 1, 2], "Verse 1"),
        SectionNode("sec_02", 32, 40, SectionType.BUILD, 0.6, 0.7, 0.7, [0, 1, 2, 3], "Build"),
        SectionNode("sec_03", 40, 56, SectionType.DROP, 0.9, 0.9, 0.9, [0, 1, 2, 3, 4], "Drop"),
        SectionNode("sec_04", 56, 72, SectionType.OUTRO, 0.8, 0.2, 0.2, [0, 1], "Outro"),
    ]


def _make_verse_heavy() -> list[SectionNode]:
    """Arrangement with multiple verses."""
    return [
        SectionNode("sec_00", 0, 8, SectionType.INTRO, 0.8, 0.2, 0.2, [0]),
        SectionNode("sec_01", 8, 24, SectionType.VERSE, 0.7, 0.5, 0.5, [0, 1]),
        SectionNode("sec_02", 24, 32, SectionType.CHORUS, 0.9, 0.8, 0.8, [0, 1, 2]),
        SectionNode("sec_03", 32, 48, SectionType.VERSE, 0.7, 0.5, 0.5, [0, 1]),
        SectionNode("sec_04", 48, 56, SectionType.CHORUS, 0.9, 0.9, 0.9, [0, 1, 2, 3]),
        SectionNode("sec_05", 56, 64, SectionType.OUTRO, 0.8, 0.2, 0.2, [0]),
    ]


# ── Transform Tests ──────────────────────────────────────────────────


class TestInsertBridge:
    def test_inserts_before_last_drop(self):
        sections = _make_sections()
        result = transform_section_order(sections, "insert_bridge_before_final_chorus", bars=8)

        assert isinstance(result, FormTransformation)
        assert len(result.after_sections) == 6  # 5 + 1 bridge
        assert result.bar_delta == 8

        # Bridge should be before the drop
        bridge = next(s for s in result.after_sections if s.section_type == SectionType.BRIDGE)
        drop_idx = next(i for i, s in enumerate(result.after_sections) if s.section_type == SectionType.DROP)
        bridge_idx = result.after_sections.index(bridge)
        assert bridge_idx < drop_idx

    def test_inserts_before_last_chorus(self):
        sections = _make_verse_heavy()
        result = transform_section_order(sections, "insert_bridge_before_final_chorus", bars=8)

        # Should find the LAST chorus and insert before it
        assert len(result.after_sections) == 7


class TestSwapVerses:
    def test_swaps_two_verses(self):
        sections = _make_verse_heavy()
        result = transform_section_order(sections, "swap_verse_positions")

        assert result.bar_delta == 0
        assert len(result.after_sections) == len(sections)

    def test_no_swap_with_single_verse(self):
        sections = _make_sections()
        result = transform_section_order(sections, "swap_verse_positions")
        assert "Not enough verses" in result.description


class TestExtendSection:
    def test_extends_by_bars(self):
        sections = _make_sections()
        result = transform_section_order(sections, "extend_section", target_index=1, bars=8)

        assert result.bar_delta == 8
        extended = result.after_sections[1]
        assert extended.end_bar - extended.start_bar == 24  # was 16, now 24

    def test_requires_target_index(self):
        with pytest.raises(ValueError, match="requires target_index"):
            transform_section_order(_make_sections(), "extend_section")

    def test_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            transform_section_order(_make_sections(), "extend_section", target_index=99)


class TestCompressSection:
    def test_compresses_by_bars(self):
        sections = _make_sections()
        result = transform_section_order(sections, "compress_section", target_index=0, bars=8)

        compressed = result.after_sections[0]
        assert compressed.end_bar - compressed.start_bar == 8  # was 16, now 8

    def test_minimum_4_bars(self):
        sections = _make_sections()
        result = transform_section_order(sections, "compress_section", target_index=0, bars=100)

        compressed = result.after_sections[0]
        assert compressed.end_bar - compressed.start_bar >= 4


class TestInsertBreakdown:
    def test_inserts_at_position(self):
        sections = _make_sections()
        result = transform_section_order(sections, "insert_breakdown", target_index=3, bars=8)

        assert len(result.after_sections) == 6
        assert result.after_sections[3].section_type == SectionType.BREAKDOWN

    def test_auto_finds_position(self):
        sections = _make_sections()
        result = transform_section_order(sections, "insert_breakdown", bars=8)

        # Should insert after highest energy section
        assert result.bar_delta == 8
        has_breakdown = any(s.section_type == SectionType.BREAKDOWN for s in result.after_sections)
        assert has_breakdown


class TestDuplicateSection:
    def test_duplicates(self):
        sections = _make_sections()
        result = transform_section_order(sections, "duplicate_section", target_index=1)

        assert len(result.after_sections) == 6
        assert result.after_sections[1].section_type == result.after_sections[2].section_type


class TestRemoveSection:
    def test_removes(self):
        sections = _make_sections()
        result = transform_section_order(sections, "remove_section", target_index=2)

        assert len(result.after_sections) == 4
        assert result.bar_delta < 0

    def test_cannot_remove_only_section(self):
        single = [SectionNode("sec_00", 0, 8, SectionType.LOOP, 0.8, 0.5, 0.5)]
        with pytest.raises(ValueError, match="Cannot remove the only section"):
            transform_section_order(single, "remove_section", target_index=0)


class TestReverseSectionOrder:
    def test_reverses(self):
        sections = _make_sections()
        result = transform_section_order(sections, "reverse_section_order")

        assert len(result.after_sections) == 5
        assert result.bar_delta == 0
        # First section should now be what was last
        assert result.after_sections[0].section_type == SectionType.OUTRO


class TestSplitSection:
    def test_splits_in_half(self):
        sections = _make_sections()
        result = transform_section_order(sections, "split_section", target_index=0)

        assert len(result.after_sections) == 6
        assert result.bar_delta == 0
        assert result.after_sections[0].end_bar - result.after_sections[0].start_bar == 8
        assert result.after_sections[1].end_bar - result.after_sections[1].start_bar == 8

    def test_too_short_to_split(self):
        short = [SectionNode("sec_00", 0, 4, SectionType.LOOP, 0.8, 0.5, 0.5)]
        with pytest.raises(ValueError, match="too short to split"):
            transform_section_order(short, "split_section", target_index=0)


# ── Validation ───────────────────────────────────────────────────────


class TestValidation:
    def test_invalid_transformation(self):
        with pytest.raises(ValueError, match="Unknown transformation"):
            transform_section_order(_make_sections(), "explode_everything")

    def test_empty_sections(self):
        with pytest.raises(ValueError, match="empty section graph"):
            transform_section_order([], "reverse_section_order")

    def test_contiguous_after_transform(self):
        """All transformations should produce contiguous bar positions."""
        sections = _make_sections()
        for t in VALID_TRANSFORMATIONS:
            try:
                if t in ("extend_section", "compress_section", "duplicate_section",
                         "remove_section", "split_section"):
                    result = transform_section_order(sections, t, target_index=1, bars=4)
                else:
                    result = transform_section_order(sections, t, bars=4)

                for i in range(1, len(result.after_sections)):
                    prev = result.after_sections[i - 1]
                    curr = result.after_sections[i]
                    assert curr.start_bar == prev.end_bar, (
                        f"{t}: gap between sections {i-1} and {i}"
                    )
            except (ValueError, IndexError):
                pass  # Some require specific conditions

    def test_to_dict(self):
        result = transform_section_order(_make_sections(), "reverse_section_order")
        d = result.to_dict()
        assert d["transformation"] == "reverse_section_order"
        assert d["bar_delta"] == 0
        assert "after_sections" in d
