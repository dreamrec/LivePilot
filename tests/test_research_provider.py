"""Tests for the Research Provider Router — provider ladder, routing, feedback."""

from __future__ import annotations

import pytest

from mcp_server.tools._research_provider import (
    PROVIDER_LADDER,
    ResearchFeedbackStore,
    ResearchOutcomeFeedback,
    ResearchProvider,
    get_available_providers,
    record_research_feedback,
    route_research,
)


# ── ResearchProvider ────────────────────────────────────────────────


class TestResearchProvider:
    def test_creates(self):
        p = ResearchProvider("session_evidence", True, 1, "free")
        assert p.name == "session_evidence"
        assert p.available is True
        assert p.priority == 1
        assert p.cost == "free"

    def test_to_dict(self):
        p = ResearchProvider("web", False, 6, "high")
        d = p.to_dict()
        assert d["name"] == "web"
        assert d["available"] is False
        assert d["priority"] == 6
        assert d["cost"] == "high"


# ── PROVIDER_LADDER ─────────────────────────────────────────────────


class TestProviderLadder:
    def test_has_six_providers(self):
        assert len(PROVIDER_LADDER) == 6

    def test_priorities_are_ascending(self):
        priorities = [p.priority for p in PROVIDER_LADDER]
        assert priorities == sorted(priorities)

    def test_first_three_are_free(self):
        for p in PROVIDER_LADDER[:3]:
            assert p.cost == "free"


# ── get_available_providers ─────────────────────────────────────────


class TestGetAvailableProviders:
    def test_returns_all_providers(self):
        result = get_available_providers()
        assert len(result) == 6

    def test_default_availability_matches_ladder(self):
        result = get_available_providers()
        for p, ladder_p in zip(result, PROVIDER_LADDER):
            assert p.available == ladder_p.available

    def test_capability_overrides(self):
        result = get_available_providers({"web": True, "session_evidence": False})
        by_name = {p.name: p for p in result}
        assert by_name["web"].available is True
        assert by_name["session_evidence"].available is False


# ── route_research ──────────────────────────────────────────────────


class TestRouteResearch:
    def test_targeted_mode_uses_free_providers(self):
        result = route_research("sidechain bass", "targeted")
        assert result["mode"] == "targeted"
        names = [p["name"] for p in result["providers_to_query"]]
        assert "session_evidence" in names
        assert "local_docs" in names
        assert "memory" in names
        # Web should be skipped
        skipped_names = [p["name"] for p in result["skipped"]]
        assert "web" in skipped_names

    def test_deep_mode_includes_all_available(self):
        providers = get_available_providers({"web": True, "user_references": True})
        result = route_research("warm reverb", "deep", providers)
        names = [p["name"] for p in result["providers_to_query"]]
        assert "web" in names
        assert "session_evidence" in names

    def test_background_mining_is_minimal(self):
        result = route_research("general patterns", "background_mining")
        names = [p["name"] for p in result["providers_to_query"]]
        assert set(names) == {"session_evidence", "memory"}

    def test_invalid_mode_returns_error(self):
        result = route_research("test", "invalid_mode")
        assert "error" in result

    def test_unavailable_providers_skipped(self):
        result = route_research("test", "deep")
        skipped_names = [p["name"] for p in result["skipped"]]
        # web, user_references, structured_connectors are unavailable by default
        assert "web" in skipped_names

    def test_providers_sorted_by_priority(self):
        result = route_research("test", "targeted")
        priorities = [p["priority"] for p in result["providers_to_query"]]
        assert priorities == sorted(priorities)


# ── ResearchOutcomeFeedback ─────────────────────────────────────────


class TestResearchOutcomeFeedback:
    def test_creates(self):
        f = ResearchOutcomeFeedback(
            research_id="r_001",
            technique_card_id="tc_001",
            applied=True,
            move_kept=True,
            score=0.8,
        )
        assert f.research_id == "r_001"
        assert f.applied is True

    def test_to_dict(self):
        f = ResearchOutcomeFeedback("r_002", "tc_002", False, False, 0.3)
        d = f.to_dict()
        assert d["research_id"] == "r_002"
        assert d["applied"] is False
        assert d["score"] == 0.3


# ── ResearchFeedbackStore ──────────────────────────────────────────


class TestResearchFeedbackStore:
    def test_record_returns_summary(self):
        store = ResearchFeedbackStore()
        fb = ResearchOutcomeFeedback("r_001", "tc_001", True, True, 0.9)
        result = store.record(fb)
        assert result["total_feedback"] == 1
        assert "effectiveness" in result

    def test_effectiveness_rates(self):
        store = ResearchFeedbackStore()
        store.record(ResearchOutcomeFeedback("r_001", "tc_001", True, True, 0.9))
        store.record(ResearchOutcomeFeedback("r_002", "tc_002", True, False, 0.4))
        store.record(ResearchOutcomeFeedback("r_003", "tc_003", False, False, 0.2))
        eff = store.get_effectiveness()
        assert eff["count"] == 3
        assert eff["applied_rate"] == pytest.approx(2 / 3, abs=0.01)
        assert eff["kept_rate"] == pytest.approx(1 / 3, abs=0.01)
        assert eff["avg_score"] == pytest.approx(0.5, abs=0.01)

    def test_empty_store_effectiveness(self):
        store = ResearchFeedbackStore()
        eff = store.get_effectiveness()
        assert eff["count"] == 0
        assert eff["applied_rate"] == 0.0


# ── record_research_feedback (standalone) ───────────────────────────


class TestRecordResearchFeedback:
    def test_returns_feedback_and_timestamp(self):
        fb = ResearchOutcomeFeedback("r_001", "tc_001", True, True, 0.8)
        result = record_research_feedback(fb)
        assert result["feedback"]["research_id"] == "r_001"
        assert "timestamp_ms" in result
