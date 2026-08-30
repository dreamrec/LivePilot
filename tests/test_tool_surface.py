"""Contracts for LivePilot's compact, search-first public tool surface."""

from __future__ import annotations

import asyncio
import json

from mcp_server.runtime.tool_surface import (
    CORE_PRODUCER_TOOLS,
    SEARCH_HIDDEN_TOOLS,
    build_tool_search_transform,
    profile_tool_names,
)
from mcp_server.server import _get_all_tools


def test_producer_profile_stays_focused_and_keeps_trust_loop():
    names = profile_tool_names("producer")
    assert names == CORE_PRODUCER_TOOLS
    assert len(names) <= 30
    assert {
        "get_session_kernel",
        "set_device_parameter",
        "atlas_search",
        "listen_ab",
        "create_experiment",
        "undo",
    } <= set(names)


def test_domain_profiles_extend_instead_of_replacing_core():
    core = set(profile_tool_names("producer"))
    assert core < set(profile_tool_names("composition"))
    assert core < set(profile_tool_names("mixing"))
    assert core < set(profile_tool_names("sampling"))


def _search(query: str) -> list[str]:
    transform = build_tool_search_transform("producer")
    tools = _get_all_tools()
    return [tool.name for tool in asyncio.run(transform._search(tools, query))]


def test_search_ranks_common_direct_edits():
    assert _search("set tempo to 128")[0] == "set_tempo"
    assert "set_device_parameter" in _search("set the filter cutoff to 2 kHz")[:2]
    assert "atlas_search" in _search("find a warm pad preset")[:2]


def test_search_ranks_workflows_without_recommending_legacy_router():
    assert "analyze_sound_design" in _search("make the drums punchier")[:2]
    assert "compose" in _search("turn this loop into a full song")[:3]
    assert "listen_ab" in _search("compare before and after")[:2]
    assert SEARCH_HIDDEN_TOOLS.isdisjoint(_search("route this request with a budget"))


def test_compact_catalog_is_under_10k_token_proxy():
    """Measure the real transformed tools/list payload, not the raw registry."""
    from fastmcp import FastMCP

    source_tools = _get_all_tools()
    local = FastMCP("surface-test")
    for tool in source_tools:
        local.add_tool(tool)
    local.add_transform(build_tool_search_transform("producer"))
    visible = asyncio.run(local.list_tools())
    payload = json.dumps(
        [
            tool.to_mcp_tool().model_dump(mode="json", by_alias=True, exclude_none=True)
            for tool in visible
        ],
        separators=(",", ":"),
    ).encode()

    assert len(visible) == len(CORE_PRODUCER_TOOLS) + 2
    # 40 KB is a conservative <10k-token proxy. The exact tokenizer audit
    # measured materially lower, but CI intentionally needs no tokenizer dep.
    assert len(payload) < 40_000
