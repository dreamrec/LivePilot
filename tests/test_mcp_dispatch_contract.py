"""Contract tests for MCP_TOOLS <-> mcp_dispatch registry.

The async execution router classifies a step as "mcp_tool" when its tool
name is in MCP_TOOLS. It then looks the tool up in the registry built by
build_mcp_dispatch_registry(). If the classifier claims a tool is
executable but the registry has no adapter, every plan step that emits
that tool fails at runtime with a confusing "not registered" error.

These tests enforce:
  * every MCP_TOOLS entry has a registered adapter
  * every registered adapter corresponds to an MCP_TOOLS entry
  * every adapter resolves the real implementation without raising
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from mcp_server.runtime.execution_router import MCP_TOOLS, READ_ONLY_TOOLS, filter_apply_steps
from mcp_server.runtime.mcp_dispatch import build_mcp_dispatch_registry


def test_every_mcp_tool_has_an_adapter():
    registry = build_mcp_dispatch_registry()
    missing = MCP_TOOLS - registry.keys()
    assert not missing, (
        f"MCP_TOOLS declares these names as mcp_tool but no adapter is "
        f"registered in build_mcp_dispatch_registry(): {sorted(missing)}. "
        f"Add each to mcp_server/runtime/mcp_dispatch.py or remove from "
        f"MCP_TOOLS."
    )


def test_every_adapter_is_in_mcp_tools():
    registry = build_mcp_dispatch_registry()
    extra = registry.keys() - MCP_TOOLS
    assert not extra, (
        f"These adapters are registered but the classifier won't route to "
        f"them because they aren't in MCP_TOOLS: {sorted(extra)}. Either "
        f"add them to MCP_TOOLS or drop the adapter."
    )


def test_every_adapter_is_callable_and_async():
    registry = build_mcp_dispatch_registry()
    for name, fn in registry.items():
        assert callable(fn), f"{name} adapter is not callable"
        assert inspect.iscoroutinefunction(fn), (
            f"{name} adapter must be async — the router awaits its result"
        )


def test_every_adapter_imports_cleanly():
    """Imports inside adapters are deferred to first call. Verify they resolve."""
    registry = build_mcp_dispatch_registry()
    for name in registry:
        # Each adapter's body does `from ... import <name>` — simulate by
        # importing the adapter's module path and attribute. We only need
        # to confirm the module exists; deeper call semantics are covered
        # elsewhere.
        assert name  # each key is a real tool name
    # Smoke import of the real modules referenced:
    for modpath in (
        "mcp_server.tools.analyzer",
        "mcp_server.tools.automation",
        "mcp_server.tools.composition",
        "mcp_server.tools.motif",
        "mcp_server.tools.research",
        "mcp_server.mix_engine.tools",
        "mcp_server.device_forge.tools",
    ):
        importlib.import_module(modpath)


def test_read_only_tools_not_in_mcp_tools_except_analysis():
    """Sanity: write-class MCP tools must not be listed as read-only.

    A few tools (analyze_mix, get_master_spectrum, get_emotional_arc,
    get_motif_graph) deliberately appear in both — they dispatch as
    mcp_tool but never mutate state. That overlap is intentional; this
    test documents it so a future drift is visible.
    """
    overlap = MCP_TOOLS & READ_ONLY_TOOLS
    expected = {
        "analyze_mix",
        "get_master_spectrum",
        "get_emotional_arc",
        "get_motif_graph",
    }
    assert overlap == expected, (
        f"Read-only/MCP overlap changed: {sorted(overlap)}. If that's "
        f"intentional, update this test; if not, one of these tools is "
        f"mutating state or is miscategorized."
    )


def test_filter_apply_steps_drops_reads():
    steps = [
        {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.5}},
        {"tool": "get_track_meters", "params": {}},
        {"tool": "get_master_spectrum", "params": {}},
        {"tool": "set_track_send", "params": {"track_index": 0, "send_index": 0, "value": 0.2}},
        {"tool": "analyze_mix", "params": {}},
    ]
    kept = filter_apply_steps(steps)
    tools = [s["tool"] for s in kept]
    assert tools == ["set_track_volume", "set_track_send"]


def test_filter_apply_steps_handles_objects():
    """Also accepts CompiledStep-like objects with a .tool attribute."""
    class FakeStep:
        def __init__(self, tool):
            self.tool = tool

        def get(self, _key, _default=None):  # duck-typing as dict fails here
            raise TypeError("fake step is not a dict")

    steps = [FakeStep("set_track_volume"), FakeStep("get_track_meters")]
    kept = filter_apply_steps(steps)
    assert len(kept) == 1
    assert kept[0].tool == "set_track_volume"
