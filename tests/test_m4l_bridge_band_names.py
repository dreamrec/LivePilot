"""Regression guard for T3 (sub_low band) from the 2026-04-22 handoff.

The M4L analyzer may emit either 8-band or 9-band spectrum payloads
depending on which frozen .amxd the user has loaded. The server side must
handle both without breaking: existing 8-band devices keep their names,
new 9-band devices get the sub_low key prepended.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from mcp_server.m4l_bridge import SpectralReceiver


def test_band_names_8_legacy_layout_unchanged():
    # Existing users on v1.15 and older had these exact names in this order.
    # Breaking this invariant breaks their tooling even if they haven't
    # re-frozen the .amxd — unacceptable.
    assert SpectralReceiver.BAND_NAMES_8 == [
        "sub",
        "low",
        "low_mid",
        "mid",
        "high_mid",
        "high",
        "presence",
        "air",
    ]


def test_band_names_9_prepends_sub_low():
    assert SpectralReceiver.BAND_NAMES_9[0] == "sub_low"
    # 9-band list is the 8-band list with sub_low prepended.
    assert SpectralReceiver.BAND_NAMES_9[1:] == SpectralReceiver.BAND_NAMES_8


def test_band_names_default_alias_is_9():
    # The default alias should track the new layout so callers reading
    # BAND_NAMES without a length hint get the forward-compatible set.
    assert SpectralReceiver.BAND_NAMES == SpectralReceiver.BAND_NAMES_9


def test_band_names_9_length():
    assert len(SpectralReceiver.BAND_NAMES_9) == 9


def test_band_names_8_length():
    assert len(SpectralReceiver.BAND_NAMES_8) == 8


def test_no_band_name_duplicates():
    # Duplicate names would collide in the cache dict.
    assert len(set(SpectralReceiver.BAND_NAMES_9)) == 9
    assert len(set(SpectralReceiver.BAND_NAMES_8)) == 8


def _make_receiver():
    # SpectralReceiver.__init__ does no I/O — it only sets up in-memory state,
    # so we can drive _handle_chunk / _handle_response directly without a live
    # UDP socket or Ableton connection.
    from mcp_server.m4l_bridge import SpectralCache, SpectralReceiver

    return SpectralReceiver(SpectralCache())


def _encode_payload(obj):
    import base64
    import json

    raw = json.dumps(obj).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def test_chunk_reassembly_tolerates_out_of_order_arrival():
    """An index>0 chunk arriving before index 0 must NOT permanently lose the
    response. This is the §bridge finding #1 regression: the old code only
    opened a bucket on index==0 and split a single response across two buckets
    that never completed.
    """
    rx = _make_receiver()

    payload = {"ok": True, "value": "x" * 50}
    encoded = _encode_payload(payload)
    half = len(encoded) // 2
    piece0, piece1 = encoded[:half], encoded[half:]

    captured = {}
    rx._handle_response = lambda full: captured.__setitem__("full", full)

    # Deliberately deliver the second chunk FIRST (UDP reordering).
    rx._handle_chunk(1, 2, piece1)
    assert "full" not in captured  # not complete yet
    rx._handle_chunk(0, 2, piece0)

    assert captured.get("full") == encoded


def test_chunk_reassembly_in_order_still_works():
    rx = _make_receiver()
    payload = {"ok": True, "value": "y" * 40}
    encoded = _encode_payload(payload)
    half = len(encoded) // 2
    piece0, piece1 = encoded[:half], encoded[half:]

    captured = {}
    rx._handle_response = lambda full: captured.__setitem__("full", full)

    rx._handle_chunk(0, 2, piece0)
    assert "full" not in captured
    rx._handle_chunk(1, 2, piece1)
    assert captured.get("full") == encoded


def test_chunk_reassembly_new_response_evicts_stale_partial():
    """A chunk with a different `total` signals a new response; the stale
    partial from an abandoned (timed-out) prior response must be evicted, not
    merged.
    """
    rx = _make_receiver()
    rx._handle_response = lambda full: None  # ignore

    # Start a 3-chunk response but never finish it (only 1 of 3 arrives).
    rx._handle_chunk(0, 3, "AAA")
    assert len(rx._chunks) == 1

    # A new 2-chunk response begins. The orphaned 3-chunk partial must be gone.
    encoded = _encode_payload({"ok": True})
    half = len(encoded) // 2
    captured = {}
    rx._handle_response = lambda full: captured.__setitem__("full", full)
    rx._handle_chunk(0, 2, encoded[:half])
    rx._handle_chunk(1, 2, encoded[half:])

    assert captured.get("full") == encoded
    assert rx._chunks == {}  # both buckets cleaned up


def test_response_request_id_mismatch_does_not_resolve_current_future():
    """A late response from command A must not resolve command B's future.

    The bridge JS echoes ``_livepilot_request_id`` for updated analyzers. The
    receiver must drop mismatched ids so a timed-out command cannot bind its
    delayed reply to the next in-flight command.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        rx = _make_receiver()
        future = loop.create_future()
        rx.set_response_future(future, request_id="cmd_b")

        rx._handle_response(_encode_payload({
            "_livepilot_request_id": "cmd_a",
            "ok": True,
            "value": "late A",
        }))

        assert not future.done()
        assert rx._response_callback is future

        rx._handle_response(_encode_payload({
            "_livepilot_request_id": "cmd_b",
            "ok": True,
            "value": "current B",
        }))

        assert future.done()
        assert future.result() == {"ok": True, "value": "current B"}
        assert rx._response_callback is None
    finally:
        loop.close()


