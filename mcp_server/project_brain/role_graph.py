"""Role graph builder — infers musical function per track per section.

Reuses _composition_engine.build_role_graph and infer_role_for_track
for the heavy inference, then converts composition RoleNodes to brain
RoleNodes and computes an overall confidence summary.

Pure computation, zero I/O.
"""

from __future__ import annotations

from ..tools._composition_engine import (
    SectionNode as CESectionNode,
    SectionType as CESectionType,
    build_role_graph as _ce_build_role_graph,
)
from .models import ConfidenceInfo, RoleGraph, RoleNode


def build_role_graph(
    sections: list[dict],
    track_data: list[dict],
    notes_map: dict[str, dict[int, list[dict]]],
) -> RoleGraph:
    """Build a RoleGraph from brain sections, track data, and note data.

    Args:
        sections: list of brain SectionNode.to_dict() or raw dicts with
            section_id, start_bar, end_bar, section_type, energy, density.
        track_data: [{index, name, devices: [{class_name, ...}]}].
        notes_map: {section_id: {track_index: [notes]}}.

    Returns:
        RoleGraph with role assignments and overall confidence.
    """
    graph = RoleGraph()

    if not sections or not track_data:
        return graph

    # Convert brain section dicts to composition-engine SectionNodes
    ce_sections = []
    for sec in sections:
        # Determine which tracks are active in this section
        # If notes_map has data for this section, those tracks are active
        section_id = sec.get("section_id", sec.get("id", ""))
        active_tracks = []
        section_notes = notes_map.get(section_id, {})
        for t_idx, notes in section_notes.items():
            if notes:
                active_tracks.append(t_idx)

        # Also include all tracks if no notes data (assume all active)
        if not active_tracks and not notes_map:
            active_tracks = [t.get("index", 0) for t in track_data]

        try:
            stype = CESectionType(sec.get("section_type", "unknown"))
        except ValueError:
            stype = CESectionType.UNKNOWN

        ce_sections.append(CESectionNode(
            section_id=section_id,
            start_bar=sec.get("start_bar", 0),
            end_bar=sec.get("end_bar", 0),
            section_type=stype,
            confidence=sec.get("confidence", 0.5),
            energy=sec.get("energy", 0.0),
            density=sec.get("density", 0.0),
            tracks_active=active_tracks,
        ))

    # Delegate to composition engine
    ce_roles = _ce_build_role_graph(ce_sections, track_data, notes_map)

    # Convert composition RoleNodes -> brain RoleNodes
    low_confidence_nodes = []
    confidence_sum = 0.0

    for ce_role in ce_roles:
        brain_role = RoleNode(
            track_index=ce_role.track_index,
            section_id=ce_role.section_id,
            role=ce_role.role.value if hasattr(ce_role.role, "value") else str(ce_role.role),
            confidence=ce_role.confidence,
            foreground=ce_role.foreground,
        )
        graph.add_role(brain_role)
        confidence_sum += ce_role.confidence

        if ce_role.confidence < 0.5:
            low_confidence_nodes.append(
                f"t{ce_role.track_index}@{ce_role.section_id}"
            )

    # Compute overall confidence
    overall = confidence_sum / max(len(ce_roles), 1)
    graph.confidence = ConfidenceInfo(
        overall=round(overall, 3),
        low_confidence_nodes=low_confidence_nodes,
    )

    return graph
