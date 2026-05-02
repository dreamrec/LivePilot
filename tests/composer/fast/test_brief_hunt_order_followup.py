"""Tests for v1.24 Phase 4 Task 18a-followup — the proven-P0 §1 fix.

Brief MUST:
  1. Search sounds/ first for curated .adg/.adv presets (Tier-A)
  2. Search drums/ for raw samples on drum roles (Tier-A)
  3. Return bare melodic synths (Operator/Wavetable etc.) ONLY as fallback
     when sounds/ returns nothing for that role
  4. Always allow drum-specific synths (DS Kick etc.) bare for drum roles
  5. Filter excluded_uris so recently-loaded curated presets are not re-picked
  6. NEVER return Tier-C containers
"""

import pytest
from unittest.mock import MagicMock, call
from mcp_server.composer.fast.tier_classification import (
    is_drum_specific_synth,
    DRUM_SPECIFIC_SYNTHS,
    DRUM_ROLES,
    MELODIC_ROLES,
    TIER_A_CURATED_PRESET,
    TIER_A_DRUM_SAMPLE,
    TIER_B_DRUM_SYNTH,
    TIER_B_AUDIBLE_DEFAULT_VALUE,
    VALID_BRIEF_TIERS,
    CONTAINERS_NEEDING_PRESETS,
    MELODIC_AUDIBLE_DEFAULTS,
)
from mcp_server.composer.fast.brief_builder import get_role_candidates


# ── drum-specific synth classification ───────────────────────────────────────


def test_drum_specific_synths_classified():
    """DS Kick, DS Snare etc. are drum-specific — allowed bare for drum roles."""
    assert is_drum_specific_synth("DS Kick")
    assert is_drum_specific_synth("DS Snare")
    assert is_drum_specific_synth("DS Hi-Hat")
    assert is_drum_specific_synth("DS Clap")
    assert is_drum_specific_synth("DS Cymbal")
    assert is_drum_specific_synth("DS Tom")
    assert is_drum_specific_synth("DS Sampler")
    assert is_drum_specific_synth("DS Drum Bus")


def test_melodic_synths_NOT_drum_specific():
    """Operator, Wavetable etc. are NOT drum-specific."""
    for name in ["Operator", "Wavetable", "Drift", "Bass", "Electric", "Tree Tone"]:
        assert not is_drum_specific_synth(name), (
            f"{name} should NOT be a drum-specific synth"
        )


def test_containers_not_drum_specific():
    """Tier-C containers are NOT drum-specific synths."""
    for name in ["Drum Sampler", "Simpler", "Sampler", "Emit", "Granulator III"]:
        assert not is_drum_specific_synth(name)


# ── role sets ─────────────────────────────────────────────────────────────────


def test_drum_roles_set():
    """Kick/snare/hat/perc/clap are DRUM_ROLES."""
    for role in ("kick", "snare", "hat", "perc", "clap"):
        assert role in DRUM_ROLES


def test_melodic_roles_set():
    """Bass/lead/pad/atmos/vox/fx/texture are MELODIC_ROLES."""
    for role in ("bass", "lead", "pad", "atmos", "vox", "fx", "texture"):
        assert role in MELODIC_ROLES


# ── hunt order: sounds/ first ─────────────────────────────────────────────────


def _mock_ableton_with_sounds(sounds_results, drums_results=None):
    """Build an ableton mock whose search_browser returns given items per path."""
    ableton = MagicMock()

    def send_command(cmd, args):
        if cmd == "search_browser":
            path = args.get("path", "")
            if path == "sounds":
                return {"items": sounds_results}
            if path == "drums":
                return {"items": drums_results or []}
        return {}

    ableton.send_command = side_effect = send_command
    ableton.send_command = MagicMock(side_effect=send_command)
    return ableton


