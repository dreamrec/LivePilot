from __future__ import annotations

import asyncio
import builtins
import json
import os
import time
from types import SimpleNamespace

import pytest

import mcp_server.production_cockpit as production_cockpit
from mcp_server.persistence.agent_focus import AgentFocusService
from mcp_server.persistence.briefs import BriefService
from mcp_server.persistence.layer_groups import LayerGroupService
from mcp_server.persistence.orchestration_queue import OrchestrationService
from mcp_server.persistence.production_context import ProductionContextService
from mcp_server.persistence import track_annotations as annotation_store
from mcp_server.production_cockpit import (
    _backend_tool_map,
    _build_section_map,
    _render_intent_first_cockpit_html,
    adopt_cockpit_memory,
    archive_cockpit_brief,
    clear_cockpit_focus,
    complete_cockpit_brief,
    delete_cockpit_brief,
    get_production_context,
    list_cockpit_briefs,
    open_livepilot_production_cockpit,
    record_cockpit_brief_dispatch,
    save_cockpit_track_intent,
    save_cockpit_layer_group,
    save_production_context,
    send_cockpit_brief,
    rerun_cockpit_brief,
    set_cockpit_working_thread,
    set_cockpit_focus,
)
from mcp_server.tools.tracks import set_track_annotation


def _session(tracks: list[dict]) -> dict:
    return {
        "tempo": 116.0,
        "signature_numerator": 4,
        "signature_denominator": 4,
        "song_length": 72.0,
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
        if command == "get_cue_points":
            return {"cue_points": self.session_info.get("cue_points", [])}
        if command == "get_arrangement_clips":
            track_index = int(params["track_index"])
            track = next(
                item for item in self.session_info["tracks"]
                if item["index"] == track_index
            )
            return {
                "track_index": track_index,
                "clips": track.get("arrangement_clips", []),
            }
        if command == "get_track_info":
            track_index = int(params["track_index"])
            track = next(
                item for item in self.session_info["tracks"]
                if item["index"] == track_index
            )
            return {
                "index": track_index,
                "name": track["name"],
                "devices": [{"name": "Utility", "class_name": "AudioEffect"}],
                "clips": [{"name": "main"}],
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


def test_production_context_service_round_trips(tmp_path):
    service = ProductionContextService(base_dir=tmp_path)
    session = _session([
        {"index": 0, "name": "Drums", "color_index": 1, "has_midi_input": True},
    ])

    saved = service.save_state(
        session,
        lane="sound design",
        workflow_mode="audition",
        audition_required=True,
        audition_count=4,
        audition_scope="layer",
        protect=["preserve_notes", "preserve_timing"],
        reference="The Suburbs",
        notes="Keep the intro bleak.",
        target_query="guitars",
        target_mode="layer",
        target_layer="intro_handoff",
        section_scope="verse 1",
        section_label="Verse 1",
    )

    assert saved["state"]["lane"] == "sound_design"
    assert saved["state"]["workflow_mode"] == "audition"
    assert saved["state"]["audition_count"] == 4
    assert saved["state"]["audition_scope"] == "layer"
    assert saved["state"]["protect"] == ["preserve_notes", "preserve_timing"]
    assert saved["state"]["target_query"] == "guitars"
    assert saved["state"]["target_mode"] == "layer"
    assert saved["state"]["target_layer"] == "intro_handoff"
    assert saved["state"]["section"] == {
        "section_id": "manual_0_verse_1",
        "label": "Verse 1",
        "start_beat": None,
        "end_beat": None,
        "source": "manual",
    }
    assert service.get_state(session)["state"]["reference"] == "The Suburbs"

    track_scope = service.save_state(session, audition_scope="track")
    assert track_scope["state"]["audition_scope"] == "track"


def test_production_context_service_rejects_unknown_values(tmp_path):
    service = ProductionContextService(base_dir=tmp_path)
    session = _session([])

    with pytest.raises(ValueError, match="lane must be one of"):
        service.save_state(session, lane="mastering")

    with pytest.raises(ValueError, match="protect flags must be one of"):
        service.save_state(session, protect=["delete_everything"])

    with pytest.raises(ValueError, match="target_mode must be one of"):
        service.save_state(session, target_mode="sideways")

    with pytest.raises(ValueError, match="audition_count must be between"):
        service.save_state(session, audition_count=0)

    with pytest.raises(ValueError, match="audition_scope must be one of"):
        service.save_state(session, audition_scope="mix")


def test_cockpit_focus_context_and_track_intent_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "Drums", "color_index": 1, "has_midi_input": True},
            {"index": 1, "name": "Vox 1", "color_index": 2, "has_audio_input": True},
            {"index": 2, "name": "Bass", "color_index": 3, "has_midi_input": True},
        ]),
    )

    set_result = set_cockpit_focus(ctx, [1], label="lead vocal")
    assert set_result["focus"]["focus"]["track_indices"] == [1]

    save_production_context(
        ctx,
        lane="mix",
        workflow_mode="guided",
        audition_required=False,
        protect=["preserve_vocal", "preserve_timing"],
        reference="Arcade Fire raw ensemble",
        notes="Do not prettify the vocal.",
        target_query="vocals",
        section_scope="verse_1",
        section_label="Verse 1",
    )
    save_cockpit_track_intent(
        ctx,
        track_index=1,
        role="lead_vox",
        priority="foreground",
        notes="Main vocal anchor.",
        composition_intent="Communal chant center.",
        sound_design_intent="Raw, close, slightly frayed.",
        mix_intent="Forward but not glossy.",
        constraints=["preserve_timing"],
    )

    context = get_production_context(ctx, request_text="balance and level this vocal")
    assert "complete_cockpit_brief" in context["completion_contract"]
    assert context["summary"]["lane"] == "mix"
    assert context["summary"]["target_query"] == "vocals"
    assert context["summary"]["target_track_names"] == [
        "Vox 1",
    ]
    assert context["summary"]["section"]["section_id"] == "manual_0_verse_1"
    assert context["summary"]["section"]["label"] == "Verse 1"
    assert context["summary"]["focused_track_names"] == ["Vox 1"]
    assert context["summary"]["audition_required"] is False
    assert context["summary"]["audition_count"] == 3
    assert context["summary"]["audition_scope"] == "layer"
    assert context["route"]["request_type"] == "mix"

    vox = next(track for track in context["tracks"] if track["index"] == 1)
    assert vox["focused"] is True
    assert vox["group"] == "vocals"
    assert vox["effective_role"] == "lead_vox"
    assert vox["priority"] == "foreground"
    assert vox["intent"]["mix_intent"] == "Forward but not glossy."

    cleared = clear_cockpit_focus(ctx)
    assert cleared["focus"]["focus"]["is_empty"] is True


