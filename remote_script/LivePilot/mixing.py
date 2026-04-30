"""
LivePilot - Mixing domain handlers (11 commands).
"""

from .router import register
from .utils import get_track


@register("set_track_volume")
def set_track_volume(song, params):
    """Set the volume of a track."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    volume = float(params["volume"])
    track.mixer_device.volume.value = volume
    return {"index": track_index, "volume": track.mixer_device.volume.value}


@register("set_track_pan")
def set_track_pan(song, params):
    """Set the panning of a track."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    pan = float(params["pan"])
    track.mixer_device.panning.value = pan
    return {"index": track_index, "pan": track.mixer_device.panning.value}


@register("set_track_send")
def set_track_send(song, params):
    """Set a send value on a track."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    send_index = int(params["send_index"])
    sends = list(track.mixer_device.sends)
    if send_index < 0 or send_index >= len(sends):
        raise IndexError(
            "Send index %d out of range (0..%d)"
            % (send_index, len(sends) - 1)
        )
    sends[send_index].value = float(params["value"])
    return {
        "index": track_index,
        "send_index": send_index,
        "value": sends[send_index].value,
    }


@register("get_return_tracks")
def get_return_tracks(song, params):
    """Return info about all return tracks."""
    result = []
    for i, track in enumerate(song.return_tracks):
        result.append({
            "index": i,
            "name": track.name,
            "color_index": track.color_index,
            "volume": track.mixer_device.volume.value,
            "panning": track.mixer_device.panning.value,
        })
    return {"return_tracks": result}


@register("get_master_track")
def get_master_track(song, params):
    """Return info about the master track."""
    master = song.master_track
    devices = []
    for i, device in enumerate(master.devices):
        devices.append({
            "index": i,
            "name": device.name,
            "class_name": device.class_name,
            "is_active": device.is_active,
        })
    return {
        "name": master.name,
        "volume": master.mixer_device.volume.value,
        "panning": master.mixer_device.panning.value,
        "devices": devices,
    }


@register("set_master_volume")
def set_master_volume(song, params):
    """Set the master track volume."""
    volume = float(params["volume"])
    song.master_track.mixer_device.volume.value = volume
    return {"volume": song.master_track.mixer_device.volume.value}


@register("get_track_routing")
def get_track_routing(song, params):
    """Get the input/output routing for a track."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    result = {"index": track_index}
    try:
        result["input_routing_type"] = track.input_routing_type.display_name
    except AttributeError:
        result["input_routing_type"] = None
    try:
        result["input_routing_channel"] = track.input_routing_channel.display_name
    except AttributeError:
        result["input_routing_channel"] = None
    try:
        result["output_routing_type"] = track.output_routing_type.display_name
    except AttributeError:
        result["output_routing_type"] = None
    try:
        result["output_routing_channel"] = track.output_routing_channel.display_name
    except AttributeError:
        result["output_routing_channel"] = None
    return result


@register("get_track_meters")
def get_track_meters(song, params):
    """Read output meter levels for one or all tracks.

    Returns peak level (0.0-1.0) for each track. When track_index is
    provided, returns a single track. Otherwise returns all tracks.

    The 'level' value is the hold-peak of max(L, R). It's cheap to read.
    The 'left'/'right' values add GUI load — only included when
    include_stereo=True.
    """
    include_stereo = bool(params.get("include_stereo", False))
    track_index = params.get("track_index")

    def read_meters(track, idx):
        entry = {
            "index": idx,
            "name": track.name,
        }
        muted = bool(getattr(track, "mute", False))
        if track.has_audio_output and not muted:
            entry["level"] = track.output_meter_level
            if include_stereo:
                entry["left"] = track.output_meter_left
                entry["right"] = track.output_meter_right
        else:
            entry["level"] = 0.0
            entry["has_audio_output"] = bool(getattr(track, "has_audio_output", False))
            if include_stereo:
                entry["left"] = 0.0
                entry["right"] = 0.0
        return entry

    if track_index is not None:
        track = get_track(song, int(track_index))
        return {"tracks": [read_meters(track, int(track_index))]}

    tracks = []
    for i, track in enumerate(song.tracks):
        tracks.append(read_meters(track, i))
    return {"tracks": tracks}


