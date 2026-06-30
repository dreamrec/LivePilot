from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from urllib import request

import pytest

from mcp_server.focus_panel import FocusPanelServer
from mcp_server.persistence.agent_focus import AgentFocusService
from mcp_server.persistence.production_context import ProductionContextService
from mcp_server.persistence.session_snapshot import SessionSnapshotStore
from mcp_server.persistence import track_annotations as annotation_store
from mcp_server.tools.tracks import set_track_annotation


def _session(tracks: list[dict]) -> dict:
    return {
        "tempo": 120.0,
        "signature_numerator": 4,
        "signature_denominator": 4,
        "song_length": 64.0,
        "tracks": tracks,
        "return_tracks": [],
        "scenes": [],
    }


def _track(index: int, name: str, color: int = 0, midi: bool = False, audio: bool = True) -> dict:
    return {
        "index": index,
        "name": name,
        "color_index": color,
        "has_midi_input": midi,
        "has_audio_input": audio,
    }


def test_agent_focus_round_trips_for_current_session():
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        service = AgentFocusService(base_dir=base)
        session = _session([
            _track(0, "drums", color=2),
            _track(1, "vox1", color=7),
        ])

        result = service.set_focus(session, [1], label="lead vox", source="test")

        assert result["focus"]["label"] == "lead vox"
        assert result["focus"]["track_indices"] == [1]
        assert result["focus"]["tracks"][0]["name"] == "vox1"

        reread = service.get_focus(session)
        assert reread["focus"]["track_indices"] == [1]
        assert reread["focus"]["resolution_status"] == "resolved"


def test_agent_focus_resolves_after_track_reorder():
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        service = AgentFocusService(base_dir=base)
        original = _session([
            _track(0, "drums", color=2),
            _track(1, "vox1", color=7),
            _track(2, "bass", color=8),
        ])
        service.set_focus(original, [1], label="lead vox", source="test")

        reordered = _session([
            _track(0, "vox1", color=7),
            _track(1, "drums", color=2),
            _track(2, "bass", color=8),
        ])
        result = service.get_focus(reordered)

        assert result["focus"]["track_indices"] == [0]
        assert result["focus"]["resolution_status"] == "resolved"
        assert result["focus"]["tracks"][0]["reason"] in {
            "name+color+has_midi_input+has_audio_input",
            "name+color+has_audio_input",
            "name+color+has_midi_input",
        }


def test_agent_focus_clear_preserves_previous_in_history():
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        service = AgentFocusService(base_dir=base)
        session = _session([_track(0, "intro-mel", midi=True, audio=False)])
        service.set_focus(session, [0], label="intro", source="test")

        cleared = service.clear_focus(session)

        assert cleared["focus"]["is_empty"] is True
        assert cleared["previous_focus"]["track_indices"] == [0]
        assert service.history(session)[0]["track_indices"] == [0]


def _ctx(session_info: dict, service: AgentFocusService):
    class Ableton:
        def send_command(self, command, params=None):
            assert command == "get_session_info"
            return session_info

    return SimpleNamespace(
        lifespan_context={
            "ableton": Ableton(),
            "agent_focus": service,
            "focus_panel_url": "http://127.0.0.1:9890/",
        }
    )


def test_mcp_focus_tools_set_get_and_resolve():
    from mcp_server.tools.tracks import get_agent_focus, resolve_track_ref, set_agent_focus

    with tempfile.TemporaryDirectory() as directory:
        service = AgentFocusService(base_dir=Path(directory))
        session = _session([
            _track(0, "drums"),
            _track(1, "bass"),
        ])
        ctx = _ctx(session, service)

        set_result = set_agent_focus(ctx, [1], label="low end")
        get_result = get_agent_focus(ctx)
        resolved = resolve_track_ref(ctx, "focused")

        assert set_result["focus"]["track_indices"] == [1]
        assert get_result["focus"]["label"] == "low end"
        assert resolved["status"] == "resolved"
        assert resolved["track_indices"] == [1]
        assert resolved["focus_panel_url"] == "http://127.0.0.1:9890/"


