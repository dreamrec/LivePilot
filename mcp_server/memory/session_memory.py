"""SessionMemory — ephemeral per-session observations, hypotheses, decisions.

Pure Python, zero I/O.  Tracks what happened *this* session so that engines
can reference recent context without polluting long-term memory.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

_VALID_CATEGORIES = {"observation", "hypothesis", "decision", "issue"}


@dataclass
class SessionMemoryEntry:
    """Ephemeral per-session memory — what happened this session."""

    id: str
    timestamp_ms: int
    category: str  # "observation", "hypothesis", "decision", "issue"
    content: str
    engine: str  # which engine created this
    confidence: float
    related_tracks: list[int] = field(default_factory=list)
    expires_with_session: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp_ms": self.timestamp_ms,
            "category": self.category,
            "content": self.content,
            "engine": self.engine,
            "confidence": self.confidence,
            "related_tracks": list(self.related_tracks),
            "expires_with_session": self.expires_with_session,
        }


class SessionMemoryStore:
    """In-memory store for session-scoped observations and decisions."""

    def __init__(self) -> None:
        self._entries: list[SessionMemoryEntry] = []

    def add(
        self,
        category: str,
        content: str,
        engine: str,
        confidence: float = 0.5,
        tracks: Optional[list[int]] = None,
    ) -> str:
        """Add a session memory entry.  Returns the new entry id."""
        if category not in _VALID_CATEGORIES:
            raise ValueError(
                f"category must be one of {_VALID_CATEGORIES}, got {category!r}"
            )
        confidence = max(0.0, min(1.0, confidence))

        entry = SessionMemoryEntry(
            id=f"smem_{uuid.uuid4().hex[:8]}",
            timestamp_ms=int(time.time() * 1000),
            category=category,
            content=content,
            engine=engine,
            confidence=confidence,
            related_tracks=list(tracks) if tracks else [],
        )
        self._entries.append(entry)
        return entry.id

    def get_recent(
        self,
        limit: int = 10,
        category: Optional[str] = None,
        engine: Optional[str] = None,
    ) -> list[SessionMemoryEntry]:
        """Return the most recent entries, optionally filtered."""
        filtered = self._entries
        if category:
            filtered = [e for e in filtered if e.category == category]
        if engine:
            filtered = [e for e in filtered if e.engine == engine]
        # Most recent first
        return list(reversed(filtered))[:limit]

    def get_by_tracks(self, track_indices: list[int]) -> list[SessionMemoryEntry]:
        """Return entries related to any of the given track indices."""
        idx_set = set(track_indices)
        return [
            e for e in self._entries
            if idx_set.intersection(e.related_tracks)
        ]

    def clear(self) -> None:
        """Wipe all session memory."""
        self._entries.clear()

    def to_dict(self) -> dict:
        """Serialize the full store."""
        return {
            "entries": [e.to_dict() for e in self._entries],
            "count": len(self._entries),
        }