@register("get_master_meters")
def get_master_meters(song, params):
    """Read output meter levels for the master track."""
    master = song.master_track
    result = {
        "level": master.output_meter_level,
        "left": master.output_meter_left,
        "right": master.output_meter_right,
    }
    return result


@register("get_mix_snapshot")
def get_mix_snapshot(song, params):
    """Get a complete snapshot of the mix: all track levels, volumes, pans,
    mute/solo states, and master meters. One call to assess the full mix."""
    tracks = []
    for i, track in enumerate(song.tracks):
        tracks.append({
            "index": i,
            "name": track.name,
            "meter_level": (
                track.output_meter_level
                if track.has_audio_output and not bool(getattr(track, "mute", False))
                else 0.0
            ),
            "volume": track.mixer_device.volume.value,
            "pan": track.mixer_device.panning.value,
            "mute": track.mute,
            "solo": track.solo,
            "has_audio_output": track.has_audio_output,
        })
    returns = []
    for i, track in enumerate(song.return_tracks):
        returns.append({
            "index": i,
            "name": track.name,
            "meter_level": track.output_meter_level,
            "volume": track.mixer_device.volume.value,
            "pan": track.mixer_device.panning.value,
            "mute": track.mute,
            "solo": track.solo,
        })
    master = song.master_track
    return {
        "tracks": tracks,
        "return_tracks": returns,
        "master": {
            "level": master.output_meter_level,
            "left": master.output_meter_left,
            "right": master.output_meter_right,
            "volume": master.mixer_device.volume.value,
        },
        "is_playing": song.is_playing,
        "tempo": song.tempo,
    }


@register("set_track_routing")
def set_track_routing(song, params):
    """Set input/output routing for a track by display name."""
    track_index = int(params["track_index"])
    track = get_track(song, track_index)
    if not any(k in params for k in ("input_type", "input_channel", "output_type", "output_channel")):
        raise ValueError("At least one routing parameter must be provided")
    result = {"index": track_index}

    if "input_type" in params:
        name = str(params["input_type"])
        available = list(track.available_input_routing_types)
        matched = None
        for rt in available:
            if rt.display_name == name:
                matched = rt
                break
        if matched is None:
            options = [rt.display_name for rt in available]
            raise ValueError(
                "Input routing type '%s' not found. Available: %s"
                % (name, ", ".join(options))
            )
        track.input_routing_type = matched
        result["input_routing_type"] = track.input_routing_type.display_name

    if "input_channel" in params:
        name = str(params["input_channel"])
        available = list(track.available_input_routing_channels)
        matched = None
        for ch in available:
            if ch.display_name == name:
                matched = ch
                break
        if matched is None:
            options = [ch.display_name for ch in available]
            raise ValueError(
                "Input routing channel '%s' not found. Available: %s"
                % (name, ", ".join(options))
            )
        track.input_routing_channel = matched
        result["input_routing_channel"] = track.input_routing_channel.display_name

    if "output_type" in params:
        name = str(params["output_type"])
        available = list(track.available_output_routing_types)
        matched = None
        for rt in available:
            if rt.display_name == name:
                matched = rt
                break
        if matched is None:
            options = [rt.display_name for rt in available]
            raise ValueError(
                "Output routing type '%s' not found. Available: %s"
                % (name, ", ".join(options))
            )
        track.output_routing_type = matched
        result["output_routing_type"] = track.output_routing_type.display_name

    if "output_channel" in params:
        name = str(params["output_channel"])
        available = list(track.available_output_routing_channels)
        matched = None
        for ch in available:
            if ch.display_name == name:
                matched = ch
                break
        if matched is None:
            options = [ch.display_name for ch in available]
            raise ValueError(
                "Output routing channel '%s' not found. Available: %s"
                % (name, ", ".join(options))
            )
        track.output_routing_channel = matched
        result["output_routing_channel"] = track.output_routing_channel.display_name

    return result


