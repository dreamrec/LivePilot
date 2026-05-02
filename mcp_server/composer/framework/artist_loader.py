"""Markdown parser for livepilot/skills/livepilot-core/references/artist-vocabularies.md."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Optional


_ARTIST_CACHE: Optional[dict[str, dict]] = None


def _artist_md_path() -> Optional[Path]:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "livepilot" / "skills" / "livepilot-core" / "references" / "artist-vocabularies.md"
        if candidate.exists():
            return candidate
    return None


def _load_artist_md() -> dict[str, dict]:
    """Parse artist entries. Existing pattern in develop/brief_builder.py:
    `### Name` headers with body content."""
    global _ARTIST_CACHE
    if _ARTIST_CACHE is not None:
        return _ARTIST_CACHE
    path = _artist_md_path()
    if path is None:
        _ARTIST_CACHE = {}
        return _ARTIST_CACHE
    text = path.read_text(encoding="utf-8")

    artists: dict[str, dict] = {}
    sections = re.split(r"^###\s+(.+?)\s*$", text, flags=re.MULTILINE)
    for i in range(1, len(sections), 2):
        name = sections[i].strip()
        if not name or "Vocabulary" in name or "How to" in name:
            continue
        body = sections[i + 1] if i + 1 < len(sections) else ""
        # Strip parenthetical aliases for canonical key: "Aphex Twin (Richard D. James)" → "Aphex Twin"
        primary = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
        if primary:
            artists[primary] = {"name": primary, "raw_md": body.strip()[:2000]}
    _ARTIST_CACHE = artists
    return _ARTIST_CACHE


def load_artist_context(artist_names: list[str]) -> dict[str, dict]:
    """Load context for the given artist names.

    artist_names: list of names (case-insensitive matched against parser keys)
    Returns: {artist_name: {raw_md: ..., ...}, ...}
    """
    if not artist_names:
        return {}
    parsed = _load_artist_md()
    result = {}
    parsed_lower = {k.lower(): k for k in parsed.keys()}
    for name in artist_names:
        canonical = parsed_lower.get(name.lower())
        if canonical:
            result[canonical] = parsed[canonical]
    return result
