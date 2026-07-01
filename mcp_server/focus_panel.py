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
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import Optional
from urllib.parse import urlparse

from .persistence.agent_focus import AgentFocusService
from .persistence.orchestration_queue import OrchestrationService
from .persistence.production_context import ProductionContextService
from .persistence.session_snapshot import SessionSnapshotStore
from .lifecycle_log import exception_fields, lifecycle_event


logger = logging.getLogger(__name__)
DEFAULT_FOCUS_PANEL_PORT = 9890


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
    ):
        self.ableton = ableton
        self.focus_service = focus_service or AgentFocusService()
        self.production_context_service = (
            production_context_service or ProductionContextService()
        )
        self.snapshot_store = snapshot_store or SessionSnapshotStore()
        self.orchestration_service = orchestration_service or OrchestrationService()
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
        focused = set(focus.get("focus", {}).get("track_indices") or [])
        tracks = []
        for track in session_info.get("tracks") or []:
            if not isinstance(track, dict):
                continue
            entry = {
                "index": track.get("index"),
                "name": track.get("name", ""),
                "color_index": track.get("color_index"),
                "mute": track.get("mute"),
                "solo": track.get("solo"),
                "arm": track.get("arm"),
                "has_midi_input": track.get("has_midi_input"),
                "has_audio_input": track.get("has_audio_input"),
            }
            entry["focused"] = entry["index"] in focused
            tracks.append(entry)
        return {
            "status": "ok",
            "tempo": session_info.get("tempo"),
            "track_count": session_info.get("track_count"),
            "tracks": tracks,
            "focus": focus.get("focus"),
            "focus_panel_url": self.url,
            "session_source": session_meta.get("source"),
            "session_project_id": session_meta.get("project_id"),
            "session_updated_at_ms": session_meta.get("updated_at_ms"),
            "session_error": session_meta.get("error"),
        }

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
        from .production_cockpit import _render_cockpit_html

        return _render_cockpit_html(transport="http")

    def get_intent_cockpit_html(self) -> str:
        from .production_cockpit import _render_intent_first_cockpit_html

        return _render_intent_first_cockpit_html(transport="http")

    def get_cockpit_payload(self) -> dict:
        from .production_cockpit import _build_context

        payload = _build_context(self._cockpit_ctx(), include_history=False)
        payload.update(self._session_meta_payload())
        return payload

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

    def _cockpit_ctx(self):
        return SimpleNamespace(
            lifespan_context={
                "ableton": _PanelAbletonProxy(self),
                "agent_focus": self.focus_service,
                "orchestration_queue": self.orchestration_service,
                "production_context": self.production_context_service,
                "focus_panel_url": self.url,
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
            self._send_html(_HTML)
            return
        if path in ("/cockpit", "/cockpit/"):
            self._send_html(self.server.panel.get_cockpit_html())
            return
        if path in ("/cockpit/intent", "/cockpit/intent/"):
            self._send_html(self.server.panel.get_intent_cockpit_html())
            return
        if path == "/api/session":
            self._send_json(self.server.panel.get_session_payload())
            return
        if path == "/api/cockpit/state":
            self._send_json(self.server.panel.get_cockpit_payload())
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
            if path == "/api/cockpit/track-intent":
                payload = self._read_json_body()
                self._send_json(self.server.panel.save_cockpit_track_intent_payload(payload))
                return
            if path == "/api/cockpit/refresh-live":
                self._send_json(self.server.panel.refresh_live_payload())
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

    def _send_empty(self, status: int = 204) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LivePilot Focus</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #181818;
      --panel: #222;
      --panel-2: #2b2b2b;
      --text: #f2f2f2;
      --muted: #a7a7a7;
      --line: #3a3a3a;
      --accent: #f6a33a;
      --good: #72c46e;
      --danger: #e05c5c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font: 13px/1.35 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    header {
      position: sticky;
      top: 0;
      z-index: 2;
      padding: 12px;
      background: #141414;
      border-bottom: 1px solid var(--line);
    }
    h1 {
      margin: 0 0 10px;
      font-size: 15px;
      font-weight: 650;
      letter-spacing: 0;
    }
    .controls {
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 8px;
      align-items: center;
    }
    input, button {
      height: 32px;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--text);
      font: inherit;
    }
    input {
      width: 100%;
      padding: 0 9px;
    }
    button {
      padding: 0 10px;
      cursor: pointer;
      white-space: nowrap;
    }
    button.primary {
      border-color: #b8752a;
      background: var(--accent);
      color: #1b1207;
      font-weight: 700;
    }
    button.ghost {
      background: transparent;
    }
    button.danger {
      border-color: #693232;
      color: #ffb6b6;
    }
    main {
      padding: 10px;
    }
    .status {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      min-height: 26px;
      margin-bottom: 10px;
      color: var(--muted);
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 24px;
      padding: 2px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel);
      color: var(--text);
    }
    .tracks {
      display: grid;
      gap: 6px;
    }
    .track {
      display: grid;
      grid-template-columns: 22px minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
      min-height: 42px;
      padding: 7px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel);
      cursor: pointer;
    }
    .track:hover {
      background: var(--panel-2);
    }
    .track.selected {
      border-color: var(--accent);
      box-shadow: inset 0 0 0 1px var(--accent);
    }
    .swatch {
      width: 15px;
      height: 15px;
      border-radius: 4px;
      border: 1px solid rgba(255,255,255,.28);
    }
    .name {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 620;
    }
    .meta {
      color: var(--muted);
      font-size: 11px;
      margin-top: 2px;
    }
    .badges {
      display: flex;
      gap: 4px;
      align-items: center;
    }
    .badge {
      min-width: 20px;
      height: 20px;
      padding: 2px 5px;
      border-radius: 5px;
      border: 1px solid var(--line);
      color: var(--muted);
      text-align: center;
      font-size: 11px;
    }
    .badge.on {
      color: #101010;
      background: var(--accent);
      border-color: var(--accent);
    }
    .empty {
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 7px;
      padding: 16px;
      text-align: center;
    }
  </style>
