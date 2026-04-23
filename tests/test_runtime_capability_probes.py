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


# ── P2#3 (v1.17.3) — probes must propagate through get_session_kernel ──
#
# Prior behavior: get_session_kernel called build_capability_state() with
# only session/analyzer/memory arguments, so web_ok and flucoma_ok
# defaulted to False. Meanwhile get_capability_state correctly probed
# both and passed them through. Higher-level planners use the session
# kernel as the orchestration entrypoint, so they stayed on degraded
# paths even when probes would have reported available.


def test_session_kernel_surfaces_web_probe_result(monkeypatch):
    """monkeypatch _probe_web to return True; get_session_kernel must
    report web as available in its capability state."""
    from mcp_server.runtime import tools as runtime_tools

    monkeypatch.setattr(runtime_tools, "_probe_web", lambda timeout=0.5: True)
    # Keep flucoma default (off) to isolate the web signal
    monkeypatch.setattr(runtime_tools, "_probe_flucoma", lambda: False)

    ctx = _make_ctx()
    kernel = runtime_tools.get_session_kernel(ctx)

    # Kernel exposes capability state double-wrapped: kernel["capability_state"]
    # is the dict from build_capability_state(...).to_dict(), which itself
    # has shape {"capability_state": {"overall_mode": ..., "domains": {...}}}.
    outer = kernel.get("capability_state")
    assert outer is not None, (
        f"kernel must expose capability_state; got kernel keys {list(kernel.keys())!r}"
    )
    cap_state = outer.get("capability_state", outer)
    domains = cap_state.get("domains", {})
    assert "web" in domains, (
        f"kernel capability state must include web domain; got {list(domains)!r}"
    )
    assert domains["web"]["available"] is True, (
        f"web probe returned True, but kernel reports web unavailable; "
        f"domains['web']={domains['web']!r}"
    )


def test_session_kernel_surfaces_flucoma_probe_result(monkeypatch):
    """monkeypatch _probe_flucoma to return True; kernel must report it."""
    from mcp_server.runtime import tools as runtime_tools

    monkeypatch.setattr(runtime_tools, "_probe_web", lambda timeout=0.5: False)
    monkeypatch.setattr(runtime_tools, "_probe_flucoma", lambda: True)

    ctx = _make_ctx()
    kernel = runtime_tools.get_session_kernel(ctx)

    outer = kernel.get("capability_state")
    assert outer is not None
    cap_state = outer.get("capability_state", outer)
    domains = cap_state.get("domains", {})
    assert domains.get("flucoma", {}).get("available") is True, (
        f"flucoma probe returned True, but kernel reports unavailable; "
        f"domains['flucoma']={domains.get('flucoma')!r}"
    )


def test_session_kernel_reports_both_unavailable_when_probes_false(monkeypatch):
    """Back-compat: when both probes return False, kernel still reports
    them correctly (unavailable)."""
    from mcp_server.runtime import tools as runtime_tools

    monkeypatch.setattr(runtime_tools, "_probe_web", lambda timeout=0.5: False)
    monkeypatch.setattr(runtime_tools, "_probe_flucoma", lambda: False)

    ctx = _make_ctx()
    kernel = runtime_tools.get_session_kernel(ctx)

    outer = kernel.get("capability_state")
    assert outer is not None
    cap_state = outer.get("capability_state", outer)
    domains = cap_state.get("domains", {})
    assert domains.get("web", {}).get("available") is False
    assert domains.get("flucoma", {}).get("available") is False
