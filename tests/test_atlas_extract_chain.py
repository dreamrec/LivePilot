"""Smoke tests for Pack-Atlas Phase E — Extract Chain.

All tests run without Live being open (no MCP / Ableton connection needed).

Sidecar reality notes (from Phase E inspection 2026-04-27):
  - drone-lab__emergent-planes.json:
      13 tracks.  'Mindless Self-Encounters' is a user_name on a device inside
      the 'Plane of Origin' GroupTrack (AudioEffectGroupDevice).
      Fuzzy match on "Mindless Self-Encounters" should match via the device's
      user_name, BUT the track finder searches track names — "Plane of Origin"
      is the actual track name.

      Available track names (for actual test assertions):
        ADD Source, Lower Plane, Instrument, Sample 1, Sample 2,
        Feedback Loop Distortion, Ethereal Plane, Water Plane,
        A-Reverb, B-Delay, Plane of Origin, Cluster Plane,
        Input Sources-> Feedback Loop Distortion

  - The spec smoke test uses "Mindless Self-Encounters" as the track_name —
    this will fail because it's a device user_name, not a track name.
    The adapted test uses "Plane of Origin" instead (the track that CONTAINS
    the Mindless Self-Encounters device).  See Phase E appendix for deviation note.
"""

import pytest
from mcp_server.atlas.extract_chain import (
    extract_chain,
    _emit_execution_steps,
    _find_track_by_name,
    _top_k_macros_by_deviation,
)


class TestExtractChainDryRun:
    """Spec test: test_extract_chain_dry_run (spec lines 640-651).

    DEVIATION from spec: track_name='Mindless Self-Encounters' is a device
    user_name, not a track name.  The actual track is 'Plane of Origin'.
    Fuzzy match is tried; if it fails we use 'Plane of Origin' directly.
    """

    def _get_result(self):
        # First try the spec's track_name via fuzzy match
        result = extract_chain(
            demo_entity_id="drone_lab__emergent_planes",
            track_name="Mindless Self-Encounters",
            target_track_index=-1,
            parameter_fidelity="approximate",
        )
        # If not found, fall back to actual track name
        if "error" in result:
            result = extract_chain(
                demo_entity_id="drone_lab__emergent_planes",
                track_name="Plane of Origin",
                target_track_index=-1,
                parameter_fidelity="approximate",
            )
        return result

    def test_executed_is_false(self):
        result = self._get_result()
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert result["executed"] is False

    def test_plan_has_enough_steps(self):
        result = self._get_result()
        assert "error" not in result
        assert len(result["execution_plan"]) >= 2, (
            f"Expected >= 2 steps, got {len(result['execution_plan'])}: "
            f"{result['execution_plan']}"
        )

    def test_plan_has_device_action(self):
        result = self._get_result()
        assert "error" not in result
        actions = [s["action"] for s in result["execution_plan"]]
        has_device_action = any(
            a in ("insert_device", "load_browser_item", "manual_rebuild")
            for a in actions
        )
        assert has_device_action, (
            f"Expected at least one device action in plan, got: {actions}"
        )

    def test_source_block_present(self):
        result = self._get_result()
        assert "error" not in result
        assert "source" in result
        src = result["source"]
        assert "demo" in src
        assert "track" in src
        assert "device_count" in src
        assert "device_chain" in src

    def test_sources_cited(self):
        result = self._get_result()
        assert "error" not in result
        sources_str = str(result.get("sources", []))
        assert "als-parse" in sources_str


