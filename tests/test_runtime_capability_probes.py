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

    # v1.17.4: capability_state is flat — kernel["capability_state"]["domains"].
    cap_state = kernel.get("capability_state")
    assert cap_state is not None, (
        f"kernel must expose capability_state; got kernel keys {list(kernel.keys())!r}"
    )
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

    cap_state = kernel.get("capability_state")
    assert cap_state is not None
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

    cap_state = kernel.get("capability_state")
    assert cap_state is not None
    domains = cap_state.get("domains", {})
    assert domains.get("web", {}).get("available") is False
    assert domains.get("flucoma", {}).get("available") is False


# ── v1.17.4 — memory_ok must be probed, not hardcoded ──────────────────
#
# Prior behavior (v1.17.3): get_session_kernel hardcoded memory_ok=True
# regardless of whether the memory store was actually functional. If the
# store raised on list_techniques (disk full, corrupted index, permissions
# error), the kernel still reported memory as available to orchestration
# planners. Same truth-gap class as the v1.17.3 web/flucoma fix.
# get_capability_state already probes correctly; kernel should too.


def test_session_kernel_reports_memory_unavailable_when_store_raises(monkeypatch):
    """When the underlying technique store raises, get_session_kernel must
    NOT report memory as available. Previously hardcoded True — the bug."""
    from mcp_server.runtime import tools as runtime_tools

    class _ExplodingStore:
        def list_techniques(self, **kwargs):
            raise RuntimeError("simulated store failure")

    monkeypatch.setattr(runtime_tools, "_memory_store", _ExplodingStore())

    ctx = _make_ctx()
    kernel = runtime_tools.get_session_kernel(ctx)

    cap_state = kernel.get("capability_state")
    assert cap_state is not None
    domains = cap_state.get("domains", {})
    memory = domains.get("memory", {})
    assert memory.get("available") is False, (
        f"memory probe raised, but kernel reports memory available; "
        f"domains['memory']={memory!r}"
    )


def test_session_kernel_reports_memory_available_when_store_works(monkeypatch):
    """Back-compat: when the store works, memory.available must be True."""
    from mcp_server.runtime import tools as runtime_tools

    class _WorkingStore:
        def list_techniques(self, **kwargs):
            return []  # empty list is a valid probe response

    monkeypatch.setattr(runtime_tools, "_memory_store", _WorkingStore())

    ctx = _make_ctx()
    kernel = runtime_tools.get_session_kernel(ctx)

    cap_state = kernel.get("capability_state")
    assert cap_state is not None
    domains = cap_state.get("domains", {})
    memory = domains.get("memory", {})
    assert memory.get("available") is True, (
        f"memory probe succeeded, but kernel reports unavailable; "
        f"domains['memory']={memory!r}"
    )


# ── v1.17.4 — flatten capability_state shape (no double-nesting) ───────
#
# Prior behavior: get_session_kernel passed build_capability_state(...).to_dict()
# as-is to build_session_kernel. state.to_dict() already wraps its own
# output in {"capability_state": {...}}, so consumers had to navigate
# kernel["capability_state"]["capability_state"]["domains"] — ugly.
# v1.17.3 tests worked around it with `outer.get("capability_state", outer)`.
# Fix: pass state.to_dict()["capability_state"] so the kernel stores the
# inner dict directly. Consumer path becomes kernel["capability_state"]["domains"].


def test_kernel_capability_state_is_flat_not_double_nested(monkeypatch):
    """The kernel's capability_state field must be the capability state dict
    directly — NOT a dict wrapping another 'capability_state' key.

    Old shape (broken): kernel["capability_state"]["capability_state"]["domains"]
    New shape (fixed):  kernel["capability_state"]["domains"]
    """
    from mcp_server.runtime import tools as runtime_tools

    monkeypatch.setattr(runtime_tools, "_probe_web", lambda timeout=0.5: False)
    monkeypatch.setattr(runtime_tools, "_probe_flucoma", lambda: False)

    ctx = _make_ctx()
    kernel = runtime_tools.get_session_kernel(ctx)

    cap_state = kernel["capability_state"]
    # The flat shape MUST expose domains + overall_mode at this level
    assert "domains" in cap_state, (
        f"kernel['capability_state'] must contain 'domains' directly; "
        f"got keys {list(cap_state.keys())!r}"
    )
    assert "overall_mode" in cap_state, (
        f"kernel['capability_state'] must contain 'overall_mode' directly; "
        f"got keys {list(cap_state.keys())!r}"
    )
    # And MUST NOT have a nested 'capability_state' key (the old broken shape)
    assert "capability_state" not in cap_state, (
        f"kernel['capability_state'] must not double-wrap 'capability_state' "
        f"key; found keys {list(cap_state.keys())!r}. Old shape was "
        f"kernel['capability_state']['capability_state']['domains'] — we "
        f"want the inner dict at kernel['capability_state'] directly."
    )


def test_kernel_flat_shape_preserves_domain_access():
    """End-to-end: with the flat shape, planners access
    kernel['capability_state']['domains']['session_access'] directly
    without any outer-wrapper hop."""
    from mcp_server.runtime import tools as runtime_tools

    ctx = _make_ctx()
    kernel = runtime_tools.get_session_kernel(ctx)

    # Direct access without any defensive fallback
    cap_state = kernel["capability_state"]
    domains = cap_state["domains"]
    session = domains["session_access"]

    assert session["available"] is True  # _Ableton returns a valid session_info
    assert session["name"] == "session_access"
