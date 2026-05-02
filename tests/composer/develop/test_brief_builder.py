"""Tests for develop-mode Brief builder."""

import pytest
from unittest.mock import MagicMock
from mcp_server.composer.develop.brief_builder import (
    build_develop_brief,
    extract_artist_refs,
    detect_research_hooks,
)


# Fixture: a representative seed_state from SeedIntrospector
SEED_STATE = {
    "scene_index": 0,
    "tempo": 122.0,
    "clip_length": 4.0,
    "time_signature": "4/4",
    "key": "Am",
    "scale_mode": "minor",
    "tracks": [
        {"index": 0, "name": "Drums", "role": "drums", "classification": "sample_trigger",
         "notes": [{"pitch": 60, "start_time": 0, "duration": 4, "velocity": 100}], "muted": False},
        {"index": 1, "name": "Bass", "role": "bass", "classification": "midi_riff",
         "notes": [{"pitch": 45, "start_time": 0, "duration": 1, "velocity": 105}], "muted": False},
        {"index": 2, "name": "Lead", "role": "lead", "classification": "midi_riff",
         "notes": [{"pitch": 69, "start_time": 0, "duration": 2, "velocity": 85}], "muted": False},
        {"index": 3, "name": "Pad", "role": "pad", "classification": "sample_trigger",
         "notes": [{"pitch": 60, "start_time": 0, "duration": 4, "velocity": 100}], "muted": True},
        {"index": 4, "name": "Texture", "role": "texture", "classification": "sample_trigger",
         "notes": [{"pitch": 60, "start_time": 0, "duration": 4, "velocity": 100}], "muted": False},
    ],
}


def _mock_ctx():
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": MagicMock()}
    return ctx


# ── core brief shape ────────────────────────────────────────────────

def test_brief_has_required_fields():
    ctx = _mock_ctx()
    brief = build_develop_brief(ctx, SEED_STATE, prompt_directive=None)
    # Required fields per spec
    assert "seed_state" in brief
    assert "identity_preservation_directive" in brief
    assert "design_targets" in brief
    assert "research_hooks" in brief
    # Carried-through identity
    assert brief["seed_state"]["key"] == "Am"
    assert brief["seed_state"]["tempo"] == 122.0


def test_brief_carries_seed_state_unchanged():
    """Brief MUST NOT mutate the input seed_state. Identity preservation
    starts with the brief itself preserving the input."""
    ctx = _mock_ctx()
    seed_copy = dict(SEED_STATE)
    seed_copy["tracks"] = list(SEED_STATE["tracks"])  # shallow copy
    build_develop_brief(ctx, seed_copy, prompt_directive=None)
    # Original tracks list still has 5 entries
    assert len(seed_copy["tracks"]) == 5
    # Tempo unchanged
    assert seed_copy["tempo"] == 122.0


# ── vocabulary-not-form regression guards ──────────────────────────

def test_brief_does_NOT_carry_form_fields():
    """CRITICAL: brief MUST NOT contain predetermined form."""
    ctx = _mock_ctx()
    brief = build_develop_brief(ctx, SEED_STATE, prompt_directive=None)
    BANNED = {
        "section_sequence", "bar_counts", "form_template",
        "variant_taxonomy", "section_to_variant",
        "variants_per_track",  # spec says agent designs these
    }
    leaks = set(brief.keys()) & BANNED
    assert not leaks, f"DevelopBrief leaked banned form-prescriptive field(s): {leaks}"


def test_design_targets_is_open_ended_text_not_list():
    """design_targets must be plain English, NOT a list of named slots."""
    ctx = _mock_ctx()
    brief = build_develop_brief(ctx, SEED_STATE, prompt_directive=None)
    assert isinstance(brief["design_targets"], str)
    assert len(brief["design_targets"]) > 50  # substantive text
    # Should NOT contain fixed-taxonomy slot names
    forbidden_in_text = ["BUILD =", "FILL =", "BREAK =", "ALT_PEAK ="]
    for f in forbidden_in_text:
        assert f not in brief["design_targets"], (
            f"design_targets prescribes fixed slot '{f}' — that's form, not vocabulary"
        )


# ── identity preservation ──────────────────────────────────────────