def test_cockpit_groups_and_targets_guitars(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
            {"index": 1, "name": "guit-rhth1", "color_index": 2, "has_midi_input": True},
            {"index": 2, "name": "electric-pretty", "color_index": 3, "has_midi_input": True},
            {"index": 3, "name": "13-lead-vox", "color_index": 4, "has_audio_input": True},
        ]),
    )

    save_production_context(ctx, target_query="guitars", section_scope="custom",
                            section_label="Bars 5-9", section_start_bar=5,
                            section_end_bar=9)
    context = get_production_context(ctx)

    guitar_group = next(group for group in context["track_groups"] if group["key"] == "guitars")
    assert guitar_group["count"] == 2
    assert context["target"]["matched_group"] == "guitars"
    assert context["target"]["track_names"] == ["guit-rhth1", "electric-pretty"]
    assert context["target"]["section"]["start_bar"] == 5.0
    assert context["target_tracks"][0]["group_label"] == "Guitars"


def test_cockpit_group_targets_exclude_utility_folders(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "voxnharms", "color_index": 1},
            {"index": 1, "name": "13-lead-vox", "color_index": 2, "has_audio_input": True},
            {"index": 2, "name": "tempo", "color_index": 3, "has_midi_input": True},
        ]),
    )

    set_track_annotation(
        ctx,
        track_index=0,
        role="organizational_folder",
        priority="utility",
        decision_state="committed",
        constraints=["folder_only", "do_not_target_for_mix_decisions"],
    )
    set_track_annotation(
        ctx,
        track_index=2,
        role="utility_map",
        priority="utility",
        decision_state="committed",
        constraints=["metadata_only", "do_not_target_for_mix_decisions"],
    )
    save_production_context(
        ctx,
        target_mode="instrument",
        target_query="Vocals",
        target_group="vocals",
    )

    context = get_production_context(ctx)

    vocal_group = next(group for group in context["track_groups"] if group["key"] == "vocals")
    assert vocal_group["track_names"] == ["13-lead-vox"]
    assert "maps" not in {group["key"] for group in context["track_groups"]}
    assert context["target"]["track_names"] == ["13-lead-vox"]
    assert context["summary"]["target_track_names"] == ["13-lead-vox"]


def test_cockpit_layer_groups_and_layer_target(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "elec-low-ampl", "color_index": 1, "has_midi_input": True},
            {"index": 1, "name": "ensemb-light", "color_index": 2, "has_midi_input": True},
            {"index": 2, "name": "born-run-gtr-hook-shadow", "color_index": 3, "has_midi_input": True},
            {"index": 3, "name": "ezbass", "color_index": 4, "has_midi_input": True},
        ]),
    )

    set_track_annotation(
        ctx,
        track_index=0,
        role="multi_role_guitar",
        decision_state="committed",
        source="user_confirmed_layer_map",
        tags=["layer:elec_low_multi_role", "layer:verse_lead_support"],
        relationships=[{
            "type": "linked_layer",
            "layer_id": "verse_lead_support",
        }],
    )
    set_track_annotation(
        ctx,
        track_index=1,
        role="brief_support_double",
        decision_state="committed",
        source="user_confirmed_layer_map",
        tags=["layer:elec_low_multi_role"],
    )
    set_track_annotation(
        ctx,
        track_index=2,
        role="rejected_shadow",
        decision_state="rejected",
        source="user_confirmed_layer_map",
        tags=["layer:verse_lead_fill"],
    )
    set_track_annotation(
        ctx,
        track_index=3,
        role="bass_foundation",
        decision_state="committed",
        source="user_confirmed_layer_map",
        tags=["layer:bass_foundation", "layer_status:bass_foundation:potential"],
    )
    save_production_context(
        ctx,
        target_mode="layer",
        target_layer="elec_low_multi_role",
        target_query="Elec Low Multi Role",
    )

    context = get_production_context(ctx)
    layer_groups = {group["key"]: group for group in context["layer_groups"]}

    assert layer_groups["elec_low_multi_role"]["track_names"] == [
        "elec-low-ampl",
        "ensemb-light",
    ]
    assert layer_groups["elec_low_multi_role"]["status"] == "layered"
    assert layer_groups["verse_lead_support"]["track_names"] == ["elec-low-ampl"]
    assert layer_groups["verse_lead_support"]["status"] == "singleton"
    assert layer_groups["bass_foundation"]["track_names"] == ["ezbass"]
    assert layer_groups["bass_foundation"]["status"] == "potential"
    assert layer_groups["bass_foundation"]["is_expandable"] is True
    assert "verse_lead_fill" not in layer_groups
    assert context["target"]["target_mode"] == "layer"
    assert context["target"]["matched_layer"] == "elec_low_multi_role"
    assert context["target"]["track_names"] == ["elec-low-ampl", "ensemb-light"]
    assert context["summary"]["target_layer"] == "elec_low_multi_role"


def test_cockpit_store_defined_layer_can_be_targeted(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "lead vox", "color_index": 1, "has_audio_input": True},
            {"index": 1, "name": "harm vox", "color_index": 2, "has_audio_input": True},
        ]),
    )

    saved = save_cockpit_layer_group(
        ctx,
        label="Vocal Stack",
        track_indices=[0, 1],
    )

    assert saved["layer_save"]["layer"]["layer_id"] == "vocal_stack"
    assert saved["layer_groups"][0]["source"] == "store"

    save_production_context(
        ctx,
        target_mode="layer",
        target_layer="vocal_stack",
        target_query="Vocal Stack",
    )
    context = get_production_context(ctx)

    assert context["target"]["matched_layer"] == "vocal_stack"
    assert context["target"]["track_names"] == ["lead vox", "harm vox"]
    assert context["summary"]["target_track_names"] == ["lead vox", "harm vox"]


