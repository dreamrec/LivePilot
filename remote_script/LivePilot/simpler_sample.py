# remote_script/LivePilot/simpler_sample.py
"""
LivePilot — Simpler sample replacement via the native Live 12.4 LOM API.

Exposes a ``replace_sample_native`` command that calls
``SimplerDevice.replace_sample(absolute_path)`` directly on the main thread.
Unlike the M4L-bridge path, this handler works on empty Simplers (the whole
reason 12.4 added the native API) and does not require a Max for Live
device in the Set.

Supports nested addressing into Drum Rack chains via the optional
``chain_index`` and ``nested_device_index`` parameters — this is how
BUG-#1 from docs/2026-04-22-bugs-discovered.md is unblocked. When
``chain_index`` is present, the device is resolved at
``track.devices[device_index].chains[chain_index].devices[nested_device_index]``.

Version-gated on ``replace_sample_native`` (12.4.0+). On earlier versions
the handler returns a STATE_ERROR; callers (MCP tools) are expected to
fall back to the bridge path.
"""

from .router import register
from .version_detect import has_feature, version_string


def _resolve_simpler_device(song, track_index, device_index, chain_index, nested_device_index):
    """Walk the device tree to the Simpler, supporting nested Drum Rack chains.

    Returns (device, error_dict). On success error_dict is None.
    When chain_index is None, returns the top-level device at device_index.
    When chain_index is provided, walks into the rack's chain and returns
    the device at nested_device_index (default 0) of that chain.
    """
    tracks = list(song.tracks)
    if track_index < 0 or track_index >= len(tracks):
        return None, {
            "error": "track_index " + str(track_index) + " out of range",
            "code": "INDEX_ERROR",
        }

    track = tracks[track_index]
    devices = list(track.devices)
    if device_index < 0 or device_index >= len(devices):
        return None, {
            "error": "device_index " + str(device_index) + " out of range",
            "code": "INDEX_ERROR",
        }

    top_device = devices[device_index]

    # Simple top-level path
    if chain_index is None:
        return top_device, None

    # Nested path — top device must be a rack (has `chains`)
    if not hasattr(top_device, "chains"):
        return None, {
            "error": (
                "Device at [" + str(track_index) + "][" + str(device_index) + "] "
                "is not a rack — chain_index is only valid for racks"
            ),
            "code": "INVALID_PARAM",
        }

    chains = list(top_device.chains)
    if chain_index < 0 or chain_index >= len(chains):
        return None, {
            "error": "chain_index " + str(chain_index) + " out of range ("
                     + str(len(chains)) + " chains)",
            "code": "INDEX_ERROR",
        }

    chain_devices = list(chains[chain_index].devices)
    nested_idx = 0 if nested_device_index is None else int(nested_device_index)
    if nested_idx < 0 or nested_idx >= len(chain_devices):
        return None, {
            "error": "nested_device_index " + str(nested_idx) + " out of range ("
                     + str(len(chain_devices)) + " devices in chain)",
            "code": "INDEX_ERROR",
        }

    return chain_devices[nested_idx], None


