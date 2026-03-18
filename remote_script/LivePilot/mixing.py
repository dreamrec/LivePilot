"""
LivePilot - Mixing domain handlers (8 commands).
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
