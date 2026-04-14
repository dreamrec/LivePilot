"""FastMCP entry point for LivePilot."""

from contextlib import asynccontextmanager
import asyncio
import os
import subprocess

from fastmcp import FastMCP, Context  # noqa: F401

from .connection import AbletonConnection
from .m4l_bridge import SpectralCache, SpectralReceiver, M4LBridge


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
                except (subprocess.CalledProcessError, FileNotFoundError):
                    return str(pid)
        return None
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None


def _master_has_livepilot_analyzer(ableton: AbletonConnection) -> bool:
    """Check whether the analyzer device is currently on the master track."""
    try:
        track = ableton.send_command("get_master_track")
    except Exception:
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
    except Exception:
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
        if bridge_state["transport"] is not None:
            await _warm_analyzer_bridge(ableton, spectral)
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
        except Exception:
            pass


mcp = FastMCP("LivePilot", lifespan=lifespan)

# Import tool modules so they register with `mcp`
from .tools import transport    # noqa: F401, E402
from .tools import tracks       # noqa: F401, E402
from .tools import clips        # noqa: F401, E402
from .tools import notes        # noqa: F401, E402
from .tools import devices      # noqa: F401, E402
from .tools import scenes       # noqa: F401, E402
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
    """Get all registered tools, compatible with FastMCP 0.x and 3.x.

    WARNING: Accesses FastMCP private internals (_tool_manager, _local_provider).
    Pinned to fastmcp>=3.0.0,<3.3.0 in requirements.txt. If upgrading FastMCP,
    verify these attributes still exist or update this function.
    """
    # FastMCP 0.x: mcp._tool_manager._tools (dict of name -> Tool)
    if hasattr(mcp, "_tool_manager"):
        return list(mcp._tool_manager._tools.values())
    # FastMCP 3.x: mcp._local_provider._components (dict of key -> Tool)
    if hasattr(mcp, "_local_provider") and hasattr(mcp._local_provider, "_components"):
        return list(mcp._local_provider._components.values())
    import sys
    print(
        "LivePilot: WARNING — could not access FastMCP tool registry, "
        "string-to-number schema coercion will not work",
        file=sys.stderr,
    )
    return []


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


_patch_tool_schemas()


def main():
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
