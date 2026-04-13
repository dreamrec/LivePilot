"""Tests for sample sources — BrowserSource, SpliceSource, FilesystemSource."""

from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

from mcp_server.sample_engine.sources import (
    BrowserSource,
    SpliceSource,
    FilesystemSource,
    build_search_queries,
)
from mcp_server.sample_engine.models import SampleCandidate


# ═══════════════════════════════════════════════════════════════════════
# BrowserSource
# ═══════════════════════════════════════════════════════════════════════


class TestBrowserSource:
    def test_build_search_params(self):
        b = BrowserSource()
        params = b.build_search_params("vocal", "samples", 10)
        assert params == {
            "path": "samples",
            "name_filter": "vocal",
            "loadable_only": True,
            "max_results": 10,
        }

    def test_build_all_search_params(self):
        b = BrowserSource()
        all_params = b.build_all_search_params("kick")
        assert len(all_params) == len(b.DEFAULT_CATEGORIES)
        assert all(p["name_filter"] == "kick" for p in all_params)

    def test_build_all_custom_categories(self):
        b = BrowserSource()
        params = b.build_all_search_params("pad", categories=["samples", "packs"])
        assert len(params) == 2

    def test_parse_results(self):
        b = BrowserSource()
        raw = [
            {"name": "Dark_Vocal_Cm.wav", "uri": "file:///a/b.wav"},
            {"name": "Kick_Hard.wav", "uri": "file:///c/d.wav"},
        ]
        candidates = b.parse_results(raw, "samples")
        assert len(candidates) == 2
        assert candidates[0].source == "browser"
        assert candidates[0].name == "Dark_Vocal_Cm"
        assert candidates[0].metadata["material_type"] == "vocal"
        assert isinstance(candidates[0], SampleCandidate)

    def test_parse_empty_results(self):
        b = BrowserSource()
        assert b.parse_results([]) == []

    def test_default_categories_includes_packs(self):
        b = BrowserSource()
        assert "packs" in b.DEFAULT_CATEGORIES


# ═══════════════════════════════════════════════════════════════════════
# SpliceSource
# ═══════════════════════════════════════════════════════════════════════


def _create_splice_db(path: str, rows: list[dict]) -> str:
    """Create a test Splice sounds.db with sample rows."""
    db_path = os.path.join(path, "sounds.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE samples (
            id INTEGER PRIMARY KEY,
            local_path TEXT,
            attr_hash TEXT,
            dir TEXT,
            audio_key TEXT,
            bpm REAL,
            chord_type TEXT,
            duration REAL,
            file_hash TEXT,
            sas_id TEXT,
            filename TEXT,
            genre TEXT,
            pack_uuid TEXT,
            sample_type TEXT,
            tags TEXT,
            popularity REAL,
            purchased_at TEXT,
            last_modified_at TEXT,
            waveform_url TEXT,
            provider_name TEXT
        )
    """)
    for row in rows:
        conn.execute(
            """INSERT INTO samples (id, local_path, audio_key, bpm, tags,
               sample_type, genre, filename, provider_name, pack_uuid,
               duration, popularity)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row.get("id", 1),
                row.get("local_path"),
                row.get("audio_key"),
                row.get("bpm"),
                row.get("tags", ""),
                row.get("sample_type", "oneshot"),
                row.get("genre", ""),
                row.get("filename", "test.wav"),
                row.get("provider_name", "Test Pack"),
                row.get("pack_uuid", "abc-123"),
                row.get("duration", 2.0),
                row.get("popularity", 50),
            ),
        )
    conn.commit()
    conn.close()
    return db_path