def _find_sidechain_surface(device):
    """Probe a Compressor device for its sidechain-routing LOM surface.

    Legacy Compressor (I) exposes flat properties directly on the device:
        available_sidechain_input_routing_types / _channels
        sidechain_input_routing_type / _channel
    Live 12.3.6's Compressor2 may not have those flat attrs (confirmed
    via Batch 18's Max JS probe and Batch 19's Python fallback both
    hitting the same gap in the flat surface). This probe tries a few
    known shapes in order and returns the first that matches.

    Returns a dict:
        desc:      string describing which shape matched
        types:     list of RoutingType candidates for input source
        channels:  list of RoutingChannel candidates, or None if the
                   shape doesn't expose a channel list
        set_type:  callable(RoutingType) — assigns the input type
        set_chan:  callable(RoutingChannel) — assigns the channel
        read_type: callable() -> RoutingType or None
        read_chan: callable() -> RoutingChannel or None
    Or None if no known shape matches — caller should emit a diagnostic.
    """
    def _shape(obj, types_attr, chans_attr, type_prop, chan_prop, desc):
        # Channels MUST be read lazily — on Compressor2's input_routing_*
        # shape, available_input_routing_channels depends on the currently
        # selected input_routing_type. Snapshotting at probe time made
        # combined (type + channel) calls fail because the snapshot was
        # taken BEFORE the new type was written. A fresh read per query
        # also keeps us honest against UI-side changes mid-call.
        def _get_channels():
            if not hasattr(obj, chans_attr):
                return None
            return list(getattr(obj, chans_attr))

        return {
            "desc": desc,
            "types": list(getattr(obj, types_attr)),
            "get_channels": _get_channels,
            "set_type": lambda rt: setattr(obj, type_prop, rt),
            "set_chan": lambda rc: setattr(obj, chan_prop, rc),
            "read_type": lambda: getattr(obj, type_prop, None),
            "read_chan": lambda: getattr(obj, chan_prop, None),
        }

    if hasattr(device, "available_sidechain_input_routing_types"):
        return _shape(
            device,
            "available_sidechain_input_routing_types",
            "available_sidechain_input_routing_channels",
            "sidechain_input_routing_type",
            "sidechain_input_routing_channel",
            "flat device.sidechain_input_routing_*",
        )
    sc_input = getattr(device, "sidechain_input", None)
    if sc_input is not None and hasattr(sc_input, "available_routing_types"):
        return _shape(
            sc_input,
            "available_routing_types",
            "available_routing_channels",
            "routing_type",
            "routing_channel",
            "nested device.sidechain_input.routing_*",
        )
    if hasattr(device, "available_input_routing_types"):
        return _shape(
            device,
            "available_input_routing_types",
            "available_input_routing_channels",
            "input_routing_type",
            "input_routing_channel",
            "flat device.input_routing_* (no sidechain_ prefix)",
        )
    return None


def _collect_routing_diagnostic(device):
    """Return a structured trail of routing/sidechain attrs on device + likely children.

    Used as a breadcrumb in the error message when _find_sidechain_surface
    returns None, so the first failing call tells us what the current Live
    build actually exposes without a separate probe session.

    BUG-A3 v2 (2026-04-30): the diagnostic now includes class_name and the
    canonical_parent class so the next live-probe operator can immediately
    tell whether they're looking at a Compressor / Compressor2 / something
    else. Also widens the child-name search to include Live 12.x patterns
    (input_routings, routing_inputs).
    """
    def _attrs(obj, prefix):
        try:
            names = sorted(
                a for a in dir(obj)
                if ("routing" in a.lower() or "sidechain" in a.lower())
                and not a.startswith("_")
            )
        except Exception:
            return []
        return [prefix + n for n in names]

    parts = []
    try:
        parts.append("class=%s" % device.class_name)
    except Exception:
        pass
    try:
        cp = getattr(device, "canonical_parent", None)
        if cp is not None:
            parts.append("canonical_parent.class=%s" % type(cp).__name__)
    except Exception:
        pass

    found = list(_attrs(device, "device."))
    # Probe widened in v2 to include Live 12.x patterns. Order is
    # least-to-most exotic so legacy shapes take precedence.
    for child_name in ("sidechain_input", "input", "sidechain", "routing",
                       "input_routings", "routing_inputs"):
        try:
            child = getattr(device, child_name, None)
        except Exception:
            child = None
        if child is None:
            continue
        found.extend(_attrs(child, "device.%s." % child_name))

    if found:
        parts.append("attrs=[%s]" % ", ".join(found))
    else:
        parts.append("attrs=<none>")
    return " | ".join(parts) if parts else "<none>"


