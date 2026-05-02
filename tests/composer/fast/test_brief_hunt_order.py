"""Tests for the v1.24 brief hunt-order fix.

Brief MUST hunt sounds/ first, then drums/samples for drum roles, then
Tier-B audible-default synths from atlas. NEVER return Tier-C bare
instrument URIs.
"""

import pytest
from unittest.mock import MagicMock, patch
from mcp_server.composer.fast.tier_classification import (
    TIER_CLASSIFICATION,
    classify_instrument,
    ROLE_SEARCH_TERMS,
)


# ── tier classification table ──────────────────────────────────────

def test_tier_b_synths_classified_correctly():
    for synth in ["Operator", "Wavetable", "Drift", "Analog", "Bass", "Electric", "Tension", "Collision", "Meld"]:
        assert classify_instrument(synth) == "B_audible_default", (
            f"{synth} must be classified as Tier-B (audible default)"
        )


def test_tier_c_containers_classified_correctly():
    for container in ["Drum Sampler", "Drum Rack", "Simpler", "Sampler", "Impulse",
                      "Emit", "Vector FM", "Vector Grain", "Granulator III"]:
        assert classify_instrument(container) == "C_needs_preset", (
            f"{container} must be classified as Tier-C (needs preset)"
        )


def test_unknown_synth_returns_none():
    """An instrument we haven't classified returns None — caller decides
    whether to include or skip."""
    assert classify_instrument("SomeNewSynthFromFuture") is None


def test_tier_classification_dict_consistency():
    """TIER_CLASSIFICATION must agree with classify_instrument for all entries."""
    for name, tier in TIER_CLASSIFICATION.items():
        assert classify_instrument(name) == tier, (
            f"TIER_CLASSIFICATION[{name!r}] = {tier!r} disagrees with classify_instrument"
        )


# ── role search terms ──────────────────────────────────────────────

def test_role_search_terms_present():
    """Every common role has a search term mapping for sounds/."""
    for role in ["kick", "hat", "snare", "bass", "pad", "lead", "perc", "clap"]:
        assert role in ROLE_SEARCH_TERMS, f"Role '{role}' missing from ROLE_SEARCH_TERMS"


def test_drum_roles_have_drums_term():
    """Drum roles must have a drums_term (for drums/ search step)."""
    for role in ["kick", "snare", "hat", "perc", "clap"]:
        terms = ROLE_SEARCH_TERMS.get(role, {})
        assert terms.get("drums_term") is not None, (
            f"Drum role '{role}' missing drums_term in ROLE_SEARCH_TERMS"
        )


def test_melodic_roles_have_sounds_term_only():
    """Melodic roles should have sounds_term but no drums_term."""
    for role in ["bass", "lead", "pad", "atmos"]:
        terms = ROLE_SEARCH_TERMS.get(role, {})
        assert terms.get("sounds_term") is not None, (
            f"Melodic role '{role}' missing sounds_term in ROLE_SEARCH_TERMS"
        )
        assert terms.get("drums_term") is None, (
            f"Melodic role '{role}' should not have drums_term"
        )


# ── hunt-order regression guards ───────────────────────────────────

BANNED_TIER_C_BARE_URIS = frozenset({
    "query:Synths#Drum%20Sampler",
    "query:Synths#Drum%20Rack",
    "query:Synths#Simpler",
    "query:Synths#Sampler",
    "query:Synths#Impulse",
    "query:Synths#Emit",
    "query:Synths#Vector%20FM",
    "query:Synths#Vector%20Grain",
    "query:Synths#Granulator%20III",
})


def test_brief_never_returns_tier_c_bare_instrument():
    """Regression guard: build_creative_brief MUST NOT return a Tier-C bare
    instrument URI in instruments_by_role for any role."""
    from mcp_server.composer.fast.brief_builder import build_creative_brief
    from mcp_server.composer.prompt_parser import CompositionIntent

    mock_atlas = MagicMock()
    mock_atlas.search.return_value = []
    # _by_tag returns Tier-C bare URIs — the old bug path
    mock_atlas._by_tag = {
        "kick": [
            {"uri": "query:Synths#Drum%20Sampler", "name": "Drum Sampler"},
        ],
        "pad": [
            {"uri": "query:Synths#Emit", "name": "Emit"},
            {"uri": "query:Synths#Granulator%20III", "name": "Granulator III"},
        ],
    }

    intent = CompositionIntent(
        genre="techno",
        tempo=128,
        key="Am",
    )

    brief = build_creative_brief(
        intent=intent,
        atlas=mock_atlas,
        fresh_project_state={},
        bars=4,
    )

    instruments_by_role = brief.get("instruments_by_role", {})
    for role, candidates in instruments_by_role.items():
        for c in candidates:
            uri = c.get("uri", "")
            assert uri not in BANNED_TIER_C_BARE_URIS, (
                f"Brief returned Tier-C bare URI '{uri}' for role '{role}' — "
                f"this is the v1.24 protocol fix violation"
            )


def test_brief_candidates_carry_tier_field():
    """Each candidate in instruments_by_role[role] must carry a 'tier' field."""
    from mcp_server.composer.fast.brief_builder import build_creative_brief
    from mcp_server.composer.prompt_parser import CompositionIntent

    mock_atlas = MagicMock()
    # Return a Tier-B synth from atlas.search
    mock_atlas.search.return_value = [
        {"device": {"uri": "query:Synths#Operator", "name": "Operator", "character_tags": []}, "score": 10},
    ]
    mock_atlas._by_tag = {}

    intent = CompositionIntent(
        genre="techno",
        tempo=128,
        key="Am",
    )

    brief = build_creative_brief(
        intent=intent,
        atlas=mock_atlas,
        fresh_project_state={},
        bars=4,
    )

    for role, candidates in brief.get("instruments_by_role", {}).items():
        for c in candidates:
            assert "tier" in c, f"Candidate for {role} missing 'tier': {c}"
            assert c["tier"] in ("A_sample_ready", "B_audible_default"), (
                f"Tier {c['tier']!r} not allowed in brief candidates for role {role}"
            )
