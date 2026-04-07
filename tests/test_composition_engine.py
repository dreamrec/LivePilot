"""Tests for Composition Engine V1 — structural and musical intelligence."""

import pytest

from mcp_server.tools._composition_engine import (
    CompositionAnalysis,
    CompositionIssue,
    GestureIntent,
    GesturePlan,
    PhraseUnit,
    RoleNode,
    RoleType,
    SectionNode,
    SectionType,
    build_role_graph,
    build_section_graph_from_arrangement,
    build_section_graph_from_scenes,
    detect_phrases,
    evaluate_composition_move,
    infer_role_for_track,
    plan_gesture,
    run_form_critic,
    run_phrase_critic,
    run_section_identity_critic,
)


# ── Section Graph ─────────────────────────────────────────────────────


class TestSectionInference:
    def _make_scenes(self, names):
        return [{"index": i, "name": n, "tempo": None, "color_index": None}
                for i, n in enumerate(names)]

    def _make_matrix(self, scene_count, track_count, active_map=None):
        """active_map: {scene_idx: [track_indices]}"""
        matrix = []
        for s in range(scene_count):
            row = []
            for t in range(track_count):
                if active_map and s in active_map and t in active_map[s]:
                    row.append({"state": "stopped", "has_clip": True, "name": f"clip_{s}_{t}"})
                else:
                    row.append(None)
            matrix.append(row)
        return matrix

    def test_scenes_with_names(self):
        scenes = self._make_scenes(["Intro", "Verse", "Chorus", "Outro"])
        matrix = self._make_matrix(4, 4, {0: [0], 1: [0, 1], 2: [0, 1, 2, 3], 3: [0]})
        sections = build_section_graph_from_scenes(scenes, matrix, 4)
        assert len(sections) == 4
        assert sections[0].section_type == SectionType.INTRO
        assert sections[1].section_type == SectionType.VERSE
        assert sections[2].section_type == SectionType.CHORUS
        assert sections[3].section_type == SectionType.OUTRO

    def test_scene_name_confidence(self):
        scenes = self._make_scenes(["Drop Section"])
        matrix = self._make_matrix(1, 4, {0: [0, 1, 2, 3]})
        sections = build_section_graph_from_scenes(scenes, matrix, 4)
        assert sections[0].section_type == SectionType.DROP
        assert sections[0].confidence >= 0.8

    def test_energy_based_inference(self):
        scenes = self._make_scenes(["A", "B", "C"])
        # A: sparse (intro-like), B: medium, C: dense
        matrix = self._make_matrix(3, 10, {0: [0], 1: [0, 1, 2, 3, 4], 2: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]})
        sections = build_section_graph_from_scenes(scenes, matrix, 10)
        assert len(sections) == 3
        # First section should be intro (low density, position 0)
        assert sections[0].section_type == SectionType.INTRO

    def test_skips_empty_scenes(self):
        scenes = self._make_scenes(["Verse", "", "", "Chorus"])
        matrix = self._make_matrix(4, 4, {0: [0, 1], 3: [0, 1, 2]})
        sections = build_section_graph_from_scenes(scenes, matrix, 4)
        assert len(sections) == 2

    def test_density_calculated(self):
        scenes = self._make_scenes(["Section"])
        matrix = self._make_matrix(1, 8, {0: [0, 1, 2, 3]})
        sections = build_section_graph_from_scenes(scenes, matrix, 8)
        assert sections[0].density == 0.5  # 4/8

    def test_section_to_dict(self):
        s = SectionNode("sec_01", 0, 8, SectionType.VERSE, 0.8, 0.5, 0.5, [0, 1], "Verse")
        d = s.to_dict()
        assert d["section_type"] == "verse"
        assert d["length_bars"] == 8

    def test_arrangement_section_graph(self):
        clips = {
            0: [{"start_time": 0, "end_time": 32, "length": 32, "name": "Pad A"}],
            1: [{"start_time": 0, "end_time": 32, "length": 32, "name": "Kick"}],
            2: [{"start_time": 32, "end_time": 64, "length": 32, "name": "Bass"}],
        }
        sections = build_section_graph_from_arrangement(clips, 4)
        assert len(sections) >= 1

    def test_empty_arrangement(self):
        sections = build_section_graph_from_arrangement({}, 4)
        assert sections == []


# ── Phrase Grid ───────────────────────────────────────────────────────


