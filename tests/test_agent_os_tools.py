"""Contract tests for Agent OS V1 MCP tools."""

import asyncio

import pytest


def _get_tool_names():
    from mcp_server.server import mcp
    tools = asyncio.run(mcp.list_tools())
    return {tool.name for tool in tools}


def test_agent_os_tools_registered():
    names = _get_tool_names()
    expected = {
        "compile_goal_vector",
        "build_world_model",
        "evaluate_move",
    }
    missing = expected - names
    assert not missing, f"Missing agent_os tools: {missing}"


class TestCompileGoalVector:
    def test_rejects_invalid_dimension(self):
        from mcp_server.tools.agent_os import compile_goal_vector
        with pytest.raises(ValueError, match="Unknown target"):
            compile_goal_vector(None, "test", {"loudness": 1.0})

    def test_rejects_invalid_mode(self):
        from mcp_server.tools.agent_os import compile_goal_vector
        with pytest.raises(ValueError, match="mode"):
            compile_goal_vector(None, "test", {"punch": 1.0}, mode="attack")

    def test_accepts_json_string_targets(self):
        from mcp_server.tools.agent_os import compile_goal_vector
        result = compile_goal_vector(None, "test", '{"punch": 0.5, "energy": 0.5}')
        assert "goal_vector" in result
        assert result["goal_vector"]["mode"] == "improve"

    def test_reports_measurable_dimensions(self):
        from mcp_server.tools.agent_os import compile_goal_vector
        result = compile_goal_vector(None, "test", {"punch": 0.3, "groove": 0.7})
        assert "punch" in result["measurable_dimensions"]
        assert "groove" in result["unmeasurable_dimensions"]


class TestEvaluateMove:
    def test_enforces_hard_rules(self):
        from mcp_server.tools.agent_os import evaluate_move
        goal = {
            "request_text": "test",
            "targets": {"weight": 1.0},
            "protect": {},
            "mode": "improve",
            "aggression": 0.5,
            "research_mode": "none",
        }
        before = {"spectrum": {"sub": 0.5, "low": 0.5}, "rms": 0.6, "peak": 0.8}
        after = {"spectrum": {"sub": 0.3, "low": 0.3}, "rms": 0.4, "peak": 0.6}
        result = evaluate_move(None, goal, before, after)
        assert result["keep_change"] is False

    def test_accepts_json_strings(self):
        import json
        from mcp_server.tools.agent_os import evaluate_move
        goal = json.dumps({
            "request_text": "test",
            "targets": {"energy": 1.0},
            "protect": {},
            "mode": "improve",
            "aggression": 0.5,
        })
        before = json.dumps({"spectrum": {"sub": 0.5}, "rms": 0.5, "peak": 0.7})
        after = json.dumps({"spectrum": {"sub": 0.5}, "rms": 0.7, "peak": 0.9})
        result = evaluate_move(None, goal, before, after)
        assert "score" in result
