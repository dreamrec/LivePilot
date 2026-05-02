"""Tests for compose(mode="full") apply infrastructure (2026-05-01).

Covers the 5 fixes that brought full mode to parity with fast mode after
live testing exposed:
  - Planner emitting wrong-unit param values (5+1 bugs in _ROLE_TEMPLATES)
  - load_sample_to_simpler skipping post-load Volume/Ve Mode/playback-mode
    hygiene → silent Simplers after sample load
  - No apply helper (agent had to walk 60+ TCP commands by hand)
  - No fresh-project pre-flight (left default tracks polluting the session)
  - No post-flight cleanup (leftover default tracks survived)

These are pure-computation tests against the helpers and the _ROLE_TEMPLATES
dict; the live-TCP path is exercised in the actual MCP session.
"""

from __future__ import annotations

import asyncio


# ── Item 2: planner param-unit fixes ──────────────────────────────


def test_drums_compressor_threshold_is_normalized():
    """Compressor 2 (modern default) Threshold is 0-1 normalized.
    Pre-fix value was -12.0 (dB direct) which fails on modern Live."""
    from mcp_server.composer.layer_planner import _ROLE_TEMPLATES

    drums = _ROLE_TEMPLATES["drums"]
    comp = next(p for p in drums["processing"] if p["name"] == "Compressor")
    threshold = comp["params"]["Threshold"]
    ratio = comp["params"]["Ratio"]
    assert 0.0 <= threshold <= 1.0, f"Threshold {threshold} not normalized 0-1"
    assert 0.0 <= ratio <= 1.0, f"Ratio {ratio} not normalized 0-1"


def test_bass_saturator_drive_is_normalized():
    """Saturator Drive is 0-1 normalized (0.6 ≈ +7 dB).
    Pre-fix value was 6.0 which is out of range and gets rejected."""
    from mcp_server.composer.layer_planner import _ROLE_TEMPLATES

    bass = _ROLE_TEMPLATES["bass"]
    sat = next(p for p in bass["processing"] if p["name"] == "Saturator")
    drive = sat["params"]["Drive"]
    assert 0.0 <= drive <= 1.0, f"Drive {drive} not normalized 0-1"


def test_eq_eight_filter_type_is_int_not_string():
    """EQ Eight `1 Filter Type A` is an int 0-7 enum.
    Pre-fix value was the string "highpass" which fails the param dispatch."""
    from mcp_server.composer.layer_planner import _ROLE_TEMPLATES

    for role in ("drums", "bass", "percussion"):
        spec = _ROLE_TEMPLATES[role]
        eq = next(p for p in spec["processing"] if p["name"] == "EQ Eight")
        ft = eq["params"]["1 Filter Type A"]
        assert isinstance(ft, int), (
            f"{role} EQ Eight Filter Type {ft!r} is {type(ft).__name__}, expected int"
        )
        assert 0 <= ft <= 7


def test_eq_eight_frequency_is_normalized():
    """EQ Eight `1 Frequency A` is 0-1 normalized log-scale on AutoFilter2.
    Pre-fix values were 30.0 / 200.0 (Hz direct) which fail."""
    from mcp_server.composer.layer_planner import _ROLE_TEMPLATES

    for role in ("drums", "bass", "percussion"):
        spec = _ROLE_TEMPLATES[role]
        eq = next(p for p in spec["processing"] if p["name"] == "EQ Eight")
        freq = eq["params"]["1 Frequency A"]
        assert 0.0 <= freq <= 1.0, (
            f"{role} EQ Eight Frequency {freq} not normalized 0-1"
        )


def test_chorus_ensemble_param_is_rate_not_rate_one():
    """Chorus-Ensemble's param is `Rate`, not `Rate 1`.
    Pre-fix used `Rate 1` which doesn't exist on the device."""
    from mcp_server.composer.layer_planner import _ROLE_TEMPLATES

    pad = _ROLE_TEMPLATES["pad"]
    chorus = next(p for p in pad["processing"] if p["name"] == "Chorus-Ensemble")
    assert "Rate" in chorus["params"]
    assert "Rate 1" not in chorus["params"], (
        "Chorus-Ensemble param `Rate 1` doesn't exist on the device"
    )


def test_grain_delay_drywet_no_slash():
    """Grain Delay's wet param is `DryWet` (no slash), distinct from
    Reverb's `Dry/Wet`. Pre-fix used `Dry/Wet` which fails."""
    from mcp_server.composer.layer_planner import _ROLE_TEMPLATES

    texture = _ROLE_TEMPLATES["texture"]
    grain = next(p for p in texture["processing"] if p["name"] == "Grain Delay")
    assert "DryWet" in grain["params"]
    assert "Dry/Wet" not in grain["params"], (
        "Grain Delay param is named DryWet (no slash), unlike Reverb"
    )


def test_reverb_keeps_dry_wet_with_slash():
    """Reverb's wet param IS `Dry/Wet` (with slash) — verified live.
    Sanity check that we didn't over-rename in the bulk fix."""
    from mcp_server.composer.layer_planner import _ROLE_TEMPLATES

    pad = _ROLE_TEMPLATES["pad"]
    reverb = next(p for p in pad["processing"] if p["name"] == "Reverb")
    assert "Dry/Wet" in reverb["params"]


def test_no_string_in_eq_eight_filter_types():
    """Defensive sweep: no role's EQ Eight filter type is a string anywhere."""
    from mcp_server.composer.layer_planner import _ROLE_TEMPLATES

    bad: list[str] = []
    for role, spec in _ROLE_TEMPLATES.items():
        for proc in spec.get("processing", []):
            if proc.get("name") == "EQ Eight":
                ft = proc.get("params", {}).get("1 Filter Type A")
                if isinstance(ft, str):
                    bad.append(f"{role}.{proc['name']}.Filter Type A = {ft!r}")
    assert not bad, f"String filter types still present: {bad}"


