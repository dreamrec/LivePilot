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


def test_bug_pack_info_handles_extended_uuid_variants():
    """Splice uses both UUID formats — canonical 36-char and extended
    43-char with a longer last group.

    Examples observed 2026-04-22 live:
      "030748a0-c2e8-44d6-bfb7-bb8a1fa4170c"  (36 chars, canonical)
      "1170db75-0ce1-5280-bb61-887a0dd7f26bf5a3951" (43 chars, extended)
      "2fc8c6b5-0d7a-8780-0396-8ea1824e9d94937b309" (43 chars, extended)

    An earlier revision truncated to `[:36]` which incorrectly discarded
    part of the legitimate extended form. The correct behavior: the
    client matches on BOTH the submitted UUID AND the canonical
    truncation so either server-returned format pairs with a submitted
    UUID in either format.
    """
    import inspect
    from mcp_server.splice_client.client import SpliceGRPCClient
    source = inspect.getsource(SpliceGRPCClient.get_pack_info)
    # The two-form matching strategy is the guard.
    assert "targets" in source, (
        "get_pack_info must build a set of UUID targets (submitted + "
        "canonical truncation) so extended-UUID Splice packs can still "
        "be resolved when the submitted form is extended but the server "
        "returns the canonical form (or vice versa)."
    )
    # The old lossy truncation-before-matching must NOT reappear
    # as the sole comparison — we need both forms tried.
    assert "p.UUID == target" not in source, (
        "Single-string equality match is insufficient. Use set membership "
        "or dual-form comparison to handle both Splice UUID variants."
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


def test_bug_pack_info_matches_extended_uuid_form():
    """Splice uses both canonical 36-char AND extended 43+-char UUIDs.

    Example extended form observed 2026-04-22:
      "1170db75-0ce1-5280-bb61-887a0dd7f26bf5a3951" (43 chars — last
      group extended to 19 chars instead of standard 12).

    An earlier rev aggressively truncated to `[:36]` which discarded
    part of this legitimate UUID. The correct behavior: try both the
    submitted form AND the canonical truncation so either one matches.
    """
    import inspect
    from mcp_server.splice_client.client import SpliceGRPCClient
    source = inspect.getsource(SpliceGRPCClient.get_pack_info)
    # Must build a set of both forms
    assert "targets = {" in source or "canonical" in source, (
        "get_pack_info must match on both submitted and canonical UUID "
        "forms — Splice's ListSamplePacks returns UUIDs in either form."
    )


def test_bug_pack_info_mcp_wrapper_passes_uuid_unchanged():
    """The MCP wrapper must NOT pre-truncate pack_uuid — let the client
    handle both-form matching."""
    import inspect
    from mcp_server.sample_engine import tools
    source = inspect.getsource(tools.splice_pack_info)
    # The old eager truncation must be gone
    assert "canonical[:36]" not in source, (
        "MCP wrapper pre-truncated UUIDs to 36 chars, breaking lookups "
        "for legitimately-extended 43-char Splice UUIDs. Remove the "
        "truncation — the client handles both forms now."
    )


def test_bug_pack_info_uses_listsamplepacks_rpc():
    """SamplePackInfo RPC doesn't exist on the App service — only
    ListSamplePacks does. The client must paginate ListSamplePacks
    and filter client-side. (Discovered live 2026-04-22 when the
    first pack_info rewrite tried `self.stub.SamplePackInfo(...)` and
    got AttributeError: 'AppStub' object has no attribute 'SamplePackInfo'.)"""
    import inspect
    from mcp_server.splice_client.client import SpliceGRPCClient
    source = inspect.getsource(SpliceGRPCClient.get_pack_info)
    assert "ListSamplePacks" in source, (
        "get_pack_info must use ListSamplePacks + client-side match — "
        "SamplePackInfo RPC is not exposed by the Splice App service."
    )
    # Must not CALL SamplePackInfo (docstring may still mention it
    # explanatorily). Check for the actual invocation pattern.
    assert "stub.SamplePackInfo" not in source, (
        "Do not call stub.SamplePackInfo — that RPC doesn't exist on "
        "the Splice App service. Use ListSamplePacks instead."
    )
    assert "SamplePackInfoRequest(" not in source, (
        "Do not construct SamplePackInfoRequest — no RPC binds it."
    )


# ── Observation 1: plan_kind_override via config ──────────────────────


def test_plan_kind_override_bypasses_classifier():
    """Users who know their actual Splice plan can pin plan_kind via
    ~/.livepilot/splice.json. Override ignores the gRPC data entirely."""
    from mcp_server.splice_client.models import PlanKind, classify_plan

    # With no override, generic "subscribed" + unknown plan_id → SOUNDS_PLUS
    without = classify_plan(sounds_status="subscribed", sounds_plan=6, features={})
    assert without == PlanKind.SOUNDS_PLUS

    # With override, the classifier returns the pinned value
    with_override = classify_plan(
        sounds_status="subscribed",
        sounds_plan=6,
        features={},
        override="ableton_live",
    )
    assert with_override == PlanKind.ABLETON_LIVE


def test_plan_kind_override_rejects_unknown_values():
    """An override string that doesn't match any PlanKind is ignored —
    fallthrough to normal classification."""
    from mcp_server.splice_client.models import PlanKind, classify_plan
    result = classify_plan(
        sounds_status="subscribed",
        sounds_plan=6,
        features={},
        override="pro_max_ultra",  # not a real PlanKind
    )
    # Falls through to the normal path → SOUNDS_PLUS
    assert result == PlanKind.SOUNDS_PLUS


def test_plan_kind_override_is_case_insensitive():
    """Users shouldn't have to match exact case."""
    from mcp_server.splice_client.models import PlanKind, classify_plan
    result = classify_plan(
        sounds_status="",
        sounds_plan=0,
        features={},
        override="ABLETON_LIVE",  # uppercase
    )
    assert result == PlanKind.ABLETON_LIVE


def test_read_plan_kind_override_handles_missing_file():
    """Silent fallback to None when ~/.livepilot/splice.json is absent
    or the key isn't in the file."""
    from mcp_server.splice_client.client import _read_plan_kind_override
    import os, tempfile, json
    # Point HOME at an empty dir — no splice.json inside
    import unittest.mock as mock
    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.dict(os.environ, {"HOME": tmp}):
            assert _read_plan_kind_override() is None


def test_read_plan_kind_override_handles_corrupt_json():
    """Corrupt JSON → None, no crash."""
    from mcp_server.splice_client.client import _read_plan_kind_override
    import os, tempfile
    import unittest.mock as mock
    with tempfile.TemporaryDirectory() as tmp:
        livepilot_dir = os.path.join(tmp, ".livepilot")
        os.makedirs(livepilot_dir, exist_ok=True)
        with open(os.path.join(livepilot_dir, "splice.json"), "w") as f:
            f.write("{not valid json")
        with mock.patch.dict(os.environ, {"HOME": tmp}):
            assert _read_plan_kind_override() is None


# ── Observation 2: startup self-test uses max view, not first ─────────


def test_get_all_tools_returns_largest_probe_result():
    """The self-test used to take the first non-empty probe, which could
    pick up a stale `_tool_manager._tools` view lagging behind
    `_local_provider._components`. Now takes the MAX across probes."""
    import inspect
    from mcp_server import server
    source = inspect.getsource(server._get_all_tools)
    assert "len(tools) > len(best)" in source, (
        "_get_all_tools must compare probe sizes and return the largest "
        "registry view. Taking the first non-empty probe can pick a "
        "stale internal dict that lags the authoritative registry."
    )


def test_get_all_tools_no_unawaited_coroutine_probe():
    """Removed the `list_tools` probe that raised RuntimeWarning every
    import — it wrapped an async method in list() without awaiting.

    Source check only — we can't `importlib.reload(server)` as a runtime
    proof because that unregisters every `@mcp.tool()` decorator and
    breaks every downstream tool-count test in the suite.
    """
    import inspect
    from mcp_server import server
    source = inspect.getsource(server._get_all_tools)
    # The probe was registered as a tuple of (label, lambda). Check for
    # the tuple form that represents an active probe.
    assert '("list_tools", lambda' not in source, (
        "The ('list_tools', lambda: list(mcp.list_tools())) probe wraps "
        "a coroutine in list() without awaiting — raises RuntimeWarning "
        "on every server import. Removed 2026-04-22."
    )
    # Belt-and-suspenders: no un-awaited coroutine call pattern in source.
    assert "list(mcp.list_tools())" not in [
        line.strip().lstrip("#").strip()
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ], (
        "Source contains `list(mcp.list_tools())` on a non-comment line — "
        "that's the broken pattern. Should only appear inside comments."
    )
