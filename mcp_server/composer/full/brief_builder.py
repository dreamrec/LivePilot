"""Full-mode brief builder — Phase 1 of the LLM-creative two-phase flow.

Takes a prompt (and optional seed_state for "extend an existing project"
flows) and returns a brief carrying VOCABULARY for the agent to design
the song's form from.

CRITICAL: The brief MUST NOT contain predetermined section sequences, bar
counts, or fixed variant taxonomies. The agent decides the form per call.
The framework only provides:
- Parsed intent (genre/mood/tempo/key from the prompt)
- Genre/artist character vocabulary (descriptive)
- The 42-event structural lexicon (named primitives, not a sequence)
- Atlas instrument candidates per role
- Live manual snippets for likely devices
- Optional seed_state for extension flows
- Research hooks (WebSearch directives for niche styles)
- An open-ended design_targets text describing the variation surface

Phase 1 stubs: genre_context, atlas_candidates_per_role, manual_snippets,
event_lexicon — empty values now, populated by Phase 4 KnowledgePack.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Optional

from ..prompt_parser import parse_prompt
from ..develop.brief_builder import (
    extract_artist_refs,
    detect_research_hooks,
)
from ..framework.knowledge_pack import KnowledgePack


# ── design targets ─────────────────────────────────────────────────

_DESIGN_TARGETS = (
    "Design a full-track arrangement from the prompt and (when provided) "
    "the seed_state. You decide every aspect of the form: section sequence, "
    "section bar counts, drop placement (or absence), breakdown placement, "
    "outro length, hook reveal/withholding/restatement schedule, element "
    "entry/exit choreography across the timeline. Use the genre_context and "
    "artist_context as flavor (sonic character, gear preferences, harmonic "
    "stance) — they describe what a style sounds like, NOT how to structure "
    "the song. Use the event_lexicon as a vocabulary of named structural "
    "moves to schedule at chosen phrase boundaries. For niche style references "
    "in research_hooks, run WebSearch to ground your form choices in the "
    "actual conventions of that subgenre. Submit your design as a plan to "
    "compose_full_apply with: per-track variant clips at chosen scene slots, "
    "per-section arrangement_clip placements referencing those variants, "
    "and structural events scheduled at phrase boundaries. The form is YOUR "
    "creative product — vocabularies tell you what techno or BoC sound like, "
    "they do not tell you the bar count of an intro."
)


# ── tempo extraction ───────────────────────────────────────────────

def _extract_tempo_from_intent(intent: Any) -> Optional[float]:
    """Pull tempo from CompositionIntent (dataclass or dict)."""
    if is_dataclass(intent):
        intent = asdict(intent)
    if not isinstance(intent, dict):
        return None
    val = intent.get("tempo")
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _extract_key_from_intent(intent: Any) -> Optional[str]:
    """Pull key from CompositionIntent (dataclass or dict)."""
    if is_dataclass(intent):
        intent = asdict(intent)
    if not isinstance(intent, dict):
        return None
    return intent.get("key")


def _intent_to_dict(intent: Any) -> dict:
    if is_dataclass(intent):
        return asdict(intent)
    if isinstance(intent, dict):
        return intent
    return {"raw_intent": str(intent)}


# ── main entry point ───────────────────────────────────────────────

def build_full_brief(
    ctx: Any,
    prompt: str,
    seed_state: Optional[dict] = None,
) -> dict:
    """Build a Phase-1 full-mode brief.

    Args:
      ctx: Lifespan context — Phase 4 KnowledgePack will use this to fetch
           atlas candidates + manual snippets. Phase 1 stub doesn't need it.
      prompt: free-text directive ("dark techno 128bpm in Am",
              "make it sound like Burial", etc.)
      seed_state: optional dict from develop's introspect_seed — when
                  present, full mode extends the existing project; when
                  None, full mode generates from prompt only.

    Returns dict with vocabulary fields. NEVER returns form-prescriptive fields.
    """
    parsed_intent = parse_prompt(prompt)
    intent_dict = _intent_to_dict(parsed_intent)

    # Tempo + key precedence: seed wins when present, else prompt
    seed_tempo = seed_state.get("tempo") if seed_state else None
    seed_key = seed_state.get("key") if seed_state else None
    tempo = seed_tempo if seed_tempo is not None else _extract_tempo_from_intent(parsed_intent)
    key = seed_key if seed_key is not None else _extract_key_from_intent(parsed_intent)

    # Vocabulary lookups
    artist_refs = extract_artist_refs(prompt or "")
    research_hooks = detect_research_hooks(prompt or "")

    # Build knowledge pack — populates genre_context, artist_context, event_lexicon
    if artist_refs:
        intent_dict["artists"] = artist_refs
    kp = KnowledgePack()
    knowledge = kp.build(intent_dict, mode="full")

    return {
        "mode": "full",
        "tempo": tempo,
        "key": key,
        "parsed_intent": intent_dict,
        "genre_context": knowledge["genre_context"],
        "artist_context": knowledge["artist_context"],
        "event_lexicon": knowledge["event_lexicon"],
        "atlas_candidates_per_role": knowledge["atlas_candidates_per_role"],
        "manual_snippets": knowledge["manual_snippets"],
        "seed_state": seed_state,
        "research_hooks": research_hooks,
        "design_targets": _DESIGN_TARGETS,
    }
