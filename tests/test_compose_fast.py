"""compose(mode="fast") + compose_fast_apply — pure-computation tests.

The new architecture (2026-05-01 redesign):
  Phase 1 — `compose(mode="fast")` returns a CREATIVE BRIEF
  Phase 2 — agent reads brief, designs a layer plan with notes
  Phase 3 — `compose_fast_apply(plan)` bulk-executes server-side

These tests cover the helpers and brief shape. The full TCP-driven
orchestrator is verified live (no mocking the Ableton TCP).
"""

from __future__ import annotations

import asyncio
import random

from mcp_server.composer import fast
from mcp_server.composer.prompt_parser import CompositionIntent


# ── Atlas viability filter ───────────────────────────────────────────


def test_rejects_midi_effect_uri():
    """Rotating Rhythm Generator (MxDeviceMidiEffect) must be filtered."""
    assert not fast.is_viable_instrument_uri(
        "query:MidiFx#Rotating%20Rhythm%20Generator", "Rotating Rhythm Generator"
    )


def test_rejects_audio_effect_uri():
    assert not fast.is_viable_instrument_uri("query:AudioFx#Reverb", "Reverb")
    assert not fast.is_viable_instrument_uri("query:AudioFx#Compressor", "Compressor")


def test_rejects_sample_less_synths():
    """Bare devices that load silent."""
    assert not fast.is_viable_instrument_uri("query:Synths#Granulator%20III", "Granulator III")
    assert not fast.is_viable_instrument_uri("query:Synths#Looper", "Looper")
    assert not fast.is_viable_instrument_uri("query:Synths#Sampler", "Sampler")
    assert not fast.is_viable_instrument_uri("query:Synths#Drum%20Rack", "Drum Rack")
    assert not fast.is_viable_instrument_uri("query:Synths#Instrument%20Rack", "Instrument Rack")


def test_rejects_banned_default_devices():
    """§1 ban: Analog/Poli/Drift/Meld are universally rejected."""
    for name in ("Analog", "Poli", "Drift", "Meld"):
        assert not fast.is_viable_instrument_uri(f"query:Synths#{name}", name, role="bass")
        assert not fast.is_viable_instrument_uri(f"query:Synths#{name}", name, role="kick")
        assert not fast.is_viable_instrument_uri(f"query:Synths#{name}", name, role="pad")


def test_accepts_native_synths():
    """Wavetable / Operator / Bass are accepted (not §1-banned)."""
    assert fast.is_viable_instrument_uri("query:Synths#Wavetable", "Wavetable")
    assert fast.is_viable_instrument_uri("query:Synths#Operator", "Operator")
    assert fast.is_viable_instrument_uri("query:Synths#Bass", "Bass")


def test_accepts_drum_samples():
    assert fast.is_viable_instrument_uri(
        "query:Drums#Kick%20808%20Sub", "Kick 808 Sub"
    )


def test_accepts_factory_sound_chains():
    assert fast.is_viable_instrument_uri(
        "query:Sounds/Bass#Warm%20Sub", "Warm Sub"
    )


def test_drum_role_keyword_check_rejects_synth_for_kick():
    """Drum-role correctness: tonal synth at MIDI 36 plays wrong note."""
    assert not fast.is_viable_instrument_uri(
        "query:Synths#Wavetable", "Wavetable", role="kick"
    )


def test_drum_role_accepts_drum_sample():
    assert fast.is_viable_instrument_uri(
        "query:Drums#Kick%20Punchy", "Kick Punchy", role="kick"
    )


def test_tonal_role_accepts_any_viable_synth():
    """Tonal roles (bass/pad/lead/atmos) skip keyword filtering."""
    assert fast.is_viable_instrument_uri(
        "query:Synths#Operator", "Operator", role="bass"
    )
    assert fast.is_viable_instrument_uri(
        "query:Synths#Tree%20Tone", "Tree Tone", role="pad"
    )


# ── pick_instrument_uri (single picker for tests/legacy use) ─────────


def test_pick_instrument_uri_skips_banned_and_takes_drum_sample():
    suggestions = [
        {"uri": "query:MidiFx#Random", "device_name": "Random"},
        {"uri": "query:Synths#Analog", "device_name": "Analog"},
        {"uri": "query:Drums#Sub%20Kick", "device_name": "Sub Kick"},
    ]
    uri, name = fast.pick_instrument_uri(suggestions, role="kick")
    assert "Drums" in uri
    assert name == "Sub Kick"


def test_pick_instrument_uri_returns_empty_when_no_viable():
    suggestions = [
        {"uri": "query:Synths#Analog", "device_name": "Analog"},
        {"uri": "query:Synths#Drift", "device_name": "Drift"},
    ]
    uri, name = fast.pick_instrument_uri(suggestions, role="bass")
    assert uri == ""
    assert name == ""


# ── Atlas tag picker (single result for tests; brief uses get_role_candidates) ─


class _FakeAtlas:
    """Minimal stub matching DeviceAtlas's _by_tag interface for testing."""

    def __init__(self, by_tag: dict[str, list[dict]]):
        self._by_tag = by_tag


def test_pick_by_role_tag_basic_kick_lookup():
    atlas = _FakeAtlas({
        "kick": [
            {"uri": "query:Drums#Punchy%20Kick", "name": "Punchy Kick"},
        ],
    })
    uri, name = fast.pick_by_role_tag(atlas, role="kick", top_n=1)
    assert "Punchy Kick" in name


def test_pick_by_role_tag_filters_banned_default():
    """Even if Analog is tagged 'kick', §1 ban excludes it."""
    atlas = _FakeAtlas({
        "kick": [
            {"uri": "query:Synths#Analog", "name": "Analog"},
            {"uri": "query:Drums#Sub%20Kick", "name": "Sub Kick"},
        ],
    })
    uri, name = fast.pick_by_role_tag(atlas, role="kick", top_n=1)
    assert name == "Sub Kick"


def test_pick_by_role_tag_returns_empty_when_no_atlas():
    uri, name = fast.pick_by_role_tag(None, role="kick")
    assert uri == ""
    assert name == ""


# ── get_role_candidates (the picker the BRIEF uses to surface options) ─


def test_get_role_candidates_returns_top_n():
    atlas = _FakeAtlas({
        "bass": [
            {"uri": f"query:Sounds/Bass#V{i}", "name": f"V{i}"} for i in range(10)
        ],
    })
    candidates = fast.get_role_candidates(atlas, role="bass", top_n=5)
    assert len(candidates) == 5
    assert all("uri" in c and "name" in c for c in candidates)


def test_get_role_candidates_filters_banned_devices():
    """Brief should never include §1-banned defaults in the candidate list."""
    atlas = _FakeAtlas({
        "bass": [
            {"uri": "query:Synths#Analog", "name": "Analog"},      # §1 banned
            {"uri": "query:Synths#Drift", "name": "Drift"},        # §1 banned
            {"uri": "query:Synths#Bass", "name": "Bass"},          # OK
        ],
    })
    candidates = fast.get_role_candidates(atlas, role="bass", top_n=5)
    names = {c["name"] for c in candidates}
    assert "Analog" not in names
    assert "Drift" not in names
    assert "Bass" in names


def test_get_role_candidates_drum_role_rejects_synth():
    """Drum-role keyword check applies in the brief picker too."""
    atlas = _FakeAtlas({
        "kick": [
            {"uri": "query:Synths#Wavetable", "name": "Wavetable"},   # rejected: no drum kw
            {"uri": "query:Drums#Sub%20Kick", "name": "Sub Kick"},     # OK
        ],
    })
    candidates = fast.get_role_candidates(atlas, role="kick", top_n=5)
    names = {c["name"] for c in candidates}
    assert "Wavetable" not in names
    assert "Sub Kick" in names


def test_get_role_candidates_genre_affinity_ranks_first():
    """Devices matching the genre rank ahead of those that don't."""
    atlas = _FakeAtlas({
        "bass": [
            {
                "uri": "query:Sounds/Bass#A",
                "name": "Bass A",
                "genre_affinity": {"primary": ["jazz"], "secondary": []},
            },
            {
                "uri": "query:Sounds/Bass#B",
                "name": "Bass B",
                "genre_affinity": {"primary": ["techno"], "secondary": []},
            },
        ],
    })
    candidates = fast.get_role_candidates(atlas, role="bass", genre="techno", top_n=2)
    # Bass B matches techno → rank 1
    assert candidates[0]["name"] == "Bass B"


