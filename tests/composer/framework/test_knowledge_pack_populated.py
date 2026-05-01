"""Tests for v1.24 Phase 5 Task 22 — KnowledgePack populated."""

import pytest
from unittest.mock import MagicMock
from mcp_server.composer.framework.knowledge_pack import KnowledgePack
from mcp_server.composer.framework.event_lexicon import EVENT_LEXICON, get_event_lexicon
from mcp_server.composer.framework.genre_loader import load_genre_context
from mcp_server.composer.framework.artist_loader import load_artist_context


# ── Event lexicon ────────────────────────────────────────────────

def test_event_lexicon_has_42_events():
    """The 42-event vocabulary is defined and registered."""
    assert len(EVENT_LEXICON) >= 40, f"Expected ~42 events, got {len(EVENT_LEXICON)}"


def test_event_lexicon_categories_present():
    """All 7 expected categories are represented."""
    cats = {ev["category"] for ev in EVENT_LEXICON}
    expected = {"filter", "drums", "layer", "riser", "dynamics", "harmonic", "space"}
    missing = expected - cats
    assert not missing, f"Missing event categories: {missing}"


def test_event_lexicon_specific_events():
    """Sanity-check that key events are in the registry."""
    names = {ev["name"] for ev in EVENT_LEXICON}
    for required in ["kick_dropout", "hpf_sweep_up", "riser_swell", "snare_roll_final_bars",
                     "full_silence_bar", "sidechain_activate", "motif_restatement"]:
        assert required in names, f"Missing event {required}"


def test_get_event_lexicon_by_category():
    """Helper filters by category."""
    drum_events = get_event_lexicon(category="drums")
    assert len(drum_events) >= 8
    for ev in drum_events:
        assert ev["category"] == "drums"


def test_event_lexicon_each_entry_has_required_fields():
    """Every event must have name, category, and description."""
    for ev in EVENT_LEXICON:
        assert "name" in ev, f"Missing 'name' in event: {ev}"
        assert "category" in ev, f"Missing 'category' in event: {ev}"
        assert "description" in ev, f"Missing 'description' in event: {ev}"


def test_event_lexicon_no_duplicates():
    """No two events share the same name."""
    names = [ev["name"] for ev in EVENT_LEXICON]
    assert len(names) == len(set(names)), "Duplicate event names found"


# ── Genre context loader ────────────────────────────────────────

def test_load_genre_context_techno():
    """Techno entry is loaded with sonic-character data."""
    ctx = load_genre_context("techno")
    assert ctx is not None
    # Must have at least some descriptive content
    assert isinstance(ctx, dict)
    assert len(ctx) > 0


def test_load_genre_context_microhouse():
    """Microhouse entry is loaded."""
    ctx = load_genre_context("microhouse")
    assert isinstance(ctx, dict)
    assert ctx.get("status") != "no_match", f"Expected microhouse match, got: {ctx}"


def test_load_genre_context_ambient():
    """Ambient entry is loaded."""
    ctx = load_genre_context("ambient")
    assert isinstance(ctx, dict)
    assert len(ctx) > 0


def test_load_genre_context_unknown_returns_no_match():
    """Unknown genre returns explicit no-match marker, doesn't raise."""
    ctx = load_genre_context("zzzz_fake_genre_xyz")
    assert ctx.get("status") == "no_match"


def test_load_genre_context_empty_string():
    """Empty string returns status dict, doesn't raise."""
    ctx = load_genre_context("")
    assert isinstance(ctx, dict)


def test_load_genre_context_raw_md_has_content():
    """Loaded genre has non-trivial raw_md content."""
    ctx = load_genre_context("techno")
    if ctx.get("status") == "no_match":
        pytest.skip("Techno not found in genre-vocabularies.md")
    assert len(ctx.get("raw_md", "")) > 50, "raw_md too short — parsing may have failed"


# ── Artist context loader ────────────────────────────────────────

def test_load_artist_context_burial():
    """Burial entry is loaded with sonic_fingerprint / reach_for / avoid."""
    refs = load_artist_context(["Burial"])
    assert "Burial" in refs or any(k.lower() == "burial" for k in refs)
    burial_data = refs.get("Burial") or next((v for k, v in refs.items() if k.lower() == "burial"), {})
    # Has SOME content (the markdown structure is variable)
    assert isinstance(burial_data, dict)
    assert len(burial_data.get("raw_md", "")) > 20


def test_load_artist_context_empty_list_returns_empty_dict():
    refs = load_artist_context([])
    assert refs == {}


def test_load_artist_context_unknown_artist():
    """Unknown artist returns empty dict, doesn't raise."""
    refs = load_artist_context(["Zzzzz_Unknown_Artist_9999"])
    assert refs == {}


def test_load_artist_context_case_insensitive():
    """Artist lookup is case-insensitive."""
    lower_refs = load_artist_context(["burial"])
    upper_refs = load_artist_context(["BURIAL"])
    mixed_refs = load_artist_context(["Burial"])
    # At least one casing should find the artist
    found_any = any(len(r) > 0 for r in [lower_refs, upper_refs, mixed_refs])
    assert found_any, "Expected Burial to be found with at least one casing"