class TestExtractChainFidelityLevels:
    """Spec test: test_extract_chain_fidelity_levels.

    exact > approximate > structure-only in terms of set_device_parameter steps.
    Uses a drone-lab track with non-zero macros.
    """

    _DEMO = "drone_lab__emergent_planes"
    _TRACK = "Plane of Origin"

    def _count_param_steps(self, result: dict) -> int:
        return sum(
            1 for s in result.get("execution_plan", [])
            if s.get("action") == "set_device_parameter"
        )

    def test_exact_produces_most_param_steps(self):
        exact = extract_chain(
            demo_entity_id=self._DEMO,
            track_name=self._TRACK,
            target_track_index=-1,
            parameter_fidelity="exact",
        )
        assert "error" not in exact

        approx = extract_chain(
            demo_entity_id=self._DEMO,
            track_name=self._TRACK,
            target_track_index=-1,
            parameter_fidelity="approximate",
        )
        assert "error" not in approx

        struct = extract_chain(
            demo_entity_id=self._DEMO,
            track_name=self._TRACK,
            target_track_index=-1,
            parameter_fidelity="structure-only",
        )
        assert "error" not in struct

        exact_params = self._count_param_steps(exact)
        approx_params = self._count_param_steps(approx)
        struct_params = self._count_param_steps(struct)

        assert struct_params == 0, (
            f"structure-only should have 0 param steps, got {struct_params}"
        )
        assert approx_params <= exact_params, (
            f"approximate ({approx_params}) should be <= exact ({exact_params})"
        )

    def test_all_fidelity_levels_return_executed_false(self):
        for fidelity in ("exact", "approximate", "structure-only"):
            result = extract_chain(
                demo_entity_id=self._DEMO,
                track_name=self._TRACK,
                target_track_index=-1,
                parameter_fidelity=fidelity,
            )
            assert result["executed"] is False, (
                f"fidelity={fidelity} should be dry-run (executed=False)"
            )

    def test_approximate_bounded_at_5_params_per_device(self):
        approx = extract_chain(
            demo_entity_id=self._DEMO,
            track_name=self._TRACK,
            target_track_index=-1,
            parameter_fidelity="approximate",
        )
        assert "error" not in approx
        # Count param steps per device index
        device_param_counts: dict[int, int] = {}
        for s in approx["execution_plan"]:
            if s.get("action") == "set_device_parameter":
                dev_idx = s.get("device_index", 0)
                device_param_counts[dev_idx] = device_param_counts.get(dev_idx, 0) + 1
        for dev_idx, count in device_param_counts.items():
            assert count <= 5, (
                f"approximate fidelity should cap at 5 params per device, "
                f"got {count} for device_index={dev_idx}"
            )


class TestExtractChainUnknownTrack:
    """Spec test: test_extract_chain_unknown_track_returns_error."""

    def test_bogus_track_name_returns_error(self):
        result = extract_chain(
            demo_entity_id="drone_lab__emergent_planes",
            track_name="This Track Definitely Does Not Exist XYZ123",
            target_track_index=-1,
        )
        assert "error" in result, (
            "Expected error for unknown track name, got success"
        )
        assert result["executed"] is False

    def test_error_includes_available_tracks(self):
        result = extract_chain(
            demo_entity_id="drone_lab__emergent_planes",
            track_name="ZZZZZ_not_a_real_track",
        )
        if "error" in result:
            assert "available_tracks" in result, (
                "Error result should list available track names"
            )
            assert len(result["available_tracks"]) > 0

    def test_bogus_demo_returns_error(self):
        result = extract_chain(
            demo_entity_id="not_a_real_pack__not_a_real_demo",
            track_name="any track",
        )
        assert "error" in result
        assert result["executed"] is False


class TestExtractChainEarthDemo:
    """Cross-demo test using drone-lab__earth."""

    def test_extract_pioneer_drone(self):
        result = extract_chain(
            demo_entity_id="drone_lab__earth",
            track_name="Pioneer Drone",
            target_track_index=-1,
            parameter_fidelity="structure-only",
        )
        assert "error" not in result, f"Error: {result.get('error')}"
        assert result["executed"] is False
        # source.track should fuzzy-match
        assert "Pioneer Drone" in result["source"]["track"]

    def test_partial_track_name_fuzzy_match(self):
        # "Pioneer" should fuzzy-match "1-Pioneer Drone"
        result = extract_chain(
            demo_entity_id="drone_lab__earth",
            track_name="Pioneer",
            target_track_index=-1,
            parameter_fidelity="structure-only",
        )
        assert "error" not in result, (
            f"Fuzzy match for 'Pioneer' failed: {result.get('error')}, "
            f"available: {result.get('available_tracks', [])}"
        )

    def test_create_track_step_present_when_no_target(self):
        result = extract_chain(
            demo_entity_id="drone_lab__earth",
            track_name="Pioneer Drone",
            target_track_index=-1,
        )
        assert "error" not in result
        actions = [s["action"] for s in result["execution_plan"]]
        assert any(
            a in ("create_midi_track", "create_audio_track")
            for a in actions
        ), f"Expected track creation step, got: {actions}"

    def test_target_track_step_when_index_given(self):
        result = extract_chain(
            demo_entity_id="drone_lab__earth",
            track_name="Pioneer Drone",
            target_track_index=3,
        )
        assert "error" not in result
        first_step = result["execution_plan"][0] if result["execution_plan"] else {}
        assert first_step.get("action") == "target_existing_track", (
            f"Expected target_existing_track as first step, got: {first_step}"
        )
        assert first_step.get("track_index") == 3


