"""Creative Constraints MCP tools — 5 tools for constrained creativity
and reference distillation.

  apply_creative_constraint_set — activate creative constraints
  distill_reference_principles — learn principles from a reference
  map_reference_principles_to_song — translate reference into current song
  generate_constrained_variants — generate triptych variants under constraints
  generate_reference_inspired_variants — variants from reference principles
"""

from __future__ import annotations

from typing import Optional

from fastmcp import Context

from ..server import mcp
from . import engine
from .models import CONSTRAINT_MODES
import logging

logger = logging.getLogger(__name__)

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
        except Exception as exc:
            logger.debug("distill_reference_principles failed: %s", exc)
    # Try to get a reference profile from the reference engine
    if not reference_profile:
        try:
            from ..reference_engine.profile_builder import build_style_reference_profile
            profile = build_style_reference_profile(
                style_name or reference_description
            )
            reference_profile = profile.to_dict()
        except Exception as exc:
            logger.debug("distill_reference_principles failed: %s", exc)
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


@mcp.tool()
def generate_constrained_variants(
    ctx: Context,
    request_text: str,
    constraints: list[str] | None = None,
    kernel_id: str = "",
) -> dict:
    """Generate creative variants under active constraints.

    Combines constraint filtering with the Preview Studio's triptych.
    Each variant respects the constraint set — e.g., "subtraction_only"
    means no variant adds new elements.

    request_text: what the user wants
    constraints: list of constraint names to apply (or uses currently active)
    kernel_id: optional session kernel reference
    """
    if not request_text.strip():
        return {"error": "request_text cannot be empty"}

    # Apply constraints
    active = _active_constraints
    if constraints:
        active = engine.build_constraint_set(constraints)

    if not active or not active.constraints:
        return {
            "error": "No constraints active — call apply_creative_constraint_set first or provide constraints",
            "available": CONSTRAINT_MODES,
        }

    # Generate variants via preview studio
    try:
        from ..preview_studio import engine as ps_engine
        song_brain = _get_song_brain_dict()
        taste_graph = {}
        try:
            from ..memory.taste_graph import build_taste_graph
            from ..memory.taste_memory import TasteMemoryStore
            from ..memory.anti_memory import AntiMemoryStore
            taste_store = ctx.lifespan_context.setdefault("taste_memory", TasteMemoryStore())
            anti_store = ctx.lifespan_context.setdefault("anti_memory", AntiMemoryStore())
            taste_graph = build_taste_graph(taste_store=taste_store, anti_store=anti_store).to_dict()
        except Exception as exc:
            logger.debug("generate_constrained_variants failed: %s", exc)
        ps = ps_engine.create_preview_set(
            request_text=f"[Constrained: {', '.join(active.constraints)}] {request_text}",
            kernel_id=kernel_id,
            strategy="creative_triptych",
            song_brain=song_brain,
            taste_graph=taste_graph,
        )

        # Validate each variant's compiled_plan against constraints.
        # BUG-B46: two problems in the old code —
        #   1) iterating `for step in v.compiled_plan` yields dict KEYS
        #      (compiled_plan is {'move_id': ..., 'steps': [...]}), so
        #      the validation ran on strings and silently passed.
        #   2) when a variant was filtered, we only blanked compiled_plan
        #      and left status='pending' — callers had no way to tell
        #      which variants became shells.
        # Now we iterate .get("steps", []) correctly, flip filtered
        # variants to status='blocked', and count blocked_count in the
        # response so callers can detect the "all variants filtered" case.
        blocked_count = 0
        for v in ps.variants:
            v.what_preserved = (
                f"{v.what_preserved} | Constraints: "
                f"{', '.join(active.constraints)}"
            )
            if v.compiled_plan:
                steps = v.compiled_plan.get("steps", []) if isinstance(
                    v.compiled_plan, dict
                ) else []
                plan = {
                    "steps": [
                        {"action": step.get("tool", ""), **step}
                        for step in steps
                    ]
                }
                validation = engine.validate_plan_against_constraints(
                    plan, active,
                )
                if not validation["valid"]:
                    v.compiled_plan = None
                    v.status = "blocked"
                    v.what_changed = (
                        f"[FILTERED] {v.what_changed} — violates "
                        f"{', '.join(active.constraints)}"
                    )
                    blocked_count += 1
            elif v.status == "blocked":
                # Already blocked upstream (no compilable move)
                blocked_count += 1

        note = (
            f"Variants with violating plans have been filtered "
            f"({blocked_count}/{len(ps.variants)} blocked)"
        )
        if blocked_count == len(ps.variants) and ps.variants:
            note = (
                f"All {blocked_count} variants violate constraints "
                f"{active.constraints!r}. Try loosening constraints or a "
                f"different request."
            )

        return {
            "preview_set": ps.to_dict(),
            "constraints_applied": active.constraints,
            "blocked_count": blocked_count,
            "executable_count": len(ps.variants) - blocked_count,
            "note": note,
        }
    except Exception as e:
        return {"error": f"Failed to generate constrained variants: {e}"}