def test_unresolved_store_layer_is_stale_not_normal_layer_chip(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    original = _session([
        {"index": 0, "name": "vanished pad", "color_index": 7, "has_midi_input": True},
    ]) | {"project_identity": {"file_path": "/tmp/current-song.als"}}
    ctx = _ctx(tmp_path, original)
    save_cockpit_layer_group(ctx, label="Old Pad", track_indices=[0])

    ctx.lifespan_context["ableton"].session_info = _session([
        {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
    ]) | {"project_identity": {"file_path": "/tmp/current-song.als"}}

    context = get_production_context(ctx)

    assert "old_pad" not in {group["key"] for group in context["layer_groups"]}
    assert context["stale_memory"]["layer_groups"][0]["key"] == "old_pad"
    assert context["memory_health"]["stale_layer_groups"] == 1


def test_foreign_set_brief_is_not_normal_current_pending_work(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    session = _session([
        {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
    ]) | {"project_identity": {"file_path": "/tmp/current-song.als"}}
    ctx = _ctx(tmp_path, session)

    ctx.lifespan_context["briefs"].create_brief(
        session,
        request_text="old sibling instruction",
        context_digest={
            "set_identity": {"name": "Old Song", "file_path": "/tmp/old-song.als"},
            "track_refs": [],
            "section": {"source": "whole_song", "label": "Whole song"},
        },
    )

    context = get_production_context(ctx)

    assert context["memory_health"]["foreign_or_unresolved_briefs"] == 1
    assert context["briefs"] == []
    assert context["stale_memory"]["briefs"][0]["aim_status"]["status"] == "foreign_set"


def test_multi_track_context_uses_saved_target_indices_and_refs(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
            {"index": 1, "name": "bass", "color_index": 2, "has_midi_input": True},
            {"index": 2, "name": "guitar", "color_index": 3, "has_audio_input": True},
        ]),
    )

    save_production_context(
        ctx,
        target_mode="tracks",
        target_label="rhythm section",
        target_track_indices=[0, 1],
    )

    context = get_production_context(ctx)

    assert context["target"]["target_mode"] == "tracks"
    assert context["target"]["track_indices"] == [0, 1]
    assert context["target"]["track_names"] == ["drums", "bass"]
    assert context["summary"]["target_track_names"] == ["drums", "bass"]


def test_cockpit_section_map_uses_cue_points(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "Drums", "color_index": 1, "has_midi_input": True},
        ]) | {
            "song_length": 80.0,
            "current_song_time": 20.0,
            "cue_points": [
                {"index": 0, "name": "Intro", "time": 0.0},
                {"index": 1, "name": "Verse 1", "time": 16.0},
                {"index": 2, "name": "Chorus", "time": 48.0},
            ],
        },
    )

    context = get_production_context(ctx)
    section_map = context["section_map"]

    assert section_map["source"] == "cue_points"
    assert section_map["source_label"] == "Arrangement markers"
    assert context["session"]["current_song_time"] == 20.0
    assert [section["label"] for section in section_map["sections"]] == [
        "Intro",
        "Verse 1",
        "Chorus",
    ]
    assert section_map["sections"][1]["start_bar"] == 5.0
    assert section_map["sections"][1]["end_bar"] == 13.0
    assert section_map["sections"][1]["is_current"] is True
    assert section_map["current_section_id"] == section_map["sections"][1]["id"]


def test_cockpit_section_map_uses_section_map_track(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {
                "index": 0,
                "name": "SECTION MAP",
                "color_index": 1,
                "has_midi_input": True,
                "arrangement_clips": [
                    {"name": "Intro", "start_time": 0.0, "end_time": 16.0, "length": 16.0},
                    {"name": "Verse 1", "start_time": 16.0, "end_time": 48.0, "length": 32.0},
                ],
            },
            {"index": 1, "name": "Piano", "color_index": 2, "has_midi_input": True},
        ]),
    )

    context = get_production_context(ctx)
    section_map = context["section_map"]

    assert section_map["source"] == "section_track"
    assert [section["label"] for section in section_map["sections"]] == [
        "Intro",
        "Verse 1",
    ]
    assert section_map["sections"][0]["bar_label"] == "Bars 1-5"
    assert section_map["sections"][1]["bar_label"] == "Bars 5-13"


def test_section_map_falls_back_to_saved_context():
    section_map = _build_section_map(
        {
            "tempo": 116,
            "signature_numerator": 4,
            "song_length": 64.0,
            "tracks": [],
        },
        {
            "section": {
                "section_id": "manual_16000_bars_5_9",
                "label": "Bars 5-9",
                "start_beat": 16.0,
                "end_beat": 32.0,
                "source": "manual",
            },
        },
    )

    assert section_map["source"] == "saved_context"
    assert section_map["sections"][0]["label"] == "Bars 5-9"
    assert section_map["sections"][0]["start_beat"] == 16.0
    assert section_map["sections"][0]["bar_label"] == "Bars 5-9"


def test_layer_status_can_target_one_layer_without_leaking(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "lead vox", "color_index": 1, "has_audio_input": True},
            {"index": 1, "name": "harm vox", "color_index": 2, "has_audio_input": True},
        ]),
    )

    set_track_annotation(
        ctx,
        track_index=0,
        role="lead_vocal",
        decision_state="committed",
        tags=["layer:vocal_stack", "layer:lead_vocal", "layer_status:lead_vocal:potential"],
    )
    set_track_annotation(
        ctx,
        track_index=1,
        role="harmony_vocal",
        decision_state="committed",
        tags=["layer:vocal_stack"],
    )

    layer_groups = {
        group["key"]: group
        for group in get_production_context(ctx)["layer_groups"]
    }

    assert layer_groups["lead_vocal"]["status"] == "potential"
    assert layer_groups["vocal_stack"]["status"] == "layered"