# ── Item 3: Simpler post-load hygiene ─────────────────────────────


def test_is_warped_loop_matches_splice_drum_loop_naming():
    """Splice drum loop filenames use `_125_` style BPM markers, not
    `125bpm` literal. The broadened detection must catch them."""
    from mcp_server.tools._analyzer_engine.sample import _is_warped_loop

    splice_paths = [
        "/Users/me/Splice/sounds/packs/Lo-Fi House/SM172/drum_loops/125/lfh_drums_125_hubble.wav",
        "/some/path/Loop_Pack/drum_loops/126/awesome_drums_126.wav",
        "/Splice/sounds/packs/Pack_Name/melodic_loops/85/melody_85_xyz.wav",
    ]
    for p in splice_paths:
        assert _is_warped_loop(p), f"Should detect loop: {p}"


def test_is_warped_loop_detects_explicit_bpm_pattern():
    """Original `125bpm` literal pattern must still match (regression)."""
    from mcp_server.tools._analyzer_engine.sample import _is_warped_loop

    assert _is_warped_loop("/some/path/song_125bpm_kick.wav")
    assert _is_warped_loop("/x/loop_at_140 BPM.wav")


def test_is_warped_loop_excludes_explicit_oneshots():
    """Files with 'oneshot' or 'one_shot' in path/name must NOT be flagged
    as loops, even if path also has loop hints."""
    from mcp_server.tools._analyzer_engine.sample import _is_warped_loop

    oneshots = [
        "/Splice/sounds/packs/Pack/One_Shots/Bass/TL_OneShot_Bass_LAGirl_C_sharp.wav",
        "/path/oneshots/kick_OS_001.wav",
        "/path/Drums/one-shot_snare.wav",
    ]
    for p in oneshots:
        assert not _is_warped_loop(p), f"Should NOT detect as loop: {p}"


def test_is_warped_loop_matches_loop_keyword():
    """`loop` keyword in filename triggers loop detection."""
    from mcp_server.tools._analyzer_engine.sample import _is_warped_loop

    assert _is_warped_loop("/path/some_loop_pack/drum_loop_amen.wav")


def test_is_warped_loop_matches_path_segment():
    """Path components like `/loops/` or `/melodic_loops/` trigger detection
    even when filename itself has no obvious markers."""
    from mcp_server.tools._analyzer_engine.sample import _is_warped_loop

    assert _is_warped_loop("/x/melodic_loops/some_clip.wav")
    assert _is_warped_loop("/x/drum_loops/clip.wav")
    assert _is_warped_loop("/x/pad_loops/clip.wav")


# ── Item 1: compose_full_apply $from_step resolution ──────────────


def test_resolve_from_step_substitutes_simple_reference():
    """The basic case — a single $from_step ref resolves to a captured
    value via path."""
    from mcp_server.composer.tools import _resolve_from_step

    step_results = {
        "layer_0_dev_0": {"loaded": "EQ Eight", "device_index": 1, "track_index": 0},
    }
    params = {
        "track_index": 0,
        "device_index": {"$from_step": "layer_0_dev_0", "path": "device_index"},
        "parameter_name": "1 Filter Type A",
        "value": 1,
    }
    resolved = _resolve_from_step(params, step_results)
    assert resolved["device_index"] == 1
    assert resolved["track_index"] == 0  # untouched
    assert resolved["value"] == 1  # untouched


def test_resolve_from_step_handles_no_refs():
    """Plain params with no $from_step pass through unchanged."""
    from mcp_server.composer.tools import _resolve_from_step

    params = {"track_index": 0, "device_name": "Saturator"}
    resolved = _resolve_from_step(params, {})
    assert resolved == params


def test_resolve_from_step_raises_on_unknown_step():
    """Reference to a step_id that wasn't captured raises ValueError."""
    from mcp_server.composer.tools import _resolve_from_step
    import pytest

    params = {
        "device_index": {"$from_step": "missing_step", "path": "device_index"},
    }
    with pytest.raises(ValueError, match=r"unknown step"):
        _resolve_from_step(params, {})


def test_resolve_from_step_raises_on_bad_path():
    """Reference to a step_id that exists, but path key not in result."""
    from mcp_server.composer.tools import _resolve_from_step
    import pytest

    step_results = {"my_step": {"foo": "bar"}}
    params = {"x": {"$from_step": "my_step", "path": "nonexistent"}}
    with pytest.raises(ValueError, match=r"path"):
        _resolve_from_step(params, step_results)


def test_resolve_from_step_handles_nested_dicts():
    """$from_step resolves recursively inside nested dict values."""
    from mcp_server.composer.tools import _resolve_from_step

    step_results = {"s1": {"device_index": 5}}
    params = {
        "outer": {
            "inner": {"$from_step": "s1", "path": "device_index"},
            "literal": "abc",
        }
    }
    resolved = _resolve_from_step(params, step_results)
    assert resolved["outer"]["inner"] == 5
    assert resolved["outer"]["literal"] == "abc"


# ── Item 1+4+5: full apply pipeline (with fake bridge) ────────────


