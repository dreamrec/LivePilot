"""FastMCP entry point for LivePilot."""

from contextlib import asynccontextmanager
import asyncio
import logging
import os
import subprocess

from fastmcp import FastMCP, Context  # noqa: F401

from .connection import AbletonConnection
from .m4l_bridge import SpectralCache, SpectralReceiver, M4LBridge

# Logger must be defined before any function uses it — several module-level
# helpers below (e.g. _master_has_livepilot_analyzer) call logger.debug on
# the import-time code path, so defining logger later raised NameError when
# those helpers fired from a tool module's module-level init.
logger = logging.getLogger(__name__)


def _identify_port_holder(port: int) -> str | None:
    """Identify which process holds the given UDP port (for logging only).

    Returns a string like "PID 12345 (python3 mcp_server)" or None if
    identification fails. Never kills or modifies the holder.
    """
    try:
        out = subprocess.check_output(
            ["lsof", "-t", "-i", f"UDP:{port}"],
            text=True,
            timeout=3,
        ).strip()
        my_pid = os.getpid()
        for pid_str in out.splitlines():
            pid = int(pid_str)
            if pid != my_pid:
                try:
                    cmdline = subprocess.check_output(
                        ["ps", "-p", str(pid), "-o", "command="],
                        text=True, timeout=2,
                    ).strip()
                    return f"{pid} ({cmdline[:60]})"
                except (subprocess.CalledProcessError,
                        subprocess.TimeoutExpired,
                        FileNotFoundError):
                    return str(pid)
        return None
    except (subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
            ValueError):
        # TimeoutExpired catches the busy-system case where lsof exceeds
        # the 3-second budget; we treat it as "can't identify" and return
        # None so startup never stalls for slow host diagnostics.
        return None


def _check_remote_script_version(ableton: AbletonConnection) -> None:
    """BUG-A1: detect stale Remote Script installs at startup.

    The installed Remote Script is loaded by Ableton at its own launch time
    and cached in Python's module system — source-tree edits don't take
    effect until the user reinstalls + restarts Live. When the installed
    copy lags behind the MCP-server source, commands added after the install
    date (e.g. ``insert_device`` in v1.10.6) return "Unknown command type".

    This check pings the Remote Script, compares its reported version to
    the MCP server version, and logs a loud warning on mismatch. We don't
    abort — the server should still work for whatever handlers the older
    Remote Script does support — but we make the drift visible.
    """
    import sys

    try:
        from . import __version__ as mcp_version
    except ImportError:
        mcp_version = "unknown"

    try:
        pong = ableton.send_command("ping")
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).debug(
            "Remote Script version check failed: %s", exc,
        )
        return

    if not isinstance(pong, dict):
        return
    rs_version = pong.get("remote_script_version")
    if rs_version is None:
        # Remote Script is old enough that it doesn't even embed its version
        # in ping responses — definitely stale.
        msg = (
            "LivePilot: Remote Script is out of date (pre-version-handshake). "
            "Run 'npx livepilot --install' and restart Ableton Live to fix "
            "'Unknown command type' errors for newer tools (insert_device, "
            "set_clip_pitch, etc)."
        )
        print(msg, file=sys.stderr)
        return

    if str(rs_version) != str(mcp_version):
        msg = (
            f"LivePilot: Remote Script version {rs_version} does not match "
            f"MCP server version {mcp_version}. Newer tools may fail with "
            f"'Unknown command type'. Run 'npx livepilot --install' and "
            f"restart Ableton Live to resync."
        )
        print(msg, file=sys.stderr)


def _master_has_livepilot_analyzer(ableton: AbletonConnection) -> bool:
    """Check whether the analyzer device is currently on the master track."""
    try:
        track = ableton.send_command("get_master_track")
    except Exception as exc:
        logger.debug("_master_has_livepilot_analyzer failed: %s", exc)
        return False
    devices = track.get("devices", []) if isinstance(track, dict) else []
    for device in devices:
        normalized = " ".join(
            str(device.get("name") or "").replace("_", " ").replace("-", " ").lower().split()
        )
        if normalized == "livepilot analyzer":
            return True
    return False


async def _warm_analyzer_bridge(
    ableton: AbletonConnection,
    spectral: SpectralCache,
    timeout: float = 3.0,
) -> None:
    """Give the analyzer stream a short startup window before first use."""
    if not _master_has_livepilot_analyzer(ableton):
        return

    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(timeout, 0.0)
    while loop.time() < deadline:
        if spectral.is_connected:
            return
        await asyncio.sleep(0.05)


