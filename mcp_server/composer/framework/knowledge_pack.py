"""KnowledgePack — assembles the vocabulary fields each compose mode's brief carries.

For full mode: rich (event_lexicon, genre_context, artist_context,
atlas_anchors, atlas_candidates_per_role, manual_snippets).
For fast mode: subset (no event_lexicon — fast mode is loop-sketch scope).
For develop mode: subset overlapping with full.

v1.25 adds `atlas_anchors` — cohort + role-anchored URIs from
atlas_pack_aware_compose, populated when atlas + brief_text are provided.
The agent uses `atlas_explore` / `atlas_audition` / `atlas_substitute`
mid-design to dig past anchors when needed (hybrid knowledge surface).
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Optional

from .event_lexicon import EVENT_LEXICON, get_event_lexicon
from .genre_loader import load_genre_context
from .artist_loader import load_artist_context

logger = logging.getLogger(__name__)


class KnowledgePack:
    """Central knowledge assembly for compose-mode briefs."""

    def build(
        self,
        intent: dict,
        mode: str = "full",
        *,
        atlas: Any = None,
        ableton: Any = None,
        ctx: Any = None,
        brief_text: str = "",
    ) -> dict:
        """Build the knowledge fields for a brief.

        intent: parsed CompositionIntent dict with at least 'genre', possibly 'sub_genre'.
                May also carry 'artists' (list of producer names).
        mode: 'fast' | 'full' | 'develop'
        atlas: AtlasManager instance (optional — when None, atlas_anchors is None)
        ableton: ableton client (optional — reserved for v1.25.x browser fallback)
        ctx: lifespan context (optional — reserved for taste_profile / recent_uris)
        brief_text: the original prompt string (required for atlas_anchors)

        Returns a dict — pass directly to brief.knowledge OR spread into brief top-level.
        """
        # Genre context — descriptive vocabulary for the parsed style
        genre = intent.get("sub_genre") or intent.get("genre") or ""
        genre_ctx = load_genre_context(genre) if genre else {}

        # Artist context — populated only if prompt mentioned producers
        artist_names = intent.get("artists") or []
        artist_ctx = load_artist_context(artist_names)

        knowledge: dict[str, Any] = {
            "genre_context": genre_ctx,
            "artist_context": artist_ctx,
            "atlas_candidates_per_role": {},  # legacy field — empty in v1.25 (replaced by atlas_anchors)
            "atlas_anchors": None,            # populated below for full mode when atlas available
            "manual_snippets": {},
        }

        # Event lexicon — full mode only (loop sketch doesn't design form)
        if mode in ("full", "develop"):
            knowledge["event_lexicon"] = list(EVENT_LEXICON)
        else:
            knowledge["event_lexicon"] = []

        # Atlas anchors — full mode only, requires atlas + brief_text. Best-effort:
        # any failure path silently leaves anchors=None and the brief still works.
        if mode == "full" and atlas is not None and brief_text:
            try:
                from .atlas_resolver import AtlasResolver
                resolver = AtlasResolver(
                    atlas=atlas,
                    ableton=ableton,
                    taste_profile=_safe_get_taste_profile(ctx),
                    recent_uris=_safe_get_recent_uris(ctx),
                )
                mood = _extract_mood(intent)
                anchors = resolver.resolve_anchors(
                    brief_text=brief_text,
                    genre=genre,
                    mood=mood,
                    artist_refs=artist_names,
                )
                knowledge["atlas_anchors"] = asdict(anchors)
            except Exception as exc:
                logger.debug("KnowledgePack.build: atlas_anchors unavailable: %s", exc)

        return knowledge


# ── Helpers ─────────────────────────────────────────────────────────


def _extract_mood(intent: dict) -> str:
    """Derive a mood string from the parsed intent.

    Combines mood + descriptors fields when present. Falls back to "" so
    the resolver's mood-overlap boost simply doesn't fire (rather than
    matching against junk).
    """
    parts: list[str] = []
    for key in ("mood", "descriptors", "modifiers"):
        val = intent.get(key)
        if isinstance(val, str) and val:
            parts.append(val)
        elif isinstance(val, (list, tuple)):
            parts.extend(str(v) for v in val if v)
    return " ".join(parts).strip()


def _safe_get_taste_profile(ctx: Any) -> Optional[dict]:
    """Best-effort taste profile fetch. Returns None on any failure."""
    if ctx is None:
        return None
    try:
        # The taste graph tools live under mcp_server/tools/agent_os.py;
        # importing here would create a cycle, so leave as None for now.
        # v1.25.x will wire in get_taste_profile() once the cycle is broken.
        return None
    except Exception:
        return None


def _safe_get_recent_uris(ctx: Any) -> Optional[set[str]]:
    """Best-effort recent-URIs fetch (§7 #2 anti-repeat). Returns None on failure."""
    if ctx is None:
        return None
    try:
        # Same cycle concern as _safe_get_taste_profile — defer to v1.25.x.
        return None
    except Exception:
        return None
