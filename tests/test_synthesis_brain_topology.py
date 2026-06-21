"""Tests for algorithm-aware / region-aware synthesis adapters (PR2/v2).

Exit condition from the PR plan: "adapter tests prove target choice
changes with patch topology/profile, not just freshness."

These tests demonstrate that:
  - Wavetable shift direction depends on current position region
    AND target.brightness (not just freshness)
  - Operator targets the real modulator per algorithm, not always B
  - Operator falls back to carrier shift on additive algorithms
  - Analog/Drift/Meld strategies are gated on role_hint + target
  - producer_payload carries strategy + topology_hint for every seed
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.synthesis_brain import (
    TimbralFingerprint,
    analyze_synth_patch,
    propose_synth_branches,
)


# ── Wavetable region-aware shift ────────────────────────────────────────


class TestWavetableRegionClassification:

    def _profile_at(self, pos: float, voices: int = 2, detune: float = 0.05):
        return analyze_synth_patch(
            device_name="Wavetable",
            track_index=0,
            device_index=0,
            parameter_state={
                "Osc 1 Position": pos,
                "Voices": voices,
                "Voices Detune": detune,
            },
        )

    def test_sub_region_with_bright_target_shifts_up(self):
        profile = self._profile_at(0.1)  # sub_region
        target = TimbralFingerprint(brightness=0.6)
        pairs = propose_synth_branches(profile, target=target)
        pos_seed = pairs[0][0]
        hint = pos_seed.producer_payload["topology_hint"]
        assert hint["current_region"] == "sub_region"
        # Target was brighter — should move up at least one region
        assert hint["target_region"] in ("mid_region", "bright_region", "complex_region")
        assert hint["new_pos"] > hint["current_pos"]

    def test_complex_region_with_dark_target_shifts_down(self):
        profile = self._profile_at(0.9)  # complex_region
        target = TimbralFingerprint(brightness=-0.6)
        pairs = propose_synth_branches(profile, target=target)
        pos_seed = pairs[0][0]
        hint = pos_seed.producer_payload["topology_hint"]
        assert hint["current_region"] == "complex_region"
        assert hint["target_region"] in ("bright_region", "mid_region", "sub_region")
        assert hint["new_pos"] < hint["current_pos"]

    def test_neutral_target_still_moves_for_contrast(self):
        profile = self._profile_at(0.2)  # sub_region
        target = TimbralFingerprint()  # all zero
        pairs = propose_synth_branches(profile, target=target)
        pos_seed = pairs[0][0]
        hint = pos_seed.producer_payload["topology_hint"]
        # Must pick a different region — can't just return current
        assert hint["target_region"] != hint["current_region"]

    def test_producer_payload_shape(self):
        profile = self._profile_at(0.3)
        pairs = propose_synth_branches(profile, target=TimbralFingerprint(brightness=0.3))
        pos_seed, _plan = pairs[0]
        p = pos_seed.producer_payload
        assert p["device_name"] == "Wavetable"
        assert p["strategy"].startswith("osc_position_to_")
        assert "topology_hint" in p
        assert {"current_region", "target_region", "current_pos", "new_pos"} <= p["topology_hint"].keys()


# ── Operator algorithm-aware targeting ──────────────────────────────────


class TestOperatorAlgorithmAwareness:

    def _profile(self, algo: int, levels: dict, coarses: dict | None = None):
        params = {"Algorithm": algo}
        for op, lvl in levels.items():
            params[f"Oscillator {op} Level"] = lvl
        for op, c in (coarses or {}).items():
            params[f"Oscillator {op} Coarse"] = c
        return analyze_synth_patch(
            device_name="Operator",
            track_index=0,
            device_index=0,
            parameter_state=params,
        )

    def test_same_levels_different_algos_target_different_ops(self):
        # Algorithm 2: carriers = [B, C, D], modulators = [A]
        # Algorithm 4: carriers = [C, D],    modulators = [A, B]
        # Same Level distribution: A=0.3, B=0.9. Under algo 2 we must
        # pick A (the only modulator). Under algo 4 we pick B (highest
        # Level among modulators).
        levels = {"A": 0.3, "B": 0.9, "C": 0.5, "D": 0.8}
        coarses = {"A": 2, "B": 3, "C": 1, "D": 1}

        algo2 = self._profile(2, levels, coarses)
        algo4 = self._profile(4, levels, coarses)

        pairs2 = propose_synth_branches(algo2)
        pairs4 = propose_synth_branches(algo4)

        assert pairs2[0][0].producer_payload["topology_hint"]["targeted_op"] == "A"
        assert pairs4[0][0].producer_payload["topology_hint"]["targeted_op"] == "B"

    def test_modulator_with_zero_level_is_skipped_for_nonzero(self):
        # Algo 0: modulators = [A, B, C]. Give A and C level 0, B level 0.7
        profile = self._profile(
            0,
            {"A": 0.0, "B": 0.7, "C": 0.0, "D": 0.8},
            {"A": 1, "B": 2, "C": 1, "D": 1},
        )
        pairs = propose_synth_branches(profile)
        hint = pairs[0][0].producer_payload["topology_hint"]
        assert hint["targeted_op"] == "B"

    def test_additive_algo_falls_back_to_carrier(self):
        # Algorithm 5: purely additive (all 4 ops are carriers, no modulators)
        profile = self._profile(
            5,
            {"A": 0.3, "B": 0.5, "C": 0.8, "D": 0.4},
            {"A": 1, "B": 1, "C": 1, "D": 1},
        )
        pairs = propose_synth_branches(profile)
        hint = pairs[0][0].producer_payload["topology_hint"]
        assert hint["target_role"] == "carrier"
        # Highest level carrier is C
        assert hint["targeted_op"] == "C"

    def test_topology_hint_records_full_carriers_and_modulators(self):
        profile = self._profile(
            1,
            {"A": 0.5, "B": 0.9, "C": 0.6, "D": 0.7},
            {"A": 2, "B": 2, "C": 3, "D": 1},
        )
        pairs = propose_synth_branches(profile)
        hint = pairs[0][0].producer_payload["topology_hint"]
        # Algorithm 1: carriers = [B, D], modulators = [A, C]
        assert set(hint["carriers"]) == {"B", "D"}
        assert set(hint["modulators"]) == {"A", "C"}

    def test_targeting_changes_independently_of_freshness(self):
        # Same profile + same freshness, different algos → different ops.
        # Proves targeting isn't just a freshness roulette.
        levels = {"A": 0.9, "B": 0.1, "C": 0.5, "D": 0.8}
        coarses = {"A": 2, "B": 1, "C": 3, "D": 1}
        p_algo0 = self._profile(0, levels, coarses)
        p_algo4 = self._profile(4, levels, coarses)
        kernel = {"freshness": 0.5}
        t = TimbralFingerprint()
        op_0 = propose_synth_branches(p_algo0, target=t, kernel=kernel)[0][0].producer_payload["topology_hint"]["targeted_op"]
        op_4 = propose_synth_branches(p_algo4, target=t, kernel=kernel)[0][0].producer_payload["topology_hint"]["targeted_op"]
        # Algo 0 mods = A,B,C: A has highest level → A
        # Algo 4 mods = A,B: A has highest level → A
        # Hmm — same target here. Let me use different levels.
        # Better: use levels that diverge between the two algos' modulator sets.
        # algo0 modulators = A,B,C — highest level op among A/B/C
        # algo4 modulators = A,B — highest level op among A/B
        # Making C dominant among modulators in algo0 but absent from algo4
        # forces different targets.
        assert op_0 == "A"
        assert op_4 == "A"  # documented — A is highest level in both sets
        # now try shifting C dominant
        levels2 = {"A": 0.2, "B": 0.2, "C": 0.95, "D": 0.3}
        p2 = self._profile(0, levels2, coarses)
        p4 = self._profile(4, levels2, coarses)
        op_0b = propose_synth_branches(p2, target=t, kernel=kernel)[0][0].producer_payload["topology_hint"]["targeted_op"]
        op_4b = propose_synth_branches(p4, target=t, kernel=kernel)[0][0].producer_payload["topology_hint"]["targeted_op"]
        # algo0: C is modulator AND highest → C
        # algo4: C is a CARRIER under algo4 (not modulator). Modulators A,B.
        #        So targeted op should be A or B, NOT C.
        assert op_0b == "C"
        assert op_4b != "C"


# ── Strategy registries: Analog / Drift / Meld ──────────────────────────


class TestAnalogStrategyRegistry:

    def _profile(self, role: str = "", params: dict | None = None):
        return analyze_synth_patch(
            device_name="Analog",
            track_index=0,
            device_index=0,
            parameter_state=params or {},
            role_hint=role,
        )

    def test_pad_role_skips_filter_pluck_strategy(self):
        # Pluck fights sustained roles; only detune_warmth should be emitted.
        pairs = propose_synth_branches(
            self._profile(role="pad", params={"Osc2 Tune": 0.0}),
            target=TimbralFingerprint(warmth=0.3),
        )
        strategies = {s.producer_payload["strategy"] for s, _ in pairs}
        assert "filter_pluck" not in strategies
        assert "detune_warmth" in strategies

    def test_bass_role_skips_detune_warmth(self):
        # Detune-warmth would cause woofiness on a bass role.
        pairs = propose_synth_branches(
            self._profile(role="bass", params={}),
            target=TimbralFingerprint(bite=0.4),
        )
        strategies = {s.producer_payload["strategy"] for s, _ in pairs}
        assert "detune_warmth" not in strategies
        assert "filter_pluck" in strategies

    def test_already_plucky_skips_filter_pluck(self):
        # Profile self-diagnoses "Already plucky"; strategy must honor.
        profile = self._profile(
            role="bass",
            params={"F1 Env Amount": 0.8, "F1 Env D": 0.1},
        )
        pairs = propose_synth_branches(profile, target=TimbralFingerprint(bite=0.5))
        strategies = {s.producer_payload["strategy"] for s, _ in pairs}
        assert "filter_pluck" not in strategies


class TestDriftStrategyRegistry:

    def _profile(self, role: str = "", params: dict | None = None):
        return analyze_synth_patch(
            device_name="Drift",
            track_index=0,
            device_index=0,
            parameter_state=params or {"Character": 0.2, "Sub Level": 0.3, "Filter Freq": 0.5},
            role_hint=role,
        )

    def test_bass_role_skips_filter_sweep(self):
        pairs = propose_synth_branches(
            self._profile(role="bass"),
            target=TimbralFingerprint(brightness=0.5),
        )
        strategies = {s.producer_payload["strategy"] for s, _ in pairs}
        assert not any(s.startswith("filter_sweep") for s in strategies)
        assert "character_blend" in strategies

    def test_lead_role_with_bright_target_opens_filter(self):
        pairs = propose_synth_branches(
            self._profile(role="lead"),
            target=TimbralFingerprint(brightness=0.6),
        )
        sweep_seeds = [s for s, _ in pairs if s.producer_payload["strategy"].startswith("filter_sweep")]
        assert len(sweep_seeds) == 1
        assert sweep_seeds[0].producer_payload["strategy"] == "filter_sweep_open"

    def test_pad_role_with_dark_target_closes_filter(self):
        pairs = propose_synth_branches(
            self._profile(role="pad", params={"Filter Freq": 0.8, "Character": 0.4, "Sub Level": 0.3}),
            target=TimbralFingerprint(brightness=-0.5),
        )
        sweep_seeds = [s for s, _ in pairs if s.producer_payload["strategy"].startswith("filter_sweep")]
        assert len(sweep_seeds) == 1
        assert sweep_seeds[0].producer_payload["strategy"] == "filter_sweep_close"


class TestMeldStrategyRegistry:

    def _profile(self, params: dict):
        return analyze_synth_patch(
            device_name="Meld",
            track_index=0,
            device_index=0,
            parameter_state=params,
        )

    def test_both_engines_emit_both_strategies(self):
        pairs = propose_synth_branches(
            self._profile({
                "Engine 1 Algorithm": 2,
                "Engine 2 Algorithm": 5,
                "Engine 1 Level": 0.6,
                "Engine 2 Level": 0.8,
            }),
        )
        strategies = {s.producer_payload["strategy"] for s, _ in pairs}
        assert "engine_algo_swap" in strategies
        assert any(s.startswith("engine_mix_shift") for s in strategies)

    def test_silent_engine_skips_mix_shift(self):
        pairs = propose_synth_branches(
            self._profile({
                "Engine 1 Algorithm": 2,
                "Engine 2 Algorithm": 5,
                "Engine 1 Level": 0.9,
                "Engine 2 Level": 0.0,  # silent
            }),
        )
        strategies = {s.producer_payload["strategy"] for s, _ in pairs}
        assert not any(s.startswith("engine_mix_shift") for s in strategies)
        assert "engine_algo_swap" in strategies


# ── Producer payload contract ───────────────────────────────────────────


class TestProducerPayloadContract:

    def test_every_synth_seed_carries_strategy_and_topology(self):
        profiles = [
            analyze_synth_patch("Wavetable", 0, 0, {"Osc 1 Position": 0.3, "Voices": 2}),
            analyze_synth_patch("Operator", 0, 0, {
                "Algorithm": 0,
                "Oscillator A Level": 0.7,
                "Oscillator A Coarse": 2,
            }),
            analyze_synth_patch("Analog", 0, 0, {}),
            analyze_synth_patch("Drift", 0, 0, {"Character": 0.2, "Filter Freq": 0.5}),
            analyze_synth_patch("Meld", 0, 0, {
                "Engine 1 Algorithm": 2,
                "Engine 1 Level": 0.6,
                "Engine 2 Level": 0.6,
            }),
        ]
        for profile in profiles:
            pairs = propose_synth_branches(profile)
            for seed, _plan in pairs:
                payload = seed.producer_payload
                assert "strategy" in payload, f"{profile.device_name}: missing strategy"
                assert "topology_hint" in payload, f"{profile.device_name}: missing topology_hint"
                assert payload["device_name"] == profile.device_name
                assert payload["track_index"] == profile.track_index
                assert payload["device_index"] == profile.device_index
