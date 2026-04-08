"""Arrangement graph builder — transforms scenes + clip matrix into ArrangementGraph.

Reuses _composition_engine.build_section_graph_from_scenes for the heavy
inference, then converts composition SectionNodes to brain SectionNodes.

Pure computation, zero I/O.
"""

from __future__ import annotations

from ..tools._composition_engine import (
    build_section_graph_from_scenes as _ce_build_sections,
)
from .models import ArrangementGraph, SectionNode


def build_arrangement_graph(
    scenes: list[dict],
    clip_matrix: list[list[dict]],
    track_count: int,
    beats_per_bar: int = 4,
) -> ArrangementGraph:
    """Build an ArrangementGraph from session-view scenes and clip matrix.

    Args:
        scenes: list of {index, name, tempo, color_index}.
        clip_matrix: [scene_index][track_index] = {state, name, ...} or None.
        track_count: total number of tracks in the session.
        beats_per_bar: beats per bar (default 4).

    Returns:
        ArrangementGraph with sections, boundaries, and freshness (unfreshed).
    """
    graph = ArrangementGraph()

    if not scenes:
        return graph

    # Delegate to composition engine for section inference
    ce_sections = _ce_build_sections(scenes, clip_matrix, track_count, beats_per_bar)

    # Convert composition SectionNodes -> brain SectionNodes
    for ce_sec in ce_sections:
        graph.sections.append(SectionNode(
            section_id=ce_sec.section_id,
            start_bar=ce_sec.start_bar,
            end_bar=ce_sec.end_bar,
            section_type=ce_sec.section_type.value,
            energy=ce_sec.energy,
            density=ce_sec.density,
        ))

    # Build boundary list (transitions between adjacent sections)
    for i in range(len(graph.sections) - 1):
        curr = graph.sections[i]
        nxt = graph.sections[i + 1]
        graph.boundaries.append({
            "from_section": curr.section_id,
            "to_section": nxt.section_id,
            "bar": curr.end_bar,
            "energy_delta": round(nxt.energy - curr.energy, 3),
        })

    return graph
