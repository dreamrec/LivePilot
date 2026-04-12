"""Tests for sample sources — unit tests with mocked I/O."""

from __future__ import annotations

import os
import json
import tempfile

import pytest

from mcp_server.sample_engine.sources import (
    BrowserSource,
    FilesystemSource,
    FreesoundSource,
    build_search_queries,
    parse_freesound_metadata,
)
from mcp_server.sample_engine.models import SampleCandidate


class TestFilesystemSource:
    def test_scan_finds_audio_files(self, tmp_path):
        # Create test audio files
        (tmp_path / "kick.wav").write_bytes(b"fake")
        (tmp_path / "vocal_Cm_120bpm.aif").write_bytes(b"fake")
        (tmp_path / "readme.txt").write_bytes(b"not audio")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "pad.mp3").write_bytes(b"fake")

        source = FilesystemSource(scan_paths=[str(tmp_path)], max_depth=3)
        results = source.scan()
        audio_names = {r.name for r in results}
        assert "kick" in audio_names
        assert "vocal_Cm_120bpm" in audio_names
        assert "pad" in audio_names
        assert "readme" not in audio_names

    def test_search_filters_by_query(self, tmp_path):
        (tmp_path / "dark_vocal_Cm.wav").write_bytes(b"fake")
        (tmp_path / "bright_pad.wav").write_bytes(b"fake")

        source = FilesystemSource(scan_paths=[str(tmp_path)])
        results = source.search("vocal")
        names = [r.name for r in results]
        assert "dark_vocal_Cm" in names
        assert "bright_pad" not in names

    def test_metadata_extracted(self, tmp_path):
        (tmp_path / "synth_Am_128bpm.wav").write_bytes(b"fake")
        source = FilesystemSource(scan_paths=[str(tmp_path)])
        results = source.scan()
        assert len(results) == 1
        assert results[0].metadata.get("key") == "Am"
        assert results[0].metadata.get("bpm") == 128.0

    def test_scan_skips_hidden_dirs(self, tmp_path):
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "secret.wav").write_bytes(b"fake")
        source = FilesystemSource(scan_paths=[str(tmp_path)])
        results = source.scan()
        assert len(results) == 0

    def test_scan_respects_max_depth(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "deep.wav").write_bytes(b"fake")
        source = FilesystemSource(scan_paths=[str(tmp_path)], max_depth=1)
        results = source.scan()
        assert len(results) == 0

    def test_scan_nonexistent_path(self):
        source = FilesystemSource(scan_paths=["/nonexistent/path/abc123"])
        results = source.scan()
        assert results == []

    def test_all_audio_extensions(self, tmp_path):
        for ext in [".wav", ".aif", ".aiff", ".mp3", ".flac", ".ogg"]:
            (tmp_path / f"sample{ext}").write_bytes(b"fake")
        source = FilesystemSource(scan_paths=[str(tmp_path)])
        results = source.scan()
        assert len(results) == 6


class TestBrowserSource:
    def test_search_returns_candidates_per_category(self):
        source = BrowserSource()
        results = source.search("kick")
        assert len(results) == 3  # default: samples, drums, user_library
        sources = {r.source for r in results}
        assert sources == {"browser"}
        categories = {r.metadata["category"] for r in results}
        assert "samples" in categories
        assert "drums" in categories
        assert "user_library" in categories

    def test_search_custom_categories(self):
        source = BrowserSource()
        results = source.search("pad", categories=["samples"])
        assert len(results) == 1
        assert results[0].metadata["category"] == "samples"
        assert results[0].metadata["query"] == "pad"

    def test_search_name_is_query(self):
        source = BrowserSource()
        results = source.search("dark vocal")
        assert all(r.name == "dark vocal" for r in results)

    def test_build_search_params(self):
        source = BrowserSource()
        params = source.build_search_params("kick", category="drums", max_results=10)
        assert params["path"] == "drums"
        assert params["name_filter"] == "kick"
        assert params["loadable_only"] is True
        assert params["max_results"] == 10

    def test_candidates_are_sample_candidate_instances(self):
        source = BrowserSource()
        results = source.search("snare")
        assert all(isinstance(r, SampleCandidate) for r in results)


class TestBuildSearchQueries:
    def test_basic_query(self):
        queries = build_search_queries("dark vocal", material_type="vocal")
        assert any("vocal" in q.lower() for q in queries)

    def test_contextual_from_song_state(self):
        queries = build_search_queries(
            "something organic",
            song_context={"key": "Cm", "tempo": 128, "missing_roles": ["texture"]}
        )
        assert len(queries) >= 1

    def test_bare_query_returns_at_least_original(self):
        queries = build_search_queries("hello world")
        assert queries[0] == "hello world"

    def test_capped_at_five(self):
        queries = build_search_queries("vocal", material_type="vocal")
        assert len(queries) <= 5

    def test_song_context_key_appended(self):
        queries = build_search_queries("pad", song_context={"key": "Dm"})
        assert any("Dm" in q for q in queries)


class TestFreesoundMetadata:
    def test_parse_ac_descriptors(self):
        raw = {
            "id": 12345,
            "name": "vocal_sample.wav",
            "tags": ["vocal", "female", "clean"],
            "ac_analysis": {
                "ac_key": "Cm",
                "ac_tempo": 120.0,
                "ac_brightness": 0.6,
                "ac_depth": 0.4,
            },
            "license": "Attribution",
            "duration": 4.5,
        }
        candidate = parse_freesound_metadata(raw)
        assert candidate.metadata["key"] == "Cm"
        assert candidate.metadata["bpm"] == 120.0
        assert candidate.freesound_id == 12345

    def test_parse_missing_ac_analysis(self):
        raw = {
            "id": 99,
            "name": "noise.wav",
            "tags": [],
        }
        candidate = parse_freesound_metadata(raw)
        assert candidate.metadata["key"] is None
        assert candidate.metadata["bpm"] is None
        assert candidate.freesound_id == 99
        assert candidate.source == "freesound"

    def test_material_classified_from_tags(self):
        raw = {
            "id": 50,
            "name": "sample.wav",
            "tags": ["drum", "loop", "percussion"],
            "ac_analysis": {},
        }
        candidate = parse_freesound_metadata(raw)
        assert candidate.metadata.get("material_type") == "drum_loop"


class TestFreesoundSource:
    def test_disabled_without_api_key(self):
        source = FreesoundSource(api_key=None)
        # Force disabled by clearing env
        source.enabled = False
        results = source.search("test")
        assert results == []

    def test_build_search_params(self):
        source = FreesoundSource(api_key="fake")
        params = source.build_search_params("vocal pad", max_results=5)
        assert params["query"] == "vocal pad"
        assert params["page_size"] == 5
        assert "id" in params["fields"]
        assert "rating_desc" in params["sort"]
