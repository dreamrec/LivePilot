"""Local browser panel for selecting LivePilot agent focus.

The panel can be served either from the MCP process or as a standalone
browser sidecar. Standalone mode is snapshot-backed so it does not compete
with the MCP process for Ableton's single Remote Script TCP connection.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import Optional
from urllib.parse import urlparse

from .persistence.agent_focus import AgentFocusService
from .persistence.briefs import BriefService
from .persistence.layer_groups import LayerGroupService
from .persistence.orchestration_queue import OrchestrationService
from .persistence.production_context import ProductionContextService
from .persistence.session_snapshot import SessionSnapshotStore
from .lifecycle_log import (
    exception_fields,
    install_process_exit_logging,
    lifecycle_event,
)


logger = logging.getLogger(__name__)
DEFAULT_FOCUS_PANEL_PORT = 9890


def _float_or_none(value) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded_session_tracks(session_info: dict) -> list[dict]:
    tracks = []
    for track in session_info.get("tracks") or []:
        if not isinstance(track, dict):
            continue
        tracks.append({
            "index": track.get("index"),
            "name": track.get("name", ""),
        })
    return tracks


def _session_project_identity(session_info: dict) -> dict:
    identity = session_info.get("project_identity")
    if not isinstance(identity, dict):
        identity = {}
    name = ""
    for key in ("name", "project_name", "set_name", "live_set_name"):
        name = str(identity.get(key) or session_info.get(key) or "").strip()
        if name:
            break
    file_path = ""
    for key in ("file_path", "path", "project_path", "set_path", "live_set_path"):
        file_path = str(identity.get(key) or session_info.get(key) or "").strip()
        if file_path:
            break
    return {
        "name": name,
        "file_path": file_path,
        "track_count": int(
            session_info.get("track_count")
            or len(session_info.get("tracks") or [])
        ),
    }


def _session_store_paths(production_context: dict) -> dict:
    store_path = str(production_context.get("store_path") or "").strip()
    if not store_path:
        return {}
    try:
        project_dir = os.path.dirname(store_path)
        return {
            "project": os.path.join(project_dir, "project.json"),
            "production_context": store_path,
        }
    except Exception:
        return {"production_context": store_path}


def _session_analyzer_payload(session_info: dict, *, live: bool) -> dict:
    raw = str(
        session_info.get("analyzer_status")
        or session_info.get("m4l_analyzer_status")
        or ""
    ).strip().lower()
    allowed = {
        "online",
        "offline",
        "stale",
        "missing_device",
        "not_last",
        "bridge_unavailable",
    }
    status = raw if raw in allowed else ("offline" if live else "bridge_unavailable")
    last_seen = (
        session_info.get("analyzer_last_seen_ms")
        or session_info.get("m4l_last_seen_ms")
    )
    return {
        "status": status,
        "last_seen_ms": last_seen,
        "message": _analyzer_message(status),
    }


def _analyzer_message(status: str) -> str:
    return {
        "online": "Analyzer online",
        "offline": "Analyzer offline",
        "stale": "Analyzer data stale",
        "missing_device": "Analyzer device missing",
        "not_last": "Analyzer is not last on master",
        "bridge_unavailable": "Analyzer bridge unavailable",
    }.get(status, "Analyzer status unknown")


def _status_payload(status: str, *, message: str = "", last_seen_ms=None) -> dict:
    return {
        "status": status,
        "last_seen_ms": last_seen_ms,
        "message": message or _analyzer_message(status),
        "judgment_only": status != "online",
    }


def _analyzer_loaded_from_master(master: dict) -> tuple[bool, bool, Optional[int]]:
    devices = (master or {}).get("devices") or []
    if not isinstance(devices, list) or not devices:
        return False, False, None
    matches = [
        device for device in devices
        if isinstance(device, dict) and device.get("name") == "LivePilot_Analyzer"
    ]
    generic = (
        len(devices) == 1
        and isinstance(devices[0], dict)
        and devices[0].get("name") == "Max Audio Effect"
        and devices[0].get("class_name") == "MxDeviceAudioEffect"
        and devices[0].get("is_active") is not False
    )
    if generic:
        matches = [devices[0]]
    if not matches:
        return False, False, None
    first = matches[0]
    last = devices[-1]
    is_last = last is first or last.get("name") == "LivePilot_Analyzer"
    return True, bool(is_last), first.get("index")


class FocusPanelServer:
    """Small localhost HTTP server for the focus panel."""

    def __init__(
        self,
        ableton=None,
        focus_service: Optional[AgentFocusService] = None,
        production_context_service: Optional[ProductionContextService] = None,
        snapshot_store: Optional[SessionSnapshotStore] = None,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        allow_live_refresh: bool = False,
        orchestration_service: Optional[OrchestrationService] = None,
        layer_group_service: Optional[LayerGroupService] = None,
        brief_service: Optional[BriefService] = None,
    ):
        self.ableton = ableton
        self.focus_service = focus_service or AgentFocusService()
        self.production_context_service = (
            production_context_service or ProductionContextService()
        )
        self.snapshot_store = snapshot_store or SessionSnapshotStore()
        self.orchestration_service = orchestration_service or OrchestrationService()
        self.layer_group_service = layer_group_service or LayerGroupService()
        self.brief_service = brief_service or BriefService()
        self.allow_live_refresh = allow_live_refresh
        self.host = host
        self.requested_port = (
            int(port)
            if port is not None
            else int(os.environ.get("LIVEPILOT_FOCUS_PANEL_PORT", DEFAULT_FOCUS_PANEL_PORT))
        )
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.url: Optional[str] = None

    def start(self) -> Optional[str]:
        if self._server is not None:
            return self.url

        for port in range(self.requested_port, self.requested_port + 20):
            try:
                server = _LivePilotFocusHTTPServer(
                    (self.host, port),
                    _FocusPanelHandler,
                    panel=self,
                )
            except OSError:
                continue
            self._server = server
            bound_port = int(server.server_address[1])
            self.url = f"http://{self.host}:{bound_port}/"
            self._thread = threading.Thread(
                target=server.serve_forever,
                name="LivePilotFocusPanel",
                daemon=True,
            )
            self._thread.start()
            logger.info("LivePilot focus panel listening at %s", self.url)
            return self.url

        logger.warning(
            "LivePilot focus panel could not bind ports %s-%s",
            self.requested_port,
            self.requested_port + 19,
        )
        return None

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._server = None
        self._thread = None
        self.url = None

    def get_session_payload(self) -> dict:
        session_info, session_meta = self._session_info_with_meta()
        focus = self.focus_service.get_focus(session_info)
        context = self.get_cockpit_payload()
        section_map = context.get("section_map") or {}
        memory_health = context.get("memory_health") or {}
        production_context = context.get("production_context") or {}
        identity = _session_project_identity(session_info)
        return {
            "status": "ok",
            "contract_version": 2,
            "tempo": session_info.get("tempo"),
            "track_count": session_info.get("track_count"),
            "project_id": context.get("project_id") or session_meta.get("project_id"),
            "project_identity": identity,
            "store_paths": _session_store_paths(production_context),
            "transport": {
                "is_playing": bool(session_info.get("is_playing")),
                "current_song_time": (
                    session_info.get("current_song_time")
                    if session_info.get("current_song_time") is not None
                    else session_info.get("current_time")
                ),
                "loop": bool(session_info.get("loop")),
                "loop_start": session_info.get("loop_start"),
                "loop_length": session_info.get("loop_length"),
                "arrangement_override": bool(session_info.get("arrangement_override")),
            },
            "section_map": {
                "source": section_map.get("source", "none"),
                "source_label": section_map.get("source_label", ""),
                "current_section_id": section_map.get("current_section_id", ""),
                "sections_count": len(section_map.get("sections") or []),
            },
            "analyzer": self._analyzer_health(session_info),
            "memory_health": {
                "briefs_count": int(memory_health.get("briefs_count") or 0),
                "foreign_or_unresolved_briefs": int(
                    memory_health.get("foreign_or_unresolved_briefs") or 0
                ),
                "annotation_warnings": int(
                    memory_health.get("annotation_warnings") or 0
                ),
                "layer_groups_count": int(memory_health.get("layer_groups_count") or 0),
                "stale_layer_groups": int(memory_health.get("stale_layer_groups") or 0),
                "unresolved_layer_members": int(
                    memory_health.get("unresolved_layer_members") or 0
                ),
            },
            "tracks": _bounded_session_tracks(session_info),
            "focus": focus.get("focus"),
            "focus_panel_url": self.url,
            "session_source": session_meta.get("source"),
            "session_project_id": session_meta.get("project_id"),
            "session_updated_at_ms": session_meta.get("updated_at_ms"),
            "session_error": session_meta.get("error"),
        }

    def get_analyzer_health_payload(self) -> dict:
        session_info = self._session_info()
        return self._analyzer_health(session_info)

    def repair_analyzer_payload(self) -> dict:
        if not self._is_live_mode():
            return {
                "status": "error",
                "reason": "snapshot_mode",
                "error": "Analyzer repair requires a live Ableton connection.",
                "analyzer": _status_payload("bridge_unavailable"),
                "_http_status": 409,
            }
        session_info = self._session_info()
        store = self.orchestration_service.store_for_session(session_info)
        active_jobs = [
            job for job in store.list_jobs(ordered=True)
            if job.get("status") in {"queued", "running", "awaiting_decision"}
        ]
        if active_jobs:
            return {
                "status": "blocked",
                "reason": "active_ableton_jobs",
                "message": "Finish or cancel queued Ableton jobs before analyzer repair.",
                "active_job_count": len(active_jobs),
                "analyzer": self._analyzer_health(session_info),
                "_http_status": 409,
            }
        owner = "cockpit_analyzer_repair"
        claim = store.claim_resource("project", owner=owner, ttl_ms=60000)
        if claim.get("status") == "blocked":
            return {
                "status": "blocked",
                "reason": "lease_conflict",
                "message": "Another LivePilot writer currently holds the project lease.",
                "claim": claim,
                "analyzer": self._analyzer_health(session_info),
                "_http_status": 409,
            }
        before = self._analyzer_health(session_info)
        ensure_result = {}
        try:
            from .tools.analyzer import ensure_analyzer_on_master

            ensure_result = ensure_analyzer_on_master(self._cockpit_ctx())
            after_session = self._session_info()
            after = self._analyzer_health(after_session)
            return {
                "status": "ok",
                "changed": ensure_result.get("status") in {"loaded"},
                "before": before,
                "ensure_analyzer_on_master": ensure_result,
                "analyzer": after,
                "remaining_reason": None if after.get("status") == "online" else after.get("status"),
            }
        except Exception as exc:  # noqa: BLE001 - browser API returns JSON.
            return {
                "status": "error",
                "error": str(exc),
                "before": before,
                "ensure_analyzer_on_master": ensure_result,
                "analyzer": self._analyzer_health(session_info),
                "_http_status": 500,
            }
        finally:
            store.release_resource("project", owner=owner)

    def _analyzer_health(self, session_info: dict) -> dict:
        if not self._is_live_mode():
            return _status_payload("bridge_unavailable")
        try:
            master = self.ableton.send_command("get_master_track", {}) or {}
        except Exception as exc:  # noqa: BLE001 - read-only health degrades.
            return _status_payload(
                "offline",
                message=f"Could not read master track: {exc}",
            )
        loaded, is_last, device_index = _analyzer_loaded_from_master(master)
        if not loaded:
            return _status_payload("missing_device")
        if not is_last:
            payload = _status_payload("not_last")
            payload["device_index"] = device_index
            return payload
        raw = _session_analyzer_payload(session_info, live=True)
        last_seen = raw.get("last_seen_ms")
        if last_seen:
            try:
                age_ms = int(time.time() * 1000) - int(last_seen)
            except (TypeError, ValueError):
                age_ms = None
            if age_ms is not None and age_ms <= 5000:
                payload = _status_payload("online", last_seen_ms=last_seen)
                payload["device_index"] = device_index
                return payload
            payload = _status_payload("stale", last_seen_ms=last_seen)
            payload["device_index"] = device_index
            return payload
        if raw.get("status") == "online":
            payload = _status_payload("online", last_seen_ms=last_seen)
            payload["device_index"] = device_index
            return payload
        payload = _status_payload("bridge_unavailable")
        payload["device_index"] = device_index
        return payload

    def set_focus_payload(self, payload: dict) -> dict:
        session_info = self._session_info()
        indices = payload.get("track_indices")
        label = payload.get("label")
        return self.focus_service.set_focus(
            session_info,
            track_indices=indices,
            label=label,
            source="focus_panel",
        )

    def clear_focus_payload(self) -> dict:
        session_info = self._session_info()
        return self.focus_service.clear_focus(session_info)

    def get_cockpit_html(self) -> str:
        return self.get_intent_cockpit_html()

    def get_intent_cockpit_html(self) -> str:
        from .production_cockpit import _render_intent_first_cockpit_html

        return _render_intent_first_cockpit_html(transport="http")

    def get_cockpit_payload(self) -> dict:
        from .production_cockpit import _build_context

        payload = _build_context(self._cockpit_ctx(), include_history=False)
        payload.update(self._session_meta_payload())
        return payload

    def get_cockpit_briefs_payload(self) -> dict:
        from .production_cockpit import list_cockpit_briefs

        return list_cockpit_briefs(self._cockpit_ctx())

    def refresh_live_payload(self) -> dict:
        try:
            session_info, session_meta = self._read_live_session()
        except Exception as exc:  # noqa: BLE001 - browser API returns JSON
            return {
                "status": "error",
                "error": str(exc),
                "hint": (
                    "If the LivePilot MCP server is connected, ask Codex to run "
                    "get_session_info; that refreshes the browser snapshot."
                ),
            }

        payload = self.get_cockpit_payload()
        payload.update({
            "status": "ok",
            "session_source": session_meta.get("source"),
            "session_project_id": session_meta.get("project_id"),
            "session_updated_at_ms": session_meta.get("updated_at_ms"),
        })
        return payload

    def get_live_selection_payload(self) -> dict:
        if not self._is_live_mode():
            return self._live_unavailable_payload()
        selection = self.ableton.send_command("get_selected_track", {}) or {}
        return {
            "status": "ok",
            "selection": selection,
        }

    def select_live_track_payload(self, payload: dict) -> dict:
        if not self._is_live_mode():
            return self._live_unavailable_payload()
        result = self.ableton.send_command(
            "select_track",
            {"track_index": int(payload["track_index"])},
        ) or {}
        response = self.get_cockpit_payload()
        response["status"] = "ok"
        response["live_selection"] = result
        return response

    def loop_live_section_payload(self, payload: dict) -> dict:
        if not self._is_live_mode():
            return self._live_unavailable_payload()
        section = self._section_payload(payload)
        start_beat = _float_or_none(section.get("start_beat"))
        end_beat = _float_or_none(section.get("end_beat"))
        if start_beat is None or end_beat is None or end_beat <= start_beat:
            return {
                "status": "error",
                "reason": "invalid_section",
                "error": "Loop section needs start_beat and end_beat",
                "_http_status": 400,
            }
        store = self.orchestration_service.store_for_session(self._session_info())
        claim = store.claim_resource("transport", owner="cockpit", ttl_ms=15000)
        if claim.get("status") != "claimed":
            return {
                "status": "error",
                "reason": "lease_conflict",
                "error": "Queue is using the transport",
                "conflicts": claim.get("conflicts", []),
                "_http_status": 409,
            }
        play = bool(payload.get("play", True))
        loop_length = end_beat - start_beat
        commands = []
        try:
            loop_result = self.ableton.send_command("set_session_loop", {
                "enabled": True,
                "loop_start": start_beat,
                "loop_length": loop_length,
            }) or {}
            commands.append({"command": "set_session_loop", "result": loop_result})
            force_result = self.ableton.send_command("force_arrangement", {
                "beat_time": start_beat,
                "play": play,
                "loop_start": start_beat,
                "loop_length": loop_length,
            }) or {}
            commands.append({"command": "force_arrangement", "result": force_result})
        finally:
            release = store.release_resource("transport", owner="cockpit")
        response = self.get_cockpit_payload()
        response.update({
            "status": "ok",
            "loop_section": section,
            "loop_start": start_beat,
            "loop_length": loop_length,
            "play": play,
            "commands": commands,
            "lease": {"claim": claim, "release": release},
        })
        return response

    def write_live_locator_payload(self, payload: dict) -> dict:
        if not self._is_live_mode():
            return self._live_unavailable_payload()
        if not bool(payload.get("confirm") or payload.get("confirmed")):
            return {
                "status": "error",
                "reason": "confirmation_required",
                "error": "write-locator requires confirm=true",
                "_http_status": 400,
            }
        section = self._section_payload(payload)
        start_beat = _float_or_none(section.get("start_beat"))
        if start_beat is None:
            return {
                "status": "error",
                "reason": "invalid_section",
                "error": "Locator section needs start_beat",
                "_http_status": 400,
            }
        store = self.orchestration_service.store_for_session(self._session_info())
        claim = store.claim_resource("project", owner="cockpit", ttl_ms=15000)
        if claim.get("status") != "claimed":
            return {
                "status": "error",
                "reason": "lease_conflict",
                "error": "Queue is writing the project",
                "conflicts": claim.get("conflicts", []),
                "_http_status": 409,
            }
        try:
            result = self.ableton.send_command("create_locator", {
                "time": start_beat,
                "name": str(payload.get("name") or section.get("label") or "Section"),
            }) or {}
        finally:
            release = store.release_resource("project", owner="cockpit")
        response = self.get_cockpit_payload()
        response.update({
            "status": "ok",
            "locator": result,
            "locator_section": section,
            "lease": {"claim": claim, "release": release},
        })
        return response

    def set_cockpit_focus_payload(self, payload: dict) -> dict:
        from .production_cockpit import set_cockpit_focus

        return set_cockpit_focus(
            self._cockpit_ctx(),
            track_indices=payload.get("track_indices") or [],
            label=str(payload.get("label") or ""),
        )

    def clear_cockpit_focus_payload(self) -> dict:
        from .production_cockpit import clear_cockpit_focus

        return clear_cockpit_focus(self._cockpit_ctx())

    def save_cockpit_context_payload(self, payload: dict) -> dict:
        from .production_cockpit import save_production_context

        allowed = {
            "lane",
            "workflow_mode",
            "audition_required",
            "audition_count",
            "audition_scope",
            "protect",
            "reference",
            "notes",
            "target_query",
            "target_group",
            "target_mode",
            "target_layer",
            "target_track_refs",
            "target_track_indices",
            "target_label",
            "output_mode",
            "working_thread",
            "evidence_budget",
            "section",
            "section_scope",
            "section_label",
            "section_start_bar",
            "section_end_bar",
        }
        return save_production_context(
            self._cockpit_ctx(),
            **{key: payload.get(key) for key in allowed if key in payload},
        )

    def send_cockpit_brief_payload(self, payload: dict) -> dict:
        from .production_cockpit import _send_cockpit_brief

        return _send_cockpit_brief(self._cockpit_ctx(), payload)

    def delete_cockpit_brief_payload(self, payload: dict) -> dict:
        from .production_cockpit import delete_cockpit_brief

        return delete_cockpit_brief(
            self._cockpit_ctx(),
            brief_id=str(payload.get("brief_id") or ""),
        )

    def archive_cockpit_brief_payload(self, payload: dict) -> dict:
        from .production_cockpit import archive_cockpit_brief

        return archive_cockpit_brief(
            self._cockpit_ctx(),
            brief_id=str(payload.get("brief_id") or ""),
        )

    def rerun_cockpit_brief_payload(self, payload: dict) -> dict:
        from .production_cockpit import rerun_cockpit_brief

        return rerun_cockpit_brief(
            self._cockpit_ctx(),
            brief_id=str(payload.get("brief_id") or ""),
        )

    def adopt_cockpit_memory_payload(self, payload: dict) -> dict:
        from .production_cockpit import adopt_cockpit_memory

        return adopt_cockpit_memory(
            self._cockpit_ctx(),
            project_id=str(payload.get("project_id") or ""),
        )

    def record_cockpit_brief_dispatch_payload(self, payload: dict) -> dict:
        from .production_cockpit import record_cockpit_brief_dispatch

        return record_cockpit_brief_dispatch(
            self._cockpit_ctx(),
            brief_id=str(payload.get("brief_id") or ""),
            method=str(payload.get("method") or ""),
            codex_thread_id=str(payload.get("codex_thread_id") or ""),
        )

    def set_cockpit_working_thread_payload(self, payload: dict) -> dict:
        from .production_cockpit import set_cockpit_working_thread

        return set_cockpit_working_thread(
            self._cockpit_ctx(),
            thread_id=str(payload.get("thread_id") or ""),
            label=str(payload.get("label") or ""),
            clear=bool(payload.get("clear", False)),
        )

    def save_cockpit_track_intent_payload(self, payload: dict) -> dict:
        from .production_cockpit import save_cockpit_track_intent

        allowed = {
            "track_index",
            "role",
            "priority",
            "notes",
            "composition_intent",
            "sound_design_intent",
            "mix_intent",
            "constraints",
            "decision_state",
        }
        return save_cockpit_track_intent(
            self._cockpit_ctx(),
            **{key: payload.get(key) for key in allowed if key in payload},
        )

    def save_cockpit_layer_payload(self, payload: dict) -> dict:
        from .production_cockpit import save_cockpit_layer_group

        allowed = {
            "label",
            "track_indices",
            "layer_id",
            "status",
            "linked_layers",
            "notes",
        }
        return save_cockpit_layer_group(
            self._cockpit_ctx(),
            **{key: payload.get(key) for key in allowed if key in payload},
        )

    def delete_cockpit_layer_payload(self, payload: dict) -> dict:
        from .production_cockpit import delete_cockpit_layer_group

        return delete_cockpit_layer_group(
            self._cockpit_ctx(),
            layer_id=str(payload.get("layer_id") or payload.get("key") or ""),
        )

    def submit_cockpit_audition_action_payload(self, payload: dict) -> dict:
        from .production_cockpit import submit_cockpit_audition_action

        return submit_cockpit_audition_action(
            self._cockpit_ctx(),
            source_job_id=str(payload.get("source_job_id") or payload.get("job_id") or ""),
            action=str(payload.get("action") or ""),
            variant_letter=str(payload.get("variant_letter") or ""),
        )

    def _cockpit_ctx(self):
        return SimpleNamespace(
            lifespan_context={
                "ableton": _PanelAbletonProxy(self),
                "agent_focus": self.focus_service,
                "briefs": self.brief_service,
                "layer_groups": self.layer_group_service,
                "orchestration_queue": self.orchestration_service,
                "production_context": self.production_context_service,
                "focus_panel_url": self.url,
                "cockpit_mode": "live" if self._is_live_mode() else "snapshot",
            }
        )

    def _session_info(self) -> dict:
        session_info, _ = self._session_info_with_meta()
        return session_info

    def _session_info_with_meta(self) -> tuple[dict, dict]:
        live_error = None

        if self.ableton is not None:
            try:
                return self._read_live_session()
            except Exception as exc:  # noqa: BLE001 - snapshot fallback is intentional
                live_error = str(exc)
                logger.warning("Focus panel live session read failed: %s", exc)

        if self.allow_live_refresh:
            try:
                return self._read_live_session()
            except Exception as exc:  # noqa: BLE001 - keep browser usable
                live_error = str(exc)
                logger.info("Focus panel live probe unavailable: %s", exc)

        snapshot = self.snapshot_store.load()
        if snapshot:
            meta = {
                "source": "snapshot",
                "project_id": snapshot.get("project_id"),
                "updated_at_ms": snapshot.get("updated_at_ms"),
            }
            if live_error:
                meta["error"] = live_error
            return dict(snapshot.get("session_info") or {}), meta

        message = (
            "No LivePilot session snapshot is available yet. Call get_session_info "
            "once through the LivePilot MCP server, or restart this cockpit with "
            "--live-refresh while no other LivePilot client is connected."
        )
        if live_error:
            message += f" Last live-read error: {live_error}"
        raise RuntimeError(message)

    def _read_live_session(self) -> tuple[dict, dict]:
        if self.ableton is not None:
            session_info = self.ableton.send_command("get_session_info", {}) or {}
            session_info = _augment_live_session_info(
                session_info,
                self.ableton.send_command,
            )
            record = self._save_snapshot(session_info, source="focus_panel")
            return session_info, {
                "source": "live",
                "project_id": (record or {}).get("project_id"),
                "updated_at_ms": (record or {}).get("updated_at_ms"),
            }

        from .connection import AbletonConnection

        connection = AbletonConnection()
        try:
            session_info = connection.send_command("get_session_info", {}) or {}
            session_info = _augment_live_session_info(
                session_info,
                connection.send_command,
            )
        finally:
            connection.disconnect()
        record = self._save_snapshot(session_info, source="focus_panel_probe")
        return session_info, {
            "source": "live_probe",
            "project_id": (record or {}).get("project_id"),
            "updated_at_ms": (record or {}).get("updated_at_ms"),
        }

    def _is_live_mode(self) -> bool:
        return self.ableton is not None

    def _live_unavailable_payload(self) -> dict:
        return {
            "status": "error",
            "reason": "snapshot_mode",
            "error": "Live pointing is unavailable in snapshot-backed cockpit mode",
            "_http_status": 409,
        }

    def _section_payload(self, payload: dict) -> dict:
        section = payload.get("section") if isinstance(payload.get("section"), dict) else {}
        if section:
            return section
        try:
            from .production_cockpit import _build_context

            context = _build_context(self._cockpit_ctx())
            target = context.get("target") if isinstance(context.get("target"), dict) else {}
            current = target.get("section") if isinstance(target.get("section"), dict) else {}
            if current:
                return current
        except Exception:
            logger.debug("failed to resolve current cockpit section", exc_info=True)
        return {}

    def _save_snapshot(self, session_info: dict, source: str) -> Optional[dict]:
        try:
            return self.snapshot_store.save(session_info, source=source)
        except Exception:
            logger.debug("failed to persist focus panel session snapshot", exc_info=True)
            return None

    def _session_meta_payload(self) -> dict:
        snapshot = self.snapshot_store.load()
        if not snapshot:
            return {
                "session_source": "unknown",
                "session_snapshot_source": "",
                "session_project_id": None,
                "session_updated_at_ms": None,
            }
        return {
            "session_source": "live" if self.ableton is not None else "snapshot",
            "session_snapshot_source": snapshot.get("source"),
            "session_project_id": snapshot.get("project_id"),
            "session_updated_at_ms": snapshot.get("updated_at_ms"),
        }


class _PanelAbletonProxy:
    """Ableton-like object used by cockpit helper functions."""

    def __init__(self, panel: FocusPanelServer):
        self._panel = panel

    def send_command(self, command: str, params: Optional[dict] = None) -> dict:
        if command == "get_session_info":
            return self._panel._session_info()
        if self._panel.ableton is not None:
            return self._panel.ableton.send_command(command, params or {})
        raise RuntimeError(
            f"{command} is unavailable in snapshot-backed cockpit mode"
        )


def _augment_live_session_info(session_info: dict, send_command) -> dict:
    """Attach lightweight arrangement metadata when live refresh owns the socket."""
    if not isinstance(session_info, dict):
        return session_info
    enriched = dict(session_info)
    try:
        cue_result = send_command("get_cue_points", {}) or {}
    except Exception:
        cue_result = {}
    cues = cue_result.get("cue_points") if isinstance(cue_result, dict) else None
    if isinstance(cues, list) and cues:
        enriched["cue_points"] = cues

    tracks = enriched.get("tracks") or []
    updated_tracks = []
    changed = False
    for track in tracks:
        if not isinstance(track, dict):
            updated_tracks.append(track)
            continue
        name = str(track.get("name") or "").lower()
        if "section map" not in name and "arrangement map" not in name:
            updated_tracks.append(track)
            continue
        index = track.get("index")
        if not isinstance(index, int):
            updated_tracks.append(track)
            continue
        try:
            clip_result = send_command(
                "get_arrangement_clips",
                {"track_index": index},
            ) or {}
        except Exception:
            updated_tracks.append(track)
            continue
        clips = clip_result.get("clips") if isinstance(clip_result, dict) else None
        if not isinstance(clips, list) or not clips:
            updated_tracks.append(track)
            continue
        entry = dict(track)
        entry["arrangement_clips"] = clips
        updated_tracks.append(entry)
        changed = True
    if changed:
        enriched["tracks"] = updated_tracks
    return enriched


class _LivePilotFocusHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class, panel: FocusPanelServer):
        super().__init__(server_address, handler_class)
        self.panel = panel


class _FocusPanelHandler(BaseHTTPRequestHandler):
    server_version = "LivePilotFocusPanel/1.0"

    def do_OPTIONS(self) -> None:
        self._send_json({"status": "ok"})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/favicon.ico":
            self._send_empty(status=204)
            return
        if path in ("", "/"):
            self._send_redirect("/cockpit/intent")
            return
        if path in ("/cockpit", "/cockpit/"):
            self._send_redirect("/cockpit/intent")
            return
        if path in ("/cockpit/intent", "/cockpit/intent/"):
            self._send_html(self.server.panel.get_intent_cockpit_html())
            return
        if path == "/api/session":
            self._send_json(self.server.panel.get_session_payload())
            return
        if path == "/api/analyzer/health":
            self._send_json(self.server.panel.get_analyzer_health_payload())
            return
        if path == "/api/cockpit/state":
            self._send_json(self.server.panel.get_cockpit_payload())
            return
        if path == "/api/cockpit/briefs":
            self._send_json(self.server.panel.get_cockpit_briefs_payload())
            return
        if path == "/api/cockpit/layers":
            self._send_json({
                "status": "ok",
                "layer_groups": self.server.panel.get_cockpit_payload().get(
                    "layer_groups", []
                ),
            })
            return
        if path == "/api/cockpit/live/selection":
            self._send_panel_payload(self.server.panel.get_live_selection_payload())
            return
        if path == "/api/focus":
            self._send_json({
                "status": "ok",
                "focus": self.server.panel.get_session_payload().get("focus"),
            })
            return
        if path == "/api/health":
            self._send_json({
                "status": "ok",
                "focus_panel_url": self.server.panel.url,
            })
            return
        self._send_json({"status": "error", "error": "not_found"}, status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/focus":
                payload = self._read_json_body()
                self._send_json(self.server.panel.set_focus_payload(payload))
                return
            if path == "/api/focus/clear":
                self._send_json(self.server.panel.clear_focus_payload())
                return
            if path == "/api/cockpit/focus":
                payload = self._read_json_body()
                self._send_json(self.server.panel.set_cockpit_focus_payload(payload))
                return
            if path == "/api/cockpit/focus/clear":
                self._send_json(self.server.panel.clear_cockpit_focus_payload())
                return
            if path == "/api/cockpit/context":
                payload = self._read_json_body()
                self._send_json(self.server.panel.save_cockpit_context_payload(payload))
                return
            if path == "/api/cockpit/brief":
                payload = self._read_json_body()
                self._send_json(self.server.panel.send_cockpit_brief_payload(payload))
                return
            if path == "/api/cockpit/brief-archive":
                payload = self._read_json_body()
                self._send_json(self.server.panel.archive_cockpit_brief_payload(payload))
                return
            if path == "/api/cockpit/brief-rerun":
                payload = self._read_json_body()
                self._send_json(self.server.panel.rerun_cockpit_brief_payload(payload))
                return
            if path == "/api/cockpit/briefs/delete":
                payload = self._read_json_body()
                self._send_json(self.server.panel.delete_cockpit_brief_payload(payload))
                return
            if path == "/api/cockpit/adopt-memory":
                payload = self._read_json_body()
                self._send_json(self.server.panel.adopt_cockpit_memory_payload(payload))
                return
            if path == "/api/cockpit/brief-dispatch":
                payload = self._read_json_body()
                self._send_json(self.server.panel.record_cockpit_brief_dispatch_payload(payload))
                return
            if path == "/api/cockpit/working-thread":
                payload = self._read_json_body()
                self._send_json(self.server.panel.set_cockpit_working_thread_payload(payload))
                return
            if path == "/api/cockpit/track-intent":
                payload = self._read_json_body()
                self._send_json(self.server.panel.save_cockpit_track_intent_payload(payload))
                return
            if path == "/api/cockpit/layers/save":
                payload = self._read_json_body()
                self._send_json(self.server.panel.save_cockpit_layer_payload(payload))
                return
            if path == "/api/cockpit/layers/delete":
                payload = self._read_json_body()
                self._send_json(self.server.panel.delete_cockpit_layer_payload(payload))
                return
            if path == "/api/cockpit/auditions/action":
                payload = self._read_json_body()
                self._send_json(
                    self.server.panel.submit_cockpit_audition_action_payload(payload)
                )
                return
            if path == "/api/cockpit/live/select-track":
                payload = self._read_json_body()
                self._send_panel_payload(
                    self.server.panel.select_live_track_payload(payload)
                )
                return
            if path == "/api/cockpit/live/loop-section":
                payload = self._read_json_body()
                self._send_panel_payload(
                    self.server.panel.loop_live_section_payload(payload)
                )
                return
            if path == "/api/cockpit/live/write-locator":
                payload = self._read_json_body()
                self._send_panel_payload(
                    self.server.panel.write_live_locator_payload(payload)
                )
                return
            if path == "/api/cockpit/refresh-live":
                self._send_json(self.server.panel.refresh_live_payload())
                return
            if path == "/api/analyzer/repair":
                self._send_panel_payload(self.server.panel.repair_analyzer_payload())
                return
            self._send_json({"status": "error", "error": "not_found"}, status=404)
        except Exception as exc:  # noqa: BLE001 - browser API should return JSON
            logger.exception("Focus panel request failed")
            self._send_json({"status": "error", "error": str(exc)}, status=400)

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        logger.debug("focus-panel: " + format, *args)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > 1024 * 1024:
            raise ValueError("Request body too large")
        data = self.rfile.read(length) if length else b"{}"
        return json.loads(data.decode("utf-8") or "{}")

    def _send_html(self, body: str, status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        encoded = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _send_panel_payload(self, payload: dict) -> None:
        body = dict(payload or {})
        status = int(body.pop("_http_status", 200) or 200)
        self._send_json(body, status=status)

    def _send_empty(self, status: int = 204) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _send_redirect(self, location: str, status: int = 302) -> None:
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the LivePilot browser focus panel / production cockpit.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LIVEPILOT_FOCUS_PANEL_PORT", DEFAULT_FOCUS_PANEL_PORT)),
    )
    parser.add_argument(
        "--live-refresh",
        action="store_true",
        help=(
            "Attempt a short get_session_info probe when no MCP-owned "
            "snapshot is available. Do not use while another LivePilot "
            "client is connected to Ableton."
        ),
    )
    args = parser.parse_args(argv)
    lifecycle_event(
        "focus_panel_main_start",
        host=args.host,
        port=args.port,
        live_refresh=args.live_refresh,
    )
    install_process_exit_logging("focus_panel_signal")

    panel = FocusPanelServer(
        ableton=None,
        host=args.host,
        port=args.port,
        allow_live_refresh=args.live_refresh,
    )
    url = panel.start()
    if not url:
        lifecycle_event("focus_panel_bind_failed", host=args.host, port=args.port)
        return 1

    cockpit_url = url.rstrip("/") + "/cockpit/intent"
    lifecycle_event("focus_panel_started", url=url, cockpit_url=cockpit_url)
    print(f"LivePilot cockpit listening at {cockpit_url}", file=sys.stderr)
    print(f"Legacy cockpit URLs redirect to {cockpit_url}", file=sys.stderr)
    if not args.live_refresh:
        print(
            "Snapshot-backed mode: live pointing/transport/locator buttons are "
            "disabled. Run get_session_info through MCP after major Live session "
            "changes to refresh the track map.",
            file=sys.stderr,
        )
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        lifecycle_event("focus_panel_keyboard_interrupt")
        pass
    except BaseException as exc:
        lifecycle_event("focus_panel_exception", **exception_fields(exc))
        raise
    finally:
        lifecycle_event("focus_panel_shutdown_begin", url=url)
        panel.stop()
        lifecycle_event("focus_panel_shutdown_complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