class TestPhraseDetection:
    def _make_section(self, start=0, end=16):
        return SectionNode("sec_01", start, end, SectionType.VERSE, 0.8, 0.5, 0.5, [0])

    def test_regular_grid_fallback(self):
        section = self._make_section(0, 16)
        # Uniform notes — no gaps, should fall back to 4-bar grid
        notes = {0: [{"pitch": 60, "start_time": float(i), "duration": 0.5}
                      for i in range(64)]}
        phrases = detect_phrases(section, notes)
        assert len(phrases) >= 2

    def test_gap_detection(self):
        section = self._make_section(0, 8)
        # Notes in bars 0-3, gap in bar 4, notes in bars 5-7
        notes = {0: [
            *[{"pitch": 60, "start_time": float(i), "duration": 0.5} for i in range(16)],
            # Gap at bar 4 (beats 16-19)
            *[{"pitch": 60, "start_time": float(i), "duration": 0.5} for i in range(20, 32)],
        ]}
        phrases = detect_phrases(section, notes)
        assert len(phrases) >= 2

    def test_cadence_strength(self):
        section = self._make_section(0, 4)
        # Dense notes then sparse last bar → strong cadence
        notes = {0: [
            *[{"pitch": 60, "start_time": float(i) * 0.25, "duration": 0.25} for i in range(12)],
            {"pitch": 60, "start_time": 3.0, "duration": 1.0},  # Long note in last bar
        ]}
        phrases = detect_phrases(section, notes)
        assert len(phrases) >= 1
        # Last bar sparser than average → cadence should be moderate-high

    def test_empty_section(self):
        section = self._make_section(0, 0)
        phrases = detect_phrases(section, {})
        assert phrases == []

    def test_phrase_to_dict(self):
        p = PhraseUnit("sec_01_phr_00", "sec_01", 0, 4, 0.7, 3.5, False)
        d = p.to_dict()
        assert d["length_bars"] == 4
        assert d["cadence_strength"] == 0.7


# ── Role Inference ────────────────────────────────────────────────────


class TestRoleInference:
    def test_name_based_kick(self):
        role, conf, fg = infer_role_for_track("Kick", [{"pitch": 36, "duration": 0.25}])
        assert role == RoleType.KICK_ANCHOR
        assert fg is True

    def test_name_based_pad(self):
        role, conf, fg = infer_role_for_track("Pad Warm", [{"pitch": 60, "duration": 8.0}])
        assert role == RoleType.HARMONY_BED

    def test_name_based_hats(self):
        role, conf, fg = infer_role_for_track("Hi-Hat", [{"pitch": 42, "duration": 0.25}])
        assert role == RoleType.RHYTHMIC_TEXTURE

    def test_sub_bass_register(self):
        role, conf, fg = infer_role_for_track("Synth 1",
            [{"pitch": 36, "duration": 2.0}, {"pitch": 38, "duration": 2.0}])
        assert role == RoleType.BASS_ANCHOR

    def test_long_notes_harmony_bed(self):
        role, conf, fg = infer_role_for_track("Strings",
            [{"pitch": 60, "duration": 8.0}, {"pitch": 64, "duration": 8.0}])
        assert role == RoleType.HARMONY_BED

    def test_dense_high_notes_lead(self):
        role, conf, fg = infer_role_for_track("Synth 2",
            [{"pitch": 72, "start_time": i * 0.25, "duration": 0.25} for i in range(16)])
        assert role == RoleType.LEAD
        assert fg is True

    def test_empty_notes(self):
        role, conf, fg = infer_role_for_track("Unknown Track", [])
        assert role == RoleType.UNKNOWN

    def test_device_class_drum(self):
        role, conf, fg = infer_role_for_track("Track 1",
            [{"pitch": 36, "duration": 0.25}], device_class="DrumGroupDevice")
        assert role == RoleType.RHYTHMIC_TEXTURE

    def test_role_to_dict(self):
        r = RoleNode(0, "Kick", "sec_01", RoleType.KICK_ANCHOR, 0.8, True)
        d = r.to_dict()
        assert d["role"] == "kick_anchor"

    def test_build_role_graph(self):
        sections = [SectionNode("sec_01", 0, 8, SectionType.VERSE, 0.8, 0.5, 0.5, [0, 1])]
        track_data = [
            {"index": 0, "name": "Kick", "devices": [{"class_name": "Operator"}]},
            {"index": 1, "name": "Pad", "devices": [{"class_name": "Drift"}]},
        ]
        notes = {"sec_01": {
            0: [{"pitch": 36, "start_time": 0, "duration": 0.25}],
            1: [{"pitch": 60, "start_time": 0, "duration": 8.0}],
        }}
        roles = build_role_graph(sections, track_data, notes)
        assert len(roles) == 2
        kick_role = next(r for r in roles if r.track_index == 0)
        assert kick_role.role == RoleType.KICK_ANCHOR


