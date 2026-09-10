"""Transport selection in ``mcp_server.server.main``.

stdio must stay the default and behave exactly as before; ``http`` /
``streamable-http`` opt in to the shared long-lived server.
"""

from unittest.mock import patch

import pytest

from mcp_server import server


@pytest.fixture(autouse=True)
def _quiet_startup():
    """Skip the contract assertions and tool-surface install for these tests."""
    with (
        patch.object(server, "_assert_expected_tool_count"),
        patch.object(server, "_configure_public_tool_surface", return_value="producer"),
    ):
        yield


def _run_main(monkeypatch, **env):
    for key in (
        "LIVEPILOT_TRANSPORT",
        "LIVEPILOT_HTTP_HOST",
        "LIVEPILOT_HTTP_PORT",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with patch.object(server.mcp, "run") as run:
        server.main()
    return run


def test_default_is_stdio(monkeypatch):
    run = _run_main(monkeypatch)
    run.assert_called_once_with(transport="stdio")


def test_unknown_transport_falls_back_to_stdio(monkeypatch):
    run = _run_main(monkeypatch, LIVEPILOT_TRANSPORT="carrier-pigeon")
    run.assert_called_once_with(transport="stdio")


@pytest.mark.parametrize("value", ["http", "streamable-http", "HTTP", " http "])
def test_http_aliases_select_http(monkeypatch, value):
    run = _run_main(monkeypatch, LIVEPILOT_TRANSPORT=value)
    kwargs = run.call_args.kwargs
    assert kwargs["transport"] == "http"


def test_http_defaults_to_loopback_8109(monkeypatch):
    run = _run_main(monkeypatch, LIVEPILOT_TRANSPORT="http")
    kwargs = run.call_args.kwargs
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 8109


def test_http_honours_host_and_port(monkeypatch):
    run = _run_main(
        monkeypatch,
        LIVEPILOT_TRANSPORT="http",
        LIVEPILOT_HTTP_HOST="0.0.0.0",
        LIVEPILOT_HTTP_PORT="9999",
    )
    kwargs = run.call_args.kwargs
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 9999


@pytest.mark.parametrize("bad", ["", "not-a-number", "80", "70000"])
def test_bad_port_falls_back_to_default(monkeypatch, bad):
    run = _run_main(monkeypatch, LIVEPILOT_TRANSPORT="http", LIVEPILOT_HTTP_PORT=bad)
    assert run.call_args.kwargs["port"] == 8109


def test_http_enables_dns_rebinding_protection(monkeypatch):
    """The server is unauthenticated — Host/Origin checks must be on."""
    run = _run_main(monkeypatch, LIVEPILOT_TRANSPORT="http", LIVEPILOT_HTTP_PORT="8109")
    kwargs = run.call_args.kwargs
    assert kwargs["host_origin_protection"] is True
    assert set(kwargs["allowed_hosts"]) == {
        "127.0.0.1",
        "localhost",
        "127.0.0.1:8109",
        "localhost:8109",
    }
