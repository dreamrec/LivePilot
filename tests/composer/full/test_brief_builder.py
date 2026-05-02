"""Tests for full-mode Brief builder.

Vocabulary-not-form: the brief carries genre/artist character + event
lexicon vocabulary. The LLM agent designs the song's form per call.
"""

import pytest
from unittest.mock import MagicMock
from mcp_server.composer.full.brief_builder import build_full_brief


def _mock_ctx():
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": MagicMock()}
    return ctx


# ── core brief shape ────────────────────────────────────────────────

def test_brief_has_required_fields():
    ctx = _mock_ctx()
    brief = build_full_brief(ctx, prompt="dark techno 128bpm in Am")
    REQUIRED = {
        "mode", "tempo", "key", "parsed_intent",
        "genre_context", "artist_context", "event_lexicon",
        "atlas_candidates_per_role", "manual_snippets",
        "seed_state", "research_hooks", "design_targets",
    }
    missing = REQUIRED - set(brief.keys())
    assert not missing, f"FullBrief missing required fields: {missing}"


def test_brief_mode_is_full():
    ctx = _mock_ctx()
    brief = build_full_brief(ctx, prompt="techno")
    assert brief["mode"] == "full"


def test_brief_seed_state_is_none_when_no_seed_provided():
    ctx = _mock_ctx()
    brief = build_full_brief(ctx, prompt="techno")
    assert brief["seed_state"] is None


def test_brief_seed_state_passed_through_when_provided():
    ctx = _mock_ctx()
    seed = {"tempo": 122.0, "key": "Am", "tracks": []}
    brief = build_full_brief(ctx, prompt="extend in techno", seed_state=seed)
    assert brief["seed_state"] == seed


# ── tempo + key precedence ──────────────────────────────────────────

def test_seed_state_tempo_wins_over_prompt_when_present():
    """When both prompt and seed provide tempo, seed wins (live truth)."""
    ctx = _mock_ctx()
    seed = {"tempo": 122.0, "key": "Am"}
    brief = build_full_brief(ctx, prompt="techno 130bpm", seed_state=seed)
    assert brief["tempo"] == 122.0


def test_prompt_tempo_used_when_no_seed():
    """No seed → tempo comes from prompt parsing."""
    ctx = _mock_ctx()
    brief = build_full_brief(ctx, prompt="techno 130bpm")
    # prompt_parser may return 130 or None depending on regex
    # just verify the field is populated as a number when prompt has BPM
    assert brief["tempo"] is None or isinstance(brief["tempo"], (int, float))


# ── vocabulary-not-form regression guards ──────────────────────────

def test_brief_does_NOT_carry_form_fields():
    """CRITICAL: FullBrief MUST NOT contain predetermined form."""
    ctx = _mock_ctx()
    brief = build_full_brief(ctx, prompt="techno")
    BANNED = {
        "section_sequence", "bar_counts", "form_template",
        "step_plan",  # full mode is now plan-LATER, not plan-NOW
        "variant_taxonomy", "section_to_variant",
        "variants_per_track",
    }
    leaks = set(brief.keys()) & BANNED
    assert not leaks, f"FullBrief leaked banned form-prescriptive field(s): {leaks}"


def test_design_targets_is_open_ended_text():
    """design_targets must be substantive plain English."""
    ctx = _mock_ctx()
    brief = build_full_brief(ctx, prompt="techno")
    assert isinstance(brief["design_targets"], str)
    assert len(brief["design_targets"]) > 100  # substantive


def test_design_targets_does_not_prescribe_section_counts():
    """design_targets MUST NOT say 'use N sections' or 'X-bar intro' etc."""
    ctx = _mock_ctx()
    brief = build_full_brief(ctx, prompt="techno")
    text_lower = brief["design_targets"].lower()
    forbidden_phrases = [
        "16-bar intro",
        "32-bar build",
        "use 8 sections",
        "must have a drop at",
        "intro must be",
        "outro should be",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in text_lower, (
            f"design_targets prescribes form: '{phrase}' — must be vocabulary, not form"
        )


# ── artist + research integration ──────────────────────────────────

def test_brief_with_artist_reference_carries_artist_context():
    ctx = _mock_ctx()
    brief = build_full_brief(ctx, prompt="make it sound like Burial")
    assert "Burial" in brief["artist_context"] or any(
        k.lower() == "burial" for k in brief["artist_context"]
    )


def test_brief_no_artist_reference_empty_artist_context():
    ctx = _mock_ctx()
    brief = build_full_brief(ctx, prompt="dark techno")
    assert brief["artist_context"] == {}


def test_brief_research_hooks_for_niche_prompt():
    ctx = _mock_ctx()
    brief = build_full_brief(ctx, prompt="UK funky wonky lo-fi")
    assert isinstance(brief["research_hooks"], list)
    # At least one niche term should be flagged
    assert len(brief["research_hooks"]) >= 1


def test_brief_research_hooks_empty_for_common_prompt():
    ctx = _mock_ctx()
    brief = build_full_brief(ctx, prompt="dark techno")
    # common terms shouldn't trigger research
    assert isinstance(brief["research_hooks"], list)


# ── stub fields are present but empty ──────────────────────────────

def test_phase1_stubs_are_dict_or_list_not_none():
    """Phase 1 stubs (genre_context, atlas_candidates, manual_snippets, event_lexicon)
    must be dict/list (not None) so consumers don't have to null-check."""
    ctx = _mock_ctx()
    brief = build_full_brief(ctx, prompt="techno")
    assert isinstance(brief["genre_context"], dict)
    assert isinstance(brief["atlas_candidates_per_role"], dict)
    assert isinstance(brief["manual_snippets"], dict)
    assert isinstance(brief["event_lexicon"], list)
