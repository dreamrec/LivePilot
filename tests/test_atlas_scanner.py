"""Tests for Device Atlas scanner and enrichment loader — pure data, no I/O."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.atlas.scanner import make_device_id, normalize_scan_results
from mcp_server.atlas.enrichments import load_enrichments, merge_enrichments


# ── make_device_id ───────────────────────────────────────────────────────────

class TestMakeDeviceId:
    def test_simple_name(self):
        assert make_device_id("Compressor") == "compressor"

    def test_spaces(self):
        assert make_device_id("EQ Eight") == "eq_eight"

    def test_special_chars(self):
        assert make_device_id("Auto Filter (Legacy)") == "auto_filter_legacy"

    def test_prefix(self):
        assert make_device_id("Model D", prefix="auv3_moog") == "auv3_moog_model_d"

    def test_prefix_with_spaces(self):
        assert make_device_id("Juno 106", prefix="AU Roland") == "au_roland_juno_106"

    def test_trailing_special(self):
        assert make_device_id("--Hello World--") == "hello_world"

    def test_empty_name(self):
        assert make_device_id("") == ""

    def test_numbers_preserved(self):
        assert make_device_id("EQ Three") == "eq_three"


# ── normalize_scan_results ───────────────────────────────────────────────────

class TestNormalizeScanResults:
    def _make_raw(self, categories: dict) -> dict:
        return {"categories": categories}

    def test_instruments(self):
        raw = self._make_raw({
            "instruments": [
                {"name": "Analog", "uri": "query:Instruments#Analog", "is_loadable": True},
                {"name": "Wavetable", "uri": "query:Instruments#Wavetable", "is_loadable": True},
            ]
        })
        devices = normalize_scan_results(raw)
        assert len(devices) == 2
        analog = devices[0]
        assert analog["id"] == "analog"
        assert analog["name"] == "Analog"
        assert analog["category"] == "instruments"
        assert analog["subcategory"] == "synths"
        assert analog["source"] == "native"
        assert analog["enriched"] is False
        assert analog["character_tags"] == []
        assert analog["genre_affinity"] == {"primary": [], "secondary": []}
        assert analog["self_contained"] is True

    def test_audio_effects(self):
        raw = self._make_raw({
            "audio_effects": [
                {"name": "Compressor", "uri": "query:AudioFx#Compressor", "is_loadable": True},
                {"name": "EQ Eight", "uri": "query:AudioFx#EQ%20Eight", "is_loadable": True},
            ]
        })
        devices = normalize_scan_results(raw)
        assert len(devices) == 2
        comp = devices[0]
        assert comp["id"] == "compressor"
        assert comp["subcategory"] == "dynamics"
        eq = devices[1]
        assert eq["id"] == "eq_eight"
        assert eq["subcategory"] == "eq"

    def test_deduplication_by_uri(self):
        raw = self._make_raw({
            "instruments": [
                {"name": "Analog", "uri": "query:Instruments#Analog", "is_loadable": True},
            ],
            "sounds": [
                {"name": "Analog", "uri": "query:Instruments#Analog", "is_loadable": True},
            ],
        })
        devices = normalize_scan_results(raw)
        assert len(devices) == 1

    def test_no_uri_no_dedup(self):
        raw = self._make_raw({
            "instruments": [
                {"name": "Custom", "uri": None, "is_loadable": True},
                {"name": "Custom", "uri": None, "is_loadable": True},
            ],
        })
        devices = normalize_scan_results(raw)
        # No URI means no dedup — both entries kept
        assert len(devices) == 2

    def test_empty_categories(self):
        raw = self._make_raw({})
        devices = normalize_scan_results(raw)
        assert devices == []

    def test_category_mapping(self):
        raw = self._make_raw({
            "drums": [
                {"name": "Kit", "uri": "query:Drums#Kit", "is_loadable": True},
            ],
            "max_for_live": [
                {"name": "LFO", "uri": "query:M4L#LFO", "is_loadable": True},
            ],
        })
        devices = normalize_scan_results(raw)
        drum = [d for d in devices if d["name"] == "Kit"][0]
        assert drum["category"] == "drum_kits"
        m4l = [d for d in devices if d["name"] == "LFO"][0]
        assert m4l["category"] == "max_for_live"

    def test_unknown_category_passthrough(self):
        raw = self._make_raw({
            "user_library": [
                {"name": "My Synth", "uri": "query:UserLib#MySynth", "is_loadable": True},
            ],
        })
        devices = normalize_scan_results(raw)
        assert devices[0]["category"] == "user_library"
        assert devices[0]["source"] == "user_library"

    def test_all_fields_present(self):
        raw = self._make_raw({
            "instruments": [
                {"name": "Drift", "uri": "query:I#Drift", "is_loadable": True},
            ]
        })
        device = normalize_scan_results(raw)[0]
        expected_keys = {
            "id", "name", "uri", "category", "subcategory", "source",
            "enriched", "character_tags", "use_cases", "genre_affinity",
            "self_contained", "key_parameters", "pairs_well_with",
            "starter_recipes", "gotchas", "health_flags",
        }
        assert set(device.keys()) == expected_keys


# ── load_enrichments ─────────────────────────────────────────────────────────

class TestLoadEnrichments:
    def test_loads_yaml_files(self, tmp_path):
        yaml = pytest.importorskip("yaml")
        subdir = tmp_path / "instruments"
        subdir.mkdir()
        data = {
            "character_tags": ["warm", "vintage"],
            "use_cases": ["bass", "pad"],
        }
        (subdir / "analog.yaml").write_text(yaml.dump(data), encoding="utf-8")
        result = load_enrichments(tmp_path)
        assert "analog" in result
        assert result["analog"]["character_tags"] == ["warm", "vintage"]

    def test_skips_underscore_files(self, tmp_path):
        yaml = pytest.importorskip("yaml")
        subdir = tmp_path / "instruments"
        subdir.mkdir()
        (subdir / "_template.yaml").write_text(
            yaml.dump({"key": "val"}), encoding="utf-8"
        )
        (subdir / "analog.yaml").write_text(
            yaml.dump({"key": "val2"}), encoding="utf-8"
        )
        result = load_enrichments(tmp_path)
        assert "_template" not in result
        assert "analog" in result

    def test_skips_underscore_dirs(self, tmp_path):
        yaml = pytest.importorskip("yaml")
        hidden = tmp_path / "_templates"
        hidden.mkdir()
        (hidden / "base.yaml").write_text(
            yaml.dump({"key": "val"}), encoding="utf-8"
        )
        result = load_enrichments(tmp_path)
        assert result == {}

    def test_empty_dir(self, tmp_path):
        result = load_enrichments(tmp_path)
        assert result == {}

    def test_nonexistent_dir(self, tmp_path):
        result = load_enrichments(tmp_path / "nope")
        assert result == {}

    def test_yml_extension(self, tmp_path):
        yaml = pytest.importorskip("yaml")
        subdir = tmp_path / "fx"
        subdir.mkdir()
        (subdir / "compressor.yml").write_text(
            yaml.dump({"character_tags": ["punchy"]}), encoding="utf-8"
        )
        result = load_enrichments(tmp_path)
        assert "compressor" in result


# ── merge_enrichments ────────────────────────────────────────────────────────

class TestMergeEnrichments:
    def test_basic_merge(self):
        devices = [
            {
                "id": "analog",
                "name": "Analog",
                "enriched": False,
                "character_tags": [],
                "use_cases": [],
                "genre_affinity": {"primary": [], "secondary": []},
                "self_contained": True,
                "key_parameters": [],
                "pairs_well_with": [],
                "starter_recipes": [],
                "gotchas": [],
                "health_flags": [],
            }
        ]
        enrichments = {
            "analog": {
                "character_tags": ["warm", "fat"],
                "use_cases": ["bass", "pad"],
                "gotchas": ["CPU-heavy with unison"],
            }
        }
        merge_enrichments(devices, enrichments)
        assert devices[0]["enriched"] is True
        assert devices[0]["character_tags"] == ["warm", "fat"]
        assert devices[0]["use_cases"] == ["bass", "pad"]
        assert devices[0]["gotchas"] == ["CPU-heavy with unison"]
        # Unmodified fields stay at defaults
        assert devices[0]["key_parameters"] == []

    def test_no_matching_enrichment(self):
        devices = [{"id": "wavetable", "enriched": False, "character_tags": []}]
        enrichments = {"analog": {"character_tags": ["warm"]}}
        merge_enrichments(devices, enrichments)
        assert devices[0]["enriched"] is False
        assert devices[0]["character_tags"] == []

    def test_ignores_unknown_fields(self):
        devices = [
            {
                "id": "analog",
                "enriched": False,
                "character_tags": [],
                "use_cases": [],
            }
        ]
        enrichments = {
            "analog": {
                "character_tags": ["warm"],
                "unknown_field": "should be ignored",
            }
        }
        merge_enrichments(devices, enrichments)
        assert devices[0]["enriched"] is True
        assert devices[0]["character_tags"] == ["warm"]
        assert "unknown_field" not in devices[0]

    def test_empty_enrichments(self):
        devices = [{"id": "analog", "enriched": False}]
        merge_enrichments(devices, {})
        assert devices[0]["enriched"] is False
