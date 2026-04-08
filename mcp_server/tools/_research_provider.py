"""Research Provider Router — explicit provider ladder with mode-based routing.

Pure Python, zero I/O.  Determines which research providers to query based on
the research mode (targeted, deep, background_mining) and provider availability.

Design: spec at docs/specs/2026-04-08-phase2-4-roadmap.md, Round 3.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Optional


# ── Provider Definitions ────────────────────────────────────────────

@dataclass
class ResearchProvider:
    """A single research data source with cost and priority metadata."""

    name: str  # "session_evidence", "local_docs", "memory", etc.
    available: bool
    priority: int  # 1=highest
    cost: str  # "free", "low", "medium", "high"

    def to_dict(self) -> dict:
        return asdict(self)


PROVIDER_LADDER: list[ResearchProvider] = [
    ResearchProvider("session_evidence", True, 1, "free"),
    ResearchProvider("local_docs", True, 2, "free"),
    ResearchProvider("memory", True, 3, "free"),
    ResearchProvider("user_references", False, 4, "low"),
    ResearchProvider("structured_connectors", False, 5, "medium"),
    ResearchProvider("web", False, 6, "high"),
]

# Which providers each mode is allowed to use
_MODE_ALLOWED: dict[str, set[str]] = {
    "targeted": {"session_evidence", "local_docs", "memory"},
    "deep": {
        "session_evidence", "local_docs", "memory",
        "user_references", "structured_connectors", "web",
    },
    "background_mining": {"session_evidence", "memory"},
}

_VALID_MODES = set(_MODE_ALLOWED.keys())


# ── Provider Selection ──────────────────────────────────────────────

def get_available_providers(
    capability_state: Optional[dict] = None,
) -> list[ResearchProvider]:
    """Return providers that are currently available.

    capability_state: optional dict of provider_name -> bool overrides.
    """
    result: list[ResearchProvider] = []
    overrides = capability_state or {}

    for p in PROVIDER_LADDER:
        available = overrides.get(p.name, p.available)
        result.append(ResearchProvider(
            name=p.name,
            available=available,
            priority=p.priority,
            cost=p.cost,
        ))

    return result


def route_research(
    query: str,
    mode: str,
    providers: Optional[list[ResearchProvider]] = None,
) -> dict:
    """Determine which providers to query based on mode.

    Returns: {
        mode, query, providers_to_query: [provider dicts],
        skipped: [provider dicts with reason],
    }
    """
    if mode not in _VALID_MODES:
        return {
            "error": f"invalid mode {mode!r}, must be one of {sorted(_VALID_MODES)}",
        }

    if providers is None:
        providers = get_available_providers()

    allowed_names = _MODE_ALLOWED[mode]

    to_query: list[dict] = []
    skipped: list[dict] = []

    for p in sorted(providers, key=lambda x: x.priority):
        if p.name not in allowed_names:
            skipped.append({**p.to_dict(), "reason": f"not allowed in {mode} mode"})
        elif not p.available:
            skipped.append({**p.to_dict(), "reason": "provider not available"})
        else:
            to_query.append(p.to_dict())

    return {
        "mode": mode,
        "query": query,
        "providers_to_query": to_query,
        "skipped": skipped,
    }


# ── Research Outcome Feedback ───────────────────────────────────────

@dataclass
class ResearchOutcomeFeedback:
    """Track whether research results were actually useful."""

    research_id: str
    technique_card_id: str
    applied: bool
    move_kept: bool
    score: float  # 0-1

    def to_dict(self) -> dict:
        return asdict(self)


class ResearchFeedbackStore:
    """In-memory store for research effectiveness tracking."""

    def __init__(self) -> None:
        self._entries: list[ResearchOutcomeFeedback] = []

    def record(self, feedback: ResearchOutcomeFeedback) -> dict:
        """Record research feedback.  Returns summary."""
        self._entries.append(feedback)
        return {
            "recorded": feedback.to_dict(),
            "total_feedback": len(self._entries),
            "effectiveness": self._effectiveness(),
        }

    def _effectiveness(self) -> dict:
        """Compute aggregate effectiveness stats."""
        if not self._entries:
            return {"applied_rate": 0.0, "kept_rate": 0.0, "avg_score": 0.0, "count": 0}

        applied = sum(1 for e in self._entries if e.applied)
        kept = sum(1 for e in self._entries if e.move_kept)
        avg_score = sum(e.score for e in self._entries) / len(self._entries)

        return {
            "applied_rate": round(applied / len(self._entries), 3),
            "kept_rate": round(kept / len(self._entries), 3),
            "avg_score": round(avg_score, 3),
            "count": len(self._entries),
        }

    def get_effectiveness(self) -> dict:
        """Public access to effectiveness stats."""
        return self._effectiveness()

    def get_all(self) -> list[dict]:
        """Return all feedback entries."""
        return [e.to_dict() for e in self._entries]

    def to_dict(self) -> dict:
        return {
            "feedback": self.get_all(),
            "effectiveness": self._effectiveness(),
        }


def record_research_feedback(feedback: ResearchOutcomeFeedback) -> dict:
    """Standalone function to create a feedback record dict."""
    return {
        "feedback": feedback.to_dict(),
        "timestamp_ms": int(time.time() * 1000),
    }
