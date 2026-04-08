"""Tests for Project Brain v1 — models, session graph builder, and build pipeline."""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.project_brain.models import (
    ArrangementGraph,
    AutomationGraph,
    CapabilityGraph,
    ConfidenceInfo,
    FreshnessInfo,
    ProjectState,
    RoleGraph,
    RoleNode,
    SectionNode,
    SessionGraph,
    TrackNode,
)
from mcp_server.project_brain.session_graph import build_session_graph
from mcp_server.project_brain.builder import build_project_state_from_data
from mcp_server.project_brain.arrangement_graph import build_arrangement_graph
from mcp_server.project_brain.role_graph import build_role_graph
from mcp_server.project_brain.automation_graph import build_automation_graph
from mcp_server.project_brain.capability_graph import build_capability_graph
from mcp_server.project_brain.refresh import refresh_tracks, refresh_arrangement


# ── FreshnessInfo ────────────────────────────────────────────────────


class TestFreshnessInfo:
    def test_default_is_stale(self):
        f = FreshnessInfo()
        assert f.stale is True
        assert f.stale_reason == "never built"
        assert f.built_at_ms == 0.0

    def test_mark_fresh(self):
        f = FreshnessInfo()
        before = time.time() * 1000
        f.mark_fresh(revision=5)
        after = time.time() * 1000
        assert f.stale is False
        assert f.stale_reason is None
        assert f.source_revision == 5
        assert before <= f.built_at_ms <= after

    def test_mark_stale(self):
        f = FreshnessInfo()
        f.mark_fresh(revision=1)
        f.mark_stale("track added")
        assert f.stale is True
        assert f.stale_reason == "track added"

    def test_to_dict(self):
        f = FreshnessInfo()
        d = f.to_dict()
        assert "stale" in d
        assert "built_at_ms" in d
        assert "source_revision" in d
        assert "stale_reason" in d


# ── ConfidenceInfo ───────────────────────────────────────────────────


class TestConfidenceInfo:
    def test_to_dict(self):
        c = ConfidenceInfo(overall=0.85, low_confidence_nodes=["track_3"])
        d = c.to_dict()
        assert d["overall"] == 0.85
        assert d["low_confidence_nodes"] == ["track_3"]

    def test_default_empty(self):
        c = ConfidenceInfo()
        assert c.overall == 0.0
        assert c.low_confidence_nodes == []


# ── SessionGraph ─────────────────────────────────────────────────────


class TestSessionGraph:
    def test_add_track(self):
        g = SessionGraph()
        t = TrackNode(index=0, name="Kick")
        g.add_track(t)
        assert len(g.tracks) == 1
        assert g.tracks[0].name == "Kick"

    def test_to_dict(self):
        g = SessionGraph(tempo=140.0, time_signature="3/4")
        g.add_track(TrackNode(index=0, name="Bass", has_midi=True))
        d = g.to_dict()
        assert d["tempo"] == 140.0
        assert d["time_signature"] == "3/4"
        assert len(d["tracks"]) == 1
        assert d["tracks"][0]["name"] == "Bass"
        assert d["tracks"][0]["has_midi"] is True
        assert "freshness" in d

    def test_empty_graph(self):
        g = SessionGraph()
        d = g.to_dict()
        assert d["tracks"] == []
        assert d["scenes"] == []
        assert d["return_tracks"] == []


# ── RoleGraph ────────────────────────────────────────────────────────


class TestRoleGraph:
    def test_add_role(self):
        rg = RoleGraph()
        r = RoleNode(track_index=2, section_id="intro_1", role="kick_anchor",
                     confidence=0.9, foreground=True)
        rg.add_role(r)
        assert len(rg.roles) == 1
        assert rg.roles[0].role == "kick_anchor"
        assert rg.roles[0].foreground is True

    def test_to_dict(self):
        rg = RoleGraph()
        rg.add_role(RoleNode(track_index=0, role="lead"))
        d = rg.to_dict()
        assert len(d["roles"]) == 1
        assert "confidence" in d
        assert "freshness" in d


# ── ProjectState ─────────────────────────────────────────────────────


