"""Fast compose mode — LLM-creative two-phase flow for 8-bar loop sketches.

Phase 1: build_fast_brief returns a creative brief (atlas-filtered instruments,
scale pitches, genre guidance). Phase 2 (agent): designs MIDI inline.
Phase 3: apply_fast_plan executes the agent-designed plan.
"""
# Re-export the public API from sub-modules
from .brief_builder import build_creative_brief
from .apply import apply_fast_plan

# Re-export all names that were previously accessible via
# `from mcp_server.composer import fast` on the flat fast.py module.
# This preserves backward compatibility for tests and tools.py.
from .brief_builder import (
    GENRE_CREATIVE_GUIDANCE,
    GENRE_KNOWLEDGE_QUERIES,
    RECOMMENDED_OCTAVES_PER_ROLE,
    _extract_loaded_device_names,
    chord_at_degree,
    degree_to_pitch,
    detect_fresh_project,
    get_creative_guidance,
    get_knowledge_queries_for_role,
    get_role_candidates,
    is_default_track_name,
    is_viable_instrument_uri,
    parse_key,
    pick_anti_defaults,
    pick_by_role_tag,
    pick_creative_seed,
    pick_instrument_uri,
    reference_artist_queries,
    scale_pitches_in_octave,
    simpler_role_for,
    track_is_empty,
)

__all__ = [
    "build_creative_brief",
    "apply_fast_plan",
    "GENRE_CREATIVE_GUIDANCE",
    "GENRE_KNOWLEDGE_QUERIES",
    "RECOMMENDED_OCTAVES_PER_ROLE",
    "_extract_loaded_device_names",
    "chord_at_degree",
    "degree_to_pitch",
    "detect_fresh_project",
    "get_creative_guidance",
    "get_knowledge_queries_for_role",
    "get_role_candidates",
    "is_default_track_name",
    "is_viable_instrument_uri",
    "parse_key",
    "pick_anti_defaults",
    "pick_by_role_tag",
    "pick_creative_seed",
    "pick_instrument_uri",
    "reference_artist_queries",
    "scale_pitches_in_octave",
    "simpler_role_for",
    "track_is_empty",
]
