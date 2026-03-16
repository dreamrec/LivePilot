"""
LivePilot - Device domain handlers (10 commands).
"""

from .router import register
from .utils import get_track, get_device


@register("get_device_info")
def get_device_info(song, params):
    """Return detailed info for a single device."""
    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    track = get_track(song, track_index)
    device = get_device(track, device_index)

    result = {
        "name": device.name,
        "class_name": device.class_name,
        "is_active": device.is_active,
        "can_have_chains": device.can_have_chains,
        "parameter_count": len(list(device.parameters)),
    }
    try:
        result["type"] = device.type
    except Exception:
        result["type"] = None
    return result


@register("get_device_parameters")
def get_device_parameters(song, params):
    """Return all parameters for a device."""
    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    track = get_track(song, track_index)
    device = get_device(track, device_index)

    parameters = []
    for i, param in enumerate(device.parameters):
        parameters.append({
            "index": i,
            "name": param.name,
            "value": param.value,
            "min": param.min,
            "max": param.max,
            "is_quantized": param.is_quantized,
            "value_string": str(param),
        })
    return {"parameters": parameters}


@register("set_device_parameter")
def set_device_parameter(song, params):
    """Set a single device parameter by name or index."""
    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    value = float(params["value"])
    track = get_track(song, track_index)
    device = get_device(track, device_index)

    parameter_name = params.get("parameter_name", None)
    parameter_index = params.get("parameter_index", None)

    if parameter_name is not None:
        param = None
        for p in device.parameters:
            if p.name == parameter_name:
                param = p
                break
        if param is None:
            raise ValueError(
                "Parameter '%s' not found on device '%s'"
                % (parameter_name, device.name)
            )
    elif parameter_index is not None:
        parameter_index = int(parameter_index)
        dev_params = list(device.parameters)
        if parameter_index < 0 or parameter_index >= len(dev_params):
            raise IndexError(
                "Parameter index %d out of range (0..%d)"
                % (parameter_index, len(dev_params) - 1)
            )
        param = dev_params[parameter_index]
    else:
        raise ValueError("Must provide parameter_name or parameter_index")

    param.value = value
    return {"name": param.name, "value": param.value}


@register("batch_set_parameters")
def batch_set_parameters(song, params):
    """Set multiple device parameters in one call."""
    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    parameters = params["parameters"]
    track = get_track(song, track_index)
    device = get_device(track, device_index)

    dev_params = list(device.parameters)
    results = []
    for entry in parameters:
        value = float(entry["value"])
        name_or_index = entry.get("name_or_index")

        if isinstance(name_or_index, int) or (
            isinstance(name_or_index, str) and name_or_index.isdigit()
        ):
            idx = int(name_or_index)
            if idx < 0 or idx >= len(dev_params):
                raise IndexError(
                    "Parameter index %d out of range (0..%d)"
                    % (idx, len(dev_params) - 1)
                )
            param = dev_params[idx]
        else:
            param = None
            for p in dev_params:
                if p.name == name_or_index:
                    param = p
                    break
            if param is None:
                raise ValueError(
                    "Parameter '%s' not found on device '%s'"
                    % (name_or_index, device.name)
                )

        param.value = value
        results.append({"name": param.name, "value": param.value})

    return {"parameters": results}


@register("toggle_device")
def toggle_device(song, params):
    """Enable or disable a device (parameter 0 is always on/off)."""
    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    active = bool(params["active"])
    track = get_track(song, track_index)
    device = get_device(track, device_index)
    device.parameters[0].value = 1.0 if active else 0.0
    return {"name": device.name, "is_active": device.parameters[0].value}


@register("delete_device")
def delete_device(song, params):
    """Delete a device from a track."""
    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    track = get_track(song, track_index)
    # Validate device exists
    get_device(track, device_index)
    track.delete_device(device_index)
    return {"deleted": device_index}


@register("load_device_by_uri")
def load_device_by_uri(song, params):
    """Load a device onto a track using a browser URI."""
    track_index = int(params["track_index"])
    uri = str(params["uri"])
    track = get_track(song, track_index)

    try:
        browser = song.browser
        browser.load_item_by_uri(uri, track)
    except Exception as e:
        raise RuntimeError(
            "Failed to load device by URI '%s': %s" % (uri, str(e))
        )
    return {"loaded": uri, "track_index": track_index}


@register("find_and_load_device")
def find_and_load_device(song, params):
    """Find a device by name in the browser and load it onto a track."""
    track_index = int(params["track_index"])
    device_name = str(params["device_name"]).lower()
    track = get_track(song, track_index)
    browser = song.browser

    MAX_ITERATIONS = 500
    iterations = 0

    def search_children(item, depth=0):
        """Recursively search browser children up to depth 4."""
        nonlocal iterations
        if depth > 4:
            return None
        try:
            children = list(item.children)
        except Exception:
            return None
        for child in children:
            iterations += 1
            if iterations > MAX_ITERATIONS:
                return None
            if child.name.lower() == device_name:
                if child.is_loadable:
                    return child
            result = search_children(child, depth + 1)
            if result is not None:
                return result
        return None

    categories = []
    try:
        categories.append(browser.instruments)
    except Exception:
        pass
    try:
        categories.append(browser.audio_effects)
    except Exception:
        pass
    try:
        categories.append(browser.midi_effects)
    except Exception:
        pass

    for category in categories:
        found = search_children(category)
        if found is not None:
            # Select the target track so the item loads onto it
            song.view.selected_track = track
            browser.load_item(found)
            return {
                "loaded": found.name,
                "track_index": track_index,
            }

    raise ValueError(
        "Device '%s' not found in browser. Check spelling or use "
        "load_device_by_uri with an exact URI." % params["device_name"]
    )


@register("get_rack_chains")
def get_rack_chains(song, params):
    """Return chain info for a rack device."""
    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    track = get_track(song, track_index)
    device = get_device(track, device_index)

    if not device.can_have_chains:
        raise ValueError(
            "Device '%s' is not a rack and cannot have chains" % device.name
        )

    chains = []
    for i, chain in enumerate(device.chains):
        chain_info = {
            "index": i,
            "name": chain.name,
            "volume": chain.mixer_device.volume.value,
            "pan": chain.mixer_device.panning.value,
            "mute": chain.mute,
            "solo": chain.solo,
        }
        chains.append(chain_info)
    return {"chains": chains}


@register("set_chain_volume")
def set_chain_volume(song, params):
    """Set volume and/or pan for a rack chain."""
    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    chain_index = int(params["chain_index"])
    track = get_track(song, track_index)
    device = get_device(track, device_index)

    if not device.can_have_chains:
        raise ValueError(
            "Device '%s' is not a rack and cannot have chains" % device.name
        )

    chains = list(device.chains)
    if chain_index < 0 or chain_index >= len(chains):
        raise IndexError(
            "Chain index %d out of range (0..%d)"
            % (chain_index, len(chains) - 1)
        )
    chain = chains[chain_index]

    if "volume" in params:
        chain.mixer_device.volume.value = float(params["volume"])
    if "pan" in params:
        chain.mixer_device.panning.value = float(params["pan"])

    return {
        "index": chain_index,
        "name": chain.name,
        "volume": chain.mixer_device.volume.value,
        "pan": chain.mixer_device.panning.value,
    }