class TestProjectState:
    def test_empty_state(self):
        ps = ProjectState()
        assert ps.revision == 0
        assert ps.is_stale() is True
        assert ps.active_issues == []

    def test_to_dict(self):
        ps = ProjectState()
        ps.session_graph.freshness.mark_fresh(1)
        d = ps.to_dict()
        assert "project_id" in d
        assert "revision" in d
        assert "session_graph" in d
        assert "arrangement_graph" in d
        assert "role_graph" in d
        assert "automation_graph" in d
        assert "capability_graph" in d
        assert "active_issues" in d
        assert "is_stale" in d

    def test_is_stale_when_all_fresh(self):
        ps = ProjectState()
        ps.session_graph.freshness.mark_fresh(1)
        ps.arrangement_graph.freshness.mark_fresh(1)
        ps.role_graph.freshness.mark_fresh(1)
        ps.automation_graph.freshness.mark_fresh(1)
        ps.capability_graph.freshness.mark_fresh(1)
        assert ps.is_stale() is False

    def test_is_stale_when_one_stale(self):
        ps = ProjectState()
        ps.session_graph.freshness.mark_fresh(1)
        ps.arrangement_graph.freshness.mark_fresh(1)
        ps.role_graph.freshness.mark_fresh(1)
        ps.automation_graph.freshness.mark_fresh(1)
        # capability_graph left stale
        assert ps.is_stale() is True


# ── Session Graph Builder ────────────────────────────────────────────


class TestSessionGraphBuilder:
    def test_builds_from_session_info(self):
        session_info = {
            "tracks": [
                {"index": 0, "name": "Kick", "has_midi_input": True, "mute": False,
                 "solo": False, "arm": True},
                {"index": 1, "name": "Bass", "has_audio_input": True, "mute": True,
                 "solo": False, "arm": False},
            ],
            "return_tracks": [{"index": 0, "name": "Reverb"}],
            "scenes": [{"index": 0, "name": "Intro"}, {"index": 1, "name": "Drop"}],
            "tempo": 128.0,
            "time_signature_numerator": 4,
            "time_signature_denominator": 4,
        }
        graph = build_session_graph(session_info)

        assert len(graph.tracks) == 2
        assert graph.tracks[0].name == "Kick"
        assert graph.tracks[0].has_midi is True
        assert graph.tracks[0].arm is True
        assert graph.tracks[1].name == "Bass"
        assert graph.tracks[1].has_audio is True
        assert graph.tracks[1].mute is True
        assert len(graph.return_tracks) == 1
        assert len(graph.scenes) == 2
        assert graph.tempo == 128.0
        assert graph.time_signature == "4/4"
        assert graph.freshness.stale is False

    def test_handles_empty_session(self):
        graph = build_session_graph({})
        assert len(graph.tracks) == 0
        assert len(graph.scenes) == 0
        assert graph.tempo == 120.0
        assert graph.freshness.stale is False


# ── Brain Builder ────────────────────────────────────────────────────


class TestBrainBuilder:
    def test_builds_full_state(self):
        session_info = {
            "tracks": [
                {"index": 0, "name": "Lead", "has_midi_input": True},
                {"index": 1, "name": "Pad", "has_audio_input": True},
            ],
            "scenes": [{"index": 0, "name": "A"}],
            "tempo": 135.0,
        }
        state = build_project_state_from_data(
            session_info=session_info,
            previous_revision=0,
        )

        assert state.revision == 1
        assert len(state.session_graph.tracks) == 2
        assert state.session_graph.tempo == 135.0
        assert state.is_stale() is False

    def test_increments_revision(self):
        session_info = {"tracks": [], "scenes": []}
        state = build_project_state_from_data(
            session_info=session_info,
            previous_revision=7,
        )
        assert state.revision == 8

    def test_with_arrangement_clips(self):
        session_info = {"tracks": [{"index": 0, "name": "Synth"}], "scenes": []}
        clips = {
            0: [
                {"index": 0, "name": "intro", "start_time": 0, "end_time": 16},
                {"index": 1, "name": "verse", "start_time": 16, "end_time": 32},
            ],
        }
        state = build_project_state_from_data(
            session_info=session_info,
            arrangement_clips=clips,
            previous_revision=0,
        )
        assert len(state.arrangement_graph.sections) == 2
        assert state.arrangement_graph.sections[0].section_id == "t0_c0"
        assert state.arrangement_graph.freshness.stale is False


# ── Arrangement Graph Builder ────────────────────────────────────────