@register("replace_sample_native")
def replace_sample_native(song, params):
    """Replace the sample in a Simpler device using the Live 12.4+ native API.

    params dict keys:
        track_index (int): 0-based index into song.tracks.
        device_index (int): 0-based index into the track's devices.
        file_path (str): absolute path to the audio file to load.
        chain_index (int, optional): if the device_index points at a rack,
            walk into this chain before finding the Simpler. Unlocks
            Drum Rack pad-by-pad construction.
        nested_device_index (int, optional): device index WITHIN the chain
            (default 0 — first device in the chain).

    Returns on success:
        sample_loaded (bool): True.
        track_index (int): echoed from input.
        device_index (int): echoed from input.
        chain_index (int|None): echoed if nested.
        nested_device_index (int|None): echoed if nested.
        method (str): "native_12_4".
        live_version (str): detected Live version at call time.

    Returns on error:
        error (str): human-readable message.
        code (str): STATE_ERROR | INDEX_ERROR | INVALID_PARAM | INTERNAL.
    """
    if not has_feature("replace_sample_native"):
        return {
            "error": (
                "replace_sample_native requires Live 12.4+. "
                "Detected: " + version_string() + ". "
                "Use the M4L-bridge replace_simpler_sample path instead."
            ),
            "code": "STATE_ERROR",
        }

    try:
        track_index = int(params["track_index"])
        device_index = int(params["device_index"])
        file_path = str(params["file_path"])
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "error": "Invalid params: " + str(exc),
            "code": "INVALID_PARAM",
        }

    # Optional nested addressing
    chain_index = params.get("chain_index")
    nested_device_index = params.get("nested_device_index")
    if chain_index is not None:
        try:
            chain_index = int(chain_index)
        except (TypeError, ValueError):
            return {
                "error": "chain_index must be an integer if provided",
                "code": "INVALID_PARAM",
            }
    if nested_device_index is not None:
        try:
            nested_device_index = int(nested_device_index)
        except (TypeError, ValueError):
            return {
                "error": "nested_device_index must be an integer if provided",
                "code": "INVALID_PARAM",
            }

    device, err = _resolve_simpler_device(
        song, track_index, device_index, chain_index, nested_device_index,
    )
    if err is not None:
        return err

    class_name = getattr(device, "class_name", "")
    # Live's LOM exposes Simpler as class_name="OriginalSimpler" (not
    # "SimplerDevice") — see remote_script/LivePilot/devices.py:852 and
    # mcp_server/sample_engine/tools.py:501 for the same check elsewhere.
    if class_name != "OriginalSimpler":
        return {
            "error": (
                "Device at resolved path is " + class_name + ", not Simpler"
            ),
            "code": "INVALID_PARAM",
        }

    try:
        device.replace_sample(file_path)
    except Exception as exc:
        return {
            "error": "SimplerDevice.replace_sample failed: " + str(exc),
            "code": "INTERNAL",
        }

    return {
        "sample_loaded": True,
        "track_index": track_index,
        "device_index": device_index,
        "chain_index": chain_index,
        "nested_device_index": nested_device_index,
        "method": "native_12_4",
        "live_version": version_string(),
    }


@register("get_simpler_file_path")
def get_simpler_file_path(song, params):
    """Read the absolute file path of a Simpler's currently-loaded sample.

    Closes the v1.12 follow-up that left ``classify_simpler_slices`` unable
    to auto-resolve the WAV path: previously the call routed through the
    M4L bridge ``get_simpler_file_path`` case (added in v1.23.3 JS) but
    Live's M4L UDP response correlation produced wrong-data on the second
    successive bridge call (a chunked-response edge case under
    investigation in the bridge wire protocol). The Remote Script reads
    ``device.sample.file_path`` directly via Python LOM — no UDP, no Max
    JS, no chunk reassembly, no ambiguity.

    params dict keys:
        track_index (int): 0-based index into song.tracks.
        device_index (int): 0-based index into track.devices.
        chain_index (int|None): optional, for nested Drum Rack chains.
        nested_device_index (int|None): optional, position inside the chain.

    Returns on success:
        file_path (str): absolute filesystem path of the loaded sample.
        track_index, device_index, chain_index, nested_device_index: echoed.
        name (str): Simpler device name (typically the sample filename).

    Returns on error:
        error (str): human-readable message.
        code (str): STATE_ERROR | INDEX_ERROR | INVALID_PARAM.
    """
    try:
        track_index = int(params["track_index"])
        device_index = int(params["device_index"])
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "error": "Invalid params: " + str(exc),
            "code": "INVALID_PARAM",
        }

    chain_index = params.get("chain_index")
    nested_device_index = params.get("nested_device_index")
    if chain_index is not None:
        try:
            chain_index = int(chain_index)
        except (TypeError, ValueError):
            return {
                "error": "chain_index must be an integer if provided",
                "code": "INVALID_PARAM",
            }
    if nested_device_index is not None:
        try:
            nested_device_index = int(nested_device_index)
        except (TypeError, ValueError):
            return {
                "error": "nested_device_index must be an integer if provided",
                "code": "INVALID_PARAM",
            }

    device, err = _resolve_simpler_device(
        song, track_index, device_index, chain_index, nested_device_index,
    )
    if err is not None:
        return err

    class_name = getattr(device, "class_name", "")
    if class_name != "OriginalSimpler":
        return {
            "error": "Device at resolved path is " + class_name + ", not Simpler",
            "code": "INVALID_PARAM",
        }

    sample = getattr(device, "sample", None)
    if sample is None:
        return {
            "error": "Simpler has no sample loaded (device.sample is None)",
            "code": "STATE_ERROR",
        }

    file_path = getattr(sample, "file_path", None)
    if not file_path:
        return {
            "error": (
                "Simpler.sample.file_path is empty — sample may be embedded "
                "in the Set or otherwise lacks a filesystem path."
            ),
            "code": "STATE_ERROR",
        }

    name = getattr(device, "name", "")

    return {
        "file_path": str(file_path),
        "track_index": track_index,
        "device_index": device_index,
        "chain_index": chain_index,
        "nested_device_index": nested_device_index,
        "name": str(name),
    }