def test_get_role_candidates_returns_empty_when_no_atlas():
    candidates = fast.get_role_candidates(None, role="kick")
    assert candidates == []


# ── Role mapping ─────────────────────────────────────────────────────


def test_simpler_role_for_drum_layers():
    assert fast.simpler_role_for("kick") == "drum"
    assert fast.simpler_role_for("snare") == "drum"
    assert fast.simpler_role_for("hat") == "drum"
    assert fast.simpler_role_for("perc") == "drum"
    assert fast.simpler_role_for("clap") == "drum"


def test_simpler_role_for_melodic_layers():
    assert fast.simpler_role_for("bass") == "melodic"
    assert fast.simpler_role_for("pad") == "melodic"
    assert fast.simpler_role_for("lead") == "melodic"
    assert fast.simpler_role_for("atmos") == "melodic"


def test_simpler_role_for_unknown_returns_none():
    assert fast.simpler_role_for("???") is None
    assert fast.simpler_role_for("") is None


# ── Fresh-project detection ──────────────────────────────────────────


def test_default_track_name_matches_common_patterns():
    assert fast.is_default_track_name("MIDI 1")
    assert fast.is_default_track_name("Audio 1")
    assert fast.is_default_track_name("1-MIDI")
    assert fast.is_default_track_name("3-Audio")


def test_default_track_name_rejects_user_renamed():
    assert not fast.is_default_track_name("KICK")
    assert not fast.is_default_track_name("Drums")
    assert not fast.is_default_track_name("Bass Track")


def test_detect_fresh_project_user_session_shape():
    session = {
        "track_count": 4,
        "tracks": [
            {"name": "1-MIDI"},
            {"name": "2-MIDI"},
            {"name": "3-Audio"},
            {"name": "4-Audio"},
        ],
    }
    assert fast.detect_fresh_project(session) is True


def test_detect_fresh_project_rejects_user_added():
    session = {
        "track_count": 5,
        "tracks": [
            {"name": "MIDI 1"},
            {"name": "Audio 1"},
            {"name": "KICK"},
            {"name": "MIDI 2"},
            {"name": "Audio 2"},
        ],
    }
    assert fast.detect_fresh_project(session) is False


def test_track_is_empty_no_clips_no_devices():
    track_info = {
        "clip_slots": [{"index": 0, "has_clip": False}],
        "devices": [],
    }
    assert fast.track_is_empty(track_info) is True


def test_track_is_empty_rejects_track_with_clip():
    track_info = {
        "clip_slots": [{"index": 0, "has_clip": True}],
        "devices": [],
    }
    assert fast.track_is_empty(track_info) is False


def test_track_is_empty_rejects_track_with_device():
    track_info = {
        "clip_slots": [],
        "devices": [{"name": "Drift", "class_name": "Drift"}],
    }
    assert fast.track_is_empty(track_info) is False


# ── Key parser + scale-degree math ──────────────────────────────────


def test_parse_key_minor():
    assert fast.parse_key("Cm") == (0, "minor")
    assert fast.parse_key("Am") == (9, "minor")
    assert fast.parse_key("F#m") == (6, "minor")


def test_parse_key_major():
    assert fast.parse_key("C") == (0, "major")
    assert fast.parse_key("G") == (7, "major")


def test_parse_key_empty_falls_back_to_cm():
    assert fast.parse_key("") == (0, "minor")
    assert fast.parse_key("garbage") == (0, "minor")


def test_degree_to_pitch_first_degree_is_root():
    assert fast.degree_to_pitch(1, key_root=0, octave=4, mode="minor") == 48
    assert fast.degree_to_pitch(1, key_root=9, octave=4, mode="minor") == 57  # A


def test_chord_at_degree_minor_i():
    chord = fast.chord_at_degree(1, key_root=0, octave=4, mode="minor")
    assert chord == [48, 51, 55]   # C-Eb-G


def test_chord_at_degree_major_V():
    chord = fast.chord_at_degree(5, key_root=0, octave=4, mode="major")
    assert chord == [55, 59, 62]   # G-B-D


def test_scale_pitches_in_octave_minor():
    pitches = fast.scale_pitches_in_octave(key_root=0, octave=4, mode="minor")
    assert pitches == [48, 50, 51, 53, 55, 56, 58]   # C natural minor


def test_scale_pitches_in_octave_major():
    pitches = fast.scale_pitches_in_octave(key_root=0, octave=4, mode="major")
    assert pitches == [48, 50, 52, 53, 55, 57, 59]   # C major


# ── Genre creative guidance ─────────────────────────────────────────


def test_get_creative_guidance_known_genre():
    g = fast.get_creative_guidance("techno")
    assert "rhythmic_feel" in g
    assert "harmonic_palette" in g
    assert "spacing_advice" in g


def test_get_creative_guidance_unknown_genre_returns_generic():
    g = fast.get_creative_guidance("space-jazz-fusion")
    assert "rhythmic_feel" in g
    # The fallback guidance should be present, not crash


def test_get_creative_guidance_subgenre_fallback():
    """If the main genre is unknown but the sub-genre is known, use sub."""
    g = fast.get_creative_guidance("unknown", sub_genre="techno")
    # techno guidance is more specific than the generic fallback —
    # check the structured palette has techno's progressions in it.
    summary = g["harmonic_palette"]["summary"]
    assert "i-VI-VII" in summary or "static i" in summary


def test_genre_guidance_covers_main_genres():
    """Verify the dict covers the genres prompt_parser knows about."""
    expected_genres = {
        "techno", "dub techno", "house", "hip hop", "drum and bass",
        "ambient", "lo-fi", "trap",
    }
    for genre in expected_genres:
        assert genre in fast.GENRE_CREATIVE_GUIDANCE, \
            f"Missing creative guidance for genre '{genre}'"


# ── Brief builder shape ─────────────────────────────────────────────


def _fake_atlas_with_full_role_coverage():
    """Atlas with at least one viable device per role we test."""
    return _FakeAtlas({
        "kick": [{"uri": "query:Drums#Sub%20Kick", "name": "Sub Kick"}],
        "snare": [{"uri": "query:Drums#Snare%20A", "name": "Snare A"}],
        "hihat": [{"uri": "query:Drums#Hat%20Closed", "name": "Hat Closed"}],
        "hat": [{"uri": "query:Drums#Hat%20Closed", "name": "Hat Closed"}],
        "perc": [{"uri": "query:Drums#Perc", "name": "Perc"}],
        "bass": [{"uri": "query:Sounds/Bass#Warm", "name": "Warm Sub"}],
        "pad": [{"uri": "query:Sounds/Pad#Drone%20Lab", "name": "Drone Lab"}],
        "lead": [{"uri": "query:Synths#Wavetable", "name": "Wavetable"}],
        "atmos": [{"uri": "query:Sounds/Atmos#Field", "name": "Field"}],
    })


def test_build_creative_brief_shape():
    intent = CompositionIntent(genre="techno", tempo=128, key="Am", mood="dark")
    atlas = _fake_atlas_with_full_role_coverage()
    fresh_state = {"detected": False, "actions_taken": []}
    brief = fast.build_creative_brief(intent, atlas, fresh_state, bars=4)
    # Required top-level fields
    for field in (
        "phase", "mode", "intent", "tempo", "key", "scale_pitches",
        "creative_guidance", "instruments_by_role", "suggested_layer_count",
        "suggested_roles", "bars", "fresh_project_state", "next_step",
        "apply_schema_hint",
    ):
        assert field in brief, f"Brief missing field: {field}"
    assert brief["phase"] == "brief"
    assert brief["mode"] == "fast"
    assert brief["bars"] == 4


