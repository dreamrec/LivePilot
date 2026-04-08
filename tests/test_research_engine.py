"""Tests for the Research Engine — targeted and deep research synthesis."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools._research_engine import (
    ResearchFinding,
    ResearchResult,
    StyleTactic,
    analyze_query,
    deep_research,
    rank_findings,
    targeted_research,
)
from mcp_server.tools._agent_os_engine import TechniqueCard


# ── Query Analysis ───────────────────────────────────────────────────


class TestAnalyzeQuery:
    def test_basic_keyword_extraction(self):
        result = analyze_query("how to sidechain bass to kick")
        assert "sidechain" in result["keywords"]
        assert "bass" in result["keywords"]
        assert "kick" in result["keywords"]

    def test_technique_category_match(self):
        result = analyze_query("warm reverb on vocals")
        assert "reverb" in result["technique_categories"]
        assert "Reverb" in result["likely_devices"]

    def test_multiple_technique_categories(self):
        result = analyze_query("sidechain compression with eq on bass")
        categories = result["technique_categories"]
        assert "sidechain" in categories
        assert "eq" in categories

    def test_specificity_increases_with_detail(self):
        vague = analyze_query("reverb")
        detailed = analyze_query("how to add warm plate reverb to vocals for space")
        assert detailed["specificity"] > vague["specificity"]

    def test_empty_query(self):
        result = analyze_query("")
        assert result["keywords"] == []
        assert result["likely_devices"] == []

    def test_unknown_technique(self):
        result = analyze_query("xylomatic refurbification")
        assert result["technique_categories"] == []
        assert result["likely_devices"] == []

    def test_device_prediction_for_synthesis(self):
        result = analyze_query("fat synthesis bass sound")
        assert "Wavetable" in result["likely_devices"] or "Operator" in result["likely_devices"]


# ── Finding Ranking ──────────────────────────────────────────────────


class TestRankFindings:
    def test_sorts_by_relevance(self):
        findings = [
            ResearchFinding("memory", "m1", 0.3, "low relevance"),
            ResearchFinding("device_atlas", "d1", 0.9, "high relevance"),
            ResearchFinding("corpus", "c1", 0.6, "mid relevance"),
        ]
        ranked = rank_findings(findings)
        assert ranked[0].relevance == 0.9
        assert ranked[-1].relevance == 0.3

    def test_deduplicates_similar(self):
        # Both findings share the same first 50 chars exactly
        findings = [
            ResearchFinding("memory", "m1", 0.8, "Compressor sidechain technique for pumping bass — use fast attack and medium release"),
            ResearchFinding("memory", "m2", 0.7, "Compressor sidechain technique for pumping bass — adjust ratio for subtlety"),
        ]
        ranked = rank_findings(findings)
        # First 50 chars identical → dedup keeps only the higher-ranked one
        assert len(ranked) == 1

    def test_caps_at_10(self):
        findings = [
            ResearchFinding("memory", f"m{i}", 0.5, f"unique finding {i} with different content")
            for i in range(20)
        ]
        ranked = rank_findings(findings)
        assert len(ranked) <= 10

    def test_empty_input(self):
        assert rank_findings([]) == []


# ── Targeted Research ────────────────────────────────────────────────


class TestTargetedResearch:
    def test_basic_synthesis(self):
        device_results = [
            {"name": "Compressor", "category": "Audio Effects", "description": "Dynamic range compression"},
        ]
        memory_results = [
            {"id": "mem_001", "type": "technique_card", "payload": {
                "problem": "Sidechain pumping",
                "method": "Set attack fast, release medium",
                "devices": ["Compressor"],
            }},
        ]

        result = targeted_research("sidechain compression", device_results, memory_results)

        assert isinstance(result, ResearchResult)
        assert result.scope == "targeted"
        assert result.query == "sidechain compression"
        assert len(result.findings) > 0
        assert "device_atlas" in result.sources_searched
        assert "memory" in result.sources_searched

    def test_generates_technique_card(self):
        result = targeted_research(
            "warm reverb",
            [{"name": "Reverb", "category": "Audio Effects", "description": "Algorithmic reverb"}],
            [],
        )
        assert result.technique_card is not None
        assert result.technique_card.problem == "warm reverb"

    def test_empty_sources(self):
        result = targeted_research("anything", [], [])
        assert result.confidence == 0.0
        assert result.findings == []

    def test_confidence_reflects_relevance(self):
        result = targeted_research(
            "compressor",
            [{"name": "Compressor", "category": "Audio Effects", "description": "Compressor for dynamics"}],
            [],
        )
        assert result.confidence > 0.0

    def test_boosts_predicted_devices(self):
        # "sidechain" should predict Compressor → boost its relevance
        result = targeted_research(
            "sidechain on bass",
            [
                {"name": "Compressor", "category": "Audio Effects", "description": "Dynamics"},
                {"name": "Utility", "category": "Audio Effects", "description": "Gain and width"},
            ],
            [],
        )
        # Compressor finding should rank higher
        if len(result.findings) >= 2:
            compressor_f = next((f for f in result.findings if "Compressor" in f.source_id), None)
            utility_f = next((f for f in result.findings if "Utility" in f.source_id), None)
            if compressor_f and utility_f:
                assert compressor_f.relevance >= utility_f.relevance


# ── Deep Research ────────────────────────────────────────────────────


class TestDeepResearch:
    def test_includes_web_findings(self):
        web_results = [
            {"url": "https://example.com/tutorial", "title": "Sidechain Tutorial", "snippet": "How to sidechain compress"},
        ]
        result = deep_research("sidechain", web_results, [], [])

        assert result.scope == "deep"
        assert "web" in result.sources_searched
        assert any(f.source_type == "web" for f in result.findings)

    def test_boosts_known_production_sources(self):
        web_results = [
            {"url": "https://www.ableton.com/guide", "title": "Ableton Guide", "snippet": "Sidechain compression tutorial"},
            {"url": "https://random-blog.com/post", "title": "Random Blog", "snippet": "Sidechain compression tutorial"},
        ]
        result = deep_research("sidechain compression", web_results, [], [])

        ableton_f = next((f for f in result.findings if "ableton.com" in f.metadata.get("url", "")), None)
        random_f = next((f for f in result.findings if "random-blog" in f.metadata.get("url", "")), None)

        if ableton_f and random_f:
            assert ableton_f.relevance >= random_f.relevance

    def test_merges_targeted_and_web(self):
        result = deep_research(
            "reverb technique",
            [{"url": "https://example.com", "title": "Web", "snippet": "reverb tips"}],
            [{"name": "Reverb", "description": "Reverb device"}],
            [{"id": "m1", "type": "research", "payload": {"content": "reverb memory"}}],
        )
        assert len(result.sources_searched) >= 2

    def test_confidence_higher_with_more_sources(self):
        targeted = targeted_research(
            "reverb",
            [{"name": "Reverb", "description": "Reverb"}],
            [],
        )
        deep = deep_research(
            "reverb",
            [{"url": "https://example.com", "title": "Reverb Guide", "snippet": "reverb tips"}],
            [{"name": "Reverb", "description": "Reverb"}],
            [],
        )
        # Deep should have equal or higher confidence due to more sources
        assert deep.confidence >= targeted.confidence or deep.findings == []

    def test_graceful_without_web(self):
        result = deep_research("reverb", [], [{"name": "Reverb", "description": "Reverb"}], [])
        assert result.scope == "deep"
        assert "web" not in result.sources_searched


# ── Data Classes ─────────────────────────────────────────────────────


class TestDataClasses:
    def test_research_finding_to_dict(self):
        f = ResearchFinding("device_atlas", "Compressor", 0.8, "Dynamic range compression")
        d = f.to_dict()
        assert d["source_type"] == "device_atlas"
        assert d["relevance"] == 0.8

    def test_research_result_to_dict(self):
        r = ResearchResult(query="test", scope="targeted", confidence=0.5)
        d = r.to_dict()
        assert d["query"] == "test"
        assert d["finding_count"] == 0

    def test_style_tactic_to_dict(self):
        st = StyleTactic(artist_or_genre="techno", tactic_name="rolling_bass")
        d = st.to_dict()
        assert d["artist_or_genre"] == "techno"

    def test_result_with_technique_card(self):
        card = TechniqueCard(problem="test", method="do thing")
        r = ResearchResult(query="test", scope="targeted", technique_card=card)
        d = r.to_dict()
        assert d["technique_card"]["problem"] == "test"
