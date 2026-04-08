"""Scoped refresh operations — update specific subgraphs without full rebuild.

Pure computation, zero I/O.
"""

from __future__ import annotations

import copy
from typing import Optional

from .arrangement_graph import build_arrangement_graph
from .models import ProjectState
from .session_graph import build_session_graph


def refresh_tracks(
    state: ProjectState,
    track_indices: list[int],
    session_info: dict,
) -> ProjectState:
    """Refresh specific tracks in the session graph without full rebuild.

    Args:
        state: current ProjectState (not mutated — a new copy is returned).
        track_indices: which track indices to refresh.
        session_info: fresh get_session_info output.

    Returns:
        New ProjectState with updated session graph and bumped revision.
    """
    new_state = copy.copy(state)
    new_state.revision = state.revision + 1

    # Rebuild session graph fully (it's cheap) then mark fresh
    new_state.session_graph = build_session_graph(session_info)
    new_state.session_graph.freshness.mark_fresh(new_state.revision)

    # Mark role and automation graphs stale since tracks changed
    new_state.role_graph = copy.copy(state.role_graph)
    new_state.role_graph.freshness.mark_stale(
        f"tracks refreshed: {track_indices}"
    )
    new_state.automation_graph = copy.copy(state.automation_graph)
    new_state.automation_graph.freshness.mark_stale(
        f"tracks refreshed: {track_indices}"
    )

    return new_state


def refresh_arrangement(
    state: ProjectState,
    scenes: list[dict],
    clip_matrix: list[list[dict]],
    track_count: int,
) -> ProjectState:
    """Refresh the arrangement graph without full rebuild.

    Args:
        state: current ProjectState (not mutated — a new copy is returned).
        scenes: fresh scene list.
        clip_matrix: fresh clip matrix.
        track_count: total track count.

    Returns:
        New ProjectState with updated arrangement graph and bumped revision.
    """
    new_state = copy.copy(state)
    new_state.revision = state.revision + 1

    new_state.arrangement_graph = build_arrangement_graph(
        scenes, clip_matrix, track_count,
    )
    new_state.arrangement_graph.freshness.mark_fresh(new_state.revision)

    # Mark role graph stale since arrangement changed
    new_state.role_graph = copy.copy(state.role_graph)
    new_state.role_graph.freshness.mark_stale("arrangement refreshed")

    return new_state
