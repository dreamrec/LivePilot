"""Contract tests for Composition Engine V1 MCP tools."""

import asyncio

import pytest


def _get_tool_names():
    from mcp_server.server import mcp
    tools = asyncio.run(mcp.list_tools())
    return {tool.name for tool in tools}


def test_composition_tools_registered():
    names = _get_tool_names()
    expected = {
        "analyze_composition",
        "get_section_graph",
        "get_phrase_grid",
        "plan_gesture",
        "evaluate_composition_move",
    }
    missing = expected - names
    assert not missing, f"Missing composition tools: {missing}"


class TestPlanGesture:
    def test_rejects_invalid_intent(self):
        from mcp_server.tools.composition import plan_gesture
        with pytest.raises(ValueError, match="Unknown intent"):
            plan_gesture(None, intent="explode", target_tracks=[0], start_bar=0)

    def test_valid_intent(self):
        from mcp_server.tools.composition import plan_gesture
        result = plan_gesture(None, intent="reveal", target_tracks="[0, 1]", start_bar=8)
        assert result["intent"] == "reveal"
        assert result["curve_family"] == "exponential"

    def test_all_intents_accepted(self):
        from mcp_server.tools.composition import plan_gesture
        from mcp_server.tools._composition_engine import GestureIntent
        for intent in GestureIntent:
            result = plan_gesture(None, intent=intent.value, target_tracks=[0], start_bar=0)
            assert result["intent"] == intent.value