def _mock_atlas_with_operator():
    """Atlas returning bare Operator — the §1 violation device."""
    atlas = MagicMock()
    atlas._by_tag = {}
    atlas.search = MagicMock(return_value=[
        {"uri": "query:Synths#Operator", "name": "Operator",
         "character_tags": [], "pack": "", "genre_affinity": {}},
    ])
    return atlas


def test_brief_returns_only_tier_a_when_sounds_curated_available_for_melodic_role():
    """§1 hard rule: when sounds/ returns a curated preset for 'bass', the
    brief MUST NOT include bare Operator/Wavetable/Drift etc.
    This is the core regression guard."""
    sounds_curated = [
        {"uri": "query:Sounds#Bass:FileId_55331", "name": "FM Deep Bass.adg",
         "is_loadable": True},
    ]
    ableton = _mock_ableton_with_sounds(sounds_curated)
    atlas = _mock_atlas_with_operator()

    candidates = get_role_candidates(
        atlas, "bass", ableton=ableton, exclude_names=set()
    )
    tiers = [c["tier"] for c in candidates]
    names = [c["name"] for c in candidates]

    # Tier-A curated preset IS present
    assert TIER_A_CURATED_PRESET in tiers
    assert "FM Deep Bass.adg" in names

    # Bare Operator MUST NOT be in candidates (§1 fix)
    assert "Operator" not in names, (
        "§1 violation: bare Operator returned despite curated 'FM Deep Bass.adg' "
        "being available in sounds/"
    )


def test_brief_falls_back_to_tier_b_only_when_sounds_empty():
    """When sounds/ returns nothing for a melodic role, the brief MAY include
    bare Tier-B synths as fallback (with fallback_warning)."""
    ableton = _mock_ableton_with_sounds([])  # sounds/ empty
    atlas = _mock_atlas_with_operator()

    candidates = get_role_candidates(
        atlas, "bass", ableton=ableton, exclude_names=set()
    )
    tiers = [c["tier"] for c in candidates]
    names = [c["name"] for c in candidates]

    # Tier-B fallback IS present (no curated alternative)
    assert TIER_B_AUDIBLE_DEFAULT_VALUE in tiers
    assert "Operator" in names

    # The fallback_warning is set so the agent knows this is not ideal
    operator_candidate = next((c for c in candidates if c["name"] == "Operator"), None)
    assert operator_candidate is not None
    assert "fallback_warning" in operator_candidate


def test_brief_drum_role_allows_drum_specific_synths_always():
    """For drum roles, DS Kick is allowed bare — its default IS the kick sound.
    This must hold even when sounds/ returns nothing."""
    ableton = _mock_ableton_with_sounds([], drums_results=[])
    atlas = MagicMock()
    atlas._by_tag = {}
    atlas.search = MagicMock(return_value=[
        {"uri": "query:Synths#DS%20Kick", "name": "DS Kick",
         "character_tags": [], "pack": "", "genre_affinity": {}},
    ])

    candidates = get_role_candidates(
        atlas, "kick", ableton=ableton, exclude_names=set()
    )
    tiers = [c["tier"] for c in candidates]
    names = [c["name"] for c in candidates]
    assert TIER_B_DRUM_SYNTH in tiers
    assert "DS Kick" in names


def test_brief_drum_role_drum_specific_synth_even_with_tier_a():
    """For drum roles, DS Kick is still allowed even when sounds/ has a sample.
    Both Tier-A and Tier-B drum synth can coexist for drum roles."""
    sounds_curated = [
        {"uri": "query:Sounds#Kick:FileId_11111", "name": "Punch Kick.adg",
         "is_loadable": True},
    ]
    ableton = _mock_ableton_with_sounds(sounds_curated, drums_results=[])
    atlas = MagicMock()
    atlas._by_tag = {}
    atlas.search = MagicMock(return_value=[
        {"uri": "query:Synths#DS%20Kick", "name": "DS Kick",
         "character_tags": [], "pack": "", "genre_affinity": {}},
    ])

    candidates = get_role_candidates(
        atlas, "kick", ableton=ableton, exclude_names=set()
    )
    names = [c["name"] for c in candidates]
    tiers = [c["tier"] for c in candidates]

    assert "Punch Kick.adg" in names
    assert "DS Kick" in names
    assert TIER_A_CURATED_PRESET in tiers
    assert TIER_B_DRUM_SYNTH in tiers


