"""Tests for runtime capability probes (PR-B).

The probes live in ``mcp_server/runtime/tools.py`` inside
``get_capability_state``. Before PR-B they were hardcoded
(``web_ok = False`` / ``flucoma_ok = False``), so orchestration picked
degraded paths on machines where these capabilities were available.

These tests verify the probes actually do work — that they return True
when the probed surface is reachable, and False (without raising) when
it isn't.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Shared fakes ────────────────────────────────────────────────────────


class _Ableton:
    """Minimal ableton stand-in; answers get_session_info only."""

    def send_command(self, cmd, params=None):
        if cmd == "get_session_info":
            return {"tempo": 120, "track_count": 0, "tracks": []}
        return {}


def _make_ctx(spectral=None):
    return SimpleNamespace(
        lifespan_context={"ableton": _Ableton(), "spectral": spectral},
    )


# ── Task B1: web probe ──────────────────────────────────────────────────


def test_web_probe_true_when_github_reachable(monkeypatch):
    """When the HEAD probe to api.github.com succeeds, web domain is available."""
    from mcp_server.runtime import tools as runtime_tools

    # Force the probe to report reachable
    monkeypatch.setattr(runtime_tools, "_probe_web", lambda timeout=0.5: True)

    ctx = _make_ctx()
    result = runtime_tools.get_capability_state(ctx)

    domains = result["capability_state"]["domains"]
    assert "web" in domains
    assert domains["web"]["available"] is True
    assert domains["web"]["mode"] == "available"


def test_web_probe_false_on_timeout(monkeypatch):
    """A failed/timed-out probe must resolve cleanly to False, never raise."""
    from mcp_server.runtime import tools as runtime_tools

    monkeypatch.setattr(runtime_tools, "_probe_web", lambda timeout=0.5: False)

    ctx = _make_ctx()
    result = runtime_tools.get_capability_state(ctx)

    domains = result["capability_state"]["domains"]
    assert domains["web"]["available"] is False
    assert "web_unavailable" in domains["web"]["reasons"]


def test_web_probe_helper_swallows_exceptions(monkeypatch):
    """The probe helper itself must swallow all network exceptions to False.

    This guards against any future refactor that forgets the try/except.
    """
    from mcp_server.runtime import tools as runtime_tools

    def _raises(*_args, **_kwargs):
        raise OSError("simulated dns failure")

    monkeypatch.setattr(runtime_tools.urllib.request, "urlopen", _raises)

    assert runtime_tools._probe_web(timeout=0.01) is False


# ── Task B2: flucoma probe ──────────────────────────────────────────────


def test_flucoma_domain_present_when_importable(monkeypatch):
    """When flucoma is importable, a flucoma domain is emitted as available."""
    from mcp_server.runtime import tools as runtime_tools

    monkeypatch.setattr(runtime_tools, "_probe_flucoma", lambda: True)

    ctx = _make_ctx()
    result = runtime_tools.get_capability_state(ctx)

    domains = result["capability_state"]["domains"]
    assert "flucoma" in domains, (
        f"Expected 'flucoma' domain in capability state; got {sorted(domains)}"
    )
    assert domains["flucoma"]["available"] is True
    assert domains["flucoma"]["mode"] == "available"


def test_flucoma_domain_unavailable_when_not_installed(monkeypatch):
    """When flucoma is not importable, the domain still emits but unavailable."""
    from mcp_server.runtime import tools as runtime_tools

    monkeypatch.setattr(runtime_tools, "_probe_flucoma", lambda: False)

    ctx = _make_ctx()
    result = runtime_tools.get_capability_state(ctx)

    domains = result["capability_state"]["domains"]
    assert "flucoma" in domains
    assert domains["flucoma"]["available"] is False
    assert "flucoma_not_installed" in domains["flucoma"]["reasons"]


def test_flucoma_probe_helper_uses_find_spec(monkeypatch):
    """The flucoma probe must consult importlib.util.find_spec (no hard import).

    Hard `import flucoma` at module load would crash CI. We require find_spec
    (None -> False) so the probe stays zero-side-effect.
    """
    import importlib.util

    from mcp_server.runtime import tools as runtime_tools

    # Simulate no spec: probe must be False, no exception.
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert runtime_tools._probe_flucoma() is False

    # Simulate a spec present
    class _Spec:  # pragma: no cover - trivial sentinel
        pass

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: _Spec())
    assert runtime_tools._probe_flucoma() is True