# ─── BUG-E2#3+#7: GroupTrack and ReturnTrack creation actions ─────────────────

class TestGroupTrackAndReturnTrackActions:
    """BUG-E2#3+#7: GroupTrack → manual_step, ReturnTrack → create_return_track.

    Uses drone-lab__emergent-planes which has:
      'Plane of Origin' type=GroupTrack
      'Cluster Plane'   type=GroupTrack
      'A-Reverb'        type=ReturnTrack
      'B-Delay'         type=ReturnTrack
    """

    _DEMO = "drone_lab__emergent_planes"

    def _first_action(self, track_name: str) -> str:
        result = extract_chain(
            demo_entity_id=self._DEMO,
            track_name=track_name,
            target_track_index=-1,
            parameter_fidelity="structure-only",
        )
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        return result["execution_plan"][0]["action"]

    def test_group_track_emits_manual_step(self):
        action = self._first_action("Plane of Origin")
        assert action == "manual_step", (
            f"GroupTrack should emit manual_step, got: {action}"
        )

    def test_cluster_plane_group_track_emits_manual_step(self):
        action = self._first_action("Cluster Plane")
        assert action == "manual_step", (
            f"GroupTrack 'Cluster Plane' should emit manual_step, got: {action}"
        )

    def test_return_track_emits_create_return_track(self):
        action = self._first_action("A-Reverb")
        assert action == "create_return_track", (
            f"ReturnTrack should emit create_return_track, got: {action}"
        )

    def test_b_delay_return_track_emits_create_return_track(self):
        action = self._first_action("B-Delay")
        assert action == "create_return_track", (
            f"ReturnTrack 'B-Delay' should emit create_return_track, got: {action}"
        )

    def test_midi_track_still_emits_create_midi_track(self):
        action = self._first_action("ADD Source")
        assert action == "create_midi_track", (
            f"MidiTrack should still emit create_midi_track, got: {action}"
        )

    def test_audio_track_still_emits_create_audio_track(self):
        action = self._first_action("Sample 1")
        assert action == "create_audio_track", (
            f"AudioTrack should still emit create_audio_track, got: {action}"
        )

    def test_group_track_warning_present(self):
        result = extract_chain(
            demo_entity_id=self._DEMO,
            track_name="Plane of Origin",
            target_track_index=-1,
            parameter_fidelity="structure-only",
        )
        assert "error" not in result
        warnings_str = str(result.get("warnings", []))
        assert "GroupTrack" in warnings_str or "group" in warnings_str.lower(), (
            "Expected GroupTrack warning in result"
        )


# ─── BUG-E2#PluginDevice: PluginDevice → manual_rebuild ──────────────────────

