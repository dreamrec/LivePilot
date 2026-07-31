"""Coverage for the async analyzer guard introduced 2026-07-31.

`_require_analyzer` builds a deliberately rich, user-actionable error: to tell
"not loaded on master" from "loaded but UDP 9880 held by another instance" it
does a synchronous TCP round-trip (`get_master_track`) plus a `subprocess`
port-holder probe. Called bare from an `async def`, both ran on the event loop
and froze every other in-flight MCP request — and they fire exactly when the
session is already unhealthy and the user is most likely retrying. The deep
review found 24 analyzer tools doing this.

`_require_analyzer_async` is the fix. These tests pin the two properties that
matter:

  * the expensive diagnostic runs OFF the event loop, and
  * the error text is byte-identical to the sync guard, because that text is
    the most user-visible surface of the analyzer layer.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server.tools._analyzer_engine.context import (  # noqa: E402
    _require_analyzer,
    _require_analyzer_async,
)


def _cache(*, connected: bool, devices: list[dict] | None = None):
    """Fake SpectralCache with just the surface the guard touches."""
    cache = MagicMock()
    cache.is_connected = connected
    ctx = MagicMock()
    ableton = MagicMock()
    ableton.send_command.return_value = {"devices": devices or []}
    ctx.lifespan_context = {"ableton": ableton}
    cache._livepilot_ctx = ctx
    return cache


ANALYZER_ON_MASTER = [{"name": "LivePilot Analyzer"}]


# --- the fast path must not pay for a thread hop ----------------------------


def test_connected_returns_without_touching_a_worker_thread():
    """These guards sit at the top of ~24 hot tools that run in tight
    evaluation loops. Re-checking an in-memory flag must not cost a threadpool
    round-trip on every call."""
    hops = []

    async def _spy(fn, *a, **kw):
        hops.append(fn)
        return fn(*a, **kw)

    with patch("mcp_server.tools._analyzer_engine.context.asyncio.to_thread", _spy):
        assert asyncio.run(_require_analyzer_async(_cache(connected=True))) is None

    assert hops == [], "connected fast path must not offload to a thread"


def test_disconnected_offloads_the_diagnostic_to_a_thread():
    """The converse: the expensive path MUST leave the event loop."""
    hops = []

    async def _spy(fn, *a, **kw):
        hops.append(fn)
        return fn(*a, **kw)

    with patch("mcp_server.tools._analyzer_engine.context.asyncio.to_thread", _spy), \
            patch("mcp_server.server._identify_port_holder", return_value=None):
        with pytest.raises(ValueError):
            asyncio.run(_require_analyzer_async(_cache(connected=False)))

    assert hops and hops[0] is _require_analyzer, (
        f"the diagnostic must be offloaded via to_thread, got {hops}"
    )


# --- error text must be identical to the sync guard -------------------------


@pytest.mark.parametrize(
    "devices, holder",
    [
        ([], None),                       # analyzer not on master at all
        (ANALYZER_ON_MASTER, None),       # loaded, bridge down, port free
        (ANALYZER_ON_MASTER, "pid 4242 python3 -m mcp_server"),  # port held
    ],
    ids=["not-loaded", "loaded-port-free", "loaded-port-held"],
)
def test_async_guard_raises_the_same_message_as_the_sync_guard(devices, holder):
    """The async form must be a pure transport change. If these ever diverge,
    users get different troubleshooting advice depending on whether the tool
    they happened to call was sync or async."""
    with patch("mcp_server.server._identify_port_holder", return_value=holder):
        with pytest.raises(ValueError) as sync_err:
            _require_analyzer(_cache(connected=False, devices=devices))

        with pytest.raises(ValueError) as async_err:
            asyncio.run(
                _require_analyzer_async(_cache(connected=False, devices=devices))
            )

    assert str(async_err.value) == str(sync_err.value)


def test_error_text_still_names_the_remedy():
    """Guards against a refactor quietly degrading the actionable text — the
    whole reason the expensive probe exists."""
    with patch("mcp_server.server._identify_port_holder", return_value=None):
        with pytest.raises(ValueError) as err:
            asyncio.run(
                _require_analyzer_async(
                    _cache(connected=False, devices=ANALYZER_ON_MASTER)
                )
            )
    assert "reconnect_bridge" in str(err.value)

    with patch("mcp_server.server._identify_port_holder", return_value=None):
        with pytest.raises(ValueError) as err2:
            asyncio.run(_require_analyzer_async(_cache(connected=False, devices=[])))
    assert "master track" in str(err2.value)


# --- one implementation, not two --------------------------------------------


def test_only_one_require_analyzer_implementation_exists():
    """`mcp_server/tools/devices.py` used to carry its own copy.

    The copies drifted, and the duplicate drifted *worse*: it told users to
    "retry" or "restart the MCP server" without ever naming `reconnect_bridge`
    — the actual fix when a stale instance is holding UDP 9880 — and dropped
    the browser path for loading the device. Which advice you got depended on
    whether the tool you happened to call lived in analyzer.py or devices.py.

    Deduplicated 2026-07-31 onto _analyzer_engine/context.py. A second
    definition reopens exactly that drift, so fail loudly instead.
    """
    import ast

    found = []
    for path in sorted((REPO_ROOT / "mcp_server").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "_require_analyzer"
            ):
                found.append(path.relative_to(REPO_ROOT).as_posix())

    # File, not line — a line number would break on any unrelated edit above it.
    assert found == ["mcp_server/tools/_analyzer_engine/context.py"], (
        "_require_analyzer must have exactly one definition, in "
        f"_analyzer_engine/context.py. Found: {found}"
    )


def test_devices_tools_use_the_shared_async_guard():
    """devices.py must route through the shared guard, not re-roll one."""
    import mcp_server.tools.devices as devices
    from mcp_server.tools._analyzer_engine import context

    assert not hasattr(devices, "_require_analyzer"), (
        "devices.py re-introduced a local _require_analyzer"
    )
    assert devices._require_analyzer_async is context._require_analyzer_async


# --- the call sites actually migrated ---------------------------------------


def test_every_async_analyzer_tool_uses_the_async_guard():
    """The 24 migrated call sites must stay migrated.

    Pinned structurally rather than by count so that adding a new async
    analyzer tool that calls the sync guard fails here with a clear message,
    instead of only showing up as a scanner-baseline drift.
    """
    import ast

    src = (REPO_ROOT / "mcp_server" / "tools" / "analyzer.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    parent: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[id(child)] = node

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
        if name != "_require_analyzer":
            continue
        cur, enclosing = parent.get(id(node)), None
        while cur is not None:
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                enclosing = cur
                break
            cur = parent.get(id(cur))
        if isinstance(enclosing, ast.AsyncFunctionDef):
            offenders.append(f"{enclosing.name}() at line {node.lineno}")

    assert not offenders, (
        "async analyzer tools must await _require_analyzer_async(cache) — the "
        "sync guard does a TCP round-trip plus a subprocess probe on its error "
        f"path and blocks the event loop. Offenders: {offenders}"
    )
