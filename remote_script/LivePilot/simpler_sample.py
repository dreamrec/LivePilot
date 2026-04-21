# remote_script/LivePilot/simpler_sample.py
"""
LivePilot — Simpler sample replacement via the native Live 12.4 LOM API.

Exposes a ``replace_sample_native`` command that calls
``SimplerDevice.replace_sample(absolute_path)`` directly on the main thread.
Unlike the M4L-bridge path, this handler works on empty Simplers (the whole
reason 12.4 added the native API) and does not require a Max for Live
device in the Set.

Version-gated on ``replace_sample_native`` (12.4.0+). On earlier versions
the handler returns a STATE_ERROR; callers (MCP tools) are expected to
fall back to the bridge path.
"""

from .router import register
from .version_detect import has_feature, version_string


@register("replace_sample_native")
def replace_sample_native(song, params):
    """Replace the sample in a Simpler device using the Live 12.4+ native API.

    params dict keys:
        track_index (int): 0-based index into song.tracks.
        device_index (int): 0-based index into the track's devices.
        file_path (str): absolute path to the audio file to load.

    Returns on success:
        sample_loaded (bool): True.
        track_index (int): echoed from input.
        device_index (int): echoed from input.
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

    tracks = list(song.tracks)
    if track_index < 0 or track_index >= len(tracks):
        return {
            "error": "track_index " + str(track_index) + " out of range",
            "code": "INDEX_ERROR",
        }

    track = tracks[track_index]
    devices = list(track.devices)
    if device_index < 0 or device_index >= len(devices):
        return {
            "error": "device_index " + str(device_index) + " out of range",
            "code": "INDEX_ERROR",
        }

    device = devices[device_index]
    class_name = getattr(device, "class_name", "")
    if class_name != "SimplerDevice":
        return {
            "error": "Device at [" + str(track_index) + "][" + str(device_index) + "] is "
                     + class_name + ", not Simpler",
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
        "method": "native_12_4",
        "live_version": version_string(),
    }
