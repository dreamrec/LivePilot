"""Clip automation envelope handlers.

Provides CRUD access to session clip automation envelopes.
Uses the same LOM API as arrangement automation (AutomationEnvelope)
but targets session clips via track.clip_slots[i].clip.
"""

from .router import register
from .utils import get_track, get_clip


@register("get_clip_automation")
def get_clip_automation(song, params):
    """List automation envelopes on a session clip."""
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])

    track = get_track(song, track_index)
    clip = get_clip(song, track_index, clip_index)
    envelopes = []

    # Check mixer parameters: volume, panning, sends
    # Use the specific parameter_type that set/clear accept (not generic "mixer")
    mixer = track.mixer_device
    for param_name, param_type, param in [
        ("Volume", "volume", mixer.volume),
        ("Pan", "panning", mixer.panning),
    ]:
        env = clip.automation_envelope(param)
        if env is not None:
            envelopes.append({
                "parameter_name": param_name,
                "parameter_type": param_type,
                "has_envelope": True,
            })

    # Check send parameters
    sends = list(mixer.sends)
    for i, send in enumerate(sends):
        env = clip.automation_envelope(send)
        if env is not None:
            envelopes.append({
                "parameter_name": "Send %s" % chr(65 + i),
                "parameter_type": "send",
                "send_index": i,
                "has_envelope": True,
            })

    # Check device parameters
    devices = list(track.devices)
    for di, device in enumerate(devices):
        dev_params = list(device.parameters)
        for pi, param in enumerate(dev_params):
            try:
                env = clip.automation_envelope(param)
                if env is not None:
                    envelopes.append({
                        "parameter_name": param.name,
                        "parameter_type": "device",
                        "device_index": di,
                        "device_name": device.name,
                        "parameter_index": pi,
                        "has_envelope": True,
                    })
            except Exception:
                pass

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "clip_name": clip.name,
        "envelope_count": len(envelopes),
        "envelopes": envelopes,
    }


@register("set_clip_automation")
def set_clip_automation(song, params):
    """Write automation points to a session clip envelope.

    parameter_type: "device", "volume", "panning", "send"
    points: [{time, value, duration?}] — time relative to clip start
    """
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    parameter_type = params["parameter_type"]
    points = params["points"]
    device_index = params.get("device_index")
    parameter_index = params.get("parameter_index")
    send_index = params.get("send_index")

    track = get_track(song, track_index)
    clip = get_clip(song, track_index, clip_index)

    # Resolve the target parameter
    if parameter_type == "volume":
        parameter = track.mixer_device.volume
    elif parameter_type == "panning":
        parameter = track.mixer_device.panning
    elif parameter_type == "send":
        if send_index is None:
            raise ValueError("send_index required for send automation")
        send_index = int(send_index)
        sends = list(track.mixer_device.sends)
        if send_index < 0 or send_index >= len(sends):
            raise IndexError("send_index %d out of range" % send_index)
        parameter = sends[send_index]
    elif parameter_type == "device":
        if device_index is None or parameter_index is None:
            raise ValueError("device_index and parameter_index required")
        device_index = int(device_index)
        parameter_index = int(parameter_index)
        devices = list(track.devices)
        if device_index < 0 or device_index >= len(devices):
            raise IndexError("device_index %d out of range" % device_index)
        dev_params = list(devices[device_index].parameters)
        if parameter_index < 0 or parameter_index >= len(dev_params):
            raise IndexError("parameter_index %d out of range" % parameter_index)
        parameter = dev_params[parameter_index]
    else:
        raise ValueError("parameter_type must be device/volume/panning/send")

    # Get or create envelope
    song.begin_undo_step()
    try:
        envelope = clip.automation_envelope(parameter)
        if envelope is None:
            envelope = clip.create_automation_envelope(parameter)

        # Write points
        written = 0
        for pt in points:
            time = float(pt["time"])
            value = float(pt["value"])
            duration = float(pt.get("duration", 0.125))
            # Clamp value to parameter range
            value = max(parameter.min, min(parameter.max, value))
            envelope.insert_step(time, duration, value)
            written += 1
    finally:
        song.end_undo_step()

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "parameter_name": parameter.name,
        "parameter_type": parameter_type,
        "points_written": written,
    }


@register("clear_clip_automation")
def clear_clip_automation(song, params):
    """Clear automation envelopes from a session clip.

    If parameter_type is provided, clears only that parameter's envelope.
    If omitted, clears ALL envelopes on the clip.
    """
    track_index = int(params["track_index"])
    clip_index = int(params["clip_index"])
    parameter_type = params.get("parameter_type")

    track = get_track(song, track_index)
    clip = get_clip(song, track_index, clip_index)

    song.begin_undo_step()
    try:
        if parameter_type is None:
            # Clear all envelopes
            clip.clear_all_envelopes()
            return {
                "track_index": track_index,
                "clip_index": clip_index,
                "cleared": "all",
            }

        # Clear specific parameter
        if parameter_type == "volume":
            parameter = track.mixer_device.volume
        elif parameter_type == "panning":
            parameter = track.mixer_device.panning
        elif parameter_type == "send":
            send_index = params.get("send_index")
            if send_index is None:
                raise ValueError("send_index required for send automation")
            send_index = int(send_index)
            sends = list(track.mixer_device.sends)
            if send_index < 0 or send_index >= len(sends):
                raise IndexError("send_index %d out of range" % send_index)
            parameter = sends[send_index]
        elif parameter_type == "device":
            device_index = params.get("device_index")
            parameter_index = params.get("parameter_index")
            if device_index is None or parameter_index is None:
                raise ValueError("device_index and parameter_index required")
            device_index = int(device_index)
            parameter_index = int(parameter_index)
            devices = list(track.devices)
            if device_index < 0 or device_index >= len(devices):
                raise IndexError("device_index %d out of range" % device_index)
            dev_params = list(devices[device_index].parameters)
            if parameter_index < 0 or parameter_index >= len(dev_params):
                raise IndexError("parameter_index %d out of range" % parameter_index)
            parameter = dev_params[parameter_index]
        else:
            raise ValueError("Unknown parameter_type")

        clip.clear_envelope(parameter)
    finally:
        song.end_undo_step()

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "cleared": parameter_type,
        "parameter_name": parameter.name,
    }
