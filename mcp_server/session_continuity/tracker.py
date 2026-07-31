"""Session Continuity tracker — pure computation + in-memory state.

Manages creative threads, turn resolutions, and session story.
Separates taste (cross-session) from identity (in-song) ranking.
"""

from __future__ import annotations

import copy
import hashlib
import logging
import threading
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
#
# _threads/_turns/_story/_project_store are mutated from both threadpooled
# sync tools (the session_continuity tool surface) and callers on the event
# loop (wonder_mode / preview_studio commit paths, the lifespan bind). The
# highest-risk interleaving: bind_project_store_from_session's merge reads
# _threads/_turns, merges with disk, then REASSIGNS both — an open_thread /
# record_turn_resolution landing between the read and the swap was silently
# discarded. One module-level lock (mirrors preview_studio/engine.py's
# _preview_sets_lock) held across each logical operation — the whole
# merge-and-swap, or an append + its store flush — closes that window.
#
# Re-entrancy contract: no function below calls another locked function
# while holding _state_lock. ensure_project_store_bound() releases the lock
# before delegating to bind_project_store_from_session() (which re-acquires
# it), so the lock can stay a plain Lock, not an RLock.

_story = SessionStory()
_threads: dict[str, CreativeThread] = {}
_turns: list[TurnResolution] = []
_project_store = None  # Optional PersistentProjectStore
_state_lock = threading.Lock()


def set_project_store(store) -> None:
    """Attach a persistent project store for flush-on-write."""
    global _project_store
    with _state_lock:
        _project_store = store


def reset_story() -> None:
    """Reset session story (for testing)."""
    global _story, _threads, _turns, _project_store
    with _state_lock:
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

    # The whole check → open → read → merge → swap → flush sequence runs
    # under the state lock so a concurrent open_thread()/record_turn_
    # resolution() can't land between the merge read and the reassignment
    # (it would be silently discarded by the swap). Store open/read/flush
    # are small JSON files and bind fires ~once per project, so the hold
    # time is acceptable.
    with _state_lock:
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

        # MERGE, don't overwrite. The whole reason a lazy/late bind exists is the
        # startup bind couldn't reach Ableton — during that window the tracker
        # accepted open_thread()/record_turn_resolution() with no store attached,
        # so those entries live ONLY in _threads/_turns and were never flushed. A
        # naive reassignment of _threads/_turns from disk silently discards them
        # (data loss). Instead: disk is the truth for anything it already holds
        # (id-keyed), and any in-memory entry whose id is absent on disk is an
        # unpersisted survivor we keep AND flush so the next bind sees it on disk.
        disk_threads = {
            t["thread_id"]: CreativeThread.from_dict(t)
            for t in raw_threads
            if isinstance(t, dict) and "thread_id" in t
        }
        unflushed_threads = [
            thread for tid, thread in _threads.items()
            if tid and tid not in disk_threads
        ]
        merged_threads = dict(disk_threads)
        for thread in unflushed_threads:
            merged_threads[thread.thread_id] = thread

        disk_turn_ids = {
            t["turn_id"] for t in raw_turns
            if isinstance(t, dict) and t.get("turn_id")
        }
        disk_turns = [
            TurnResolution.from_dict(t)
            for t in raw_turns
            if isinstance(t, dict)
        ]
        # Turns are append-only history: keep disk order, then append any
        # in-memory turn whose id isn't already on disk (preserve insertion order).
        unflushed_turns = [
            turn for turn in _turns
            if turn.turn_id and turn.turn_id not in disk_turn_ids
        ]
        merged_turns = disk_turns + unflushed_turns

        _threads = merged_threads
        _turns = merged_turns
        _project_store = store

        # Persist the survivors now that a store is attached. We do this AFTER
        # binding _project_store so a failure here doesn't leave the survivors
        # invisible — they're already live in memory; this only writes them
        # through to disk so a future restart/rebind keeps them. Flushing while
        # still holding the lock keeps a concurrent writer from double-flushing
        # the same entry through the freshly-bound store.
        for thread in unflushed_threads:
            try:
                store.save_thread(thread.to_dict())
            except Exception as exc:
                logger.debug("bind_project_store_from_session: thread flush failed: %s", exc)
        for turn in unflushed_turns:
            try:
                store.save_turn(turn.to_dict())
            except Exception as exc:
                logger.debug("bind_project_store_from_session: turn flush failed: %s", exc)

        thread_count, turn_count = len(_threads), len(_turns)

    logger.info(
        "session_continuity: bound project %s "
        "(%d threads, %d turns; %d threads + %d turns merged from memory)",
        new_id, thread_count, turn_count,
        len(unflushed_threads), len(unflushed_turns),
    )
    return new_id