class TestPluginDeviceManualRebuild:
    """BUG-E2#PluginDevice: PluginDevice class must emit manual_rebuild, not insert_device."""

    def _make_plugin_device(self, user_name: str = "Serum") -> dict:
        return {
            "class": "PluginDevice",
            "user_name": user_name,
            "macros": [],
            "params": None,
            "depth": 0,
        }

    def test_plugin_device_emits_manual_rebuild(self):
        steps, warnings = _emit_execution_steps(
            device=self._make_plugin_device("Serum"),
            fidelity="exact",
            track_name="Test Track",
            device_index=0,
        )
        assert len(steps) == 1
        assert steps[0]["action"] == "manual_rebuild", (
            f"PluginDevice should emit manual_rebuild, got: {steps[0]['action']}"
        )

    def test_plugin_device_not_insert_device(self):
        steps, warnings = _emit_execution_steps(
            device=self._make_plugin_device("Massive X"),
            fidelity="exact",
            track_name="Test Track",
            device_index=0,
        )
        actions = [s["action"] for s in steps]
        assert "insert_device" not in actions, (
            f"PluginDevice must not emit insert_device, got: {actions}"
        )

    def test_plugin_device_emits_warning(self):
        _, warnings = _emit_execution_steps(
            device=self._make_plugin_device("Kontakt"),
            fidelity="exact",
            track_name="Test Track",
            device_index=0,
        )
        assert len(warnings) == 1
        assert "PluginDevice" in warnings[0] or "plugin" in warnings[0].lower()

    def test_plugin_device_manual_rebuild_has_note(self):
        steps, _ = _emit_execution_steps(
            device=self._make_plugin_device("Vital"),
            fidelity="approximate",
            track_name="Test Track",
            device_index=2,
        )
        assert steps[0].get("note"), "manual_rebuild step must include a note"
        assert "PluginDevice" in steps[0]["note"] or "plugin" in steps[0]["note"].lower()

    def test_plugin_device_with_metadata_surfaces_in_manual_rebuild(self):
        """When the parser captured plugin identity (Live 12+ schema), the
        manual_rebuild step should expose vendor/format + browser_search_hint."""
        device = self._make_plugin_device("Verb Bus")
        device["plugin"] = {
            "format": "VST",
            "name": "Valhalla VintageVerb",
            "manufacturer": "Valhalla DSP",
            "file_name": "ValhallaVintageVerb.vst",
            "unique_id": "vlh1",
            "exposed_param_count": 12,
        }
        steps, warnings = _emit_execution_steps(
            device=device, fidelity="exact",
            track_name="Test Track", device_index=0,
        )
        step = steps[0]
        assert step["action"] == "manual_rebuild"
        assert step["plugin"]["name"] == "Valhalla VintageVerb"
        assert step["plugin"]["manufacturer"] == "Valhalla DSP"
        # browser_search_hint uses the plugin's display name (more reliable
        # than rack user_name) and routes to the plugins/ browser path.
        assert step["browser_search_hint"]["name_filter"] == "Valhalla VintageVerb"
        assert step["browser_search_hint"]["suggested_path"] == "plugins"
        # Note text mentions format + manufacturer for agent context.
        assert "VST" in step["note"]
        assert "Valhalla DSP" in step["note"]
        # Warning mentions format + vendor.
        assert "VST" in warnings[0] and "Valhalla DSP" in warnings[0]

    def test_plugin_device_without_metadata_still_works(self):
        """Older sidecars (pre-v1.23.4 parser) have no `plugin` field — must
        still emit a usable manual_rebuild with a fallback browser_search_hint."""
        device = self._make_plugin_device("Mystery FX")
        # No 'plugin' key — simulating old sidecar
        steps, _ = _emit_execution_steps(
            device=device, fidelity="exact",
            track_name="Test Track", device_index=0,
        )
        step = steps[0]
        assert step["action"] == "manual_rebuild"
        assert "plugin" not in step  # cleanly omitted, not None
        assert step["browser_search_hint"]["name_filter"] == "Mystery FX"


# ─── BUG-E2#5: approximate fidelity sorts by deviation from default ───────────

