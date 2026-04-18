#!/usr/bin/env python3
"""Generate tool catalog from live runtime metadata.

Produces a markdown tool catalog validated against mcp.list_tools().
This is the single source of truth — hand-edited catalogs are replaced.

Usage: python3 scripts/generate_tool_catalog.py > docs/manual/tool-catalog-generated.md
"""

import asyncio
import inspect
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def get_tools() -> list[dict]:
    """Get all registered tools with metadata."""
    from mcp_server.server import mcp

    tools_raw = asyncio.run(mcp.list_tools())
    tools = []
    for t in tools_raw:
        # Get the module path to determine domain
        func = t.fn if hasattr(t, "fn") else None
        module = ""
        if func:
            module = func.__module__ if hasattr(func, "__module__") else ""

        # Get parameter names
        params = []
        if func:
            sig = inspect.signature(func)
            for name, param in sig.parameters.items():
                if name == "ctx":
                    continue
                required = param.default is inspect.Parameter.empty
                params.append({"name": name, "required": required})

        tools.append({
            "name": t.name,
            "description": t.description[:120] if hasattr(t, "description") and t.description else "",
            "module": module,
            "params": params,
        })

    return tools


def infer_domain(module: str) -> str:
    """Infer domain from module path using the same module-layout rule as
    ``scripts/sync_metadata.py``:
      - ``mcp_server.<X>.<...>``              → ``<X>``
      - ``mcp_server.tools.<Y>``              → ``<Y>``
    The display name is Title-Cased; underscores become spaces.
    """
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "mcp_server":
        return "Other"
    if parts[1] == "tools":
        domain_key = parts[2] if len(parts) > 2 else "other"
    else:
        domain_key = parts[1]
    return domain_key.replace("_", " ").title()


def main():
    tools = get_tools()
    total = len(tools)

    # Group by domain
    domains = defaultdict(list)
    for t in tools:
        domain = infer_domain(t["module"])
        domains[domain].append(t)

    print(f"# LivePilot — Full Tool Catalog (Generated)")
    print()
    print(f"{total} tools across {len(domains)} domains.")
    print()
    print("> Auto-generated from `mcp.list_tools()`. Do not hand-edit.")
    print("> Regenerate: `python3 scripts/generate_tool_catalog.py`")
    print()
    print("---")
    print()

    for domain in sorted(domains.keys()):
        tool_list = sorted(domains[domain], key=lambda t: t["name"])
        print(f"## {domain} ({len(tool_list)})")
        print()
        print("| Tool | Description |")
        print("|------|-------------|")
        for t in tool_list:
            desc = t["description"].split("\n")[0].strip()
            print(f"| `{t['name']}` | {desc} |")
        print()

    print(f"---")
    print(f"*Generated from {total} registered tools.*")


if __name__ == "__main__":
    main()