class _FakeAbletonFull:
    """Records send_command calls and returns shaped responses for
    full-mode apply walk verification."""

    def __init__(self, fresh_default_track_count: int = 4):
        self.calls: list[tuple[str, dict]] = []
        self._track_count = fresh_default_track_count
        self._fresh = fresh_default_track_count
        self._device_counters: dict[int, int] = {}

    def send_command(self, name: str, params: dict) -> dict:
        self.calls.append((name, dict(params)))
        if name == "get_session_info":
            return {
                "track_count": self._track_count,
                "scene_count": 8,
                "scenes": [{"name": ""} for _ in range(8)],
                "tracks": [
                    {"name": f"{i + 1}-MIDI" if i < 2 else f"{i + 1}-Audio",
                     "color_index": 0}
                    for i in range(self._track_count)
                ],
            }
        if name == "get_track_info":
            ti = int(params.get("track_index", 0))
            return {
                "name": f"{ti + 1}-MIDI" if ti < self._fresh else "user-named",
                "clip_slots": [],
                "devices": [],
            }
        if name == "delete_track":
            self._track_count = max(1, self._track_count - 1)
            return {"deleted": True}
        if name == "create_midi_track":
            self._track_count += 1
            new_idx = int(params.get("index", -1))
            return {"index": new_idx, "name": params.get("name", "")}
        if name == "set_tempo":
            return {"tempo": float(params.get("tempo", 120))}
        if name == "set_track_name":
            return {"name": params.get("name")}
        if name == "set_track_volume":
            return {"volume": float(params.get("volume", 0))}
        if name == "set_track_pan":
            return {"pan": float(params.get("pan", 0))}
        if name == "insert_device":
            ti = int(params["track_index"])
            counter = self._device_counters.get(ti, 0)
            self._device_counters[ti] = counter + 1
            return {
                "loaded": params["device_name"],
                "device_index": counter + 1,  # +1 because Simpler is at 0
                "track_index": ti,
            }
        if name == "set_device_parameter":
            return {"value": params.get("value")}
        if name == "create_clip":
            return {"created": True}
        if name == "add_notes":
            return {"added": len(params.get("notes") or [])}
        if name == "create_arrangement_clip":
            return {"clip_count": 1}
        if name == "create_native_arrangement_clip":
            ci = getattr(self, "_next_arr_clip_index", 0)
            self._next_arr_clip_index = ci + 1
            return {
                "track_index": params.get("track_index", 0),
                "clip_index": ci,
                "start_time": params.get("start_time", 0),
                "length": params.get("length", 4),
                "name": params.get("name", ""),
                "has_envelope_support": True,
                "native": True,
            }
        if name == "add_arrangement_notes":
            return {"notes_added": len(params.get("notes", []))}
        if name == "set_clip_loop":
            return {"ok": True}
        return {}


class _FakeCtxFull:
    def __init__(self, ableton):
        self.lifespan_context = {"ableton": ableton}


def test_apply_full_plan_walks_simple_plan_no_load_sample():
    """A small plan with TCP-only steps should walk cleanly,
    resolving $from_step refs as it goes."""
    from mcp_server.composer.tools import _apply_full_plan

    fake = _FakeAbletonFull(fresh_default_track_count=0)  # no fresh state
    ctx = _FakeCtxFull(fake)

    plan_response = {
        "plan": [
            {"tool": "set_tempo", "params": {"tempo": 144},
             "description": "Set tempo"},
            {"step_id": "track_0", "tool": "create_midi_track",
             "params": {"index": 0}, "description": "Create track 0", "role": "drums"},
            {"tool": "set_track_name",
             "params": {"track_index": 0, "name": "Drums"},
             "description": "Name", "role": "drums"},
            {"step_id": "dev_0", "tool": "insert_device",
             "params": {"track_index": 0, "device_name": "Saturator"},
             "description": "Insert Saturator", "role": "drums"},
            {"tool": "set_device_parameter",
             "params": {
                 "track_index": 0,
                 "device_index": {"$from_step": "dev_0", "path": "device_index"},
                 "parameter_name": "Drive",
                 "value": 0.6,
             },
             "description": "Set Drive 0.6", "role": "drums"},
        ],
    }

    # Note: _apply_full_plan is async — we drive it via asyncio.run since
    # this test doesn't have a running loop.
    result = asyncio.run(_apply_full_plan(ctx, plan_response))

    assert result["phase"] == "apply"
    assert result["mode"] == "full"
    assert result["steps_executed"] == 5
    assert result["steps_failed"] == 0

    # Verify the $from_step ref resolved to 1 (the Saturator's device_index)
    setp_call = next((c for c in fake.calls if c[0] == "set_device_parameter"), None)
    assert setp_call is not None, "set_device_parameter should have been called"
    assert setp_call[1]["device_index"] == 1, (
        f"Expected device_index=1 from $from_step, got {setp_call[1]['device_index']}"
    )


def test_apply_full_plan_runs_preflight_on_fresh_project():
    """When the session looks like a fresh project (4 default tracks),
    pre-flight should delete N-1 of them before walking."""
    from mcp_server.composer.tools import _apply_full_plan

    fake = _FakeAbletonFull(fresh_default_track_count=4)
    ctx = _FakeCtxFull(fake)

    plan_response = {"plan": [
        {"tool": "set_tempo", "params": {"tempo": 144}, "description": ""},
    ]}
    result = asyncio.run(_apply_full_plan(ctx, plan_response))

    # Pre-flight should have detected the fresh project + deleted 3 of 4 default tracks
    fresh_actions = result["fresh_project_actions"]
    assert any("detected_fresh_project" in a for a in fresh_actions)
    assert any("deleted_3_default_tracks_preflight" in a for a in fresh_actions)
    delete_calls = [c for c in fake.calls if c[0] == "delete_track"]
    assert len(delete_calls) >= 3, f"Expected ≥3 pre-flight deletes, got {len(delete_calls)}"


