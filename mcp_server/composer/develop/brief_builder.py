"""Develop-mode brief builder — Phase 1 of the LLM-creative two-phase flow.

Takes a SeedState (from seed_introspector) and an optional prompt directive,
returns a brief carrying VOCABULARY for the agent to design variants from.

CRITICAL: The brief MUST NOT contain predetermined section sequences, bar
counts, or fixed variant taxonomies. The agent decides those per call.
The framework only provides:
- The existing seed (read-only context)
- Genre/artist character vocabulary (descriptive)
- The 42-event structural lexicon (named primitives, not a sequence)
- Atlas instrument alternates (for sample-trigger swaps)
- Research hooks (WebSearch directives for niche styles)
- An open-ended design_targets text describing the variation surface
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional


# ── artist vocabulary loader ────────────────────────────────────────

# Cached after first load; ARTIST_NAMES is a tuple of producer names parsed from
# artist-vocabularies.md (matches the file's ### heading lines).
_ARTIST_NAMES_CACHE: Optional[tuple[str, ...]] = None


def _load_artist_names() -> tuple[str, ...]:
    """Parse artist-vocabularies.md for known producer names (cached).

    Artist entries use ### headings (h3). Section groupings use ## (h2).
    We parse ### lines only.
    """
    global _ARTIST_NAMES_CACHE
    if _ARTIST_NAMES_CACHE is not None:
        return _ARTIST_NAMES_CACHE

    # Locate the markdown file relative to repo root
    here = Path(__file__).resolve()
    # Walk up to find livepilot/skills/livepilot-core/references/artist-vocabularies.md
    for parent in here.parents:
        candidate = (
            parent
            / "livepilot"
            / "skills"
            / "livepilot-core"
            / "references"
            / "artist-vocabularies.md"
        )
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8")
            names = []
            for line in text.splitlines():
                # Artist entries are ### headings, e.g. "### Burial"
                # or "### Aphex Twin (Richard D. James)"
                m = re.match(r"^###\s+(.+?)\s*$", line)
                if m:
                    raw = m.group(1).strip()
                    # Strip parenthetical aliases: "Aphex Twin (Richard D. James)" → "Aphex Twin"
                    # Keep the primary name only
                    primary = re.sub(r"\s*\(.*?\)\s*$", "", raw).strip()
                    if primary:
                        names.append(primary)
                        # Also add alias if present (the part inside parens)
                        alias_m = re.search(r"\(([^)]+)\)", raw)
                        if alias_m:
                            alias = alias_m.group(1).strip()
                            # Only add meaningful aliases (not descriptive phrases)
                            if alias and len(alias.split()) <= 4:
                                names.append(alias)
            _ARTIST_NAMES_CACHE = tuple(names)
            return _ARTIST_NAMES_CACHE

    # Fallback if the markdown isn't found: empty tuple
    _ARTIST_NAMES_CACHE = ()
    return _ARTIST_NAMES_CACHE


def extract_artist_refs(prompt: str) -> list[str]:
    """Find producer names in the prompt (case-insensitive substring match).

    Returns a list of canonical artist names (preserving the artist-
    vocabularies.md spelling — the primary name, not the alias).
    """
    if not prompt:
        return []
    names = _load_artist_names()
    if not names:
        return []
    prompt_lower = prompt.lower()
    found = []
    seen_lower: set[str] = set()
    for name in names:
        name_lower = name.lower()
        if name_lower in seen_lower:
            continue
        if name_lower in prompt_lower:
            found.append(name)
            seen_lower.add(name_lower)
    return found


# ── research hooks ──────────────────────────────────────────────────

# Common-genre terms that DON'T need research (LLM training data covers them)
_COMMON_GENRE_TERMS = {
    "techno",
    "house",
    "ambient",
    "hiphop",
    "hip-hop",
    "trap",
    "pop",
    "rock",
    "jazz",
    "edm",
    "electronic",
    "dance",
    "downtempo",
    "minimal",
    "deep house",
    "minor",
    "major",
    "key",
    "tempo",
    "bpm",
    "lo-fi",
    "lofi",
    "dark",
}

# Niche terms that warrant research (not exhaustive — heuristic)
_NICHE_GENRE_HINTS = (
    "wonky",
    "uk funky",
    "footwork",
    "juke",
    "kuduro",
    "gqom",
    "speed garage",
    "hyperpop",
    "vapor",
    "chillwave",
    "future garage",
    "dubstep wobble",
    "psy-trance",
    "psytrance",
    "balearic",
    "italo",
    "freestyle",
    "screwed",
    "chopped and screwed",
    "phonk",
    "drift phonk",
)


def detect_research_hooks(prompt: str) -> list[str]:
    """Identify niche style terms the agent should research before designing.

    Returns a list of terms found in the prompt that are NOT in the common
    set. Heuristic — agent uses these as WebSearch directives.
    """
    if not prompt:
        return []
    prompt_lower = prompt.lower()
    hooks = []
    for hint in _NICHE_GENRE_HINTS:
        if hint in prompt_lower:
            hooks.append(hint)
    return hooks


# ── atlas alternates (stub for Phase 4 enrichment) ─────────────────

def _atlas_alternates_per_role(seed_state: dict) -> dict:
    """For sample-trigger roles, return alternate sample suggestions.

    Phase 1 stub — returns empty dict per role. Phase 4 KnowledgePack
    integration will populate with real atlas_search results.
    """
    alternates: dict = {}
    for track in seed_state.get("tracks", []):
        if track.get("classification") == "sample_trigger":
            alternates[track["role"]] = []  # populated in Phase 4
    return alternates


# ── genre context ──────────────────────────────────────────────────

def _genre_context_for(prompt_directive: Optional[str]) -> dict:
    """Phase 1 stub — full genre-vocabularies.md loading happens in Phase 4.

    Returns empty dict shape; Phase 4 will populate with the descriptive
    character data (kick, bass register, harmonic palette, devices).
    """
    return {}


# ── identity preservation ──────────────────────────────────────────

_IDENTITY_DIRECTIVE = (
    "Preserve the existing seed identity. Existing samples MUST NOT be replaced "
    "(except where you intentionally schedule a sample swap as part of a variant). "
    "Existing notes in scene 0 MUST NOT be overwritten — write variants to NEW scenes "
    "(scene_index >= 1). Existing automation curves MUST be preserved as the 'main' "
    "state. The original loop must still play identically when fired. New material "
    "extends the loop; it does not replace it."
)


# ── design targets ─────────────────────────────────────────────────

_DESIGN_TARGETS = (
    "Design a set of variant clips for the seed loop that allow it to develop into a "
    "fuller arrangement. You decide: how many variants per layer, what sections those "
    "variants serve, the section sequence and length, where the hook lands, when to "
    "withhold and restate. Use the seed's identity (key, tempo, role classification) "
    "as the unbreakable foundation. For midi_riff layers, design fresh per-variant "
    "MIDI rooted in the same scale and tonal center. For sample_trigger layers, "
    "consider sample swaps in fills and breakdowns — but only when the variation "
    "genuinely benefits, not as default. Drum dropouts, sustained pad swells, and "
    "filter sweeps are valid structural moves drawn from the event lexicon. The form "
    "is yours to design — vocabularies tell you what a genre or artist sounds like, "
    "they do not tell you the bar count of an intro."
)


# ── main entry point ───────────────────────────────────────────────

def build_develop_brief(
    ctx: Any,
    seed_state: dict,
    prompt_directive: Optional[str] = None,
) -> dict:
    """Build a Phase-1 develop brief.

    Args:
      ctx: Lifespan context (lifespan_context.ableton, etc.) — not heavily
           used in Phase 1; Phase 4 KnowledgePack consumes it.
      seed_state: SeedState dict from introspect_seed() — read-only
      prompt_directive: optional free-text directive ("extend in microhouse style",
                        "make it sound like Burial", etc.)

    Returns dict with vocabulary fields. NEVER returns form-prescriptive fields.
    """
    artist_refs = extract_artist_refs(prompt_directive or "")
    research_hooks = detect_research_hooks(prompt_directive or "")
    genre_context = _genre_context_for(prompt_directive)
    artist_context = {name: {} for name in artist_refs}  # Phase 4 fills in
    atlas_alternates = _atlas_alternates_per_role(seed_state)

    brief = {
        "mode": "develop",
        "tempo": seed_state.get("tempo", 120.0),
        "key": seed_state.get("key"),
        "seed_state": seed_state,
        "identity_preservation_directive": _IDENTITY_DIRECTIVE,
        "design_targets": _DESIGN_TARGETS,
        "genre_context": genre_context,
        "artist_context": artist_context,
        "atlas_alternates_per_role": atlas_alternates,
        "research_hooks": research_hooks,
        "prompt_directive": prompt_directive,
    }
    return brief