class TestSpliceSource:
    def test_disabled_when_no_db(self):
        s = SpliceSource(db_path="/nonexistent/sounds.db")
        assert s.enabled is False
        assert s.search("kick") == []

    def test_search_finds_downloaded_samples(self, tmp_path):
        db = _create_splice_db(str(tmp_path), [
            {"id": 1, "local_path": "/tmp/kick.wav", "filename": "kick.wav",
             "tags": "kicks drums hard", "sample_type": "oneshot", "bpm": 128},
            {"id": 2, "local_path": "/tmp/vocal.wav", "filename": "vocal_Cm.wav",
             "tags": "vocal female dark", "sample_type": "loop", "audio_key": "Cm", "bpm": 120},
            {"id": 3, "local_path": None, "filename": "not_downloaded.wav",
             "tags": "synth", "sample_type": "loop"},
        ])
        s = SpliceSource(db_path=db)
        assert s.enabled is True

        results = s.search("kick")
        assert len(results) == 1
        assert results[0].name == "kick.wav"
        assert results[0].source == "splice"
        assert results[0].file_path == "/tmp/kick.wav"

    def test_search_excludes_not_downloaded(self, tmp_path):
        db = _create_splice_db(str(tmp_path), [
            {"id": 1, "local_path": None, "filename": "cloud_only.wav",
             "tags": "synth", "sample_type": "loop"},
        ])
        s = SpliceSource(db_path=db)
        assert s.search("synth") == []

    def test_search_by_key(self, tmp_path):
        db = _create_splice_db(str(tmp_path), [
            {"id": 1, "local_path": "/a.wav", "filename": "pad_Cm.wav",
             "tags": "pad ambient", "audio_key": "Cm", "sample_type": "loop"},
            {"id": 2, "local_path": "/b.wav", "filename": "pad_Am.wav",
             "tags": "pad ambient", "audio_key": "Am", "sample_type": "loop"},
        ])
        s = SpliceSource(db_path=db)
        results = s.search("", key="Cm")
        assert len(results) == 1
        assert results[0].metadata["key"] == "Cm"

    def test_search_by_bpm_range(self, tmp_path):
        db = _create_splice_db(str(tmp_path), [
            {"id": 1, "local_path": "/a.wav", "filename": "break_fast.wav",
             "tags": "drums", "bpm": 170, "sample_type": "loop"},
            {"id": 2, "local_path": "/b.wav", "filename": "break_slow.wav",
             "tags": "drums", "bpm": 90, "sample_type": "loop"},
        ])
        s = SpliceSource(db_path=db)
        results = s.search("", bpm_min=160, bpm_max=180)
        assert len(results) == 1
        assert results[0].metadata["bpm"] == 170

    def test_rich_metadata(self, tmp_path):
        db = _create_splice_db(str(tmp_path), [
            {"id": 42, "local_path": "/samples/lead.wav", "filename": "lead.wav",
             "tags": "synth lead bright", "audio_key": "F#", "bpm": 128,
             "genre": "House", "sample_type": "loop", "provider_name": "KSHMR",
             "pack_uuid": "xyz-789", "duration": 4.0, "popularity": 95},
        ])
        s = SpliceSource(db_path=db)
        results = s.search("lead")
        assert len(results) == 1
        m = results[0].metadata
        assert m["key"] == "F#"
        assert m["bpm"] == 128
        assert m["genre"] == "House"
        assert m["pack"] == "KSHMR"
        assert m["duration"] == 4.0
        assert m["material_type"] == "instrument_loop"

    def test_material_type_classification(self, tmp_path):
        db = _create_splice_db(str(tmp_path), [
            {"id": 1, "local_path": "/a.wav", "filename": "a.wav",
             "tags": "vocal female", "sample_type": "loop"},
            {"id": 2, "local_path": "/b.wav", "filename": "b.wav",
             "tags": "kicks drums", "sample_type": "oneshot"},
            {"id": 3, "local_path": "/c.wav", "filename": "c.wav",
             "tags": "ambient pad texture", "sample_type": "loop"},
        ])
        s = SpliceSource(db_path=db)
        all_results = s.search("")
        types = {r.name: r.metadata["material_type"] for r in all_results}
        assert types["a.wav"] == "vocal"
        assert types["b.wav"] == "one_shot"
        assert types["c.wav"] == "texture"

    def test_get_sample_count(self, tmp_path):
        db = _create_splice_db(str(tmp_path), [
            {"id": 1, "local_path": "/a.wav", "filename": "a.wav", "tags": ""},
            {"id": 2, "local_path": "/b.wav", "filename": "b.wav", "tags": ""},
            {"id": 3, "local_path": None, "filename": "c.wav", "tags": ""},
        ])
        s = SpliceSource(db_path=db)
        assert s.get_sample_count() == 2

    def test_get_available_keys(self, tmp_path):
        db = _create_splice_db(str(tmp_path), [
            {"id": 1, "local_path": "/a.wav", "filename": "a.wav",
             "audio_key": "Cm", "tags": ""},
            {"id": 2, "local_path": "/b.wav", "filename": "b.wav",
             "audio_key": "Am", "tags": ""},
            {"id": 3, "local_path": "/c.wav", "filename": "c.wav",
             "audio_key": "Cm", "tags": ""},
        ])
        s = SpliceSource(db_path=db)
        keys = s.get_available_keys()
        assert "Am" in keys
        assert "Cm" in keys

    def test_search_by_key_and_tempo(self, tmp_path):
        db = _create_splice_db(str(tmp_path), [
            {"id": 1, "local_path": "/a.wav", "filename": "a.wav",
             "audio_key": "Cm", "bpm": 128, "tags": "synth"},
            {"id": 2, "local_path": "/b.wav", "filename": "b.wav",
             "audio_key": "Cm", "bpm": 80, "tags": "synth"},
            {"id": 3, "local_path": "/c.wav", "filename": "c.wav",
             "audio_key": "Am", "bpm": 128, "tags": "synth"},
        ])
        s = SpliceSource(db_path=db)
        results = s.search_by_key_and_tempo("Cm", 128.0, tolerance_bpm=5)
        assert len(results) == 1
        assert results[0].metadata["key"] == "Cm"
        assert results[0].metadata["bpm"] == 128

    def test_readonly_access(self, tmp_path):
        db = _create_splice_db(str(tmp_path), [
            {"id": 1, "local_path": "/a.wav", "filename": "a.wav", "tags": ""},
        ])
        s = SpliceSource(db_path=db)
        assert len(s.search("")) == 1
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM samples")
        conn.close()

    def test_search_by_genre(self, tmp_path):
        db = _create_splice_db(str(tmp_path), [
            {"id": 1, "local_path": "/a.wav", "filename": "a.wav",
             "tags": "drums", "genre": "House"},
            {"id": 2, "local_path": "/b.wav", "filename": "b.wav",
             "tags": "drums", "genre": "Trap"},
        ])
        s = SpliceSource(db_path=db)
        results = s.search("", genre="house")
        assert len(results) == 1

    def test_get_available_genres(self, tmp_path):
        db = _create_splice_db(str(tmp_path), [
            {"id": 1, "local_path": "/a.wav", "filename": "a.wav",
             "tags": "", "genre": "House"},
            {"id": 2, "local_path": "/b.wav", "filename": "b.wav",
             "tags": "", "genre": "Trap"},
        ])
        s = SpliceSource(db_path=db)
        genres = s.get_available_genres()
        assert "House" in genres
        assert "Trap" in genres


