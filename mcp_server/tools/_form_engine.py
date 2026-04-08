"""Form Engine — radical structural transformations for arrangements.

Reorder sections, expand loops, compress verbose arrangements, insert bridges,
and propose new section graphs from transformation commands.

Zero external dependencies beyond stdlib.

Design: spec at docs/specs/2026-04-08-phase2-4-roadmap.md, Round 4 (4.4).
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Optional

from ._composition_engine import SectionNode, SectionType


# ── Transformation Types ─────────────────────────────────────────────

VALID_TRANSFORMATIONS = frozenset({
    "insert_bridge_before_final_chorus",
    "swap_verse_positions",
    "extend_section",
    "compress_section",
    "insert_breakdown",
    "duplicate_section",
    "remove_section",
    "reverse_section_order",
    "split_section",
})


@dataclass
class FormTransformation:
    """A proposed structural transformation with before/after section graphs."""
    transformation: str
    target_section_index: Optional[int]
    before_sections: list[SectionNode]
    after_sections: list[SectionNode]
    description: str
    bar_delta: int  # how many bars added (positive) or removed (negative)

    def to_dict(self) -> dict:
        return {
            "transformation": self.transformation,
            "target_section_index": self.target_section_index,
            "before_section_count": len(self.before_sections),
            "after_section_count": len(self.after_sections),
            "description": self.description,
            "bar_delta": self.bar_delta,
            "after_sections": [s.to_dict() for s in self.after_sections],
        }


# ── Core Transform Functions ─────────────────────────────────────────

def transform_section_order(
    sections: list[SectionNode],
    transformation: str,
    target_index: Optional[int] = None,
    bars: int = 8,
) -> FormTransformation:
    """Apply a structural transformation to the section graph.

    sections: current section graph
    transformation: one of VALID_TRANSFORMATIONS
    target_index: which section to transform (for targeted operations)
    bars: how many bars (for extend/compress/insert)

    Returns: FormTransformation with the proposed new section graph.
    """
    if transformation not in VALID_TRANSFORMATIONS:
        raise ValueError(
            f"Unknown transformation '{transformation}'. "
            f"Valid: {sorted(VALID_TRANSFORMATIONS)}"
        )

    if not sections:
        raise ValueError("Cannot transform empty section graph")

    # Deep copy to avoid mutating originals
    original = sections
    new_sections = deepcopy(sections)

    if transformation == "insert_bridge_before_final_chorus":
        return _insert_bridge_before_final_chorus(original, new_sections, bars)

    elif transformation == "swap_verse_positions":
        return _swap_verse_positions(original, new_sections)

    elif transformation == "extend_section":
        if target_index is None:
            raise ValueError("extend_section requires target_index")
        return _extend_section(original, new_sections, target_index, bars)

    elif transformation == "compress_section":
        if target_index is None:
            raise ValueError("compress_section requires target_index")
        return _compress_section(original, new_sections, target_index, bars)

    elif transformation == "insert_breakdown":
        if target_index is None:
            target_index = _find_best_breakdown_position(new_sections)
        return _insert_breakdown(original, new_sections, target_index, bars)

    elif transformation == "duplicate_section":
        if target_index is None:
            raise ValueError("duplicate_section requires target_index")
        return _duplicate_section(original, new_sections, target_index)

    elif transformation == "remove_section":
        if target_index is None:
            raise ValueError("remove_section requires target_index")
        return _remove_section(original, new_sections, target_index)

    elif transformation == "reverse_section_order":
        return _reverse_section_order(original, new_sections)

    elif transformation == "split_section":
        if target_index is None:
            raise ValueError("split_section requires target_index")
        return _split_section(original, new_sections, target_index)

    # Should not reach here due to validation above
    raise ValueError(f"Unhandled transformation: {transformation}")


def _reindex_sections(sections: list[SectionNode]) -> list[SectionNode]:
    """Re-assign section_ids and adjust bar positions to be contiguous."""
    current_bar = 0
    for i, section in enumerate(sections):
        length = section.end_bar - section.start_bar
        section.section_id = f"sec_{i:02d}"
        section.start_bar = current_bar
        section.end_bar = current_bar + length
        current_bar += length
    return sections


def _total_bars(sections: list[SectionNode]) -> int:
    return sections[-1].end_bar if sections else 0


# ── Individual Transformations ───────────────────────────────────────

def _insert_bridge_before_final_chorus(
    original: list[SectionNode],
    sections: list[SectionNode],
    bridge_bars: int,
) -> FormTransformation:
    """Insert a bridge section before the last chorus/drop."""
    # Find the last chorus or drop
    last_climax_idx = None
    for i in range(len(sections) - 1, -1, -1):
        if sections[i].section_type in (SectionType.CHORUS, SectionType.DROP):
            last_climax_idx = i
            break

    if last_climax_idx is None:
        # No chorus/drop found — insert before the last section
        last_climax_idx = len(sections) - 1

    # Create bridge section
    insert_bar = sections[last_climax_idx].start_bar
    bridge = SectionNode(
        section_id="bridge_new",
        start_bar=insert_bar,
        end_bar=insert_bar + bridge_bars,
        section_type=SectionType.BRIDGE,
        confidence=0.9,
        energy=0.4,
        density=0.3,
        tracks_active=sections[last_climax_idx].tracks_active[:3],  # Sparse
        name="Bridge",
    )

    sections.insert(last_climax_idx, bridge)
    sections = _reindex_sections(sections)

    return FormTransformation(
        transformation="insert_bridge_before_final_chorus",
        target_section_index=last_climax_idx,
        before_sections=original,
        after_sections=sections,
        description=f"Inserted {bridge_bars}-bar bridge before final climax",
        bar_delta=bridge_bars,
    )


def _swap_verse_positions(
    original: list[SectionNode],
    sections: list[SectionNode],
) -> FormTransformation:
    """Swap the first two verse sections for variety."""
    verse_indices = [i for i, s in enumerate(sections) if s.section_type == SectionType.VERSE]

    if len(verse_indices) < 2:
        return FormTransformation(
            transformation="swap_verse_positions",
            target_section_index=None,
            before_sections=original,
            after_sections=sections,
            description="Not enough verses to swap (need at least 2)",
            bar_delta=0,
        )

    i, j = verse_indices[0], verse_indices[1]
    sections[i], sections[j] = sections[j], sections[i]
    sections = _reindex_sections(sections)

    return FormTransformation(
        transformation="swap_verse_positions",
        target_section_index=verse_indices[0],
        before_sections=original,
        after_sections=sections,
        description=f"Swapped verses at positions {i} and {j}",
        bar_delta=0,
    )


def _extend_section(
    original: list[SectionNode],
    sections: list[SectionNode],
    target_index: int,
    bars: int,
) -> FormTransformation:
    if target_index < 0 or target_index >= len(sections):
        raise ValueError(f"target_index {target_index} out of range")

    sections[target_index].end_bar += bars
    sections = _reindex_sections(sections)

    return FormTransformation(
        transformation="extend_section",
        target_section_index=target_index,
        before_sections=original,
        after_sections=sections,
        description=f"Extended section {target_index} by {bars} bars",
        bar_delta=bars,
    )


def _compress_section(
    original: list[SectionNode],
    sections: list[SectionNode],
    target_index: int,
    bars: int,
) -> FormTransformation:
    if target_index < 0 or target_index >= len(sections):
        raise ValueError(f"target_index {target_index} out of range")

    current_length = sections[target_index].end_bar - sections[target_index].start_bar
    new_length = max(4, current_length - bars)  # Minimum 4 bars
    actual_reduction = current_length - new_length
    sections[target_index].end_bar = sections[target_index].start_bar + new_length
    sections = _reindex_sections(sections)

    return FormTransformation(
        transformation="compress_section",
        target_section_index=target_index,
        before_sections=original,
        after_sections=sections,
        description=f"Compressed section {target_index} by {actual_reduction} bars",
        bar_delta=-actual_reduction,
    )


def _find_best_breakdown_position(sections: list[SectionNode]) -> int:
    """Find the best position for a breakdown — after the highest energy section."""
    if not sections:
        return 0
    max_energy_idx = max(range(len(sections)), key=lambda i: sections[i].energy)
    return min(max_energy_idx + 1, len(sections))


def _insert_breakdown(
    original: list[SectionNode],
    sections: list[SectionNode],
    position: int,
    bars: int,
) -> FormTransformation:
    position = min(position, len(sections))
    insert_bar = sections[position].start_bar if position < len(sections) else _total_bars(sections)

    # Breakdown inherits tracks from surrounding section but reduces
    ref_tracks = sections[min(position, len(sections) - 1)].tracks_active
    breakdown = SectionNode(
        section_id="bd_new",
        start_bar=insert_bar,
        end_bar=insert_bar + bars,
        section_type=SectionType.BREAKDOWN,
        confidence=0.9,
        energy=0.25,
        density=0.2,
        tracks_active=ref_tracks[:2],  # Very sparse
        name="Breakdown",
    )

    sections.insert(position, breakdown)
    sections = _reindex_sections(sections)

    return FormTransformation(
        transformation="insert_breakdown",
        target_section_index=position,
        before_sections=original,
        after_sections=sections,
        description=f"Inserted {bars}-bar breakdown at position {position}",
        bar_delta=bars,
    )


def _duplicate_section(
    original: list[SectionNode],
    sections: list[SectionNode],
    target_index: int,
) -> FormTransformation:
    if target_index < 0 or target_index >= len(sections):
        raise ValueError(f"target_index {target_index} out of range")

    source = sections[target_index]
    length = source.end_bar - source.start_bar
    duplicate = deepcopy(source)
    duplicate.name = f"{source.name} (repeat)" if source.name else ""

    sections.insert(target_index + 1, duplicate)
    sections = _reindex_sections(sections)

    return FormTransformation(
        transformation="duplicate_section",
        target_section_index=target_index,
        before_sections=original,
        after_sections=sections,
        description=f"Duplicated section {target_index} ({length} bars)",
        bar_delta=length,
    )


def _remove_section(
    original: list[SectionNode],
    sections: list[SectionNode],
    target_index: int,
) -> FormTransformation:
    if target_index < 0 or target_index >= len(sections):
        raise ValueError(f"target_index {target_index} out of range")
    if len(sections) <= 1:
        raise ValueError("Cannot remove the only section")

    removed = sections.pop(target_index)
    removed_bars = removed.end_bar - removed.start_bar
    sections = _reindex_sections(sections)

    return FormTransformation(
        transformation="remove_section",
        target_section_index=target_index,
        before_sections=original,
        after_sections=sections,
        description=f"Removed section {target_index} ({removed_bars} bars)",
        bar_delta=-removed_bars,
    )


def _reverse_section_order(
    original: list[SectionNode],
    sections: list[SectionNode],
) -> FormTransformation:
    sections.reverse()
    sections = _reindex_sections(sections)

    return FormTransformation(
        transformation="reverse_section_order",
        target_section_index=None,
        before_sections=original,
        after_sections=sections,
        description=f"Reversed order of {len(sections)} sections",
        bar_delta=0,
    )


def _split_section(
    original: list[SectionNode],
    sections: list[SectionNode],
    target_index: int,
) -> FormTransformation:
    if target_index < 0 or target_index >= len(sections):
        raise ValueError(f"target_index {target_index} out of range")

    source = sections[target_index]
    length = source.end_bar - source.start_bar
    if length < 8:
        raise ValueError(f"Section too short to split ({length} bars, minimum 8)")

    midpoint = source.start_bar + length // 2

    # First half keeps original type
    first_half = deepcopy(source)
    first_half.end_bar = midpoint

    # Second half
    second_half = deepcopy(source)
    second_half.start_bar = midpoint
    second_half.name = f"{source.name} B" if source.name else ""

    sections[target_index] = first_half
    sections.insert(target_index + 1, second_half)
    sections = _reindex_sections(sections)

    return FormTransformation(
        transformation="split_section",
        target_section_index=target_index,
        before_sections=original,
        after_sections=sections,
        description=f"Split section {target_index} into two {length // 2}-bar halves",
        bar_delta=0,
    )
