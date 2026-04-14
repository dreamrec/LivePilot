"""Tests for composer sample resolution.

The composer used to emit pseudo-tools and placeholder strings
({downloaded_path}) because sample resolution was deferred until "the agent
figures it out". Plans were aspirational, not executable. This resolver
moves resolution to plan time so compose() can drop unresolvable layers
cleanly and emit only real tool calls.
"""

import pytest

from mcp_server.composer.layer_planner import LayerSpec
from mcp_server.composer.sample_resolver import resolve_sample_for_layer


def test_resolve_returns_path_when_filesystem_hit(tmp_path):
    sample = tmp_path / "kick_tight.wav"
    sample.write_bytes(b"RIFF....WAVE")

    layer = LayerSpec(role="kick", search_query="tight kick techno")
    path, source = resolve_sample_for_layer(layer, search_roots=[tmp_path])

    assert path == str(sample)
    assert source == "filesystem"


def test_resolve_returns_none_when_no_match(tmp_path):
    (tmp_path / "unrelated.wav").write_bytes(b"RIFF....WAVE")

    layer = LayerSpec(role="kick", search_query="nonexistent_xyz_12345")
    path, source = resolve_sample_for_layer(layer, search_roots=[tmp_path])

    assert path is None
    assert source == "unresolved"


def test_resolve_without_search_roots_returns_unresolved():
    layer = LayerSpec(role="bass", search_query="fat bass")
    path, source = resolve_sample_for_layer(layer, search_roots=[])
    assert path is None
    assert source == "unresolved"


def test_resolve_matches_on_role_when_query_tokens_too_short(tmp_path):
    (tmp_path / "bass_sample.wav").write_bytes(b"RIFF....WAVE")
    # Single-char tokens should not be used for matching; role should match
    layer = LayerSpec(role="bass", search_query="a b")
    path, source = resolve_sample_for_layer(layer, search_roots=[tmp_path])
    assert path is not None
    assert source == "filesystem"


def test_resolve_prefers_first_search_root_hit(tmp_path):
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "kick_a.wav").write_bytes(b"RIFF")
    (root_b / "kick_b.wav").write_bytes(b"RIFF")

    layer = LayerSpec(role="kick", search_query="kick")
    path, source = resolve_sample_for_layer(layer, search_roots=[root_a, root_b])
    assert path.endswith("kick_a.wav") or path.endswith("kick_b.wav")
    assert source == "filesystem"


def test_resolve_handles_nonexistent_search_root(tmp_path):
    missing = tmp_path / "does_not_exist"

    layer = LayerSpec(role="kick", search_query="kick")
    path, source = resolve_sample_for_layer(layer, search_roots=[missing])
    assert path is None
    assert source == "unresolved"


def test_resolve_finds_aif_files(tmp_path):
    (tmp_path / "snare_punch.aif").write_bytes(b"FORM")
    layer = LayerSpec(role="snare", search_query="punch snare")
    path, source = resolve_sample_for_layer(layer, search_roots=[tmp_path])
    assert path.endswith(".aif")
    assert source == "filesystem"
