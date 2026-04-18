"""Session Continuity tracker — pure computation + in-memory state.

Manages creative threads, turn resolutions, and session story.
Separates taste (cross-session) from identity (in-song) ranking.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional

from .models import (
    CreativeThread,
    SessionStory,
    TasteIdentityRanking,
    TurnResolution,
)

logger = logging.getLogger(__name__)


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


def bind_project_store_from_session(session_info: dict) -> Optional[str]:
    """Bind a per-project persistent store and hydrate in-memory state.

    Computes a project fingerprint from ``session_info`` (tempo, time sig,
    song length, track/scene/return layout), opens the matching
    ``ProjectStore`` under ``~/.livepilot/projects/<hash>/``, and rehydrates
    the in-memory ``_threads`` and ``_turns`` from disk so that restarting
    the MCP server preserves the user's creative threads and turn history.

    Returns the project_id (12-char hash) on success, ``None`` on failure
    (so callers can log without aborting startup). If the hash hasn't
    changed since the last bind, this is a no-op — hot path is safe to
    call on every turn.

    Without this function, ``set_project_store()`` existed but nobody
    called it, meaning README's "return to a project with prior creative
    threads intact" was literally false — threads/turns were in-memory
    only and reset on every server restart.
    """
    global _threads, _turns, _project_store

    try:
        from ..persistence.project_store import ProjectStore, project_hash
    except Exception as exc:
        logger.debug("bind_project_store_from_session: import failed: %s", exc)
        return None

    try:
        new_id = project_hash(session_info or {})
    except Exception as exc:
        logger.debug("bind_project_store_from_session: hash failed: %s", exc)
        return None

    # Already bound to this project? Nothing to do.
    if _project_store is not None and getattr(_project_store, "project_id", None) == new_id:
        return new_id

    try:
        store = ProjectStore(new_id)
    except Exception as exc:
        logger.debug("bind_project_store_from_session: store open failed: %s", exc)
        return None

    # Hydrate in-memory threads + turns from the persisted store. We only
    # rebuild what the tracker keeps live — SessionStory is recomputed on
    # each get_session_story() call, so it doesn't need a direct restore.
    try:
        raw_threads = store.get_threads()
        raw_turns = store.get_turns()
    except Exception as exc:
        logger.debug("bind_project_store_from_session: read failed: %s", exc)
        raw_threads, raw_turns = [], []

    _threads = {
        t["thread_id"]: CreativeThread.from_dict(t)
        for t in raw_threads
        if isinstance(t, dict) and "thread_id" in t
    }
    _turns = [
        TurnResolution.from_dict(t)
        for t in raw_turns
        if isinstance(t, dict)
    ]
    _project_store = store
    logger.info(
        "session_continuity: bound project %s (%d threads, %d turns restored)",
        new_id, len(_threads), len(_turns),
    )
    return new_id


def ensure_project_store_bound(ctx) -> Optional[str]:
    """Lazy bind on first use — for tools called before lifespan could reach Ableton.

    ``ctx`` is a FastMCP Context; reads the ``ableton`` connection from
    ``ctx.lifespan_context`` and fetches session info to compute the project
    hash. Safe to call on every turn — if already bound to this project, it's
    a no-op. Returns the project_id or ``None`` on failure.
    """
    if _project_store is not None:
        return getattr(_project_store, "project_id", None)
    try:
        ableton = ctx.lifespan_context.get("ableton")
        if ableton is None:
            return None
        info = ableton.send_command("get_session_info")
        if isinstance(info, dict) and not info.get("error"):
            return bind_project_store_from_session(info)
    except Exception as exc:
        logger.debug("ensure_project_store_bound: %s", exc)
    return None


# ── Session story ─────────────────────────────────────────────────


def get_session_story(
    song_brain: Optional[dict] = None,
) -> SessionStory:
    """Get the current session story with identity summary.

    BUG-B16: now also populates song_brain_id from the passed brain so
    callers can tell which brain generated the identity_summary.
    Previously the field was empty and users got a half-populated
    response that read as "something's wrong" even though the partial
    data was correct for a fresh session.
    """
    song_brain = song_brain or {}

    _story.identity_summary = song_brain.get("identity_core", "")
    _story.song_brain_id = str(song_brain.get("brain_id", "") or "")
    # Carry song_id through when present on the brain — fresh sessions
    # leave this empty, which is documented below.
    if not _story.song_id and song_brain.get("song_id"):
        _story.song_id = str(song_brain.get("song_id"))

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
        except Exception as exc:
            logger.debug("record_turn_resolution failed: %s", exc)
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
        except Exception as exc:
            logger.debug("open_thread failed: %s", exc)
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
            except Exception as exc:
                logger.debug("resolve_thread failed: %s", exc)
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
        # Routed through the canonical accessor so dimension_weights.transition_boldness
        # is honored. Previously read the top-level key directly and always got 0.5.
        from ..memory.taste_accessors import get_dimension_pref
        boldness_pref = get_dimension_pref(taste_graph, "transition_boldness", default=0.5)
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
