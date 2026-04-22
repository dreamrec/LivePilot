"""Tests for the Splice plan classifier and the two-pocket subscription model.

The classifier is the gate between our old credit-floor model (which
assumed every download costs credits) and the corrected model where the
Ableton Live plan uses a separate daily quota. These tests lock down the
contract so a future refactor can't silently fall back to "subscribed →
credit floor", which would re-introduce the bug the user reported on
2026-04-22.
"""

from __future__ import annotations

import pytest

from mcp_server.splice_client.models import (
    PlanKind,
    SpliceCredits,
    SpliceSample,
    classify_plan,
)


# ── Plan classifier ───────────────────────────────────────────────────


def test_classify_plan_features_ableton_unmetered_wins():
    """Feature flag takes precedence over any other signal."""
    plan = classify_plan(
        sounds_status="subscribed",
        sounds_plan=0,
        features={"ableton_unmetered": True},
    )
    assert plan == PlanKind.ABLETON_LIVE


def test_classify_plan_features_ableton_live_plan_flag():
    plan = classify_plan(
        sounds_status="anything",
        sounds_plan=0,
        features={"ableton_live_plan": True},
    )
    assert plan == PlanKind.ABLETON_LIVE


def test_classify_plan_features_generic_unmetered():
    plan = classify_plan(
        sounds_status="subscribed",
        sounds_plan=0,
        features={"unmetered_downloads": True},
    )
    assert plan == PlanKind.ABLETON_LIVE


def test_classify_plan_features_creator_plus():
    plan = classify_plan(
        sounds_status="subscribed",
        sounds_plan=0,
        features={"creator_plus": True},
    )
    assert plan == PlanKind.CREATOR_PLUS


def test_classify_plan_numeric_ids():
    """Numeric plan IDs classify without feature flags."""
    assert classify_plan("", 12, {}) == PlanKind.ABLETON_LIVE
    assert classify_plan("", 11, {}) == PlanKind.CREATOR_PLUS
    assert classify_plan("", 2, {}) == PlanKind.CREATOR
    assert classify_plan("", 0, {}) == PlanKind.FREE


def test_classify_plan_string_heuristics():
    """Free-form plan strings — last-resort parsing."""
    assert classify_plan("Ableton Live Plan", 999, {}) == PlanKind.ABLETON_LIVE
    assert classify_plan("Creator Plus", 999, {}) == PlanKind.CREATOR_PLUS
    assert classify_plan("Creator", 999, {}) == PlanKind.CREATOR
    assert classify_plan("free", 999, {}) == PlanKind.FREE
    assert classify_plan("trial", 999, {}) == PlanKind.FREE


def test_classify_plan_generic_subscribed_is_sounds_plus():
    """Critical: 'subscribed' alone MUST NOT classify as ABLETON_LIVE.

    Reason: the user reported 2026-04-22 that their live SoundsStatus
    returns the generic string "subscribed". If we wrongly classified that
    as the Ableton plan, we'd bypass the credit floor for Creator/Sounds+
    users and drain their monthly allotment. The safest default is
    SOUNDS_PLUS (credit-metered).
    """
    plan = classify_plan("subscribed", 0, {})
    assert plan == PlanKind.SOUNDS_PLUS
    assert not plan.has_daily_sample_quota


def test_classify_plan_empty_returns_free():
    plan = classify_plan("", 0, {})
    assert plan == PlanKind.FREE


def test_classify_plan_unknown_string_is_unknown():
    plan = classify_plan("weird-internal-name", 999, None)
    assert plan == PlanKind.UNKNOWN


# ── Plan properties ───────────────────────────────────────────────────


def test_has_daily_sample_quota_only_ableton_live():
    """Only ABLETON_LIVE gets the daily-quota flag. Everyone else uses credits."""
    assert PlanKind.ABLETON_LIVE.has_daily_sample_quota
    for other in (
        PlanKind.SOUNDS_PLUS,
        PlanKind.CREATOR,
        PlanKind.CREATOR_PLUS,
        PlanKind.FREE,
        PlanKind.UNKNOWN,
    ):
        assert not other.has_daily_sample_quota, other


def test_is_subscribed_excludes_free_and_unknown():
    assert PlanKind.ABLETON_LIVE.is_subscribed
    assert PlanKind.SOUNDS_PLUS.is_subscribed
    assert PlanKind.CREATOR.is_subscribed
    assert PlanKind.CREATOR_PLUS.is_subscribed
    assert not PlanKind.FREE.is_subscribed
    assert not PlanKind.UNKNOWN.is_subscribed


# ── SpliceCredits serialization ───────────────────────────────────────


def test_credits_to_dict_carries_plan_kind():
    credits = SpliceCredits(
        credits=80,
        username="user-1367453956",
        plan="subscribed",
        sounds_plan_id=12,
        features={"ableton_unmetered": True},
        plan_kind=PlanKind.ABLETON_LIVE,
        user_uuid="abc-123",
    )
    d = credits.to_dict()
    assert d["credits"] == 80
    assert d["plan_kind"] == "ableton_live"
    assert d["sounds_plan_id"] == 12
    assert d["features"] == {"ableton_unmetered": True}
    assert d["user_uuid"] == "abc-123"


# ── Free-sample detection ─────────────────────────────────────────────


def test_sample_is_free_when_not_premium():
    sample = SpliceSample(is_premium=False, price=100)
    assert sample.is_free


def test_sample_is_free_when_price_zero():
    sample = SpliceSample(is_premium=True, price=0)
    assert sample.is_free


def test_sample_is_paid_when_premium_and_priced():
    sample = SpliceSample(is_premium=True, price=1)
    assert not sample.is_free


def test_sample_to_dict_includes_is_free_and_price():
    sample = SpliceSample(
        file_hash="abc",
        filename="kick.wav",
        is_premium=True,
        price=1,
    )
    d = sample.to_dict()
    assert d["is_premium"] is True
    assert d["price"] == 1
    assert d["is_free"] is False