def test_send_cockpit_brief_creates_snapshot_task_and_layer_audition_job(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
            {"index": 1, "name": "el-guit-intro", "color_index": 2, "has_audio_input": True},
            {"index": 2, "name": "violins1-intro", "color_index": 3, "has_midi_input": True},
        ]),
    )
    set_track_annotation(
        ctx,
        track_index=1,
        role="intro_handoff_guitar",
        decision_state="committed",
        tags=["layer:intro_handoff"],
    )
    set_track_annotation(
        ctx,
        track_index=2,
        role="intro_handoff_strings",
        decision_state="committed",
        tags=["layer:intro_handoff"],
    )

    context = send_cockpit_brief(
        ctx,
        lane="sound_design",
        workflow_mode="audition",
        audition_required=True,
        audition_count=3,
        audition_scope="layer",
        request_text="make the intro handoff pop out",
        target_mode="layer",
        target_layer="intro_handoff",
        target_query="Intro Handoff",
        section_scope="intro",
        section_label="Intro",
    )

    submission = context["orchestration_submission"]
    brief = submission["brief"]
    assert submission["status"] == "ok"
    assert brief["request_text"] == "make the intro handoff pop out"
    assert submission["snapshot"]["brief"]["text"] == "make the intro handoff pop out"
    assert submission["snapshot"]["brief"]["brief_id"] == brief["brief_id"]
    assert "session_info" not in submission["snapshot"]["session_kernel"]
    assert submission["snapshot"]["session_kernel"]["session_ref"]["embedded"] is False
    assert "cockpit_context" not in submission["snapshot"]
    assert submission["snapshot"]["context_digest"]["track_indices"] == [1, 2]
    assert submission["snapshot"]["context_digest"]["layer_id"] == "intro_handoff"
    assert submission["snapshot"]["production_context_state"]["workflow_mode"] == "audition"
    assert submission["snapshot"]["track_intent_map"]["omitted_full_intent_map"] is True
    assert submission["task"]["agent_role"] == "audition_planner"
    assert submission["task"]["constraints"]["brief_id"] == brief["brief_id"]
    assert submission["task"]["scope"]["layer_id"] == "intro_handoff"
    assert submission["task"]["scope"]["brief_id"] == brief["brief_id"]
    assert submission["job"]["job_type"] == "audition"
    assert submission["job"]["status"] == "queued"
    assert submission["job"]["scope"]["brief_id"] == brief["brief_id"]
    assert submission["job"]["scope"]["source_track_indices"] == [1, 2]
    assert submission["job"]["audition_manifest"]["variant_count"] == 3
    assert brief["job_ids"] == [submission["job"]["job_id"]]
    assert context["orchestration"]["counts"]["queued_tasks"] == 1
    assert context["orchestration"]["counts"]["queued_jobs"] == 1


def test_layer_brief_uses_focused_subset_for_audition_scope(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
            {"index": 1, "name": "el-guit-intro", "color_index": 2, "has_audio_input": True},
            {"index": 2, "name": "violins1-intro", "color_index": 3, "has_midi_input": True},
        ]),
    )
    set_track_annotation(
        ctx,
        track_index=1,
        role="intro_handoff_guitar",
        decision_state="committed",
        tags=["layer:intro_handoff"],
    )
    set_track_annotation(
        ctx,
        track_index=2,
        role="intro_handoff_strings",
        decision_state="committed",
        tags=["layer:intro_handoff"],
    )
    set_cockpit_focus(ctx, track_indices=[1], label="guitar only")

    context = send_cockpit_brief(
        ctx,
        lane="mix",
        workflow_mode="audition",
        audition_required=True,
        audition_count=2,
        audition_scope="layer",
        request_text="make only the guitar pop out",
        target_mode="layer",
        target_layer="intro_handoff",
        target_query="Intro Handoff",
    )

    submission = context["orchestration_submission"]
    assert submission["snapshot"]["brief"]["target_track_names"] == ["el-guit-intro", "violins1-intro"]
    assert submission["brief"]["context_digest"]["track_indices"] == [1]
    assert submission["task"]["scope"]["track_indices"] == [1]
    assert submission["job"]["scope"]["source_track_indices"] == [1]


