"""Sample sources — discover samples from browser, filesystem, and Freesound.

Browser source is a thin wrapper around existing MCP tools (search_browser,
get_browser_items). Filesystem scans local directories. Freesound uses the
public API v2.
"""

from __future__ import annotations

import os
import json
from typing import Optional

from .models import SampleCandidate
from .analyzer import parse_filename_metadata, classify_material_from_name


_AUDIO_EXTENSIONS = frozenset({
    ".wav", ".aif", ".aiff", ".mp3", ".flac", ".ogg",
})


# ── Browser Source ─────────────────────────────────────────────────


class BrowserSource:
    """Search Ableton's browser for samples. Wraps search_browser and get_browser_items."""

    def search(self, query: str, categories: list[str] | None = None, max_results: int = 20) -> list[SampleCandidate]:
        """Build search parameters for the browser. Actual execution happens in tools.py."""
        categories = categories or ["samples", "drums", "user_library"]
        candidates = []
        for category in categories:
            candidates.append(SampleCandidate(
                source="browser",
                name=query,
                metadata={"category": category, "query": query},
            ))
        return candidates

    def build_search_params(self, query: str, category: str = "samples", max_results: int = 20) -> dict:
        return {"path": category, "name_filter": query, "loadable_only": True, "max_results": max_results}


# ── Filesystem Source ───────────────────────────────────────────────


class FilesystemSource:
    """Scan local directories for audio files with metadata extraction."""

    def __init__(
        self,
        scan_paths: Optional[list[str]] = None,
        max_depth: int = 6,
    ):
        self.scan_paths = scan_paths or []
        self.max_depth = max_depth

    def scan(self) -> list[SampleCandidate]:
        """Scan all configured paths for audio files."""
        candidates: list[SampleCandidate] = []
        for base_path in self.scan_paths:
            expanded = os.path.expanduser(base_path)
            if not os.path.isdir(expanded):
                continue
            self._scan_dir(expanded, 0, candidates)
        return candidates

    def search(self, query: str, max_results: int = 20) -> list[SampleCandidate]:
        """Search scanned files by query keywords."""
        all_files = self.scan()
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored: list[tuple[SampleCandidate, float]] = []
        for candidate in all_files:
            name_lower = candidate.name.lower()
            score = sum(1 for w in query_words if w in name_lower)
            # Boost for metadata matches
            if candidate.metadata.get("key") and query_lower in str(candidate.metadata.get("key", "")).lower():
                score += 0.5
            if score > 0:
                scored.append((candidate, score))

        scored.sort(key=lambda x: -x[1])
        return [c for c, _ in scored[:max_results]]

    def _scan_dir(self, path: str, depth: int, out: list[SampleCandidate]):
        if depth > self.max_depth:
            return
        try:
            entries = os.scandir(path)
        except PermissionError:
            return

        for entry in entries:
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in _AUDIO_EXTENSIONS:
                    stem = os.path.splitext(entry.name)[0]
                    metadata = parse_filename_metadata(entry.name)
                    metadata["material_type"] = classify_material_from_name(stem)
                    out.append(SampleCandidate(
                        source="filesystem",
                        name=stem,
                        file_path=entry.path,
                        metadata=metadata,
                    ))
            elif entry.is_dir() and not entry.name.startswith("."):
                self._scan_dir(entry.path, depth + 1, out)


# ── Freesound Helpers ───────────────────────────────────────────────


def parse_freesound_metadata(raw: dict) -> SampleCandidate:
    """Parse a Freesound API response into a SampleCandidate."""
    ac = raw.get("ac_analysis") or {}
    metadata = {
        "key": ac.get("ac_key"),
        "bpm": ac.get("ac_tempo"),
        "brightness": ac.get("ac_brightness"),
        "depth": ac.get("ac_depth"),
        "tags": raw.get("tags", []),
        "duration": raw.get("duration"),
        "license": raw.get("license"),
    }
    tags = raw.get("tags", [])
    tag_str = " ".join(tags)
    material = classify_material_from_name(tag_str)
    metadata["material_type"] = material

    return SampleCandidate(
        source="freesound",
        name=raw.get("name", ""),
        freesound_id=raw.get("id"),
        metadata=metadata,
    )


class FreesoundSource:
    """Search Freesound API v2. Requires FREESOUND_API_KEY env var."""

    def __init__(self, api_key: Optional[str] = None, download_dir: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FREESOUND_API_KEY")
        self.download_dir = download_dir or os.path.expanduser(
            "~/Documents/LivePilot/downloads/freesound"
        )
        self.enabled = bool(self.api_key)

    def search(self, query: str, max_results: int = 10,
               license_filter: str = "Attribution") -> list[SampleCandidate]:
        """Search Freesound. Returns candidates without downloading.

        Actual HTTP calls happen in the MCP tool layer (tools.py) which
        can use httpx/aiohttp. This module builds the query and parses results.
        """
        if not self.enabled:
            return []
        # Build query params for the tool layer to execute
        return []  # Placeholder — actual HTTP is in tools.py

    def build_search_params(self, query: str, max_results: int = 10,
                            license_filter: str = "Attribution") -> dict:
        """Build Freesound API search parameters."""
        return {
            "query": query,
            "page_size": min(max_results, 15),
            "fields": "id,name,tags,duration,license,ac_analysis,previews",
            "filter": f'license:"{license_filter}"',
            "sort": "rating_desc",
        }


# ── Search Query Builder ────────────────────────────────────────────


def build_search_queries(
    user_query: str,
    material_type: Optional[str] = None,
    song_context: Optional[dict] = None,
) -> list[str]:
    """Build smart search queries from user request + song context.

    Returns multiple query strings to try across different sources.
    """
    queries = [user_query]

    if material_type:
        # Add material-specific synonyms
        synonyms = {
            "vocal": ["vocal", "vox", "voice", "acapella"],
            "drum_loop": ["drum loop", "breakbeat", "percussion loop"],
            "texture": ["ambient", "pad", "texture", "drone"],
            "one_shot": ["one shot", "hit", "stab"],
        }
        for syn in synonyms.get(material_type, []):
            if syn.lower() not in user_query.lower():
                queries.append(f"{user_query} {syn}")

    if song_context:
        key = song_context.get("key", "")
        if key and key not in user_query:
            queries.append(f"{user_query} {key}")

    return queries[:5]  # Cap at 5 queries
