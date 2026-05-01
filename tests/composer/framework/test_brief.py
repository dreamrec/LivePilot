"""Tests for Brief dataclass round-trip + subclass-specific fields."""

import pytest
from mcp_server.composer.framework.brief import (
    Brief, FastBrief, FullBrief, DevelopBrief,
)


def test_brief_round_trip():
    """Base Brief → to_dict → from_dict produces equal Brief."""
    original = Brief(
        mode="fast", tempo=128.0, key="Am",
        intent={"genre": "techno"}, knowledge={},
    )
    serialized = original.to_dict()
    restored = Brief.from_dict(serialized)
    assert restored == original


def test_fast_brief_carries_subclass_fields():
    """FastBrief round-trips with instruments_by_role + scale_pitches."""
    original = FastBrief(
        mode="fast", tempo=128.0, key="Am",
        intent={"genre": "techno"}, knowledge={},
        instruments_by_role={"bass": ["op1", "op2"]},
        scale_pitches=[57, 60, 64, 69],
    )
    restored = FastBrief.from_dict(original.to_dict())
    assert restored == original
    assert restored.instruments_by_role == {"bass": ["op1", "op2"]}
    assert restored.scale_pitches == [57, 60, 64, 69]


def test_full_brief_no_form_fields():
    """FullBrief MUST NOT have section_sequence / bar_counts / form_template."""
    fields_dict = FullBrief.__dataclass_fields__
    BANNED = {"section_sequence", "bar_counts", "form_template", "section_to_variant"}
    leaks = set(fields_dict.keys()) & BANNED
    assert not leaks, f"FullBrief leaked banned form-template field(s): {leaks}"


def test_full_brief_carries_research_and_design_targets():
    original = FullBrief(
        mode="full", tempo=130.0, key="Cm",
        intent={"genre": "minimal"}, knowledge={},
        research_hooks=["microhouse"],
        design_targets="develop into full track",
    )
    restored = FullBrief.from_dict(original.to_dict())
    assert restored == original


def test_develop_brief_carries_seed_state():
    original = DevelopBrief(
        mode="develop", tempo=122.0, key="Am",
        intent={}, knowledge={},
        seed_state={"clip_length": 4.0, "tracks": []},
        identity_preservation_directive="preserve all existing notes and samples",
    )
    restored = DevelopBrief.from_dict(original.to_dict())
    assert restored == original
    assert restored.seed_state["clip_length"] == 4.0


def test_from_dict_filters_unknown_keys():
    """Forward-compat: extra keys in serialized data don't crash from_dict."""
    data = {
        "mode": "fast", "tempo": 120.0, "key": None,
        "intent": {}, "knowledge": {},
        "instruments_by_role": {}, "scale_pitches": [],
        "future_field_we_dont_know_about": "should be ignored",
    }
    restored = FastBrief.from_dict(data)
    assert restored.mode == "fast"


def test_brief_subclasses_are_frozen():
    """Briefs are immutable — assigning fields after construction raises."""
    b = FastBrief(mode="fast", tempo=120.0, key="Am", intent={}, knowledge={})
    with pytest.raises(Exception):  # FrozenInstanceError
        b.tempo = 130.0  # type: ignore[misc]