@register("set_compressor_sidechain")
def set_compressor_sidechain(song, params):
    """Configure a Compressor's sidechain input routing (BUG-A3).

    Probes the LOM sidechain-routing surface — legacy Compressor (I)
    exposes `available_sidechain_input_routing_types` directly, but
    Live 12.3.6's Compressor2 doesn't, so we fall back to a small set of
    known shapes via _find_sidechain_surface. On no match the error
    message embeds a dir() audit of routing/sidechain attrs on the
    device and its likely children so future Live builds reveal
    themselves without a separate probe.

    Params:
        track_index: 0+ regular, -1/-2 returns, -1000 master
        device_index: Compressor's position in the chain
        source_type (optional): RoutingType display name
                                (e.g. "1-DRUMS", "Ext. In", "No Input")
        source_channel (optional): RoutingChannel display name
                                   (e.g. "Post FX", "Pre FX", "Post Mixer")

    Omit a param to leave that property unchanged.
    """
    track_index = int(params["track_index"])
    device_index = int(params["device_index"])
    source_type = params.get("source_type")
    source_channel = params.get("source_channel")

    track = get_track(song, track_index)
    devices = list(track.devices)
    if device_index < 0 or device_index >= len(devices):
        raise ValueError(
            "Device index %d out of range (track has %d devices)"
            % (device_index, len(devices))
        )
    device = devices[device_index]

    class_name = device.class_name
    if class_name not in ("Compressor2", "Compressor"):
        raise ValueError(
            "Not a Compressor device (class is %s)" % class_name
        )

    # Older Compressor builds may not expose `sidechain_enabled` as a
    # property; the automatable "S/C On" parameter is the fallback.
    try:
        device.sidechain_enabled = True
    except AttributeError:
        for param in device.parameters:
            if param.name == "S/C On":
                param.value = 1
                break

    result = {
        "ok": True,
        "track_index": track_index,
        "device_index": device_index,
    }

    want_type = source_type is not None and source_type != ""
    want_channel = source_channel is not None and source_channel != ""
    surface = _find_sidechain_surface(device)

    if (want_type or want_channel) and surface is None:
        raise ValueError(
            "This Live build doesn't expose a sidechain routing surface "
            "on %s. Inspected attrs: %s"
            % (class_name, _collect_routing_diagnostic(device))
        )

    if want_type:
        available = surface["types"]
        matched = None
        for rt in available:
            if rt.display_name == source_type:
                matched = rt
                break
        if matched is None:
            options = [rt.display_name for rt in available]
            raise ValueError(
                "Sidechain input type '%s' not found (surface=%s). "
                "Available: %s"
                % (source_type, surface["desc"], ", ".join(options))
            )
        surface["set_type"](matched)

    if want_channel:
        # Lazy fetch — on Compressor2 the channel list depends on the
        # currently-set input_routing_type, so combined calls need the
        # post-type-write state, not the probe-time snapshot.
        channels = surface["get_channels"]()
        if channels is None:
            raise ValueError(
                "Sidechain surface on %s (%s) exposes input types but no "
                "channel list. Inspected attrs: %s"
                % (class_name, surface["desc"],
                   _collect_routing_diagnostic(device))
            )
        matched = None
        for ch in channels:
            if ch.display_name == source_channel:
                matched = ch
                break
        if matched is None:
            options = [ch.display_name for ch in channels]
            raise ValueError(
                "Sidechain input channel '%s' not found (surface=%s). "
                "Available: %s"
                % (source_channel, surface["desc"], ", ".join(options))
            )
        surface["set_chan"](matched)

    # Read back via the same surface used to write. Fall back to the
    # input params if the surface isn't exposed or raises on read.
    try:
        if surface is None:
            raise AttributeError("no sidechain surface for readback")
        type_obj = surface["read_type"]()
        chan_obj = surface["read_chan"]()
        result["sidechain"] = {
            "type": type_obj.display_name if type_obj is not None else "",
            "channel": chan_obj.display_name if chan_obj is not None else "",
            "enabled": bool(getattr(device, "sidechain_enabled", True)),
        }
    except AttributeError:
        result["sidechain"] = {
            "type": source_type or "",
            "channel": source_channel or "",
            "enabled": True,
        }
    return result