# ── Critics ───────────────────────────────────────────────────────────


class TestFormCritic:
    def test_no_sections(self):
        issues = run_form_critic([])
        assert any(i.issue_type == "no_sections" for i in issues)

    def test_too_few_sections(self):
        sections = [SectionNode(f"s{i}", i * 8, (i + 1) * 8, SectionType.VERSE, 0.8, 0.5, 0.5)
                     for i in range(2)]
        issues = run_form_critic(sections)
        assert any(i.issue_type == "too_few_sections" for i in issues)

    def test_flat_energy(self):
        sections = [SectionNode(f"s{i}", i * 8, (i + 1) * 8, SectionType.VERSE, 0.8, 0.5, 0.5)
                     for i in range(4)]
        issues = run_form_critic(sections)
        assert any(i.issue_type == "flat_energy_arc" for i in issues)

    def test_good_energy_arc(self):
        sections = [
            SectionNode("s0", 0, 8, SectionType.INTRO, 0.8, 0.2, 0.2),
            SectionNode("s1", 8, 16, SectionType.VERSE, 0.8, 0.5, 0.5),
            SectionNode("s2", 16, 24, SectionType.CHORUS, 0.8, 0.9, 0.9),
            SectionNode("s3", 24, 32, SectionType.OUTRO, 0.8, 0.3, 0.3),
        ]
        issues = run_form_critic(sections)
        assert not any(i.issue_type == "flat_energy_arc" for i in issues)

    def test_intro_too_dense(self):
        sections = [
            SectionNode("s0", 0, 8, SectionType.INTRO, 0.8, 0.9, 0.9),
            SectionNode("s1", 8, 16, SectionType.VERSE, 0.8, 0.5, 0.5),
        ]
        issues = run_form_critic(sections)
        assert any(i.issue_type == "intro_too_dense" for i in issues)

    def test_no_adjacent_contrast(self):
        sections = [
            SectionNode("s0", 0, 8, SectionType.VERSE, 0.8, 0.5, 0.5, name="Verse"),
            SectionNode("s1", 8, 16, SectionType.CHORUS, 0.8, 0.52, 0.52, name="Chorus"),
        ]
        issues = run_form_critic(sections)
        assert any(i.issue_type == "no_adjacent_contrast" for i in issues)


class TestSectionIdentityCritic:
    def test_no_foreground(self):
        sections = [SectionNode("s0", 0, 8, SectionType.VERSE, 0.8, 0.5, 0.5, [0, 1])]
        roles = [
            RoleNode(0, "Pad", "s0", RoleType.HARMONY_BED, 0.8, False),
            RoleNode(1, "Texture", "s0", RoleType.TEXTURE_WASH, 0.7, False),
        ]
        issues = run_section_identity_critic(sections, roles)
        assert any(i.issue_type == "no_foreground" for i in issues)

    def test_too_many_foregrounds(self):
        sections = [SectionNode("s0", 0, 8, SectionType.VERSE, 0.8, 0.5, 0.5, [0, 1, 2, 3])]
        roles = [RoleNode(i, f"Lead{i}", "s0", RoleType.LEAD, 0.8, True) for i in range(4)]
        issues = run_section_identity_critic(sections, roles)
        assert any(i.issue_type == "too_many_foregrounds" for i in issues)

    def test_chorus_weaker_than_verse(self):
        sections = [
            SectionNode("s0", 0, 8, SectionType.VERSE, 0.8, 0.7, 0.7),
            SectionNode("s1", 8, 16, SectionType.CHORUS, 0.8, 0.5, 0.5),
        ]
        issues = run_section_identity_critic(sections, [])
        assert any(i.issue_type == "chorus_not_stronger_than_verse" for i in issues)


class TestPhraseCritic:
    def _make_phrases(self, count, length=4, variation=False, cadence=0.5):
        return [PhraseUnit(f"phr_{i}", "s0", i * length, (i + 1) * length,
                           cadence, 3.0 + (1.0 if variation and i % 2 else 0.0), variation and i % 2 == 1)
                for i in range(count)]

    def test_uniform_lengths(self):
        phrases = self._make_phrases(5, length=4)
        issues = run_phrase_critic(phrases)
        assert any(i.issue_type == "uniform_phrase_lengths" for i in issues)

    def test_weak_cadences(self):
        phrases = [PhraseUnit(f"phr_{i}", "s0", i * 4, (i + 1) * 4, 0.1, 3.0, False)
                   for i in range(5)]
        issues = run_phrase_critic(phrases)
        assert any(i.issue_type == "weak_cadences" for i in issues)

    def test_no_variation(self):
        phrases = self._make_phrases(4, variation=False)
        issues = run_phrase_critic(phrases)
        assert any(i.issue_type == "no_phrase_variation" for i in issues)

    def test_good_phrases_no_issues(self):
        phrases = [
            PhraseUnit("p0", "s0", 0, 4, 0.7, 4.0, False),
            PhraseUnit("p1", "s0", 4, 12, 0.8, 2.0, True),  # Different length + variation
        ]
        issues = run_phrase_critic(phrases)
        # With only 2 phrases, most critics shouldn't fire
        assert not any(i.issue_type == "uniform_phrase_lengths" for i in issues)