def test_apply_full_plan_skips_preflight_on_user_session():
    """When the session has user-named tracks, pre-flight should NOT
    delete anything (would destroy the user's work)."""
    from mcp_server.composer.tools import _apply_full_plan
    from mcp_server.composer import fast as fast_compose

    fake = _FakeAbletonFull(fresh_default_track_count=0)  # no defaults
    ctx = _FakeCtxFull(fake)
    plan_response = {"plan": [{"tool": "set_tempo", "params": {"tempo": 120},
                               "description": ""}]}
    result = asyncio.run(_apply_full_plan(ctx, plan_response))

    # No deletions in pre-flight
    fresh = result["fresh_project_actions"]
    assert not any("deleted" in a for a in fresh)


def test_apply_full_plan_reports_per_step_outcomes():
    """Per-step diagnostics include description + role + step_id for each
    step, in plan order. Failed steps don't abort the walk."""
    from mcp_server.composer.tools import _apply_full_plan

    fake = _FakeAbletonFull(fresh_default_track_count=0)
    ctx = _FakeCtxFull(fake)
    plan_response = {"plan": [
        {"step_id": "s1", "tool": "set_tempo", "params": {"tempo": 144},
         "description": "Set tempo", "role": None},
        {"step_id": "s2", "tool": "set_track_name",
         "params": {"track_index": 0, "name": "Drums"},
         "description": "Name track 0", "role": "drums"},
    ]}
    result = asyncio.run(_apply_full_plan(ctx, plan_response))

    outcomes = result["step_outcomes"]
    assert len(outcomes) == 2
    assert outcomes[0]["step_id"] == "s1"
    assert outcomes[0]["description"] == "Set tempo"
    assert outcomes[0]["ok"] is True
    assert outcomes[1]["role"] == "drums"


def test_apply_full_plan_handles_unresolvable_from_step_gracefully():
    """A bad $from_step ref should fail that step but NOT abort the walk."""
    from mcp_server.composer.tools import _apply_full_plan

    fake = _FakeAbletonFull(fresh_default_track_count=0)
    ctx = _FakeCtxFull(fake)
    plan_response = {"plan": [
        {"tool": "set_device_parameter",
         "params": {
             "track_index": 0,
             "device_index": {"$from_step": "never_existed", "path": "device_index"},
             "parameter_name": "Drive",
             "value": 0.6,
         },
         "description": "Bad ref"},
        {"tool": "set_tempo", "params": {"tempo": 144},
         "description": "Should still run after bad step"},
    ]}
    result = asyncio.run(_apply_full_plan(ctx, plan_response))

    assert result["steps_executed"] == 2
    assert result["steps_failed"] == 1
    # Second step (set_tempo) should have succeeded despite first failing
    assert result["step_outcomes"][1]["ok"] is True


# ── 2026-05-01 follow-up patches surfaced by live test ─────────────


def test_planner_emits_full_clip_length_trigger_note():
    """BUG-FULL-MODE-6: trigger note duration must equal SOURCE_BEATS so
    the sample plays continuously through each clip iteration. Pre-fix
    duration=1 caused choppy 1-beat-of-4 playback."""
    # SOURCE_BEATS is a function-local constant in engine.py; read the
    # source directly to verify the literal at the emit site rather than
    # importing it. Two acceptable forms (with/without the space).
    import mcp_server.composer.engine as engine
    src = open(engine.__file__).read()
    assert (
        '"duration": SOURCE_BEATS' in src
        or '"duration":SOURCE_BEATS' in src
    ), (
        "Trigger note duration should reference SOURCE_BEATS, not a "
        "hardcoded 1.0 — see BUG-FULL-MODE-6"
    )
    # Also verify there's no leftover hardcoded `"duration": 1.0` in the
    # add_notes step (would indicate the patch wasn't applied).
    assert '"duration": 1.0,       # 1 beat' not in src, (
        "Old 1-beat duration literal should be removed"
    )


def test_simpler_hygiene_no_longer_overrides_ve_mode():
    """BUG-FULL-MODE-3 reconsidered: Ve Mode = 4 was the wrong default
    (caused tremolo cycling on long notes). Hygiene must NOT touch
    Ve Mode and let Live's default `0=None` (standard ADSR) stand."""
    src = open(
        "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot/mcp_server/tools/_analyzer_engine/sample.py"
    ).read()
    # The hygiene_params list must NOT include Ve Mode anymore
    hygiene_section_idx = src.find("hygiene_params: list[dict]")
    assert hygiene_section_idx > 0
    hygiene_block = src[hygiene_section_idx:hygiene_section_idx + 600]
    assert '"Ve Mode"' not in hygiene_block, (
        "hygiene_params list should NOT include Ve Mode override anymore"
    )


def test_simpler_hygiene_still_sets_volume_and_snap():
    """Regression: Volume=0 and Snap=0 are still mandatory hygiene."""
    src = open(
        "/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot/mcp_server/tools/_analyzer_engine/sample.py"
    ).read()
    assert '"Volume"' in src
    assert '"Snap"' in src
    # Note: just structural — verifying the literal names are still in
    # the file. Functional behavior is exercised in the live MCP session.


# Pre-flight bridge reconnect (Item 4 follow-up)


class _FakeAbletonFullWithBridge(_FakeAbletonFull):
    """Extends the basic fake with bridge-state tracking so we can
    verify reconnect_bridge gets called from pre-flight."""

    def __init__(self, fresh_default_track_count: int = 4):
        super().__init__(fresh_default_track_count)
        self.bridge_reconnect_called = False