# ═══════════════════════════════════════════════════════════════════════
# FilesystemSource
# ═══════════════════════════════════════════════════════════════════════


class TestFilesystemSource:
    def test_scan_finds_audio_files(self, tmp_path):
        (tmp_path / "kick.wav").write_bytes(b"fake")
        (tmp_path / "vocal_Cm_120bpm.aif").write_bytes(b"fake")
        (tmp_path / "readme.txt").write_bytes(b"not audio")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "pad.mp3").write_bytes(b"fake")

        source = FilesystemSource(scan_paths=[str(tmp_path)], max_depth=3)
        results = source.scan()
        names = {r.name for r in results}
        assert "kick" in names
        assert "vocal_Cm_120bpm" in names
        assert "pad" in names
        assert "readme" not in names

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
        assert len(source.scan()) == 0

    def test_scan_respects_max_depth(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (deep / "deep.wav").write_bytes(b"fake")
        source = FilesystemSource(scan_paths=[str(tmp_path)], max_depth=2)
        assert len(source.scan()) == 0

    def test_all_audio_extensions(self, tmp_path):
        for ext in [".wav", ".aif", ".aiff", ".mp3", ".flac", ".ogg"]:
            (tmp_path / f"test{ext}").write_bytes(b"fake")
        source = FilesystemSource(scan_paths=[str(tmp_path)])
        assert len(source.scan()) == 6


# ═══════════════════════════════════════════════════════════════════════
# Search Query Builder
# ═══════════════════════════════════════════════════════════════════════


class TestBuildSearchQueries:
    def test_basic_query(self):
        queries = build_search_queries("dark vocal", material_type="vocal")
        assert any("vocal" in q.lower() for q in queries)

    def test_contextual_from_song_state(self):
        queries = build_search_queries(
            "something organic",
            song_context={"key": "Cm", "tempo": 128},
        )
        assert len(queries) >= 1

    def test_bare_query_returns_original(self):
        queries = build_search_queries("test")
        assert queries[0] == "test"

    def test_capped_at_five(self):
        queries = build_search_queries("x", material_type="vocal")
        assert len(queries) <= 5

    def test_song_context_key_appended(self):
        queries = build_search_queries("pad", song_context={"key": "Gm"})
        assert any("Gm" in q for q in queries)

    def test_instrument_loop_synonyms(self):
        queries = build_search_queries("warm", material_type="instrument_loop")
        assert any("synth" in q.lower() or "keys" in q.lower() for q in queries)