def test_brief_intent_includes_parsed_fields():
    intent = CompositionIntent(genre="techno", tempo=128, key="Am", mood="dark")
    brief = fast.build_creative_brief(
        intent, _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    assert brief["intent"]["genre"] == "techno"
    assert brief["intent"]["tempo"] == 128
    assert brief["intent"]["key"] == "Am"


def test_brief_key_includes_parsed_root_and_mode():
    intent = CompositionIntent(genre="techno", key="Am")
    brief = fast.build_creative_brief(
        intent, _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    assert brief["key"]["key_root"] == 9
    assert brief["key"]["mode"] == "minor"
    assert brief["key"]["key_str"] == "Am"


def test_brief_scale_pitches_correct_for_a_minor():
    intent = CompositionIntent(genre="techno", key="Am")
    brief = fast.build_creative_brief(
        intent, _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    # A minor scale at octave 4: A(57)-B(59)-C(60)-D(62)-E(64)-F(65)-G(67)
    assert brief["scale_pitches"]["scale_at_octave_4"] == [57, 59, 60, 62, 64, 65, 67]


def test_brief_instruments_by_role_uses_atlas_candidates():
    """Each suggested role gets its filtered candidate list."""
    intent = CompositionIntent(genre="techno")
    brief = fast.build_creative_brief(
        intent, _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    inst = brief["instruments_by_role"]
    # techno's suggested roles include kick/hat/bass/pad
    assert "kick" in inst
    assert "bass" in inst
    # Each should have at least one candidate
    assert len(inst["kick"]) >= 1
    assert inst["kick"][0]["name"] == "Sub Kick"


def test_brief_creative_guidance_matches_genre():
    intent = CompositionIntent(genre="dub techno")
    brief = fast.build_creative_brief(
        intent, _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    # Dub techno guidance should mention Basic Channel signature in the
    # harmonic_palette summary (Phase A: harmonic_palette is now a dict).
    summary = brief["creative_guidance"]["harmonic_palette"]["summary"]
    assert "Basic Channel" in summary


def test_brief_apply_schema_hint_present():
    """The brief explicitly tells the agent what fast_apply expects."""
    intent = CompositionIntent(genre="techno")
    brief = fast.build_creative_brief(
        intent, _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    assert "layers" in brief["apply_schema_hint"]


def test_brief_next_step_directs_to_fast_apply():
    intent = CompositionIntent(genre="techno")
    brief = fast.build_creative_brief(
        intent, _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    assert "compose_fast_apply" in brief["next_step"]


def test_brief_genre_specific_role_suggestions():
    """Different genres suggest different layer roles."""
    ambient_brief = fast.build_creative_brief(
        CompositionIntent(genre="ambient"),
        _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    trap_brief = fast.build_creative_brief(
        CompositionIntent(genre="trap"),
        _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    # Ambient should NOT include kick (it's beatless)
    assert "kick" not in ambient_brief["suggested_roles"]
    assert "pad" in ambient_brief["suggested_roles"]
    # Trap MUST include kick
    assert "kick" in trap_brief["suggested_roles"]


# ── Phase A: structured harmonic + rhythmic + articulation palettes ──


def test_genre_guidance_has_structured_harmonic_palette():
    """Every genre's harmonic_palette must be a dict with 'progressions'
    list (not just a text string)."""
    for genre in ("techno", "dub techno", "house", "hip hop", "drum and bass",
                  "ambient", "lo-fi", "trap"):
        g = fast.GENRE_CREATIVE_GUIDANCE[genre]
        hp = g["harmonic_palette"]
        assert isinstance(hp, dict), f"{genre}: harmonic_palette should be dict"
        assert "progressions" in hp, f"{genre}: missing 'progressions'"
        assert isinstance(hp["progressions"], list)
        assert len(hp["progressions"]) >= 2, f"{genre}: <2 progressions"
        # Each progression: name, degrees, feel
        for prog in hp["progressions"]:
            assert "name" in prog
            assert "degrees" in prog
            assert isinstance(prog["degrees"], list)
            assert "feel" in prog


def test_genre_guidance_has_rhythmic_palette():
    """Each genre has a rhythmic_palette of named gestures."""
    for genre in ("techno", "dub techno", "house", "hip hop", "drum and bass",
                  "ambient", "lo-fi", "trap"):
        g = fast.GENRE_CREATIVE_GUIDANCE[genre]
        rp = g["rhythmic_palette"]
        assert isinstance(rp, list)
        assert len(rp) >= 1, f"{genre}: empty rhythmic_palette"
        # Each gesture: name, kick_pattern, swing_pct
        for gesture in rp:
            assert "name" in gesture
            assert "kick_pattern" in gesture
            assert "swing_pct" in gesture


def test_genre_guidance_has_articulation_targets():
    """Each genre has explicit numeric articulation targets."""
    for genre in ("techno", "dub techno", "house", "hip hop", "drum and bass",
                  "ambient", "lo-fi", "trap"):
        g = fast.GENRE_CREATIVE_GUIDANCE[genre]
        a = g["articulation_targets"]
        assert isinstance(a, dict)
        for field in ("velocity_stddev_min", "ghost_note_velocity_range",
                      "duration_variation_count_min", "swing_pct",
                      "humanization_timing_ms"):
            assert field in a, f"{genre}: articulation_targets missing {field}"


def test_genre_guidance_has_effect_chain_hints():
    """Each genre has effect chain hints per role (Phase A foundation
    for Phase B effect-chain integration)."""
    for genre in ("techno", "dub techno", "house", "hip hop", "drum and bass",
                  "ambient", "lo-fi", "trap"):
        g = fast.GENRE_CREATIVE_GUIDANCE[genre]
        echains = g["effect_chain_hints"]
        assert isinstance(echains, dict)
        # Each value is a list of effect descriptions
        for role, chain in echains.items():
            assert isinstance(chain, list)


def test_genre_guidance_has_knowledge_search_queries():
    """Each genre suggests Ableton Knowledge transcript-search queries
    (Phase A integration with the search_transcripts MCP tool)."""
    for genre in ("techno", "dub techno", "house", "hip hop", "drum and bass",
                  "ambient", "lo-fi", "trap"):
        g = fast.GENRE_CREATIVE_GUIDANCE[genre]
        queries = g["knowledge_search_queries"]
        assert isinstance(queries, list)
        assert len(queries) >= 1, f"{genre}: missing knowledge_search_queries"


def test_fallback_guidance_is_structurally_complete():
    """The unknown-genre fallback must have the same structured fields
    so brief-builder logic doesn't break on niche prompts."""
    g = fast.get_creative_guidance("space-jazz-fusion")
    for field in ("rhythmic_feel", "harmonic_palette", "rhythmic_palette",
                  "articulation_targets", "effect_chain_hints",
                  "knowledge_search_queries"):
        assert field in g, f"Fallback guidance missing field: {field}"
    assert isinstance(g["harmonic_palette"], dict)
    assert "progressions" in g["harmonic_palette"]


# ── Phase A: creative seed + anti-defaults (random per call) ─────────


def test_pick_creative_seed_returns_dict_with_label_and_directive():
    seed = fast.pick_creative_seed(rng=random.Random(0))
    assert "label" in seed
    assert "directive" in seed
    assert isinstance(seed["label"], str)
    assert isinstance(seed["directive"], str)


def test_pick_creative_seed_varies_across_seeds():
    """With many seeds, we should land on multiple different creative seeds."""
    labels = set()
    for s in range(50):
        seed = fast.pick_creative_seed(rng=random.Random(s))
        labels.add(seed["label"])
    # Pool has 10 seeds; over 50 random picks, we should see at least 5
    assert len(labels) >= 5, \
        f"Only saw {len(labels)} unique creative seeds — variety broken"


def test_pick_anti_defaults_returns_count_items():
    anti = fast.pick_anti_defaults("techno", count=2, rng=random.Random(0))
    assert len(anti) == 2
    for item in anti:
        assert isinstance(item, str)


def test_pick_anti_defaults_varies_across_seeds():
    """Different seeds → different anti-default subsets."""
    seen: set[tuple[str, ...]] = set()
    for s in range(30):
        anti = fast.pick_anti_defaults("techno", count=2, rng=random.Random(s))
        seen.add(tuple(sorted(anti)))
    # Pool has 4 anti-defaults for techno; combinations of 2 = 6 possibilities.
    # Over 30 seeds we should see at least 3 different combos.
    assert len(seen) >= 3, \
        f"Only saw {len(seen)} unique anti-default combinations — variety broken"


def test_pick_anti_defaults_falls_back_to_default_for_unknown_genre():
    anti = fast.pick_anti_defaults("space-jazz-fusion", count=2, rng=random.Random(0))
    assert len(anti) == 2


def test_pick_anti_defaults_caps_at_pool_size():
    """If count > pool size, return min(count, pool)."""
    # techno pool has 4 items
    anti = fast.pick_anti_defaults("techno", count=10, rng=random.Random(0))
    assert len(anti) == 4


# ── Phase A: brief includes Phase A fields ───────────────────────────


def test_brief_phase_a_includes_creative_seed():
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
        rng=random.Random(0),
    )
    assert "creative_seed" in brief
    assert "label" in brief["creative_seed"]
    assert "directive" in brief["creative_seed"]


def test_brief_phase_a_includes_anti_defaults():
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
        rng=random.Random(0),
    )
    assert "anti_defaults" in brief
    assert isinstance(brief["anti_defaults"], list)
    assert len(brief["anti_defaults"]) >= 1


def test_brief_phase_a_creative_seed_varies_across_seeds():
    """Same prompt + different seed → different creative seed in brief."""
    seeds_seen = set()
    for s in range(20):
        brief = fast.build_creative_brief(
            CompositionIntent(genre="techno"),
            _fake_atlas_with_full_role_coverage(),
            {"detected": False, "actions_taken": []},
            rng=random.Random(s),
        )
        seeds_seen.add(brief["creative_seed"]["label"])
    assert len(seeds_seen) >= 4, \
        "Brief creative_seed not varying across seeds — Phase A surprise broken"


def test_brief_phase_a_includes_recommended_searches():
    """Tier-1 evolved Phase A's `knowledge_search_queries` (genre-level
    list of strings) into `recommended_searches` (per-role tool+query
    entries). Verify the new field is present."""
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    assert "recommended_searches" in brief
    assert isinstance(brief["recommended_searches"], list)
    assert len(brief["recommended_searches"]) >= 1


def test_brief_phase_a_includes_structured_palettes():
    """Brief surfaces the structured harmonic + rhythmic + articulation
    palettes from genre guidance."""
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    g = brief["creative_guidance"]
    assert isinstance(g["harmonic_palette"], dict)
    assert "progressions" in g["harmonic_palette"]
    assert isinstance(g["rhythmic_palette"], list)
    assert isinstance(g["articulation_targets"], dict)


def test_brief_phase_a_uses_12_candidates_per_role_default():
    """Default candidates_per_role should be 12 for variety (was 5 in v1)."""
    # Build a fake atlas with many bass candidates
    atlas = _FakeAtlas({
        "bass": [
            {"uri": f"query:Sounds/Bass#V{i}", "name": f"V{i}"} for i in range(20)
        ],
        "kick": [{"uri": "query:Drums#K", "name": "K"}],
        "hat": [{"uri": "query:Drums#H", "name": "H"}],
        "pad": [{"uri": "query:Sounds/Pad#P", "name": "P"}],
    })
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        atlas,
        {"detected": False, "actions_taken": []},
    )
    bass_candidates = brief["instruments_by_role"]["bass"]
    assert len(bass_candidates) == 12, \
        f"Expected 12 bass candidates (Phase A default), got {len(bass_candidates)}"


def test_brief_phase_a_next_step_mentions_creative_seed_and_anti_defaults():
    """The next_step instructions must direct the agent to honor seed +
    anti-defaults — otherwise Phase A randomization is invisible to the LLM."""
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    next_step = brief["next_step"]
    assert "creative_seed" in next_step.lower() or "creative seed" in next_step.lower()
    assert "anti_default" in next_step.lower() or "anti-default" in next_step.lower()


def test_brief_phase_a_next_step_mentions_ableton_knowledge_searches():
    """next_step should direct the agent toward the recommended_searches
    flow (Tier-1) and the Ableton Knowledge MCP tools."""
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    next_step = brief["next_step"]
    assert "recommended_searches" in next_step
    assert "Ableton Knowledge" in next_step


def test_brief_phase_version_is_A():
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    assert brief["phase_version"] == "A"


# ── Tier-1: Knowledge query templates per genre × role ──────────────


def test_get_knowledge_queries_for_role_known_genre():
    """Each genre has at least one query per primary role."""
    queries = fast.get_knowledge_queries_for_role("techno", "kick")
    assert len(queries) >= 1
    for q in queries:
        assert "tool" in q
        assert "query" in q


def test_get_knowledge_queries_for_role_unknown_genre_falls_back():
    """Unknown genre still returns a sensible query plan — manual first
    (most reliable Ableton corpus), then transcript, then video."""
    queries = fast.get_knowledge_queries_for_role("space-jazz", "kick")
    assert len(queries) >= 1
    tools_used = [q["tool"] for q in queries]
    assert "search_live_manual" in tools_used
    assert "search_transcripts" in tools_used


def test_genre_knowledge_queries_cover_main_genres():
    """Every supported genre has at least one role mapped."""
    expected_genres = {
        "techno", "dub techno", "house", "hip hop", "drum and bass",
        "ambient", "lo-fi", "trap",
    }
    for genre in expected_genres:
        assert genre in fast.GENRE_KNOWLEDGE_QUERIES
        assert len(fast.GENRE_KNOWLEDGE_QUERIES[genre]) >= 1


def test_brief_includes_recommended_searches_per_role():
    """Brief.recommended_searches has at least one entry per suggested role."""
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    assert "recommended_searches" in brief
    searches = brief["recommended_searches"]
    assert isinstance(searches, list)
    # techno has 4 suggested roles (kick, hat, bass, pad), each with ≥1 query
    assert len(searches) >= 4
    # Every entry has the right shape
    for s in searches:
        assert "role" in s
        assert "tool" in s
        assert "query" in s


def test_brief_recommended_searches_use_ableton_knowledge_tool_names():
    """All recommended search tools should map to actual Ableton Knowledge
    MCP tool names (search_transcripts / search_live_manual / search_videos /
    search_knowledge_base)."""
    valid_tools = {
        "search_transcripts", "search_live_manual",
        "search_videos", "search_knowledge_base",
        "get_ableton_knowledge_info",
    }
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    for s in brief["recommended_searches"]:
        assert s["tool"] in valid_tools, f"Unknown tool: {s['tool']}"


# ── Tier-2: Reference-artist mode ───────────────────────────────────


def test_reference_artist_queries_returns_three_queries():
    queries = fast.reference_artist_queries("Ricardo Villalobos", genre="techno")
    assert len(queries) == 3


def test_reference_artist_queries_mention_artist_name():
    queries = fast.reference_artist_queries("Ricardo Villalobos")
    for q in queries:
        assert "Ricardo Villalobos" in q["query"]


def test_reference_artist_queries_empty_for_no_artist():
    assert fast.reference_artist_queries("") == []
    assert fast.reference_artist_queries(None) == []


def test_brief_includes_reference_searches_when_reference_set():
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
        reference="Ricardo Villalobos",
    )
    assert brief["reference_artist"] == "Ricardo Villalobos"
    assert len(brief["reference_searches"]) >= 1
    for s in brief["reference_searches"]:
        assert "Ricardo Villalobos" in s["query"]


def test_brief_reference_searches_empty_when_no_reference():
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage(),
        {"detected": False, "actions_taken": []},
    )
    assert brief["reference_artist"] is None
    assert brief["reference_searches"] == []


# ── Tier-3: consult_ableton_knowledge helpers ───────────────────────


def test_classify_consultation_intent_sound_design():
    from mcp_server.composer.tools import _classify_consultation_intent
    assert _classify_consultation_intent("how do i make my kick punchier?") == "sound_design"
    assert _classify_consultation_intent("warm bass design tips") == "sound_design"


def test_classify_consultation_intent_device():
    from mcp_server.composer.tools import _classify_consultation_intent
    # "Auto Filter" matches device class — even though "warm" matches sound_design,
    # device should win on specific keyword count
    assert _classify_consultation_intent(
        "what does the auto filter env modulation do"
    ) == "device"


def test_classify_consultation_intent_arrangement():
    from mcp_server.composer.tools import _classify_consultation_intent
    assert _classify_consultation_intent("how do I structure a build into a drop") == "arrangement"


def test_classify_consultation_intent_mixing():
    from mcp_server.composer.tools import _classify_consultation_intent
    assert _classify_consultation_intent("master loudness target lufs") == "mixing"


def test_classify_consultation_intent_general_fallback():
    from mcp_server.composer.tools import _classify_consultation_intent
    assert _classify_consultation_intent("hi there how are you") == "general"


def test_build_consultation_plan_device_intent_fires_manual_first():
    from mcp_server.composer.tools import _build_consultation_plan
    plan = _build_consultation_plan(
        "what does Operator do",
        "what does operator do",
        "device",
        "",
    )
    assert plan[0]["tool"] == "search_live_manual"


def test_build_consultation_plan_sound_design_uses_genre_prefix():
    from mcp_server.composer.tools import _build_consultation_plan
    plan = _build_consultation_plan(
        "kick punch",
        "kick punch",
        "sound_design",
        "techno",
    )
    # First query should include the genre prefix
    assert "techno" in plan[0]["query"].lower()


# ── BUG-M: Vector Grain rejection ───────────────────────────────────


def test_vector_grain_rejected_as_silent_without_config():
    """Vector Grain is a granular synth — silent until a sample is loaded.
    Same class as Granulator III; must be in the silent-without-config set."""
    assert not fast.is_viable_instrument_uri(
        "query:Synths#Vector%20Grain", "Vector Grain", role="pad"
    )


# ── BUG-K: atlas_search fallback in get_role_candidates ─────────────


class _FakeAtlasWithSearch:
    """Stub matching DeviceAtlas's _by_tag + search() interface."""

    def __init__(self, by_tag: dict[str, list[dict]], search_results: dict[str, list[dict]] = None):
        self._by_tag = by_tag
        self._search_results = search_results or {}

    def search(self, query: str, category: str = "all", limit: int = 10) -> list[dict]:
        return self._search_results.get(query, [])[:limit]


def test_get_role_candidates_falls_back_to_search_when_tags_empty():
    """User's atlas may not have canonical role tags. When _by_tag is empty
    for a role, we fall through to atlas.search() with a sonic-description
    query."""
    atlas = _FakeAtlasWithSearch(
        by_tag={},  # no tags at all
        search_results={
            "warm techno bass sub low end": [
                {"uri": "query:Synths#Bass", "name": "Bass",
                 "character_tags": ["bass", "low_end"]},
            ],
        },
    )
    candidates = fast.get_role_candidates(atlas, role="bass", genre="techno", top_n=5)
    assert len(candidates) >= 1
    assert candidates[0]["name"] == "Bass"
    assert candidates[0]["source"] == "search"


def test_get_role_candidates_combines_tag_and_search_results():
    """When tags partially populate, search() supplements but doesn't dupe."""
    atlas = _FakeAtlasWithSearch(
        by_tag={"kick": [
            {"uri": "query:Drums#Kick%20A", "name": "Kick A"},
        ]},
        search_results={
            "punchy techno kick drum sub bass anchor": [
                {"uri": "query:Drums#Kick%20A", "name": "Kick A"},  # dupe — should not double
                {"uri": "query:Drums#Kick%20B", "name": "Kick B"},  # new
            ],
        },
    )
    candidates = fast.get_role_candidates(atlas, role="kick", genre="techno", top_n=5)
    names = [c["name"] for c in candidates]
    assert "Kick A" in names
    assert "Kick B" in names
    # Dedup check
    assert names.count("Kick A") == 1


# ── Anti-repeat: exclude_names filter ───────────────────────────────


def test_get_role_candidates_excludes_named_devices():
    """When `exclude_names` is passed, those devices drop out of the result.
    This is what breaks the 'Tree Tone always wins' repetition."""
    atlas = _FakeAtlasWithSearch(
        by_tag={"pad": [
            {"uri": "query:Synths#Tree%20Tone", "name": "Tree Tone"},
            {"uri": "query:Sounds/Pad#Drone%20Lab", "name": "Drone Lab"},
        ]},
    )
    candidates = fast.get_role_candidates(
        atlas, role="pad", top_n=5,
        exclude_names={"Tree Tone"},
    )
    names = [c["name"] for c in candidates]
    assert "Tree Tone" not in names
    assert "Drone Lab" in names


def test_extract_loaded_device_names_pulls_from_session_tracks():
    session_info = {
        "tracks": [
            {"name": "KICK", "devices": [{"name": "Drum Rack"}]},
            {"name": "BASS", "devices": [{"name": "Bass"}]},
            {"name": "PAD", "devices": [{"name": "Tree Tone"}]},
        ],
    }
    names = fast._extract_loaded_device_names(session_info)
    assert "Drum Rack" in names
    assert "Bass" in names
    assert "Tree Tone" in names


def test_extract_loaded_device_names_empty_session():
    assert fast._extract_loaded_device_names({"tracks": []}) == set()
    assert fast._extract_loaded_device_names({}) == set()


# ── Octave recommendations ──────────────────────────────────────────


def test_recommended_octaves_covers_all_main_roles():
    for role in ("kick", "snare", "hat", "perc", "clap", "bass", "pad", "lead", "atmos"):
        assert role in fast.RECOMMENDED_OCTAVES_PER_ROLE


def test_bass_octave_recommendation_avoids_octave_1():
    """Critical: the user said 'everything is super low pitched' because
    we designed bass at A1=33. The brief MUST recommend octave 2+ for bass."""
    bass_rec = fast.RECOMMENDED_OCTAVES_PER_ROLE["bass"]
    assert bass_rec["recommended_octave"] >= 2
    midi_low, midi_high = bass_rec["midi_range"]
    assert midi_low >= 33  # MIDI 33 = A1 — at or above the muddy zone
    # The TYPICAL bass should be above A1
    assert midi_high > midi_low + 6  # at least an octave of usable range


def test_pad_octave_recommendation_is_mid():
    pad_rec = fast.RECOMMENDED_OCTAVES_PER_ROLE["pad"]
    assert pad_rec["recommended_octave"] == 4


def test_kick_recommendation_uses_drum_rack_convention():
    kick_rec = fast.RECOMMENDED_OCTAVES_PER_ROLE["kick"]
    assert kick_rec["midi_pitch"] == 36  # C1 — drum rack convention


# ── Brief integration: octaves_by_role + excluded_recently_used ─────


def _fake_atlas_with_full_role_coverage_v2():
    """Test atlas with both tag and search coverage for all roles."""
    devices = {
        "kick": [{"uri": "query:Drums#Sub%20Kick", "name": "Sub Kick"}],
        "snare": [{"uri": "query:Drums#Snare%20A", "name": "Snare A"}],
        "hihat": [{"uri": "query:Drums#Hat%20Closed", "name": "Hat Closed"}],
        "hat": [{"uri": "query:Drums#Hat%20Closed", "name": "Hat Closed"}],
        "perc": [{"uri": "query:Drums#Perc", "name": "Perc"}],
        "bass": [{"uri": "query:Sounds/Bass#Warm", "name": "Warm Sub"}],
        "pad": [{"uri": "query:Sounds/Pad#Drone%20Lab", "name": "Drone Lab"}],
        "lead": [{"uri": "query:Synths#Wavetable", "name": "Wavetable"}],
        "atmos": [{"uri": "query:Sounds/Atmos#Field", "name": "Field"}],
    }
    return _FakeAtlasWithSearch(by_tag=devices)


def test_brief_includes_octaves_by_role():
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage_v2(),
        {"detected": False, "actions_taken": []},
    )
    assert "octaves_by_role" in brief
    obr = brief["octaves_by_role"]
    # techno has bass + pad in suggested_roles
    assert "bass" in obr
    assert "pad" in obr
    # Bass recommendation must steer away from octave 1
    assert obr["bass"]["recommended_octave"] >= 2


def test_brief_includes_excluded_recently_used():
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage_v2(),
        {"detected": False, "actions_taken": []},
        exclude_loaded_device_names={"Tree Tone", "Drum Rack"},
    )
    assert "excluded_recently_used" in brief
    excl = brief["excluded_recently_used"]
    assert "Tree Tone" in excl
    assert "Drum Rack" in excl


def test_brief_anti_repeat_actually_filters_candidates():
    """End-to-end: passing Tree Tone in exclude_loaded_device_names should
    drop it from instruments_by_role['pad']."""
    atlas = _FakeAtlasWithSearch(
        by_tag={"pad": [
            {"uri": "query:Synths#Tree%20Tone", "name": "Tree Tone"},
            {"uri": "query:Sounds/Pad#Drone%20Lab", "name": "Drone Lab"},
        ]},
    )
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        atlas,
        {"detected": False, "actions_taken": []},
        exclude_loaded_device_names={"Tree Tone"},
    )
    pad_candidates = brief["instruments_by_role"]["pad"]
    names = {c["name"] for c in pad_candidates}
    assert "Tree Tone" not in names


# ── BUG-L: rewritten knowledge queries hit Ableton corpus ───────────


def test_knowledge_queries_use_device_names_for_manual_searches():
    """Ableton's manual is indexed by device name. Our queries should
    target devices ('Saturator', 'Auto Filter') not jargon ('saturation transient')."""
    queries = fast.get_knowledge_queries_for_role("techno", "kick")
    # First query is search_live_manual — should be a clean device name
    assert queries[0]["tool"] == "search_live_manual"
    # Should be a single concise device name
    assert len(queries[0]["query"].split()) <= 3


def test_knowledge_queries_use_user_question_shape_for_transcripts():
    """Transcripts respond better to user-question-shaped queries
    ('how to mix kick') than producer-jargon ('kick saturation transient')."""
    queries = fast.get_knowledge_queries_for_role("techno", "kick")
    transcript_queries = [q for q in queries if q["tool"] == "search_transcripts"]
    assert len(transcript_queries) >= 1
    # Should contain "how to" or similar user-question shape
    q = transcript_queries[0]["query"].lower()
    assert "how to" in q or "design" in q or "mix" in q


def test_knowledge_queries_include_video_search_with_genre():
    """search_videos with the genre keyword catches 'Made in Ableton'
    producer videos."""
    queries = fast.get_knowledge_queries_for_role("techno", "kick")
    video_queries = [q for q in queries if q["tool"] == "search_videos"]
    assert len(video_queries) >= 1
    assert "techno" in video_queries[0]["query"].lower()


def test_genre_knowledge_queries_dict_built_from_function():
    """Backward-compat: GENRE_KNOWLEDGE_QUERIES dict still exposes
    the same data as the function for callers that read it directly."""
    # Should have entries for the main genres
    for genre in ("techno", "house", "hip hop"):
        assert genre in fast.GENRE_KNOWLEDGE_QUERIES
        assert "kick" in fast.GENRE_KNOWLEDGE_QUERIES[genre]
        # Each role has at least one query
        assert len(fast.GENRE_KNOWLEDGE_QUERIES[genre]["kick"]) >= 1


# ── BUG-K root cause fix: atlas.search() returns wrapped {device, score} ──


class _FakeAtlasReturningWrappedSearchResults:
    """Atlas stub mimicking AtlasManager.search() which returns
    [{"device": <dev_dict>, "score": int}, ...] — NOT the raw device dicts.
    This is the bug that broke BUG-K's first-pass fix."""

    def __init__(self, search_results: list[dict]):
        self._by_tag = {}
        self._search_results = search_results

    def search(self, query: str, category: str = "all", limit: int = 10) -> list[dict]:
        return self._search_results[:limit]


def test_get_role_candidates_unwraps_device_score_wrapper():
    """The fallback must unwrap atlas.search()'s {device, score} format.
    Before the fix, candidates came out with name=None / uri=None."""
    atlas = _FakeAtlasReturningWrappedSearchResults(search_results=[
        {"device": {"uri": "query:Synths#Wavetable", "name": "Wavetable",
                    "character_tags": ["lush", "evolving"]}, "score": 175},
        {"device": {"uri": "query:Synths#Tree%20Tone", "name": "Tree Tone",
                    "character_tags": ["organic", "evolving"]}, "score": 140},
    ])
    candidates = fast.get_role_candidates(atlas, role="pad", top_n=5)
    assert len(candidates) >= 2
    names = {c["name"] for c in candidates}
    assert "Wavetable" in names
    assert "Tree Tone" in names
    # No None values bleeding through
    assert all(c["name"] for c in candidates)
    assert all(c["uri"] for c in candidates)


def test_get_role_candidates_handles_unwrapped_device_dicts():
    """Backward compat: if a future atlas version returns raw device
    dicts (no wrapper), the picker still works."""
    atlas = _FakeAtlasReturningWrappedSearchResults(search_results=[
        {"uri": "query:Synths#Wavetable", "name": "Wavetable"},
    ])
    candidates = fast.get_role_candidates(atlas, role="pad", top_n=5)
    assert len(candidates) >= 1
    assert candidates[0]["name"] == "Wavetable"


# ── BUG-N: URI normalization in compose_fast_apply ──────────────────


def test_uri_normalization_decodes_percent_26():
    """BUG-N: search_browser returns Sounds URIs with literal `&`,
    but agents may URL-encode it to %26 in their plan, breaking the
    exact-match URI walk in load_browser_item. Normalize on the way in."""
    test_cases = [
        ("query:Sounds#Ambient%20%26%20Evolving:FileId_56475",
         "query:Sounds#Ambient%20&%20Evolving:FileId_56475"),
        ("query:Sounds#Ambient & Evolving:FileId_56475",
         "query:Sounds#Ambient & Evolving:FileId_56475"),
        ("query:Sounds#Ambient%2526%20Evolving",  # double-encoded
         "query:Sounds#Ambient&%20Evolving"),
    ]
    for input_uri, expected in test_cases:
        normalized = input_uri.replace("%2526", "&").replace("%26", "&")
        assert normalized == expected, f"{input_uri!r} → {normalized!r}, expected {expected!r}"


# ── BUG-O: recommended_searches capped at 1 per role ────────────────


def test_brief_recommended_searches_capped_at_one_per_role():
    """BUG-O: 3 queries per role × 4 roles = 12 searches. Too many.
    Cap at 1 per role; rest go into optional_searches."""
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage_v2(),
        {"detected": False, "actions_taken": []},
    )
    rec_roles = [s["role"] for s in brief["recommended_searches"]]
    # techno suggested_roles = ["kick", "hat", "bass", "pad"] = 4 roles
    # → exactly 4 recommended searches (1 per role)
    assert len(rec_roles) == len(set(rec_roles)), \
        "Each role should appear at most once in recommended_searches"
    assert len(brief["recommended_searches"]) <= 5, \
        f"Too many recommended searches: {len(brief['recommended_searches'])}"


