"""Tests for M4LBridge lifecycle and MidiToolCache heartbeat/request correlation.

Covers:
  - LIVE#1 (P2): M4LBridge.close() is idempotent and releases the UDP socket
  - LIVE#1 (P2): atexit handler is registered at bridge construction
  - P2-4: MidiToolCache separates _request_time from _last_seen so that a
    mark_ready() heartbeat cannot resurrect an expired request payload
"""

from __future__ import annotations

import atexit
import socket
import time
import unittest.mock as mock

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.m4l_bridge import M4LBridge, MidiToolCache, SpectralCache, SpectralReceiver


# ── LIVE#1 tests — bridge close() idempotency and socket release ─────────────


def test_bridge_close_is_idempotent():
    """Calling close() twice must not raise and must leave _closed=True."""
    cache = SpectralCache()
    bridge = M4LBridge(cache)

    bridge.close()
    assert bridge._closed is True

    # Second call — must not raise (e.g. from double socket.close())
    bridge.close()
    assert bridge._closed is True


def test_bridge_close_sets_closed_flag():
    """After close(), _closed must be True."""
    cache = SpectralCache()
    bridge = M4LBridge(cache)
    assert bridge._closed is False
    bridge.close()
    assert bridge._closed is True


def test_bridge_close_closes_socket():
    """close() must call _sock.close() exactly once, even if called twice."""
    cache = SpectralCache()
    bridge = M4LBridge(cache)

    mock_sock = mock.MagicMock()
    bridge._sock = mock_sock

    bridge.close()
    mock_sock.close.assert_called_once()

    # Second close — must NOT call sock.close() again (idempotent guard)
    bridge.close()
    mock_sock.close.assert_called_once()  # still once, not twice


def test_bridge_close_tolerates_oserror():
    """If _sock.close() raises OSError (already closed fd), close() absorbs it."""
    cache = SpectralCache()
    bridge = M4LBridge(cache)

    mock_sock = mock.MagicMock()
    mock_sock.close.side_effect = OSError("bad file descriptor")
    bridge._sock = mock_sock

    # Must not propagate the OSError
    bridge.close()
    assert bridge._closed is True


def test_bridge_atexit_registered_on_construction():
    """M4LBridge registers close() via atexit at construction time.

    We intercept atexit.register to verify the call was made with
    bridge.close as the callable (not a lambda), so the atexit handler
    actually holds a reference to the right method.
    """
    registered_calls: list[tuple] = []
    original_register = atexit.register

    def mock_register(fn, *args, **kwargs):
        registered_calls.append((fn, args, kwargs))
        return original_register(fn, *args, **kwargs)

    with mock.patch("atexit.register", side_effect=mock_register):
        cache = SpectralCache()
        bridge = M4LBridge(cache)

    # At least one registration must be bridge.close
    close_registrations = [call for call in registered_calls if call[0] == bridge.close]
    assert close_registrations, (
        "M4LBridge.__init__ did not register bridge.close via atexit.register. "
        "An orphaned process will hold UDP 9880 until the OS reclaims it."
    )

    # Clean up — the bridge was already registered via the real atexit, close it
    bridge.close()


def test_bridge_close_before_socket_created_does_not_raise():
    """If the socket creation is patched away (simulating a construction
    failure scenario), close() must still be callable without raising."""
    cache = SpectralCache()

    with mock.patch("socket.socket") as mock_sock_cls:
        mock_sock_instance = mock.MagicMock()
        mock_sock_cls.return_value = mock_sock_instance
        bridge = M4LBridge(cache)

    bridge.close()
    assert bridge._closed is True


# ── P2-4 tests — MidiToolCache heartbeat/request timestamp separation ─────────


def test_miditool_cache_request_time_separate_from_last_seen():
    """set_request() must stamp _request_time independently of _last_seen.

    After set_request(), _request_time and _last_seen should both be set.
    After mark_ready() (a heartbeat), _last_seen advances but _request_time
    must NOT change — so the request payload's staleness is still measured
    against the original request timestamp, not the heartbeat.
    """
    cache = MidiToolCache(max_age=5.0)

    ctx = {"grid": 1.0}
    notes = [{"pitch": 60}]
    cache.set_request(ctx, notes)

    request_time_after_set = cache._request_time
    last_seen_after_set = cache._last_seen
    assert request_time_after_set > 0.0
    assert last_seen_after_set > 0.0

    # Simulate a small delay then a heartbeat
    time.sleep(0.05)
    cache.mark_ready()

    # _last_seen advanced (heartbeat bumped it)
    assert cache._last_seen > last_seen_after_set

    # _request_time must NOT have changed — heartbeat must not reset it
    assert cache._request_time == request_time_after_set, (
        "mark_ready() updated _request_time, meaning a heartbeat can resurrect "
        "an expired request payload. _request_time must only be set by set_request()."
    )