def _bind_session_continuity(ableton: AbletonConnection) -> None:
    """Hydrate the session-continuity tracker from persistent per-project state.

    Fetches a minimal session fingerprint (tempo, signature, track/scene
    layout) from the Remote Script, computes a project hash, and asks the
    tracker to bind the matching ProjectStore + restore any previously-saved
    creative threads and turn resolutions from disk.

    Never raises: startup must succeed even if Ableton isn't reachable. In
    that case, the tracker stays in-memory and the first ``record_turn_*`` /
    ``open_thread`` call will lazy-bind via ``ensure_project_store_bound()``.
    """
    try:
        from .session_continuity.tracker import bind_project_store_from_session

        info = ableton.send_command("get_session_info")
        if isinstance(info, dict) and not info.get("error"):
            bind_project_store_from_session(info)
    except Exception as exc:
        logger.debug("_bind_session_continuity: lazy-bind (reason: %s)", exc)


@asynccontextmanager
async def lifespan(server):
    """Create and yield the shared AbletonConnection + M4L bridge + registries."""
    from .runtime.mcp_dispatch import build_mcp_dispatch_registry
    from .splice_client.client import SpliceGRPCClient

    ableton = AbletonConnection()
    spectral = SpectralCache()
    receiver = SpectralReceiver(spectral)
    m4l = M4LBridge(spectral, receiver)
    mcp_dispatch = build_mcp_dispatch_registry()

    # Splice gRPC client — graceful degradation if Splice desktop isn't
    # running or grpcio isn't installed. .connected will be False in that
    # case and sample_resolver treats it as "no splice hits".
    splice_client = SpliceGRPCClient()
    try:
        await splice_client.connect()
    except Exception as exc:
        logger.debug("lifespan failed: %s", exc)
        pass  # client remains in disconnected state

    # Start UDP listener for incoming M4L spectral data (port 9880)
    loop = asyncio.get_running_loop()
    transport = None
    try:
        transport, _ = await loop.create_datagram_endpoint(
            lambda: receiver,
            local_addr=('127.0.0.1', 9880),
        )
    except OSError:
        # Port 9880 already bound — another LivePilot instance is running.
        # Degrade gracefully. The reconnect_bridge tool can retry later
        # if the other instance is stopped.
        import sys
        holder_info = _identify_port_holder(9880)
        print(
            "LivePilot: UDP port 9880 already in use%s — "
            "analyzer/bridge tools unavailable at startup. "
            "Use the reconnect_bridge tool after stopping the other instance, "
            "or restart this server."
            % (f" (PID {holder_info})" if holder_info else ""),
            file=sys.stderr,
        )
        transport = None

    # Store transport + loop so tools can attempt reconnection mid-session
    bridge_state = {
        "transport": transport,
        "loop": loop,
        "receiver": receiver,
    }

    try:
        # BUG-A1: detect stale Remote Script installs early so the user
        # sees a clear message instead of cryptic "Unknown command type" errors.
        _check_remote_script_version(ableton)
        if bridge_state["transport"] is not None:
            await _warm_analyzer_bridge(ableton, spectral)
        # Bind per-project persistent store so creative threads and turn
        # history survive server restarts. Until v1.10.9 this was plumbed
        # through the tracker but never called — threads/turns were effectively
        # in-memory only. If Ableton isn't reachable yet, tools will lazy-bind
        # on first write via ensure_project_store_bound().
        _bind_session_continuity(ableton)
        yield {
            "ableton": ableton,
            "spectral": spectral,
            "m4l": m4l,
            "_bridge_state": bridge_state,
            "mcp_dispatch": mcp_dispatch,
            "splice_client": splice_client,
        }
    finally:
        if bridge_state["transport"]:
            bridge_state["transport"].close()
        m4l.close()
        ableton.disconnect()
        try:
            await splice_client.disconnect()
        except Exception as exc:
            logger.debug("lifespan failed: %s", exc)
mcp = FastMCP("LivePilot", lifespan=lifespan)

