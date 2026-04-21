# tests/test_replace_sample_routing.py
"""MCP-side routing: replace_simpler_sample and load_sample_to_simpler
choose native (12.4+) vs. M4L-bridge (pre-12.4) path based on the
detected Live version.

Context key convention (source: mcp_server/server.py lifespan):
  - "ableton"  : AbletonConnection (sync send_command(name, dict))
  - "m4l"      : M4LBridge (async send_command(name, *args))
  - "spectral" : SpectralCache
  - "_live_caps": lazily cached by mcp_server.tools.analyzer._live_caps
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from mcp_server.runtime.live_version import LiveVersionCapabilities


def _mk_ctx(live_version: str, bridge_result=None):
    """Construct a minimal context matching the keys analyzer.py actually reads."""
    bridge = MagicMock()
    bridge.send_command = AsyncMock(
        return_value=bridge_result or {"sample_loaded": True}
    )
    ableton = MagicMock()
    ableton.send_command = MagicMock(return_value={})

    spectral = MagicMock()
    spectral.is_connected = True

    ctx = MagicMock()
    ctx.lifespan_context = {
        "ableton": ableton,
        "m4l": bridge,
        "spectral": spectral,
        "_live_caps": LiveVersionCapabilities.from_version_string(live_version),
    }
    return ctx, bridge, ableton


# ── replace_simpler_sample routing ─────────────────────────────────────

@pytest.mark.asyncio
async def test_12_4_uses_native_path():
    ctx, bridge, ableton = _mk_ctx("12.4.0")
    ableton.send_command.return_value = {
        "sample_loaded": True,
        "method": "native_12_4",
        "track_index": 0,
        "device_index": 0,
    }
    with patch("mcp_server.tools.analyzer._require_analyzer"), \
         patch("mcp_server.tools.analyzer._simpler_post_load_hygiene",
               new=AsyncMock(return_value={"verified": True})):
        from mcp_server.tools.analyzer import replace_simpler_sample
        result = await replace_simpler_sample(ctx, 0, 0, "/tmp/a.wav")

    ableton.send_command.assert_called_once()
    call_name = ableton.send_command.call_args[0][0]
    assert call_name == "replace_sample_native"
    bridge.send_command.assert_not_called()
    assert result["method"] == "native_12_4"


@pytest.mark.asyncio
async def test_12_3_6_uses_bridge_path():
    ctx, bridge, ableton = _mk_ctx("12.3.6")
    with patch("mcp_server.tools.analyzer._require_analyzer"), \
         patch("mcp_server.tools.analyzer._simpler_post_load_hygiene",
               new=AsyncMock(return_value={"verified": True})):
        from mcp_server.tools.analyzer import replace_simpler_sample
        await replace_simpler_sample(ctx, 0, 0, "/tmp/a.wav")

    bridge.send_command.assert_called_once()
    call_name = bridge.send_command.call_args[0][0]
    assert call_name == "replace_simpler_sample"
    for call in ableton.send_command.call_args_list:
        assert call[0][0] != "replace_sample_native"


@pytest.mark.asyncio
async def test_12_4_falls_back_to_bridge_on_native_error():
    ctx, bridge, ableton = _mk_ctx("12.4.0")
    ableton.send_command.return_value = {
        "error": "file not found",
        "code": "INTERNAL",
    }
    with patch("mcp_server.tools.analyzer._require_analyzer"), \
         patch("mcp_server.tools.analyzer._simpler_post_load_hygiene",
               new=AsyncMock(return_value={"verified": True})):
        from mcp_server.tools.analyzer import replace_simpler_sample
        await replace_simpler_sample(ctx, 0, 0, "/tmp/a.wav")

    assert ableton.send_command.called
    assert bridge.send_command.called
    assert bridge.send_command.call_args[0][0] == "replace_simpler_sample"


# ── load_sample_to_simpler routing ─────────────────────────────────────

@pytest.mark.asyncio
async def test_load_12_4_skips_bootstrap_and_uses_native():
    ctx, bridge, ableton = _mk_ctx("12.4.0")
    ableton.send_command.side_effect = [
        {"device_index": 0},
        {"sample_loaded": True, "method": "native_12_4",
         "track_index": 0, "device_index": 0},
    ]
    with patch("mcp_server.tools.analyzer._require_analyzer"), \
         patch("mcp_server.tools.analyzer._simpler_post_load_hygiene",
               new=AsyncMock(return_value={"verified": True})):
        from mcp_server.tools.analyzer import load_sample_to_simpler
        result = await load_sample_to_simpler(ctx, 0, "/tmp/a.wav")

    assert not bridge.send_command.called
    assert result.get("method") == "native_12_4"


@pytest.mark.asyncio
async def test_load_12_3_6_uses_bootstrap_and_bridge():
    ctx, bridge, ableton = _mk_ctx("12.3.6")
    ableton.send_command.side_effect = [
        {"results": [{"uri": "query:Samples:kick_A.wav"}]},
        {"loaded": True},
        {"devices": [{"name": "Simpler"}]},
    ]
    with patch("mcp_server.tools.analyzer._require_analyzer"), \
         patch("mcp_server.tools.analyzer._simpler_post_load_hygiene",
               new=AsyncMock(return_value={"verified": True})):
        from mcp_server.tools.analyzer import load_sample_to_simpler
        await load_sample_to_simpler(ctx, 0, "/tmp/a.wav")

    assert bridge.send_command.called
    assert bridge.send_command.call_args[0][0] == "replace_simpler_sample"
