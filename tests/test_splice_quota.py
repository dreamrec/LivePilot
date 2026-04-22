"""Tests for the daily sample download quota tracker.

The tracker is what makes the Ableton Live plan's 100/day ceiling
observable in code. Without it, the agent would happily hit the server
limit and get cryptic 4xx responses mid-flow. These tests lock down the
ceiling behavior, UTC midnight reset, and warn-threshold semantics.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from mcp_server.splice_client.quota import (
    DailyQuotaTracker,
    QuotaState,
    _today_utc,
    DEFAULT_DAILY_LIMIT,
    DEFAULT_WARN_THRESHOLD,
)


def _fresh_tracker(tmp_path, limit=DEFAULT_DAILY_LIMIT, warn=DEFAULT_WARN_THRESHOLD):
    """Build a tracker pointing at a temp ledger."""
    return DailyQuotaTracker(
        path=os.path.join(tmp_path, "quota.json"),
        daily_limit=limit,
        warn_threshold=warn,
    )


def test_tracker_initial_state_is_zero(tmp_path):
    t = _fresh_tracker(tmp_path)
    used, remaining = t.current()
    assert used == 0
    assert remaining == DEFAULT_DAILY_LIMIT


def test_record_download_increments(tmp_path):
    t = _fresh_tracker(tmp_path)
    result = t.record_download(file_hash="h1", filename="kick.wav")
    assert result["used_today"] == 1
    assert result["remaining_today"] == DEFAULT_DAILY_LIMIT - 1
    assert result["warning"] is None


def test_record_download_persists_across_instances(tmp_path):
    path = os.path.join(tmp_path, "quota.json")
    t1 = DailyQuotaTracker(path=path)
    t1.record_download("h1")
    t2 = DailyQuotaTracker(path=path)
    used, _ = t2.current()
    assert used == 1


def test_warn_threshold_triggers(tmp_path):
    """At 90/100, we get a warning but downloads still allowed."""
    t = _fresh_tracker(tmp_path, limit=100, warn=90)
    for _ in range(89):
        t.record_download("h", "n.wav")
    result = t.record_download("h", "n.wav")  # 90th
    assert result["used_today"] == 90
    assert result["warning"] is not None
    assert "daily quota" in result["warning"].lower()


def test_at_limit_marks_warning(tmp_path):
    """At 100/100, warning emphasizes reset timing."""
    t = _fresh_tracker(tmp_path, limit=10, warn=8)
    for _ in range(10):
        t.record_download("h", "n.wav")
    # 11th push still records but warn reflects at-limit status
    result = t.record_download("h", "n.wav")
    assert result["used_today"] == 11
    assert result["warning"] is not None
    assert "UTC midnight" in result["warning"]


def test_would_exceed_after_limit(tmp_path):
    t = _fresh_tracker(tmp_path, limit=5)
    for _ in range(5):
        t.record_download("h")
    assert t.would_exceed(additional=1)
    assert t.would_exceed(additional=100)


def test_would_exceed_below_limit(tmp_path):
    t = _fresh_tracker(tmp_path, limit=5)
    t.record_download("h")
    assert not t.would_exceed(additional=1)
    assert not t.would_exceed(additional=3)
    assert t.would_exceed(additional=5)


def test_summary_shape(tmp_path):
    t = _fresh_tracker(tmp_path, limit=100, warn=90)
    for _ in range(92):
        t.record_download("h")
    s = t.summary()
    assert s == {
        "used_today": 92,
        "remaining_today": 8,
        "daily_limit": 100,
        "warn_threshold": 90,
        "near_limit": True,
        "at_limit": False,
    }


def test_quota_state_prunes_old_days(tmp_path):
    """State keeps only the most recent 30 days of counters."""
    path = os.path.join(tmp_path, "quota.json")
    # Write 50 historical days manually
    state = QuotaState(
        counts={f"2025-01-{d:02d}": d for d in range(1, 32)},
    )
    state.counts["2025-02-01"] = 5
    state.counts["2025-02-02"] = 5
    state.counts["2025-02-03"] = 5
    with open(path, "w") as f:
        f.write(state.to_json())
    t = DailyQuotaTracker(path=path)
    # record_download triggers pruning
    t.record_download("h")
    with open(path) as f:
        raw = json.loads(f.read())
    assert len(raw["counts"]) <= 31  # 30 historical + today


def test_downloads_log_bounded(tmp_path):
    """Log trims to the last 200 entries."""
    t = _fresh_tracker(tmp_path)
    for i in range(250):
        t.record_download(f"hash-{i}", f"file{i}.wav")
    with open(t.path) as f:
        raw = json.loads(f.read())
    assert len(raw["downloads"]) == 200
    # Last entry must be the most recent
    assert raw["downloads"][-1]["file_hash"] == "hash-249"


def test_today_utc_format():
    """UTC day key is ISO-8601 YYYY-MM-DD."""
    today = _today_utc()
    assert len(today) == 10
    assert today[4] == "-" and today[7] == "-"


def test_missing_file_returns_empty_state(tmp_path):
    path = os.path.join(tmp_path, "missing.json")
    t = DailyQuotaTracker(path=path)
    used, rem = t.current()
    assert used == 0 and rem == DEFAULT_DAILY_LIMIT


def test_corrupt_file_returns_empty_state(tmp_path):
    path = os.path.join(tmp_path, "corrupt.json")
    with open(path, "w") as f:
        f.write("{not json}")
    t = DailyQuotaTracker(path=path)
    used, _ = t.current()
    assert used == 0


def test_non_object_json_returns_empty_state(tmp_path):
    path = os.path.join(tmp_path, "list.json")
    with open(path, "w") as f:
        f.write('["not", "an", "object"]')
    t = DailyQuotaTracker(path=path)
    used, _ = t.current()
    assert used == 0
