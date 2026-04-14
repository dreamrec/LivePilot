"""Tests for the unified execution router."""

from mcp_server.runtime.execution_router import (
    ExecutionResult,
    classify_step,
    execute_step,
    execute_plan_steps,
)


# ── Classification ───────────────────────────────────────────────


def test_classify_remote_command():
    assert classify_step("set_track_volume") == "remote_command"


def test_classify_bridge_command():
    assert classify_step("get_hidden_params") == "bridge_command"


def test_classify_mcp_tool():
    assert classify_step("apply_automation_shape") == "mcp_tool"


def test_classify_unknown():
    assert classify_step("nonexistent_xyz_999") == "unknown"


def test_classify_undo_is_remote():
    assert classify_step("undo") == "remote_command"


def test_load_sample_to_simpler_is_mcp_tool():
    """load_sample_to_simpler is a Python async MCP tool, not a bridge command.

    It internally calls search_browser + load_browser_item + replace_simpler_sample
    (the last via the M4L bridge), but the tool itself is dispatched in-process.
    """
    assert classify_step("load_sample_to_simpler") == "mcp_tool"


def test_capture_audio_is_bridge_not_mcp():
    """capture_audio is handled by livepilot_bridge.js:146, not an in-proc MCP fn."""
    assert classify_step("capture_audio") == "bridge_command"


# ── Single step execution ────────────────────────────────────────


def test_remote_step_without_ableton_returns_unavailable():
    result = execute_step(
        tool="set_track_volume",
        params={"track_index": 0, "volume": 0.5},
        ableton=None,
        ctx=None,
    )
    assert result.ok is False
    assert result.backend == "remote_command"
    assert "unavailable" in result.error.lower()


def test_unknown_step_returns_error():
    result = execute_step(
        tool="fake_tool_xyz",
        params={},
        ableton=None,
        ctx=None,
    )
    assert result.ok is False
    assert result.backend == "unknown"


def test_execution_result_to_dict():
    r = ExecutionResult(
        ok=True, backend="remote_command",
        tool="set_track_volume", result={"volume": 0.5},
    )
    d = r.to_dict()
    assert d["ok"] is True
    assert d["backend"] == "remote_command"
    assert d["tool"] == "set_track_volume"


def test_failed_result_to_dict():
    r = ExecutionResult(
        ok=False, backend="mcp_tool",
        tool="analyze_mix", error="not wired yet",
    )
    d = r.to_dict()
    assert d["ok"] is False
    assert "error" in d


# ── Plan execution ───────────────────────────────────────────────


class FakeAbleton:
    def __init__(self, fail_on=None):
        self.calls = []
        self._fail_on = fail_on or set()

    def send_command(self, cmd, params=None):
        self.calls.append(cmd)
        if cmd in self._fail_on:
            raise RuntimeError(f"Fake failure on {cmd}")
        return {"ok": True, "cmd": cmd}


def test_all_remote_plan_executes():
    ab = FakeAbleton()
    steps = [
        {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.5}},
        {"tool": "set_track_pan", "params": {"track_index": 0, "pan": 0.3}},
    ]
    results = execute_plan_steps(steps, ableton=ab)
    assert len(results) == 2
    assert all(r.ok for r in results)
    assert ab.calls == ["set_track_volume", "set_track_pan"]


def test_plan_stops_on_failure():
    ab = FakeAbleton(fail_on={"set_track_pan"})
    steps = [
        {"tool": "set_track_volume", "params": {}},
        {"tool": "set_track_pan", "params": {}},
        {"tool": "set_track_send", "params": {}},
    ]
    results = execute_plan_steps(steps, ableton=ab)
    assert len(results) == 2  # stopped after failure
    assert results[0].ok is True
    assert results[1].ok is False


def test_empty_plan():
    results = execute_plan_steps([], ableton=None)
    assert results == []


def test_unknown_tool_in_plan():
    steps = [{"tool": "nonexistent_xyz", "params": {}}]
    results = execute_plan_steps(steps, ableton=FakeAbleton())
    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].backend == "unknown"


def test_dual_key_format():
    """Router accepts both {tool, params} and {command, args} formats."""
    ab = FakeAbleton()
    steps = [{"command": "set_track_volume", "args": {"track_index": 0}}]
    results = execute_plan_steps(steps, ableton=ab)
    assert len(results) == 1
    assert results[0].ok is True


def test_applied_count_matches_successes():
    ab = FakeAbleton(fail_on={"set_track_send"})
    steps = [
        {"tool": "set_track_volume", "params": {}},
        {"tool": "set_track_pan", "params": {}},
        {"tool": "set_track_send", "params": {}},
    ]
    results = execute_plan_steps(steps, ableton=ab)
    applied = sum(1 for r in results if r.ok)
    assert applied == 2


# ── Async router with step-result binding ──────────────────────────────

import asyncio


class FakeBridge:
    def __init__(self, fail_on=None):
        self.calls = []
        self._fail_on = fail_on or set()

    async def send_command(self, cmd, *args, **kwargs):
        self.calls.append(cmd)
        if cmd in self._fail_on:
            return {"error": f"fake bridge failure on {cmd}"}
        return {"ok": True, "cmd": cmd}


class FakeAbletonReturning:
    """Ableton fake that returns a device_index on insert_device."""
    def __init__(self):
        self.calls = []
        self.last_set_params = None

    def send_command(self, cmd, params=None):
        self.calls.append((cmd, params))
        if cmd == "insert_device":
            return {"loaded": "Reverb", "device_index": 7, "track_index": 0}
        if cmd == "set_device_parameter":
            self.last_set_params = params
            return {"ok": True}
        return {"ok": True}


