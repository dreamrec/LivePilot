"""v1.20.3: tests for ``ensure_analyzer_on_master`` — an idempotent
pre-flight tool that loads LivePilot_Analyzer on master when it's not
already there.

Motivated by the v1.20.1 campaign's operator-error class of bug: Claude
(the LLM operator) should have loaded the analyzer at the start of a
fresh session per its global memory, but forgot. Automating via a
dedicated tool closes that class of failure — any downstream caller
(director Phase 1, operator scripts, MCP consumers) can invoke
ensure_analyzer_on_master() idempotently without worrying about
whether it was already called.

Behavior:
  * analyzer already on master → no-op, returns status="already_loaded"
  * analyzer NOT on master, device IS in Ableton browser → load it,
    return status="loaded"
  * analyzer NOT in browser → return status="install_required" with
    actionable message (caller should invoke install_m4l_device first)
  * load fails for any other reason → status="failed" with error detail

Post-load verification: tool confirms single instance + reports the
device_index of the loaded analyzer so callers can confirm it's the
last device on master (which is required for correct spectral
measurement per CLAUDE.md:LivePilot_Analyzer-must-be-LAST-on-master).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _make_ctx(
    master_devices: list[dict],
    load_response: dict | None = None,
    load_error: Exception | None = None,
):
    """Build a minimal ctx that routes get_master_track to `master_devices`
    and simulates find_and_load_device's outcome."""

    calls: list[tuple[str, dict | None]] = []

    class _Ableton:
        def send_command(self, cmd, params=None):
            calls.append((cmd, dict(params) if params else None))
            if cmd == "get_master_track":
                return {"name": "Main", "volume": 0.85, "devices": master_devices}
            # Default OK for other commands
            return {"ok": True}

    # find_and_load_device needs its own mock because it's an MCP tool
    # (not a raw remote command).
    from mcp_server.tools import devices as devices_mod

    real_find = devices_mod.find_and_load_device

    def fake_find_and_load(ctx, track_index, device_name, allow_duplicate=False):
        calls.append(("_find_and_load_device", {
            "track_index": track_index,
            "device_name": device_name,
            "allow_duplicate": allow_duplicate,
        }))
        if load_error is not None:
            raise load_error
        return load_response or {"loaded": device_name, "track_index": track_index, "device_index": 0}

    ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton()}, _calls=calls)
    ctx._fake_find = fake_find_and_load
    return ctx, calls


