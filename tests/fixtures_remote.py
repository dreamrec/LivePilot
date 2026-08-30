"""Canonical, realistic Remote Script response fixtures.

83+ test files hand-roll their own thinner-than-real fakes for the same
handful of high-traffic remote commands (get_track_info, get_session_info,
get_device_parameters, batch_set_parameters, get_scene_matrix). Every one of
those fakes drifts a little from the real handler shape — missing keys,
wrong nesting, stale field names — and nothing catches the drift until a
tool crashes against the real Remote Script in Ableton.

This module is the single canonical source for those response shapes. Shapes
are seeded directly from the real handlers:
  - remote_script/LivePilot/tracks.py::get_track_info
  - remote_script/LivePilot/transport.py::get_session_info
  - remote_script/LivePilot/devices.py::get_device_parameters
  - remote_script/LivePilot/devices.py::batch_set_parameters
  - remote_script/LivePilot/scenes.py::get_scene_matrix

and from captured real-session dumps referenced in BUGS.md (e.g. the
per-track ``volume`` key added for P2-21 relative-nudge support, and the
``value_string`` / ``display_value`` best-effort-serialization contract for
parameters whose display string raises).

Existing hand-rolled fakes are intentionally NOT migrated — that churn was
explicitly out of scope. New tests (and any test being rewritten anyway)
should prefer these builders and ``make_fake_ableton()`` over another
one-off dict literal.

``test_remote_fixture_contracts.py`` asserts these shapes can never silently
drift from the real handlers by running the real handler code against a
fake-LOM harness and diffing keys against what's built here.
"""

from __future__ import annotations

from typing import Any, Callable, Optional


# ─── get_track_info ──────────────────────────────────────────────────────────

def make_track_clip_slot(index: int = 0, has_clip: bool = False, **clip_overrides) -> dict:
    slot: dict[str, Any] = {"index": index, "has_clip": has_clip}
    if has_clip:
        clip = {
            "name": "Clip",
            "color_index": 0,
            "length": 4.0,
            "is_playing": False,
            "is_recording": False,
            "looping": True,
            "loop_start": 0.0,
            "loop_end": 4.0,
            "start_marker": 0.0,
            "end_marker": 4.0,
        }
        clip.update(clip_overrides)
        slot.update(clip)
    return slot


def make_track_device(index: int = 0, name: str = "Drift", class_name: str = "InstrumentGroupDevice",
                       is_active: bool = True, parameters: Optional[list] = None) -> dict:
    return {
        "index": index,
        "name": name,
        "class_name": class_name,
        "is_active": is_active,
        "parameters": parameters if parameters is not None else [
            {"index": 0, "name": "Device On", "value": 1.0, "min": 0.0, "max": 1.0, "is_quantized": True},
        ],
    }


def make_track_info(
    track_index: int = 0,
    name: str = "Track 1",
    *,
    color_index: int = 0,
    mute: bool = False,
    solo: bool = False,
    is_foldable: bool = False,
    is_grouped: bool = False,
    clip_slots: Optional[list] = None,
    devices: Optional[list] = None,
    volume: float = 0.85,
    panning: float = 0.0,
    sends: Optional[list] = None,
    arm: Optional[bool] = False,
    has_midi_input: Optional[bool] = True,
    has_audio_input: Optional[bool] = False,
    current_monitoring_state: Optional[int] = 0,
) -> dict:
    """Canonical ``get_track_info`` response — mirrors tracks.py::get_track_info.

    Regular tracks (track_index >= 0) expose arm/has_midi_input/
    has_audio_input/current_monitoring_state guarded by try/except in the
    real handler (Group/Return/Master raise RuntimeError on these LOM
    properties, so the handler degrades to None instead of omitting the
    key). Master/return convention (track_index < 0) is not modeled here —
    see make_master_track_info() below.
    """
    result: dict[str, Any] = {
        "index": track_index,
        "name": name,
        "color_index": color_index,
        "mute": mute,
        "solo": solo,
        "is_foldable": is_foldable,
        "is_grouped": is_grouped,
        "clip_slots": clip_slots if clip_slots is not None else [make_track_clip_slot(0)],
        "devices": devices if devices is not None else [],
        "mixer": {"volume": volume, "panning": panning},
        "sends": sends if sends is not None else [],
    }
    if is_foldable:
        result["fold_state"] = True

    if track_index >= 0:
        result["arm"] = arm
        result["has_midi_input"] = has_midi_input
        result["has_audio_input"] = has_audio_input
        result["current_monitoring_state"] = current_monitoring_state
    else:
        result["arm"] = None
        result["has_midi_input"] = None
        result["has_audio_input"] = None
        result["is_return_track"] = track_index != -1000
        result["is_master_track"] = track_index == -1000

    return result


