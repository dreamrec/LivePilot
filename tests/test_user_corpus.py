"""Tests for the user-corpus builder.

Covers the Scanner ABC contract, manifest IO, and runner orchestration.
End-to-end smoke tests against real .als/.adg files are in a separate file
so they can be skipped in CI without filesystem access.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from mcp_server.user_corpus import (
    Manifest,
    Source,
    Scanner,
    register_scanner,
    get_scanner,
    list_scanners,
    load_manifest,
    save_manifest,
    init_default_manifest,
    run_scan,
)


# ─── Scanner registry ────────────────────────────────────────────────────────


def test_built_in_scanners_registered():
    """The 4 built-in scanners must be present after package import."""
    types = list_scanners()
    for expected in ("als", "adg", "amxd", "plugin-preset"):
        assert expected in types, f"Built-in scanner '{expected}' not registered"


def test_scanner_registry_via_decorator(tmp_path):
    """Custom scanners self-register through the @register_scanner decorator."""
    @register_scanner
    class FakeScanner(Scanner):
        type_id = "test-fake-format"
        file_extensions = [".fake"]
        output_subdir = "fake"

        def scan_one(self, path):
            return {"data": "ok"}

        def derive_tags(self, sidecar):
            return ["fake"]

        def derive_description(self, sidecar):
            return "fake description"

    assert "test-fake-format" in list_scanners()
    inst = get_scanner("test-fake-format")
    assert inst.type_id == "test-fake-format"


def test_get_scanner_unknown_raises():
    with pytest.raises(KeyError):
        get_scanner("does-not-exist-xyz")


# ─── Manifest IO ─────────────────────────────────────────────────────────────


def test_manifest_round_trip(tmp_path):
    path = tmp_path / "manifest.yaml"
    m = Manifest(sources=[
        Source(id="x", type="als", path="~/Music/X"),
        Source(id="y", type="adg", path="~/Music/Y", recursive=False),
    ])
    save_manifest(m, path)
    loaded = load_manifest(path)
    assert len(loaded.sources) == 2
    assert loaded.sources[0].id == "x"
    assert loaded.sources[1].recursive is False


def test_load_manifest_missing_returns_default():
    m = load_manifest(Path("/tmp/definitely-does-not-exist-xyz/manifest.yaml"))
    assert isinstance(m, Manifest)
    assert m.sources == []


def test_init_default_manifest_creates_file(tmp_path):
    path = tmp_path / "subdir" / "manifest.yaml"
    init_default_manifest(path)
    assert path.exists()
    loaded = load_manifest(path)
    assert loaded.schema_version == 1


def test_add_source_rejects_duplicate(tmp_path):
    m = Manifest(sources=[Source(id="x", type="als", path="/tmp/x")])
    with pytest.raises(ValueError):
        m.add_source(Source(id="x", type="adg", path="/tmp/y"))


def test_remove_source_returns_match(tmp_path):
    src = Source(id="x", type="als", path="/tmp/x")
    m = Manifest(sources=[src])
    out = m.remove_source("x")
    assert out is src
    assert m.sources == []


# ─── Runner against synthetic scanner ────────────────────────────────────────


def test_runner_writes_sidecar_and_wrapper(tmp_path):
    """End-to-end: synthetic scanner over a file produces both artifacts."""

    @register_scanner
    class TxtScanner(Scanner):
        type_id = "test-txt"
        file_extensions = [".txt"]
        output_subdir = "txt_files"

        def scan_one(self, path):
            return {"name": path.stem, "content_length": len(path.read_text())}

        def derive_tags(self, sidecar):
            return [f"len-{sidecar.get('content_length', 0)}"]

        def derive_description(self, sidecar):
            return f"txt file '{sidecar.get('name')}' ({sidecar.get('content_length')} chars)"

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "hello.txt").write_text("hello world!")

    out_root = tmp_path / "out"
    manifest = Manifest(
        sources=[Source(id="my-txt", type="test-txt", path=str(src_dir))],
        output={"root": str(out_root), "schema_version": 1},
        options={"skip_unchanged": True},
    )
    result = run_scan(manifest)

    assert len(result.sources) == 1
    assert result.sources[0].files_scanned == 1
    assert result.sources[0].files_errored == 0

    sidecar_path = out_root / "txt_files" / "_parses" / "my-txt__hello.json"
    wrapper_path = out_root / "txt_files" / "my-txt__hello.yaml"
    assert sidecar_path.exists()
    assert wrapper_path.exists()

    sidecar = json.loads(sidecar_path.read_text())
    assert sidecar["scanner"] == "test-txt"
    assert sidecar["data"]["content_length"] == 12
    assert "source_mtime" in sidecar
    assert "source_sha256" in sidecar

    wrapper = yaml.safe_load(wrapper_path.read_text())
    assert wrapper["entity_id"] == "my-txt__hello"
    assert wrapper["namespace"] == "user.my-txt"
    assert "scanner:test-txt" in wrapper["tags"]
    assert "len-12" in wrapper["tags"]


def test_runner_skips_unchanged(tmp_path):
    """Second scan over the same file should skip when mtime matches."""

    @register_scanner
    class TxtScanner2(Scanner):
        type_id = "test-txt2"
        file_extensions = [".txt"]
        output_subdir = "txt2"

        def scan_one(self, path):
            return {"data": 1}

        def derive_tags(self, sidecar):
            return []

        def derive_description(self, sidecar):
            return ""

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "x.txt").write_text("content")
    out_root = tmp_path / "out"
    manifest = Manifest(
        sources=[Source(id="t", type="test-txt2", path=str(src_dir))],
        output={"root": str(out_root)},
    )
    r1 = run_scan(manifest)
    assert r1.sources[0].files_scanned == 1
    assert r1.sources[0].files_skipped == 0

    r2 = run_scan(manifest)
    assert r2.sources[0].files_scanned == 0
    assert r2.sources[0].files_skipped == 1


def test_runner_filters_by_source_id(tmp_path):
    @register_scanner
    class TxtScanner3(Scanner):
        type_id = "test-txt3"
        file_extensions = [".txt"]
        output_subdir = "txt3"

        def scan_one(self, path):
            return {"data": 1}

        def derive_tags(self, sidecar):
            return []

        def derive_description(self, sidecar):
            return ""

    src1 = tmp_path / "s1"
    src2 = tmp_path / "s2"
    src1.mkdir()
    src2.mkdir()
    (src1 / "a.txt").write_text("a")
    (src2 / "b.txt").write_text("b")
    manifest = Manifest(
        sources=[
            Source(id="s1", type="test-txt3", path=str(src1)),
            Source(id="s2", type="test-txt3", path=str(src2)),
        ],
        output={"root": str(tmp_path / "out")},
    )
    r = run_scan(manifest, only_source_id="s2")
    assert len(r.sources) == 1
    assert r.sources[0].source_id == "s2"


def test_runner_per_file_error_does_not_abort(tmp_path):
    """One failing file should not stop the rest of the scan."""

    @register_scanner
    class FailingScanner(Scanner):
        type_id = "test-failing"
        file_extensions = [".fail"]
        output_subdir = "failing"

        def scan_one(self, path):
            if "boom" in path.name:
                raise RuntimeError("synthetic failure")
            return {"data": "ok"}

        def derive_tags(self, sidecar):
            return []

        def derive_description(self, sidecar):
            return ""

    src = tmp_path / "src"
    src.mkdir()
    (src / "good.fail").write_text("x")
    (src / "boom.fail").write_text("x")
    (src / "another-good.fail").write_text("x")

    manifest = Manifest(
        sources=[Source(id="t", type="test-failing", path=str(src))],
        output={"root": str(tmp_path / "out")},
    )
    r = run_scan(manifest)
    assert r.sources[0].files_scanned == 2
    assert r.sources[0].files_errored == 1
    assert "boom" in r.sources[0].errors[0][0]


# ─── Schema invariants ───────────────────────────────────────────────────────


def test_sidecar_carries_provenance_metadata(tmp_path):
    @register_scanner
    class TxtScanner4(Scanner):
        type_id = "test-txt4"
        file_extensions = [".txt"]
        output_subdir = "txt4"

        def scan_one(self, path):
            return {"data": 42}

        def derive_tags(self, sidecar):
            return []

        def derive_description(self, sidecar):
            return ""

    src = tmp_path / "src"
    src.mkdir()
    (src / "test.txt").write_text("hello")
    manifest = Manifest(
        sources=[Source(id="t", type="test-txt4", path=str(src))],
        output={"root": str(tmp_path / "out")},
    )
    run_scan(manifest)
    sidecar_path = tmp_path / "out" / "txt4" / "_parses" / "t__test.json"
    sidecar = json.loads(sidecar_path.read_text())
    # Required provenance fields
    for key in ("schema_version", "scanner", "source_id", "source_path",
                "source_mtime", "source_sha256", "scan_timestamp", "data"):
        assert key in sidecar, f"missing provenance key: {key}"
    assert sidecar["source_id"] == "t"
    assert sidecar["scanner"] == "test-txt4"
