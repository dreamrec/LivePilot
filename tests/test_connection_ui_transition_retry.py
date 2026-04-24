"""v1.20.2 Race-condition fix: retry once on "Connection closed by
Ableton" errors triggered by UI transitions (e.g., Cmd+N opens a new
live set and briefly interrupts the command socket).

Pre-fix: the v1.20 live-test campaign observed this error 3× in ~30
minutes — reliably after each ``Cmd+N`` keystroke followed by an
immediate ``set_tempo`` call. The Remote Script's socket receive
returned empty bytes; send_command raised without retry.

Fix: when a command fails with ``Connection closed by Ableton``,
reconnect and retry ONCE after a 400ms backoff. Idempotent mutations
(set_tempo, set_track_volume) tolerate the rare double-apply; strict
callers can layer their own read-first-then-write pattern if they
care. The retry is capped at one attempt — further failures raise
and the caller learns there's a real problem beyond a UI transition.

Campaign source: ~/Desktop/DREAM AI/demo Project/REPORT.md
§"Reproducible race condition".
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_connection():
    """Build a connection object but avoid actually opening a socket."""
    from mcp_server.connection import AbletonConnection
    conn = AbletonConnection(host="127.0.0.1", port=9878)
    return conn


class TestUITransitionRetry:
    def test_retry_once_on_connection_closed_during_transition(self):
        """When _send_raw raises 'Connection closed by Ableton', the
        outer send_command should disconnect, sleep briefly, reconnect,
        and try the command once more. If the retry succeeds, return
        normally."""
        from mcp_server.connection import AbletonConnection, AbletonConnectionError
        conn = AbletonConnection(host="127.0.0.1", port=9878)

        # Simulate: initial connection exists, first _send_raw fails with
        # "Connection closed by Ableton" (send_completed=True), second
        # _send_raw succeeds.
        success_response = {"ok": True, "result": {"tempo": 120}}

        def fake_send_raw(command, recv_timeout=None):
            if fake_send_raw.call_count == 0:
                fake_send_raw.call_count += 1
                err = AbletonConnectionError("Connection closed by Ableton")
                err._send_completed = True
                raise err
            fake_send_raw.call_count += 1
            return success_response
        fake_send_raw.call_count = 0

        with patch.object(conn, "_send_raw", side_effect=fake_send_raw):
            with patch.object(conn, "is_connected", return_value=True):
                with patch.object(conn, "disconnect") as disc:
                    with patch.object(conn, "connect") as conn_mock:
                        with patch("mcp_server.connection.time.sleep"):
                            result = conn.send_command("set_tempo", {"tempo": 120})

        assert result == {"tempo": 120}
        assert fake_send_raw.call_count == 2, (
            f"expected exactly 1 retry (2 total calls), got {fake_send_raw.call_count}"
        )
        # Retry path should have disconnected + reconnected once
        assert disc.called
        assert conn_mock.called

    def test_no_retry_on_timeout(self):
        """Timeout errors are NOT retried — Ableton may have processed
        the command; duplicate mutation risk."""
        from mcp_server.connection import AbletonConnection, AbletonConnectionError
        conn = AbletonConnection(host="127.0.0.1", port=9878)

        def fake_send_raw(command, recv_timeout=None):
            fake_send_raw.call_count += 1
            err = AbletonConnectionError("Timeout waiting for response from Ableton (5s)")
            err._send_completed = True
            raise err
        fake_send_raw.call_count = 0

        with patch.object(conn, "_send_raw", side_effect=fake_send_raw):
            with patch.object(conn, "is_connected", return_value=True):
                with pytest.raises(AbletonConnectionError, match="Timeout"):
                    conn.send_command("set_tempo", {"tempo": 120})

        assert fake_send_raw.call_count == 1, (
            "timeout must NOT retry — only tried once"
        )

    def test_retry_budget_capped_at_one(self):
        """If the retry itself also fails with 'Connection closed', do
        NOT retry again — raise. One retry budget only."""
        from mcp_server.connection import AbletonConnection, AbletonConnectionError
        conn = AbletonConnection(host="127.0.0.1", port=9878)

        def fake_send_raw(command, recv_timeout=None):
            fake_send_raw.call_count += 1
            err = AbletonConnectionError("Connection closed by Ableton")
            err._send_completed = True
            raise err
        fake_send_raw.call_count = 0

        with patch.object(conn, "_send_raw", side_effect=fake_send_raw):
            with patch.object(conn, "is_connected", return_value=True):
                with patch.object(conn, "disconnect"):
                    with patch.object(conn, "connect"):
                        with patch("mcp_server.connection.time.sleep"):
                            with pytest.raises(AbletonConnectionError,
                                               match="Connection closed"):
                                conn.send_command("set_tempo", {"tempo": 120})

        assert fake_send_raw.call_count == 2, (
            f"expected 1 original + 1 retry = 2 calls, got {fake_send_raw.call_count}"
        )