def make_master_track_info(volume: float = 0.85, panning: float = 0.0) -> dict:
    return make_track_info(
        track_index=-1000,
        name="Master",
        volume=volume,
        panning=panning,
    )


# ─── get_session_info ───────────────────────────────────────────────────────

def make_session_track_summary(
    index: int = 0,
    name: str = "Track 1",
    *,
    color_index: int = 0,
    mute: bool = False,
    solo: bool = False,
    arm: Optional[bool] = False,
    has_midi_input: Optional[bool] = True,
    has_audio_input: Optional[bool] = False,
    volume: Optional[float] = 0.85,
) -> dict:
    """Per-track summary row inside get_session_info()["tracks"].

    Thinner than get_track_info's per-track shape (no clip_slots/devices),
    but carries the P2-21 ``volume`` key added so semantic-move compilers
    can compile relative nudges instead of blind absolute overwrites
    (transport.py::get_session_info, guarded the same try/except-degrades-
    to-None way as arm/has_midi_input/has_audio_input).
    """
    return {
        "index": index,
        "name": name,
        "color_index": color_index,
        "mute": mute,
        "solo": solo,
        "arm": arm,
        "has_midi_input": has_midi_input,
        "has_audio_input": has_audio_input,
        "volume": volume,
    }


def make_session_return_track_summary(index: int = 0, name: str = "A Reverb", **overrides) -> dict:
    row = {
        "index": index,
        "name": name,
        "color_index": 0,
        "mute": False,
        "solo": False,
    }
    row.update(overrides)
    return row


def make_session_scene_summary(index: int = 0, name: str = "Scene 1", tempo: Optional[float] = None) -> dict:
    return {"index": index, "name": name, "color_index": 0, "tempo": tempo}


def make_session_info(
    *,
    session_instance_id: str = "test-song-instance",
    file_path: str = "",
    tempo: float = 120.0,
    signature_numerator: int = 4,
    signature_denominator: int = 4,
    is_playing: bool = False,
    song_length: float = 64.0,
    current_song_time: float = 0.0,
    loop: bool = False,
    loop_start: float = 0.0,
    loop_length: float = 16.0,
    metronome: bool = False,
    record_mode: bool = False,
    session_record: bool = False,
    tracks: Optional[list] = None,
    return_tracks: Optional[list] = None,
    scenes: Optional[list] = None,
    live_version: str = "12.4.0",
) -> dict:
    """Canonical ``get_session_info`` response — mirrors transport.py::get_session_info."""
    tracks_info = tracks if tracks is not None else [make_session_track_summary(0)]
    return_tracks_info = return_tracks if return_tracks is not None else []
    scenes_info = scenes if scenes is not None else [make_session_scene_summary(0)]

    return {
        "session_instance_id": session_instance_id,
        "file_path": file_path,
        "tempo": tempo,
        "signature_numerator": signature_numerator,
        "signature_denominator": signature_denominator,
        "is_playing": is_playing,
        "song_length": song_length,
        "current_song_time": current_song_time,
        "loop": loop,
        "loop_start": loop_start,
        "loop_length": loop_length,
        "metronome": metronome,
        "record_mode": record_mode,
        "session_record": session_record,
        "track_count": len(tracks_info),
        "return_track_count": len(return_tracks_info),
        "scene_count": len(scenes_info),
        "tracks": tracks_info,
        "return_tracks": return_tracks_info,
        "scenes": scenes_info,
        "live_version": live_version,
        "api_features": {},
    }


