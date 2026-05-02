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
    "actual conventions of that subgenre.\n\n"
    "INSTRUMENT SELECTION (v1.25 hybrid knowledge surface — MANDATED FOUR-SOURCE SEARCH):\n"
    "The brief's `atlas_anchors` is ONE source. Before committing any role pick "
    "you MUST also query the other three sources below. Factory-atlas-only picks "
    "have repeatedly missed canonical user-curated instruments (e.g., the 808 Trap "
    "Selector Rack from Trap Drums by Sound Oracle pack lives in the packs overlay, "
    "not the factory tag index). Always union BEFORE deciding.\n\n"
    "Source 1 — Factory atlas (already surfaced in atlas_anchors). Three tools:\n"
    "  • atlas_audition(uri) — full sidecar dump for a chosen URI: character "
    "tags, signature_techniques, producer-curated macro values, related demos. "
    "Call this BEFORE committing to a candidate when its tags alone aren't "
    "enough to know if it fits the section.\n"
    "  • atlas_explore(role, mood, genre, artists?) — refined per-role query "
    "when an anchor doesn't fit the section's purpose, or when you need siblings "
    "of a role pick. Returns 3-5 ranked candidates with reasoning trails.\n"
    "  • atlas_substitute(current_uri, anti_tag) — anti-tag-driven swap to use "
    "AFTER analyze_sound_design or analyze_mix flags an issue (\"too bright\", "
    "\"too aggressive\", \"too sparse\", \"muddy\", \"static\", \"generic\"). "
    "Returns 3 alternatives that explicitly avoid the unwanted property.\n\n"
    "Source 2 — User corpus (mandatory union — ~/.livepilot/atlas-overlays/):\n"
    "  • extension_atlas_search(query=\"<role>\", limit=10) — searches all four "
    "overlay namespaces: `packs` (Ableton factory packs with hidden_gems, "
    "notable_presets, signature_workflows fields), `m4l-devices` (curated M4L "
    "device knowledge), `user.*` (your scanned .amxd / plugin / preset library), "
    "`elektron` (hardware-mirror chains). Producer-curated rack instruments "
    "(808 Trap Selector Rack, Harmonic Drone Generator, etc.) live here, NOT "
    "in the factory tag index. Always run this query alongside atlas_explore.\n"
    "  • extension_atlas_search(query=\"<role-or-aesthetic>\", entity_type=\"demo_project\") — "
    "GROUND-TRUTH ROLE→URI MAPPING. The packs namespace contains 100+ analyzed "
    "demo .als project parses; each carries actual track-by-track instrument "
    "URIs proven on real Ableton-shipped demos. For 808 bass, query "
    "`demo_project` to find which pack-included .als demos use 808 bass and "
    "what URI they loaded — the highest-confidence source for any role.\n"
    "  • extension_atlas_get(namespace, entity_id) — full body of a chosen entry "
    "including hidden_gems and signature_workflows fields the search summary trims.\n\n"
    "Source 3 — Anthropic Ableton Knowledge MCP (mcp__Ableton_Knowledge__*):\n"
    "  • search_transcripts(query) — Ableton's official tutorial video transcripts; "
    "ground-truth pedagogy on how producers actually use the device.\n"
    "  • search_live_manual(query) — live manual snippets for any device or feature.\n"
    "  • search_knowledge_base(query) — broader Ableton knowledge base.\n"
    "  • search_videos(query) — official tutorial video metadata.\n"
    "  Run these for the ROLE term (e.g., \"808 bass\", \"sidechain compression\") "
    "and for any artist/genre reference in the prompt to ground your design choices.\n\n"
    "FOUR-SOURCE SEARCH PROTOCOL per role:\n"
    "  1. Read atlas_anchors[role] (Source 1 starting point).\n"
    "  2. Call atlas_explore(role, mood, genre, artists) (Source 1 ranked alts).\n"
    "  3. Call extension_atlas_search(query=role) and extension_atlas_search(query=role, "
    "entity_type=\"demo_project\") (Source 2 user corpus + ground-truth demos).\n"
    "  4. Call mcp__Ableton_Knowledge__search_transcripts(query=role) for context (Source 3).\n"
    "  5. Union results, score against brief's mood/aesthetic, then commit.\n\n"
    "The framework's job was to surface the corpus. The picks are yours. "
    "Submit your design as a plan to compose_full_apply with: per-track variant "
    "clips at chosen scene slots, per-section arrangement_clip placements "
    "referencing those variants, and structural events scheduled at phrase "
    "boundaries. The form is YOUR creative product — vocabularies tell you "
    "what techno or BoC sound like, they do not tell you the bar count of an intro."
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

    # Build knowledge pack — populates genre_context, artist_context, event_lexicon,
    # AND v1.25 atlas_anchors when atlas + brief_text are available.
    if artist_refs:
        intent_dict["artists"] = artist_refs
    kp = KnowledgePack()
    atlas_obj = _safe_get_atlas(ctx)
    ableton_obj = _safe_get_ableton(ctx)
    knowledge = kp.build(
        intent_dict,
        mode="full",
        atlas=atlas_obj,
        ableton=ableton_obj,
        ctx=ctx,
        brief_text=prompt or "",
    )

    return {
        "mode": "full",
        "tempo": tempo,
        "key": key,
        "parsed_intent": intent_dict,
        "genre_context": knowledge["genre_context"],
        "artist_context": knowledge["artist_context"],
        "event_lexicon": knowledge["event_lexicon"],
        "atlas_candidates_per_role": knowledge["atlas_candidates_per_role"],
        "atlas_anchors": knowledge.get("atlas_anchors"),
        "manual_snippets": knowledge["manual_snippets"],
        "seed_state": seed_state,
        "research_hooks": research_hooks,
        "design_targets": _DESIGN_TARGETS,
    }


# ── Lifespan-context helpers ───────────────────────────────────────


def _safe_get_atlas(ctx: Any) -> Optional[Any]:
    """Best-effort atlas fetch. Returns None on any failure."""
    try:
        from ...atlas import get_atlas
        return get_atlas()
    except Exception:
        return None


def _safe_get_ableton(ctx: Any) -> Optional[Any]:
    """Best-effort ableton-client fetch from lifespan_context. None on miss."""
    try:
        if ctx is not None and hasattr(ctx, "lifespan_context"):
            return ctx.lifespan_context.get("ableton")
    except Exception:
        pass
    return None