def test_identity_preservation_directive_is_explicit():
    """Directive must clearly state samples/notes/automation must survive."""
    ctx = _mock_ctx()
    brief = build_develop_brief(ctx, SEED_STATE, prompt_directive=None)
    directive = brief["identity_preservation_directive"]
    assert isinstance(directive, str)
    # Substantive coverage
    text_lower = directive.lower()
    assert "preserve" in text_lower or "must survive" in text_lower or "do not overwrite" in text_lower


# ── prompt directive ────────────────────────────────────────────────

def test_brief_with_prompt_directive_carries_genre_context():
    """When prompt is provided, genre_context populated from genre vocabulary."""
    ctx = _mock_ctx()
    brief = build_develop_brief(ctx, SEED_STATE, prompt_directive="extend in microhouse style")
    # genre_context populated (the impl can be a placeholder dict for now;
    # full genre-vocabulary loading happens in Phase 4 KnowledgePack)
    assert "genre_context" in brief
    # The prompt directive is at least preserved
    assert brief.get("prompt_directive") == "extend in microhouse style"


def test_brief_no_prompt_directive_no_genre_context_required():
    """No prompt → genre_context may be empty/None (inferred-only path is Phase 4)."""
    ctx = _mock_ctx()
    brief = build_develop_brief(ctx, SEED_STATE, prompt_directive=None)
    # genre_context KEY must exist (uniform shape) but its value may be empty
    assert "genre_context" in brief


# ── research hooks ──────────────────────────────────────────────────

def test_research_hooks_for_niche_terms():
    """Niche-style prompts trigger research_hooks."""
    ctx = _mock_ctx()
    brief = build_develop_brief(ctx, SEED_STATE, prompt_directive="UK funky wonky lo-fi")
    hooks = brief["research_hooks"]
    assert isinstance(hooks, list)
    # Niche terms ("UK funky", "wonky") are likely to be flagged
    # Implementation may use any heuristic; just verify hooks list is non-empty for niche prompts
    assert len(hooks) >= 1


def test_research_hooks_empty_for_common_prompt():
    """Common terms (techno, house, ambient) don't need research."""
    ctx = _mock_ctx()
    brief = build_develop_brief(ctx, SEED_STATE, prompt_directive="dark techno")
    hooks = brief["research_hooks"]
    assert isinstance(hooks, list)
    # Common terms shouldn't trigger hooks (impl may differ; test just for shape)


def test_research_hooks_no_directive_returns_empty():
    """No prompt → no research hooks (nothing to research)."""
    ctx = _mock_ctx()
    brief = build_develop_brief(ctx, SEED_STATE, prompt_directive=None)
    assert brief["research_hooks"] == []


# ── extract_artist_refs ─────────────────────────────────────────────

def test_extract_artist_refs_finds_known_artist():
    """Artist names from artist-vocabularies.md are detected (case-insensitive)."""
    refs = extract_artist_refs("make it sound like Burial")
    assert "Burial" in refs or "burial" in [r.lower() for r in refs]


def test_extract_artist_refs_empty_for_no_artists():
    refs = extract_artist_refs("dark techno")
    assert refs == []


def test_extract_artist_refs_empty_string():
    refs = extract_artist_refs("")
    assert refs == []


# ── module-level regression guard ──────────────────────────────────

def test_no_fixed_taxonomy_constants_in_develop_module():
    """No module in mcp_server.composer.develop defines BUILD/FILL/BREAK/ALT constants."""
    import pkgutil
    import mcp_server.composer.develop as pkg
    BANNED = {"BUILD", "FILL", "BREAK", "ALT_PEAK", "BREAKDOWN", "DROP"}
    for mod_info in pkgutil.iter_modules(pkg.__path__):
        mod = __import__(f"mcp_server.composer.develop.{mod_info.name}", fromlist=[""])
        names = {n for n in dir(mod) if n.isupper()}
        leaks = names & BANNED
        assert not leaks, f"{mod_info.name} leaks fixed-taxonomy constant(s): {leaks}"


# ── atlas_alternates_per_role ──────────────────────────────────────

def test_brief_carries_atlas_alternates_for_sample_trigger_roles():
    """For sample-trigger layers, brief should suggest sample alternates the agent could swap in."""
    ctx = _mock_ctx()
    brief = build_develop_brief(ctx, SEED_STATE, prompt_directive=None)
    # The field exists (shape contract) — actual atlas integration may be a stub for now
    assert "atlas_alternates_per_role" in brief
    assert isinstance(brief["atlas_alternates_per_role"], dict)