def test_apply_full_plan_calls_reconnect_bridge_in_preflight(monkeypatch):
    """BUG-FULL-MODE-7 + BUG-FULL-MODE-14: pre-flight loads the analyzer,
    calls reconnect_bridge, then pings the bridge with retry logic to ensure
    the M4L JS listener has bound its UDP socket before the plan walk begins."""
    from mcp_server.composer.tools import _apply_full_plan
    import mcp_server.tools.analyzer as analyzer_module
    import mcp_server.tools._analyzer_engine.context as context_module

    # Track whether reconnect_bridge was called
    called: dict[str, bool] = {"reconnect": False}

    async def fake_reconnect(ctx):
        called["reconnect"] = True
        return {"ok": True, "message": "fake bridge connected"}

    # Also mock ensure_analyzer_on_master so it doesn't hit Ableton
    def fake_ensure_analyzer(ctx):
        return {"status": "loaded", "device_index": 0}

    # Mock _get_m4l to return a fake bridge that responds to ping
    class _FakeBridge:
        async def send_command(self, cmd, *args, **kwargs):
            return {"pong": True}

    monkeypatch.setattr(analyzer_module, "reconnect_bridge", fake_reconnect)
    monkeypatch.setattr(analyzer_module, "ensure_analyzer_on_master", fake_ensure_analyzer)
    monkeypatch.setattr(context_module, "_get_m4l", lambda ctx: _FakeBridge())

    fake = _FakeAbletonFull(fresh_default_track_count=0)
    ctx = _FakeCtxFull(fake)
    plan_response = {"plan": [
        {"tool": "set_tempo", "params": {"tempo": 122}, "description": ""},
    ]}
    result = asyncio.run(_apply_full_plan(ctx, plan_response))

    assert called["reconnect"] is True, "reconnect_bridge should have been called in pre-flight"
    assert "bridge_connected" in result["fresh_project_actions"]


# Post-flight full-scan cleanup (Item 5 follow-up)


class _FakeAbletonFullScanCleanup(_FakeAbletonFull):
    """Models a session where the leftover default track sits at a
    non-zero index after the plan created new tracks at 0-4."""

    def __init__(self):
        super().__init__(fresh_default_track_count=0)
        # Simulate post-plan state: 5 user-named tracks at 0-4, plus
        # one leftover default-named "6-MIDI" at index 5.
        self._post_tracks = [
            {"name": "Drums", "color_index": 0},
            {"name": "Bass", "color_index": 0},
            {"name": "Lead", "color_index": 0},
            {"name": "Pad", "color_index": 0},
            {"name": "Texture", "color_index": 0},
            {"name": "6-MIDI", "color_index": 0},  # the leftover survivor
        ]
        self._track_count = 6
        self._delete_history: list[int] = []

    def send_command(self, name: str, params: dict) -> dict:
        self.calls.append((name, dict(params)))
        if name == "get_session_info":
            return {
                "track_count": self._track_count,
                "scene_count": 8,
                "scenes": [{"name": ""} for _ in range(8)],
                "tracks": list(self._post_tracks),
            }
        if name == "get_track_info":
            ti = int(params.get("track_index", 0))
            if 0 <= ti < len(self._post_tracks):
                track = self._post_tracks[ti]
                # User-named tracks have a clip; default-named is empty
                is_default = ti >= 5
                return {
                    "name": track["name"],
                    "clip_slots": [] if is_default else [{"has_clip": True}],
                    "devices": [] if is_default else [{"name": "Some Device"}],
                }
            return {"name": "?", "clip_slots": [], "devices": []}
        if name == "delete_track":
            ti = int(params.get("track_index", 0))
            self._delete_history.append(ti)
            if 0 <= ti < len(self._post_tracks):
                del self._post_tracks[ti]
                self._track_count = max(1, self._track_count - 1)
            return {"deleted": True}
        if name == "set_tempo":
            return {"tempo": float(params.get("tempo", 120))}
        return {}


def test_apply_full_plan_postflight_finds_default_at_nonzero_index():
    """BUG-FULL-MODE-8: post-cleanup must scan ALL tracks for default
    names, not just tracks[0]. Full mode's planner creates tracks at
    indices 0-N which pushes the survivor to a high index."""
    from mcp_server.composer.tools import _apply_full_plan

    fake = _FakeAbletonFullScanCleanup()
    ctx = _FakeCtxFull(fake)
    # Plan body is intentionally tiny — we're testing post-flight, not the walk
    plan_response = {"plan": [
        {"tool": "set_tempo", "params": {"tempo": 122}, "description": ""},
    ]}
    result = asyncio.run(_apply_full_plan(ctx, plan_response))

    # Post-flight should have found "6-MIDI" at index 5 and deleted it
    assert result["final_cleanup_actions"], (
        f"Expected at least one cleanup action, got {result['final_cleanup_actions']}"
    )
    assert any("at_5" in a or "default_track" in a for a in result["final_cleanup_actions"])
    # The delete_track call should have targeted index 5
    assert 5 in fake._delete_history


def test_apply_full_plan_postflight_preserves_user_tracks():
    """Post-cleanup must NOT delete user-named tracks even if they're
    empty (they could be intentionally placeholder)."""
    from mcp_server.composer.tools import _apply_full_plan

    fake = _FakeAbletonFull(fresh_default_track_count=0)
    ctx = _FakeCtxFull(fake)
    plan_response = {"plan": [
        {"tool": "set_tempo", "params": {"tempo": 122}, "description": ""},
    ]}
    result = asyncio.run(_apply_full_plan(ctx, plan_response))

    # No default tracks → no cleanup actions
    assert not result["final_cleanup_actions"], (
        f"Should not have deleted any tracks, got {result['final_cleanup_actions']}"
    )


# ── BUG-FULL-MODE-11: simpler_set_warp in hygiene (drum-loop tempo lock) ─


class _FakeBridge:
    """Minimal async bridge fake — records send_command calls."""

    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []

    async def send_command(self, name, *args, **kwargs):
        self.calls.append((name, tuple(args), dict(kwargs)))
        return {"ok": True}