def test_async_router_dispatches_remote_bridge_and_mcp():
    """Async router must run plans mixing all three backends via correct transports."""
    from mcp_server.runtime.execution_router import execute_plan_steps_async

    ab = FakeAbleton()
    bridge = FakeBridge()

    async def fake_mcp_tool(params, ctx=None):
        return {"mcp_ok": True, "params": params}

    mcp_registry = {"fake_mcp_tool": fake_mcp_tool}

    steps = [
        {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.5}},  # remote
        {"tool": "get_hidden_params", "params": {}},                                 # bridge
        # fake_mcp_tool isn't in MCP_TOOLS — use explicit backend annotation
        {"tool": "fake_mcp_tool", "params": {"x": 1}, "backend": "mcp_tool"},
    ]

    results = asyncio.run(execute_plan_steps_async(
        steps, ableton=ab, bridge=bridge, mcp_registry=mcp_registry,
    ))
    assert len(results) == 3
    errors = [r.error for r in results if not r.ok]
    assert all(r.ok for r in results), f"errors: {errors}"
    assert ab.calls == ["set_track_volume"]
    assert bridge.calls == ["get_hidden_params"]


def test_async_router_step_binding_resolves_device_index():
    """A later step can reference an earlier step's result via $from_step."""
    from mcp_server.runtime.execution_router import execute_plan_steps_async

    ab = FakeAbletonReturning()

    steps = [
        {
            "step_id": "insert",
            "tool": "insert_device",
            "params": {"track_index": 0, "device_name": "Reverb"},
        },
        {
            "tool": "set_device_parameter",
            "params": {
                "track_index": 0,
                "device_index": {"$from_step": "insert", "path": "device_index"},
                "parameter_name": "Dry/Wet",
                "value": 0.3,
            },
        },
    ]

    results = asyncio.run(execute_plan_steps_async(steps, ableton=ab))
    assert len(results) == 2
    assert all(r.ok for r in results), [r.error for r in results if not r.ok]
    assert ab.last_set_params["device_index"] == 7


def test_async_router_binding_missing_step_id_fails_that_step():
    from mcp_server.runtime.execution_router import execute_plan_steps_async

    ab = FakeAbleton()
    steps = [
        {
            "tool": "set_device_parameter",
            "params": {
                "device_index": {"$from_step": "nonexistent", "path": "device_index"},
            },
        },
    ]
    results = asyncio.run(execute_plan_steps_async(steps, ableton=ab))
    assert len(results) == 1
    assert results[0].ok is False
    assert "nonexistent" in results[0].error.lower() or "binding" in results[0].error.lower()


def test_async_router_mcp_tool_not_in_registry_fails_clearly():
    from mcp_server.runtime.execution_router import execute_plan_steps_async

    steps = [{"tool": "apply_automation_shape", "params": {}}]
    results = asyncio.run(execute_plan_steps_async(
        steps, ableton=FakeAbleton(), mcp_registry={},
    ))
    assert results[0].ok is False
    assert "apply_automation_shape" in results[0].error


def test_async_router_bridge_unavailable_fails_clearly():
    from mcp_server.runtime.execution_router import execute_plan_steps_async

    steps = [{"tool": "get_hidden_params", "params": {}}]
    # No bridge provided
    results = asyncio.run(execute_plan_steps_async(
        steps, ableton=FakeAbleton(), bridge=None,
    ))
    assert results[0].ok is False
    assert "bridge unavailable" in results[0].error.lower()


def test_async_router_binding_nested_path():
    """Path resolution supports dotted access into nested dicts."""
    from mcp_server.runtime.execution_router import execute_plan_steps_async

    class FakeAb:
        def __init__(self):
            self.last = None
        def send_command(self, cmd, params=None):
            if cmd == "stage":
                return {"stage_result": {"nested": {"value": 42}}}
            if cmd == "consume":
                self.last = params
                return {"ok": True}
            return {"ok": True}

    ab = FakeAb()
    steps = [
        {"step_id": "s1", "tool": "stage", "params": {}},
        {"tool": "consume", "params": {"val": {"$from_step": "s1", "path": "stage_result.nested.value"}}},
    ]
    # consume isn't a real remote command — classify as unknown, so declare backend
    for s in steps:
        s["backend"] = "remote_command"

    results = asyncio.run(execute_plan_steps_async(steps, ableton=ab))
    assert all(r.ok for r in results), [r.error for r in results if not r.ok]
    assert ab.last["val"] == 42


def test_async_router_respects_declared_backend():
    """An explicit `backend` key on a step overrides classify_step."""
    from mcp_server.runtime.execution_router import execute_plan_steps_async

    async def fake_mcp(params, ctx=None):
        return {"ok": True, "via": "mcp"}

    # Use a name that normally classifies as remote
    steps = [{
        "tool": "set_track_volume",
        "params": {},
        "backend": "mcp_tool",
    }]
    results = asyncio.run(execute_plan_steps_async(
        steps, ableton=FakeAbleton(), mcp_registry={"set_track_volume": fake_mcp},
    ))
    assert results[0].ok
    assert results[0].result["via"] == "mcp"


def test_mcp_dispatch_registry_contains_load_sample_to_simpler():
    from mcp_server.runtime.mcp_dispatch import build_mcp_dispatch_registry
    reg = build_mcp_dispatch_registry()
    assert "load_sample_to_simpler" in reg
    assert callable(reg["load_sample_to_simpler"])
