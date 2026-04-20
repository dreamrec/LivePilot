"""Tests for composer winner escalation (PR3/5).

Covers:
  - propose_composer_branches now carries intent + strategy in producer_payload
  - escalate_composer_branch rehydrates intent and runs ComposerEngine.compose
  - Graceful fallback when intent missing (pre-v2 branches)
  - Graceful fallback when compose() returns zero layers
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from mcp_server.composer import propose_composer_branches, escalate_composer_branch
from mcp_server.composer.engine import ComposerEngine, CompositionResult
from mcp_server.composer.prompt_parser import CompositionIntent
from mcp_server.composer.layer_planner import LayerSpec


# ── Emit-time: producer_payload shape ────────────────────────────────────


class TestEmitTimePayload:

    def test_composer_seeds_carry_intent_in_payload(self):
        pairs = propose_composer_branches(
            "techno at 128 bpm, energetic",
            kernel={"freshness": 0.5},
        )
        assert len(pairs) >= 1
        for seed, _plan in pairs:
            p = seed.producer_payload
            assert "strategy" in p
            assert "intent" in p
            assert "request_text" in p
            assert "reason" in p

    def test_intent_dict_is_reconstructible(self):
        pairs = propose_composer_branches(
            "ambient track at 80 bpm",
            kernel={"freshness": 0.2},
        )
        seed, _ = pairs[0]
        intent_dict = seed.producer_payload["intent"]
        # Must have all CompositionIntent fields — required for rehydration.
        for key in ("genre", "tempo", "energy", "duration_bars"):
            assert key in intent_dict

    def test_strategy_name_in_payload_matches_hypothesis(self):
        pairs = propose_composer_branches(
            "techno at 128",
            kernel={"freshness": 0.85},
            count=3,
        )
        for seed, _plan in pairs:
            strategy = seed.producer_payload["strategy"]
            assert strategy in ("canonical", "energy_shift", "layer_contrast")
            assert strategy in seed.hypothesis.lower()


# ── Escalation: happy path ───────────────────────────────────────────────


class _StubCompositionResult:
    """Minimal stub — shape-compatible with CompositionResult."""
    def __init__(self, plan, layers, warnings=None, resolved_samples=None, credits=0):
        self.plan = plan
        self.layers = layers
        self.warnings = warnings or []
        self.resolved_samples = resolved_samples or {}
        self.credits_estimated = credits


class TestEscalateHappyPath:

    @pytest.mark.asyncio
    async def test_escalation_runs_compose_with_rehydrated_intent(self, monkeypatch):
        # Intercept ComposerEngine.compose so we don't need Splice / filesystem.
        captured = {}

        async def fake_compose(self, intent, **kwargs):
            captured["intent"] = intent
            captured["kwargs"] = kwargs
            return _StubCompositionResult(
                plan=[
                    {"tool": "set_tempo", "params": {"tempo": 128.0}},
                    {"tool": "create_midi_track", "params": {"name": "kick"}},
                    {"tool": "load_browser_item", "params": {
                        "track_index": 0, "uri": "fake://kick.wav"}},
                ],
                layers=[
                    LayerSpec(role="kick", search_query="kick"),
                    LayerSpec(role="bass", search_query="bass"),
                ],
                resolved_samples={"kick": "/path/kick.wav", "bass": "/path/bass.wav"},
                credits=2,
            )

        monkeypatch.setattr(ComposerEngine, "compose", fake_compose)

        payload = {
            "schema_version": 1,
            "strategy": "canonical",
            "intent": {
                "genre": "techno",
                "tempo": 128,
                "energy": 0.7,
                "duration_bars": 64,
                "descriptors": [],
                "explicit_elements": [],
            },
            "request_text": "build a techno track",
            "reason": "baseline",
        }
        result = await escalate_composer_branch(payload)

        assert result["ok"] is True
        assert result["step_count"] == 3
        assert result["layer_count"] == 2
        assert result["resolved_samples"] == {
            "kick": "/path/kick.wav", "bass": "/path/bass.wav",
        }
        # Rehydrated intent is the one compose() received.
        assert captured["intent"].genre == "techno"
        assert captured["intent"].tempo == 128


# ── Escalation: fallback paths ───────────────────────────────────────────


class TestEscalateFallbacks:

    @pytest.mark.asyncio
    async def test_missing_intent_returns_explicit_error(self):
        result = await escalate_composer_branch({"schema_version": 1})
        assert result["ok"] is False
        assert "intent" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_zero_layers_triggers_fallback(self, monkeypatch):
        async def fake_empty_compose(self, intent, **kwargs):
            return _StubCompositionResult(plan=[], layers=[])

        monkeypatch.setattr(ComposerEngine, "compose", fake_empty_compose)

        result = await escalate_composer_branch({
            "strategy": "canonical",
            "intent": {"genre": "techno", "tempo": 128, "energy": 0.7},
        })
        assert result["ok"] is False
        assert "zero executable layers" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_compose_exception_returns_error(self, monkeypatch):
        async def fake_failing_compose(self, intent, **kwargs):
            raise RuntimeError("splice timeout")

        monkeypatch.setattr(ComposerEngine, "compose", fake_failing_compose)

        result = await escalate_composer_branch({
            "strategy": "canonical",
            "intent": {"genre": "techno"},
        })
        assert result["ok"] is False
        assert "splice timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_unknown_intent_keys_are_ignored(self, monkeypatch):
        # Future payloads may add keys. The rehydration must ignore unknown
        # keys gracefully instead of crashing.
        async def fake_compose(self, intent, **kwargs):
            return _StubCompositionResult(
                plan=[{"tool": "set_tempo", "params": {"tempo": 120.0}}],
                layers=[LayerSpec(role="test", search_query="test")],
            )

        monkeypatch.setattr(ComposerEngine, "compose", fake_compose)

        result = await escalate_composer_branch({
            "schema_version": 99,  # future
            "intent": {
                "genre": "ambient",
                "tempo": 80,
                "this_is_a_future_key": "ignored",
                "another_future_key": [1, 2, 3],
            },
        })
        assert result["ok"] is True


# Pytest-asyncio needs mode='auto' OR per-test @pytest.mark.asyncio. Repo
# uses the marker-based approach; we declared it above.
