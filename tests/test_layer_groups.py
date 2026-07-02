from __future__ import annotations

from types import SimpleNamespace

from mcp_server.persistence.layer_groups import LayerGroupService
from mcp_server.persistence.briefs import BriefService
from mcp_server.persistence.orchestration_queue import OrchestrationService
from mcp_server.persistence.production_context import ProductionContextService
from mcp_server.persistence.agent_focus import AgentFocusService
from mcp_server.persistence import track_annotations as annotation_store
from mcp_server.production_cockpit import (
    get_production_context,
    save_cockpit_layer_group,
)
from mcp_server.tools.tracks import (
    delete_layer_group,
    list_layer_groups,
    save_layer_group,
    set_track_annotation,
)


def _track(index: int, name: str, color: int = 0, midi: bool = True) -> dict:
    return {
        "index": index,
        "name": name,
        "color_index": color,
        "has_midi_input": midi,
        "has_audio_input": not midi,
    }


def _session(tracks: list[dict]) -> dict:
    return {
        "tempo": 116.0,
        "signature_numerator": 4,
        "signature_denominator": 4,
        "song_length": 64.0,
        "project_identity": {"file_path": "/tmp/layer-test.als"},
        "track_count": len(tracks),
        "tracks": tracks,
        "return_tracks": [],
        "scenes": [],
    }


class _Ableton:
    def __init__(self, session_info: dict):
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


def _ctx(tmp_path, session_info: dict):
    return SimpleNamespace(
        lifespan_context={
            "ableton": _Ableton(session_info),
            "agent_focus": AgentFocusService(base_dir=tmp_path),
            "briefs": BriefService(base_dir=tmp_path),
            "layer_groups": LayerGroupService(base_dir=tmp_path),
            "orchestration_queue": OrchestrationService(base_dir=tmp_path),
            "production_context": ProductionContextService(base_dir=tmp_path),
            "focus_panel_url": "http://127.0.0.1:9890/",
        }
    )


def test_layer_group_round_trips_and_resolves_after_reorder_and_rename(tmp_path):
    service = LayerGroupService(base_dir=tmp_path)
    original = _session([
        _track(0, "el-guit-intro", color=11),
        _track(1, "violins1-intro", color=12),
    ])

    saved = service.save_group(
        original,
        label="Intro Handoff",
        track_indices=[0, 1],
    )

    assert saved["layer"]["layer_id"] == "intro_handoff"
    assert saved["layer"]["track_names"] == ["el-guit-intro", "violins1-intro"]

    reordered = _session([
        _track(0, "drums", color=1),
        _track(1, "violins1-intro renamed", color=12),
        _track(2, "el-guit-intro renamed", color=11),
    ])
    listed = service.list_groups(reordered)["layer_groups"][0]

    assert listed["track_indices"] == [2, 1]
    assert listed["track_names"] == [
        "el-guit-intro renamed",
        "violins1-intro renamed",
    ]
    assert listed["unresolved_count"] == 0


def test_layer_group_reports_unresolved_members(tmp_path):
    service = LayerGroupService(base_dir=tmp_path)
    original = _session([_track(0, "glockenspiel", color=7)])
    service.save_group(original, label="Intro High Motif", track_indices=[0])

    missing = service.list_groups(_session([_track(0, "bass", color=2)]))
    group = missing["layer_groups"][0]

    assert group["track_indices"] == []
    assert group["unresolved_count"] == 1
    assert group["unresolved_members"][0]["resolution"]["status"] == "unresolved"


def test_layer_group_mcp_tools_increment_revision(tmp_path):
    session = _session([
        _track(0, "lead vox", color=8, midi=False),
        _track(1, "harm vox", color=9, midi=False),
    ])
    ctx = _ctx(tmp_path, session)

    saved = save_layer_group(
        ctx,
        label="Vocal Stack",
        track_indices=[0, 1],
        status="layered",
    )

    assert saved["layer"]["layer_id"] == "vocal_stack"
    assert saved["orchestration_revision"] == 1
    assert list_layer_groups(ctx)["layer_groups"][0]["track_names"] == [
        "lead vox",
        "harm vox",
    ]

    deleted = delete_layer_group(ctx, "vocal_stack")

    assert deleted["deleted"] is True
    assert deleted["orchestration_revision"] == 2
    assert list_layer_groups(ctx)["layer_groups"] == []


def test_store_layers_merge_with_annotation_tags_without_duplication(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            _track(0, "el-guit-intro", color=11),
            _track(1, "violins1-intro", color=12),
            _track(2, "violas1-intro", color=13),
        ]),
    )

    save_cockpit_layer_group(
        ctx,
        label="Intro Handoff",
        track_indices=[0, 1],
    )
    set_track_annotation(
        ctx,
        track_index=1,
        decision_state="committed",
        tags=["layer:intro_handoff"],
        source="legacy_layer_tag",
    )
    set_track_annotation(
        ctx,
        track_index=2,
        decision_state="committed",
        tags=["layer:intro_handoff"],
        source="legacy_layer_tag",
    )

    context = get_production_context(ctx)
    layer = next(
        group for group in context["layer_groups"]
        if group["key"] == "intro_handoff"
    )

    assert layer["track_names"] == [
        "el-guit-intro",
        "violins1-intro",
        "violas1-intro",
    ]
    assert layer["sources"] == ["store", "annotation_tag"]
    assert layer["count"] == 3
