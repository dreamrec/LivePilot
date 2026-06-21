"""Tests for plan-aware download gating (SpliceGRPCClient.decide_download).

This is the single critical path that decides whether a sample download
proceeds. Three distinct branches must be locked down:

  1. Free samples → bypass everything (IsPremium=False or Price=0).
  2. Ableton Live plan → daily quota, NEVER credit floor.
  3. Credit-metered plans → credit floor applies.

Regression trap: if we ever let "subscribed" plan_kind=SOUNDS_PLUS
silently land on the ABLETON_LIVE branch, we'll drain the user's credits
without warning. Test explicitly.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from mcp_server.splice_client.client import SpliceGRPCClient, CREDIT_HARD_FLOOR
from mcp_server.splice_client.models import (
    PlanKind,
    SpliceCredits,
    SpliceSample,
)
from mcp_server.splice_client.quota import DailyQuotaTracker


class _FakeClient(SpliceGRPCClient):
    """Plan-aware fake that skips gRPC entirely."""

    def __init__(self, plan, credits_value, tmp_path):
        tracker = DailyQuotaTracker(
            path=os.path.join(tmp_path, "quota.json"),
            daily_limit=100,
            warn_threshold=90,
        )
        super().__init__(quota_tracker=tracker)
        self.connected = True
        self._plan = plan
        self._credits_value = credits_value

    async def get_credits(self) -> SpliceCredits:
        creds = SpliceCredits(
            credits=self._credits_value,
            plan="whatever",
            plan_kind=self._plan,
        )
        self._cached_credits = creds
        return creds


# ── Free samples bypass every gate ─────────────────────────────────────


def test_free_sample_allowed_even_with_zero_credits(tmp_path):
    client = _FakeClient(PlanKind.UNKNOWN, credits_value=0, tmp_path=tmp_path)
    sample = SpliceSample(file_hash="h", is_premium=False, price=0)
    decision = asyncio.run(client.decide_download("h", sample=sample))
    assert decision.allowed
    assert decision.gating_mode == "free_sample"


def test_free_sample_allowed_on_free_plan(tmp_path):
    client = _FakeClient(PlanKind.FREE, credits_value=0, tmp_path=tmp_path)
    sample = SpliceSample(is_premium=True, price=0)  # price=0 overrides premium
    decision = asyncio.run(client.decide_download("h", sample=sample))
    assert decision.allowed
    assert decision.gating_mode == "free_sample"


# ── Ableton Live plan uses daily quota ────────────────────────────────


def test_ableton_plan_allows_download_under_quota(tmp_path):
    client = _FakeClient(PlanKind.ABLETON_LIVE, credits_value=80, tmp_path=tmp_path)
    decision = asyncio.run(client.decide_download("h"))
    assert decision.allowed
    assert decision.gating_mode == "daily_quota"
    assert decision.credits_remaining == 80


def test_ableton_plan_allows_even_when_credits_zero(tmp_path):
    """Critical: zero credits should NOT block the Ableton plan's sample path.

    This is the P0 bug the user reported — our CREDIT_HARD_FLOOR guard
    wrongly refused downloads they're entitled to under the daily quota.
    """
    client = _FakeClient(PlanKind.ABLETON_LIVE, credits_value=0, tmp_path=tmp_path)
    decision = asyncio.run(client.decide_download("h"))
    assert decision.allowed, (
        "Ableton Live plan must bypass credit floor — 0 credits is fine "
        "because sample downloads deplete the daily counter, not credits."
    )
    assert decision.gating_mode == "daily_quota"


def test_ableton_plan_blocks_at_daily_quota(tmp_path):
    client = _FakeClient(PlanKind.ABLETON_LIVE, credits_value=80, tmp_path=tmp_path)
    # Hammer the tracker to 100/100
    for _ in range(100):
        client._quota.record_download(f"h-{_}", "n.wav")
    decision = asyncio.run(client.decide_download("h"))
    assert not decision.allowed
    assert decision.gating_mode == "daily_quota"
    assert decision.quota_used >= 100
    assert "resets at utc midnight" in decision.reason.lower()


# ── Credit-metered plans ──────────────────────────────────────────────


def test_credit_metered_blocks_at_floor(tmp_path):
    """SOUNDS_PLUS user with credits at the floor must be refused."""
    client = _FakeClient(
        PlanKind.SOUNDS_PLUS,
        credits_value=CREDIT_HARD_FLOOR,
        tmp_path=tmp_path,
    )
    decision = asyncio.run(client.decide_download("h"))
    assert not decision.allowed
    assert decision.gating_mode == "credit_floor"


def test_credit_metered_allows_above_floor(tmp_path):
    client = _FakeClient(
        PlanKind.SOUNDS_PLUS,
        credits_value=CREDIT_HARD_FLOOR + 10,
        tmp_path=tmp_path,
    )
    decision = asyncio.run(client.decide_download("h"))
    assert decision.allowed
    assert decision.gating_mode == "credit_floor"


def test_unknown_plan_uses_credit_floor(tmp_path):
    """When plan is indeterminate, behave like credit-metered (safer default)."""
    client = _FakeClient(PlanKind.UNKNOWN, credits_value=1, tmp_path=tmp_path)
    decision = asyncio.run(client.decide_download("h"))
    assert not decision.allowed
    assert decision.gating_mode == "credit_floor"


# ── Disconnected state ────────────────────────────────────────────────


def test_disconnected_returns_blocked(tmp_path):
    client = _FakeClient(PlanKind.ABLETON_LIVE, credits_value=80, tmp_path=tmp_path)
    client.connected = False
    decision = asyncio.run(client.decide_download("h"))
    assert not decision.allowed
    assert decision.gating_mode == "blocked"
    assert decision.plan_kind == PlanKind.UNKNOWN


# ── DownloadDecision serialization ─────────────────────────────────────


def test_decision_dict_has_expected_shape(tmp_path):
    client = _FakeClient(PlanKind.ABLETON_LIVE, credits_value=80, tmp_path=tmp_path)
    decision = asyncio.run(client.decide_download("h"))
    d = decision.to_dict()
    required = {
        "allowed", "reason", "plan_kind", "gating_mode",
        "credits_remaining", "quota_used", "quota_remaining",
    }
    assert required <= set(d.keys())