class TestArrangementGraphBuilder:
    def test_builds_from_scenes_and_matrix(self):
        scenes = [
            {"index": 0, "name": "Intro"},
            {"index": 1, "name": "Verse"},
            {"index": 2, "name": "Chorus"},
        ]
        clip_matrix = [
            [{"state": "stopped", "has_clip": True, "name": "intro_pad"}],
            [{"state": "stopped", "has_clip": True, "name": "verse_lead"}],
            [{"state": "stopped", "has_clip": True, "name": "chorus_all"}],
        ]
        graph = build_arrangement_graph(scenes, clip_matrix, track_count=1)

        assert len(graph.sections) == 3
        assert graph.sections[0].section_type == "intro"
        assert graph.sections[1].section_type == "verse"
        assert graph.sections[2].section_type == "chorus"
        # Each section has start_bar/end_bar
        assert graph.sections[0].start_bar == 0
        assert graph.sections[0].end_bar == 8
        assert graph.sections[1].start_bar == 8

    def test_boundaries_between_sections(self):
        scenes = [
            {"index": 0, "name": "Intro"},
            {"index": 1, "name": "Drop"},
        ]
        clip_matrix = [
            [{"state": "stopped", "has_clip": True}],
            [{"state": "stopped", "has_clip": True}],
        ]
        graph = build_arrangement_graph(scenes, clip_matrix, track_count=1)

        assert len(graph.boundaries) == 1
        assert graph.boundaries[0]["from_section"] == graph.sections[0].section_id
        assert graph.boundaries[0]["to_section"] == graph.sections[1].section_id

    def test_empty_scenes(self):
        graph = build_arrangement_graph([], [], track_count=4)
        assert len(graph.sections) == 0
        assert len(graph.boundaries) == 0

    def test_density_reflects_active_tracks(self):
        scenes = [{"index": 0, "name": "Full"}]
        # 3 tracks, 2 have clips
        clip_matrix = [
            [
                {"state": "stopped", "has_clip": True},
                {"state": "stopped", "has_clip": True},
                None,
            ],
        ]
        graph = build_arrangement_graph(scenes, clip_matrix, track_count=3)

        assert len(graph.sections) == 1
        # density should be 2/3 ~ 0.667
        assert 0.6 < graph.sections[0].density < 0.7


# ── Role Graph Builder ───────────────────────────────────────────────


class TestRoleGraphBuilder:
    def test_builds_roles_from_sections_and_tracks(self):
        sections = [
            {
                "section_id": "sec_00",
                "start_bar": 0,
                "end_bar": 8,
                "section_type": "intro",
                "energy": 0.5,
                "density": 0.5,
            },
        ]
        track_data = [
            {"index": 0, "name": "Kick", "devices": [{"class_name": "DrumGroupDevice"}]},
            {"index": 1, "name": "Lead Synth", "devices": [{"class_name": "InstrumentGroupDevice"}]},
        ]
        notes_map = {
            "sec_00": {
                0: [{"pitch": 36, "duration": 0.25, "start_time": 0}],
                1: [{"pitch": 72, "duration": 1.0, "start_time": 0}],
            },
        }
        graph = build_role_graph(sections, track_data, notes_map)

        assert len(graph.roles) >= 1
        # Should have confidence info
        assert graph.confidence.overall > 0
        assert graph.freshness.stale is True  # builder doesn't mark fresh

    def test_empty_sections(self):
        graph = build_role_graph([], [{"index": 0, "name": "Bass"}], {})
        assert len(graph.roles) == 0

    def test_empty_tracks(self):
        sections = [{"section_id": "sec_00", "start_bar": 0, "end_bar": 8,
                      "section_type": "verse", "energy": 0.5, "density": 0.5}]
        graph = build_role_graph(sections, [], {})
        assert len(graph.roles) == 0

    def test_low_confidence_tracked(self):
        sections = [
            {
                "section_id": "sec_00",
                "start_bar": 0,
                "end_bar": 8,
                "section_type": "unknown",
                "energy": 0.3,
                "density": 0.3,
            },
        ]
        track_data = [
            {"index": 0, "name": "Track 1", "devices": []},
        ]
        # No notes -> low confidence role
        notes_map = {"sec_00": {0: []}}
        graph = build_role_graph(sections, track_data, notes_map)

        # Even with no notes, if track is active it might get a role
        # The important thing is low_confidence_nodes are tracked
        if graph.roles:
            for r in graph.roles:
                if r.confidence < 0.5:
                    assert f"t{r.track_index}@{r.section_id}" in graph.confidence.low_confidence_nodes


# ── Automation Graph Builder ─────────────────────────────────────────


