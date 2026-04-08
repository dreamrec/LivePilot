"""Tests for snapshot normalizer — canonical input normalization."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._snapshot_normalizer import normalize_sonic_snapshot


class TestNormalizeSonicSnapshot:
    def test_accepts_bands_key(self):
        raw = {"bands": {"sub": 0.1, "low": 0.2}, "rms": 0.5, "peak": 0.8}
        result = normalize_sonic_snapshot(raw)
        assert result["spectrum"]["sub"] == 0.1
        assert result["rms"] == 0.5

    def test_accepts_spectrum_key(self):
        raw = {"spectrum": {"sub": 0.1}, "rms": 0.5, "peak": 0.8}
        result = normalize_sonic_snapshot(raw)
        assert result["spectrum"]["sub"] == 0.1

    def test_none_input(self):
        result = normalize_sonic_snapshot(None)
        assert result is None

    def test_empty_input(self):
        result = normalize_sonic_snapshot({})
        assert result is None

    def test_empty_bands(self):
        result = normalize_sonic_snapshot({"bands": {}, "rms": 0.5})
        assert result is None

    def test_adds_source_metadata(self):
        raw = {"bands": {"sub": 0.1}, "rms": 0.5, "peak": 0.8}
        result = normalize_sonic_snapshot(raw, source="analyzer")
        assert result["source"] == "analyzer"

    def test_preserves_key_detection(self):
        raw = {"bands": {"sub": 0.1}, "rms": 0.5, "peak": 0.8, "key": "Cm"}
        result = normalize_sonic_snapshot(raw)
        assert result["detected_key"] == "Cm"

    def test_detected_key_alias(self):
        raw = {"bands": {"sub": 0.1}, "rms": 0.5, "peak": 0.8, "detected_key": "G"}
        result = normalize_sonic_snapshot(raw)
        assert result["detected_key"] == "G"

    def test_has_normalized_at_timestamp(self):
        raw = {"bands": {"sub": 0.1}, "rms": 0.5, "peak": 0.8}
        result = normalize_sonic_snapshot(raw)
        assert "normalized_at_ms" in result
        assert isinstance(result["normalized_at_ms"], int)

    def test_default_source_is_unknown(self):
        raw = {"bands": {"sub": 0.1}, "rms": 0.5, "peak": 0.8}
        result = normalize_sonic_snapshot(raw)
        assert result["source"] == "unknown"
