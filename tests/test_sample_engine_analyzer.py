"""Tests for SampleAnalyzer — pure computation, no I/O."""

from __future__ import annotations

import pytest

from mcp_server.sample_engine.analyzer import (
    parse_filename_metadata,
    classify_material_from_name,
    suggest_simpler_mode,
    suggest_warp_mode,
)
from mcp_server.sample_engine.models import SampleProfile


class TestFilenameParser:
    def test_key_bpm_pattern(self):
        result = parse_filename_metadata("vocal_Cm_120bpm.wav")
        assert result["key"] == "Cm"
        assert result["bpm"] == 120.0

    def test_bpm_key_pattern(self):
        result = parse_filename_metadata("120_Am_guitar.aif")
        assert result["bpm"] == 120.0
        assert result["key"] == "Am"

    def test_bpm_only(self):
        result = parse_filename_metadata("DUSTY_BREAK_95.wav")
        assert result["bpm"] == 95.0
        assert result["key"] is None

    def test_key_only(self):
        result = parse_filename_metadata("pad_Fsharp.wav")
        assert result["key"] == "F#"

    def test_no_metadata(self):
        result = parse_filename_metadata("untitled_003.wav")
        assert result["key"] is None
        assert result["bpm"] is None

    def test_sharp_flat_keys(self):
        result = parse_filename_metadata("synth_Bb_90bpm.wav")
        assert result["key"] == "Bb"

    def test_minor_key(self):
        result = parse_filename_metadata("bass_Ebm_140.wav")
        assert result["key"] == "Ebm"
        assert result["bpm"] == 140.0

    def test_splice_style(self):
        result = parse_filename_metadata("SP_DnB_Reese_Bass_Cm_174_Wet.wav")
        assert result["key"] == "Cm"
        assert result["bpm"] == 174.0


class TestMaterialClassifier:
    def test_vocal_keywords(self):
        assert classify_material_from_name("dark_vocal_loop") == "vocal"
        assert classify_material_from_name("vox_chop_dry") == "vocal"

    def test_drum_keywords(self):
        assert classify_material_from_name("drum_loop_funky") == "drum_loop"
        assert classify_material_from_name("breakbeat_170") == "drum_loop"
        assert classify_material_from_name("hihat_pattern") == "drum_loop"

    def test_one_shot_keywords(self):
        assert classify_material_from_name("kick_hard") == "one_shot"
        assert classify_material_from_name("snare_crack") == "one_shot"
        assert classify_material_from_name("clap_tight") == "one_shot"

    def test_texture_keywords(self):
        assert classify_material_from_name("ambient_pad_drone") == "texture"
        assert classify_material_from_name("noise_texture") == "texture"

    def test_unknown(self):
        assert classify_material_from_name("untitled_003") == "unknown"

    def test_foley(self):
        assert classify_material_from_name("foley_metal_scrape") == "foley"


class TestSimplerModeRecommender:
    def test_one_shot_short_duration(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="unknown", duration_seconds=0.3)
        assert suggest_simpler_mode(p) == "classic"

    def test_drum_loop_slices_by_transient(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="drum_loop", duration_seconds=4.0)
        mode, slice_by = suggest_simpler_mode(p), "transient"
        assert mode == "slice"

    def test_vocal_slices_by_region(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="vocal", duration_seconds=8.0)
        assert suggest_simpler_mode(p) == "slice"

    def test_texture_stays_classic(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="texture", duration_seconds=10.0)
        assert suggest_simpler_mode(p) == "classic"


class TestWarpModeRecommender:
    def test_drum_loop_beats_mode(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="drum_loop")
        assert suggest_warp_mode(p) == "beats"

    def test_vocal_complex_pro(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="vocal")
        assert suggest_warp_mode(p) == "complex_pro"

    def test_texture_texture_mode(self):
        p = SampleProfile(source="t", file_path="/t.wav", name="t",
                          material_type="texture")
        assert suggest_warp_mode(p) == "texture"
