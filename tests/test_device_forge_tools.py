"""Contract tests for Device Forge MCP tools."""

from __future__ import annotations

import asyncio

import pytest


def _get_tool_names():
    from mcp_server.server import mcp
    tools = asyncio.run(mcp.list_tools())
    return {tool.name for tool in tools}


def test_device_forge_tools_registered():
    names = _get_tool_names()
    expected = {
        "generate_m4l_effect",
        "list_genexpr_templates",
        "install_m4l_device",
    }
    missing = expected - names
    assert not missing, f"Missing device forge tools: {missing}"
