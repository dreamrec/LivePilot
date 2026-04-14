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