class _FakeAbletonForHygiene:
    """Fake bridge.send_command-compatible Ableton handle that returns
    the right shapes for the hygiene function."""

    def __init__(self, simpler_name: str = "drum_loop_125_xyz"):
        self._name = simpler_name

    def send_command(self, command, params):
        if command == "get_track_info":
            return {
                "devices": [
                    {"name": self._name, "class_name": "OriginalSimpler"}
                ]
            }
        # All other writes succeed silently
        return {}


def test_simpler_hygiene_calls_warp_on_drum_loop():
    """BUG-FULL-MODE-11: post-load hygiene must enable Simpler warping
    on tempo-locked loops. Drum loops → warp_mode=0 (Beats)."""
    from mcp_server.tools._analyzer_engine.sample import _simpler_post_load_hygiene

    bridge = _FakeBridge()
    ableton = _FakeAbletonForHygiene(simpler_name="lfh_drums_125_hubble")
    file_path = "/Splice/sounds/packs/Pack/Loops/drum_loops/lfh_drums_125_hubble.wav"

    result = asyncio.run(_simpler_post_load_hygiene(
        bridge, ableton, track_index=0, device_index=0, file_path=file_path,
    ))

    warp_calls = [c for c in bridge.calls if c[0] == "simpler_set_warp"]
    assert len(warp_calls) == 1, f"Expected 1 simpler_set_warp call, got {len(warp_calls)}"
    name, args, kwargs = warp_calls[0]
    # Positional args: track_index, device_index, warping(1), warp_mode
    assert args[0] == 0  # track_index
    assert args[1] == 0  # device_index
    assert args[2] == 1  # warping ON
    assert args[3] == 0  # warp_mode = 0 (Beats) for drum loops
    assert result["warp_set"] is True


def test_simpler_hygiene_picks_texture_warp_for_vocal_loop():
    """Vocal loops → warp_mode=2 (Texture) for clean transients."""
    from mcp_server.tools._analyzer_engine.sample import _simpler_post_load_hygiene

    bridge = _FakeBridge()
    ableton = _FakeAbletonForHygiene(simpler_name="vocal_melody_140_x")
    file_path = "/Splice/sounds/packs/Pack/loops/vocal_loops/vocal_melody_140_x.wav"

    result = asyncio.run(_simpler_post_load_hygiene(
        bridge, ableton, track_index=2, device_index=0, file_path=file_path,
    ))

    warp_calls = [c for c in bridge.calls if c[0] == "simpler_set_warp"]
    assert len(warp_calls) == 1
    args = warp_calls[0][1]
    assert args[3] == 2, f"Vocal loop should use warp_mode=2 (Texture), got {args[3]}"


def test_simpler_hygiene_picks_complex_warp_for_melodic_loop():
    """Melodic / pad / synth loops → warp_mode=4 (Complex) for harmonic material."""
    from mcp_server.tools._analyzer_engine.sample import _simpler_post_load_hygiene

    bridge = _FakeBridge()
    # simpler_name must match the file stem so the verification step doesn't
    # bail early with "device name doesn't match expected file".
    ableton = _FakeAbletonForHygiene(simpler_name="melodic_loop_122_x")
    file_path = "/Splice/sounds/packs/Pack/loops/melodic_loops/melodic_loop_122_x.wav"

    result = asyncio.run(_simpler_post_load_hygiene(
        bridge, ableton, track_index=2, device_index=0, file_path=file_path,
    ))

    warp_calls = [c for c in bridge.calls if c[0] == "simpler_set_warp"]
    assert len(warp_calls) == 1
    args = warp_calls[0][1]
    assert args[3] == 4, f"Melodic loop should use warp_mode=4 (Complex), got {args[3]}"


def test_simpler_hygiene_skips_warp_on_oneshot():
    """One-shots stay un-warped — warping a kick produces phasing."""
    from mcp_server.tools._analyzer_engine.sample import _simpler_post_load_hygiene

    bridge = _FakeBridge()
    ableton = _FakeAbletonForHygiene(simpler_name="Piano_OneShot_PianoPhrase_Am")
    file_path = "/Splice/sounds/packs/Pack/One_Shots/Piano/Piano_OneShot_PianoPhrase_Am.wav"

    result = asyncio.run(_simpler_post_load_hygiene(
        bridge, ableton, track_index=1, device_index=0, file_path=file_path,
    ))

    warp_calls = [c for c in bridge.calls if c[0] == "simpler_set_warp"]
    assert len(warp_calls) == 0, (
        f"One-shot should NOT call simpler_set_warp; got {len(warp_calls)} calls"
    )
    assert result["warp_set"] is False


# ── Creative-chop mode (2026-05-01 user feedback) ─────────────────
#
# Auto-warping every loop to project tempo is the production-safe default,
# but kills the creative latitude of intentional tempo mismatch (J Dilla /
# Madlib / IDM territory — a 90-bpm loop in a 122-bpm project produces
# rhythmic chopping when the source/project ratio is musically meaningful).
# These tests cover the new `warp_strategy` parameter that supports:
#   - "always" (default): warp every loop (current behavior)
#   - "chop": never warp (creative chopping mode)
#   - "smart": warp tonal layers; for drums/perc, leave un-warped if
#     source/project ratio is in the magic set ±2% (0.5, 0.667, 0.75,
#     0.8, 1.25, 1.333, 1.5, 2.0).


