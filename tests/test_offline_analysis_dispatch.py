"""#103: real worker results, bounded lifetime, and cancellation recovery."""
import asyncio
import sys

import numpy as np
import pytest
import soundfile as sf

from mcp_server.runtime import offline_analysis


@pytest.fixture
def capture(tmp_path):
    path = tmp_path / 'capture.aiff'
    t = np.arange(48000) / 48000
    mono = (.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, np.column_stack([mono, mono]), 48000)
    return str(path)


@pytest.mark.asyncio
@pytest.mark.parametrize('operation,key', [
    ('analyze_spectrum_offline', 'centroid_hz'),
    ('analyze_loudness', 'integrated_lufs'),
    ('read_audio_metadata', 'sample_rate'),
    ('listen_capture', 'snapshot'),
])
async def test_registered_tool_runs_real_worker(operation, key, capture):
    from mcp_server.server import mcp
    arguments = {'file': capture, 'bpm': 120} if operation == 'listen_capture' else {'file_path': capture}
    result = await mcp.call_tool(operation, arguments)
    assert key in result.structured_content


@pytest.fixture
def hung_worker(monkeypatch):
    # Substitute only the child executable body, keeping AnyIO's real process
    # ownership, pipes, cancellation and wait code in the path under test.
    import anyio._core._subprocesses as process_core
    original = process_core.open_process
    children = []
    async def open_hung(command, **kwargs):
        process = await original([sys.executable, '-c',
                                 'import sys,time; sys.stdin.buffer.read(); time.sleep(60)'], **kwargs)
        children.append(process)
        return process
    monkeypatch.setattr(process_core, 'open_process', open_hung)
    return children


@pytest.mark.asyncio
async def test_hung_analysis_times_out_and_reaps_child(hung_worker):
    result = await offline_analysis.run_offline_analysis('read_audio_metadata', {}, timeout=.5)
    assert result['code'] == 'TIMEOUT'
    assert len(hung_worker) == 1
    assert hung_worker[0].returncode is not None


@pytest.mark.asyncio
async def test_cancellation_reaps_child_and_keeps_mcp_session_usable(hung_worker, mcp_client_factory):
    async with mcp_client_factory() as client:
        task = asyncio.create_task(client.call_tool('read_audio_metadata', {'file_path': 'unused.wav'}))
        for _ in range(100):
            if hung_worker:
                break
            await asyncio.sleep(.01)
        assert hung_worker
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        # Cancellation is a protocol notification; give the server handler a
        # bounded interval to close and reap the child before checking it.
        for _ in range(100):
            if hung_worker[0].returncode is not None:
                break
            await asyncio.sleep(.01)
        assert hung_worker[0].returncode is not None
        result = await client.call_tool('get_session_info', {})
        assert not result.is_error


@pytest.mark.asyncio
async def test_worker_preserves_input_error(capture):
    result = await offline_analysis.run_offline_analysis('analyze_loudness',
                                                        {'file_path': capture, 'detail': 'bad'})
    assert result['code'] == 'INVALID_PARAM'


@pytest.mark.asyncio
async def test_search_first_call_tool_route_runs_analysis(capture):
    from fastmcp import Client, FastMCP
    from mcp_server.runtime.tool_surface import build_tool_search_transform
    from mcp_server.server import _get_all_tools
    local = FastMCP('offline-search-test')
    for tool in _get_all_tools():
        local.add_tool(tool)
    local.add_transform(build_tool_search_transform('producer'))
    async with Client(local) as client:
        result = await client.call_tool('call_tool', {
            'name': 'analyze_spectrum_offline', 'arguments': {'file_path': capture},
        })
    assert not result.is_error
    assert 'centroid_hz' in str(result)