def test_tier_a_sorted_before_tier_b():
    """Tier-A candidates always appear before Tier-B in the returned list."""
    sounds_curated = [
        {"uri": "query:Sounds#Bass:FileId_55331", "name": "FM Deep Bass.adg",
         "is_loadable": True},
    ]
    drums_results = []
    ableton = _mock_ableton_with_sounds(sounds_curated, drums_results)
    # Atlas returns DS Kick (B_drum_synth) and some unknown for drum role
    atlas = MagicMock()
    atlas._by_tag = {}
    atlas.search = MagicMock(return_value=[
        {"uri": "query:Synths#DS%20Kick", "name": "DS Kick",
         "character_tags": [], "pack": "", "genre_affinity": {}},
    ])

    # For bass role: FM Deep Bass.adg (Tier-A) should sort before any Tier-B
    candidates = get_role_candidates(
        atlas, "bass", ableton=ableton, exclude_names=set()
    )
    assert len(candidates) >= 1
    # First candidate must be Tier-A
    assert candidates[0]["tier"] == TIER_A_CURATED_PRESET, (
        f"First candidate tier was {candidates[0]['tier']!r}, expected A_curated_preset"
    )


# ── Step 1b: drums/ raw samples ──────────────────────────────────────────────


def test_drum_role_gets_drums_raw_samples_as_tier_a():
    """drums/ raw .aif/.wav samples appear as Tier-A for drum roles."""
    drums_samples = [
        {"uri": "query:Drums#kick_hard.aif", "name": "kick_hard.aif",
         "is_loadable": True},
        {"uri": "query:Drums#kick_soft.wav", "name": "kick_soft.wav",
         "is_loadable": True},
    ]
    ableton = _mock_ableton_with_sounds([], drums_results=drums_samples)
    atlas = MagicMock()
    atlas._by_tag = {}
    atlas.search = MagicMock(return_value=[])

    candidates = get_role_candidates(
        atlas, "kick", ableton=ableton, exclude_names=set()
    )
    tiers = [c["tier"] for c in candidates]
    names = [c["name"] for c in candidates]

    assert TIER_A_DRUM_SAMPLE in tiers
    assert "kick_hard.aif" in names


def test_melodic_role_does_not_search_drums_path():
    """For melodic roles (bass, pad, lead), the drums/ path is NOT searched."""
    ableton = _mock_ableton_with_sounds([])
    atlas = MagicMock()
    atlas._by_tag = {}
    atlas.search = MagicMock(return_value=[])

    get_role_candidates(atlas, "bass", ableton=ableton, exclude_names=set())

    # Only one search_browser call (for sounds/) — not for drums/
    calls = ableton.send_command.call_args_list
    paths_searched = [c.args[1].get("path") for c in calls if c.args[0] == "search_browser"]
    assert "drums" not in paths_searched, (
        f"Melodic role 'bass' should not search drums/; got paths: {paths_searched}"
    )


# ── excluded_uris: anti-repeat for curated presets ──────────────────────────