# Import tool modules so they register with `mcp`
from .tools import transport    # noqa: F401, E402
from .tools import tracks       # noqa: F401, E402
from .tools import clips        # noqa: F401, E402
from .tools import notes        # noqa: F401, E402
from .tools import devices      # noqa: F401, E402
from .tools import scenes       # noqa: F401, E402
from .tools import scales       # noqa: F401, E402
from .tools import follow_actions  # noqa: F401, E402
from .tools import grooves      # noqa: F401, E402
from .tools import take_lanes   # noqa: F401, E402
from .tools import mixing       # noqa: F401, E402
from .tools import browser      # noqa: F401, E402
from .tools import arrangement  # noqa: F401, E402
from .tools import memory       # noqa: F401, E402
from .tools import analyzer     # noqa: F401, E402
from .tools import automation   # noqa: F401, E402
from .tools import theory       # noqa: F401, E402
from .tools import generative   # noqa: F401, E402
from .tools import harmony      # noqa: F401, E402
from .tools import midi_io      # noqa: F401, E402
from .tools import perception   # noqa: F401, E402
from .tools import agent_os     # noqa: F401, E402
from .tools import composition  # noqa: F401, E402
from .tools import motif         # noqa: F401, E402
from .tools import research      # noqa: F401, E402
from .tools import planner       # noqa: F401, E402
from .project_brain import tools as project_brain_tools  # noqa: F401, E402
from .runtime import tools as runtime_tools              # noqa: F401, E402
from .runtime import action_tools as action_ledger_tools  # noqa: F401, E402
from .evaluation import tools as evaluation_tools  # noqa: F401, E402
from .memory import tools as memory_fabric_tools   # noqa: F401, E402
from .mix_engine import tools as mix_engine_tools  # noqa: F401, E402
from .sound_design import tools as sound_design_tools      # noqa: F401, E402
from .transition_engine import tools as transition_tools   # noqa: F401, E402
from .reference_engine import tools as reference_tools     # noqa: F401, E402
from .translation_engine import tools as translation_tools  # noqa: F401, E402
from .performance_engine import tools as performance_tools  # noqa: F401, E402
from .runtime import safety_tools  # noqa: F401, E402
from .semantic_moves import tools as semantic_move_tools  # noqa: F401, E402
from .experiment import tools as experiment_tools         # noqa: F401, E402
from .musical_intelligence import tools as musical_intel_tools  # noqa: F401, E402
from .song_brain import tools as song_brain_tools              # noqa: F401, E402
from .preview_studio import tools as preview_studio_tools      # noqa: F401, E402
from .hook_hunter import tools as hook_hunter_tools            # noqa: F401, E402
from .stuckness_detector import tools as stuckness_tools       # noqa: F401, E402
from .wonder_mode import tools as wonder_mode_tools            # noqa: F401, E402
from .session_continuity import tools as session_cont_tools    # noqa: F401, E402
from .creative_constraints import tools as constraints_tools   # noqa: F401, E402
from .device_forge import tools as device_forge_tools          # noqa: F401, E402
from .sample_engine import tools as sample_engine_tools        # noqa: F401, E402
from .atlas import tools as atlas_tools                        # noqa: F401, E402
from .composer import tools as composer_tools                  # noqa: F401, E402
from .tools import diagnostics   # noqa: F401, E402

# ---------------------------------------------------------------------------
# Schema coercion patch — accept strings for numeric parameters
# ---------------------------------------------------------------------------
# Some MCP clients (with deferred tools) send all parameter
# values as strings.  Their client-side Zod validators reject "0" against
# {"type": "integer"} before the request even reaches our server.
#
# Fix: widen every integer/number property in the advertised JSON Schema to
# also accept strings.  Server-side Pydantic validation (lax mode) coerces
# "5" → 5 and "0.75" → 0.75 automatically, so no tool code changes needed.
# ---------------------------------------------------------------------------


def _coerce_schema_property(prop: dict) -> None:
    """Widen a single JSON Schema property to also accept strings."""
    if prop.get("type") in ("integer", "number") and "anyOf" not in prop:
        original_type = prop.pop("type")
        prop["anyOf"] = [{"type": original_type}, {"type": "string"}]
    elif "anyOf" in prop:
        # Skip if this anyOf was already coerced (contains both a numeric and string type)
        variant_types = {v.get("type") for v in prop["anyOf"] if isinstance(v, dict)}
        if "string" in variant_types and variant_types & {"integer", "number"}:
            return
        for variant in prop["anyOf"]:
            if isinstance(variant, dict):
                _coerce_schema_property(variant)
    # Recurse into array items so list[int]/list[float] params also accept strings
    if "items" in prop and isinstance(prop["items"], dict):
        _coerce_schema_property(prop["items"])
    if "properties" in prop and isinstance(prop["properties"], dict):
        for nested in prop["properties"].values():
            if isinstance(nested, dict):
                _coerce_schema_property(nested)
    if "$defs" in prop and isinstance(prop["$defs"], dict):
        for nested in prop["$defs"].values():
            if isinstance(nested, dict):
                _coerce_schema_property(nested)


