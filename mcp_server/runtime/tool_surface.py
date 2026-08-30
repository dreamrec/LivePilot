"""Compact, search-first public tool surface for LivePilot.

LivePilot keeps its exact atomic controls internally, but advertising every
control on every MCP ``tools/list`` call wastes context and makes selection
less reliable.  This module keeps a small, task-oriented front door visible
and makes the rest discoverable through FastMCP's search/call proxy.

The profile changes visibility only. Hidden tools remain directly callable
by name, so existing clients and skills do not lose capability.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from fastmcp.server.transforms.search import (
    BM25SearchTransform,
    serialize_tools_for_output_markdown,
)
from fastmcp.tools.base import Tool


# The default front door covers the high-trust production loop:
# inspect -> exact edit -> compare -> keep/undo.  Domain-specific profiles
# add common tools without changing what remains searchable.
CORE_PRODUCER_TOOLS: tuple[str, ...] = (
    "get_session_kernel",
    "get_capability_state",
    "get_session_info",
    "set_tempo",
    "start_playback",
    "stop_playback",
    "undo",
    "redo",
    "get_track_info",
    "get_clip_info",
    "get_device_info",
    "get_device_parameters",
    "set_device_parameter",
    "add_notes",
    "search_browser",
    "load_browser_item",
    "atlas_search",
    "atlas_device_info",
    "list_semantic_moves",
    "preview_semantic_move",
    "apply_semantic_move",
    "create_experiment",
    "run_experiment",
    "commit_experiment",
    "discard_experiment",
    "listen_ab",
)

TOOL_PROFILES: dict[str, tuple[str, ...]] = {
    "producer": CORE_PRODUCER_TOOLS,
    "composition": CORE_PRODUCER_TOOLS
    + (
        "compose",
        "compose_full_apply",
        "plan_arrangement",
        "analyze_composition",
        "get_section_graph",
        "create_clip",
        "create_arrangement_clip",
        "add_arrangement_notes",
    ),
    "mixing": CORE_PRODUCER_TOOLS
    + (
        "get_mix_snapshot",
        "analyze_mix",
        "get_mix_issues",
        "plan_mix_move",
        "set_track_volume",
        "set_track_pan",
        "set_track_send",
        "get_master_meters",
    ),
    "sampling": CORE_PRODUCER_TOOLS
    + (
        "analyze_sample",
        "evaluate_sample_fit",
        "search_samples",
        "plan_sample_workflow",
        "splice_catalog_hunt",
        "splice_preview_sample",
        "splice_download_sample",
    ),
}


# These compatibility/coordination helpers are still directly callable but
# should not be recommended by search. They either duplicate the model's own
# routing or represent a legacy path retained for old clients.
SEARCH_HIDDEN_TOOLS: frozenset[str] = frozenset(
    {
        "route_request",
        "get_turn_budget",
        "get_composition_plan",
    }
)


# Explicit musical vocabulary fixes the weak spots observed with stock BM25.
# This is retrieval guidance only: it never executes or routes a request.
_QUERY_HINTS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (
        re.compile(r"\b(?:tempo|bpm|metronome)\b", re.I),
        ("set_tempo", "tap_tempo", "nudge_tempo", "toggle_metronome"),
    ),
    (
        re.compile(r"\b(?:filter|cutoff|resonance|macro|parameter)\b", re.I),
        (
            "get_device_parameters",
            "set_device_parameter",
            "get_device_presets",
            "atlas_search",
        ),
    ),
    (
        re.compile(r"\b(?:preset|pad|bass|lead|instrument|device|synth|sound)\b", re.I),
        ("atlas_search", "search_browser", "load_browser_item", "analyze_sound_design"),
    ),
    (
        re.compile(r"\b(?:note|notes|melody|chord|harmony|midi)\b", re.I),
        ("get_notes", "add_notes", "analyze_harmony", "harmonize_melody"),
    ),
    (
        re.compile(r"\b(?:louder|quieter|volume|pan|send|mix|masking|headroom)\b", re.I),
        ("analyze_mix", "get_mix_issues", "plan_mix_move", "set_track_volume"),
    ),
    (
        re.compile(r"\b(?:punch|punchier|warm|warmer|bright|brighter|texture)\b", re.I),
        (
            "analyze_sound_design",
            "plan_sound_design_move",
            "apply_semantic_move",
            "analyze_mix",
        ),
    ),
    (
        re.compile(r"\b(?:before|after|compare|comparison|a/?b|audition|render)\b", re.I),
        ("listen_ab", "create_experiment", "run_experiment", "compare_experiments"),
    ),
    (
        re.compile(r"\b(?:undo|redo|revert|restore|discard|keep|commit)\b", re.I),
        ("undo", "redo", "discard_experiment", "commit_experiment"),
    ),
    (
        re.compile(r"\b(?:arrange|arrangement|song|section|drop|breakdown|extend)\b", re.I),
        ("compose", "plan_arrangement", "analyze_loop_for_extension", "develop_apply"),
    ),
    (
        re.compile(r"\b(?:sample|splice|loop|slice|chop)\b", re.I),
        ("search_samples", "analyze_sample", "plan_sample_workflow", "splice_catalog_hunt"),
    ),
    (
        re.compile(r"\b(?:taste|preference|prefer|liked|disliked|learn)\b", re.I),
        (
            "record_positive_preference",
            "record_anti_preference",
            "get_taste_graph",
            "taste_record_pair",
        ),
    ),
)


def profile_tool_names(profile: str) -> tuple[str, ...]:
    """Return pinned tool names for a supported public profile."""
    normalized = profile.strip().lower()
    if normalized not in TOOL_PROFILES:
        supported = ", ".join(sorted((*TOOL_PROFILES, "full")))
        raise ValueError(f"Unknown LivePilot tool profile '{profile}'. Expected: {supported}")
    # Preserve declaration order while removing duplicates from extensions.
    return tuple(dict.fromkeys(TOOL_PROFILES[normalized]))


def _hinted_tool_names(query: str) -> list[str]:
    hinted: list[str] = []
    for pattern, names in _QUERY_HINTS:
        if pattern.search(query):
            hinted.extend(names)
    return list(dict.fromkeys(hinted))


class LivePilotToolSearchTransform(BM25SearchTransform):
    """BM25 discovery with LivePilot vocabulary and weak routers suppressed."""

    async def _search(self, tools: Sequence[Tool], query: str) -> Sequence[Tool]:
        eligible = [tool for tool in tools if tool.name not in SEARCH_HIDDEN_TOOLS]
        hinted_names = _hinted_tool_names(query)

        # Repeating exact tool names gives BM25 a useful lexical bridge while
        # preserving ordinary ranking for requests that need no hint.
        expanded_query = " ".join((query, *hinted_names, *hinted_names))
        ranked = list(await super()._search(eligible, expanded_query))
        by_name = {tool.name: tool for tool in eligible}

        ordered: list[Tool] = []
        for name in hinted_names:
            tool = by_name.get(name)
            if tool is not None and tool not in ordered:
                ordered.append(tool)
        for tool in ranked:
            if tool not in ordered:
                ordered.append(tool)
        return ordered[: self._max_results]


def build_tool_search_transform(profile: str = "producer") -> LivePilotToolSearchTransform:
    """Build the compact public catalog transform for ``profile``."""
    return LivePilotToolSearchTransform(
        max_results=6,
        always_visible=list(profile_tool_names(profile)),
        search_result_serializer=serialize_tools_for_output_markdown,
    )
