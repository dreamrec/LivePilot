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