def test_send_cockpit_brief_snapshot_stays_compact_with_large_session(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    tracks = []
    for index in range(48):
        tracks.append({
            "index": index,
            "name": f"track-{index}",
            "color_index": index % 8,
            "has_audio_input": True,
            "arrangement_clips": [
                {
                    "name": f"clip-{clip_index}",
                    "start_time": clip_index * 4,
                    "duration": 4,
                    "notes": "x" * 512,
                }
                for clip_index in range(20)
            ],
        })
    ctx = _ctx(tmp_path, _session(tracks))

    context = send_cockpit_brief(
        ctx,
        lane="mix",
        workflow_mode="guided",
        request_text="make track 2 pop out but keep the notes and timing",
        target_mode="query",
        target_query="track-2",
    )

    snapshot = context["orchestration_submission"]["snapshot"]
    encoded = json.dumps(snapshot, sort_keys=True)
    assert len(encoded) < 50000
    assert "arrangement_clips" not in encoded
    assert "session_info" not in snapshot["session_kernel"]
    assert "cockpit_context" not in snapshot
    assert 2 in snapshot["context_digest"]["track_indices"]


def test_brief_context_digest_carries_set_identity_and_aim_survives_reorder(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    session = _session([
        {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
        {"index": 1, "name": "el-guit-intro", "color_index": 2, "has_audio_input": True},
    ])
    session["project_identity"] = {
        "name": "Aim Test",
        "file_path": "/tmp/aim-test.als",
    }
    ctx = _ctx(tmp_path, session)

    context = send_cockpit_brief(
        ctx,
        lane="mix",
        workflow_mode="guided",
        audition_required=False,
        request_text="make the guitar easier to hear",
        target_mode="query",
        target_query="el-guit-intro",
    )
    digest = context["orchestration_submission"]["brief"]["context_digest"]
    assert digest["set_identity"] == {
        "name": "Aim Test",
        "file_path": "/tmp/aim-test.als",
        "track_count": 2,
    }

    reordered = _session([
        {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
        {"index": 1, "name": "scratch", "color_index": 9, "has_audio_input": True},
        {"index": 2, "name": "el-guit-intro", "color_index": 2, "has_audio_input": True},
    ])
    reordered["project_identity"] = dict(session["project_identity"])
    ctx.lifespan_context["ableton"].session_info = reordered

    brief = list_cockpit_briefs(ctx)["briefs"][0]

    assert brief["aim_status"]["status"] == "current"
    assert brief["aim_status"]["resolved_track_indices"] == [2]


def test_brief_aim_status_reports_degraded_and_foreign_set(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    session = _session([
        {"index": 0, "name": "el-guit-intro", "color_index": 2, "has_audio_input": True},
        {"index": 1, "name": "violins1-intro", "color_index": 3, "has_midi_input": True},
    ])
    session["project_identity"] = {"file_path": "/tmp/current-song.als"}
    ctx = _ctx(tmp_path, session)

    send_cockpit_brief(
        ctx,
        lane="sound_design",
        workflow_mode="guided",
        audition_required=False,
        request_text="make the intro handoff speak",
        target_mode="query",
        target_query="intro",
    )
    reduced = _session([
        {"index": 0, "name": "el-guit-intro", "color_index": 2, "has_audio_input": True},
        {"index": 1, "name": "bass", "color_index": 8, "has_midi_input": True},
    ])
    reduced["project_identity"] = dict(session["project_identity"])
    ctx.lifespan_context["ableton"].session_info = reduced

    degraded = list_cockpit_briefs(ctx)["briefs"][0]["aim_status"]

    assert degraded["status"] == "degraded"
    assert degraded["resolved"] == 1
    assert degraded["total"] == 2
    assert degraded["unresolved_refs"][0]["name"] == "violins1-intro"

    service = ctx.lifespan_context["briefs"]
    service.create_brief(
        reduced,
        request_text="old sibling-set aim",
        context_digest={
            "set_identity": {
                "name": "Other Song",
                "file_path": "/tmp/other-song.als",
                "track_count": 37,
            },
            "track_refs": [],
            "section": {"source": "whole_song", "label": "Whole song"},
        },
    )

    brief_listing = list_cockpit_briefs(ctx)
    foreign = brief_listing["stale_briefs"][0]["aim_status"]

    assert foreign["status"] == "foreign_set"
    assert foreign["label"] == "Other Song"
    assert brief_listing["briefs"][0]["aim_status"]["status"] == "degraded"


def test_rerun_brief_prefills_resolved_aim_and_child_lineage(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    session = _session([
        {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
        {"index": 1, "name": "el-guit-intro", "color_index": 2, "has_audio_input": True},
    ])
    session["project_identity"] = {"file_path": "/tmp/rerun-song.als"}
    ctx = _ctx(tmp_path, session)
    context = send_cockpit_brief(
        ctx,
        lane="mix",
        workflow_mode="guided",
        audition_required=False,
        request_text="make the guitar easier to hear",
        target_mode="query",
        target_query="el-guit-intro",
        evidence_budget="quick",
    )
    source = context["orchestration_submission"]["brief"]

    moved = _session([
        {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
        {"index": 1, "name": "bass", "color_index": 5, "has_midi_input": True},
        {"index": 2, "name": "el-guit-intro", "color_index": 2, "has_audio_input": True},
    ])
    moved["project_identity"] = dict(session["project_identity"])
    ctx.lifespan_context["ableton"].session_info = moved

    package = rerun_cockpit_brief(ctx, source["brief_id"])

    assert package["parent_brief_id"] == source["brief_id"]
    assert package["thread_id"] == source["thread_id"]
    assert package["request_text"] == "make the guitar easier to hear"
    assert package["evidence_budget"] == "quick"
    assert package["resolved_track_indices"] == [2]

    child_context = send_cockpit_brief(
        ctx,
        lane=package["lane"],
        workflow_mode=package["workflow_mode"],
        audition_required=False,
        request_text=package["request_text"],
        target_mode=package["target_mode"],
        target_query=package["target_query"],
        parent_brief_id=package["parent_brief_id"],
        thread_id=package["thread_id"],
    )
    child = child_context["orchestration_submission"]["brief"]

    assert child["parent_brief_id"] == source["brief_id"]
    assert child["thread_id"] == source["thread_id"]


def test_adopt_cockpit_memory_imports_suggested_store(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    original = _session([
        {"index": 0, "name": "Drums", "color_index": 1, "has_midi_input": True},
        {"index": 1, "name": "Bass", "color_index": 2, "has_audio_input": True},
        {"index": 2, "name": "Piano", "color_index": 3, "has_midi_input": True},
        {"index": 3, "name": "Guitar", "color_index": 4, "has_audio_input": True},
    ])
    original["project_identity"] = {"file_path": "/tmp/original-memory.als"}
    original_id = annotation_store.annotation_project_id_for_session(original, tmp_path)
    store = annotation_store.TrackAnnotationStore(original_id, base_dir=tmp_path)
    for track in original["tracks"]:
        store.upsert({
            "scope": "track",
            "role": "part",
            "track_ref": {
                "last_seen_index": track["index"],
                "name": track["name"],
                "signature": annotation_store.make_track_signature(track),
            },
        })

    sibling = _session([
        {"index": 0, "name": "Drums", "color_index": 1, "has_midi_input": True},
        {"index": 1, "name": "Guide", "color_index": 9, "has_audio_input": True},
    ])
    sibling["project_identity"] = {"file_path": "/tmp/sibling-memory.als"}
    ctx = _ctx(tmp_path, sibling)
    before = get_production_context(ctx)

    assert before["memory_suggestion"]["project_id"] == original_id

    adopted = adopt_cockpit_memory(ctx, original_id)

    assert adopted["memory_adoption"]["project_id"] == original_id
    assert adopted["project_id"] == original_id
    assert adopted["memory_suggestion"] is None


def test_archive_cockpit_brief_marks_abandoned_without_revision_bump(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
        ]),
    )
    context = send_cockpit_brief(
        ctx,
        lane="mix",
        workflow_mode="guided",
        audition_required=False,
        request_text="temporary saved brief",
    )
    brief_id = context["orchestration_submission"]["brief"]["brief_id"]
    store = ctx.lifespan_context["orchestration_queue"].store_for_session(
        ctx.lifespan_context["ableton"].session_info
    )
    before_revision = store.get_revision()

    archived = archive_cockpit_brief(ctx, brief_id=brief_id)

    assert store.get_revision() == before_revision
    assert archived["brief_archive"]["brief"]["outcome"]["status"] == "abandoned"
    assert archived["briefs"][0]["status"] == "abandoned"
    assert archived["briefs"][0]["outcome"]["summary"] == "archived from cockpit"

    compat = delete_cockpit_brief(ctx, brief_id=brief_id)

    assert compat["briefs"][0]["status"] == "abandoned"


def test_brief_dispatch_prompt_links_and_stamp_round_trip(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "el-guit-intro", "color_index": 1, "has_audio_input": True},
        ]),
    )

    context = send_cockpit_brief(
        ctx,
        lane="mix",
        workflow_mode="guided",
        audition_required=False,
        request_text="make the guitar easier to hear",
        target_mode="query",
        target_query="el-guit-intro",
    )

    submission = context["orchestration_submission"]
    brief = submission["brief"]
    dispatch = submission["dispatch"]
    assert context["dispatch"]["prompt_template"].startswith("Pick up LivePilot cockpit brief")
    assert f"#{brief['seq']}" in dispatch["prompt"]
    assert brief["brief_id"] in dispatch["prompt"]
    assert "get_production_context / list_cockpit_briefs" in dispatch["prompt"]
    assert dispatch["deeplink_new_thread"].startswith("codex://threads/new?prompt=")
    assert "path=" in dispatch["deeplink_new_thread"]
    assert context["briefs"][0]["dispatch_action"]["prompt"] == dispatch["prompt"]

    stamped = record_cockpit_brief_dispatch(
        ctx,
        brief_id=brief["brief_id"],
        method="deeplink",
    )

    assert stamped["brief_dispatch"]["brief"]["dispatch"]["method"] == "deeplink"
    assert stamped["briefs"][0]["dispatch"]["method"] == "deeplink"
    assert stamped["briefs"][0]["dispatch_action"]["prompt"] == dispatch["prompt"]


def test_complete_cockpit_brief_writes_learnings_and_rejected_options(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "el-guit-intro", "color_index": 1, "has_audio_input": True},
        ]),
    )
    context = send_cockpit_brief(
        ctx,
        lane="mix",
        workflow_mode="guided",
        audition_required=False,
        request_text="make the guitar easier to hear",
    )
    brief_id = context["orchestration_submission"]["brief"]["brief_id"]

    completed = complete_cockpit_brief(
        ctx,
        brief_id=brief_id,
        status="done",
        summary="Kept edge saturation and rejected the chorusy version.",
        learnings=[{
            "track_index": 0,
            "role": "intro_guitar_hook",
            "priority": "foreground",
            "mix_intent": "Speak clearly without covering the vocal.",
            "decision_state": "committed",
            "rejected_option": {
                "label": "wide chorus wash",
                "reason": "Blurred the handoff and felt too polished.",
            },
        }],
    )
    annotation = completed["context"]["track_intent_map"]["tracks"][0]["annotations"][0]

    assert completed["brief"]["outcome"]["status"] == "done"
    assert completed["brief"]["outcome"]["learnings_count"] == 1
    assert completed["learning_results"][0]["ok"] is True
    assert completed["orchestration_revision"] == 1
    assert annotation["source"] == "brief_completion"
    assert annotation["role"] == "intro_guitar_hook"
    assert annotation["mix_intent"] == "Speak clearly without covering the vocal."
    assert annotation["decision_state"] == "committed"
    assert annotation["options"] == [{
        "label": "wide chorus wash",
        "decision_state": "rejected",
        "notes": "Blurred the handoff and felt too polished.",
    }]
    assert "Rejected wide chorus wash" in annotation["notes"]
    assert completed["context"]["briefs"][0]["status"] == "done"


def test_complete_cockpit_brief_allows_empty_learnings(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
        ]),
    )
    context = send_cockpit_brief(
        ctx,
        lane="mix",
        workflow_mode="guided",
        audition_required=False,
        request_text="analyze the balance",
    )
    brief_id = context["orchestration_submission"]["brief"]["brief_id"]

    completed = complete_cockpit_brief(
        ctx,
        brief_id=brief_id,
        status="done",
        summary="Analysis only; no song-memory changes needed.",
        learnings=[],
    )

    assert completed["brief"]["outcome"]["status"] == "done"
    assert completed["brief"]["outcome"]["learnings_count"] == 0
    assert completed["learning_results"] == []
    assert completed["context"]["briefs"][0]["status"] == "done"


