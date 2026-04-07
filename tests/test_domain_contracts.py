"""Domain contract tests — verify parameter validation, error handling, and tool signatures.

Goes beyond registration tests to check that tools enforce their contracts:
- Required parameters are validated
- Range checks work (tempo, volume, pitch, etc.)
- Error messages are helpful
"""

import json
import socket
import threading
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.connection import AbletonConnection, AbletonConnectionError


class MockAbletonServer:
    """Minimal TCP server that returns canned responses for contract testing."""

    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self):
        self._sock.settimeout(1.0)
        while self._running:
            try:
                client, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(client,), daemon=True).start()

    def _handle(self, client):
        buf = b""
        client.settimeout(5.0)
        try:
            while self._running:
                chunk = client.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    req = json.loads(line)
                    resp = {"id": req.get("id", "?"), "ok": True, "result": {}}
                    if req.get("type") == "ping":
                        resp["result"] = {"pong": True}
                    client.sendall((json.dumps(resp) + "\n").encode())
        except (socket.timeout, OSError):
            pass
        finally:
            client.close()

    def stop(self):
        self._running = False
        try:
            self._sock.close()
        except OSError:
            pass
        self._thread.join(timeout=3)


@pytest.fixture
def mock_server():
    server = MockAbletonServer()
    yield server
    server.stop()


@pytest.fixture
def conn(mock_server):
    c = AbletonConnection(host="127.0.0.1", port=mock_server.port)
    c.connect()
    yield c
    c.disconnect()


# ── Transport contracts ─────────────────────────────────────────────

class TestTransportContracts:
    def test_set_tempo_rejects_below_range(self):
        from mcp_server.tools.transport import _validate_tempo
        with pytest.raises(ValueError, match="20.*999"):
            _validate_tempo(10)

    def test_set_tempo_rejects_above_range(self):
        from mcp_server.tools.transport import _validate_tempo
        with pytest.raises(ValueError, match="20.*999"):
            _validate_tempo(1000)

    def test_set_tempo_accepts_valid(self):
        from mcp_server.tools.transport import _validate_tempo
        _validate_tempo(120)  # Should not raise

    def test_time_signature_rejects_bad_denominator(self):
        from mcp_server.tools.transport import _validate_time_signature
        with pytest.raises(ValueError, match="[Dd]enominator"):
            _validate_time_signature(4, 3)

    def test_time_signature_accepts_valid(self):
        from mcp_server.tools.transport import _validate_time_signature
        _validate_time_signature(4, 4)
        _validate_time_signature(6, 8)
        _validate_time_signature(3, 4)


# ── Notes contracts ─────────────────────────────────────────────────

class TestNotesContracts:
    def test_note_requires_pitch(self):
        from mcp_server.tools.notes import _validate_note
        with pytest.raises(ValueError, match="pitch"):
            _validate_note({"start_time": 0, "duration": 0.5})

    def test_note_pitch_range(self):
        from mcp_server.tools.notes import _validate_note
        with pytest.raises(ValueError, match="pitch.*0.*127"):
            _validate_note({"pitch": 128, "start_time": 0, "duration": 0.5})

    def test_note_requires_start_time(self):
        from mcp_server.tools.notes import _validate_note
        with pytest.raises(ValueError, match="start_time"):
            _validate_note({"pitch": 60, "duration": 0.5})

    def test_note_requires_duration(self):
        from mcp_server.tools.notes import _validate_note
        with pytest.raises(ValueError, match="duration"):
            _validate_note({"pitch": 60, "start_time": 0})

    def test_note_rejects_zero_duration(self):
        from mcp_server.tools.notes import _validate_note
        with pytest.raises(ValueError, match="duration"):
            _validate_note({"pitch": 60, "start_time": 0, "duration": 0})

    def test_note_velocity_range(self):
        from mcp_server.tools.notes import _validate_note
        with pytest.raises(ValueError, match="velocity"):
            _validate_note({"pitch": 60, "start_time": 0, "duration": 0.5, "velocity": 200})

    def test_valid_note_passes(self):
        from mcp_server.tools.notes import _validate_note
        _validate_note({"pitch": 60, "start_time": 0, "duration": 0.5, "velocity": 100})

    def test_valid_note_with_probability(self):
        from mcp_server.tools.notes import _validate_note
        _validate_note({"pitch": 60, "start_time": 0, "duration": 0.5, "probability": 0.5})


# ── Automation contracts ────────────────────────────────────────────

class TestAutomationContracts:
    def test_get_clip_automation_rejects_invalid_track(self):
        from mcp_server.tools.automation import get_clip_automation
        with pytest.raises(ValueError, match="track_index"):
            get_clip_automation(None, track_index=-100, clip_index=0)

    def test_get_clip_automation_rejects_negative_clip(self):
        from mcp_server.tools.automation import get_clip_automation
        with pytest.raises(ValueError, match="clip_index"):
            get_clip_automation(None, track_index=0, clip_index=-1)

    def test_set_clip_automation_rejects_invalid_parameter_type(self):
        from mcp_server.tools.automation import set_clip_automation
        with pytest.raises(ValueError, match="parameter_type"):
            set_clip_automation(None, track_index=0, clip_index=0,
                               parameter_type="invalid", points=[])

    def test_apply_automation_shape_rejects_invalid_indices(self):
        from mcp_server.tools.automation import apply_automation_shape
        with pytest.raises(ValueError, match="track_index"):
            apply_automation_shape(None, track_index=-100, clip_index=0,
                                   parameter_type="volume", curve_type="linear")

    def test_clear_clip_automation_rejects_invalid_track(self):
        from mcp_server.tools.automation import clear_clip_automation
        with pytest.raises(ValueError, match="track_index"):
            clear_clip_automation(None, track_index=-100, clip_index=0)


