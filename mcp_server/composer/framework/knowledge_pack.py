"""KnowledgePack — assembles the vocabulary fields each compose mode's brief carries.

For full mode: rich (event_lexicon, genre_context, artist_context, atlas_candidates, manual_snippets).
For fast mode: subset (no event_lexicon — fast mode is loop-sketch scope, doesn't design form).
For develop mode: subset overlapping with full.
"""

from __future__ import annotations
from typing import Any

from .event_lexicon import EVENT_LEXICON, get_event_lexicon
from .genre_loader import load_genre_context
from .artist_loader import load_artist_context


class KnowledgePack:
    """Central knowledge assembly for compose-mode briefs."""

    def build(self, intent: dict, mode: str = "full") -> dict:
        """Build the knowledge fields for a brief.

        intent: parsed CompositionIntent dict with at least 'genre', possibly 'sub_genre'.
                May also carry 'artists' (list of producer names).
        mode: 'fast' | 'full' | 'develop'

        Returns a dict — pass directly to brief.knowledge OR spread into brief top-level.
        """
        # Genre context — descriptive vocabulary for the parsed style
        genre = intent.get("sub_genre") or intent.get("genre") or ""
        genre_ctx = load_genre_context(genre) if genre else {}

        # Artist context — populated only if prompt mentioned producers
        artist_names = intent.get("artists") or []
        artist_ctx = load_artist_context(artist_names)

        knowledge = {
            "genre_context": genre_ctx,
            "artist_context": artist_ctx,
            "atlas_candidates_per_role": {},  # populated by brief_builder via existing get_role_candidates
            "manual_snippets": {},  # populated by brief_builder per likely device
        }

        # Event lexicon — full mode only (loop sketch doesn't design form)
        if mode in ("full", "develop"):
            knowledge["event_lexicon"] = list(EVENT_LEXICON)
        else:
            knowledge["event_lexicon"] = []

        return knowledge
