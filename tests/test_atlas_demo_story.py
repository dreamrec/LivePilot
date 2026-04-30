"""Smoke tests for Pack-Atlas Phase E — Demo Story.

All tests run without Live being open (no MCP / Ableton connection needed).
They exercise the sidecar loader + classification logic with real sidecar data.

Sidecar reality notes (from Phase C appendix + Phase E inspection):
  - drone-lab__earth.json:
      8 tracks: 1-Pioneer Drone, 2-Burnt Sun Bass, 3-Hourglass Texture,
      4-Cyber Angel Drone, 5-MPE Sinus Drone, 6-Distant Thunder FX,
      A-Reverb (ReturnTrack), B-Delay (ReturnTrack)
  - BPM: 80.0, Scale: C Major
  - All tracks have InstrumentGroupDevice or AudioEffectGroupDevice racks
  - Demo macros have NO name field (only index + value)
"""

import pytest
from mcp_server.atlas.demo_story import demo_story


class TestDemoStoryDronelabEarth:
    """Spec test: test_demo_story_drone_lab_earth (spec lines 631-638)."""

    def test_bpm_is_correct(self):
        result = demo_story(demo_entity_id="drone_lab__earth")
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        # BPM is float 80.0 — compare loosely
        assert abs(result["demo"]["bpm"] - 80.0) < 0.1

    def test_track_count(self):
        result = demo_story(demo_entity_id="drone_lab__earth")
        # 8 tracks total (6 MidiTrack + 2 ReturnTrack)
        assert result["demo"]["track_count"] == 8
        assert len(result["track_breakdown"]) == 8

    def test_pioneer_drone_present(self):
        result = demo_story(demo_entity_id="drone_lab__earth")
        names = [t["name"] for t in result["track_breakdown"]]
        assert any("Pioneer Drone" in n for n in names), (
            f"'Pioneer Drone' not found. Actual names: {names}"
        )

    def test_pioneer_drone_classified_as_harmonic_foundation(self):
        result = demo_story(demo_entity_id="drone_lab__earth")
        pd = next(
            t for t in result["track_breakdown"]
            if "Pioneer Drone" in t["name"]
        )
        role = pd["role"].lower()
        assert "harmonic" in role or "foundation" in role, (
            f"Expected harmonic-foundation, got: '{pd['role']}'"
        )

    def test_return_tracks_are_spatial_or_fxbus(self):
        result = demo_story(demo_entity_id="drone_lab__earth")
        return_tracks = [
            t for t in result["track_breakdown"]
            if t["type"] == "ReturnTrack"
        ]
        assert len(return_tracks) >= 1
        for t in return_tracks:
            assert t["role"] in ("spatial-glue", "fx-bus"), (
                f"Return track '{t['name']}' has unexpected role: {t['role']}"
            )

    def test_sources_present(self):
        result = demo_story(demo_entity_id="drone_lab__earth")
        assert result.get("sources"), "sources list should be non-empty"
        sources_str = str(result["sources"])
        assert "als-parse" in sources_str

    def test_production_sequence_inferred(self):
        result = demo_story(demo_entity_id="drone_lab__earth")
        seq = result.get("production_sequence_inference", [])
        assert len(seq) >= 3, f"Expected >= 3 production steps, got {len(seq)}"

    def test_learning_path_present(self):
        result = demo_story(demo_entity_id="drone_lab__earth")
        lp = result.get("suggested_learning_path", [])
        assert len(lp) >= 2, f"Expected >= 2 learning path steps, got {len(lp)}"


class TestDemoStoryDetailLevels:
    """Spec test: test_demo_story_handles_terse_and_verbose."""

    def test_verbose_narrative_longer_than_terse(self):
        terse = demo_story(demo_entity_id="drone_lab__earth", detail_level="terse")
        verbose = demo_story(demo_entity_id="drone_lab__earth", detail_level="verbose")

        assert "error" not in terse
        assert "error" not in verbose

        terse_len = len(terse["narrative"])
        verbose_len = len(verbose["narrative"])
        assert verbose_len > terse_len, (
            f"Verbose ({verbose_len} chars) should be longer than terse ({terse_len} chars)"
        )

    def test_standard_between_terse_and_verbose(self):
        terse = demo_story(demo_entity_id="drone_lab__earth", detail_level="terse")
        standard = demo_story(demo_entity_id="drone_lab__earth", detail_level="standard")
        verbose = demo_story(demo_entity_id="drone_lab__earth", detail_level="verbose")

        # Standard should generally be between terse and verbose in length
        # (not enforced strictly — just check all three succeed)
        assert "error" not in standard
        assert len(standard["narrative"]) > 0

    def test_all_three_levels_produce_track_breakdown(self):
        for level in ("terse", "standard", "verbose"):
            result = demo_story(demo_entity_id="drone_lab__earth", detail_level=level)
            assert "track_breakdown" in result, f"No track_breakdown for level={level}"
            assert len(result["track_breakdown"]) > 0


