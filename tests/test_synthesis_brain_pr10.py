"""Tests for PR10 additions to synthesis_brain.

Covers:
  - Analog adapter (filter_envelope_variant)
  - Drift adapter (character_blend)
  - Meld adapter (engine_algo_swap)
  - extract_timbre_fingerprint across spectrum / loudness / spectral_shape
  - diff_fingerprint
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.branches import BranchSeed
from mcp_server.synthesis_brain import (
    analyze_synth_patch,
    propose_synth_branches,
    extract_timbre_fingerprint,
    diff_fingerprint,
    supported_devices,
    TimbralFingerprint,
)


# ── Analog ──────────────────────────────────────────────────────────────


class TestAnalogAdapter:

    def test_registered(self):
        assert "Analog" in supported_devices()

    def test_filter_envelope_variant(self):
        profile = analyze_synth_patch(
            device_name="Analog",
            track_index=1,
            device_index=0,
            parameter_state={"F1 Env Amount": 0.2, "F1 Env D": 0.5},
        )
        pairs = propose_synth_branches(profile)
        assert len(pairs) == 1
        seed, plan = pairs[0]
        assert seed.source == "synthesis"
        assert "filter-pluck" in seed.hypothesis.lower()
        tool_names = [s["params"]["parameter_name"] for s in plan["steps"]]
        assert "F1 Env Amount" in tool_names
        assert "F1 Env D" in tool_names

    def test_skips_when_already_plucky(self):
        profile = analyze_synth_patch(
            device_name="Analog",
            track_index=1,
            device_index=0,
            parameter_state={"F1 Env Amount": 0.8, "F1 Env D": 0.1},
        )
        assert any("Already plucky" in n for n in profile.notes)
        assert propose_synth_branches(profile) == []


# ── Drift ───────────────────────────────────────────────────────────────


class TestDriftAdapter:

    def test_registered(self):
        assert "Drift" in supported_devices()

    def test_character_blend_variant(self):
        profile = analyze_synth_patch(
            device_name="Drift",
            track_index=2,
            device_index=0,
            parameter_state={"Character": 0.1, "Sub Level": 0.0},
        )
        pairs = propose_synth_branches(profile)
        assert len(pairs) == 1
        seed, plan = pairs[0]
        assert seed.source == "synthesis"
        assert "character" in seed.hypothesis.lower()
        names = [s["params"]["parameter_name"] for s in plan["steps"]]
        assert "Character" in names
        assert "Sub Level" in names

    def test_sub_clash_note_for_lead(self):
        profile = analyze_synth_patch(
            device_name="Drift",
            track_index=2,
            device_index=0,
            parameter_state={"Sub Level": 0.7},
            role_hint="lead",
        )
        assert any("bass clash" in n for n in profile.notes)


# ── Meld ────────────────────────────────────────────────────────────────


class TestMeldAdapter:

    def test_registered(self):
        assert "Meld" in supported_devices()

    def test_engine_algo_swap(self):
        profile = analyze_synth_patch(
            device_name="Meld",
            track_index=3,
            device_index=0,
            parameter_state={"Engine 1 Algorithm": 2, "Engine 2 Algorithm": 5},
        )
        pairs = propose_synth_branches(profile)
        assert len(pairs) == 1
        seed, plan = pairs[0]
        assert "Engine 1 Algorithm" in [s["params"]["parameter_name"] for s in plan["steps"]]
        new_algo = plan["steps"][0]["params"]["value"]
        assert new_algo != 2

    def test_same_engine_algo_notes(self):
        profile = analyze_synth_patch(
            device_name="Meld",
            track_index=3,
            device_index=0,
            parameter_state={"Engine 1 Algorithm": 4, "Engine 2 Algorithm": 4},
        )
        assert any("same algorithm" in n.lower() for n in profile.notes)

    def test_freshness_amplifies_shift(self):
        profile = analyze_synth_patch(
            device_name="Meld",
            track_index=3,
            device_index=0,
            parameter_state={"Engine 1 Algorithm": 2},
        )
        low = propose_synth_branches(profile, kernel={"freshness": 0.2})
        high = propose_synth_branches(profile, kernel={"freshness": 0.9})
        low_target = low[0][1]["steps"][0]["params"]["value"]
        high_target = high[0][1]["steps"][0]["params"]["value"]
        assert abs(high_target - 2) > abs(low_target - 2)


# ── extract_timbre_fingerprint ──────────────────────────────────────────


class TestExtractTimbreFingerprint:

    def test_empty_inputs_returns_neutral(self):
        fp = extract_timbre_fingerprint()
        assert fp.brightness == 0.0
        assert fp.warmth == 0.0

    def test_bright_spectrum_high_brightness(self):
        spectrum = {
            "sub": 0.1, "low": 0.2, "low_mid": 0.2,
            "mid": 0.4, "high_mid": 0.8, "high": 0.9,
            "very_high": 0.6, "ultra": 0.3,
        }
        fp = extract_timbre_fingerprint(spectrum=spectrum)
        assert fp.brightness > 0.0

    def test_dark_spectrum_negative_brightness(self):
        spectrum = {
            "sub": 0.9, "low": 0.8, "low_mid": 0.7,
            "mid": 0.3, "high_mid": 0.1, "high": 0.05,
            "very_high": 0.02, "ultra": 0.0,
        }
        fp = extract_timbre_fingerprint(spectrum=spectrum)
        assert fp.brightness < 0.0

    def test_spectral_centroid_preferred_when_present(self):
        # When centroid is in spectral_shape, it overrides band heuristic.
        spectrum = {"sub": 0.9, "low": 0.9, "low_mid": 0.8, "mid": 0.2}  # dark bands
        fp = extract_timbre_fingerprint(
            spectrum=spectrum,
            spectral_shape={"centroid": 4500},  # high centroid — bright
        )
        assert fp.brightness > 0.0  # centroid wins

    def test_warmth_from_low_mid(self):
        spectrum = {"sub": 0.1, "low": 0.1, "low_mid": 0.9, "mid": 0.3,
                    "high_mid": 0.1, "high": 0.05}
        fp = extract_timbre_fingerprint(spectrum=spectrum)
        assert fp.warmth > 0.0

    def test_flatness_drives_texture_density(self):
        fp_smooth = extract_timbre_fingerprint(
            spectral_shape={"flatness": 0.1}
        )
        fp_noisy = extract_timbre_fingerprint(
            spectral_shape={"flatness": 0.9}
        )
        assert fp_noisy.texture_density > fp_smooth.texture_density
        assert fp_noisy.instability > fp_smooth.instability

    def test_width_always_zero_in_pr10(self):
        # PR10 is single-channel; stereo detection lands later.
        fp = extract_timbre_fingerprint(
            spectrum={"mid": 0.5}, loudness={"rms": 0.3, "peak": 0.8}
        )
        assert fp.width == 0.0

    def test_values_clamped_to_unit_range(self):
        spectrum = {k: 99.0 for k in ("sub", "low", "low_mid", "mid",
                                      "high_mid", "high", "very_high", "ultra")}
        fp = extract_timbre_fingerprint(spectrum=spectrum)
        for value in (fp.brightness, fp.warmth, fp.bite, fp.softness,
                      fp.instability, fp.texture_density, fp.polish):
            assert -1.0 <= value <= 1.0


# ── diff_fingerprint ────────────────────────────────────────────────────


class TestDiffFingerprint:

    def test_zero_diff_for_equal_fingerprints(self):
        a = TimbralFingerprint(brightness=0.5, warmth=0.3)
        b = TimbralFingerprint(brightness=0.5, warmth=0.3)
        d = diff_fingerprint(a, b)
        assert d["brightness"] == 0.0
        assert d["warmth"] == 0.0

    def test_positive_diff_when_b_brighter(self):
        a = TimbralFingerprint(brightness=-0.3)
        b = TimbralFingerprint(brightness=0.4)
        d = diff_fingerprint(a, b)
        assert d["brightness"] == 0.7

    def test_all_dimensions_surfaced(self):
        a = TimbralFingerprint()
        b = TimbralFingerprint()
        d = diff_fingerprint(a, b)
        for dim in ("brightness", "warmth", "bite", "softness", "instability",
                    "width", "texture_density", "movement", "polish"):
            assert dim in d
