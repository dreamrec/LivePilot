"""Tests for Capability State v1 — runtime capability model."""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.runtime.capability_state import (
    CapabilityDomain,
    CapabilityState,
    build_capability_state,
)


# ── CapabilityDomain ────────────────────────────────────────────────────

class TestCapabilityDomain:
    def test_healthy_domain(self):
        d = CapabilityDomain(
            name="session_access",
            available=True,
            confidence=1.0,
            mode="healthy",
        )
        assert d.available is True
        assert d.confidence == 1.0
        assert d.mode == "healthy"
        assert d.reasons == []

    def test_degraded_domain(self):
        d = CapabilityDomain(
            name="analyzer",
            available=False,
            confidence=0.0,
            mode="unavailable",
            reasons=["analyzer_offline"],
        )
        assert d.available is False
        assert d.confidence == 0.0
        assert d.reasons == ["analyzer_offline"]

    def test_to_dict(self):
        d = CapabilityDomain(
            name="memory",
            available=True,
            confidence=1.0,
            freshness_ms=120,
            mode="available",
            reasons=[],
        )
        out = d.to_dict()
        assert out["name"] == "memory"
        assert out["available"] is True
        assert out["freshness_ms"] == 120
        assert isinstance(out, dict)

    def test_confidence_validation_low(self):
        import pytest
        with pytest.raises(ValueError, match="confidence"):
            CapabilityDomain(name="x", available=True, confidence=-0.1)

    def test_confidence_validation_high(self):
        import pytest
        with pytest.raises(ValueError, match="confidence"):
            CapabilityDomain(name="x", available=True, confidence=1.1)


# ── CapabilityState ─────────────────────────────────────────────────────

class TestCapabilityState:
    def test_builds_from_probes(self):
        state = build_capability_state(session_ok=True)
        assert isinstance(state, CapabilityState)
        assert "session_access" in state.domains
        assert "analyzer" in state.domains
        assert "memory" in state.domains
        assert "web" in state.domains
        assert "research" in state.domains

    def test_degraded_mode_without_analyzer(self):
        state = build_capability_state(session_ok=True, analyzer_ok=False)
        assert state.overall_mode == "measured_degraded"
        assert state.domains["analyzer"].available is False

    def test_normal_mode_with_everything(self):
        state = build_capability_state(
            session_ok=True,
            analyzer_ok=True,
            analyzer_fresh=True,
            memory_ok=True,
            web_ok=True,
        )
        assert state.overall_mode == "normal"
        assert state.domains["session_access"].available is True
        assert state.domains["analyzer"].available is True
        assert state.domains["memory"].available is True
        assert state.domains["web"].available is True

    def test_to_dict(self):
        state = build_capability_state(session_ok=True, memory_ok=True)
        out = state.to_dict()
        assert "capability_state" in out
        cs = out["capability_state"]
        assert "generated_at_ms" in cs
        assert "overall_mode" in cs
        assert "domains" in cs
        assert isinstance(cs["domains"]["session_access"], dict)
        assert cs["domains"]["session_access"]["available"] is True

    def test_generated_at_ms_is_recent(self):
        before = int(time.time() * 1000)
        state = build_capability_state(session_ok=True)
        after = int(time.time() * 1000)
        assert before <= state.generated_at_ms <= after


# ── Query methods ───────────────────────────────────────────────────────

class TestCapabilityQueries:
    def test_can_use_measured_evaluation_true(self):
        state = build_capability_state(
            session_ok=True,
            analyzer_ok=True,
            analyzer_fresh=True,
        )
        assert state.can_use_measured_evaluation() is True

    def test_can_use_measured_evaluation_false_no_analyzer(self):
        state = build_capability_state(session_ok=True, analyzer_ok=False)
        assert state.can_use_measured_evaluation() is False

    def test_can_use_measured_evaluation_false_stale(self):
        state = build_capability_state(
            session_ok=True, analyzer_ok=True, analyzer_fresh=False,
        )
        # Stale analyzer: available=False, confidence=0.4 → below threshold
        assert state.can_use_measured_evaluation() is False

    def test_can_run_research_targeted_always_with_session(self):
        state = build_capability_state(session_ok=True)
        assert state.can_run_research("targeted") is True

    def test_can_run_research_targeted_with_memory_only(self):
        state = build_capability_state(memory_ok=True)
        assert state.can_run_research("targeted") is True

    def test_can_run_research_targeted_nothing_available(self):
        state = build_capability_state()
        assert state.can_run_research("targeted") is False

    def test_can_run_research_deep_needs_web(self):
        state = build_capability_state(session_ok=True, web_ok=False)
        assert state.can_run_research("deep") is False

    def test_can_run_research_deep_with_web(self):
        state = build_capability_state(session_ok=True, web_ok=True)
        assert state.can_run_research("deep") is True


# ── Builder combinations ────────────────────────────────────────────────

class TestBuildCapabilityState:
    def test_nothing_produces_read_only(self):
        state = build_capability_state()
        assert state.overall_mode == "read_only"

    def test_session_only_produces_measured_degraded(self):
        state = build_capability_state(session_ok=True)
        assert state.overall_mode == "measured_degraded"

    def test_session_plus_analyzer_not_fresh_produces_judgment_only(self):
        state = build_capability_state(
            session_ok=True, analyzer_ok=True, analyzer_fresh=False,
        )
        assert state.overall_mode == "judgment_only"

    def test_session_plus_fresh_analyzer_produces_normal(self):
        state = build_capability_state(
            session_ok=True, analyzer_ok=True, analyzer_fresh=True,
        )
        assert state.overall_mode == "normal"

    def test_analyzer_without_session_is_read_only(self):
        state = build_capability_state(
            session_ok=False, analyzer_ok=True, analyzer_fresh=True,
        )
        assert state.overall_mode == "read_only"

    def test_all_flags_on(self):
        state = build_capability_state(
            session_ok=True,
            analyzer_ok=True,
            analyzer_fresh=True,
            memory_ok=True,
            web_ok=True,
            flucoma_ok=True,
        )
        assert state.overall_mode == "normal"
        assert state.domains["research"].mode == "full"
        assert state.domains["research"].confidence == 1.0

    def test_research_targeted_only_without_web(self):
        state = build_capability_state(
            session_ok=True, memory_ok=True, web_ok=False,
        )
        assert state.domains["research"].mode == "targeted_only"
        assert state.domains["research"].available is True
        assert "web_unavailable" in state.domains["research"].reasons

    def test_research_unavailable_when_nothing(self):
        state = build_capability_state()
        assert state.domains["research"].mode == "unavailable"
        assert state.domains["research"].available is False
