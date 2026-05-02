"""Tests for v1.24 fast-mode apply post-load repair (Tasks 18b + 18d)."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock


def _mock_ctx_recording(simpler_params=None):
    """Build a mock ctx that records all send_command calls.

    simpler_params: optional dict of {param_name: value} that get_device_parameters returns.
    """
    ableton = MagicMock()
    ableton._calls = []
    ableton._params = simpler_params or {
        "Volume": -12.0, "Snap": 1, "Transpose": 0, "Sample Length": 1,
        "Trigger Mode": 0,
    }

    def send_command(cmd, args):
        ableton._calls.append((cmd, args))
        if cmd == "get_session_info":
            return {"tempo": 122.0, "track_count": 0, "scene_count": 8, "tracks": []}
        if cmd == "create_midi_track":
            return {"track_index": 0}
        if cmd == "load_browser_item":
            return {"track_index": args.get("track_index", 0), "loaded": True, "name": "MockSample.aif", "device_count": 1}
        if cmd == "create_clip":
            return {"track_index": args["track_index"], "clip_index": args["clip_index"]}
        if cmd == "add_notes":
            return {"notes_added": len(args.get("notes", []))}
        if cmd == "get_device_info":
            return {
                "name": "MockSample", "class_name": "OriginalSimpler",
                "is_active": True, "parameter_count": 63, "type": 1,
            }
        if cmd == "get_device_parameters":
            return {
                "parameters": [
                    {"index": i, "name": name, "value": val, "min": -36 if name == "Volume" else 0, "max": 36 if name == "Volume" else 1, "is_quantized": name == "Snap"}
                    for i, (name, val) in enumerate(ableton._params.items())
                ]
            }
        if cmd == "set_device_parameter":
            return {"name": args.get("parameter_name"), "value": args["value"], "value_string": str(args["value"])}
        if cmd == "batch_set_parameters":
            return {"parameters": [{"name": p.get("parameter_name"), "value": p["value"]} for p in args.get("parameters", [])]}
        if cmd == "insert_device":
            return {"device_index": 1, "name": args.get("device_class", "MockDevice")}
        return {"ok": True}

    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}
    return ctx


# ── 18d: drum role-default repair ──────────────────────────────────

@pytest.mark.asyncio
async def test_drum_role_repair_sets_volume_snap_transpose():
    """For kick/hat/snare/perc/clap layers, apply MUST set:
    - Volume = 0 dB
    - Snap = Off
    - Transpose = +24 semitones (compensates for wrong root)
    after load_browser_item, regardless of whether role='drum' 'worked'."""
    from mcp_server.composer.fast.apply import apply_fast_plan

    ctx = _mock_ctx_recording()
    plan = {
        "scene_index": None, "bars": 4, "tempo": 122,
        "layers": [{
            "role": "kick",
            "uri": "query:Drums#Drum%20Hits:Kick:FileId_30457",
            "track_name": "KICK",
            "notes": [{"pitch": 36, "start_time": 0, "duration": 0.5, "velocity": 100}],
            "effects": [],
            "sends": [],
        }],
    }

    result = apply_fast_plan(ctx, plan)
    if hasattr(result, "__await__"):
        result = await result

    cmds = ctx.lifespan_context["ableton"]._calls

    # Find the parameter-setting calls for Volume, Snap, Transpose on the loaded Simpler
    set_param_calls = [c[1] for c in cmds if c[0] in ("set_device_parameter", "batch_set_parameters")]

    # Collect all (param_name, value) tuples that were set.
    # The Remote Script accepts `name_or_index` (legacy) — `parameter_name`
    # was attempted in the original v1.24 fix but doesn't translate; fixed
    # to use name_or_index post live test.
    def _extract_param_name(p: dict) -> str | None:
        return p.get("name_or_index") or p.get("parameter_name") or p.get("parameter_index")

    params_set = []
    for args in set_param_calls:
        if "parameter_name" in args or "name_or_index" in args:
            name = args.get("name_or_index") or args.get("parameter_name")
            params_set.append((name, args["value"]))
        elif "parameters" in args:
            for p in args["parameters"]:
                params_set.append((_extract_param_name(p), p.get("value")))
        elif "operations" in args:
            for p in args["operations"]:
                params_set.append((_extract_param_name(p), p.get("value")))

    param_dict = {name: val for name, val in params_set if name}

    assert param_dict.get("Volume") == 0, f"Volume should be set to 0 dB, got {param_dict.get('Volume')}"
    assert param_dict.get("Snap") == 0, f"Snap should be set to 0 (Off), got {param_dict.get('Snap')}"
    assert param_dict.get("Transpose") == 24, f"Transpose should be set to +24 (root-note compensation), got {param_dict.get('Transpose')}"


@pytest.mark.asyncio
async def test_non_drum_role_no_repair():
    """For bass/lead/pad layers, NO drum repair — the role-default repair
    only applies to drum-family roles."""
    from mcp_server.composer.fast.apply import apply_fast_plan

    ctx = _mock_ctx_recording()
    plan = {
        "scene_index": None, "bars": 4, "tempo": 122,
        "layers": [{
            "role": "bass",
            "uri": "query:Synths#Operator",
            "track_name": "BASS",
            "notes": [{"pitch": 45, "start_time": 0, "duration": 1, "velocity": 100}],
            "effects": [],
            "sends": [],
        }],
    }

    result = apply_fast_plan(ctx, plan)
    if hasattr(result, "__await__"):
        result = await result

    cmds = ctx.lifespan_context["ableton"]._calls

    # No Transpose=24 should have been applied to a bass layer
    set_param_calls = [c[1] for c in cmds if c[0] in ("set_device_parameter", "batch_set_parameters")]
    transpose_set_to_24 = False
    for args in set_param_calls:
        if "parameter_name" in args and args.get("parameter_name") == "Transpose" and args.get("value") == 24:
            transpose_set_to_24 = True
        elif "parameters" in args:
            for p in args["parameters"]:
                if p.get("parameter_name") == "Transpose" and p.get("value") == 24:
                    transpose_set_to_24 = True

    assert not transpose_set_to_24, "Transpose=+24 should NOT be applied to non-drum layers"


# ── 18b: empty-container detection ─────────────────────────────────

@pytest.mark.asyncio
async def test_empty_drum_sampler_detected_as_silent():
    """When Drum Sampler/DrumCell is loaded with no sample (Sample Length=0),
    the layer result must include a silent_load_warning."""
    from mcp_server.composer.fast.apply import apply_fast_plan

    # Simulate empty DrumCell: Sample Length = 0
    ctx = _mock_ctx_recording(simpler_params={
        "Volume": -12.0, "Snap": 1, "Transpose": 0,
        "Sample Length": 0,  # empty container indicator
    })

    # Override device_info to return DrumCell class_name
    original_send = ctx.lifespan_context["ableton"].send_command
    def patched_send(cmd, args):
        if cmd == "get_device_info":
            return {
                "name": "Drum Sampler", "class_name": "DrumCell",
                "is_active": True, "parameter_count": 40, "type": 1,
            }
        return original_send(cmd, args)
    ctx.lifespan_context["ableton"].send_command = patched_send

    plan = {
        "scene_index": None, "bars": 4, "tempo": 122,
        "layers": [{
            "role": "kick",
            "uri": "query:Synths#Drum%20Sampler",  # this is the bad URI
            "track_name": "KICK",
            "notes": [{"pitch": 36, "start_time": 0, "duration": 0.5, "velocity": 100}],
            "effects": [],
            "sends": [],
        }],
    }

    result = apply_fast_plan(ctx, plan)
    if hasattr(result, "__await__"):
        result = await result

    # Result should include warnings for the silent layer
    layers = result.get("layers", [])
    assert len(layers) == 1
    layer = layers[0]
    warnings = layer.get("warnings") or []
    silent_warning = any("silent" in str(w).lower() or "empty" in str(w).lower() for w in warnings) or \
                     ("silent_load_warning" in layer)

    assert silent_warning, f"Expected silent_load_warning on empty DrumCell layer, got: {layer}"