class TestAutomationGraphBuilder:
    def test_finds_automated_params(self):
        track_infos = [
            {
                "index": 0,
                "name": "Lead",
                "devices": [
                    {
                        "name": "Auto Filter",
                        "class_name": "AutoFilter",
                        "parameters": [
                            {"name": "Frequency", "value": 0.5, "is_automated": True},
                            {"name": "Resonance", "value": 0.3, "is_automated": False},
                        ],
                    },
                ],
            },
        ]
        graph = build_automation_graph(track_infos)

        assert len(graph.automated_params) == 1
        assert graph.automated_params[0]["param_name"] == "Frequency"
        assert graph.automated_params[0]["track_name"] == "Lead"

    def test_no_automation(self):
        track_infos = [
            {
                "index": 0,
                "name": "Bass",
                "devices": [
                    {
                        "name": "EQ Eight",
                        "parameters": [
                            {"name": "Gain", "value": 0.0, "is_automated": False},
                        ],
                    },
                ],
            },
        ]
        graph = build_automation_graph(track_infos)
        assert len(graph.automated_params) == 0

    def test_empty_track_infos(self):
        graph = build_automation_graph([])
        assert len(graph.automated_params) == 0
        assert graph.density_by_section == {}

    def test_density_by_section(self):
        track_infos = [
            {
                "index": 0,
                "name": "Synth",
                "devices": [
                    {
                        "name": "Filter",
                        "parameters": [
                            {"name": "Cutoff", "value": 0.5, "is_automated": True},
                        ],
                    },
                ],
            },
        ]
        sections = [
            {"section_id": "sec_00", "density": 0.8},
            {"section_id": "sec_01", "density": 0.3},
        ]
        graph = build_automation_graph(track_infos, sections=sections)
        assert "sec_00" in graph.density_by_section
        assert "sec_01" in graph.density_by_section
        assert graph.density_by_section["sec_00"] > graph.density_by_section["sec_01"]

    def test_automation_state_field(self):
        """Some tracks report automation_state > 0 instead of is_automated."""
        track_infos = [
            {
                "index": 0,
                "name": "FX",
                "devices": [
                    {
                        "name": "Reverb",
                        "parameters": [
                            {"name": "Decay", "value": 0.5, "automation_state": 2},
                        ],
                    },
                ],
            },
        ]
        graph = build_automation_graph(track_infos)
        assert len(graph.automated_params) == 1


# ── Capability Graph Builder ─────────────────────────────────────────


class TestCapabilityGraphBuilder:
    def test_all_available(self):
        graph = build_capability_graph(
            analyzer_ok=True, analyzer_fresh=True,
            flucoma_ok=True, session_ok=True,
            memory_ok=True, web_ok=True,
        )
        assert graph.analyzer_available is True
        assert graph.flucoma_available is True
        assert "session_access" in graph.research_providers
        assert "memory" in graph.research_providers
        assert "web" in graph.research_providers

    def test_nothing_available(self):
        graph = build_capability_graph(session_ok=False)
        assert graph.analyzer_available is False
        assert graph.flucoma_available is False
        assert graph.research_providers == []

    def test_analyzer_not_fresh(self):
        graph = build_capability_graph(analyzer_ok=True, analyzer_fresh=False)
        assert graph.analyzer_available is False

    def test_plugin_health_passthrough(self):
        health = {"Serum": {"parameter_count": 256, "healthy": True}}
        graph = build_capability_graph(plugin_health=health)
        assert graph.plugin_health == health

    def test_partial_capabilities(self):
        graph = build_capability_graph(session_ok=True, memory_ok=True)
        assert "session_access" in graph.research_providers
        assert "memory" in graph.research_providers
        assert "web" not in graph.research_providers


# ── Refresh Operations ───────────────────────────────────────────────


class TestRefreshOperations:
    def _make_fresh_state(self) -> ProjectState:
        """Create a fully fresh state for testing."""
        session_info = {
            "tracks": [
                {"index": 0, "name": "Kick"},
                {"index": 1, "name": "Bass"},
            ],
            "scenes": [{"index": 0, "name": "A"}],
            "tempo": 128.0,
        }
        return build_project_state_from_data(
            session_info=session_info,
            previous_revision=0,
        )

    def test_refresh_tracks_bumps_revision(self):
        state = self._make_fresh_state()
        assert state.revision == 1

        new_info = {
            "tracks": [
                {"index": 0, "name": "Kick"},
                {"index": 1, "name": "Sub Bass"},
                {"index": 2, "name": "Lead"},
            ],
            "scenes": [{"index": 0, "name": "A"}],
            "tempo": 128.0,
        }
        new_state = refresh_tracks(state, [1, 2], new_info)
        assert new_state.revision == 2
        assert len(new_state.session_graph.tracks) == 3
        assert new_state.session_graph.freshness.stale is False

    def test_refresh_tracks_stales_dependents(self):
        state = self._make_fresh_state()

        new_info = {
            "tracks": [{"index": 0, "name": "Kick"}],
            "scenes": [],
            "tempo": 128.0,
        }
        new_state = refresh_tracks(state, [0], new_info)
        assert new_state.role_graph.freshness.stale is True
        assert new_state.automation_graph.freshness.stale is True

    def test_refresh_arrangement(self):
        state = self._make_fresh_state()
        scenes = [
            {"index": 0, "name": "Intro"},
            {"index": 1, "name": "Drop"},
        ]
        clip_matrix = [
            [{"state": "stopped", "has_clip": True}],
            [{"state": "stopped", "has_clip": True}],
        ]
        new_state = refresh_arrangement(state, scenes, clip_matrix, track_count=1)

        assert new_state.revision == 2
        assert len(new_state.arrangement_graph.sections) == 2
        assert new_state.arrangement_graph.freshness.stale is False
        assert new_state.role_graph.freshness.stale is True

    def test_refresh_preserves_original(self):
        state = self._make_fresh_state()
        original_revision = state.revision

        new_info = {
            "tracks": [{"index": 0, "name": "Changed"}],
            "scenes": [],
            "tempo": 130.0,
        }
        new_state = refresh_tracks(state, [0], new_info)

        # Original should be untouched
        assert state.revision == original_revision
        assert len(state.session_graph.tracks) == 2


