"""Bridge shared-secret token auth — Python side (v1.28 re-freeze batch).

Security review 2026-07-30: OSC 9881 (MCP server → M4L analyzer commands)
binds to ALL interfaces inside Max — `udpreceive 9881` takes no
bind-interface argument — so a LAN-adjacent host can blindly fire any
bridge command. Fix: the server generates a random token at startup,
publishes it to a file only local processes can read
(~/Documents/LivePilot/bridge_token — same home-derivation as the JS
_get_captures_dir()), and prepends "__livepilot_token:<hex>" as the FIRST
OSC argument of every command. The frozen JS validates and drops
non-matching commands.

Compatibility contract tested here (flag both ways):
  * legacy device (ping version < 1.28.0): token must NEVER be sent —
    old frozen dispatchers would read it as the first positional arg.
  * new device (ping version >= 1.28.0): every send_command/send_capture
    packet carries the token as the first string arg.
  * the version is learned from the existing ping response; a non-ping
    command on a fresh bridge runs a ping handshake first.

Also covers the /capture_error reply channel (part of the same re-freeze
batch): capture_audio's busy/invalid-filename branches used to reply on
/response, which send_capture never listens to.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import stat
import struct
from pathlib import Path

import pytest

from mcp_server.m4l_bridge import (
    M4LBridge,
    SpectralCache,
    SpectralReceiver,
    TOKEN_AUTH_MIN_BRIDGE_VERSION,
    parse_bridge_version,
)


REPO = Path(__file__).resolve().parent.parent
BRIDGE_JS = REPO / "m4l_device" / "livepilot_bridge.js"

TOKEN_PREFIX = "__livepilot_token:"
REQUEST_ID_PREFIX = "__livepilot_request_id:"


# ── OSC wire helpers ────────────────────────────────────────────────────────


def _parse_packet(packet: bytes) -> tuple[str, list]:
    """Parse an outgoing OSC packet into (address, [decoded args]).

    String args produced by M4LBridge._build_osc are `b64:`-prefixed
    urlsafe-base64; decode them back so tests assert on logical values.
    """
    null_pos = packet.index(b"\x00")
    address = packet[:null_pos].decode("ascii")
    offset = null_pos + 1
    while offset % 4 != 0:
        offset += 1

    tag_null = packet.index(b"\x00", offset)
    type_tags = packet[offset + 1:tag_null].decode("ascii")
    offset = tag_null + 1
    while offset % 4 != 0:
        offset += 1

    args: list = []
    for tag in type_tags:
        if tag == "i":
            args.append(struct.unpack(">i", packet[offset:offset + 4])[0])
            offset += 4
        elif tag == "f":
            args.append(struct.unpack(">f", packet[offset:offset + 4])[0])
            offset += 4
        elif tag == "s":
            s_null = packet.index(b"\x00", offset)
            raw = packet[offset:s_null].decode("ascii")
            if raw.startswith("b64:"):
                payload = raw[4:] + "=" * (-len(raw[4:]) % 4)
                raw = base64.urlsafe_b64decode(payload).decode("utf-8")
            args.append(raw)
            offset = s_null + 1
            while offset % 4 != 0:
                offset += 1
    return address, args


def _build_osc(address: str, *args) -> bytes:
    """Minimal OSC builder for simulating incoming M4L → server packets."""
    addr_bytes = address.encode("ascii") + b"\x00"
    while len(addr_bytes) % 4 != 0:
        addr_bytes += b"\x00"
    type_tags = ","
    arg_data = b""
    for arg in args:
        if isinstance(arg, int):
            type_tags += "i"
            arg_data += struct.pack(">i", arg)
        elif isinstance(arg, str):
            type_tags += "s"
            s_bytes = arg.encode("ascii") + b"\x00"
            while len(s_bytes) % 4 != 0:
                s_bytes += b"\x00"
            arg_data += s_bytes
    tag_bytes = type_tags.encode("ascii") + b"\x00"
    while len(tag_bytes) % 4 != 0:
        tag_bytes += b"\x00"
    return addr_bytes + tag_bytes + arg_data


def _encode_payload(payload: dict) -> str:
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class _FakeDevice:
    """Stands in for bridge._sock and replies like a frozen .amxd.

    Records every outgoing (command, decoded_args) pair, then resolves the
    receiver's pending response future on the next loop tick — pings get a
    version payload, everything else a generic ok.
    """

    def __init__(self, receiver: SpectralReceiver, version: str = "1.28.0"):
        self.receiver = receiver
        self.version = version
        self.packets: list[tuple[str, list]] = []

    def sendto(self, data: bytes, addr=None) -> None:
        command, args = _parse_packet(data)
        self.packets.append((command, args))
        asyncio.get_running_loop().call_soon(self._reply, command)

    def _reply(self, command: str) -> None:
        cb = self.receiver._response_callback
        if cb is not None and not cb.done():
            payload: dict = {"ok": True}
            if command == "ping":
                payload["version"] = self.version
            cb.set_result(payload)

    def close(self) -> None:  # atexit-registered M4LBridge.close() calls this
        pass


def _make_bridge(tmp_path: Path, version: str | None = None,
                 device_version: str = "1.28.0"):
    cache = SpectralCache()
    cache.update("rms", 0.1)  # mark analyzer as connected
    receiver = SpectralReceiver(cache)
    bridge = M4LBridge(
        cache, receiver,
        token_file_path=tmp_path / "bridge_token",
    )
    device = _FakeDevice(receiver, version=device_version)
    bridge._sock = device
    if version is not None:
        bridge.note_bridge_version(version)
    return bridge, device


# ── Version parsing / gating ────────────────────────────────────────────────


def test_parse_bridge_version():
    assert parse_bridge_version("1.28.0") == (1, 28, 0)
    assert parse_bridge_version("1.27.3") == (1, 27, 3)
    assert parse_bridge_version("2.0.0") == (2, 0, 0)
    assert parse_bridge_version("1.28") == (1, 28, 0)
    assert parse_bridge_version("1.28.0-beta") == (1, 28, 0)
    assert parse_bridge_version("garbage") is None
    assert parse_bridge_version("") is None


def test_auth_disabled_by_default(tmp_path):
    bridge, _ = _make_bridge(tmp_path)
    assert bridge.token_auth_enabled is False


def test_note_bridge_version_gates_on_min_version(tmp_path):
    bridge, _ = _make_bridge(tmp_path)

    bridge.note_bridge_version("1.27.3")
    assert bridge.token_auth_enabled is False

    bridge.note_bridge_version("1.28.0")
    assert bridge.token_auth_enabled is True

    bridge.note_bridge_version("2.0.0")
    assert bridge.token_auth_enabled is True

    # Sanity: the gate constant itself is what these versions straddle.
    assert TOKEN_AUTH_MIN_BRIDGE_VERSION == (1, 28, 0)


def test_note_bridge_version_malformed_stays_off(tmp_path):
    bridge, _ = _make_bridge(tmp_path)
    bridge.note_bridge_version("garbage")
    assert bridge.token_auth_enabled is False
    bridge.note_bridge_version(None)
    assert bridge.token_auth_enabled is False


# ── send_command: token on the wire (compat flag both ways) ────────────────


@pytest.mark.asyncio
async def test_send_command_no_token_for_legacy_device(tmp_path):
    """Pre-1.28 frozen device: the token arg must NEVER appear — the old
    dispatcher would consume it as the first positional argument."""
    bridge, device = _make_bridge(tmp_path, version="1.27.3")

    result = await bridge.send_command("get_params", 0, 1, timeout=2.0)
    assert result.get("ok") is True

    command, args = device.packets[-1]
    assert command == "get_params"
    string_args = [a for a in args if isinstance(a, str)]
    assert not any(a.startswith(TOKEN_PREFIX) for a in string_args)
    # Positional args untouched, request id still trails.
    assert args[0] == 0 and args[1] == 1
    assert string_args[-1].startswith(REQUEST_ID_PREFIX)


@pytest.mark.asyncio
async def test_send_command_token_is_first_arg_for_new_device(tmp_path):
    bridge, device = _make_bridge(tmp_path, version="1.28.0")

    result = await bridge.send_command("get_params", 0, 1, timeout=2.0)
    assert result.get("ok") is True

    command, args = device.packets[-1]
    assert command == "get_params"
    # Token is the FIRST argument on the wire...
    assert isinstance(args[0], str) and args[0] == TOKEN_PREFIX + bridge.auth_token
    # ...original positionals follow, request id still trails.
    assert args[1] == 0 and args[2] == 1
    assert args[-1].startswith(REQUEST_ID_PREFIX)


@pytest.mark.asyncio
async def test_send_capture_token_both_ways(tmp_path):
    for version, expect_token in (("1.27.3", False), ("1.28.0", True)):
        bridge, device = _make_bridge(tmp_path, version=version)

        async def _resolve_capture():
            await asyncio.sleep(0.05)
            fut = bridge.receiver._capture_future
            if fut and not fut.done():
                fut.set_result({"ok": True, "file": "t.wav"})

        task = asyncio.create_task(_resolve_capture())
        result = await bridge.send_capture("capture_audio", 1000, "t.wav", timeout=2.0)
        await task
        assert result.get("ok") is True

        command, args = device.packets[-1]
        assert command == "capture_audio"
        has_token = isinstance(args[0], str) and args[0].startswith(TOKEN_PREFIX)
        assert has_token is expect_token, (
            f"version={version}: token presence should be {expect_token}"
        )


# ── Version handshake via the existing ping ────────────────────────────────


@pytest.mark.asyncio
async def test_ping_response_learns_version_and_enables_auth(tmp_path):
    bridge, device = _make_bridge(tmp_path, device_version="1.28.0")
    assert bridge.token_auth_enabled is False

    result = await bridge.send_command("ping", timeout=2.0)
    assert result.get("version") == "1.28.0"
    assert bridge.token_auth_enabled is True


@pytest.mark.asyncio
async def test_ping_response_keeps_auth_off_for_legacy(tmp_path):
    bridge, device = _make_bridge(tmp_path, device_version="1.27.3")
    await bridge.send_command("ping", timeout=2.0)
    assert bridge.token_auth_enabled is False


@pytest.mark.asyncio
async def test_handshake_ping_precedes_first_real_command(tmp_path):
    """On a fresh bridge (version unknown) a non-ping command must run the
    ping handshake first: an untokened command would be dropped by a new
    device, a tokened one would break an old device."""
    bridge, device = _make_bridge(tmp_path, device_version="1.28.0")

    result = await bridge.send_command("get_params", 0, 1, timeout=2.0)
    assert result.get("ok") is True

    commands = [c for c, _ in device.packets]
    assert commands == ["ping", "get_params"]
    # The handshake ping itself is untokened (the device exempts ping).
    _, ping_args = device.packets[0]
    assert not any(
        isinstance(a, str) and a.startswith(TOKEN_PREFIX) for a in ping_args
    )
    # The real command carries the token, learned mid-call.
    _, cmd_args = device.packets[1]
    assert cmd_args[0] == TOKEN_PREFIX + bridge.auth_token


@pytest.mark.asyncio
async def test_handshake_runs_once(tmp_path):
    bridge, device = _make_bridge(tmp_path, device_version="1.28.0")
    await bridge.send_command("get_params", 0, 1, timeout=2.0)
    await bridge.send_command("get_selected", timeout=2.0)
    commands = [c for c, _ in device.packets]
    assert commands.count("ping") == 1


@pytest.mark.asyncio
async def test_send_capture_runs_handshake_on_fresh_bridge(tmp_path):
    bridge, device = _make_bridge(tmp_path, device_version="1.28.0")

    async def _resolve_capture():
        await asyncio.sleep(0.05)
        fut = bridge.receiver._capture_future
        if fut and not fut.done():
            fut.set_result({"ok": True})

    task = asyncio.create_task(_resolve_capture())
    await bridge.send_capture("capture_audio", 1000, "t.wav", timeout=2.0)
    await task

    commands = [c for c, _ in device.packets]
    assert commands[0] == "ping"
    assert commands[-1] == "capture_audio"
    _, cap_args = device.packets[-1]
    assert cap_args[0] == TOKEN_PREFIX + bridge.auth_token


# ── Token file publication ──────────────────────────────────────────────────


def test_init_does_not_touch_disk(tmp_path):
    token_path = tmp_path / "bridge_token"
    cache = SpectralCache()
    M4LBridge(cache, SpectralReceiver(cache), token_file_path=token_path)
    assert not token_path.exists(), (
        "M4LBridge.__init__ must not write the token file — unit tests "
        "construct bridges freely; publication is the lifespan's job."
    )


def test_publish_auth_token_writes_file_0600(tmp_path):
    token_path = tmp_path / "nested" / "bridge_token"
    cache = SpectralCache()
    bridge = M4LBridge(cache, SpectralReceiver(cache), token_file_path=token_path)

    written = bridge.publish_auth_token()
    assert written == token_path
    assert token_path.read_text(encoding="utf-8").strip() == bridge.auth_token
    mode = stat.S_IMODE(token_path.stat().st_mode)
    assert mode == 0o600, f"token file mode is {oct(mode)}, expected 0o600"


def test_publish_auth_token_failure_is_nonfatal(tmp_path):
    # Point the token path INSIDE an existing file so mkdir/open must fail.
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    cache = SpectralCache()
    bridge = M4LBridge(
        cache, SpectralReceiver(cache),
        token_file_path=blocker / "bridge_token",
    )
    assert bridge.publish_auth_token() is None  # no raise


def test_env_kill_switch_disables_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVEPILOT_BRIDGE_TOKEN_DISABLE", "1")
    token_path = tmp_path / "bridge_token"
    cache = SpectralCache()
    bridge = M4LBridge(cache, SpectralReceiver(cache), token_file_path=token_path)

    assert bridge.publish_auth_token() is None
    assert not token_path.exists()

    bridge.note_bridge_version("1.28.0")
    assert bridge.token_auth_enabled is False


# ── /capture_error reply channel (re-freeze batch item 3) ───────────────────


def test_capture_error_resolves_capture_future():
    """capture_audio's busy branch used to reply on /response, which
    send_capture never listens to — the caller ate a 35s timeout and the
    error could resolve an UNRELATED pending command. New JS replies on
    /capture_error; the receiver must route it to the capture future."""
    loop = asyncio.new_event_loop()
    try:
        cache = SpectralCache()
        receiver = SpectralReceiver(cache)

        capture_fut = loop.create_future()
        response_fut = loop.create_future()
        receiver.set_capture_future(capture_fut)
        receiver.set_response_future(response_fut)

        payload = {"ok": False, "error": "Capture already in progress. Call capture_stop first."}
        packet = _build_osc("/capture_error", _encode_payload(payload))
        receiver._parse_osc(packet)

        assert capture_fut.done(), "/capture_error did not resolve _capture_future"
        assert capture_fut.result() == payload
        assert not response_fut.done(), "/capture_error must not touch _response_callback"
    finally:
        loop.close()


def test_capture_error_without_future_is_safe():
    cache = SpectralCache()
    receiver = SpectralReceiver(cache)
    packet = _build_osc("/capture_error", _encode_payload({"ok": False, "error": "busy"}))
    receiver._parse_osc(packet)  # must not raise


# ── Frozen-JS source contract (what the next re-freeze must contain) ───────
#
# The .amxd's frozen JS is authoritative at runtime; these tests pin the
# SOURCE so the pending re-freeze batch can't silently lose a piece.
# Precedent: test_capture_bridge.test_bridge_js_has_b64_decode_support.


def _js_source() -> str:
    return BRIDGE_JS.read_text(encoding="utf-8")


def _js_function_body(source: str, name: str) -> str:
    match = re.search(
        rf"function {re.escape(name)}\(.*?(?=\nfunction |\Z)", source, re.S
    )
    assert match, f"function {name} not found in livepilot_bridge.js"
    return match.group(0)


def test_bridge_js_validates_token():
    source = _js_source()
    assert '"__livepilot_token:"' in source or "'__livepilot_token:'" in source
    assert "bridge_token" in source, "JS must read ~/Documents/LivePilot/bridge_token"
    assert "_auth_check" in source
    # ping stays exempt — it is the version handshake that decides whether
    # the server sends the token at all.
    body = _js_function_body(source, "_auth_check")
    assert '"ping"' in body


def _strip_line_comments(text: str) -> str:
    """Drop full-line `//` comments so a commented-out call site does not
    satisfy a plain substring/regex search over the raw function body."""
    return "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("//")
    )


def test_bridge_js_anything_calls_auth_check():
    """anything() — the actual OSC command dispatcher — must call
    _auth_check(cmd, supplied_token) and drop the message on failure.

    test_bridge_js_validates_token (above) only checks that the token
    prefix / bridge_token / _auth_check strings exist SOMEWHERE in the
    file; it would still pass if the call site inside anything() were
    deleted or commented out while the standalone _auth_check function
    definition and the string literals were left intact — i.e. the
    security check goes dead while every existing assertion stays green.
    This test pins the call site itself, mirroring
    test_bridge_js_capture_errors_use_capture_error_channel's pattern of
    extracting a specific function's body and asserting on it.
    """
    source = _js_source()
    body = _js_function_body(source, "anything")
    active_code = _strip_line_comments(body)

    guard = re.search(
        r"if\s*\(\s*!\s*_auth_check\s*\(\s*cmd\s*,\s*supplied_token\s*\)\s*\)",
        active_code,
    )
    assert guard, (
        "anything() must call `if (!_auth_check(cmd, supplied_token))` and "
        "return early — the auth check exists elsewhere in the file but "
        "the dispatcher no longer enforces it, so every OSC command would "
        "run unauthenticated"
    )

    # The guard must actually short-circuit the message, not just be called
    # for effect — the next non-comment line dropping into the dispatcher
    # must be a bare `return;` (no reply, per the anti-oracle comment).
    guard_tail = active_code[guard.end():]
    assert re.match(r"\s*\{\s*return\s*;", guard_tail), (
        "the _auth_check guard in anything() must return early on failure"
    )


def test_bridge_js_capture_errors_use_capture_error_channel():
    source = _js_source()
    assert '"/capture_error"' in source
    body = _js_function_body(source, "cmd_capture_audio")
    assert "send_capture_error" in body, (
        "capture_audio's busy/invalid-filename branches must reply via "
        "/capture_error, not send_response"
    )
    assert "send_response" not in body, (
        "cmd_capture_audio still replies on /response somewhere — those "
        "replies are invisible to send_capture"
    )


def test_bridge_js_display_values_and_plugin_params_capture_request_id():
    """spike/12.4.5 batch item: batched readers must close over the request
    id (Task.schedule gaps let interleaved commands clobber the module-level
    current_response_request_id)."""
    source = _js_source()
    for fn in ("cmd_get_display_values", "cmd_get_plugin_params"):
        body = _js_function_body(source, fn)
        assert "captured_request_id" in body, (
            f"{fn} must capture current_response_request_id in a closure "
            "like cmd_get_params does"
        )