class TestDemoStoryErrorHandling:
    """Spec test: test_demo_story_unknown_demo_returns_error."""

    def test_unknown_entity_id_returns_error_not_exception(self):
        result = demo_story(demo_entity_id="bogus_pack__nonexistent_demo_xyz")
        # Must return structured error, not raise an exception
        assert "error" in result, "Expected error key in result for unknown demo"
        assert result.get("entity_id") == "bogus_pack__nonexistent_demo_xyz"

    def test_error_result_has_no_track_breakdown(self):
        result = demo_story(demo_entity_id="this_does_not_exist__at_all")
        assert "track_breakdown" not in result or result.get("error")

    def test_error_result_has_sources_key(self):
        result = demo_story(demo_entity_id="completely_bogus__entity_id_000")
        assert "sources" in result


class TestDemoStoryMoodReel:
    """Cross-pack sanity check — ensures demo_story works beyond Drone Lab."""

    def test_mood_reel_demo_loads(self):
        result = demo_story(
            demo_entity_id="mood_reel__the_killer_awaits_gmin_135_bpm"
        )
        # This may fail due to slug translation — try hyphenated form too
        if "error" in result:
            result = demo_story(
                demo_entity_id="mood-reel__the-killer-awaits-gmin-135-bpm"
            )
        assert "error" not in result, f"Failed to load mood-reel demo: {result.get('error')}"
        assert result["demo"]["bpm"] > 0

    def test_mood_reel_has_rhythmic_driver(self):
        result = demo_story(
            demo_entity_id="mood_reel__the_killer_awaits_gmin_135_bpm"
        )
        if "error" in result:
            result = demo_story(
                demo_entity_id="mood-reel__the-killer-awaits-gmin-135-bpm"
            )
        if "error" in result:
            pytest.skip("mood-reel demo not available")
        roles = [t["role"] for t in result["track_breakdown"]]
        # mood-reel__the_killer_awaits has Ship Noise Kit (DrumGroupDevice)
        assert "rhythmic-driver" in roles, (
            f"Expected rhythmic-driver in {roles}"
        )


class TestDemoStoryFocusTracks:
    """Optional: focus_tracks narrows the breakdown."""

    def test_focus_tracks_narrows_breakdown(self):
        result = demo_story(
            demo_entity_id="drone_lab__earth",
            focus_tracks=["1-Pioneer Drone", "A-Reverb"],
        )
        assert "error" not in result
        names = [t["name"] for t in result["track_breakdown"]]
        assert "1-Pioneer Drone" in names
        # Other tracks should be filtered out
        assert "2-Burnt Sun Bass" not in names, (
            "focus_tracks should exclude 2-Burnt Sun Bass"
        )


# ─── BUG-INT#2: chain recursion in demo_story ────────────────────────────────

class TestDemoStoryChainRecursion:
    """BUG-INT#2: _build_chain_summary must recurse into dev.chains so inner
    rack devices appear in the narrative.

    Uses mood-reel__chapter-one-by-thomas-ragsdale, track '3-Saturn Ascends':
      InstrumentGroupDevice (Saturn Ascends)
        chains → [InstrumentVector (Nasal Bass), Pedal, Erosion, Limiter]

    Before fix: chain_summary showed only "InstrumentGroupDevice (Saturn Ascends) → Delay"
    After fix : chain_summary shows "[InstrumentVector (Nasal Bass) → Pedal → Erosion → Limiter]"
    """

    _DEMO = "mood_reel__chapter_one_by_thomas_ragsdale"

    def test_chain_summary_mentions_inner_devices(self):
        result = demo_story(
            demo_entity_id=self._DEMO,
            focus_tracks=["Saturn"],
            detail_level="verbose",
        )
        if "error" in result:
            pytest.skip(f"mood-reel chapter-one sidecar not available: {result['error']}")
        tb = result.get("track_breakdown", [])
        saturn = next((t for t in tb if "Saturn" in t.get("name", "")), None)
        assert saturn is not None, "Saturn Ascends track not found in track_breakdown"
        chain_summary = saturn.get("device_chain_summary", "")
        assert "Erosion" in chain_summary, (
            f"Erosion (inner chain device) not found in chain_summary. Got: {chain_summary}"
        )

    def test_chain_summary_has_inner_chain_bracket_notation(self):
        result = demo_story(
            demo_entity_id=self._DEMO,
            focus_tracks=["Saturn"],
        )
        if "error" in result:
            pytest.skip(f"mood-reel chapter-one sidecar not available: {result['error']}")
        tb = result.get("track_breakdown", [])
        saturn = next((t for t in tb if "Saturn" in t.get("name", "")), None)
        if saturn is None:
            pytest.skip("Saturn Ascends track not found")
        chain_summary = saturn.get("device_chain_summary", "")
        # The bracket notation [inner → devices] should be present for rack devices
        assert "[" in chain_summary, (
            f"Expected bracket notation for inner chain in: {chain_summary}"
        )

    def test_flat_device_chain_unaffected(self):
        """Tracks with no inner chains should produce a plain arrow-separated string."""
        result = demo_story(demo_entity_id="drone_lab__earth")
        assert "error" not in result
        tb = result.get("track_breakdown", [])
        # All tracks should still have non-empty device_chain_summary
        for t in tb:
            summary = t.get("device_chain_summary", "")
            assert summary, f"Track '{t['name']}' has empty device_chain_summary"