class TestEnsureAnalyzerOnMaster:
    def test_already_loaded_noop(self, monkeypatch):
        """When LivePilot_Analyzer is already on master, no load happens;
        returns status=already_loaded with the existing device_index."""
        from mcp_server.tools import analyzer as analyzer_mod

        ctx, calls = _make_ctx(master_devices=[
            {"index": 0, "name": "LivePilot_Analyzer",
             "class_name": "MxDeviceAudioEffect", "is_active": True},
        ])
        # Patch find_and_load_device module reference so the tool uses our fake.
        monkeypatch.setattr(analyzer_mod, "_load_analyzer_impl", ctx._fake_find)

        result = analyzer_mod.ensure_analyzer_on_master(ctx)

        assert result["status"] == "already_loaded"
        assert result["device_index"] == 0
        # No load attempt
        load_calls = [c for c in calls if c[0] == "_find_and_load_device"]
        assert not load_calls, f"expected no load call, got {load_calls}"

    def test_loads_when_missing(self, monkeypatch):
        """When master has no analyzer, tool calls find_and_load_device
        with track_index=-1000 (master convention)."""
        from mcp_server.tools import analyzer as analyzer_mod

        ctx, calls = _make_ctx(
            master_devices=[],
            load_response={"loaded": "LivePilot_Analyzer", "track_index": -1000,
                           "device_index": 0},
        )
        monkeypatch.setattr(analyzer_mod, "_load_analyzer_impl", ctx._fake_find)

        result = analyzer_mod.ensure_analyzer_on_master(ctx)

        assert result["status"] == "loaded"
        load_calls = [c for c in calls if c[0] == "_find_and_load_device"]
        assert len(load_calls) == 1
        assert load_calls[0][1]["track_index"] == -1000
        assert load_calls[0][1]["device_name"] == "LivePilot_Analyzer"

    def test_returns_install_required_when_device_not_in_browser(self, monkeypatch):
        """find_and_load_device raises ValueError when the name isn't in
        the browser. Tool should catch and return an actionable
        install_required status instead of bubbling the exception."""
        from mcp_server.tools import analyzer as analyzer_mod

        ctx, calls = _make_ctx(
            master_devices=[],
            load_error=ValueError("Device 'LivePilot_Analyzer' not found in browser"),
        )
        monkeypatch.setattr(analyzer_mod, "_load_analyzer_impl", ctx._fake_find)
        # BUG-T#1: pin the path check to False so this test exercises the
        # genuinely-not-installed path regardless of dev-machine state.
        monkeypatch.setattr(
            analyzer_mod, "_analyzer_amxd_installed_at_user_library",
            lambda: False,
        )

        result = analyzer_mod.ensure_analyzer_on_master(ctx)

        assert result["status"] == "install_required"
        # Actionable guidance
        assert "install_m4l_device" in result.get("hint", "")
        assert "LivePilot_Analyzer.amxd" in result.get("hint", "")

    def test_skips_duplicate_analyzer_if_already_present(self, monkeypatch):
        """If multiple analyzers exist on master (edge case — prior bug),
        tool still returns already_loaded with the FIRST device_index,
        and does NOT load a second instance."""
        from mcp_server.tools import analyzer as analyzer_mod

        ctx, calls = _make_ctx(master_devices=[
            {"index": 2, "name": "LivePilot_Analyzer"},
            {"index": 4, "name": "LivePilot_Analyzer"},  # duplicate
        ])
        monkeypatch.setattr(analyzer_mod, "_load_analyzer_impl", ctx._fake_find)

        result = analyzer_mod.ensure_analyzer_on_master(ctx)

        assert result["status"] == "already_loaded"
        assert result["device_index"] == 2  # first match
        # Caller-visible warning about the duplicate
        assert result.get("duplicate_count") == 2

    def test_reports_position_in_chain(self, monkeypatch):
        """Tool reports whether the analyzer is LAST on master.
        CLAUDE.md invariant: 'LivePilot_Analyzer must be LAST on master'."""
        from mcp_server.tools import analyzer as analyzer_mod

        ctx, calls = _make_ctx(master_devices=[
            {"index": 0, "name": "EQ Eight"},
            {"index": 1, "name": "LivePilot_Analyzer"},
            {"index": 2, "name": "Compressor"},  # analyzer NOT last
        ])
        monkeypatch.setattr(analyzer_mod, "_load_analyzer_impl", ctx._fake_find)

        result = analyzer_mod.ensure_analyzer_on_master(ctx)

        assert result["status"] == "already_loaded"
        assert result["is_last_on_master"] is False
        # Warning text that surfaces the invariant
        assert "last" in result.get("warning", "").lower()

    def test_is_idempotent(self, monkeypatch):
        """Calling twice in a row should return the same status both
        times without creating a second analyzer."""
        from mcp_server.tools import analyzer as analyzer_mod

        # First call: master empty → load
        master_state = []

        class _Ableton:
            def send_command(self, cmd, params=None):
                if cmd == "get_master_track":
                    return {"name": "Main", "devices": list(master_state)}
                return {"ok": True}

        ctx = SimpleNamespace(lifespan_context={"ableton": _Ableton()})

        load_call_count = 0

        def fake_find(ctx_, track_index, device_name, allow_duplicate=False):
            nonlocal load_call_count
            load_call_count += 1
            # Simulate successful load: analyzer now appears on master
            master_state.append({"index": len(master_state),
                                 "name": "LivePilot_Analyzer"})
            return {"loaded": device_name, "track_index": track_index,
                    "device_index": len(master_state) - 1}

        monkeypatch.setattr(analyzer_mod, "_load_analyzer_impl", fake_find)

        r1 = analyzer_mod.ensure_analyzer_on_master(ctx)
        r2 = analyzer_mod.ensure_analyzer_on_master(ctx)

        assert r1["status"] == "loaded"
        assert r2["status"] == "already_loaded"
        assert load_call_count == 1, (
            f"expected exactly 1 load attempt across 2 calls, got {load_call_count}"
        )


class TestColdBrowserCacheDisambiguation:
    """BUG-T#1: cold User Library browser cache on first Live boot can make
    find_and_load_device exceed recv_timeout. Before the fix, the catch-block
    surfaced ``install_required`` even though the .amxd was at the canonical
    path — sending the agent into a reinstall loop. The fix uses a filesystem
    check to disambiguate ``cache_cold`` from genuinely-not-installed."""

    def test_cache_cold_when_amxd_present_on_disk(self, monkeypatch):
        """Load failure + .amxd present at User Library path → cache_cold."""
        from mcp_server.tools import analyzer as analyzer_mod

        ctx, calls = _make_ctx(
            master_devices=[],
            load_error=Exception("Timeout waiting for response from Ableton (20s)"),
        )
        monkeypatch.setattr(analyzer_mod, "_load_analyzer_impl", ctx._fake_find)
        monkeypatch.setattr(
            analyzer_mod, "_analyzer_amxd_installed_at_user_library",
            lambda: True,
        )

        result = analyzer_mod.ensure_analyzer_on_master(ctx)

        assert result["status"] == "cache_cold"
        assert "Retry" in result.get("hint", "") or "retry" in result.get("hint", "")
        # Critically: must NOT tell the agent to reinstall
        assert "install_m4l_device" not in result.get("hint", "")

    def test_install_required_when_amxd_missing_on_disk(self, monkeypatch):
        """Load failure + .amxd absent at User Library path → install_required."""
        from mcp_server.tools import analyzer as analyzer_mod

        ctx, calls = _make_ctx(
            master_devices=[],
            load_error=ValueError("Device 'LivePilot_Analyzer' not found in browser"),
        )
        monkeypatch.setattr(analyzer_mod, "_load_analyzer_impl", ctx._fake_find)
        monkeypatch.setattr(
            analyzer_mod, "_analyzer_amxd_installed_at_user_library",
            lambda: False,
        )

        result = analyzer_mod.ensure_analyzer_on_master(ctx)

        assert result["status"] == "install_required"
        assert "install_m4l_device" in result.get("hint", "")