# ── Tracks contracts ────────────────────────────────────────────────

class TestTracksContracts:
    def test_color_index_range(self):
        from mcp_server.tools.tracks import _validate_color_index
        with pytest.raises(ValueError, match="color_index.*0.*69"):
            _validate_color_index(70)
        with pytest.raises(ValueError, match="color_index"):
            _validate_color_index(-1)
        _validate_color_index(0)
        _validate_color_index(69)

    def test_track_index_accepts_return_tracks(self):
        from mcp_server.tools.tracks import _validate_track_index
        # Return tracks (-1 to -99) should be accepted
        _validate_track_index(-1)
        _validate_track_index(-4)
        _validate_track_index(-99)
        # Out of range should be rejected
        with pytest.raises(ValueError, match="track_index"):
            _validate_track_index(-100)
        # allow_return=False should reject negatives
        with pytest.raises(ValueError, match="track_index"):
            _validate_track_index(-1, allow_return=False)
        _validate_track_index(0)


# ── Clips contracts ─────────────────────────────────────────────────

class TestClipsContracts:
    def test_index_validation_accepts_zero(self):
        """Track and clip index validators accept zero (minimum valid index)."""
        from mcp_server.tools.clips import _validate_track_index, _validate_clip_index
        _validate_track_index(0)
        _validate_clip_index(0)

    def test_index_validation_rejects_negative(self):
        """Track and clip index validators reject negative indices."""
        from mcp_server.tools.clips import _validate_track_index, _validate_clip_index
        with pytest.raises(ValueError):
            _validate_track_index(-1)
        with pytest.raises(ValueError):
            _validate_clip_index(-1)


# ── Connection contracts ────────────────────────────────────────────

class TestConnectionContracts:
    def test_error_hints_have_content(self):
        """All error codes should have non-empty hints."""
        from mcp_server.connection import _ERROR_HINTS
        for code, hint in _ERROR_HINTS.items():
            assert len(hint) > 20, f"Hint for {code} too short"

    def test_friendly_error_includes_code_and_message(self):
        from mcp_server.connection import _friendly_error
        result = _friendly_error("INDEX_ERROR", "Track 99 not found", "get_track_info")
        assert "[INDEX_ERROR]" in result
        assert "Track 99 not found" in result
        assert "get_session_info" in result  # from INDEX_ERROR hint text (command_type param is unused)

    def test_friendly_error_unknown_code(self):
        from mcp_server.connection import _friendly_error
        result = _friendly_error("UNKNOWN_CODE", "Something broke", "test")
        assert "[UNKNOWN_CODE]" in result
        assert "Something broke" in result

    def test_command_log_records_entries(self, conn):
        conn.send_command("get_session_info")
        log = conn.get_recent_commands(10)
        assert len(log) >= 1
        entry = log[0]
        assert entry["command"] == "get_session_info"
        assert entry["ok"] is True
        assert "timestamp" in entry

    def test_command_log_limit(self, conn):
        for _ in range(5):
            conn.send_command("get_session_info")
        log = conn.get_recent_commands(3)
        assert len(log) == 3

    def test_command_log_newest_first(self, conn):
        conn.send_command("get_session_info")
        conn.send_command("set_tempo", {"tempo": 140})
        log = conn.get_recent_commands(10)
        assert log[0]["command"] == "set_tempo"
        assert log[1]["command"] == "get_session_info"


# ── Diagnostics contracts ───────────────────────────────────────────

class TestDiagnosticsContracts:
    def test_default_name_detection(self):
        """Test the name detection logic used by diagnostics (duplicated here
        since remote_script can't be imported outside Ableton)."""
        _DEFAULT_NAME_PATTERNS = frozenset(["MIDI", "Audio", "Inst", "Return"])

        def _looks_default_name(name):
            stripped = name.strip()
            for part in stripped.split("-"):
                part = part.strip()
                if part.isdigit():
                    continue
                if part in _DEFAULT_NAME_PATTERNS:
                    return True
            return False

        assert _looks_default_name("1-MIDI") is True
        assert _looks_default_name("2-Audio") is True
        assert _looks_default_name("MIDI") is True
        assert _looks_default_name("Audio") is True
        assert _looks_default_name("My Bass") is False
        assert _looks_default_name("Drums") is False
        assert _looks_default_name("Lead Synth") is False
        assert _looks_default_name("3-Return") is True

    def test_diagnostics_tool_registered(self):
        """get_session_diagnostics must be in the registered tool list."""
        import asyncio
        from mcp_server.server import mcp
        tools = asyncio.run(mcp.list_tools())
        tool_names = {t.name for t in tools}
        assert "get_session_diagnostics" in tool_names
