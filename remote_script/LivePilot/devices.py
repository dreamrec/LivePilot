"""
LivePilot - Device domain handlers (11 commands).
"""

import Live
from collections import deque

from .router import register
from .utils import get_track, get_device


def _get_browser():
    """Get the browser from the Application object (not Song)."""
    return Live.Application.get_application().browser


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
    except AttributeError:
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
            "value_string": param.str_for_value(param.value),
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
        # Try exact match first
        for p in device.parameters:
            if p.name == parameter_name:
                param = p
                break
        # Fallback: case-insensitive match
        if param is None:
            target_lower = parameter_name.lower()
            for p in device.parameters:
                if p.name.lower() == target_lower:
                    param = p
                    break
        if param is None:
            available = [p.name for p in list(device.parameters)[:20]]
            raise ValueError(
                "Parameter '%s' not found on device '%s'. "
                "Available (first 20): %s"
                % (parameter_name, device.name, ", ".join(available))
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
            target = str(name_or_index)
            # Try exact match first
            for p in dev_params:
                if p.name == target:
                    param = p
                    break
            # Fallback: case-insensitive match
            if param is None:
                target_lower = target.lower()
                for p in dev_params:
                    if p.name.lower() == target_lower:
                        param = p
                        break
            if param is None:
                # List similar parameter names for debugging
                available = [p.name for p in dev_params[:20]]
                raise ValueError(
                    "Parameter '%s' not found on device '%s'. "
                    "Available (first 20): %s"
                    % (name_or_index, device.name, ", ".join(available))
                )

        param.value = value
        results.append({"name": param.name, "value": param.value})

    return {"parameters": results}


@register("toggle_device")
def toggle_device(song, params):
    """Enable or disable a device."""
    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    active = bool(params["active"])
    track = get_track(song, track_index)
    device = get_device(track, device_index)

    # Find the "Device On" parameter by name (safer than assuming index 0)
    on_param = None
    for p in device.parameters:
        if p.name == "Device On":
            on_param = p
            break
    if on_param is None:
        # Fallback to parameter 0 for devices that don't use "Device On"
        if not list(device.parameters):
            raise ValueError("Device '%s' has no parameters to toggle" % device.name)
        on_param = device.parameters[0]

    on_param.value = 1.0 if active else 0.0
    return {"name": device.name, "is_active": on_param.value > 0.5}


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
    """Load a device onto a track using a browser URI.

    First tries URI-based matching (exact child.uri comparison).
    Falls back to name extraction from the URI's last path segment.
    Searches all browser categories including user_library and samples.
    """
    track_index = int(params["track_index"])
    uri = str(params["uri"])
    track = get_track(song, track_index)
    browser = _get_browser()

    # Parse category hint from URI (e.g., "query:Drums#..." -> prioritize drums)
    _category_map = {
        "drums": "drums", "samples": "samples", "instruments": "instruments",
        "audiofx": "audio_effects", "audio_effects": "audio_effects",
        "midifx": "midi_effects", "midi_effects": "midi_effects",
        "sounds": "sounds", "packs": "packs",
        "userlibrary": "user_library", "user_library": "user_library",
    }
    priority_attr = None
    if ":" in uri:
        # Extract category from "query:Drums#..." or "query:UserLibrary#..."
        after_colon = uri.split(":", 1)[1]
        cat_hint = after_colon.split("#", 1)[0].lower().replace(" ", "_")
        priority_attr = _category_map.get(cat_hint)

    # Build category search order — prioritize the category from the URI
    category_attrs = [
        "user_library", "plugins", "max_for_live", "samples",
        "instruments", "audio_effects", "midi_effects", "packs",
        "sounds", "drums",
    ]
    if priority_attr and priority_attr in category_attrs:
        category_attrs.remove(priority_attr)
        category_attrs.insert(0, priority_attr)

    categories = []
    for attr in category_attrs:
        try:
            categories.append(getattr(browser, attr))
        except AttributeError:
            pass

    _iterations = [0]
    MAX_ITERATIONS = 50000

    # ── Strategy 1: match by URI directly ────────────────────────────
    def find_by_uri(parent, target_uri, depth=0):
        if depth > 8 or _iterations[0] > MAX_ITERATIONS:
            return None
        try:
            children = list(parent.children)
        except AttributeError:
            return None
        for child in children:
            _iterations[0] += 1
            if _iterations[0] > MAX_ITERATIONS:
                return None
            try:
                if child.uri == target_uri and child.is_loadable:
                    return child
            except AttributeError:
                pass
            result = find_by_uri(child, target_uri, depth + 1)
            if result is not None:
                return result
        return None

    for category in categories:
        _iterations[0] = 0  # Reset counter per category to avoid premature cutoff
        found = find_by_uri(category, uri)
        if found is not None:
            song.view.selected_track = track
            browser.load_item(found)
            return {"loaded": found.name, "track_index": track_index}

    # ── Strategy 2: extract name from URI, search by name ────────────
    device_name = uri
    if "#" in uri:
        device_name = uri.split("#", 1)[1]
    # For Sounds URIs like "Pad:FileId_6343", the FileId is an internal
    # identifier useless for name search — retry URI match with deep limit.
    if "FileId_" in device_name:
        _iterations[0] = 0
        DEEP_MAX = 200000
        def find_by_uri_deep(parent, target_uri, depth=0):
            if depth > 12 or _iterations[0] > DEEP_MAX:
                return None
            try:
                children = list(parent.children)
            except AttributeError:
                return None
            for child in children:
                _iterations[0] += 1
                if _iterations[0] > DEEP_MAX:
                    return None
                try:
                    if child.uri == target_uri and child.is_loadable:
                        return child
                except AttributeError:
                    pass
                result = find_by_uri_deep(child, target_uri, depth + 1)
                if result is not None:
                    return result
            return None

        for category in categories:
            _iterations[0] = 0
            found = find_by_uri_deep(category, uri)
            if found is not None:
                song.view.selected_track = track
                browser.load_item(found)
                return {"loaded": found.name, "track_index": track_index}

        raise ValueError(
            "Item '%s' not found in browser (FileId URI — try "
            "find_and_load_device with the exact name instead)" % uri
        )

    for sep in (":", "/"):
        if sep in device_name:
            device_name = device_name.rsplit(sep, 1)[1]
    # URL-decode
    try:
        from urllib.parse import unquote
        device_name = unquote(device_name)
    except ImportError:
        device_name = device_name.replace("%20", " ")
    # Strip file extensions
    for ext in (".amxd", ".adv", ".adg", ".aupreset", ".als", ".wav", ".aif", ".aiff", ".mp3"):
        if device_name.lower().endswith(ext):
            device_name = device_name[:-len(ext)]
            break

    target = device_name.lower()
    _iterations[0] = 0

    def find_by_name(parent, depth=0):
        if depth > 8 or _iterations[0] > MAX_ITERATIONS:
            return None
        try:
            children = list(parent.children)
        except AttributeError:
            return None
        for child in children:
            _iterations[0] += 1
            if _iterations[0] > MAX_ITERATIONS:
                return None
            child_lower = child.name.lower()
            if (child_lower == target or target in child_lower) and child.is_loadable:
                return child
            result = find_by_name(child, depth + 1)
            if result is not None:
                return result
        return None

    for category in categories:
        found = find_by_name(category)
        if found is not None:
            song.view.selected_track = track
            browser.load_item(found)
            return {"loaded": found.name, "track_index": track_index}

    raise ValueError(
        "Device '%s' not found in browser" % device_name
    )


@register("find_and_load_device")
def find_and_load_device(song, params):
    """Find a device by name in the browser and load it onto a track.

    Searches all browser categories including user_library for M4L devices.
    Supports partial matching: 'Kickster' matches 'trnr.Kickster'.
    """
    track_index = int(params["track_index"])
    device_name = str(params["device_name"]).lower()
    track = get_track(song, track_index)
    browser = _get_browser()

    MAX_ITERATIONS = 50000
    iterations = 0

    def _name_matches(child_name, target, exact_only):
        """Check if a browser item name matches the search target."""
        child_lower = child_name.lower()
        # Strip extension for comparison
        child_base = child_lower
        for ext in (".amxd", ".adv", ".adg", ".aupreset", ".als"):
            if child_base.endswith(ext):
                child_base = child_base[:-len(ext)]
                break
        if exact_only:
            return child_base == target
        else:
            return child_base == target or target in child_lower

    def search_breadth_first(category, exact_only=False):
        """Breadth-first search: check all top-level items first, then recurse.
        This ensures raw 'Operator' is found before 'Hello Operator.adg' buried
        in a user_library subfolder."""
        nonlocal iterations
        # Queue of (item, depth) tuples — deque for O(1) popleft
        queue = deque([(category, 0)])
        while queue:
            item, depth = queue.popleft()
            if depth > 8:
                continue
            try:
                children = list(item.children)
            except AttributeError:
                continue
            for child in children:
                iterations += 1
                if iterations > MAX_ITERATIONS:
                    return None
                if _name_matches(child.name, device_name, exact_only) and child.is_loadable:
                    return child
                # Queue children for later (breadth-first)
                if child.is_folder:
                    queue.append((child, depth + 1))
        return None

    # Search device categories only — never samples (avoids "Castanet Reverb.aif"
    # matching before the actual Reverb device).
    # plugins + max_for_live included for AU/VST/AUv3 and M4L devices.
    category_attrs = (
        "audio_effects", "instruments", "midi_effects",
        "plugins", "max_for_live", "user_library",
        "drums", "sounds", "packs",
    )
    categories = []
    for attr in category_attrs:
        try:
            categories.append(getattr(browser, attr))
        except AttributeError:
            pass

    # Pass 0: FAST — check only top-level children of each category (no recursion).
    # Raw devices like "Operator", "Analog", "Compressor" are always top-level.
    # This is O(N) where N = number of top-level items (~50), not O(thousands).
    for category in categories:
        try:
            for child in category.children:
                if _name_matches(child.name, device_name, True) and child.is_loadable:
                    song.view.selected_track = track
                    browser.load_item(child)
                    return {
                        "loaded": child.name,
                        "track_index": track_index,
                    }
        except AttributeError:
            pass

    # Pass 1: exact name match with recursion (for items nested in folders)
    for category in categories:
        iterations = 0
        found = search_breadth_first(category, exact_only=True)
        if found is not None:
            song.view.selected_track = track
            browser.load_item(found)
            return {
                "loaded": found.name,
                "track_index": track_index,
            }

    # Pass 2: partial name match (for M4L devices like "trnr.Kickster")
    for category in categories:
        iterations = 0
        found = search_breadth_first(category, exact_only=False)
        if found is not None:
            song.view.selected_track = track
            browser.load_item(found)
            return {
                "loaded": found.name,
                "track_index": track_index,
            }

    raise ValueError(
        "Device '%s' not found in browser. Check spelling or use "
        "search_browser to find the exact name." % params["device_name"]
    )


@register("set_simpler_playback_mode")
def set_simpler_playback_mode(song, params):
    """Set Simpler's playback mode (Classic/One-Shot/Slice).

    playback_mode: 0=Classic, 1=One-Shot, 2=Slice
    slice_by (optional, only for Slice mode): 0=Transient, 1=Beat, 2=Region, 3=Manual
    sensitivity (optional, 0.0-1.0, only for Transient slicing)
    """
    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    playback_mode = int(params["playback_mode"])
    track = get_track(song, track_index)
    device = get_device(track, device_index)

    if device.class_name != "OriginalSimpler":
        raise ValueError(
            "Device '%s' is %s, not Simpler"
            % (device.name, device.class_name)
        )
    if playback_mode not in (0, 1, 2):
        raise ValueError("playback_mode must be 0 (Classic), 1 (One-Shot), or 2 (Slice)")

    device.playback_mode = playback_mode

    result = {
        "track_index": track_index,
        "device_index": device_index,
        "playback_mode": playback_mode,
        "mode_name": ["Classic", "One-Shot", "Slice"][playback_mode],
    }

    # Set slicing style if in Slice mode
    if playback_mode == 2:
        slice_by = params.get("slice_by", None)
        if slice_by is not None:
            slice_by = int(slice_by)
            if slice_by not in (0, 1, 2, 3):
                raise ValueError(
                    "slice_by must be 0 (Transient), 1 (Beat), 2 (Region), or 3 (Manual)"
                )
            device.slicing_style = slice_by
            result["slice_by"] = slice_by
            result["slice_by_name"] = ["Transient", "Beat", "Region", "Manual"][slice_by]

        sensitivity = params.get("sensitivity", None)
        if sensitivity is not None:
            sensitivity = float(sensitivity)
            device.slicing_sensitivity = max(0.0, min(1.0, sensitivity))
            result["sensitivity"] = device.slicing_sensitivity

    return result


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
