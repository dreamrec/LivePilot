"""#102: permit UDP callbacks during doctor warm-up and detect Windows holders."""
import asyncio
import json
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.asyncio
async def test_bridge_warmup_processes_queued_packets(monkeypatch):
    from mcp_server import server
    spectral = type('Cache', (), {'is_connected': False})()
    monkeypatch.setattr(server, '_master_has_livepilot_analyzer', lambda ableton: True)
    asyncio.get_running_loop().call_later(.02, setattr, spectral, 'is_connected', True)
    await server._warm_analyzer_bridge(object(), spectral, timeout=.5)
    assert spectral.is_connected


def test_windows_udp_holder_uses_exact_port_and_excludes_self(monkeypatch):
    from mcp_server import server
    monkeypatch.setattr(server.sys, 'platform', 'win32')
    rows = f'  UDP    127.0.0.1:19880    *:*    987\n  UDP    0.0.0.0:9880    *:*    {server.os.getpid()}\n  UDP    [::]:9880    *:*    654\n'
    def netstat(command, **kwargs):
        assert command == ['netstat', '-ano', '-p', 'udp']
        return rows
    monkeypatch.setattr(server.subprocess, 'check_output', netstat)
    assert server._identify_port_holder(9880) == '654'


def test_windows_tcp_client_parser():
    node = shutil.which('node')
    if not node:
        pytest.skip('node unavailable')
    root = Path(__file__).resolve().parents[1]
    rows = '  TCP  127.0.0.1:9878  127.0.0.1:12345  ESTABLISHED  321\n  TCP  127.0.0.1:12345  127.0.0.1:9878  ESTABLISHED  654\n'
    script = 'const {parseWindowsLiveClient:p}=require("./bin/livepilot.js"); console.log(JSON.stringify([p('+json.dumps(rows)+',"127.0.0.1",9878),p('+json.dumps(rows)+',"127.0.0.1",19878)]));'
    out = subprocess.run([node, '-e', script], cwd=root, text=True, capture_output=True, check=True)
    assert json.loads(out.stdout) == ['PID 654', None]
