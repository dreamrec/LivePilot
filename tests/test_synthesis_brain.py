"""Tests for the synthesis_brain subsystem (PR9).

Covers:
  - Model construction and serialization
  - Adapter registry
  - Wavetable adapter: extract_profile + propose_branches
  - Operator adapter: extract_profile + propose_branches
  - Engine: analyze_synth_patch / propose_synth_branches dispatch
  - Opaque-fallback behavior for unsupported devices
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.branches import BranchSeed
from mcp_server.synthesis_brain import (
    SynthProfile,
    TimbralFingerprint,
    ModulationGraph,
    ArticulationProfile,
    OPAQUE,
    NATIVE,
    analyze_synth_patch,
    propose_synth_branches,
    supported_devices,
)
from mcp_server.synthesis_brain.adapters import get_adapter, registered_devices


# ── Models ──────────────────────────────────────────────────────────────


class TestModels:

    def test_timbral_fingerprint_defaults_to_zero(self):
        t = TimbralFingerprint()
        assert t.brightness == 0.0
        assert t.warmth == 0.0

    def test_modulation_graph_empty_by_default(self):
        m = ModulationGraph()
        assert m.routes == []

    def test_synth_profile_opaque_default(self):
        p = SynthProfile()
        assert p.opacity == OPAQUE
        assert p.parameter_state == {}

    def test_to_dict_shape(self):
        p = SynthProfile(
            device_name="Wavetable", opacity=NATIVE, track_index=2, device_index=0,
            parameter_state={"Voices": 4}, role_hint="pad",
        )
        d = p.to_dict()
        assert d["device_name"] == "Wavetable"
        assert d["opacity"] == NATIVE
        assert d["parameter_state"]["Voices"] == 4


# ── Registry ────────────────────────────────────────────────────────────


class TestRegistry:

    def test_wavetable_registered(self):
        assert "Wavetable" in registered_devices()

    def test_operator_registered(self):
        assert "Operator" in registered_devices()

    def test_unknown_device_returns_none(self):
        assert get_adapter("NonExistentSynth") is None

    def test_supported_devices_lists_adapters(self):
        devs = supported_devices()
        assert "Wavetable" in devs
        assert "Operator" in devs


# ── Wavetable adapter ───────────────────────────────────────────────────


class TestWavetableAdapter:

    def test_extract_profile_marks_native(self):
        p = analyze_synth_patch(
            device_name="Wavetable",
            track_index=3,
            device_index=0,
            parameter_state={"Voices": 4, "Voices Detune": 0.15, "Osc 1 Position": 0.5},
            display_values={"Voices": "4", "Voices Detune": "15 ct"},
            role_hint="pad",
        )
        assert p.opacity == NATIVE
        assert p.device_name == "Wavetable"
        assert p.track_index == 3
        assert p.role_hint == "pad"

    def test_extract_profile_notes_over_thickening(self):
        p = analyze_synth_patch(
            device_name="Wavetable",
            track_index=3,
            device_index=0,
            parameter_state={"Voices": 6, "Voices Detune": 0.3},
        )
        assert any("over-thickening" in n for n in p.notes)

    def test_extract_profile_focuses_known_params(self):
        p = analyze_synth_patch(
            device_name="Wavetable",
            track_index=3,
            device_index=0,
            parameter_state={
                "Voices": 4,
                "UnknownParam": 999,  # must be dropped from focused state
            },
        )
        assert "Voices" in p.parameter_state
        assert "UnknownParam" not in p.parameter_state

    def test_propose_branches_emits_osc_position_and_width(self):
        profile = analyze_synth_patch(
            device_name="Wavetable",
            track_index=3,
            device_index=0,
            parameter_state={"Osc 1 Position": 0.2, "Voices": 2, "Voices Detune": 0.05},
        )
        pairs = propose_synth_branches(profile)
        assert len(pairs) >= 2
        seeds = [s for s, _ in pairs]
        assert all(isinstance(s, BranchSeed) for s in seeds)
        assert all(s.source == "synthesis" for s in seeds)
        # First branch is osc position shift
        assert "Osc 1 Position" in seeds[0].hypothesis

    def test_position_shift_plan_has_single_step(self):
        profile = analyze_synth_patch(
            device_name="Wavetable",
            track_index=3,
            device_index=0,
            parameter_state={"Osc 1 Position": 0.2},
        )
        pairs = propose_synth_branches(profile)
        _seed, plan = pairs[0]
        assert plan["step_count"] == 1
        assert plan["steps"][0]["tool"] == "set_device_parameter"
        assert plan["steps"][0]["params"]["parameter_name"] == "Osc 1 Position"

    def test_width_branch_skipped_when_already_thick(self):
        profile = analyze_synth_patch(
            device_name="Wavetable",
            track_index=3,
            device_index=0,
            parameter_state={"Voices": 7, "Voices Detune": 0.25, "Osc 1 Position": 0.5},
        )
        pairs = propose_synth_branches(profile)
        # Only position shift should survive; no width variant.
        assert len(pairs) == 1
        assert "Voices" not in pairs[0][0].hypothesis

    def test_freshness_controls_shift_magnitude(self):
        profile = analyze_synth_patch(
            device_name="Wavetable",
            track_index=3,
            device_index=0,
            parameter_state={"Osc 1 Position": 0.2, "Voices": 2},
        )
        conservative = propose_synth_branches(profile, kernel={"freshness": 0.2})
        bold = propose_synth_branches(profile, kernel={"freshness": 0.9})
        # Same positional seed, different new_pos values ⇒ different seed_ids.
        assert conservative[0][0].seed_id != bold[0][0].seed_id


# ── Operator adapter ────────────────────────────────────────────────────


class TestOperatorAdapter:

    def test_extract_profile_detects_modulators(self):
        p = analyze_synth_patch(
            device_name="Operator",
            track_index=1,
            device_index=0,
            parameter_state={
                "Algorithm": 1,
                "Oscillator A Level": 1.0,
                "Oscillator A Coarse": 1,
                "Oscillator B Level": 0.5,
                "Oscillator B Coarse": 2,  # modulator (Coarse>1, Level>0)
            },
        )
        # B should be flagged as a modulator
        assert any(r["source"] == "Oscillator B" for r in p.modulation.routes)

    def test_propose_shifts_modulator_ratio(self):
        # PR2/v2: targeting is algorithm + Level aware. Give Osc B a
        # concrete Level so it becomes the picked modulator under
        # algorithm 0 (where A/B/C are all modulators).
        profile = analyze_synth_patch(
            device_name="Operator",
            track_index=1,
            device_index=0,
            parameter_state={
                "Algorithm": 0,
                "Oscillator A Level": 0.1,
                "Oscillator B Coarse": 2,
                "Oscillator B Level": 0.9,  # highest — B is picked
                "Oscillator C Level": 0.2,
            },
        )
        pairs = propose_synth_branches(profile)
        assert len(pairs) >= 1
        seed, plan = pairs[0]
        assert seed.source == "synthesis"
        assert "Osc B Coarse" in plan["summary"]
        assert plan["steps"][0]["params"]["parameter_name"] == "Oscillator B Coarse"

    def test_novelty_escalates_with_freshness(self):
        profile = analyze_synth_patch(
            device_name="Operator",
            track_index=1,
            device_index=0,
            parameter_state={"Oscillator B Coarse": 2},
        )
        low = propose_synth_branches(profile, kernel={"freshness": 0.2})
        high = propose_synth_branches(profile, kernel={"freshness": 0.9})
        # Larger step at high freshness
        low_target = low[0][1]["steps"][0]["params"]["value"]
        high_target = high[0][1]["steps"][0]["params"]["value"]
        assert abs(high_target - 2) > abs(low_target - 2)


# ── Opaque / unsupported devices ────────────────────────────────────────


class TestOpaqueFallback:

    def test_analyze_unknown_device_returns_opaque_profile(self):
        p = analyze_synth_patch(
            device_name="SomeUnknownAU",
            track_index=0,
            device_index=0,
            parameter_state={"Param1": 0.5},
        )
        assert p.opacity == OPAQUE
        assert any("No synthesis_brain adapter" in n for n in p.notes)
        # Raw params survive for callers that want to inspect.
        assert p.parameter_state == {"Param1": 0.5}

    def test_propose_opaque_returns_empty(self):
        p = SynthProfile(device_name="UnknownAU", opacity=OPAQUE)
        assert propose_synth_branches(p) == []

    def test_propose_without_adapter_returns_empty(self):
        p = SynthProfile(device_name="UnknownAU", opacity=NATIVE)
        # Opacity mismatch — registry still has no adapter for this name.
        assert propose_synth_branches(p) == []


# ── Branch-seed contract ────────────────────────────────────────────────


class TestBranchSeedContract:

    def test_seeds_are_synthesis_source(self):
        profile = analyze_synth_patch(
            device_name="Wavetable", track_index=0, device_index=0,
            parameter_state={"Osc 1 Position": 0.4},
        )
        pairs = propose_synth_branches(profile)
        for seed, _ in pairs:
            assert seed.source == "synthesis"

    def test_plans_are_execution_router_compatible(self):
        profile = analyze_synth_patch(
            device_name="Wavetable", track_index=0, device_index=0,
            parameter_state={"Osc 1 Position": 0.4, "Voices": 2},
        )
        pairs = propose_synth_branches(profile)
        for _seed, plan in pairs:
            assert "steps" in plan
            assert "step_count" in plan
            assert "summary" in plan
            for step in plan["steps"]:
                assert "tool" in step
                assert "params" in step

    def test_seeds_carry_distinctness_reason(self):
        profile = analyze_synth_patch(
            device_name="Wavetable", track_index=0, device_index=0,
            parameter_state={"Osc 1 Position": 0.4, "Voices": 2},
        )
        pairs = propose_synth_branches(profile)
        for seed, _ in pairs:
            assert seed.distinctness_reason, f"seed {seed.seed_id} missing distinctness_reason"
