"""Shared pytest fixtures for tests/.

Currently just the in-process FastMCP client harness used by
test_mcp_e2e.py to drive real tools through mcp.call_tool() /
fastmcp.Client dispatch (schema validation, coercion, lifespan context)
without a live Ableton Live instance or a real TCP/socket server.

Kept intentionally tiny — this is not a global fixture dumping ground for
the 83 existing hand-rolled-fake test files (out of scope for this batch).
"""

from __future__ import annotations

import sys
from typing import AsyncIterator, Callable, Optional
from unittest.mock import patch

import pytest
import pytest_asyncio

from fastmcp import Client

from mcp_server.connection import AbletonConnection
from tests.fixtures_remote import make_fake_ableton


@pytest_asyncio.fixture
async def mcp_client_factory() -> AsyncIterator[Callable]:
    """Yield a factory that opens an in-process fastmcp.Client against the
    real `mcp` app, with AbletonConnection.send_command/send_command_async
    patched at the class level to a FakeAbletonConnection's methods.

    Patching at the class level (not swapping the lifespan-context object)
    is necessary because mcp_server.server.lifespan() constructs its own
    ``AbletonConnection()`` instance internally — there is no seam to inject
    a different instance without either patching the class or monkeypatching
    the lifespan function itself. Class-level patching is the smaller,
    more surgical change and matches how test_bugfixes_*.py already patches
    AbletonConnection elsewhere in this suite.

    Usage:
        async def test_x(mcp_client_factory):
            async with mcp_client_factory({"get_track_info": ...}) as client:
                result = await client.call_tool("get_track_info", {...})
    """
    from mcp_server.server import mcp

    def _factory(overrides: Optional[dict] = None):
        fake = make_fake_ableton(overrides)
        patcher_sync = patch.object(AbletonConnection, "send_command", fake.send_command)
        patcher_async = patch.object(AbletonConnection, "send_command_async", fake.send_command_async)

        class _ClientContext:
            async def __aenter__(self):
                patcher_sync.start()
                patcher_async.start()
                self._client_cm = Client(mcp)
                client = await self._client_cm.__aenter__()
                client.fake_ableton = fake  # expose call log to the test
                return client

            async def __aexit__(self, exc_type, exc, tb):
                try:
                    await self._client_cm.__aexit__(exc_type, exc, tb)
                finally:
                    patcher_async.stop()
                    patcher_sync.stop()

        return _ClientContext()

    yield _factory


# ---------------------------------------------------------------------------
# Test isolation: fake `Live` / `remote_script` module injection
# ---------------------------------------------------------------------------

# Eight test files fake out Ableton's `Live` module and the `remote_script`
# package so the Remote Script handlers can be imported outside Ableton. They
# inject into sys.modules from inside test bodies, and most never remove what
# they injected — so whatever the last one wrote leaked into every test that
# ran afterwards.
#
# That is not merely untidy, it silently changes behaviour. The concrete bug
# (found 2026-07-31): `remote_script/LivePilot/version_detect.py` does
# `import Live` at module scope, which binds that module OBJECT permanently.
# `test_devices_duplicate_loading` deliberately injects a `Live` reporting
# 12.0.0, and leaves both it and the bound `version_detect` behind.
# `test_simpler_sample_native` then swaps in a 12.4.0 fake and clears
# version_detect's cached value — but `version_detect.Live` still points at
# the stale 12.0.0 object, so the version probe returned 12.0.0 and a
# `replace_sample_native` test failed with "requires Live 12.4+".
#
# It only reproduced under a partial run (`-k`), because a full run happened
# to select an earlier test in the class that re-imported version_detect
# first. So a green full suite was hiding it — which is the worst shape for
# this kind of bug.
#
# Restoring these two namespaces around every test removes the whole class:
# an injecting test can no longer reach the next one, whether or not its
# author remembered to clean up. Measured cost is ~0.07s across the suite.

_INJECTED_ROOTS = ("Live", "remote_script")


def _is_injected_module(name: str) -> bool:
    return any(name == root or name.startswith(root + ".") for root in _INJECTED_ROOTS)


@pytest.fixture(autouse=True)
def _restore_injected_modules():
    """Snapshot and restore faked `Live` / `remote_script` sys.modules entries.

    Restores by identity, not just by key: a test that REPLACES an existing
    entry (rather than adding one) must have the original object put back, or
    any module holding a `from X import Y` reference to it keeps the stale one.
    """
    saved = {k: v for k, v in sys.modules.items() if _is_injected_module(k)}
    try:
        yield
    finally:
        for key in [k for k in sys.modules if _is_injected_module(k)]:
            if key not in saved:
                del sys.modules[key]
        sys.modules.update(saved)