def test_complete_cockpit_brief_isolates_per_learning_errors(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
        ]),
    )
    context = send_cockpit_brief(
        ctx,
        lane="mix",
        workflow_mode="guided",
        audition_required=False,
        request_text="tighten the drums",
    )
    brief_id = context["orchestration_submission"]["brief"]["brief_id"]

    completed = complete_cockpit_brief(
        ctx,
        brief_id=brief_id,
        status="done",
        summary="Recorded the usable drum learning.",
        learnings=[
            {"track_index": 999, "role": "bad"},
            {"track_index": 0, "role": "drum_foundation", "decision_state": "committed"},
        ],
    )

    assert completed["learning_results"][0]["ok"] is False
    assert "Track index 999" in completed["learning_results"][0]["error"]
    assert completed["learning_results"][1]["ok"] is True
    assert completed["brief"]["outcome"]["learnings_count"] == 1
    assert completed["context"]["track_intent_map"]["tracks"][0]["effective_role"] == "drum_foundation"


def test_working_thread_dispatch_actions_and_status(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    sessions_dir = tmp_path / "codex_sessions"
    rollout_dir = sessions_dir / "2026" / "07" / "03"
    rollout_dir.mkdir(parents=True)
    thread_id = "019f2903-7fd2-79b3-9ae0-e46a767c326d"
    (rollout_dir / f"rollout-2026-07-03T13-25-23-{thread_id}.jsonl").write_text(
        "not parsed\n"
    )
    monkeypatch.setattr(production_cockpit, "_CODEX_SESSIONS_DIR", sessions_dir)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "el-guit-intro", "color_index": 1, "has_audio_input": True},
        ]),
    )

    save_production_context(
        ctx,
        target_mode="query",
        target_query="el-guit-intro",
        working_thread={"thread_id": thread_id, "label": "Verse pass"},
        evidence_budget="quick",
    )
    context = send_cockpit_brief(
        ctx,
        lane="mix",
        workflow_mode="guided",
        audition_required=False,
        request_text="make the guitar easier to hear",
        target_mode="query",
        target_query="el-guit-intro",
        evidence_budget="quick",
    )

    state = context["production_context"]["state"]
    action = context["briefs"][0]["dispatch_action"]
    task = context["orchestration_submission"]["task"]

    assert context["production_context"]["working_thread_status"] == "live"
    assert state["working_thread"]["thread_id"] == thread_id
    assert state["evidence_budget"] == "quick"
    assert action["deeplink_working_thread"] == f"codex://threads/{thread_id}"
    assert action["sweep_prompt"].startswith("Pick up the unseen LivePilot")
    assert action["existing_thread_prefill"] is False
    assert action["existing_thread_prefill_status"] == "unverified_safe_fallback"
    assert task["constraints"]["evidence_budget"] == "quick"
    assert context["orchestration_submission"]["brief"]["context_digest"]["evidence_budget"] == "quick"