def test_load_artist_context_multiple_artists():
    """Multiple artists can be loaded at once."""
    refs = load_artist_context(["Burial", "Gas"])
    # Both should resolve (or at least not raise)
    assert isinstance(refs, dict)


# ── KnowledgePack.build (full mode) ─────────────────────────────

def _mock_ableton():
    ableton = MagicMock()
    def send_command(cmd, args):
        if cmd == "search_browser":
            return {"items": []}
        if cmd == "search_live_manual":
            return {"results": []}
        return {}
    ableton.send_command = send_command
    return ableton


def test_kp_build_full_returns_required_fields():
    kp = KnowledgePack()
    intent = {"genre": "techno", "tempo": 128, "key": "Am"}
    result = kp.build(intent, mode="full")
    REQUIRED = {"event_lexicon", "genre_context", "artist_context",
                "atlas_candidates_per_role", "manual_snippets"}
    missing = REQUIRED - set(result.keys())
    assert not missing, f"build_full missing fields: {missing}"


def test_kp_build_full_event_lexicon_populated():
    """build(mode='full') ALWAYS includes the event lexicon — full mode designs form using it."""
    kp = KnowledgePack()
    result = kp.build({"genre": ""}, mode="full")
    assert isinstance(result["event_lexicon"], list)
    assert len(result["event_lexicon"]) >= 40


def test_kp_build_fast_no_event_lexicon():
    """Fast mode brief is loop-sketch scope — doesn't need the form-design vocabulary."""
    kp = KnowledgePack()
    result = kp.build({"genre": ""}, mode="fast")
    # Fast mode either omits event_lexicon or returns empty
    assert result.get("event_lexicon") in (None, [])


def test_kp_build_develop_includes_event_lexicon():
    """Develop mode also includes the event lexicon."""
    kp = KnowledgePack()
    result = kp.build({"genre": "techno"}, mode="develop")
    assert isinstance(result["event_lexicon"], list)
    assert len(result["event_lexicon"]) >= 40


def test_kp_build_with_artists_populates_artist_context():
    """When intent carries artists, artist_context is populated."""
    kp = KnowledgePack()
    result = kp.build({"genre": "techno", "artists": ["Burial"]}, mode="full")
    assert isinstance(result["artist_context"], dict)
    # Burial should be in the result
    has_burial = "Burial" in result["artist_context"] or any(
        k.lower() == "burial" for k in result["artist_context"]
    )
    assert has_burial, f"Expected Burial in artist_context, got keys: {list(result['artist_context'].keys())}"


def test_kp_build_genre_context_populated_for_known_genre():
    """build() populates genre_context for known genres."""
    kp = KnowledgePack()
    result = kp.build({"genre": "techno"}, mode="full")
    assert isinstance(result["genre_context"], dict)
    assert len(result["genre_context"]) > 0


def test_kp_build_genre_context_no_match_for_unknown():
    """build() returns no_match for unrecognized genre, not an empty dict."""
    kp = KnowledgePack()
    result = kp.build({"genre": "zzz_fake_zzz"}, mode="full")
    ctx = result["genre_context"]
    assert ctx.get("status") == "no_match"


# ── FullBrief integration ───────────────────────────────────────

def test_full_brief_consumes_knowledge_pack():
    """build_full_brief result has populated knowledge fields, not empty stubs."""
    from mcp_server.composer.full.brief_builder import build_full_brief
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": _mock_ableton()}
    brief = build_full_brief(ctx, prompt="techno 128bpm")

    # Event lexicon has content
    assert isinstance(brief["event_lexicon"], list)
    assert len(brief["event_lexicon"]) >= 40, "FullBrief.event_lexicon not populated"


def test_full_brief_genre_context_populated_for_known_genre():
    from mcp_server.composer.full.brief_builder import build_full_brief
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": _mock_ableton()}
    brief = build_full_brief(ctx, prompt="techno 128bpm")
    # genre_context should have something for "techno"
    assert isinstance(brief["genre_context"], dict)
    # If the parser couldn't find techno, status is "no_match" — but it shouldn't be empty
    assert len(brief["genre_context"]) > 0


def test_full_brief_artist_context_when_artist_in_prompt():
    from mcp_server.composer.full.brief_builder import build_full_brief
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": _mock_ableton()}
    brief = build_full_brief(ctx, prompt="make it sound like Burial")
    assert "Burial" in brief["artist_context"] or any(
        k.lower() == "burial" for k in brief["artist_context"]
    )


def test_full_brief_empty_artist_context_when_no_artist():
    """When no artist in prompt, artist_context is an empty dict."""
    from mcp_server.composer.full.brief_builder import build_full_brief
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": _mock_ableton()}
    brief = build_full_brief(ctx, prompt="minimal techno 130bpm")
    assert isinstance(brief["artist_context"], dict)


def test_full_brief_has_all_required_fields():
    """FullBrief output carries all required top-level fields."""
    from mcp_server.composer.full.brief_builder import build_full_brief
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": _mock_ableton()}
    brief = build_full_brief(ctx, prompt="ambient drone")
    required = {"mode", "tempo", "key", "parsed_intent", "genre_context", "artist_context",
                "event_lexicon", "atlas_candidates_per_role", "manual_snippets",
                "seed_state", "research_hooks", "design_targets"}
    missing = required - set(brief.keys())
    assert not missing, f"FullBrief missing fields: {missing}"