def test_miditool_heartbeat_does_not_resurrect_expired_request():
    """A mark_ready() ping after request expiry must not make get_last_context
    return the stale context.

    This is the core P2-4 scenario: the request ages out (max_age=0 so it
    expires immediately), then a heartbeat arrives. Without a separate
    _request_time, the heartbeat would reset the staleness clock and
    get_last_context would return the stale payload as if it were fresh.
    With the fix, staleness is measured against _request_time only.
    """
    # max_age=0 means the request expires immediately after set_request()
    cache = MidiToolCache(max_age=0.0)

    ctx = {"grid": 1.0}
    notes = [{"pitch": 60}]
    cache.set_request(ctx, notes)

    # Backdate the request instead of sleeping. Expiry is `age > max_age`, so
    # with max_age=0 the monotonic clock must STRICTLY advance — and Windows'
    # time.monotonic() ticks at ~15.6 ms, so a 10 ms sleep can leave age
    # exactly 0.0 and the payload reads as fresh. That flaked the Windows CI
    # leg on 2026-07-31 (passed on macOS/Linux, failed intermittently on
    # Windows). Controlling the timestamp makes the test deterministic
    # everywhere and removes the sleep from the suite's runtime.
    cache._request_time -= 1.0

    # Confirm the request has expired
    assert cache.get_last_context() is None, (
        "Request payload should be expired (max_age=0) but get_last_context returned a value."
    )
    assert cache.get_last_notes() is None, (
        "Request payload should be expired (max_age=0) but get_last_notes returned a value."
    )

    # Now fire a heartbeat — must NOT resurrect the expired payload
    cache.mark_ready()

    assert cache.get_last_context() is None, (
        "mark_ready() heartbeat resurrected an expired get_last_context payload. "
        "P2-4 regression: _last_seen is being used as the request staleness clock."
    )
    assert cache.get_last_notes() is None, (
        "mark_ready() heartbeat resurrected an expired get_last_notes payload. "
        "P2-4 regression: _last_seen is being used as the request staleness clock."
    )


def test_miditool_heartbeat_keeps_is_connected_alive():
    """mark_ready() must still keep is_connected True even after this fix.

    The heartbeat's purpose is to maintain the is_connected signal;
    separating _request_time from _last_seen must not break that.
    """
    cache = MidiToolCache(max_age=5.0)
    assert cache.is_connected is False  # no data yet

    cache.mark_ready()
    assert cache.is_connected is True


def test_miditool_fresh_request_still_readable():
    """A fresh set_request() payload must still be readable via get_last_context
    and get_last_notes (the fix must not break the happy path).
    """
    cache = MidiToolCache(max_age=5.0)

    ctx = {"grid": 2.0, "scale": "major"}
    notes = [{"pitch": 64, "velocity": 0.8}]
    cache.set_request(ctx, notes)

    result_ctx = cache.get_last_context()
    result_notes = cache.get_last_notes()

    assert result_ctx is not None
    assert result_ctx == ctx
    assert result_notes is not None
    assert result_notes == notes


def test_miditool_request_time_not_updated_by_mark_ready():
    """Verify _request_time field exists and is untouched by mark_ready()."""
    cache = MidiToolCache(max_age=5.0)

    # Before any request, _request_time should be 0.0 (default)
    assert hasattr(cache, "_request_time"), (
        "MidiToolCache has no _request_time attribute — P2-4 fix not applied."
    )
    assert cache._request_time == 0.0

    cache.mark_ready()
    # Still 0.0 — mark_ready must not touch _request_time
    assert cache._request_time == 0.0, (
        "mark_ready() modified _request_time. Only set_request() should do that."
    )

    # After set_request, _request_time must be set
    cache.set_request({"grid": 1.0}, [])
    assert cache._request_time > 0.0

    # Backdate rather than sleep. This is not cosmetic: if the clock does not
    # advance (Windows monotonic ticks at ~15.6 ms, swallowing a 10 ms sleep),
    # then a BUGGY mark_ready() that did reset _request_time to "now" would
    # still compare equal to t1 and the assertion would pass spuriously — the
    # guard silently stops guarding. Backdating guarantees any reset is
    # detectable.
    cache._request_time -= 1.0
    t1 = cache._request_time

    # Another heartbeat must not change _request_time
    cache.mark_ready()
    assert cache._request_time == t1, (
        "mark_ready() updated _request_time after set_request(). "
        "Heartbeat must not reset the request staleness clock."
    )
