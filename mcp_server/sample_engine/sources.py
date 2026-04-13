"""Sample sources — discover samples from Ableton browser, Splice, and local filesystem.

Three sources:
- BrowserSource: searches Ableton's built-in browser (samples, drums, packs, user_library)
- SpliceSource: reads Splice's local sounds.db SQLite database for rich metadata
- FilesystemSource: scans user-configured local directories

All sources return SampleCandidate objects. Actual Ableton communication happens in tools.py.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Optional

from .models import SampleCandidate
from .analyzer import parse_filename_metadata, classify_material_from_name


_AUDIO_EXTENSIONS = frozenset({
    ".wav", ".aif", ".aiff", ".mp3", ".flac", ".ogg",
})


# ── Browser Source ─────────────────────────────────────────────────


class BrowserSource:
    """Search Ableton's browser for samples, drums, packs, and user library.

    Parameter-building class — actual Ableton communication happens in tools.py
    which calls build_search_params() and sends the command over TCP.
    """

    DEFAULT_CATEGORIES = ("samples", "drums", "packs", "user_library")

    def build_search_params(
        self, query: str, category: str = "samples", max_results: int = 20,
    ) -> dict:
        """Build a single search_browser command payload."""
        return {
            "path": category,
            "name_filter": query,
            "loadable_only": True,
            "max_results": max_results,
        }

    def build_all_search_params(
        self,
        query: str,
        categories: Optional[list[str]] = None,
        max_results: int = 20,
    ) -> list[dict]:
        """Build search params for each category."""
        cats = categories or list(self.DEFAULT_CATEGORIES)
        return [self.build_search_params(query, cat, max_results) for cat in cats]

    def parse_results(
        self, raw_results: list[dict], category: str = "browser",
    ) -> list[SampleCandidate]:
        """Parse raw browser search results into SampleCandidates."""
        candidates: list[SampleCandidate] = []
        for item in raw_results:
            name = item.get("name", "")
            stem = os.path.splitext(name)[0] if name else ""
            material = classify_material_from_name(stem) if stem else "unknown"
            candidates.append(SampleCandidate(
                source="browser",
                name=stem or name,
                uri=item.get("uri"),
                metadata={
                    "category": category,
                    "uri": item.get("uri", ""),
                    "material_type": material,
                },
            ))
        return candidates


# ── Splice Source ──────────────────────────────────────────────────


# Candidate paths for Splice's sounds.db on macOS
_SPLICE_DB_CANDIDATES = [
    "~/Library/Application Support/com.splice.Splice/sounds.db",
    "~/Library/Application Support/Splice/sounds.db",
    "~/Splice/sounds.db",
]

# Map Splice sample_type to our material_type
_SPLICE_TYPE_MAP = {
    "oneshot": "one_shot",
    "one-shot": "one_shot",
    "loop": "drum_loop",  # default for loops, refined by tags
}

# Tag-based material refinement for loops
_SPLICE_LOOP_REFINEMENT = {
    "vocal": "vocal",
    "vox": "vocal",
    "voice": "vocal",
    "synth": "instrument_loop",
    "keys": "instrument_loop",
    "piano": "instrument_loop",
    "guitar": "instrument_loop",
    "bass": "instrument_loop",
    "pad": "texture",
    "ambient": "texture",
    "texture": "texture",
    "atmosphere": "texture",
    "foley": "foley",
    "fx": "fx",
    "riser": "fx",
    "sweep": "fx",
}


class SpliceSource:
    """Read Splice's local sounds.db for rich sample metadata.

    Splice stores downloaded samples in a SQLite database with columns:
    id, local_path, audio_key, bpm, tags, sample_type, genre, filename,
    provider_name, pack_uuid, duration, popularity, and more.

    The database is opened read-only to avoid corrupting Splice's live data.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self._find_db()
        self.enabled = self.db_path is not None and os.path.isfile(self.db_path)

    @staticmethod
    def _find_db() -> Optional[str]:
        """Auto-detect Splice sounds.db location."""
        for candidate in _SPLICE_DB_CANDIDATES:
            expanded = os.path.expanduser(candidate)
            if os.path.isfile(expanded):
                return expanded
        return None

    def _connect(self) -> Optional[sqlite3.Connection]:
        """Open read-only connection to Splice database."""
        if not self.enabled:
            return None
        try:
            uri = f"file:{self.db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            conn.row_factory = sqlite3.Row
            return conn
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return None

    def search(
        self,
        query: str,
        max_results: int = 20,
        sample_type: Optional[str] = None,
        key: Optional[str] = None,
        bpm_min: Optional[float] = None,
        bpm_max: Optional[float] = None,
        genre: Optional[str] = None,
    ) -> list[SampleCandidate]:
        """Search Splice database by tags, filename, key, BPM, genre.

        Only returns samples with local_path NOT NULL (actually downloaded).
        """
        conn = self._connect()
        if conn is None:
            return []

        try:
            conditions = ["local_path IS NOT NULL"]
            params: list = []

            # Text search across tags and filename
            if query:
                words = query.lower().split()
                for word in words:
                    conditions.append(
                        "(LOWER(tags) LIKE ? OR LOWER(filename) LIKE ?)"
                    )
                    params.extend([f"%{word}%", f"%{word}%"])

            if sample_type:
                conditions.append("sample_type = ?")
                params.append(sample_type)

            if key:
                conditions.append("audio_key = ?")
                params.append(key)

            if bpm_min is not None:
                conditions.append("bpm >= ?")
                params.append(bpm_min)

            if bpm_max is not None:
                conditions.append("bpm <= ?")
                params.append(bpm_max)

            if genre:
                conditions.append("LOWER(genre) LIKE ?")
                params.append(f"%{genre.lower()}%")

            where = " AND ".join(conditions)
            sql = f"""
                SELECT id, local_path, audio_key, bpm, tags, sample_type,
                       genre, filename, provider_name, pack_uuid, duration,
                       popularity
                FROM samples
                WHERE {where}
                ORDER BY popularity DESC
                LIMIT ?
            """
            params.append(max_results)

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            return [self._row_to_candidate(row) for row in rows]
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return []
        finally:
            conn.close()

    def get_sample_count(self) -> int:
        """Return total number of downloaded samples in the Splice library."""
        conn = self._connect()
        if conn is None:
            return 0
        try:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM samples WHERE local_path IS NOT NULL"
            )
            return cursor.fetchone()[0]
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return 0
        finally:
            conn.close()

    def get_available_keys(self) -> list[str]:
        """Return all unique keys in the Splice library."""
        conn = self._connect()
        if conn is None:
            return []
        try:
            cursor = conn.execute(
                "SELECT DISTINCT audio_key FROM samples "
                "WHERE audio_key IS NOT NULL AND local_path IS NOT NULL "
                "ORDER BY audio_key"
            )
            return [row[0] for row in cursor.fetchall()]
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return []
        finally:
            conn.close()

    def get_available_genres(self) -> list[str]:
        """Return all unique genres in the Splice library."""
        conn = self._connect()
        if conn is None:
            return []
        try:
            cursor = conn.execute(
                "SELECT DISTINCT genre FROM samples "
                "WHERE genre IS NOT NULL AND genre != '' AND local_path IS NOT NULL "
                "ORDER BY genre"
            )
            return [row[0] for row in cursor.fetchall()]
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return []
        finally:
            conn.close()

    def search_by_key_and_tempo(
        self,
        key: str,
        bpm: float,
        tolerance_bpm: float = 5.0,
        max_results: int = 10,
    ) -> list[SampleCandidate]:
        """Find samples matching a specific key and tempo range.

        This is the power query — find samples that musically fit your song.
        """
        return self.search(
            query="",
            key=key,
            bpm_min=bpm - tolerance_bpm,
            bpm_max=bpm + tolerance_bpm,
            max_results=max_results,
        )

    def _row_to_candidate(self, row: sqlite3.Row) -> SampleCandidate:
        """Convert a database row to SampleCandidate with rich metadata."""
        tags = str(row["tags"] or "")
        splice_type = str(row["sample_type"] or "")
        material = self._classify_splice_material(splice_type, tags)

        return SampleCandidate(
            source="splice",
            name=str(row["filename"] or ""),
            file_path=str(row["local_path"] or ""),
            metadata={
                "key": row["audio_key"],
                "bpm": row["bpm"],
                "tags": tags,
                "genre": row["genre"],
                "sample_type": splice_type,
                "material_type": material,
                "pack": row["provider_name"],
                "pack_uuid": row["pack_uuid"],
                "duration": row["duration"],
                "popularity": row["popularity"],
                "splice_id": row["id"],
            },
        )

    @staticmethod
    def _classify_splice_material(sample_type: str, tags: str) -> str:
        """Classify material type from Splice's sample_type + tags.

        Splice has "oneshot" and "loop". We refine loops by tag content.
        """
        base = _SPLICE_TYPE_MAP.get(sample_type.lower(), "unknown")

        if base == "one_shot":
            return "one_shot"

        # Refine loops by tag keywords
        tags_lower = tags.lower()
        for keyword, material in _SPLICE_LOOP_REFINEMENT.items():
            if keyword in tags_lower:
                return material

        # Default: if it's a loop, call it drum_loop (most common)
        if base == "drum_loop":
            return "drum_loop"

        # Fall back to filename-based classification
        return classify_material_from_name(tags_lower) or "unknown"


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
            if candidate.metadata.get("key") and query_lower in str(
                candidate.metadata.get("key", "")
            ).lower():
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


# ── Search Query Builder ────────────────────────────────────────────


def build_search_queries(
    user_query: str,
    material_type: Optional[str] = None,
    song_context: Optional[dict] = None,
) -> list[str]:
    """Build smart search queries from user request + song context."""
    queries = [user_query]

    if material_type:
        synonyms = {
            "vocal": ["vocal", "vox", "voice", "acapella"],
            "drum_loop": ["drum loop", "breakbeat", "percussion loop", "break"],
            "texture": ["ambient", "pad", "texture", "drone"],
            "one_shot": ["one shot", "hit", "stab"],
            "instrument_loop": ["synth", "keys", "guitar", "bass loop"],
            "foley": ["foley", "field recording", "found sound"],
        }
        for syn in synonyms.get(material_type, []):
            if syn.lower() not in user_query.lower():
                queries.append(f"{user_query} {syn}")

    if song_context:
        key = song_context.get("key", "")
        if key and key not in user_query:
            queries.append(f"{user_query} {key}")

    return queries[:5]