def test_excluded_uris_filter_curated_preset_reuse():
    """When a curated preset URI is in excluded_uris, it MUST NOT appear.

    This is the Acid Meltdown Bass / Interplanetary Trip Pad repeat case
    that the live test surfaced.
    """
    sounds_curated = [
        {"uri": "query:Sounds#Bass:FileId_56710", "name": "Acid Meltdown Bass.adv",
         "is_loadable": True},
        {"uri": "query:Sounds#Bass:FileId_55331", "name": "FM Deep Bass.adg",
         "is_loadable": True},
    ]
    ableton = _mock_ableton_with_sounds(sounds_curated)
    atlas = MagicMock()
    atlas._by_tag = {}
    atlas.search = MagicMock(return_value=[])

    # Acid Meltdown was loaded last round — its URI is excluded
    candidates = get_role_candidates(
        atlas, "bass",
        ableton=ableton,
        exclude_names=set(),
        excluded_uris={"query:Sounds#Bass:FileId_56710"},
    )
    names = [c["name"] for c in candidates]
    assert "Acid Meltdown Bass.adv" not in names, (
        "excluded_uris must filter out recently-loaded curated presets"
    )
    assert "FM Deep Bass.adg" in names


def test_excluded_names_still_work():
    """exclude_names filtering is still honoured alongside excluded_uris."""
    sounds_curated = [
        {"uri": "query:Sounds#Pad:FileId_11111", "name": "Interplanetary Trip Pad.adg",
         "is_loadable": True},
        {"uri": "query:Sounds#Pad:FileId_22222", "name": "Soft Sky Pad.adg",
         "is_loadable": True},
    ]
    ableton = _mock_ableton_with_sounds(sounds_curated)
    atlas = MagicMock()
    atlas._by_tag = {}
    atlas.search = MagicMock(return_value=[])

    candidates = get_role_candidates(
        atlas, "pad",
        ableton=ableton,
        exclude_names={"Interplanetary Trip Pad.adg"},
        excluded_uris=set(),
    )
    names = [c["name"] for c in candidates]
    assert "Interplanetary Trip Pad.adg" not in names
    assert "Soft Sky Pad.adg" in names


# ── Tier-C never in output ───────────────────────────────────────────────────


def test_brief_no_tier_c_anywhere():
    """Regression guard: NO Tier-C containers in any candidate, for any role."""
    sounds_results = []
    ableton = _mock_ableton_with_sounds(sounds_results)
    atlas = MagicMock()
    atlas._by_tag = {}
    atlas.search = MagicMock(return_value=[
        {"uri": "query:Synths#Drum%20Sampler", "name": "Drum Sampler",
         "character_tags": [], "pack": "", "genre_affinity": {}},
        {"uri": "query:Synths#Emit", "name": "Emit",
         "character_tags": [], "pack": "", "genre_affinity": {}},
        {"uri": "query:Synths#Operator", "name": "Operator",
         "character_tags": [], "pack": "", "genre_affinity": {}},
    ])

    for role in ("bass", "pad", "lead", "kick", "snare", "hat"):
        candidates = get_role_candidates(
            atlas, role, ableton=ableton, exclude_names=set()
        )
        names = [c["name"] for c in candidates]
        for container in CONTAINERS_NEEDING_PRESETS:
            assert container not in names, (
                f"Tier-C container '{container}' must never appear in brief "
                f"for role '{role}'"
            )


# ── backward compat: no ableton → pure atlas path still works ────────────────


def test_no_ableton_falls_back_to_atlas_only():
    """When ableton=None, the function still works (atlas-only path).
    This ensures backward compat with callers that don't have an ableton client.
    """
    atlas = MagicMock()
    atlas._by_tag = {}
    atlas.search = MagicMock(return_value=[
        {"uri": "query:Synths#Operator", "name": "Operator",
         "character_tags": [], "pack": "", "genre_affinity": {}},
    ])

    # No ableton, no excluded_uris — pure atlas fallback
    candidates = get_role_candidates(atlas, "bass", exclude_names=set())
    names = [c["name"] for c in candidates]
    # Operator is included as B_audible_default fallback (no sounds/ to prefer)
    assert "Operator" in names
    assert candidates[0]["tier"] == TIER_B_AUDIBLE_DEFAULT_VALUE


def test_no_atlas_no_ableton_returns_empty():
    """When both atlas and ableton are None, return empty list (no crash)."""
    candidates = get_role_candidates(None, "bass", exclude_names=set())
    assert candidates == []
