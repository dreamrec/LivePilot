"""Develop compose mode — extends an existing seed loop into a full track.

Two-phase LLM-creative flow (mirrors fast/full): Phase 1 returns a brief
with seed identity + vocabulary, Phase 2 (agent) designs variants, Phase 3
applies them to the live session.
"""
from .seed_introspector import classify_track, infer_role_from_name, introspect_seed
from .brief_builder import build_develop_brief, extract_artist_refs, detect_research_hooks
from .apply import apply_develop_plan

__all__ = [
    "classify_track",
    "infer_role_from_name",
    "introspect_seed",
    "build_develop_brief",
    "extract_artist_refs",
    "detect_research_hooks",
    "apply_develop_plan",
]