def _get_all_tools():
    """Get all registered tools — defends against FastMCP internal drift.

    FastMCP's public API doesn't expose the registry as of 3.2.x (see
    docs/FASTMCP_UPSTREAM_FR.md). Until it does, we probe known internal
    attribute paths. Each probe fires in try/except so a structural
    rearrangement (e.g. ``_components`` renamed under 3.3+) falls through
    to the next path rather than exploding.

    WARNING: Accesses FastMCP private internals. Pinned to
    fastmcp>=3.0.0,<3.3.0 in requirements.txt. The startup self-test
    (_assert_tool_registry_accessible) will fail loudly if every probe
    returns empty — better than silently returning [] and disabling
    schema coercion.
    """
    probes = [
        # FastMCP 0.x: mcp._tool_manager._tools (dict of name -> Tool)
        ("_tool_manager._tools", lambda: list(mcp._tool_manager._tools.values())),
        # FastMCP 3.0–3.2: mcp._local_provider._components
        (
            "_local_provider._components",
            lambda: list(mcp._local_provider._components.values()),
        ),
        # FastMCP 3.3+ speculative: mcp._local_provider._tools (anticipated
        # rename based on naming conventions in other providers). Kept here
        # so a future bump surfaces a partial match rather than a full miss.
        (
            "_local_provider._tools",
            lambda: list(mcp._local_provider._tools.values()),
        ),
        # Public-API future path (what we're asking for in the upstream FR);
        # harmless to probe now so that once it ships we can lift the ceiling
        # without touching this function again.
        ("list_tools", lambda: list(mcp.list_tools())),
    ]
    for label, fn in probes:
        try:
            tools = fn()
        except (AttributeError, TypeError):
            continue
        except Exception:  # noqa: BLE001 — any error from an internal probe means "skip"
            continue
        if tools:
            return tools

    # All probes empty. Surface fastmcp version + attempted paths so the
    # breakage is diagnosable without re-reading the code.
    import sys
    try:
        import fastmcp as _fm
        fm_version = getattr(_fm, "__version__", "unknown")
    except Exception:  # noqa: BLE001
        fm_version = "unknown"
    print(
        "LivePilot: ERROR — could not access FastMCP tool registry "
        f"(fastmcp=={fm_version}). Tried: "
        + ", ".join(label for label, _ in probes)
        + ". Schema coercion and tool-catalog generation will be broken. "
        "If FastMCP updated its internals, see docs/FASTMCP_UPSTREAM_FR.md.",
        file=sys.stderr,
    )
    return []


def _assert_tool_registry_accessible() -> None:
    """Loudly fail startup if the FastMCP registry probe returns nothing.

    Called once at module import, just before schema patching. The schema
    patch silently no-ops on an empty registry, so without this assertion
    a FastMCP-internals rename would degrade silently and produce a server
    with 324 tools but no string-to-number coercion — a subtle, hard-to-
    diagnose class of failure we've paid for once already.

    Reads the expected count from ``tests/test_tools_contract.py`` (same
    source of truth sync_metadata.py uses), so no second magic number.
    """
    import re
    import sys

    try:
        contract_src = (
            (__file__.rsplit("/", 2)[0] + "/tests/test_tools_contract.py")
            if "__file__" in globals() else None
        )
        # Prefer an absolute path via Path for reliability:
        from pathlib import Path
        contract_path = Path(__file__).resolve().parents[1] / "tests" / "test_tools_contract.py"
        expected = None
        if contract_path.exists():
            match = re.search(
                r"assert len\(tools\) == (\d+)",
                contract_path.read_text(encoding="utf-8"),
            )
            if match:
                expected = int(match.group(1))
    except Exception:  # noqa: BLE001 — self-test must not block startup
        expected = None

    actual = len(_get_all_tools())
    if actual == 0:
        # Registry probe returned empty — this is the regression the test guards.
        # Don't sys.exit (some test harnesses import server.py without a live
        # FastMCP); print a loud diagnostic and let downstream code react.
        print(
            "LivePilot: STARTUP SELF-TEST FAILED — _get_all_tools() returned 0. "
            "FastMCP internals likely changed. Verify requirements.txt pin "
            "(fastmcp>=3.0.0,<3.3.0) matches the installed version.",
            file=sys.stderr,
        )
        return
    if expected is not None and actual != expected:
        print(
            f"LivePilot: STARTUP SELF-TEST WARNING — _get_all_tools() "
            f"returned {actual} tools, tests/test_tools_contract.py expects "
            f"{expected}. If you've added/removed tools, update the contract "
            "and run scripts/sync_metadata.py --fix.",
            file=sys.stderr,
        )


def _patch_tool_schemas() -> None:
    """Post-process all registered tool schemas for string coercion."""
    for tool in _get_all_tools():
        props = tool.parameters.get("properties", {})
        for name, prop in props.items():
            if name == "ctx":
                continue  # skip the Context parameter
            _coerce_schema_property(prop)
        for definition in tool.parameters.get("$defs", {}).values():
            if isinstance(definition, dict):
                _coerce_schema_property(definition)

_assert_tool_registry_accessible()
_patch_tool_schemas()


def main():
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