@mcp.tool()
def generate_reference_inspired_variants(
    ctx: Context,
    request_text: str = "",
    kernel_id: str = "",
) -> dict:
    """Generate creative variants inspired by a distilled reference.

    Requires a prior call to distill_reference_principles.
    Uses the distilled principles (not surface traits) to shape
    each variant through the current song's identity.

    request_text: optional extra context for what the user wants
    kernel_id: optional session kernel reference
    """
    if _cached_distillation is None:
        return {"error": "No reference distilled yet — call distill_reference_principles first"}

    # BUG-B54: the reference-engine chain (distill → map → generate_variants)
    # used to silently degrade when distill_reference_principles returned
    # empty principles (BUG-B17). Callers got 3 shell variants branded
    # "reference-inspired" with no reference material driving them.
    # Refuse to run when principles are empty — the user should fix the
    # distillation step first.
    principles_list = list(_cached_distillation.principles or [])
    if not principles_list:
        return {
            "error": (
                "distill_reference_principles returned no principles — "
                "reference-inspired variant generation refuses to run on "
                "empty input (would produce meaningless 'reference-inspired' "
                "shell variants). Try a more specific reference description "
                "or pick a reference covered by the built-in style corpus."
            ),
            "reference": _cached_distillation.reference_description,
            "principles_applied": [],
        }

    # Build request text from reference principles
    principles_text = ", ".join(
        p.principle for p in principles_list[:3]
    )
    full_request = (
        f"Inspired by: {_cached_distillation.reference_description}. "
        f"Key principles: {principles_text}. "
        f"{request_text}"
    ).strip()

    # Generate variants via preview studio
    try:
        from ..preview_studio import engine as ps_engine
        song_brain = _get_song_brain_dict()

        ps = ps_engine.create_preview_set(
            request_text=full_request,
            kernel_id=kernel_id,
            strategy="creative_triptych",
            song_brain=song_brain,
        )

        # Annotate variants with reference info
        for v in ps.variants:
            v.why_it_matters = (
                f"Reference-inspired: {_cached_distillation.reference_description}. "
                f"{v.why_it_matters}"
            )

        return {
            "preview_set": ps.to_dict(),
            "reference": _cached_distillation.reference_description,
            "principles_applied": [
                p.to_dict() for p in principles_list[:5]
            ],
            "note": "Variants are shaped by reference principles, not surface imitation",
        }
    except Exception as e:
        return {"error": f"Failed to generate reference-inspired variants: {e}"}

# ── Helpers ───────────────────────────────────────────────────────


def _get_song_brain_dict() -> dict:
    try:
        from ..song_brain.tools import _current_brain
        if _current_brain is not None:
            return _current_brain.to_dict()
    except Exception as _e:
        if __debug__:
            import sys

            print(f"LivePilot: SongBrain unavailable in creative_constraints: {_e}", file=sys.stderr)
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