class TestApproximateFidelityDeviationSort:
    """BUG-E2#5: _top_k_macros_by_deviation uses preset defaults when provided."""

    def _make_macros(self, index_value_pairs: list[tuple[int, float]]) -> list[dict]:
        return [{"index": i, "value": str(v)} for i, v in index_value_pairs]

    def test_without_defaults_sorts_by_abs_value(self):
        # Highest abs value should come first
        macros = self._make_macros([(0, 50), (1, 127), (2, 30)])
        top = _top_k_macros_by_deviation(macros, k=2, preset_defaults=None)
        assert top[0]["index"] == 1  # 127 is largest abs
        assert top[1]["index"] == 0  # 50 second

    def test_with_defaults_sorts_by_deviation_from_default(self):
        # index 0: live=50, default=48 → deviation=2
        # index 1: live=127, default=127 → deviation=0 (pinned at max — no change)
        # index 2: live=30, default=0 → deviation=30
        macros = self._make_macros([(0, 50), (1, 127), (2, 30)])
        defaults = {0: 48.0, 1: 127.0, 2: 0.0}
        top = _top_k_macros_by_deviation(macros, k=2, preset_defaults=defaults)
        # index 2 should be first (deviation 30), index 0 second (deviation 2)
        assert top[0]["index"] == 2
        assert top[1]["index"] == 0

    def test_pinned_max_macro_deprioritized_with_defaults(self):
        # A macro pinned at 127 with a default of 127 has zero deviation
        macros = self._make_macros([(0, 127), (1, 65), (2, 10)])
        defaults = {0: 127.0, 1: 50.0, 2: 0.0}
        top = _top_k_macros_by_deviation(macros, k=1, preset_defaults=defaults)
        # index 1 has deviation=15, index 0 has deviation=0
        # index 2 has deviation=10
        assert top[0]["index"] == 1  # deviation 15 wins


# ─── BUG-extract_chain-fuzzy: ambiguity warning ───────────────────────────────

class TestFuzzyMatchAmbiguityWarning:
    """BUG-extract_chain-fuzzy: fuzzy match with >=2 hits returns ambiguity_warning."""

    _DEMO = "drone_lab__emergent_planes"

    def test_ambiguous_match_includes_matched_track_field(self):
        # "Plane" matches: Lower Plane, Ethereal Plane, Water Plane,
        # Plane of Origin, Cluster Plane — 5+ candidates
        result = extract_chain(
            demo_entity_id=self._DEMO,
            track_name="plane",
            target_track_index=-1,
            parameter_fidelity="structure-only",
        )
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "matched_track" in result, (
            "ambiguous fuzzy match must include matched_track field"
        )

    def test_ambiguous_match_includes_ambiguity_warning_field(self):
        result = extract_chain(
            demo_entity_id=self._DEMO,
            track_name="plane",
            target_track_index=-1,
            parameter_fidelity="structure-only",
        )
        assert "error" not in result
        assert "ambiguity_warning" in result, (
            "ambiguous fuzzy match must include ambiguity_warning field"
        )

    def test_ambiguity_warning_lists_other_candidates(self):
        result = extract_chain(
            demo_entity_id=self._DEMO,
            track_name="plane",
            target_track_index=-1,
            parameter_fidelity="structure-only",
        )
        assert "error" not in result
        warning = result.get("ambiguity_warning", "")
        # Should mention the other candidates
        assert "candidate" in warning.lower() or "matched" in warning.lower(), (
            f"ambiguity_warning should describe alternatives: {warning}"
        )

    def test_exact_match_has_no_ambiguity_warning(self):
        result = extract_chain(
            demo_entity_id=self._DEMO,
            track_name="A-Reverb",  # exact name
            target_track_index=-1,
            parameter_fidelity="structure-only",
        )
        assert "error" not in result
        assert "ambiguity_warning" not in result, (
            "exact match should not have ambiguity_warning"
        )

    def test_find_track_by_name_returns_tuple(self):
        from mcp_server.atlas.extract_chain import _find_track_by_name
        demo = {"tracks": [
            {"name": "Lower Plane"},
            {"name": "Ethereal Plane"},
            {"name": "Water Plane"},
        ]}
        track, others = _find_track_by_name(demo, "plane")
        assert track is not None
        assert len(others) == 2, f"Expected 2 other candidates, got: {others}"


# ─── BUG-INT#2: chain recursion — inner chain classes surfaced ─────────────────