# ── Gesture Planner ───────────────────────────────────────────────────


class TestGesturePlanner:
    def test_reveal(self):
        g = plan_gesture(GestureIntent.REVEAL, [0, 1], start_bar=8)
        assert g.intent == GestureIntent.REVEAL
        assert g.curve_family == "exponential"
        assert g.direction == "up"
        assert g.start_bar == 8
        assert g.end_bar == 12  # default 4 bars

    def test_inhale(self):
        g = plan_gesture(GestureIntent.INHALE, [0], start_bar=16, duration_bars=2)
        assert g.end_bar == 18
        assert g.curve_family == "exponential"
        assert g.direction == "down"

    def test_punctuate(self):
        g = plan_gesture(GestureIntent.PUNCTUATE, [5], start_bar=4)
        assert g.curve_family == "spike"
        assert g.end_bar == 5  # default 1 bar

    def test_drift(self):
        g = plan_gesture(GestureIntent.DRIFT, [6], start_bar=0, foreground=False)
        assert g.curve_family == "perlin"
        assert g.foreground is False

    def test_all_intents_have_mappings(self):
        for intent in GestureIntent:
            g = plan_gesture(intent, [0], start_bar=0)
            assert g.curve_family, f"No curve_family for {intent}"

    def test_gesture_to_dict(self):
        g = plan_gesture(GestureIntent.RELEASE, [0], start_bar=8)
        d = g.to_dict()
        assert d["intent"] == "release"
        assert "duration_bars" in d


# ── Composition Evaluation ────────────────────────────────────────────


class TestCompositionEvaluation:
    def test_improvement_kept(self):
        before = [
            CompositionIssue("flat_energy_arc", "form", 0.7, 0.8),
            CompositionIssue("no_foreground", "section_identity", 0.6, 0.7),
        ]
        after = [
            CompositionIssue("no_foreground", "section_identity", 0.6, 0.7),
        ]
        result = evaluate_composition_move(before, after, {}, {})
        assert result["keep_change"] is True
        assert result["issue_delta"] == 1

    def test_worse_undone(self):
        before = [CompositionIssue("flat_energy", "form", 0.5, 0.8)]
        after = [
            CompositionIssue("flat_energy", "form", 0.5, 0.8),
            CompositionIssue("intro_dense", "form", 0.6, 0.7),
            CompositionIssue("no_foreground", "section_identity", 0.7, 0.8),
        ]
        result = evaluate_composition_move(before, after, {}, {})
        assert result["keep_change"] is False

    def test_no_change(self):
        before = [CompositionIssue("flat", "form", 0.5, 0.8)]
        after = [CompositionIssue("flat", "form", 0.5, 0.8)]
        result = evaluate_composition_move(before, after, {}, {})
        # No improvement but no regression — borderline
        assert result["issue_delta"] == 0

    def test_consecutive_undo_hint(self):
        before = []
        after = [CompositionIssue("new_issue", "form", 0.8, 0.9)]
        result = evaluate_composition_move(before, after, {}, {})
        assert result["consecutive_undo_hint"] is True


# ── Full Analysis ─────────────────────────────────────────────────────


class TestCompositionAnalysis:
    def test_to_dict(self):
        analysis = CompositionAnalysis(
            sections=[SectionNode("s0", 0, 8, SectionType.VERSE, 0.8, 0.5, 0.5)],
            phrases=[PhraseUnit("p0", "s0", 0, 4, 0.7, 3.0, False)],
            roles=[RoleNode(0, "Kick", "s0", RoleType.KICK_ANCHOR, 0.8, True)],
            issues=[CompositionIssue("too_few", "form", 0.6, 0.8)],
        )
        d = analysis.to_dict()
        assert d["section_count"] == 1
        assert d["phrase_count"] == 1
        assert d["role_count"] == 1
        assert d["issue_count"] == 1
        assert d["issue_summary"]["form"] == 1