def test_resolve_track_ref_reports_ambiguous_substrings():
    from mcp_server.tools.tracks import resolve_track_ref

    with tempfile.TemporaryDirectory() as directory:
        service = AgentFocusService(base_dir=Path(directory))
        session = _session([
            _track(0, "vox lead"),
            _track(1, "vox double"),
        ])
        result = resolve_track_ref(_ctx(session, service), "vox")

        assert result["status"] == "ambiguous"
        assert sorted(result["track_indices"]) == [0, 1]


def test_set_agent_focus_rejects_missing_track():
    from mcp_server.tools.tracks import set_agent_focus

    with tempfile.TemporaryDirectory() as directory:
        service = AgentFocusService(base_dir=Path(directory))
        session = _session([_track(0, "drums")])
        with pytest.raises(ValueError, match="Track index not found"):
            set_agent_focus(_ctx(session, service), [9])


def test_focus_panel_http_api_sets_focus():
    class Ableton:
        def __init__(self, session_info):
            self.session_info = session_info

        def send_command(self, command, params=None):
            if command == "get_session_info":
                return self.session_info
            if command == "get_track_info":
                track_index = int(params["track_index"])
                track = next(
                    item for item in self.session_info["tracks"]
                    if item["index"] == track_index
                )
                return {
                    "index": track_index,
                    "name": track["name"],
                    "devices": [],
                    "clips": [],
                }
            raise AssertionError(f"Unexpected command: {command}")

    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        service = AgentFocusService(base_dir=base)
        session = _session([
            _track(0, "drums"),
            _track(1, "intro-mel", midi=True, audio=False),
        ])
        panel = FocusPanelServer(
            Ableton(session),
            service,
            port=0,
            snapshot_store=SessionSnapshotStore(base / "current_session.json"),
        )
        try:
            url = panel.start()
            assert url

            req = request.Request(
                url + "api/focus",
                data=json.dumps({"track_indices": [1], "label": "intro"}).encode("utf-8"),
                headers={"content-type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=5) as response:
                body = json.loads(response.read().decode("utf-8"))

            assert body["focus"]["track_indices"] == [1]

            with request.urlopen(url + "api/session", timeout=5) as response:
                body = json.loads(response.read().decode("utf-8"))

            assert body["focus"]["label"] == "intro"
            assert body["tracks"][1]["focused"] is True
        finally:
            panel.stop()


def test_focus_panel_serves_dual_use_cockpit(monkeypatch):
    class Ableton:
        def __init__(self, session_info):
            self.session_info = session_info

        def send_command(self, command, params=None):
            assert command == "get_session_info"
            return self.session_info

    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", base)
        service = AgentFocusService(base_dir=base)
        production_context = ProductionContextService(base_dir=base)
        session = _session([
            _track(0, "drums"),
            _track(1, "keys", midi=True, audio=False),
            _track(2, "piano", midi=True, audio=False),
        ])
        ableton = Ableton(session)
        ctx = SimpleNamespace(
            lifespan_context={
                "ableton": ableton,
                "agent_focus": service,
                "production_context": production_context,
                "focus_panel_url": "http://127.0.0.1:9890/",
            }
        )
        set_track_annotation(
            ctx,
            track_index=1,
            role="intro_motif_double",
            decision_state="committed",
            tags=["layer:intro_high_motif"],
        )
        set_track_annotation(
            ctx,
            track_index=2,
            role="intro_motif_double",
            decision_state="committed",
            tags=["layer:intro_high_motif"],
        )
        panel = FocusPanelServer(
            ableton,
            service,
            production_context,
            snapshot_store=SessionSnapshotStore(base / "current_session.json"),
            port=0,
        )
        try:
            url = panel.start()
            assert url

            with request.urlopen(url + "cockpit", timeout=5) as response:
                html = response.read().decode("utf-8")
            assert "LivePilot Production Cockpit" in html
            assert "/api/cockpit/state" in html
            assert "window.openai.callTool" not in html

            with request.urlopen(url + "cockpit/intent", timeout=5) as response:
                intent_html = response.read().decode("utf-8")
            assert "LivePilot Intent Cockpit" in intent_html
            assert "Save brief for Codex" in intent_html
            assert "/api/cockpit/state" in intent_html
            assert "/api/cockpit/context" in intent_html
            assert "/api/cockpit/refresh-live" in intent_html
            assert "window.openai.callTool" not in intent_html

            with request.urlopen(url + "api/cockpit/state", timeout=5) as response:
                state_body = json.loads(response.read().decode("utf-8"))
            assert state_body["session_source"] == "live"
            assert state_body["session_snapshot_source"] == "focus_panel"

            refresh_req = request.Request(
                url + "api/cockpit/refresh-live",
                data=b"",
                method="POST",
            )
            with request.urlopen(refresh_req, timeout=5) as response:
                refresh_body = json.loads(response.read().decode("utf-8"))
            assert refresh_body["status"] == "ok"
            assert refresh_body["session_source"] == "live"
            assert refresh_body["summary"]["target_track_names"] == []

            req = request.Request(
                url + "api/cockpit/context",
                data=json.dumps({
                    "lane": "mix",
                    "target_query": "Keys / Piano",
                    "target_group": "keys_piano",
                    "section_scope": "intro",
                    "section_label": "Intro",
                }).encode("utf-8"),
                headers={"content-type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=5) as response:
                context_body = json.loads(response.read().decode("utf-8"))
            assert context_body["summary"]["target_track_names"] == ["keys", "piano"]

            req = request.Request(
                url + "api/cockpit/context",
                data=json.dumps({
                    "target_mode": "layer",
                    "target_query": "Intro High Motif",
                    "target_layer": "intro_high_motif",
                }).encode("utf-8"),
                headers={"content-type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=5) as response:
                layer_body = json.loads(response.read().decode("utf-8"))
            assert layer_body["layer_groups"][0]["key"] == "intro_high_motif"
            assert layer_body["target"]["matched_layer"] == "intro_high_motif"
            assert layer_body["summary"]["target_track_names"] == ["keys", "piano"]

            req = request.Request(
                url + "api/cockpit/focus",
                data=json.dumps({"track_indices": [1, 2], "label": "Keys / Piano"}).encode("utf-8"),
                headers={"content-type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=5) as response:
                focus_body = json.loads(response.read().decode("utf-8"))
            assert focus_body["summary"]["focused_track_count"] == 2

            req = request.Request(
                url + "api/cockpit/track-intent",
                data=json.dumps({
                    "track_index": 1,
                    "role": "chords",
                    "priority": "support",
                    "mix_intent": "Sit behind the vocal.",
                }).encode("utf-8"),
                headers={"content-type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=5) as response:
                intent_body = json.loads(response.read().decode("utf-8"))
            keys = next(track for track in intent_body["tracks"] if track["index"] == 1)
            assert keys["effective_role"] == "chords"
            assert keys["priority"] == "support"
            assert keys["intent"]["mix_intent"] == "Sit behind the vocal."
        finally:
            panel.stop()


def test_focus_panel_standalone_uses_snapshot_without_ableton(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", base)
        snapshot_store = SessionSnapshotStore(base / "current_session.json")
        session = _session([
            _track(0, "drums"),
            _track(1, "guit-rhth1", midi=True, audio=False),
        ])
        snapshot_store.save(session, source="test")
        service = AgentFocusService(base_dir=base)
        production_context = ProductionContextService(base_dir=base)
        panel = FocusPanelServer(
            ableton=None,
            focus_service=service,
            production_context_service=production_context,
            snapshot_store=snapshot_store,
            port=0,
        )
        try:
            url = panel.start()
            assert url

            with request.urlopen(url + "api/cockpit/state", timeout=5) as response:
                state = json.loads(response.read().decode("utf-8"))
            assert state["status"] == "ok"
            assert state["tracks"][1]["name"] == "guit-rhth1"
            assert state["session_source"] == "snapshot"
            assert state["session_snapshot_source"] == "test"

            req = request.Request(
                url + "api/cockpit/focus",
                data=json.dumps({"track_indices": [1], "label": "guitar target"}).encode("utf-8"),
                headers={"content-type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=5) as response:
                focused = json.loads(response.read().decode("utf-8"))
            assert focused["summary"]["focused_track_names"] == ["guit-rhth1"]
            assert service.get_focus(session)["focus"]["track_indices"] == [1]
        finally:
            panel.stop()
