"""
LivePilot - Device domain handlers (12 commands).
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
        info = {
            "index": i,
            "name": param.name,
            "value": param.value,
            "min": param.min,
            "max": param.max,
            "is_quantized": param.is_quantized,
            "value_string": param.str_for_value(param.value),
        }
        # 12.2+ feature: native display_value
        try:
            info["display_value"] = param.display_value
        except AttributeError:
            pass
        parameters.append(info)
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
    result = {
        "name": param.name,
        "value": param.value,
        "value_string": param.str_for_value(param.value),
        "min": param.min,
        "max": param.max,
    }
    # 12.2+: include display_value
    try:
        result["display_value"] = param.display_value
    except AttributeError:
        pass
    return result


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
        result_entry = {
            "name": param.name,
            "value": param.value,
            "value_string": param.str_for_value(param.value),
        }
        # 12.2+: include display_value
        try:
            result_entry["display_value"] = param.display_value
        except AttributeError:
            pass
        results.append(result_entry)

    return {"parameters": results}


@register("toggle_device")
def toggle_device(song, params):
    """Enable or disable a device."""
    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    active = bool(params["active"])
    track = get_track(song, track_index)
    device = get_device(track, device_index)

    # Find the "Device On" parameter by name — the previous fallback
    # blindly assumed parameters[0] was an on/off switch, which for many
    # devices is actually "Filter Frequency", "Gain", or similar. The
    # fallback silently mutated an arbitrary parameter while reporting
    # is_active as if toggling had worked. Now refuse to guess.
    on_param = None
    for p in device.parameters:
        if p.name == "Device On":
            on_param = p
            break
    if on_param is None:
        raise ValueError(
            "Device '%s' exposes no 'Device On' parameter and cannot be "
            "toggled programmatically. Use delete_device or disable it "
            "through the UI." % device.name
        )

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


@register("move_device")
def move_device(song, params):
    """Move a device to a new position on the same or different track.

    Uses Song.move_device(device, target_track, target_index).
    """
    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    target_index = int(params.get("target_index", device_index))
    target_track_index = params.get("target_track_index", None)

    track = get_track(song, track_index)
    device = get_device(track, device_index)

    if target_track_index is not None:
        target_track = get_track(song, int(target_track_index))
    else:
        target_track = track

    song.move_device(device, target_track, target_index)
    return {
        "moved": device.name,
        "from_track": track_index,
        "from_index": device_index,
        "to_track": int(target_track_index) if target_track_index is not None else track_index,
        "to_index": target_index,
    }


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


# ── Device name registry for insert_device (12.3+) ──────────────────────

NATIVE_DEVICE_NAMES = frozenset({
    # Instruments
    "Analog", "Collision", "Drift", "Electric", "Drum Rack",
    "Instrument Rack", "Meld", "Operator", "Sampler", "Simpler",
    "Tension", "Wavetable",
    # Audio Effects
    "Align Delay", "Amp", "Audio Effect Rack", "Auto Filter",
    "Auto Pan-Tremolo", "Auto Shift", "Beat Repeat", "Cabinet",
    "Channel EQ", "Chorus-Ensemble", "Color Limiter", "Compressor",
    "Convolution Reverb", "Corpus", "Delay", "Drum Buss",
    "Dynamic Tube", "Echo", "EQ Eight", "EQ Three", "Erosion",
    "External Audio Effect", "Flanger", "Frequency Shifter", "Gate",
    "Glue Compressor", "Grain Delay", "Hybrid Reverb", "Limiter",
    "Looper", "Multiband Dynamics", "Overdrive", "Pedal",
    "Phaser-Flanger", "Pitch Hack", "Redux", "Re-Enveloper",
    "Resonators", "Reverb", "Roar", "Saturator", "Shifter",
    "Spectral Blur", "Spectral Resonator", "Spectral Time", "Tuner",
    "Utility", "Vinyl Distortion", "Vocoder",
    # MIDI Effects
    "Arpeggiator", "Chord", "Expression Control", "MIDI Effect Rack",
    "Note Echo", "Note Length", "Pitch", "Random", "Scale", "Strum",
    "Velocity",
})

# Case-insensitive lookup for user convenience
_DEVICE_NAME_LOOKUP = {name.lower(): name for name in NATIVE_DEVICE_NAMES}


@register("insert_device")
def insert_device(song, params):
    """Insert a native Live device by name (12.3+ API).

    Much faster than browser search — a single call with no state dependency.
    Only works for native devices (not plugins or M4L).

    Required: track_index, device_name
    Optional: position (-1 = end of chain, default), chain_index + device_index (for rack chains)
    """
    from .version_detect import has_feature

    if not has_feature("insert_device"):
        raise RuntimeError(
            "insert_device requires Live 12.3+. "
            "Use find_and_load_device (browser search) instead."
        )

    track_index = int(params["track_index"])
    device_name = str(params["device_name"])
    position = int(params.get("position", -1))
    chain_index = params.get("chain_index")

    # Resolve canonical name (case-insensitive)
    canonical = _DEVICE_NAME_LOOKUP.get(device_name.lower())
    if canonical is None:
        raise ValueError(
            "Device '%s' is not a native Live device. "
            "insert_device only supports native devices (not plugins or M4L). "
            "Use find_and_load_device for plugins."
            % device_name
        )

    track = get_track(song, track_index)

    song.begin_undo_step()
    try:
        if chain_index is not None:
            # 12.3+ Chain.insert_device — insert into a rack chain
            chain_index = int(chain_index)
            device_on_track = get_device(track, int(params.get("device_index", 0)))
            chains = list(device_on_track.chains)
            if chain_index < 0 or chain_index >= len(chains):
                raise IndexError(
                    "Chain index %d out of range (0..%d)"
                    % (chain_index, len(chains) - 1)
                )
            chain = chains[chain_index]
            if position >= 0:
                device = chain.insert_device(canonical, position)
            else:
                device = chain.insert_device(canonical)
            container_devices = list(chain.devices)
        else:
            # Track-level insertion
            if position >= 0:
                device = track.insert_device(canonical, position)
            else:
                device = track.insert_device(canonical)
            container_devices = list(track.devices)
    finally:
        song.end_undo_step()

    # Resolve the index the newly-inserted device landed at so callers can
    # bind later parameter/chain operations to it (composer plans rely on this).
    try:
        inserted_index = container_devices.index(device)
    except ValueError:
        inserted_index = len(container_devices) - 1

    # Read back the device info — use "loaded" key to match
    # the convention expected by _postflight_loaded_device on MCP side
    result = {
        "loaded": device.name,
        "class_name": device.class_name,
        "track_index": track_index,
        "device_index": inserted_index,  # additive — for step-result binding
        "parameter_count": len(list(device.parameters)),
    }
    if position >= 0:
        result["position"] = position
    return result


@register("insert_rack_chain")
def insert_rack_chain(song, params):
    """Insert a new chain into an Instrument Rack, Audio Effect Rack, or Drum Rack (12.3+).

    Required: track_index, device_index
    Optional: position (-1 = end)
    """
    from .version_detect import has_feature

    if not has_feature("insert_chain"):
        raise RuntimeError(
            "insert_rack_chain requires Live 12.3+."
        )

    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    position = int(params.get("position", -1))

    track = get_track(song, track_index)
    device = get_device(track, device_index)

    if not device.can_have_chains:
        raise ValueError(
            "Device '%s' is not a rack — cannot insert chains"
            % device.name
        )

    song.begin_undo_step()
    try:
        if position >= 0:
            device.insert_chain(position)
        else:
            device.insert_chain()
    finally:
        song.end_undo_step()

    chain_count = len(list(device.chains))
    return {
        "inserted": True,
        "track_index": track_index,
        "device_index": device_index,
        "chain_count": chain_count,
    }


@register("set_drum_chain_note")
def set_drum_chain_note(song, params):
    """Set which MIDI note triggers a drum chain (12.3+).

    Required: track_index, device_index, chain_index, note
    note: MIDI note number (0-127), or -1 for 'All Notes'
    """
    from .version_detect import has_feature

    if not has_feature("drum_chain_in_note"):
        raise RuntimeError(
            "set_drum_chain_note requires Live 12.3+."
        )

    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    chain_index = int(params["chain_index"])
    note = int(params["note"])

    if note < -1 or note > 127:
        raise ValueError("note must be -1 (All Notes) or 0-127")

    track = get_track(song, track_index)
    device = get_device(track, device_index)

    chains = list(device.chains)
    if chain_index < 0 or chain_index >= len(chains):
        raise IndexError(
            "Chain index %d out of range (0..%d)"
            % (chain_index, len(chains) - 1)
        )

    chain = chains[chain_index]
    chain.in_note = note

    return {
        "track_index": track_index,
        "device_index": device_index,
        "chain_index": chain_index,
        "in_note": note,
    }


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

    # 12.3+ fast path: try insert_device for native devices
    from .version_detect import has_feature
    if has_feature("insert_device"):
        canonical = _DEVICE_NAME_LOOKUP.get(device_name)
        if canonical is not None:
            try:
                song.begin_undo_step()
                try:
                    device = track.insert_device(canonical)
                finally:
                    song.end_undo_step()
                return {
                    "loaded": device.name,
                    "class_name": device.class_name,
                    "track_index": track_index,
                    "parameter_count": len(list(device.parameters)),
                }
            except Exception:
                pass  # Fall through to browser search

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


# ── Rack Variations + Macro CRUD (Live 11+) ─────────────────────────────


def _get_rack(song, params):
    """Resolve (track, device) and validate it is a Rack (can_have_chains)."""
    track = get_track(song, int(params["track_index"]))
    device = get_device(track, int(params["device_index"]))
    if not getattr(device, "can_have_chains", False):
        raise ValueError(
            "Device '%s' is not a Rack (can_have_chains=False)" % device.name
        )
    return device


@register("get_rack_variations")
def get_rack_variations(song, params):
    """Return variation count, selected index, and visible macro count for a Rack."""
    from .version_detect import has_feature
    if not has_feature("rack_variations_api"):
        raise RuntimeError("Rack variations require Live 11+.")
    rack = _get_rack(song, params)
    return {
        "count": int(getattr(rack, "variation_count", 0)),
        "selected_index": int(getattr(rack, "selected_variation_index", -1)),
        "visible_macro_count": int(getattr(rack, "visible_macro_count", 0)),
    }


@register("store_rack_variation")
def store_rack_variation(song, params):
    """Store current macro values as a new variation on a Rack."""
    from .version_detect import has_feature
    if not has_feature("rack_variations_api"):
        raise RuntimeError("Rack variations require Live 11+.")
    rack = _get_rack(song, params)
    rack.store_variation()
    count = int(rack.variation_count)
    return {
        "count": count,
        "new_index": count - 1,
    }


@register("recall_rack_variation")
def recall_rack_variation(song, params):
    """Select and recall a variation on a Rack by index."""
    from .version_detect import has_feature
    if not has_feature("rack_variations_api"):
        raise RuntimeError("Rack variations require Live 11+.")
    rack = _get_rack(song, params)
    idx = int(params["variation_index"])
    count = int(rack.variation_count)
    if count <= 0:
        raise IndexError("Rack has no variations stored")
    if not 0 <= idx < count:
        raise IndexError(
            "variation_index %d out of range (0..%d)" % (idx, count - 1)
        )
    rack.selected_variation_index = idx
    rack.recall_selected_variation()
    return {"selected_index": int(rack.selected_variation_index)}


@register("delete_rack_variation")
def delete_rack_variation(song, params):
    """Delete a variation on a Rack by index (selects it first, then deletes)."""
    from .version_detect import has_feature
    if not has_feature("rack_variations_api"):
        raise RuntimeError("Rack variations require Live 11+.")
    rack = _get_rack(song, params)
    idx = int(params["variation_index"])
    count = int(rack.variation_count)
    if count <= 0:
        raise IndexError("Rack has no variations to delete")
    if not 0 <= idx < count:
        raise IndexError(
            "variation_index %d out of range (0..%d)" % (idx, count - 1)
        )
    rack.selected_variation_index = idx
    rack.delete_selected_variation()
    return {"count": int(rack.variation_count)}


@register("randomize_rack_macros")
def randomize_rack_macros(song, params):
    """Randomize the macro values on a Rack (Live's built-in dice)."""
    from .version_detect import has_feature
    if not has_feature("rack_variations_api"):
        raise RuntimeError("Rack variations require Live 11+.")
    rack = _get_rack(song, params)
    rack.randomize_macros()
    return {"ok": True}


@register("add_rack_macro")
def add_rack_macro(song, params):
    """Add one macro to a Rack (raises visible_macro_count by 1, max 16)."""
    from .version_detect import has_feature
    if not has_feature("rack_variations_api"):
        raise RuntimeError("Rack variations require Live 11+.")
    rack = _get_rack(song, params)
    rack.add_macro()
    return {"visible_macro_count": int(rack.visible_macro_count)}


@register("remove_rack_macro")
def remove_rack_macro(song, params):
    """Remove the last macro from a Rack (lowers visible_macro_count by 1, min 1)."""
    from .version_detect import has_feature
    if not has_feature("rack_variations_api"):
        raise RuntimeError("Rack variations require Live 11+.")
    rack = _get_rack(song, params)
    rack.remove_macro()
    return {"visible_macro_count": int(rack.visible_macro_count)}


@register("set_rack_visible_macros")
def set_rack_visible_macros(song, params):
    """Set visible_macro_count on a Rack directly (1-16)."""
    from .version_detect import has_feature
    if not has_feature("rack_variations_api"):
        raise RuntimeError("Rack variations require Live 11+.")
    rack = _get_rack(song, params)
    count = int(params["count"])
    if not 1 <= count <= 16:
        raise ValueError("count must be 1-16")
    rack.visible_macro_count = count
    return {"visible_macro_count": int(rack.visible_macro_count)}


# ── Simpler Slice CRUD (Live 11+) ───────────────────────────────────────


def _get_simpler(song, params):
    """Resolve (track, device, sample) for a Simpler and validate.

    Simpler's class_name is "OriginalSimpler". We match on "Simpler" so
    third-party simpler-like devices (if any ever surface) aren't silently
    accepted — but the common Original Simpler path is covered.
    """
    track = get_track(song, int(params["track_index"]))
    device = get_device(track, int(params["device_index"]))
    if "Simpler" not in str(getattr(device, "class_name", "")):
        raise ValueError(
            "Device at %d is not a Simpler (class_name=%s)"
            % (int(params["device_index"]),
               getattr(device, "class_name", "?"))
        )
    sample = getattr(device, "sample", None)
    if sample is None:
        raise RuntimeError("Simpler has no sample loaded")
    return device, sample


@register("insert_simpler_slice")
def insert_simpler_slice(song, params):
    """Insert a slice at the given sample-frame position."""
    from .version_detect import has_feature
    if not has_feature("simpler_slice_crud"):
        raise RuntimeError("Simpler slice CRUD requires Live 11+.")
    device, sample = _get_simpler(song, params)
    t = int(params["time_samples"])
    if t < 0:
        raise ValueError("time_samples must be >= 0")
    sample.insert_slice(t)
    slices = list(getattr(sample, "slices", []))
    return {"slice_count": len(slices)}


@register("move_simpler_slice")
def move_simpler_slice(song, params):
    """Move a slice from old_time_samples to new_time_samples (both sample frames)."""
    from .version_detect import has_feature
    if not has_feature("simpler_slice_crud"):
        raise RuntimeError("Simpler slice CRUD requires Live 11+.")
    device, sample = _get_simpler(song, params)
    old_t = int(params["old_time_samples"])
    new_t = int(params["new_time_samples"])
    if old_t < 0 or new_t < 0:
        raise ValueError("time values must be >= 0")
    sample.move_slice(old_t, new_t)
    return {"ok": True, "old_time_samples": old_t, "new_time_samples": new_t}


@register("remove_simpler_slice")
def remove_simpler_slice(song, params):
    """Remove the slice at the exact sample-frame position."""
    from .version_detect import has_feature
    if not has_feature("simpler_slice_crud"):
        raise RuntimeError("Simpler slice CRUD requires Live 11+.")
    device, sample = _get_simpler(song, params)
    t = int(params["time_samples"])
    sample.remove_slice(t)
    slices = list(getattr(sample, "slices", []))
    return {"slice_count": len(slices)}


@register("clear_simpler_slices")
def clear_simpler_slices(song, params):
    """Remove all manual slices from the Simpler."""
    from .version_detect import has_feature
    if not has_feature("simpler_slice_crud"):
        raise RuntimeError("Simpler slice CRUD requires Live 11+.")
    device, sample = _get_simpler(song, params)
    sample.clear_slices()
    return {"slice_count": 0}


@register("reset_simpler_slices")
def reset_simpler_slices(song, params):
    """Reset slices to Live's default detection for the current slicing_style."""
    from .version_detect import has_feature
    if not has_feature("simpler_slice_crud"):
        raise RuntimeError("Simpler slice CRUD requires Live 11+.")
    device, sample = _get_simpler(song, params)
    sample.reset_slices()
    slices = list(getattr(sample, "slices", []))
    return {"slice_count": len(slices)}


@register("import_slices_from_onsets")
def import_slices_from_onsets(song, params):
    """Set Transient-mode slicing and trigger re-detection.

    Writes slicing_style=0 (Transient) and slicing_sensitivity, then calls
    reset_slices() so Live re-scans the sample with the new settings.
    Returns the resulting slice_count and the sensitivity that was applied.
    """
    from .version_detect import has_feature
    if not has_feature("simpler_slice_crud"):
        raise RuntimeError("Simpler slice CRUD requires Live 11+.")
    device, sample = _get_simpler(song, params)
    sensitivity = float(params.get("sensitivity", 0.5))
    if not 0.0 <= sensitivity <= 1.0:
        raise ValueError("sensitivity must be 0.0-1.0")
    # slicing_style: 0=Transient, 1=Beats, 2=Region, 3=Manual
    if hasattr(sample, "slicing_style"):
        sample.slicing_style = 0
    if hasattr(sample, "slicing_sensitivity"):
        sample.slicing_sensitivity = sensitivity
    if hasattr(sample, "reset_slices"):
        sample.reset_slices()
    slices = list(getattr(sample, "slices", []))
    return {"slice_count": len(slices), "sensitivity": sensitivity}