def test_extract_bpm_from_filename_handles_splice_naming():
    """Splice files embed BPM as `_125_` or `_125bpm` or `125 BPM`."""
    from mcp_server.composer.tools import _extract_bpm_from_filename

    # Standard Splice naming with bare digits
    assert _extract_bpm_from_filename(
        "/Splice/sounds/packs/Pack/Loops/drum_loops/lfh_drums_125_hubble.wav"
    ) == 125
    # Underscore-bracketed BPM
    assert _extract_bpm_from_filename(
        "/Splice/path/SO_SD_90_drum_loop_slippy.wav"
    ) == 90
    # Explicit "bpm" literal
    assert _extract_bpm_from_filename(
        "/Splice/path/song_140bpm_kick.wav"
    ) == 140
    # No BPM hint → None
    assert _extract_bpm_from_filename(
        "/Splice/path/Piano_OneShot_PianoPhrase_Am.wav"
    ) is None


def test_extract_bpm_filters_implausible_values():
    """3-digit numbers in filenames aren't always BPMs (e.g. catalog IDs).
    Only 60-200 range counts as plausible BPM."""
    from mcp_server.composer.tools import _extract_bpm_from_filename

    # 250 is not a plausible BPM — too fast
    assert _extract_bpm_from_filename("/path/track_250_xyz.wav") is None
    # 50 is not a plausible BPM — too slow
    assert _extract_bpm_from_filename("/path/track_50_xyz.wav") is None
    # 60 (lower edge) is plausible
    assert _extract_bpm_from_filename("/path/track_60_xyz.wav") == 60
    # 200 (upper edge) is plausible
    assert _extract_bpm_from_filename("/path/track_200_xyz.wav") == 200


def test_is_meaningful_ratio_detects_three_four_cross_rhythm():
    """3:4 cross-rhythm (source/project ≈ 0.75) is musically meaningful."""
    from mcp_server.composer.tools import _is_meaningful_ratio

    # 90 in 120 = 0.75 exactly (3:4 cross-rhythm)
    assert _is_meaningful_ratio(90, 120) is True
    # 90 in 122 = 0.738 — within 2% of 0.75
    assert _is_meaningful_ratio(90, 122) is True
    # 75 in 100 = 0.75 exactly
    assert _is_meaningful_ratio(75, 100) is True


def test_is_meaningful_ratio_detects_half_and_double_time():
    """0.5 (half-time) and 2.0 (double-time) are the most useful ratios."""
    from mcp_server.composer.tools import _is_meaningful_ratio

    assert _is_meaningful_ratio(60, 120) is True   # 0.5 — half-time
    assert _is_meaningful_ratio(122, 244) is True  # ~0.5
    assert _is_meaningful_ratio(180, 90) is True   # 2.0 — double-time
    assert _is_meaningful_ratio(122, 61) is True   # ~2.0


def test_is_meaningful_ratio_detects_polyrhythms():
    """2:3 (~0.667) and 3:2 (1.5) polyrhythms — the J Dilla territory."""
    from mcp_server.composer.tools import _is_meaningful_ratio

    assert _is_meaningful_ratio(80, 120) is True   # 0.667 — 2:3 polyrhythm
    assert _is_meaningful_ratio(120, 80) is True   # 1.5 — 3:2 polyrhythm
    assert _is_meaningful_ratio(100, 150) is True  # 0.667


def test_is_meaningful_ratio_rejects_arbitrary_mismatches():
    """Random tempo gaps with no clean polyrhythmic relationship → reject."""
    from mcp_server.composer.tools import _is_meaningful_ratio

    # 95 in 122 = 0.778 — between 0.75 and 0.8, not within 2% of either
    assert _is_meaningful_ratio(95, 122) is False
    # 110 in 122 = 0.902 — no magic ratio nearby
    assert _is_meaningful_ratio(110, 122) is False
    # 100 in 122 = 0.820 — close to 0.8 but outside 2% tolerance
    assert _is_meaningful_ratio(100, 122) is False


def test_is_meaningful_ratio_handles_zero_and_none():
    """Defensive: missing BPM data → return False (no chopping benefit)."""
    from mcp_server.composer.tools import _is_meaningful_ratio

    assert _is_meaningful_ratio(0, 120) is False
    assert _is_meaningful_ratio(120, 0) is False
    assert _is_meaningful_ratio(None, 120) is False
    assert _is_meaningful_ratio(120, None) is False


def test_simpler_hygiene_skips_warp_when_warp_loops_false():
    """BUG-FULL-MODE-12 (2026-05-01): hygiene must honor `warp_loops=False`
    even on warped-loop file names. This is the user-controlled override
    for chop mode."""
    from mcp_server.tools._analyzer_engine.sample import _simpler_post_load_hygiene

    bridge = _FakeBridge()
    ableton = _FakeAbletonForHygiene(simpler_name="lfh_drums_125_hubble")
    file_path = "/Splice/sounds/packs/Pack/Loops/drum_loops/lfh_drums_125_hubble.wav"

    result = asyncio.run(_simpler_post_load_hygiene(
        bridge, ableton, track_index=0, device_index=0,
        file_path=file_path,
        warp_loops=False,  # explicit chop mode
    ))

    warp_calls = [c for c in bridge.calls if c[0] == "simpler_set_warp"]
    assert len(warp_calls) == 0, (
        f"warp_loops=False must skip warp; got {len(warp_calls)} calls"
    )
    assert result["warp_set"] is False


def test_simpler_hygiene_warps_when_warp_loops_true_default():
    """Regression: default warp_loops=True still warps drum loops."""
    from mcp_server.tools._analyzer_engine.sample import _simpler_post_load_hygiene

    bridge = _FakeBridge()
    ableton = _FakeAbletonForHygiene(simpler_name="lfh_drums_125_hubble")
    file_path = "/Splice/sounds/packs/Pack/Loops/drum_loops/lfh_drums_125_hubble.wav"

    # No warp_loops kwarg → default behavior
    result = asyncio.run(_simpler_post_load_hygiene(
        bridge, ableton, track_index=0, device_index=0, file_path=file_path,
    ))

    warp_calls = [c for c in bridge.calls if c[0] == "simpler_set_warp"]
    assert len(warp_calls) == 1
    assert result["warp_set"] is True


