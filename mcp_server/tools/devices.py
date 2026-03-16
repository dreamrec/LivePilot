"""Device MCP tools — parameters, racks, browser loading.

10 tools matching the Remote Script devices domain.
"""

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    """Extract AbletonConnection from lifespan context."""
    return ctx.lifespan_context["ableton"]


def _validate_track_index(track_index: int):
    if track_index < 0:
        raise ValueError("track_index must be >= 0")


def _validate_device_index(device_index: int):
    if device_index < 0:
        raise ValueError("device_index must be >= 0")


def _validate_chain_index(chain_index: int):
    if chain_index < 0:
        raise ValueError("chain_index must be >= 0")


@mcp.tool()
def get_device_info(ctx: Context, track_index: int, device_index: int) -> dict:
    """Get info about a device: name, class, type, active state, parameter count."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("get_device_info", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def get_device_parameters(ctx: Context, track_index: int, device_index: int) -> dict:
    """Get all parameters for a device with names, values, and ranges."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("get_device_parameters", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def set_device_parameter(
    ctx: Context,
    track_index: int,
    device_index: int,
    value: float,
    parameter_name: str | None = None,
    parameter_index: int | None = None,
) -> dict:
    """Set a device parameter by name or index."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if parameter_name is None and parameter_index is None:
        raise ValueError("Must provide parameter_name or parameter_index")
    if parameter_index is not None and parameter_index < 0:
        raise ValueError("parameter_index must be >= 0")
    params = {
        "track_index": track_index,
        "device_index": device_index,
        "value": value,
    }
    if parameter_name is not None:
        params["parameter_name"] = parameter_name
    if parameter_index is not None:
        params["parameter_index"] = parameter_index
    return _get_ableton(ctx).send_command("set_device_parameter", params)


@mcp.tool()
def batch_set_parameters(
    ctx: Context,
    track_index: int,
    device_index: int,
    parameters: list[dict],
) -> dict:
    """Set multiple device parameters in one call. Each entry: {name_or_index, value}."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    if not parameters:
        raise ValueError("parameters list cannot be empty")
    for entry in parameters:
        if "name_or_index" not in entry or "value" not in entry:
            raise ValueError("Each parameter must have 'name_or_index' and 'value'")
    return _get_ableton(ctx).send_command("batch_set_parameters", {
        "track_index": track_index,
        "device_index": device_index,
        "parameters": parameters,
    })


@mcp.tool()
def toggle_device(ctx: Context, track_index: int, device_index: int, active: bool) -> dict:
    """Enable or disable a device."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("toggle_device", {
        "track_index": track_index,
        "device_index": device_index,
        "active": active,
    })


@mcp.tool()
def delete_device(ctx: Context, track_index: int, device_index: int) -> dict:
    """Delete a device from a track. Use undo to revert if needed."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("delete_device", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def load_device_by_uri(ctx: Context, track_index: int, uri: str) -> dict:
    """Load a device onto a track using a browser URI string."""
    _validate_track_index(track_index)
    if not uri.strip():
        raise ValueError("URI cannot be empty")
    return _get_ableton(ctx).send_command("load_device_by_uri", {
        "track_index": track_index,
        "uri": uri,
    })


@mcp.tool()
def find_and_load_device(ctx: Context, track_index: int, device_name: str) -> dict:
    """Search the browser for a device by name and load it onto a track."""
    _validate_track_index(track_index)
    if not device_name.strip():
        raise ValueError("device_name cannot be empty")
    return _get_ableton(ctx).send_command("find_and_load_device", {
        "track_index": track_index,
        "device_name": device_name,
    })


@mcp.tool()
def get_rack_chains(ctx: Context, track_index: int, device_index: int) -> dict:
    """Get all chains in a rack device with volume, pan, mute, solo."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    return _get_ableton(ctx).send_command("get_rack_chains", {
        "track_index": track_index,
        "device_index": device_index,
    })


@mcp.tool()
def set_chain_volume(
    ctx: Context,
    track_index: int,
    device_index: int,
    chain_index: int,
    volume: float | None = None,
    pan: float | None = None,
) -> dict:
    """Set volume and/or pan for a chain in a rack device."""
    _validate_track_index(track_index)
    _validate_device_index(device_index)
    _validate_chain_index(chain_index)
    if volume is not None and not 0.0 <= volume <= 1.0:
        raise ValueError("volume must be between 0.0 and 1.0")
    if pan is not None and not -1.0 <= pan <= 1.0:
        raise ValueError("pan must be between -1.0 and 1.0")
    if volume is None and pan is None:
        raise ValueError("Must provide volume and/or pan")
    params = {
        "track_index": track_index,
        "device_index": device_index,
        "chain_index": chain_index,
    }
    if volume is not None:
        params["volume"] = volume
    if pan is not None:
        params["pan"] = pan
    return _get_ableton(ctx).send_command("set_chain_volume", params)