def test_working_thread_status_missing_when_rollout_absent(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    sessions_dir = tmp_path / "codex_sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(production_cockpit, "_CODEX_SESSIONS_DIR", sessions_dir)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
        ]),
    )

    context = save_production_context(
        ctx,
        working_thread={
            "thread_id": "019f2903-7fd2-79b3-9ae0-e46a767c326d",
            "label": "Missing thread",
        },
    )

    assert context["production_context"]["working_thread_status"] == "missing"
    assert context["briefs"] == []


def test_dispatched_thread_id_is_captured_from_single_recent_rollout(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    sessions_dir = tmp_path / "codex_sessions"
    rollout_dir = sessions_dir / "2026" / "07" / "03"
    rollout_dir.mkdir(parents=True)
    monkeypatch.setattr(production_cockpit, "_CODEX_SESSIONS_DIR", sessions_dir)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "el-guit-intro", "color_index": 1, "has_audio_input": True},
        ]),
    )
    context = send_cockpit_brief(
        ctx,
        lane="mix",
        workflow_mode="guided",
        audition_required=False,
        request_text="make the guitar easier to hear",
    )
    brief_id = context["orchestration_submission"]["brief"]["brief_id"]
    stamped = record_cockpit_brief_dispatch(ctx, brief_id=brief_id, method="deeplink")
    at_ms = stamped["brief_dispatch"]["brief"]["dispatch"]["at_ms"]
    thread_id = "019f2903-7fd2-79b3-9ae0-e46a767c326d"
    path = rollout_dir / f"rollout-2026-07-03T13-25-23-{thread_id}.jsonl"
    path.write_text("not parsed\n")
    os.utime(path, ((at_ms + 1000) / 1000.0, (at_ms + 1000) / 1000.0))

    captured = get_production_context(ctx)

    assert captured["captured_thread"] == {
        "brief_id": brief_id,
        "thread_id": thread_id,
    }
    brief = captured["briefs"][0]
    assert brief["dispatch"]["codex_thread_id"] == thread_id
    assert brief["dispatch_action"]["prompt"].startswith("Pick up LivePilot cockpit brief")


def test_rollout_capture_ignores_ambiguous_and_old_candidates(
    tmp_path,
    monkeypatch,
):
    sessions_dir = tmp_path / "codex_sessions"
    rollout_dir = sessions_dir / "2026" / "07" / "03"
    rollout_dir.mkdir(parents=True)
    monkeypatch.setattr(production_cockpit, "_CODEX_SESSIONS_DIR", sessions_dir)
    now_ms = int(time.time() * 1000)
    first = "019f2903-7fd2-79b3-9ae0-e46a767c326d"
    second = "019f2904-7fd2-79b3-9ae0-e46a767c326d"
    old = "019f2905-7fd2-79b3-9ae0-e46a767c326d"
    monkeypatch.setattr(
        production_cockpit,
        "_rollout_candidate_time_seconds",
        lambda path: path.stat().st_mtime,
    )
    for thread_id in (first, second, old):
        path = rollout_dir / f"rollout-2026-07-03T13-25-23-{thread_id}.jsonl"
        path.write_text("not parsed\n")
        mtime = (now_ms + 1000) / 1000.0
        if thread_id == old:
            mtime = (now_ms - 10_000) / 1000.0
        os.utime(path, (mtime, mtime))

    assert sorted(production_cockpit._recent_rollout_thread_candidates(now_ms)) == [
        first,
        second,
    ]
    for path in rollout_dir.glob(f"*-{second}.jsonl"):
        path.unlink()
    assert production_cockpit._recent_rollout_thread_candidates(now_ms) == [first]


def test_rollout_candidate_time_prefers_birthtime_when_available(monkeypatch):
    class FakeStat:
        st_birthtime = 123.0
        st_mtime = 456.0

    class FakePath:
        def stat(self):
            return FakeStat()

    assert production_cockpit._rollout_candidate_time_seconds(FakePath()) == 123.0


def test_rollout_scan_does_not_open_rollout_contents(tmp_path, monkeypatch):
    sessions_dir = tmp_path / "codex_sessions"
    rollout_dir = sessions_dir / "2026" / "07" / "03"
    rollout_dir.mkdir(parents=True)
    monkeypatch.setattr(production_cockpit, "_CODEX_SESSIONS_DIR", sessions_dir)
    thread_id = "019f2903-7fd2-79b3-9ae0-e46a767c326d"
    path = rollout_dir / f"rollout-2026-07-03T13-25-23-{thread_id}.jsonl"
    path.write_text("would fail if read\n")
    now_ms = int(time.time() * 1000)
    os.utime(path, ((now_ms + 1000) / 1000.0, (now_ms + 1000) / 1000.0))

    def forbidden_open(*_args, **_kwargs):
        raise AssertionError("rollout contents must not be opened")

    monkeypatch.setattr(builtins, "open", forbidden_open)

    assert production_cockpit._recent_rollout_thread_candidates(now_ms) == [thread_id]


def test_set_cockpit_working_thread_round_trips_pin_and_clear(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
        ]),
    )
    thread_id = "019f2903-7fd2-79b3-9ae0-e46a767c326d"

    pinned = set_cockpit_working_thread(
        ctx,
        thread_id=thread_id,
        label="Intro pass",
    )
    cleared = set_cockpit_working_thread(ctx, clear=True)

    assert pinned["working_thread_update"]["status"] == "pinned"
    assert pinned["production_context"]["state"]["working_thread"]["thread_id"] == thread_id
    assert cleared["working_thread_update"]["status"] == "cleared"
    assert cleared["production_context"]["state"]["working_thread"] is None


def test_send_cockpit_brief_creates_track_scoped_audition_job(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "drums", "color_index": 1, "has_audio_input": True},
            {"index": 1, "name": "el-guit-intro", "color_index": 2, "has_audio_input": True},
        ]),
    )

    context = send_cockpit_brief(
        ctx,
        lane="mix",
        workflow_mode="audition",
        audition_required=True,
        audition_count=2,
        audition_scope="track",
        request_text="make this guitar speak",
        target_mode="query",
        target_query="el-guit-intro",
    )

    submission = context["orchestration_submission"]
    assert submission["job"]["job_type"] == "audition"
    assert submission["job"]["scope"]["target_mode"] == "track"
    assert submission["job"]["scope"]["source_track_indices"] == [1]
    assert submission["job"]["audition_manifest"]["scope_type"] == "track"
    assert submission["job"]["audition_manifest"]["variant_count"] == 2