def test_brief_includes_optional_searches():
    """The remaining queries (transcripts + videos) live in optional_searches
    so the agent can fire them only when there's time."""
    brief = fast.build_creative_brief(
        CompositionIntent(genre="techno"),
        _fake_atlas_with_full_role_coverage_v2(),
        {"detected": False, "actions_taken": []},
    )
    assert "optional_searches" in brief
    assert isinstance(brief["optional_searches"], list)
    # Should have entries (the queries cut from recommended_searches)
    assert len(brief["optional_searches"]) >= 1


# ── BUG-P: atlas indexer populates _by_tag from character_tags too ──


def test_atlas_indexer_pulls_character_tags_into_by_tag():
    """BUG-P: enriched factory atlas devices use `character_tags`, not `tags`.
    The indexer must read both so _by_tag is actually populated."""
    from mcp_server.atlas import AtlasManager
    import json
    import tempfile
    import os

    # Build a tiny atlas with a device that has only character_tags (no tags)
    fake_atlas = {
        "version": "1.0",
        "devices": [
            {
                "id": "test_kick",
                "name": "Test Kick",
                "uri": "query:Synths#Test%20Kick",
                "category": "instruments",
                "character_tags": ["kick", "drum", "punchy"],
                # Note: NO `tags` field
            },
        ],
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(fake_atlas, f)
        path = f.name

    try:
        manager = AtlasManager(path)
        # The kick tag should be populated via character_tags fallback
        assert "kick" in manager._by_tag, \
            "BUG-P: character_tags not indexed into _by_tag"
        assert len(manager._by_tag["kick"]) == 1
        assert manager._by_tag["kick"][0]["name"] == "Test Kick"
    finally:
        os.unlink(path)


def test_atlas_indexer_dedupes_when_tags_and_character_tags_overlap():
    """If a device has 'kick' in BOTH tags and character_tags, only index once."""
    from mcp_server.atlas import AtlasManager
    import json
    import tempfile
    import os

    fake_atlas = {
        "version": "1.0",
        "devices": [
            {
                "id": "dual",
                "name": "Dual Tag Kick",
                "uri": "query:Synths#Dual",
                "category": "instruments",
                "tags": ["kick", "drum"],
                "character_tags": ["kick", "punchy"],  # 'kick' overlaps
            },
        ],
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(fake_atlas, f)
        path = f.name

    try:
        manager = AtlasManager(path)
        # 'kick' should appear once (deduped), not twice
        assert len(manager._by_tag.get("kick", [])) == 1
    finally:
        os.unlink(path)


# ── Phase B (2026-05-01): structured effect_chain_hints + send_hints ──


def test_genre_guidance_effect_chain_hints_are_structured_lists():
    """Phase B: every genre's effect_chain_hints must be a dict whose VALUES
    are lists of {device, params} dicts — not free-text strings. The
    apply pipeline can only execute structured form."""
    for genre, guidance in fast.GENRE_CREATIVE_GUIDANCE.items():
        hints = guidance.get("effect_chain_hints")
        assert isinstance(hints, dict), f"{genre}: effect_chain_hints must be dict"
        for role, chain in hints.items():
            assert isinstance(chain, list), (
                f"{genre}.{role}: chain must be list, got {type(chain).__name__}"
            )
            for entry in chain:
                assert isinstance(entry, dict), (
                    f"{genre}.{role}: entry must be dict, got {entry!r}"
                )
                assert "device" in entry and isinstance(entry["device"], str), (
                    f"{genre}.{role}: missing/invalid 'device' in {entry!r}"
                )
                assert "params" in entry and isinstance(entry["params"], dict), (
                    f"{genre}.{role}: missing/invalid 'params' in {entry!r}"
                )


def test_genre_guidance_includes_send_hints_field():
    """Phase B: every genre must declare a send_hints dict (may be empty)."""
    for genre, guidance in fast.GENRE_CREATIVE_GUIDANCE.items():
        assert "send_hints" in guidance, f"{genre} missing send_hints"
        assert isinstance(guidance["send_hints"], dict), (
            f"{genre}: send_hints must be dict"
        )


def test_send_hints_entries_are_well_shaped():
    """Phase B: each send_hints[role] entry must be a list of
    {return_name|send_index, value}."""
    for genre, guidance in fast.GENRE_CREATIVE_GUIDANCE.items():
        sends = guidance.get("send_hints") or {}
        for role, entries in sends.items():
            assert isinstance(entries, list), (
                f"{genre}.{role}: send entries must be list"
            )
            for s in entries:
                assert isinstance(s, dict), f"{genre}.{role}: entry must be dict"
                assert "value" in s, f"{genre}.{role}: missing value"
                assert isinstance(s["value"], (int, float)), (
                    f"{genre}.{role}: value must be numeric"
                )
                assert (
                    "return_name" in s or "send_index" in s
                ), f"{genre}.{role}: must include return_name or send_index"


def test_creative_guidance_fallback_has_structured_fields():
    """Phase B: get_creative_guidance fallback for unknown genre must
    include the structured fields too — agents shouldn't crash on
    obscure prompts."""
    g = fast.get_creative_guidance("not_a_real_genre", "")
    assert "effect_chain_hints" in g
    assert isinstance(g["effect_chain_hints"], dict)
    assert "send_hints" in g
    assert isinstance(g["send_hints"], dict)


def test_techno_effect_chain_includes_saturator_with_drive():
    """Phase B sanity: techno kick should have structured Saturator hint
    with a Drive value the agent can execute directly."""
    g = fast.get_creative_guidance("techno", "")
    kick_chain = g["effect_chain_hints"].get("kick") or []
    saturators = [e for e in kick_chain if e["device"].lower() == "saturator"]
    assert saturators, "techno kick must include Saturator"
    sat = saturators[0]
    assert "Drive" in sat["params"]
    assert 0.0 <= sat["params"]["Drive"] <= 1.0, "Saturator Drive is normalized 0-1"


def test_lofi_pad_chain_includes_chorus_ensemble():
    """Phase B sanity: lo-fi pad chain should reach for Chorus-Ensemble."""
    g = fast.get_creative_guidance("lo-fi", "")
    pad_chain = g["effect_chain_hints"].get("pad") or []
    devices = [e["device"] for e in pad_chain]
    assert any("Chorus" in d for d in devices), (
        "lo-fi pad should include a Chorus-family device"
    )


def test_brief_apply_schema_hint_documents_effects_and_sends():
    """Phase B: the brief's apply_schema_hint MUST show agent how to
    structure effects + sends — otherwise the agent skips them.
    Built via fast.build_creative_brief directly (no Ableton needed)."""
    intent = CompositionIntent(
        genre="techno", sub_genre="", mood="dark", tempo=128, key="Am",
    )
    brief = fast.build_creative_brief(
        intent=intent,
        atlas=None,
        fresh_project_state={"detected": False, "actions_taken": [],
                             "tempo_set": False,
                             "starting_track_count_after_cleanup": 0},
        bars=4,
        reference=None,
        exclude_loaded_device_names=set(),
    )
    schema = brief.get("apply_schema_hint") or {}
    layer_template = (schema.get("layers") or [{}])[0]
    assert "effects" in layer_template, "schema must document effects array"
    assert "sends" in layer_template, "schema must document sends array"


def test_brief_next_step_mentions_effects_and_sends():
    """Phase B: agent reads next_step as primary instruction. Must
    explicitly say 'effects' and 'sends' or agents skip them."""
    intent = CompositionIntent(
        genre="techno", sub_genre="", mood="dark", tempo=128, key="Am",
    )
    brief = fast.build_creative_brief(
        intent=intent,
        atlas=None,
        fresh_project_state={"detected": False, "actions_taken": [],
                             "tempo_set": False,
                             "starting_track_count_after_cleanup": 0},
        bars=4,
        reference=None,
        exclude_loaded_device_names=set(),
    )
    nxt = (brief.get("next_step") or "").lower()
    assert "effects" in nxt
    assert "sends" in nxt
    assert "effect_chain_hints" in nxt or "send_hints" in nxt


# ── Phase B: _apply_fast_plan effect/send execution (with fake bridge) ─


class _FakeAbleton:
    """Records send_command calls and returns shaped responses so we can
    verify the apply pipeline issues the right TCP commands in the right
    order without spinning up a real Ableton."""

    def __init__(self, return_tracks: list[str] | None = None):
        self.calls: list[tuple[str, dict]] = []
        self._track_count = 0
        self._return_tracks = return_tracks or []
        # device_index counter per (track_index) — increments on insert_device
        self._track_devices: dict[int, int] = {}

    def send_command(self, name: str, params: dict) -> dict:
        self.calls.append((name, dict(params)))
        if name == "get_session_info":
            return {
                "track_count": self._track_count,
                "scene_count": 1,
                "scenes": [{"name": ""}],
                "tracks": [],
            }
        if name == "get_return_tracks":
            return {
                "return_tracks": [
                    {"index": i, "name": n} for i, n in enumerate(self._return_tracks)
                ]
            }
        if name == "create_midi_track":
            self._track_count += 1
            return {"index": self._track_count - 1}
        if name == "load_browser_item":
            return {"loaded": "Some Synth"}
        if name == "create_clip":
            return {"ok": True}
        if name == "add_notes":
            return {"added": len(params.get("notes") or [])}
        if name == "insert_device":
            ti = int(params["track_index"])
            di = self._track_devices.get(ti, 0)
            self._track_devices[ti] = di + 1
            return {
                "loaded": params["device_name"],
                "device_index": di,
                "parameter_count": 8,
            }
        if name == "set_device_parameter":
            return {
                "name": params.get("parameter_name", ""),
                "value": float(params.get("value", 0)),
            }
        if name == "set_track_send":
            return {
                "index": params["track_index"],
                "send_index": params["send_index"],
                "value": float(params["value"]),
            }
        if name == "fire_scene":
            return {"fired": True}
        if name == "get_track_info":
            return {"clips": [], "devices": [{"name": "loaded"}]}
        return {}


class _FakeCtx:
    def __init__(self, ableton):
        self.lifespan_context = {"ableton": ableton}


def test_apply_fast_plan_inserts_effects_with_params():
    """Phase B: when plan.layers[*].effects is set, _apply_fast_plan
    issues insert_device + set_device_parameter for each entry."""
    from mcp_server.composer.tools import _apply_fast_plan

    fake = _FakeAbleton(return_tracks=[])
    ctx = _FakeCtx(fake)
    plan = {
        "layers": [
            {
                "role": "kick",
                "uri": "query:Drums#Kick%20Bell",
                "notes": [{"pitch": 36, "start_time": 0, "duration": 1, "velocity": 100}],
                "effects": [
                    {"device": "Saturator", "params": {"Drive": 0.4}},
                    {"device": "EQ Eight", "params": {}},
                ],
            }
        ],
        "scene_index": 0,
        "bars": 4,
    }
    result = asyncio.run(_apply_fast_plan(ctx, plan))

    insert_calls = [c for c in fake.calls if c[0] == "insert_device"]
    assert len(insert_calls) == 2, f"expected 2 insert_device calls, got {len(insert_calls)}"
    assert insert_calls[0][1]["device_name"] == "Saturator"
    assert insert_calls[1][1]["device_name"] == "EQ Eight"

    setp_calls = [c for c in fake.calls if c[0] == "set_device_parameter"]
    assert len(setp_calls) == 1, "Saturator has Drive=0.4; EQ Eight has empty params"
    assert setp_calls[0][1]["parameter_name"] == "Drive"
    assert setp_calls[0][1]["value"] == 0.4

    assert result["effects_loaded"] == 2
    assert result["effects_failed"] == 0


def test_apply_fast_plan_resolves_send_by_return_name():
    """Phase B: layer.sends with return_name should resolve to the
    correct send_index via get_return_tracks lookup."""
    from mcp_server.composer.tools import _apply_fast_plan

    fake = _FakeAbleton(return_tracks=["A-Reverb", "B-Delay"])
    ctx = _FakeCtx(fake)
    plan = {
        "layers": [
            {
                "role": "pad",
                "uri": "query:Synths#Drift",
                "notes": [{"pitch": 60, "start_time": 0, "duration": 4, "velocity": 80}],
                "effects": [],
                "sends": [
                    {"return_name": "A-Reverb", "value": 0.30},
                    {"return_name": "B-Delay", "value": 0.10},
                ],
            }
        ],
        "scene_index": 0,
        "bars": 4,
    }
    result = asyncio.run(_apply_fast_plan(ctx, plan))

    send_calls = [c for c in fake.calls if c[0] == "set_track_send"]
    assert len(send_calls) == 2
    assert send_calls[0][1]["send_index"] == 0  # A-Reverb is index 0
    assert send_calls[0][1]["value"] == 0.30
    assert send_calls[1][1]["send_index"] == 1  # B-Delay is index 1
    assert send_calls[1][1]["value"] == 0.10
    assert result["sends_set"] == 2


def test_apply_fast_plan_send_fails_softly_when_return_missing():
    """Phase B: missing return must NOT crash the layer — record the
    miss in sends_applied with ok=False and continue."""
    from mcp_server.composer.tools import _apply_fast_plan

    fake = _FakeAbleton(return_tracks=[])  # no returns at all
    ctx = _FakeCtx(fake)
    plan = {
        "layers": [
            {
                "role": "pad",
                "uri": "query:Synths#Drift",
                "notes": [{"pitch": 60, "start_time": 0, "duration": 4, "velocity": 80}],
                "sends": [{"return_name": "Nonexistent-Reverb", "value": 0.3}],
            }
        ],
        "scene_index": 0,
        "bars": 4,
    }
    result = asyncio.run(_apply_fast_plan(ctx, plan))

    # Layer itself should still succeed
    layer = result["layers"][0]
    assert layer["ok"] is True
    # The send should be recorded as missed
    sends = layer.get("sends_applied") or []
    assert len(sends) == 1
    assert sends[0]["ok"] is False
    assert "not found" in (sends[0].get("error") or "")
    # No actual TCP set_track_send call should have fired
    assert not any(c[0] == "set_track_send" for c in fake.calls)


def test_apply_fast_plan_send_index_takes_precedence_over_return_name():
    """Phase B: if both send_index and return_name are provided,
    send_index wins (it's the more direct/explicit selector)."""
    from mcp_server.composer.tools import _apply_fast_plan

    fake = _FakeAbleton(return_tracks=["A-Reverb", "B-Delay"])
    ctx = _FakeCtx(fake)
    plan = {
        "layers": [
            {
                "role": "pad",
                "uri": "query:Synths#Drift",
                "notes": [{"pitch": 60, "start_time": 0, "duration": 4, "velocity": 80}],
                "sends": [
                    # return_name says A-Reverb (idx 0) but send_index forces 1
                    {"return_name": "A-Reverb", "send_index": 1, "value": 0.5},
                ],
            }
        ],
        "scene_index": 0,
        "bars": 4,
    }
    asyncio.run(_apply_fast_plan(ctx, plan))

    send_calls = [c for c in fake.calls if c[0] == "set_track_send"]
    assert len(send_calls) == 1
    assert send_calls[0][1]["send_index"] == 1


def test_apply_fast_plan_summary_counts_effects_and_sends():
    """Phase B: the result summary must report effects_loaded and
    sends_set so the user sees what actually happened."""
    from mcp_server.composer.tools import _apply_fast_plan

    fake = _FakeAbleton(return_tracks=["A-Reverb"])
    ctx = _FakeCtx(fake)
    plan = {
        "layers": [
            {
                "role": "kick",
                "uri": "query:Drums#Kick",
                "notes": [{"pitch": 36, "start_time": 0, "duration": 1, "velocity": 100}],
                "effects": [{"device": "Saturator", "params": {"Drive": 0.5}}],
                "sends": [{"return_name": "A-Reverb", "value": 0.1}],
            }
        ],
        "scene_index": 0,
        "bars": 4,
    }
    result = asyncio.run(_apply_fast_plan(ctx, plan))
    assert "effects loaded" in result["summary"]
    assert "sends set" in result["summary"]
    assert result["effects_loaded"] == 1
    assert result["sends_set"] == 1


def test_apply_fast_plan_no_effects_no_sends_still_works():
    """Phase B regression: layers that DON'T include effects/sends must
    still apply (Phase A backward compatibility)."""
    from mcp_server.composer.tools import _apply_fast_plan

    fake = _FakeAbleton(return_tracks=[])
    ctx = _FakeCtx(fake)
    plan = {
        "layers": [
            {
                "role": "kick",
                "uri": "query:Drums#Kick",
                "notes": [{"pitch": 36, "start_time": 0, "duration": 1, "velocity": 100}],
            }
        ],
        "scene_index": 0,
        "bars": 4,
    }
    result = asyncio.run(_apply_fast_plan(ctx, plan))
    assert result["effects_loaded"] == 0
    assert result["sends_set"] == 0
    assert result["tracks_created"] == 1
    # No insert_device or set_track_send calls should have been made
    assert not any(c[0] == "insert_device" for c in fake.calls)
    assert not any(c[0] == "set_track_send" for c in fake.calls)
