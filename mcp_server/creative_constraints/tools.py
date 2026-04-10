"""Creative Constraints MCP tools — 3 tools for constrained creativity
and reference distillation.

  apply_creative_constraint_set — activate creative constraints
  distill_reference_principles — learn principles from a reference
  map_reference_principles_to_song — translate reference into current song
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp
from . import engine
from .models import CONSTRAINT_MODES


# Module-level cache for active constraints and distillations
_active_constraints: Optional[engine.ConstraintSet] = None
_cached_distillation: Optional[engine.ReferenceDistillation] = None


@mcp.tool()
def apply_creative_constraint_set(
    ctx: Context,
    constraints: list[str] | None = None,
) -> dict:
    """Apply creative constraints to focus suggestions.

    Constraints modify planning and ranking, not just validation.
    When stuck, try adding constraints instead of more unconstrained advice.

    Available constraints:
    - use_loaded_devices_only — only use what's already loaded
    - no_new_tracks — work within existing tracks
    - subtraction_only — only remove/reduce, no additions
    - arrangement_only — only structural changes
    - mood_shift_without_new_fx — shift mood with existing tools
    - make_it_stranger_but_keep_the_hook — push novelty safely
    - club_translation_safe — keep changes club/DJ-friendly
    - performance_safe_creative — only live-safe changes

    constraints: list of constraint names to activate
    """
    global _active_constraints

    if not constraints:
        return {
            "error": "No constraints provided",
            "available": CONSTRAINT_MODES,
        }

    cs = engine.build_constraint_set(constraints)
    _active_constraints = cs

    invalid = [c for c in constraints if c not in CONSTRAINT_MODES]
    result = {
        "active_constraints": cs.constraints,
        "description": cs.description,
        "reason": cs.reason,
    }
    if invalid:
        result["invalid_constraints"] = invalid
        result["available"] = CONSTRAINT_MODES

    return result


@mcp.tool()
def distill_reference_principles(
    ctx: Context,
    reference_description: str = "",
    style_name: str = "",
) -> dict:
    """Learn musical principles from a reference — not surface traits.

    Extracts: emotional posture, density motion, arrangement patience,
    texture treatment, width strategy, and payoff architecture.

    Never outputs a plan that copies surface traits directly.
    Always translates through the current song's identity.

    reference_description: text description of the reference
    style_name: optional style/genre name for style-based references
    """
    global _cached_distillation

    if not reference_description.strip() and not style_name.strip():
        return {"error": "Provide reference_description or style_name"}

    # Build a reference profile from available data
    reference_profile: dict = {}

    # Try to get style tactics if style_name is provided
    if style_name:
        try:
            from ..tools._research_engine import get_style_tactics
            tactics = get_style_tactics(style_name)
            if tactics:
                reference_profile = {
                    "emotional_stance": tactics.get("emotional_stance", ""),
                    "density_arc": tactics.get("density_arc", []),
                    "section_pacing": tactics.get("section_pacing", []),
                    "width_depth": tactics.get("width_depth", {}),
                    "spectral_contour": tactics.get("spectral_contour", {}),
                    "groove_posture": tactics.get("groove_posture", {}),
                    "harmonic_character": tactics.get("harmonic_character", ""),
                }
        except Exception:
            pass

    # Try to get a reference profile from the reference engine
    if not reference_profile:
        try:
            from ..reference_engine.profile_builder import build_style_reference_profile
            profile = build_style_reference_profile(
                style_name or reference_description
            )
            reference_profile = profile.to_dict()
        except Exception:
            # Fallback: build from description keywords
            reference_profile = _profile_from_description(reference_description)

    distillation = engine.distill_reference_principles(
        reference_profile=reference_profile,
        reference_description=reference_description or style_name,
    )
    _cached_distillation = distillation

    return distillation.to_dict()


@mcp.tool()
def map_reference_principles_to_song(
    ctx: Context,
) -> dict:
    """Map distilled reference principles to the current song.

    Must call distill_reference_principles first. Translates each
    principle through the song's identity, loaded tools, and hook.

    Returns actionable mappings — how to apply each principle
    while preserving the song's own character.
    """
    if _cached_distillation is None:
        return {"error": "No reference distilled yet — call distill_reference_principles first"}

    song_brain = _get_song_brain_dict()

    mappings = engine.map_principles_to_song(song_brain, _cached_distillation)

    return {
        "reference": _cached_distillation.reference_description,
        "mappings": mappings,
        "mapping_count": len(mappings),
        "note": "Principles are adapted to your song — not copied from the reference",
    }


# ── Helpers ───────────────────────────────────────────────────────


def _get_song_brain_dict() -> dict:
    try:
        from ..song_brain.tools import _current_brain
        if _current_brain is not None:
            return _current_brain.to_dict()
    except Exception:
        pass
    return {}


def _profile_from_description(description: str) -> dict:
    """Build a rough reference profile from text description."""
    desc_lower = description.lower()

    emotional_map = {
        "dark": "tense",
        "bright": "euphoric",
        "sad": "melancholic",
        "aggressive": "aggressive",
        "dreamy": "dreamy",
        "chill": "relaxed",
        "intense": "aggressive",
        "minimal": "restrained",
    }

    emotional = ""
    for keyword, stance in emotional_map.items():
        if keyword in desc_lower:
            emotional = stance
            break

    return {
        "emotional_stance": emotional,
        "density_arc": [],
        "section_pacing": [],
        "width_depth": {},
        "spectral_contour": {},
        "groove_posture": {},
        "harmonic_character": "",
    }