def test_bridge_js_echoes_private_request_id_contract():
    """The Max JS bridge must echo Python's private request token."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    js = (root / "m4l_device" / "livepilot_bridge.js").read_text(encoding="utf-8")

    assert "__livepilot_request_id:" in js
    assert "_livepilot_request_id" in js


# ── v1.27.2: strict correlation + chunk hardening regressions ──────────────


def test_no_id_response_dropped_after_id_seen():
    """Once the analyzer is known to stamp request ids, a NO-id response
    arriving while a future is live (e.g. a batched read that lost its id
    across Task.schedule gaps and outlived its timeout) is a stale straggler
    and must NOT resolve the in-flight command's future."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        rx = _make_receiver()
        rx._seen_request_id = True  # an id-bearing response was already seen
        future = loop.create_future()
        rx.set_response_future(future, request_id="cmd_x")

        # A no-id straggler arrives — must be dropped, future left intact.
        rx._handle_response(_encode_payload({"ok": True, "value": "straggler"}))
        assert not future.done()
        assert rx._response_callback is future

        # The correctly-correlated reply resolves it.
        rx._handle_response(_encode_payload({
            "_livepilot_request_id": "cmd_x", "ok": True, "value": "real",
        }))
        assert future.done()
        assert future.result() == {"ok": True, "value": "real"}
    finally:
        loop.close()


def test_no_id_response_accepted_for_legacy_build():
    """Backwards compat: a pre-request-id analyzer never stamps ids. Until an
    id is ever seen, a no-id response resolves the in-flight future."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        rx = _make_receiver()
        assert rx._seen_request_id is False
        future = loop.create_future()
        rx.set_response_future(future, request_id="cmd_legacy")
        rx._handle_response(_encode_payload({"ok": True, "value": "legacy"}))
        assert future.done()
        assert future.result() == {"ok": True, "value": "legacy"}
    finally:
        loop.close()


def test_chunk_request_id_buckets_are_isolated():
    """Chunks carrying distinct request ids reassemble into separate buckets,
    even when interleaved — a stale chunk from a timed-out command can never
    contaminate another command's response."""
    rx = _make_receiver()
    a = _encode_payload({"ok": True, "cmd": "A", "pad": "a" * 40})
    b = _encode_payload({"ok": True, "cmd": "B", "pad": "b" * 40})
    ah, bh = len(a) // 2, len(b) // 2

    captured = []
    rx._handle_response = lambda full: captured.append(full)

    rx._handle_chunk(0, 2, a[:ah], request_id="A")
    rx._handle_chunk(0, 2, b[:bh], request_id="B")
    assert captured == []  # neither complete
    rx._handle_chunk(1, 2, b[bh:], request_id="B")
    rx._handle_chunk(1, 2, a[ah:], request_id="A")

    assert a in captured and b in captured


def test_chunk_out_of_range_index_dropped():
    """An out-of-range index (>= total) must be dropped — never stored nor
    counted toward completion. The old len()==total check could KeyError."""
    rx = _make_receiver()
    captured = []
    rx._handle_response = lambda full: captured.append(full)

    rx._handle_chunk(5, 2, "GARBAGE", request_id="C")  # out of range — ignored
    rx._handle_chunk(0, 2, "AA", request_id="C")
    assert captured == []  # still waiting for index 1, and no KeyError raised
    rx._handle_chunk(1, 2, "BB", request_id="C")
    assert captured == ["AABB"]


def test_chunk_duplicate_index_no_premature_reassembly():
    """A duplicate index must not let len(parts)==total fire reassembly while a
    real index is still missing (the KeyError-on-missing-key path)."""
    rx = _make_receiver()
    captured = []
    rx._handle_response = lambda full: captured.append(full)

    rx._handle_chunk(0, 3, "AA", request_id="D")
    rx._handle_chunk(0, 3, "AA", request_id="D")  # duplicate index 0
    assert captured == []  # only one distinct index — must NOT reassemble
    rx._handle_chunk(1, 3, "BB", request_id="D")
    rx._handle_chunk(2, 3, "CC", request_id="D")
    assert captured == ["AABBCC"]


def test_bridge_js_batched_reads_capture_request_id():
    """Batched-read handlers must capture the request id in a closure (so it
    survives Task.schedule gaps) and pass it explicitly to send_response; the
    chunk header must carry the id as its first arg."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    js = (root / "m4l_device" / "livepilot_bridge.js").read_text(encoding="utf-8")

    # One capture per batched-read handler (get_params/hidden_params/auto_state).
    assert js.count("var captured_request_id = current_response_request_id;") >= 3
    assert "function send_response(obj, explicit_id)" in js
    assert '"/response_chunk", (rid || "")' in js
