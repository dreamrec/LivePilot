"""Session Continuity data models — pure dataclasses, zero I/O."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class CreativeThread:
    """An unresolved creative goal or direction."""

    thread_id: str = ""
    description: str = ""
    domain: str = ""  # "arrangement", "sound_design", "mix", "harmony", "identity"
    status: str = "open"  # "open", "resolved", "abandoned", "stale"
    priority: float = 0.5
    created_at_ms: int = 0
    last_touched_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_stale(self) -> bool:
        """A thread is stale if untouched for >30 minutes."""
        now = int(time.time() * 1000)
        return (now - self.last_touched_ms) > 30 * 60 * 1000 if self.last_touched_ms else False


@dataclass
class TurnResolution:
    """What happened in a single creative turn."""

    turn_id: str = ""
    request_text: str = ""
    outcome: str = ""  # "accepted", "rejected", "modified", "undone"
    move_applied: str = ""
    identity_effect: str = ""
    user_sentiment: str = ""  # "loved", "liked", "neutral", "disliked", "hated"
    timestamp_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionStory:
    """The narrative of the current session."""

    song_id: str = ""
    identity_summary: str = ""
    what_changed_last: str = ""
    what_still_feels_open: list[str] = field(default_factory=list)
    threads: list[CreativeThread] = field(default_factory=list)
    turns: list[TurnResolution] = field(default_factory=list)
    mood_arc: list[str] = field(default_factory=list)  # sequence of moods

    def to_dict(self) -> dict:
        return {
            "song_id": self.song_id,
            "identity_summary": self.identity_summary,
            "what_changed_last": self.what_changed_last,
            "what_still_feels_open": self.what_still_feels_open,
            "threads": [t.to_dict() for t in self.threads if t.status == "open"],
            "recent_turns": [t.to_dict() for t in self.turns[-5:]],
            "mood_arc": self.mood_arc[-10:],
            "total_turns": len(self.turns),
        }


@dataclass
class TasteIdentityRanking:
    """Result of ranking candidates with separated taste and identity."""

    candidate_id: str = ""
    taste_score: float = 0.0
    identity_score: float = 0.0
    composite_score: float = 0.0
    taste_explanation: str = ""
    identity_explanation: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