# Compose_full_apply level — strategy translation


def test_compose_full_apply_chop_strategy_skips_all_warps():
    """warp_strategy='chop' → every load_sample_to_simpler step gets
    warp_loops=False, no warping happens anywhere."""
    from mcp_server.composer.tools import _apply_full_plan
    import mcp_server.tools.analyzer as analyzer_module

    captured_load_kwargs: list[dict] = []

    async def fake_load_sample_to_simpler(ctx, **kwargs):
        captured_load_kwargs.append(dict(kwargs))
        return {"sample_loaded": True, "device_index": 0}

    # Stub these out — we only care about the load_sample dispatch
    fake = _FakeAbletonFull(fresh_default_track_count=0)
    ctx = _FakeCtxFull(fake)

    # Patch via monkey-patching the module
    original = analyzer_module.load_sample_to_simpler
    analyzer_module.load_sample_to_simpler = fake_load_sample_to_simpler
    try:
        plan_response = {"plan": [
            {"tool": "load_sample_to_simpler",
             "params": {"track_index": 0, "file_path": "/x/drum_loop_120.wav"},
             "role": "drums"},
            {"tool": "load_sample_to_simpler",
             "params": {"track_index": 1, "file_path": "/x/melodic_loop_120.wav"},
             "role": "lead"},
        ]}
        asyncio.run(_apply_full_plan(ctx, plan_response, warp_strategy="chop"))
    finally:
        analyzer_module.load_sample_to_simpler = original

    # Both load calls should have been told warp_loops=False
    assert len(captured_load_kwargs) == 2
    assert captured_load_kwargs[0]["warp_loops"] is False
    assert captured_load_kwargs[1]["warp_loops"] is False


def test_compose_full_apply_smart_strategy_keeps_drums_unwarped_at_meaningful_ratio():
    """warp_strategy='smart' + drum role + meaningful BPM ratio → un-warped.
    But pad/bass/lead always warp regardless of ratio."""
    from mcp_server.composer.tools import _apply_full_plan
    import mcp_server.tools.analyzer as analyzer_module

    captured: list[dict] = []

    async def fake_load(ctx, **kwargs):
        captured.append(dict(kwargs))
        return {"sample_loaded": True, "device_index": 0}

    fake = _FakeAbletonFull(fresh_default_track_count=0)
    ctx = _FakeCtxFull(fake)

    original = analyzer_module.load_sample_to_simpler
    analyzer_module.load_sample_to_simpler = fake_load
    try:
        plan_response = {
            "intent": {"tempo": 120},  # project tempo from intent
            "plan": [
                # Drums @ 90 BPM → 0.75 ratio (3:4 cross-rhythm) → meaningful → no warp
                {"tool": "load_sample_to_simpler",
                 "params": {"track_index": 0, "file_path": "/x/drum_loop_90.wav"},
                 "role": "drums"},
                # Drums @ 110 BPM → 0.917 ratio → not meaningful → warp
                {"tool": "load_sample_to_simpler",
                 "params": {"track_index": 1, "file_path": "/x/drum_loop_110.wav"},
                 "role": "drums"},
                # Pad @ 90 BPM → ratio same as drums but pad ALWAYS warps
                {"tool": "load_sample_to_simpler",
                 "params": {"track_index": 2, "file_path": "/x/pad_loop_90.wav"},
                 "role": "pad"},
            ]
        }
        asyncio.run(_apply_full_plan(ctx, plan_response, warp_strategy="smart"))
    finally:
        analyzer_module.load_sample_to_simpler = original

    assert len(captured) == 3
    # Drum @ 90 in 120 = 0.75 (3:4) → smart strategy leaves un-warped
    assert captured[0]["warp_loops"] is False, (
        "Drum @ 90 BPM in 120 BPM project (3:4 ratio) should be un-warped"
    )
    # Drum @ 110 in 120 = 0.917 → not meaningful → still warps
    assert captured[1]["warp_loops"] is True, (
        "Drum @ 110 BPM in 120 BPM (no magic ratio) should warp"
    )
    # Pad always warps regardless of ratio
    assert captured[2]["warp_loops"] is True, (
        "Pad role should always warp regardless of ratio"
    )


def test_compose_full_apply_always_strategy_warps_everything():
    """Default strategy='always' (production-safe) — every loop warps."""
    from mcp_server.composer.tools import _apply_full_plan
    import mcp_server.tools.analyzer as analyzer_module

    captured: list[dict] = []

    async def fake_load(ctx, **kwargs):
        captured.append(dict(kwargs))
        return {"sample_loaded": True, "device_index": 0}

    fake = _FakeAbletonFull(fresh_default_track_count=0)
    ctx = _FakeCtxFull(fake)

    original = analyzer_module.load_sample_to_simpler
    analyzer_module.load_sample_to_simpler = fake_load
    try:
        plan_response = {
            "intent": {"tempo": 120},
            "plan": [
                # Even meaningful-ratio drums get warped under 'always'
                {"tool": "load_sample_to_simpler",
                 "params": {"track_index": 0, "file_path": "/x/drum_loop_90.wav"},
                 "role": "drums"},
            ]
        }
        # Default warp_strategy
        asyncio.run(_apply_full_plan(ctx, plan_response))
    finally:
        analyzer_module.load_sample_to_simpler = original

    assert len(captured) == 1
    assert captured[0]["warp_loops"] is True