class TestChainRecursionInnerDevices:
    """BUG-INT#2: _walk_device_chain now recurses into dev.chains.

    Uses mood-reel__chapter-one-by-thomas-ragsdale, track '3-Saturn Ascends':
      InstrumentGroupDevice (Saturn Ascends)
        chains → [InstrumentVector (Nasal Bass), Pedal, Erosion, Limiter]
      Delay
      AudioEffectGroupDevice (EQ Eight)
        chains → [Eq8]

    Before fix: device_chain_summary listed only top-level classes, no Erosion.
    After fix : inner_chain_classes and chain_summary expose nested devices.
    """

    _DEMO = "mood_reel__chapter_one_by_thomas_ragsdale"
    _TRACK = "3-Saturn Ascends"

    def _get_result(self):
        result = extract_chain(
            demo_entity_id=self._DEMO,
            track_name=self._TRACK,
            parameter_fidelity="exact",
        )
        if "error" in result and "not found" in result["error"].lower():
            pytest.skip(f"mood-reel chapter-one sidecar not available: {result['error']}")
        return result

    def test_inner_chain_classes_present_on_rack_device(self):
        result = self._get_result()
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        chain = result["source"]["device_chain"]
        rack_entries = [d for d in chain if d.get("class") == "InstrumentGroupDevice"]
        assert rack_entries, "Expected at least one InstrumentGroupDevice in device_chain"
        rack = rack_entries[0]
        inner = rack.get("inner_chain_classes", [])
        assert inner, "inner_chain_classes should be populated for InstrumentGroupDevice with chains"

    def test_erosion_visible_in_inner_chain_classes(self):
        result = self._get_result()
        assert "error" not in result
        chain = result["source"]["device_chain"]
        all_inner = []
        for d in chain:
            all_inner.extend(d.get("inner_chain_classes", []))
        assert "Erosion" in all_inner, (
            f"Erosion not found in inner_chain_classes. Full inner: {all_inner}"
        )

    def test_chain_summary_on_rack_step_mentions_erosion(self):
        result = self._get_result()
        assert "error" not in result
        plan = result["execution_plan"]
        rack_steps = [
            s for s in plan
            if s.get("action") in ("load_browser_item", "manual_rebuild")
            and s.get("chain_summary")
        ]
        assert rack_steps, "Expected at least one plan step with chain_summary"
        combined = " ".join(s.get("chain_summary", "") for s in rack_steps)
        assert "Erosion" in combined, (
            f"Erosion not found in any chain_summary field. Got: {combined}"
        )

    def test_top_level_device_count_unchanged(self):
        """Recursion must not inflate the top-level device count."""
        result = self._get_result()
        assert "error" not in result
        # Saturn Ascends has 3 top-level devices: InstrumentGroupDevice, Delay,
        # AudioEffectGroupDevice
        assert result["source"]["device_count"] == 3, (
            f"Expected 3 top-level devices, got: {result['source']['device_count']}"
        )


# ─── BUG-EDGE#8: empty track_name guard ──────────────────────────────────────

class TestEmptyTrackNameGuard:
    """BUG-EDGE#8: empty / whitespace-only track_name must return error, not
    silently pick the first track.

    Root cause: '' in any_string is always True, so pass-2 fuzzy match
    matched every track and returned candidates[0].
    """

    _DEMO = "drone_lab__earth"

    def test_empty_string_returns_error(self):
        result = extract_chain(
            demo_entity_id=self._DEMO,
            track_name="",
        )
        assert "error" in result, (
            "Empty track_name should return an error, not a plan"
        )
        assert result.get("executed") is False

    def test_whitespace_only_returns_error(self):
        result = extract_chain(
            demo_entity_id=self._DEMO,
            track_name="   ",
        )
        assert "error" in result
        assert "track_name" in result["error"].lower() or "required" in result["error"].lower()

    def test_empty_track_name_returns_available_tracks(self):
        result = extract_chain(
            demo_entity_id=self._DEMO,
            track_name="",
        )
        assert "available_tracks" in result, (
            "Empty track_name error must include available_tracks list"
        )
        assert len(result["available_tracks"]) > 0

    def test_empty_track_name_error_has_status_field(self):
        result = extract_chain(
            demo_entity_id=self._DEMO,
            track_name="",
        )
        assert result.get("status") == "error"

    def test_nonempty_track_name_still_works(self):
        result = extract_chain(
            demo_entity_id=self._DEMO,
            track_name="Pioneer Drone",
            parameter_fidelity="structure-only",
        )
        assert "error" not in result, f"Valid track_name should succeed: {result.get('error')}"
        assert "Pioneer Drone" in result["source"]["track"]
