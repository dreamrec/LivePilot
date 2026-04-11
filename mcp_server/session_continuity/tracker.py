"""Session Continuity tracker — pure computation + in-memory state.

Manages creative threads, turn resolutions, and session story.
Separates taste (cross-session) from identity (in-song) ranking.
"""

from __future__ import annotations

import hashlib
import time
from typing import Optional

from .models import (
    CreativeThread,
    SessionStory,
    TasteIdentityRanking,
    TurnResolution,
)


# ── In-memory state ───────────────────────────────────────────────

_story = SessionStory()
_threads: dict[str, CreativeThread] = {}
_turns: list[TurnResolution] = []
_project_store = None  # Optional PersistentProjectStore


def set_project_store(store) -> None:
    """Attach a persistent project store for flush-on-write."""
    global _project_store
    _project_store = store


def reset_story() -> None:
    """Reset session story (for testing)."""
    global _story, _threads, _turns, _project_store
    _story = SessionStory()
    _threads = {}
    _turns = []
    _project_store = None


# ── Session story ─────────────────────────────────────────────────


def get_session_story(
    song_brain: Optional[dict] = None,
) -> SessionStory:
    """Get the current session story with identity summary."""
    song_brain = song_brain or {}

    _story.identity_summary = song_brain.get("identity_core", "")
    _story.threads = [t for t in _threads.values() if t.status == "open"]
    _story.turns = _turns
    _story.what_still_feels_open = [
        t.description for t in _threads.values()
        if t.status == "open" and not t.is_stale
    ]

    if _turns:
        last = _turns[-1]
        _story.what_changed_last = f"{last.request_text} → {last.outcome}"

    return _story


def resume_last_intent() -> dict:
    """Resume the most recent unresolved creative intent."""
    open_threads = [
        t for t in _threads.values()
        if t.status == "open" and not t.is_stale
    ]

    if not open_threads:
        return {
            "found": False,
            "note": "No unresolved creative intents to resume",
        }

    # Sort by last touched (most recent first)
    open_threads.sort(key=lambda t: t.last_touched_ms, reverse=True)
    latest = open_threads[0]

    return {
        "found": True,
        "thread_id": latest.thread_id,
        "description": latest.description,
        "domain": latest.domain,
        "priority": latest.priority,
        "suggestion": f"Continue working on: {latest.description}",
    }


# ── Turn tracking ─────────────────────────────────────────────────


def record_turn_resolution(
    request_text: str,
    outcome: str = "accepted",
    move_applied: str = "",
    identity_effect: str = "",
    user_sentiment: str = "neutral",
) -> TurnResolution:
    """Record what happened in a creative turn."""
    now = int(time.time() * 1000)
    turn_id = hashlib.sha256(f"{request_text}_{now}".encode()).hexdigest()[:10]

    turn = TurnResolution(
        turn_id=turn_id,
        request_text=request_text,
        outcome=outcome,
        move_applied=move_applied,
        identity_effect=identity_effect,
        user_sentiment=user_sentiment,
        timestamp_ms=now,
    )
    _turns.append(turn)

    # Update mood arc
    if user_sentiment in ("loved", "liked"):
        _story.mood_arc.append("positive")
    elif user_sentiment in ("disliked", "hated"):
        _story.mood_arc.append("negative")
    else:
        _story.mood_arc.append("neutral")

    # Flush to persistent store
    if _project_store is not None:
        try:
            _project_store.save_turn(turn.to_dict())
        except Exception:
            pass

    return turn


# ── Creative threads ──────────────────────────────────────────────


def open_thread(description: str, domain: str = "", priority: float = 0.5) -> CreativeThread:
    """Open a new creative thread."""
    now = int(time.time() * 1000)
    thread_id = hashlib.sha256(f"{description}_{now}".encode()).hexdigest()[:10]

    thread = CreativeThread(
        thread_id=thread_id,
        description=description,
        domain=domain,
        status="open",
        priority=priority,
        created_at_ms=now,
        last_touched_ms=now,
    )
    _threads[thread_id] = thread

    # Flush to persistent store
    if _project_store is not None:
        try:
            _project_store.save_thread(thread.to_dict())
        except Exception:
            pass

    return thread


def resolve_thread(thread_id: str) -> Optional[CreativeThread]:
    """Mark a creative thread as resolved."""
    thread = _threads.get(thread_id)
    if thread:
        thread.status = "resolved"
        thread.last_touched_ms = int(time.time() * 1000)
        if _project_store is not None:
            try:
                _project_store.save_thread(thread.to_dict())
            except Exception:
                pass
    return thread


def list_open_threads() -> list[CreativeThread]:
    """List all open (non-stale) creative threads."""
    return [
        t for t in _threads.values()
        if t.status == "open" and not t.is_stale
    ]


# ── Taste vs Identity ranking ────────────────────────────────────


def rank_by_taste_and_identity(
    candidates: list[dict],
    taste_graph: Optional[dict] = None,
    song_brain: Optional[dict] = None,
) -> list[TasteIdentityRanking]:
    """Rank candidates with separated taste and identity scoring.

    Taste ranks options (cross-session preference).
    Identity constrains/shapes options (in-song).
    Identity has stronger weight inside a session.
    """
    taste_graph = taste_graph or {}
    song_brain = song_brain or {}
    results: list[TasteIdentityRanking] = []

    for candidate in candidates:
        cid = candidate.get("id", candidate.get("variant_id", ""))
        novelty = candidate.get("novelty_level", 0.5)
        identity_effect = candidate.get("identity_effect", "preserves")

        # Taste score — how well does this fit cross-session preferences?
        boldness_pref = taste_graph.get("transition_boldness", 0.5)
        taste_score = 1.0 - abs(novelty - boldness_pref) * 0.8
        taste_score = round(max(0.0, min(1.0, taste_score)), 3)

        # Identity score — does this serve the current song?
        identity_scores = {
            "preserves": 0.9,
            "evolves": 0.7,
            "contrasts": 0.45,
            "resets": 0.15,
        }
        identity_score = identity_scores.get(identity_effect, 0.5)

        # Sacred element penalty — penalize non-preserving candidates
        # that target sacred dimensions
        sacred = song_brain.get("sacred_elements", [])
        targets = candidate.get("targets_snapshot", {})
        sacred_penalty = sum(
            s.get("salience", 0.5) * 0.15
            for s in sacred
            if s.get("element_type") in targets and identity_effect != "preserves"
        )
        identity_score = max(0.0, identity_score - sacred_penalty)

        # Composite: identity weighted more heavily within a session
        composite = taste_score * 0.35 + identity_score * 0.65

        # Explanations
        taste_exp = (
            f"{'Good' if taste_score > 0.6 else 'Moderate' if taste_score > 0.3 else 'Poor'} "
            f"taste fit — novelty {novelty:.0%} vs preference {boldness_pref:.0%}"
        )
        identity_exp = (
            f"Identity effect: {identity_effect} — "
            f"{'safe for current song' if identity_score > 0.6 else 'risky for song identity'}"
        )

        results.append(TasteIdentityRanking(
            candidate_id=cid,
            taste_score=taste_score,
            identity_score=identity_score,
            composite_score=round(composite, 3),
            taste_explanation=taste_exp,
            identity_explanation=identity_exp,
            recommendation="recommended" if composite > 0.6 else (
                "consider" if composite > 0.4 else "caution"
            ),
        ))

    results.sort(key=lambda r: r.composite_score, reverse=True)
    return results