def ensure_project_store_bound(ctx) -> Optional[str]:
    """Lazy bind on first use — for tools called before lifespan could reach Ableton.

    ``ctx`` is a FastMCP Context; reads the ``ableton`` connection from
    ``ctx.lifespan_context`` and fetches session info to compute the project
    hash. Safe to call on every turn — if already bound to this project, it's
    a no-op. Returns the project_id or ``None`` on failure.
    """
    # Fast-path read under the lock, then RELEASE before delegating to
    # bind_project_store_from_session (which re-acquires it) — holding it
    # across the call would deadlock the plain (non-reentrant) _state_lock,
    # and across send_command would serialize unrelated tools behind TCP I/O.
    # Two racing callers may both reach bind; its own locked already-bound
    # check makes the loser a no-op.
    with _state_lock:
        store = _project_store
    if store is not None:
        return getattr(store, "project_id", None)
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

    Returns an isolated snapshot, not the shared module-level singleton.
    ``_story`` is one process-wide object reused by every call (these
    tools run threadpooled — see the module comment). A caller that took
    the raw object would be racing every other in-flight call: a second
    caller could overwrite identity_summary/song_brain_id/threads/turns
    on the same object before the first caller serializes it (its own
    ``to_dict()`` runs after this function — and this lock — returns).
    ``_story.threads``/``.turns`` are also freshly-built lists of
    CreativeThread/TurnResolution objects aliased from ``_threads``, which
    ``resolve_thread()`` mutates in place — a shallow copy of ``_story``
    would still leak that mutation into an already-returned snapshot, so
    this deep-copies while still holding the lock.
    """
    song_brain = song_brain or {}

    with _state_lock:
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

        return copy.deepcopy(_story)


def resume_last_intent() -> dict:
    """Resume the most recent unresolved creative intent."""
    with _state_lock:
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
    # Append + flush under one lock hold: a bind merging concurrently must
    # see either "not appended yet" (its merge skips it, we append to the
    # merged list after) or "appended AND flushed" (its merge takes the disk
    # copy) — never the half-state where it re-flushes what we're flushing.
    with _state_lock:
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
    with _state_lock:
        _threads[thread_id] = thread

        # Flush to persistent store
        if _project_store is not None:
            try:
                _project_store.save_thread(thread.to_dict())
            except Exception as exc:
                logger.debug("open_thread failed: %s", exc)
    return thread


def resolve_thread(thread_id: str) -> Optional[CreativeThread]:
    """Mark a creative thread as resolved.

    Returns a copy, not the object stored in ``_threads`` — same reasoning
    as get_session_story(): the stored object is one this module mutates
    in place (here and via any future resolve_thread on the same id), so
    handing back the live reference would let a later mutation bleed into
    a caller that hasn't finished using the value it already got back.
    """
    with _state_lock:
        thread = _threads.get(thread_id)
        if thread:
            thread.status = "resolved"
            thread.last_touched_ms = int(time.time() * 1000)
            if _project_store is not None:
                try:
                    _project_store.save_thread(thread.to_dict())
                except Exception as exc:
                    logger.debug("resolve_thread failed: %s", exc)
            return copy.deepcopy(thread)
        return thread


def list_open_threads() -> list[CreativeThread]:
    """List all open (non-stale) creative threads."""
    with _state_lock:
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
