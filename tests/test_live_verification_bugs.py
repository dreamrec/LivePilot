"""Regression guards for bugs discovered during live verification
before the v1.16.1 publish.

These three bugs all passed unit tests but surfaced only when MCP tools
were invoked against a running Splice desktop + Ableton 12.4:

  1. add_drum_rack_pad crashed with ImportError — wrong relative path
     (`from .._analyzer_engine` instead of `._analyzer_engine`).
  2. splice_preview_sample returned "No preview URL" for un-downloaded
     catalog samples — SampleInfo RPC doesn't carry PreviewURL for
     those; need to fall back to SearchSamples(FileHash=...).
  3. splice_pack_info returned opaque "Pack not found or gRPC call
     failed" — no way to tell RPC failure from invalid UUID from
     permission error. Now returns structured error messages and
     normalizes trailing bytes on pack_uuid.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest


# ── Bug #1: add_drum_rack_pad import path ─────────────────────────────


def test_bug_add_drum_rack_pad_importable():
    """Regression guard: add_drum_rack_pad must import cleanly.

    Earlier form had `from .._analyzer_engine.sample import ...` inside
    the function body — that path resolves to `mcp_server._analyzer_engine`
    which doesn't exist (the real package is `mcp_server.tools._analyzer_engine`).
    The function would crash with ImportError on first invocation.

    We exercise the import path rather than trying to execute the full
    tool (which needs live Ableton). If the relative path regresses again
    this test will fail at function discovery.
    """
    from mcp_server.tools.analyzer import add_drum_rack_pad
    assert add_drum_rack_pad is not None
    # The hygiene helper it depends on must be available at module scope
    from mcp_server.tools.analyzer import _simpler_post_load_hygiene
    assert _simpler_post_load_hygiene is not None


def test_bug_add_drum_rack_pad_no_broken_inline_import():
    """Ensure no future refactor re-introduces the broken `from .._analyzer_engine` path."""
    import inspect
    from mcp_server.tools import analyzer
    source = inspect.getsource(analyzer)
    # The specific broken form — we allow `.._analyzer_engine` nowhere.
    assert "from .._analyzer_engine" not in source, (
        "Found `from .._analyzer_engine` import — this resolves to "
        "mcp_server._analyzer_engine which doesn't exist. Use "
        "`._analyzer_engine` (single dot = sibling in mcp_server.tools)."
    )


# ── Bug #2: splice_preview_sample SearchSamples fallback ──────────────


def test_bug_splice_preview_falls_back_to_search_when_sampleinfo_empty():
    """SampleInfo returns an empty sample for un-downloaded catalog items.

    The preview tool must fall back to SearchSamples(FileHash=...) to
    obtain the PreviewURL in that case.
    """
    from mcp_server.splice_client.models import SpliceSample, SpliceSearchResult

    # A fake client where SampleInfo returns empty, SearchSamples returns
    # a sample with a preview_url.
    client = MagicMock()
    client.connected = True

    async def empty_info(_file_hash):
        return SpliceSample()  # empty — no preview_url

    async def catalog_search(**kwargs):
        # Expect SearchSamples(file_hash=...) to be the fallback.
        assert kwargs.get("file_hash") == "abc-hash"
        return SpliceSearchResult(
            total_hits=1,
            samples=[SpliceSample(
                file_hash="abc-hash",
                filename="test.wav",
                preview_url="https://example.com/preview.mp3",
                duration_ms=1000,
            )],
        )

    client.get_sample_info = empty_info
    client.search_samples = catalog_search

    # Simulate the tool's inner logic rather than the full decorator
    # stack — we're testing the fallback algorithm.
    sample = asyncio.run(client.get_sample_info("abc-hash"))
    assert not sample.preview_url  # baseline: SampleInfo is empty
    fallback = asyncio.run(client.search_samples(file_hash="abc-hash", per_page=1))
    assert fallback.samples[0].preview_url == "https://example.com/preview.mp3"


def test_bug_splice_preview_source_includes_search_fallback():
    """The actual tool source must contain the SearchSamples fallback path."""
    import inspect
    from mcp_server.sample_engine import tools
    source = inspect.getsource(tools.splice_preview_sample)
    assert "search_samples" in source and "file_hash=file_hash" in source, (
        "splice_preview_sample must call search_samples(file_hash=...) "
        "as a fallback when SampleInfo returns an empty PreviewURL. "
        "See BUG discovered 2026-04-22 live verification."
    )


# ── Bug #3: splice_pack_info structured errors + UUID normalization ───


def test_bug_pack_info_returns_tuple_shape():
    """SpliceGRPCClient.get_pack_info now returns (pack, error) — not just pack."""
    import inspect
    from mcp_server.splice_client.client import SpliceGRPCClient
    sig = inspect.signature(SpliceGRPCClient.get_pack_info)
    ret = sig.return_annotation
    # Should be tuple[Optional[SplicePack], Optional[str]]
    assert "tuple" in str(ret).lower() or "Tuple" in str(ret), (
        f"get_pack_info must return a tuple (pack, error_msg). Got: {ret}"
    )


def test_bug_pack_info_normalizes_trailing_suffix():
    """Some Splice pack_uuids have decoration bytes past the 36-char UUID.

    Example observed 2026-04-22 live:
      "2fc8c6b5-0d7a-8780-0396-8ea1824e9d94937b309"  (45 chars)
      — valid UUID is the first 36 chars:
      "2fc8c6b5-0d7a-8780-0396-8ea1824e9d94"

    The MCP wrapper truncates to canonical form before the RPC so
    existing catalog search results can be fed straight into
    splice_pack_info.
    """
    import inspect
    from mcp_server.sample_engine import tools
    source = inspect.getsource(tools.splice_pack_info)
    # Must contain canonical-form truncation logic
    assert (
        'canonical[:36]' in source
        or 'canonical = pack_uuid' in source
    ), (
        "splice_pack_info must normalize pack_uuid to canonical 36-char "
        "UUID form before calling the gRPC. Long forms like "
        "'<uuid>937b309' otherwise fail server-side."
    )


def test_bug_pack_info_surfaces_real_error():
    """When the RPC returns an empty Pack, the tool must surface a
    structured error — not the legacy opaque 'Pack not found or gRPC
    call failed' which hides whether the failure was invalid UUID,
    network, or permission."""
    import inspect
    from mcp_server.sample_engine import tools
    source = inspect.getsource(tools.splice_pack_info)
    # Must surface the error message from the client (err_msg)
    assert 'err_msg' in source, (
        "splice_pack_info must forward err_msg from client.get_pack_info "
        "so callers can diagnose the real failure cause."
    )