# ─── get_device_parameters ──────────────────────────────────────────────────

def make_device_parameter(
    index: int = 0,
    name: str = "Cutoff",
    value: float = 0.5,
    *,
    min: float = 0.0,
    max: float = 1.0,
    is_quantized: bool = False,
    value_string: Optional[str] = "50.0 %",
    display_value: Optional[str] = "50.0 %",
) -> dict:
    """One entry of get_device_parameters()["parameters"].

    value_string/display_value are Optional[str] on purpose: the real
    handler best-effort-serializes them to None when Live's
    str_for_value()/display_value raise RuntimeError("Invalid display
    value") — seen on Operator, Compressor2, AutoFilter2 — rather than
    aborting the whole device read (see devices.py::get_device_parameters).
    """
    return {
        "index": index,
        "name": name,
        "value": value,
        "min": min,
        "max": max,
        "is_quantized": is_quantized,
        "value_string": value_string,
        "display_value": display_value,
    }


def make_device_parameters(parameters: Optional[list] = None) -> dict:
    """Canonical ``get_device_parameters`` response — mirrors
    devices.py::get_device_parameters."""
    return {
        "parameters": parameters if parameters is not None else [
            make_device_parameter(0, "Device On", 1.0, is_quantized=True,
                                   value_string="On", display_value="On"),
            make_device_parameter(1, "Cutoff", 0.5),
        ],
    }


# ─── batch_set_parameters ───────────────────────────────────────────────────

def make_batch_param_success(name: str, value: float, *, value_string: Optional[str] = None,
                              display_value: Optional[str] = None) -> dict:
    vs = value_string if value_string is not None else "%.2f" % value
    dv = display_value if display_value is not None else vs
    return {"ok": True, "name": name, "value": value, "value_string": vs, "display_value": dv}


def make_batch_param_failure(name_or_index, error: str) -> dict:
    return {"ok": False, "name_or_index": name_or_index, "error": error}


def make_batch_set_parameters_result(entries: Optional[list] = None) -> dict:
    """Canonical ``batch_set_parameters`` response — mirrors
    devices.py::batch_set_parameters.

    Partial-success contract: top-level ``ok`` is True only when every
    entry succeeded; ``applied``/``failed`` are counts, ``parameters`` is
    the per-entry {ok: True, ...} / {ok: False, error} result list. A
    mid-batch failure never aborts the whole call or strands earlier
    writes as an opaque exception.
    """
    rows = entries if entries is not None else [make_batch_param_success("Cutoff", 0.6)]
    applied = sum(1 for r in rows if r.get("ok"))
    failed = len(rows) - applied
    return {
        "ok": failed == 0,
        "applied": applied,
        "failed": failed,
        "parameters": rows,
    }


# ─── get_scene_matrix ────────────────────────────────────────────────────────

def make_scene_matrix_track_header(index: int = 0, name: str = "Track 1") -> dict:
    return {"index": index, "name": name}


def make_scene_matrix_scene_header(index: int = 0, name: str = "Scene 1", tempo: Optional[float] = None) -> dict:
    return {"index": index, "name": name, "tempo": tempo}


def make_scene_matrix_cell(state: str = "empty", *, name: Optional[str] = None,
                            color_index: Optional[int] = None) -> dict:
    """One matrix cell. ``state`` is one of empty/stopped/playing/triggered/
    recording/missing (missing = fewer clip_slots than scenes on that track).
    """
    cell: dict[str, Any] = {"state": state}
    if state not in ("empty", "missing"):
        cell["name"] = name if name is not None else "Clip"
        cell["color_index"] = color_index if color_index is not None else 0
    return cell