</head>
<body>
  <header>
    <h1>LivePilot Focus</h1>
    <div class="controls">
      <input id="label" placeholder="label, e.g. vox + intro melody">
      <button class="primary" id="setFocus">Set</button>
      <button class="danger" id="clearFocus">Clear</button>
    </div>
    <div class="controls" style="grid-template-columns: 1fr auto; margin-top: 8px;">
      <input id="filter" placeholder="filter tracks">
      <button class="ghost" id="refresh">Refresh</button>
    </div>
  </header>
  <main>
    <div class="status" id="status">Loading...</div>
    <div class="tracks" id="tracks"></div>
  </main>
  <script>
    const state = {
      tracks: [],
      selected: new Set(),
      filter: "",
      dirty: false,
      lastFocus: null
    };

    const abletonPalette = [
      "#ffb000", "#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#5ac8fa",
      "#007aff", "#5856d6", "#af52de", "#ff2d55", "#8e8e93", "#ffffff"
    ];

    function colorFor(index) {
      const n = Number(index);
      return abletonPalette[Math.abs(Number.isFinite(n) ? n : 0) % abletonPalette.length];
    }

    async function api(path, options = {}) {
      const res = await fetch(path, {
        ...options,
        headers: {
          "content-type": "application/json",
          ...(options.headers || {})
        }
      });
      const body = await res.json();
      if (!res.ok || body.status === "error") {
        throw new Error(body.error || `Request failed: ${res.status}`);
      }
      return body;
    }

    async function refresh() {
      setStatus("Loading...");
      try {
        const data = await api("/api/session");
        state.tracks = data.tracks || [];
        state.lastFocus = data.focus || null;
        if (!state.dirty) {
          state.selected = new Set((data.focus?.track_indices || []).map(Number));
        }
        const label = document.getElementById("label");
        if (!label.value && data.focus?.label) label.value = data.focus.label;
        render(activeFocus());
      } catch (err) {
        setStatus(`Error: ${err.message}`);
      }
    }

    function setStatus(text) {
      document.getElementById("status").textContent = text;
    }

    function render(focus) {
      focus = focus || activeFocus();
      const focusText = focus && !focus.is_empty
        ? `${state.dirty ? "Draft: " : "Focused: "}${focus.tracks.map(t => `${t.index} ${t.name}`).join(", ")}`
        : "No focus set";
      document.getElementById("status").innerHTML =
        `<span class="pill">${escapeHtml(focusText)}</span>` +
        `<span class="pill">${state.tracks.length} tracks</span>`;

      const q = state.filter.trim().toLowerCase();
      const filtered = state.tracks.filter(track => {
        if (!q) return true;
        return String(track.name || "").toLowerCase().includes(q) ||
          String(track.index).includes(q);
      });
      const root = document.getElementById("tracks");
      if (!filtered.length) {
        root.innerHTML = `<div class="empty">No matching tracks</div>`;
        return;
      }
      root.innerHTML = filtered.map(trackTemplate).join("");
      for (const el of root.querySelectorAll(".track")) {
        el.addEventListener("click", () => toggleTrack(Number(el.dataset.index)));
      }
    }

    function trackTemplate(track) {
      const selected = state.selected.has(Number(track.index));
      const kind = track.has_midi_input ? "MIDI" : track.has_audio_input ? "Audio" : "Track";
      return `
        <div class="track ${selected ? "selected" : ""}" data-index="${track.index}">
          <div class="swatch" style="background:${colorFor(track.color_index)}"></div>
          <div>
            <div class="name">${track.index}. ${escapeHtml(track.name || "")}</div>
            <div class="meta">${kind}</div>
          </div>
          <div class="badges">
            <span class="badge ${track.mute ? "on" : ""}">M</span>
            <span class="badge ${track.solo ? "on" : ""}">S</span>
            <span class="badge ${track.arm ? "on" : ""}">R</span>
          </div>
        </div>
      `;
    }

    function toggleTrack(index) {
      if (state.selected.has(index)) {
        state.selected.delete(index);
      } else {
        state.selected.add(index);
      }
      state.dirty = true;
      render(activeFocus());
    }

    function selectedTracks() {
      return state.tracks.filter(t => state.selected.has(Number(t.index)));
    }

    function activeFocus() {
      if (state.dirty) {
        return {
          track_indices: Array.from(state.selected),
          tracks: selectedTracks(),
          is_empty: state.selected.size === 0
        };
      }
      return state.lastFocus || {
        track_indices: [],
        tracks: [],
        is_empty: true
      };
    }

    async function setFocus() {
      const track_indices = Array.from(state.selected);
      if (!track_indices.length) {
        setStatus("Select at least one track first");
        return;
      }
      const label = document.getElementById("label").value;
      await api("/api/focus", {
        method: "POST",
        body: JSON.stringify({ track_indices, label })
      });
      state.dirty = false;
      await refresh();
    }

    async function clearFocus() {
      await api("/api/focus/clear", { method: "POST", body: "{}" });
      state.dirty = false;
      state.selected.clear();
      document.getElementById("label").value = "";
      await refresh();
    }

    function escapeHtml(value) {
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    document.getElementById("setFocus").addEventListener("click", setFocus);
    document.getElementById("clearFocus").addEventListener("click", clearFocus);
    document.getElementById("refresh").addEventListener("click", refresh);
    document.getElementById("filter").addEventListener("input", (event) => {
      state.filter = event.target.value;
      render(activeFocus());
    });
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""


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
    _install_signal_lifecycle_logging()

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

    cockpit_url = url.rstrip("/") + "/cockpit"
    intent_url = url.rstrip("/") + "/cockpit/intent"
    lifecycle_event("focus_panel_started", url=url, cockpit_url=cockpit_url)
    print(f"LivePilot focus panel listening at {url}", file=sys.stderr)
    print(f"LivePilot production cockpit listening at {cockpit_url}", file=sys.stderr)
    print(f"LivePilot intent cockpit listening at {intent_url}", file=sys.stderr)
    if not args.live_refresh:
        print(
            "Snapshot-backed mode: run get_session_info through MCP after "
            "major Live session changes to refresh the track map.",
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


def _install_signal_lifecycle_logging() -> None:
    if getattr(_install_signal_lifecycle_logging, "_installed", False):
        return
    _install_signal_lifecycle_logging._installed = True

    def _handler(signum, frame):  # noqa: ARG001 - stdlib signal signature
        name = signal.Signals(signum).name
        lifecycle_event("focus_panel_signal", signal=name, signum=signum)
        if signum == signal.SIGINT:
            raise KeyboardInterrupt
        raise SystemExit(128 + signum)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handler)
        except (OSError, ValueError):
            pass


if __name__ == "__main__":
    raise SystemExit(main())