# ── Full Pipeline with All Builders ──────────────────────────────────


class TestFullPipeline:
    def test_full_build_with_scenes_and_tracks(self):
        session_info = {
            "tracks": [
                {"index": 0, "name": "Kick", "has_midi_input": True},
                {"index": 1, "name": "Bass", "has_midi_input": True},
                {"index": 2, "name": "Lead Synth", "has_midi_input": True},
            ],
            "scenes": [{"index": 0, "name": "Intro"}, {"index": 1, "name": "Drop"}],
            "tempo": 128.0,
        }
        scenes = [
            {"index": 0, "name": "Intro"},
            {"index": 1, "name": "Drop"},
        ]
        clip_matrix = [
            [
                {"state": "stopped", "has_clip": True},
                None,
                {"state": "stopped", "has_clip": True},
            ],
            [
                {"state": "stopped", "has_clip": True},
                {"state": "stopped", "has_clip": True},
                {"state": "stopped", "has_clip": True},
            ],
        ]
        track_infos = [
            {
                "index": 0, "name": "Kick",
                "devices": [{"class_name": "DrumGroupDevice", "name": "Drum Rack",
                              "parameters": [{"name": "Volume", "value": 0.8, "is_automated": False}]}],
            },
            {
                "index": 1, "name": "Bass",
                "devices": [{"class_name": "InstrumentGroupDevice", "name": "Bass Synth",
                              "parameters": [{"name": "Cutoff", "value": 0.5, "is_automated": True}]}],
            },
            {
                "index": 2, "name": "Lead Synth",
                "devices": [{"class_name": "InstrumentGroupDevice", "name": "Serum",
                              "parameters": [{"name": "Filter", "value": 0.7, "is_automated": False}]}],
            },
        ]

        state = build_project_state_from_data(
            session_info=session_info,
            scenes=scenes,
            clip_matrix=clip_matrix,
            track_infos=track_infos,
            analyzer_ok=True,
            analyzer_fresh=True,
            flucoma_ok=True,
            session_ok=True,
            previous_revision=0,
        )

        # All subgraphs should be fresh
        assert state.is_stale() is False

        # Session graph
        assert len(state.session_graph.tracks) == 3
        assert state.session_graph.tempo == 128.0

        # Arrangement graph
        assert len(state.arrangement_graph.sections) == 2
        assert state.arrangement_graph.sections[0].section_type == "intro"

        # Automation graph
        assert len(state.automation_graph.automated_params) == 1
        assert state.automation_graph.automated_params[0]["param_name"] == "Cutoff"

        # Capability graph
        assert state.capability_graph.analyzer_available is True
        assert state.capability_graph.flucoma_available is True

    def test_full_build_minimal(self):
        """Build with just session_info — everything should still work."""
        session_info = {
            "tracks": [{"index": 0, "name": "Track 1"}],
            "scenes": [],
            "tempo": 120.0,
        }
        state = build_project_state_from_data(
            session_info=session_info,
            previous_revision=0,
        )
        assert state.is_stale() is False
        assert len(state.session_graph.tracks) == 1
        assert len(state.arrangement_graph.sections) == 0
        assert len(state.role_graph.roles) == 0
        assert len(state.automation_graph.automated_params) == 0

    def test_to_dict_serializable(self):
        """Ensure the full state dict is JSON-serializable."""
        import json
        session_info = {
            "tracks": [{"index": 0, "name": "Synth"}],
            "scenes": [{"index": 0, "name": "Main"}],
            "tempo": 140.0,
        }
        state = build_project_state_from_data(
            session_info=session_info,
            previous_revision=0,
        )
        d = state.to_dict()
        # Should not raise
        json.dumps(d)