def test_cockpit_mcp_read_tools_are_registered_unconditionally():
    from mcp_server.server import mcp

    async def _run():
        tools = await mcp.list_tools()
        names = {tool.name for tool in tools}
        assert "open_livepilot_production_cockpit" in names
        assert "get_production_context" in names
        assert "list_cockpit_briefs" in names
        assert "complete_cockpit_brief" in names
        assert not (set(_backend_tool_map().values()) & names)

    asyncio.run(_run())


def test_open_cockpit_returns_browser_url(tmp_path, monkeypatch):
    monkeypatch.setattr(annotation_store, "_PROJECTS_DIR", tmp_path)
    ctx = _ctx(
        tmp_path,
        _session([
            {"index": 0, "name": "Intro Texture", "color_index": 4, "has_midi_input": True},
        ]),
    )

    result = open_livepilot_production_cockpit(ctx)

    assert result.structured_content["cockpit_url"] == "http://127.0.0.1:9890/cockpit/intent"
    assert not result.meta
    assert result.structured_content["tracks"][0]["name"] == "Intro Texture"


def test_intent_cockpit_templates_render_as_single_primary_ui():
    html = _render_intent_first_cockpit_html(transport="http")

    assert "__INTENT_CSS__" not in html
    assert "__INTENT_JS__" not in html
    assert "__BACKEND_TOOLS__" not in html
    assert "__CALL_TOOL_JS__" not in html
    assert "Save brief for Codex" in html
    assert "Suggestions" in html
    assert "Song Layers" in html
    assert "Apply Brief" not in html
    assert html.count('class="primary"') == 1


def test_intent_first_cockpit_renders_http_backend_contract():
    html = _render_intent_first_cockpit_html(transport="http")

    assert "LivePilot Intent Cockpit" in html
    assert "id=\"outputModeRow\"" in html
    assert "let outputModeUserOverride = false" in html
    assert "if (!outputModeUserOverride) outputMode = outputModeFromWorkflow(ctx.workflow_mode)" in html
    assert "id=\"auditionCount\"" in html
    assert "Choose a layer or track target before saving auditions." in html
    assert "audition_count: auditionCount()" in html
    assert 'audition_scope: targetMode() === "layer" ? "layer" : "track"' in html
    assert "request_text: text" in html
    assert "notes: appendNote" not in html
    assert "function appendNote" not in html
    assert "Save brief for Codex" in html
    assert "Clear target" in html
    assert "Save selection as layer" in html
    assert "id=\"deleteLayer\"" in html
    assert "button:disabled" in html
    assert "function laneInferenceText(text)" in html
    assert "cut through|stand out" in html
    assert "pop|punch|forward" in html
    assert "function previewProtect(text)" in html
    assert "(inferred)" in html
    assert "Section: ${" in html
    assert "Song Sections" in html
    assert "id=\"songStrip\"" in html
    assert "id=\"sectionRow\"" not in html
    assert "async function chooseSection(sectionId)" in html
    assert "section: savedSection()" in html
    assert '"#wholeSongButton").addEventListener("click", chooseWholeSong)' in html
    assert "Suggestions" in html
    assert "Song Layers" in html
    assert "function savedPickerMode()" in html
    assert "let targetModeUserOverride = false" in html
    assert "function pickerModeAfterRefresh(modeBeforeRefresh)" in html
    assert "return targetModeUserOverride ? pickerMode() : (modeBeforeRefresh || savedPickerMode())" in html
    assert "targetModeUserOverride = true" in html
    assert "targetModeDraft = savedMode" not in html
    assert "Needs you" in html
    assert "id=\"needsYouCard\"" in html
    assert "id=\"needsYouBadge\"" in html
    assert "id=\"needsYouItems\"" in html
    assert "data-mode=\"track\"" in html
    assert "Choose target" not in html
    assert "async function clearTarget()" in html
    assert '"#clearTarget").addEventListener("click", clearTarget)' in html
    assert "Refresh from Ableton" in html
    assert "/api/cockpit/state" in html
    assert "/api/cockpit/context" in html
    assert "/api/cockpit/brief" in html
    assert "/api/cockpit/brief-archive" in html
    assert "/api/cockpit/brief-rerun" in html
    assert "/api/cockpit/adopt-memory" in html
    assert "/api/cockpit/briefs/delete" in html
    assert "/api/cockpit/brief-dispatch" in html
    assert "/api/cockpit/working-thread" in html
    assert "/api/cockpit/focus" in html
    assert "/api/cockpit/layers/save" in html
    assert "/api/cockpit/layers/delete" in html
    assert "/api/cockpit/refresh-live" in html
    assert "async function saveCurrentLayer()" in html
    assert "function trackLayerChips(track)" in html
    assert "function renderNeedsYou()" in html
    assert "function renderBriefFeed()" in html
    assert "function briefAgeText(brief)" in html
    assert "saved ${formatAge" in html
    assert "function briefStatusText(brief)" in html
    assert "done · ${count} learning" in html
    assert "button.brief-action" in html
    assert "Re-run" in html
    assert "Archive" in html
    assert "New Codex thread" in html
    assert "Open working thread" in html
    assert "Copy prompt" in html
    assert "id=\"workingThreadPill\"" in html
    assert "id=\"pinCapturedThread\"" in html
    assert "id=\"clearWorkingThread\"" in html
    assert "id=\"evidenceBudget\"" in html
    assert "Evidence budget" in html
    assert "deeplink_working_thread" in html
    assert "deeplink_existing" in html
    assert "function dispatchStatusText(brief)" in html
    assert "recordBriefDispatch" in html
    assert "function renderWorkingThread()" in html
    assert "function pinCapturedThread()" in html
    assert "function openWorkingThread(briefId, href)" in html
    assert "copyBriefPrompt" in html
    assert "async function handleTrackRowClick(index)" in html
    assert "Layer focus updated" in html
    assert "submitAuditionAction" in html
    assert "/api/cockpit/auditions/action" in html
    assert "setInterval(() =>" in html
    assert "window.openai.callTool" not in html
