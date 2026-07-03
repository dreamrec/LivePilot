"""Regression tests for keeping pytest away from real ~/.livepilot state."""

from __future__ import annotations

import json
from pathlib import Path


def _session_info() -> dict:
    return {
        "tempo": 139.0,
        "signature_numerator": 4,
        "signature_denominator": 4,
        "song_length": 64.0,
        "project_identity": {
            "file_path": "/tmp/livepilot-test-suite/project.als",
        },
        "tracks": [
            {
                "index": 0,
                "name": "Piano",
                "color_index": 4,
                "has_midi_input": True,
                "has_audio_input": False,
            },
            {
                "index": 1,
                "name": "Guitar",
                "color_index": 7,
                "has_midi_input": False,
                "has_audio_input": True,
            },
        ],
        "return_tracks": [],
        "scenes": [],
    }


def test_default_persistence_uses_livepilot_home_override(tmp_path, monkeypatch):
    fake_home = tmp_path / "fake-home"
    isolated_home = tmp_path / "isolated-livepilot-home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("LIVEPILOT_HOME", str(isolated_home))

    from mcp_server.lifecycle_log import lifecycle_event
    from mcp_server.memory.technique_store import TechniqueStore
    from mcp_server.persistence.agent_focus import AgentFocusService
    from mcp_server.persistence.briefs import BriefService
    from mcp_server.persistence.layer_groups import LayerGroupService
    from mcp_server.persistence.orchestration_queue import OrchestrationService
    from mcp_server.persistence.production_context import ProductionContextService
    from mcp_server.persistence.project_store import ProjectStore
    from mcp_server.persistence.session_snapshot import SessionSnapshotStore
    from mcp_server.persistence.taste_store import PersistentTasteStore
    from mcp_server.persistence.track_annotations import (
        TrackAnnotationStore,
        annotation_project_id_for_session,
    )
    from mcp_server.runtime.capability_probe import probe_capabilities
    from mcp_server.splice_client.http_bridge import SpliceHTTPConfig
    from mcp_server.splice_client.quota import DailyQuotaTracker

    session = _session_info()
    project_id = annotation_project_id_for_session(session)

    TrackAnnotationStore(project_id).upsert({
        "track_index": 0,
        "track_signature": {"name": "Piano", "color_index": 4},
        "role": "lead",
    })
    BriefService().store_for_session(session).create_brief({
        "request_text": "isolation regression",
    })
    BriefService().stamp_reader(session, "codex")
    AgentFocusService().set_focus(session, track_indices=[0], label="Piano")
    ProductionContextService().save_state(session, lane="mix", target_query="Piano")
    LayerGroupService().store_for_session(session).upsert_layer({
        "layer_id": "test_layer",
        "label": "Test Layer",
        "member_refs": [{"track_index": 0, "track_name": "Piano"}],
    })
    OrchestrationService().create_snapshot(session, brief={"brief_id": "brief-test"})
    ProjectStore("manual_project").save_thread({"thread_id": "thread-test"})
    SessionSnapshotStore().save(session, source="test")
    PersistentTasteStore().record_move_outcome("move.test", "mix", kept=True)
    TechniqueStore().save(
        name="Test Technique",
        type="mix_template",
        qualities={"summary": "test"},
        payload={"ok": True},
    )
    DailyQuotaTracker().record_download("hash", "sample.wav")
    (isolated_home / "splice.json").write_text(
        json.dumps({"base_url": "https://example.invalid"}),
        encoding="utf-8",
    )
    assert SpliceHTTPConfig.from_env().base_url == "https://example.invalid"
    lifecycle_event("test_livepilot_home_isolation")

    persistence = probe_capabilities()["persistence"]
    assert persistence["status"] == "ok"
    assert not (fake_home / ".livepilot").exists()
    assert (isolated_home / "projects" / project_id / "briefs.json").is_file()
    assert (isolated_home / "current_session.json").is_file()
    assert (isolated_home / "taste.json").is_file()
    assert (isolated_home / "memory" / "techniques.json").is_file()
    assert (isolated_home / "splice_quota.json").is_file()
    assert (isolated_home / "logs" / "lifecycle.jsonl").is_file()
