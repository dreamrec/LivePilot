"""Run offline DSP in a disposable process, away from the MCP transport.

A stuck native import/DSP call must have a finite lifetime. AnyIO owns and
reaps the child on timeout or cancellation, including Windows stdio sessions.
Only the six fixed offline entry points below can be dispatched.
"""
from __future__ import annotations

import functools
import inspect
import json
import logging
import os
from pathlib import Path
import sys

import anyio

logger = logging.getLogger(__name__)
OPERATIONS = {
    "analyze_loudness": "mcp_server.tools.perception",
    "analyze_spectrum_offline": "mcp_server.tools.perception",
    "compare_to_reference": "mcp_server.tools.perception",
    "read_audio_metadata": "mcp_server.tools.perception",
    "listen_capture": "mcp_server.listening.tools",
    "listen_ab": "mcp_server.listening.tools",
}
DEFAULT_TIMEOUT = 120.0


async def run_offline_analysis(operation: str, arguments: dict, *, timeout=None) -> dict:
    if operation not in OPERATIONS:
        raise ValueError(f"Unknown offline analysis operation: {operation}")
    if timeout is None:
        # Optional model download + first CLAP load needs a larger cold budget.
        timeout = 600.0 if arguments.get("embed") else DEFAULT_TIMEOUT
    env = os.environ.copy()
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "NUMBA_NUM_THREADS"):
        env[key] = "1"
    # Keep the MCP stdio channel exclusively owned by the parent. The worker's
    # stdout is a private pipe; diagnostics go to stderr, never the MCP stream.
    command = [sys.executable, "-m", "mcp_server.runtime.offline_worker"]
    try:
        with anyio.fail_after(timeout):
            process = await anyio.run_process(
                command,
                input=json.dumps({"operation": operation, "arguments": arguments}).encode("utf-8"),
                cwd=str(Path(__file__).resolve().parents[2]),
                env=env,
                check=False,
            )
    except TimeoutError:
        return {"error": f"Offline analysis '{operation}' timed out after {timeout:g}s; worker stopped.",
                "code": "TIMEOUT"}
    if process.returncode:
        logger.warning("Offline worker %s exited %s: %s", operation,
                       process.returncode, process.stderr.decode("utf-8", errors="replace")[-2000:])
        return {"error": f"Offline analysis '{operation}' worker failed (exit {process.returncode}).",
                "code": "INTERNAL"}
    try:
        return json.loads(process.stdout)
    except (ValueError, UnicodeError):
        return {"error": f"Offline analysis '{operation}' worker returned invalid JSON.",
                "code": "INTERNAL"}


def isolated_analysis(fn):
    """Keep the synchronous engine available as __wrapped__ for local callers.

    The registered MCP callable is async, so native work cannot hold its
    request loop or its shared thread pool hostage.
    """
    signature = inspect.signature(fn)

    @functools.wraps(fn)
    async def isolated(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        return await run_offline_analysis(fn.__name__, dict(bound.arguments))

    return isolated
