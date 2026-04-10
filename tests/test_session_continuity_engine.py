"""Unit tests for Session Continuity tracker — pure computation, no Ableton needed."""

import time

from mcp_server.session_continuity.tracker import (
    get_session_story,
    list_open_threads,
    open_thread,
    rank_by_taste_and_identity,
    record_turn_resolution,
    reset_story,
    resolve_thread,
    resume_last_intent,
)


def setup_function():
    """Reset state before each test."""
    reset_story()


# ── Turn recording ───────────────────────────────────────────────


def test_record_turn():
    """Recording a turn should track outcome and sentiment."""
    turn = record_turn_resolution(
        request_text="add reverb to vocals",
        outcome="accepted",
        move_applied="add_reverb",
        identity_effect="preserves",
        user_sentiment="liked",
    )
    assert turn.turn_id
    assert turn.request_text == "add reverb to vocals"
    assert turn.outcome == "accepted"
    assert turn.user_sentiment == "liked"
    assert turn.timestamp_ms > 0


def test_multiple_turns_tracked():
    """Multiple turns should accumulate."""
    record_turn_resolution("first action", "accepted")
    record_turn_resolution("second action", "rejected")
    record_turn_resolution("third action", "accepted")

    story = get_session_story()
    assert story.to_dict()["total_turns"] == 3


def test_mood_arc_from_sentiment():
    """Mood arc should reflect user sentiment."""
    record_turn_resolution("good one", "accepted", user_sentiment="loved")
    record_turn_resolution("bad one", "rejected", user_sentiment="hated")
    record_turn_resolution("meh", "accepted", user_sentiment="neutral")

    story = get_session_story()
    assert story.mood_arc == ["positive", "negative", "neutral"]


# ── Session story ────────────────────────────────────────────────


def test_session_story_includes_identity():
    """Story should include identity from song brain."""
    song_brain = {"identity_core": "Dark ambient textures with a pulsing sub-bass"}
    story = get_session_story(song_brain)
    assert story.identity_summary == "Dark ambient textures with a pulsing sub-bass"


def test_session_story_what_changed_last():
    """Story should report what changed last."""
    record_turn_resolution("add compression", "accepted")
    story = get_session_story()
    assert "compression" in story.what_changed_last.lower()


def test_session_story_empty():
    """Empty session should return valid story."""
    story = get_session_story()
    assert story.to_dict()["total_turns"] == 0
    assert story.identity_summary == ""


# ── Creative threads ─────────────────────────────────────────────


def test_open_thread():
    """Opening a thread should create a trackable thread."""
    thread = open_thread("Develop the chorus hook", domain="arrangement")
    assert thread.thread_id
    assert thread.status == "open"
    assert thread.description == "Develop the chorus hook"


def test_list_open_threads():
    """Should list only open, non-stale threads."""
    open_thread("Thread 1", domain="mix")
    open_thread("Thread 2", domain="arrangement")
    threads = list_open_threads()
    assert len(threads) == 2


def test_resolve_thread():
    """Resolved threads should be excluded from open list."""
    t = open_thread("Resolve me", domain="mix")
    resolve_thread(t.thread_id)
    threads = list_open_threads()
    assert len(threads) == 0


def test_stale_threads_excluded():
    """Threads untouched for >30 minutes should be excluded."""
    t = open_thread("Old thread", domain="mix")
    # Manually make it stale
    t.last_touched_ms = int(time.time() * 1000) - 31 * 60 * 1000
    threads = list_open_threads()
    assert len(threads) == 0


def test_resume_last_intent():
    """Should resume the most recent open thread."""
    t1 = open_thread("First idea", domain="arrangement")
    t2 = open_thread("Latest idea", domain="sound_design")
    # Ensure the second thread has a later timestamp
    t2.last_touched_ms = t1.last_touched_ms + 1000
    result = resume_last_intent()
    assert result["found"] is True
    assert "Latest idea" in result["description"]


def test_resume_last_intent_empty():
    """No open threads should report not found."""
    result = resume_last_intent()
    assert result["found"] is False


# ── Taste vs Identity ranking ────────────────────────────────────


def test_identity_weighted_more():
    """Identity should have stronger weight (0.65) than taste (0.35)."""
    candidates = [
        {"id": "safe", "novelty_level": 0.2, "identity_effect": "preserves"},
        {"id": "risky", "novelty_level": 0.9, "identity_effect": "resets"},
    ]
    rankings = rank_by_taste_and_identity(candidates)
    # preserves (identity=0.9) should outscore resets (identity=0.15)
    assert rankings[0].candidate_id == "safe"
    assert rankings[0].composite_score > rankings[1].composite_score


def test_ranking_returns_explanations():
    """Rankings should include taste and identity explanations."""
    candidates = [
        {"id": "test", "novelty_level": 0.5, "identity_effect": "evolves"},
    ]
    rankings = rank_by_taste_and_identity(candidates)
    assert len(rankings) == 1
    r = rankings[0]
    assert r.taste_explanation
    assert r.identity_explanation
    assert r.recommendation in ("recommended", "consider", "caution")


def test_ranking_empty_candidates():
    """Empty candidates should return empty rankings."""
    rankings = rank_by_taste_and_identity([])
    assert rankings == []


def test_ranking_sorted_by_composite():
    """Rankings should be sorted by composite score, descending."""
    candidates = [
        {"id": "a", "novelty_level": 0.3, "identity_effect": "preserves"},
        {"id": "b", "novelty_level": 0.5, "identity_effect": "evolves"},
        {"id": "c", "novelty_level": 0.9, "identity_effect": "resets"},
    ]
    rankings = rank_by_taste_and_identity(candidates)
    scores = [r.composite_score for r in rankings]
    assert scores == sorted(scores, reverse=True)
