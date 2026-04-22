"""Tests for the Phase B follow-ups after the 2026-04-22 bug batch.

Covers:
  - B5: JSON config file support in SpliceHTTPConfig
  - B6: collection_uuid in generic search_samples
  - B7: verify_all_devices_health tool signature + eligibility logic
  - B8: sub_detail param in get_master_spectrum
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest


# ── B5: JSON config file for HTTPS bridge ──────────────────────────────


def _isolated_env(**overrides):
    """Snapshot relevant env vars, apply overrides, return restore fn."""
    keys = (
        "SPLICE_API_BASE_URL",
        "SPLICE_DESCRIBE_ENDPOINT",
        "SPLICE_VARIATION_ENDPOINT",
        "SPLICE_SEARCH_WITH_SOUND_ENDPOINT",
        "SPLICE_HTTP_TIMEOUT",
        "SPLICE_HTTP_RETRIES",
        "SPLICE_ALLOW_UNVERIFIED_ENDPOINTS",
    )
    snapshot = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    for k, v in overrides.items():
        os.environ[k] = v

    def restore():
        for k in keys:
            os.environ.pop(k, None)
        for k, v in snapshot.items():
            if v is not None:
                os.environ[k] = v
    return restore


def test_b5_config_loaded_from_json_file():
    from mcp_server.splice_client.http_bridge import SpliceHTTPConfig
    restore = _isolated_env()
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "base_url": "https://api.splice.example",
                "describe_endpoint": "/v7/describe",
                "timeout_sec": 45,
            }, f)
            path = f.name
        try:
            cfg = SpliceHTTPConfig.from_env(config_path=path)
            assert cfg.base_url == "https://api.splice.example"
            assert cfg.describe_endpoint == "/v7/describe"
            assert cfg.timeout_sec == 45.0
            assert cfg.is_user_configured
        finally:
            os.unlink(path)
    finally:
        restore()


def test_b5_env_var_overrides_json():
    from mcp_server.splice_client.http_bridge import SpliceHTTPConfig
    restore = _isolated_env(SPLICE_DESCRIBE_ENDPOINT="/from-env")
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"describe_endpoint": "/from-json"}, f)
            path = f.name
        try:
            cfg = SpliceHTTPConfig.from_env(config_path=path)
            # Env must win
            assert cfg.describe_endpoint == "/from-env"
            assert cfg.is_user_configured
        finally:
            os.unlink(path)
    finally:
        restore()


def test_b5_missing_file_silently_uses_defaults():
    from mcp_server.splice_client.http_bridge import SpliceHTTPConfig
    restore = _isolated_env()
    try:
        cfg = SpliceHTTPConfig.from_env(config_path="/nonexistent/splice.json")
        assert cfg.base_url == "https://api.splice.com"  # default preserved
        assert not cfg.is_user_configured
    finally:
        restore()


def test_b5_corrupt_file_falls_back_to_defaults():
    from mcp_server.splice_client.http_bridge import SpliceHTTPConfig
    restore = _isolated_env()
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{not valid json")
            path = f.name
        try:
            cfg = SpliceHTTPConfig.from_env(config_path=path)
            assert cfg.base_url == "https://api.splice.com"
            assert not cfg.is_user_configured
        finally:
            os.unlink(path)
    finally:
        restore()


def test_b5_non_object_json_falls_back():
    """A JSON array/string at the top level is wrong shape — ignore it."""
    from mcp_server.splice_client.http_bridge import SpliceHTTPConfig
    restore = _isolated_env()
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(["not", "an", "object"], f)
            path = f.name
        try:
            cfg = SpliceHTTPConfig.from_env(config_path=path)
            assert cfg.base_url == "https://api.splice.com"
            assert not cfg.is_user_configured
        finally:
            os.unlink(path)
    finally:
        restore()


def test_b5_allow_unverified_flag_from_json():
    """`allow_unverified_endpoints: true` should mark config as user-configured
    even when no explicit endpoint is overridden."""
    from mcp_server.splice_client.http_bridge import SpliceHTTPConfig
    restore = _isolated_env()
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"allow_unverified_endpoints": True}, f)
            path = f.name
        try:
            cfg = SpliceHTTPConfig.from_env(config_path=path)
            assert cfg.is_user_configured
        finally:
            os.unlink(path)
    finally:
        restore()


# ── B6: collection_uuid in search_samples ─────────────────────────────


def test_b6_search_samples_accepts_collection_uuid():
    import inspect
    from mcp_server.sample_engine.tools import search_samples
    sig = inspect.signature(search_samples)
    assert "collection_uuid" in sig.parameters


# ── B7: verify_all_devices_health ─────────────────────────────────────


def test_b7_verify_all_devices_health_signature():
    import inspect
    from mcp_server.tools.analyzer import verify_all_devices_health
    sig = inspect.signature(verify_all_devices_health)
    assert "test_midi_note" in sig.parameters
    assert "skip_audio_tracks" in sig.parameters
    assert "skip_empty_tracks" in sig.parameters
    assert "threshold" in sig.parameters


# ── B8: sub_detail in get_master_spectrum ─────────────────────────────


def test_b8_get_master_spectrum_has_sub_detail():
    import inspect
    from mcp_server.tools.analyzer import get_master_spectrum
    sig = inspect.signature(get_master_spectrum)
    assert "sub_detail" in sig.parameters


def test_b8_attach_sub_detail_without_mel_warns_cleanly():
    """When FluCoMa mel data is absent, _attach_sub_detail writes a warning
    without crashing."""
    from mcp_server.tools.analyzer import _attach_sub_detail

    class _EmptyCache:
        def get(self, key):
            return None

    result: dict = {}
    _attach_sub_detail(_EmptyCache(), result)
    assert "sub_detail_warning" in result
    assert "FluCoMa" in result["sub_detail_warning"]


def test_b8_attach_sub_detail_with_mel_data_populates_buckets():
    """Given 40-band mel data, sub_detail has sub_deep/sub_mid/sub_high."""
    from mcp_server.tools.analyzer import _attach_sub_detail

    class _MelCache:
        def get(self, key):
            if key == "mel_bands":
                return {
                    "value": [0.8, 0.6, 0.4, 0.2] + [0.0] * 36,
                    "age_ms": 120,
                }
            return None

    result: dict = {}
    _attach_sub_detail(_MelCache(), result)
    assert "sub_detail" in result
    sd = result["sub_detail"]
    assert "sub_deep" in sd
    assert "sub_mid" in sd
    assert "sub_high" in sd
    # sub_deep is mean of bands 0 and 1 → (0.8+0.6)/2 = 0.7
    assert sd["sub_deep"] == pytest.approx(0.7, abs=0.01)
    assert sd["sub_mid"] == pytest.approx(0.4, abs=0.01)
    assert sd["sub_high"] == pytest.approx(0.2, abs=0.01)
    assert sd["source"] == "flucoma_mel_40"


def test_b8_attach_sub_detail_handles_short_mel_list():
    """Mel list with <4 bands → warning instead of crash."""
    from mcp_server.tools.analyzer import _attach_sub_detail

    class _ShortMelCache:
        def get(self, key):
            if key == "mel_bands":
                return {"value": [0.5, 0.3], "age_ms": 100}
            return None

    result: dict = {}
    _attach_sub_detail(_ShortMelCache(), result)
    assert "sub_detail_warning" in result


# ── rename_chain remote-command registration ──────────────────────────


def test_rename_chain_is_registered_remote_command():
    """The rename_chain MCP tool targets set_chain_name — must be in the
    authoritative remote-command list (test_command_boundary_audit relies
    on this)."""
    from mcp_server.runtime.remote_commands import ALL_VALID_COMMANDS
    assert "set_chain_name" in ALL_VALID_COMMANDS
    assert "fire_test_note" in ALL_VALID_COMMANDS
    assert "cleanup_test_note" in ALL_VALID_COMMANDS
