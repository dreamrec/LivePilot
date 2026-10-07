"""Every tool parameter that defaults to None must accept an explicit null.

FastMCP copies a None default into the schema as "default": null. If the
annotation is a bare `list` or `dict`, the schema's type excludes null, and
a client that sends that advertised default is rejected before the tool runs.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_none_defaults_accept_null():
    from mcp_server.server import mcp

    bad = []
    for tool in asyncio.run(mcp.list_tools()):
        for name, prop in tool.parameters.get("properties", {}).items():
            if prop.get("default", ...) is not None:
                continue
            if "type" not in prop and "anyOf" not in prop:
                continue  # untyped (e.g. Any): null already allowed
            types = [prop.get("type")] + [b.get("type") for b in prop.get("anyOf", [])]
            if "null" not in types:
                bad.append(f"{tool.name}.{name}")
    assert bad == []
