"""Smoke tests for the Splice gRPC client.

These are not end-to-end tests — they don't talk to the real Splice
desktop binary. They exercise the local wiring: credit-floor gate,
timeout plumbing, import-degradation graceful fallback, and port.conf
parsing. Missing these guards is how v1.10.5 ended up silently falling
back to SQL-only for two releases.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from unittest import mock

import pytest

from mcp_server.splice_client import client as splice_client
from mcp_server.splice_client.client import (
    SpliceGRPCClient,
    CREDIT_HARD_FLOOR,
    SEARCH_TIMEOUT,
    INFO_TIMEOUT,
    CREDITS_TIMEOUT,
)
from mcp_server.splice_client.models import SpliceCredits


# ── Credit floor ──────────────────────────────────────────────────────


class _FakeCreditsClient(SpliceGRPCClient):
    """Lets us set the credit balance without gRPC."""
    def __init__(self, credits: int):
        self._credits = credits
        self.connected = True  # skip real TLS/channel setup

    async def get_credits(self) -> SpliceCredits:
        return SpliceCredits(credits=self._credits, username="test", plan="core")


def test_credit_floor_blocks_when_balance_at_floor():
    """With exactly CREDIT_HARD_FLOOR credits remaining, can_afford returns False."""
    client = _FakeCreditsClient(credits=CREDIT_HARD_FLOOR)
    can, remaining = asyncio.run(client.can_afford(credits_needed=1, budget=10))
    assert can is False
    assert remaining == CREDIT_HARD_FLOOR


def test_credit_floor_blocks_when_draining_below():
    """Request that would drain below the floor is refused."""
    client = _FakeCreditsClient(credits=CREDIT_HARD_FLOOR + 2)  # 2 usable
    can, remaining = asyncio.run(client.can_afford(credits_needed=3, budget=10))
    assert can is False
    assert remaining == CREDIT_HARD_FLOOR + 2


def test_credit_floor_allows_safe_spend():
    """Request fitting inside budget and above floor passes."""
    client = _FakeCreditsClient(credits=50)
    can, remaining = asyncio.run(client.can_afford(credits_needed=3, budget=10))
    assert can is True
    assert remaining == 50


def test_credit_floor_respects_budget():
    """Budget still caps the spend even when balance is huge."""
    client = _FakeCreditsClient(credits=1000)
    can, remaining = asyncio.run(client.can_afford(credits_needed=20, budget=10))
    assert can is False


# ── Timeout constants ─────────────────────────────────────────────────


def test_timeouts_are_bounded():
    """Every per-call timeout must be a sane positive number.

    Without timeouts, a hung Splice process blocked the MCP event loop
    until gRPC's default (often infinite) deadline fired. This guards
    against accidentally removing or zeroing them.
    """
    for name, value in [
        ("SEARCH_TIMEOUT", SEARCH_TIMEOUT),
        ("INFO_TIMEOUT", INFO_TIMEOUT),
        ("CREDITS_TIMEOUT", CREDITS_TIMEOUT),
    ]:
        assert 0 < value <= 60, f"{name}={value} is out of reasonable bounds"


# ── Port.conf parsing ─────────────────────────────────────────────────


def _write_port_conf(content: str) -> str:
    """Write a temp port.conf file, return its directory (matching _SPLICE_APP_SUPPORT layout)."""
    tmpdir = tempfile.mkdtemp(prefix="livepilot-splice-")
    conf = os.path.join(tmpdir, "port.conf")
    with open(conf, "w") as f:
        f.write(content)
    return tmpdir


def _make_client_with_app_support(tmpdir: str) -> SpliceGRPCClient:
    """Create a client pointing at tmpdir for port.conf without running __init__ side effects."""
    with mock.patch.object(splice_client, "_SPLICE_APP_SUPPORT", tmpdir):
        c = SpliceGRPCClient.__new__(SpliceGRPCClient)  # skip __init__
        c.connected = False
        return c


def test_read_port_returns_none_if_missing():
    tmpdir = tempfile.mkdtemp(prefix="livepilot-noport-")
    c = _make_client_with_app_support(tmpdir)
    with mock.patch.object(splice_client, "_SPLICE_APP_SUPPORT", tmpdir):
        port = c._read_port()
    assert port is None


def test_read_port_parses_host_colon_port():
    tmpdir = _write_port_conf("127.0.0.1:56765\n")
    c = _make_client_with_app_support(tmpdir)
    with mock.patch.object(splice_client, "_SPLICE_APP_SUPPORT", tmpdir):
        port = c._read_port()
    assert port == 56765


def test_read_port_parses_bare_port():
    tmpdir = _write_port_conf("56765\n")
    c = _make_client_with_app_support(tmpdir)
    with mock.patch.object(splice_client, "_SPLICE_APP_SUPPORT", tmpdir):
        port = c._read_port()
    assert port == 56765


def test_read_port_tolerates_malformed():
    tmpdir = _write_port_conf("not-a-port\n")
    c = _make_client_with_app_support(tmpdir)
    with mock.patch.object(splice_client, "_SPLICE_APP_SUPPORT", tmpdir):
        port = c._read_port()
    # Must not crash — returns None when content cannot be parsed.
    assert port is None


# ── Graceful fallback when gRPC is missing ────────────────────────────


def test_client_degrades_gracefully_without_grpc():
    """If grpcio isn't importable, client methods must return sensible
    empty values instead of raising. This is the exact regression that
    silently shipped in v1.10.2–1.10.4 before v1.10.5 fixed it."""
    c = SpliceGRPCClient.__new__(SpliceGRPCClient)
    c.connected = False

    # All public methods should be safe to call when disconnected.
    assert asyncio.run(c.get_credits()).credits == 0
    # search_samples + get_sample_info return empty rather than raising
    result = asyncio.run(c.search_samples("anything"))
    assert result.samples == []
    assert asyncio.run(c.get_sample_info("abc")) is None
