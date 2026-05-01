"""Markdown parser for livepilot/skills/livepilot-core/references/genre-vocabularies.md.

Genre entries are demarcated by `## genre_name` headers. Each entry contains
descriptive content (kick character, bass register, harmonic palette, etc.).
We parse opportunistically — capture the raw markdown block per genre name,
let the agent reason on the content rather than over-structuring it.
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Optional


_GENRE_CACHE: Optional[dict[str, dict]] = None


def _genre_md_path() -> Optional[Path]:
    """Locate genre-vocabularies.md by walking up from this file."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "livepilot" / "skills" / "livepilot-core" / "references" / "genre-vocabularies.md"
        if candidate.exists():
            return candidate
    return None


def _load_genre_md() -> dict[str, dict]:
    """Parse the markdown into {genre_name_lowered: {raw: text, ...}}.

    Cached after first call.
    """
    global _GENRE_CACHE
    if _GENRE_CACHE is not None:
        return _GENRE_CACHE
    path = _genre_md_path()
    if path is None:
        _GENRE_CACHE = {}
        return _GENRE_CACHE

    text = path.read_text(encoding="utf-8")
    # Genres are demarcated by `## name` (or `### name`) — the structure
    # may vary, so handle both. Use a regex split.
    genres: dict[str, dict] = {}
    sections = re.split(r"^##+\s+(.+?)\s*$", text, flags=re.MULTILINE)
    # Re.split returns [pre, name1, body1, name2, body2, ...]
    for i in range(1, len(sections), 2):
        name = sections[i].strip()
        if not name or name.lower() in ("vocabulary", "how to read this", "table of contents"):
            continue
        body = sections[i + 1] if i + 1 < len(sections) else ""
        # Lowercase + underscore normalize the key
        key = name.lower().replace(" ", "_").replace("-", "_")
        genres[key] = {"name": name, "raw_md": body.strip()[:2000]}  # cap to keep brief size sane

    _GENRE_CACHE = genres
    return _GENRE_CACHE


def load_genre_context(genre: str) -> dict:
    """Load descriptive context for a parsed genre.

    genre: parsed genre slug (techno, microhouse, ambient, etc.)

    Returns a dict with content if found, or {"status": "no_match", ...} if not.
    """
    if not genre:
        return {"status": "no_genre_provided"}
    genres = _load_genre_md()
    key = genre.lower().replace(" ", "_").replace("-", "_")
    if key in genres:
        return genres[key]
    # Try fuzzy: genre might be sub-genre matching a key contained in entry names
    for k, v in genres.items():
        if key in k or k in key:
            return v
    return {"status": "no_match", "parsed_genre": genre}