def make_scene_matrix(
    *,
    track_count: int = 2,
    scene_count: int = 2,
    track_names: Optional[list] = None,
    scene_names: Optional[list] = None,
    matrix: Optional[list] = None,
) -> dict:
    """Canonical ``get_scene_matrix`` response — mirrors scenes.py::get_scene_matrix.

    Layout is scenes x tracks (``matrix[scene_index][track_index]``), matching
    the real handler's row-major (outer loop over scenes) construction.
    """
    tnames = track_names if track_names is not None else [f"Track {i + 1}" for i in range(track_count)]
    snames = scene_names if scene_names is not None else [f"Scene {i + 1}" for i in range(scene_count)]

    track_headers = [make_scene_matrix_track_header(i, n) for i, n in enumerate(tnames)]
    scene_headers = [make_scene_matrix_scene_header(i, n) for i, n in enumerate(snames)]

    if matrix is not None:
        grid = matrix
    else:
        grid = [
            [make_scene_matrix_cell("empty") for _ in range(len(tnames))]
            for _ in range(len(snames))
        ]

    return {
        "tracks": track_headers,
        "scenes": scene_headers,
        "matrix": grid,
    }


# ─── make_fake_ableton ───────────────────────────────────────────────────────

class FakeAbletonConnection:
    """Drop-in stand-in for mcp_server.connection.AbletonConnection.

    Exposes BOTH ``send_command`` (sync) and ``send_command_async``
    (coroutine) so it can back either sync or async MCP tools without the
    test needing to know which one a given tool uses. Responses come from
    a dispatch table keyed by command_type; each entry is either a static
    dict/callable-free value or a callable(params) -> dict for commands
    whose response depends on the request.

    Unmapped commands raise AbletonConnectionError (mirroring what real
    Ableton does for "Unknown command type"), so a test exercising a code
    path that hits an unstubbed command fails loudly instead of returning
    None/{}.
    """

    def __init__(self, responses: Optional[dict[str, Any]] = None):
        self.responses: dict[str, Any] = dict(responses or {})
        self.calls: list[tuple[str, dict]] = []
        # A basic ping is always available so lifespan's version-check
        # startup probe doesn't need every caller to stub it explicitly.
        self.responses.setdefault("ping", {
            "pong": True,
            "remote_script_version": "test-fixture",
            "commands": [],
        })

    def send_command(self, command_type: str, params: Optional[dict] = None) -> dict:
        from mcp_server.connection import AbletonConnectionError

        params = params or {}
        self.calls.append((command_type, params))
        if command_type not in self.responses:
            raise AbletonConnectionError(
                f"[NOT_FOUND] Unknown command type '{command_type}' "
                f"(while running '{command_type}')"
            )
        entry = self.responses[command_type]
        if callable(entry):
            return entry(params)
        return entry

    async def send_command_async(self, command_type: str, params: Optional[dict] = None) -> dict:
        return self.send_command(command_type, params)

    def is_connected(self) -> bool:
        return True

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass


def make_fake_ableton(overrides: Optional[dict[str, Any]] = None) -> FakeAbletonConnection:
    """Build a FakeAbletonConnection seeded with the canonical high-traffic
    fixtures, letting callers override specific command responses.

    ``overrides`` maps command_type -> response dict OR a
    callable(params) -> dict for request-dependent responses (e.g. echoing
    back the track_index that was asked for).

    Example
    -------
        ableton = make_fake_ableton({
            "get_track_info": lambda p: make_track_info(p["track_index"]),
        })
        ableton.send_command("get_track_info", {"track_index": 3})["index"]  # 3
    """
    defaults: dict[str, Any] = {
        "get_track_info": lambda p: make_track_info(p.get("track_index", 0)),
        "get_session_info": make_session_info(),
        "get_device_parameters": make_device_parameters(),
        "batch_set_parameters": make_batch_set_parameters_result(),
        "get_scene_matrix": make_scene_matrix(),
        "get_master_track": make_master_track_info(),
    }
    defaults.update(overrides or {})
    return FakeAbletonConnection(defaults)
