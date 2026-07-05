    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

    const QUICK_MOVES = [
      {label: "Make it rawer", text: "Make the focused part rawer and grittier, but keep the notes and timing.", lane: "sound_design", protect: ["preserve_notes", "preserve_timing"]},
      {label: "Sit behind vocal", text: "Tuck the focused part behind the vocal so it supports instead of fights.", lane: "mix", protect: ["preserve_vocal", "preserve_timing"]},
      {label: "Make it bigger", text: "Make the focused part bigger and wider without crowding the mix.", lane: "mix", protect: ["preserve_notes", "preserve_timing"]},
      {label: "Less glossy", text: "Take the polish off the focused part; make it less glossy and more honest.", lane: "sound_design", protect: ["preserve_notes", "preserve_timing"]},
      {label: "Fix what feels off", text: "Listen in context and fix whatever feels off, keeping the important musical idea intact.", lane: "holistic", protect: []}
    ];
    const OUTPUTS = {
      ask: {label: "Ask before acting", workflow: "guided", audition: false},
      auditions: {label: "Layer auditions", workflow: "audition", audition: true},
      apply: {label: "Apply carefully", workflow: "commit", audition: false}
    };
    const PROTECT_LABELS = {
      preserve_arrangement: "Arrangement",
      preserve_notes: "Notes",
      preserve_timing: "Timing",
      preserve_sound: "Sound",
      preserve_level: "Level",
      preserve_vocal: "Vocal",
      preserve_groove: "Groove"
    };
    let state = null;
    let selected = new Set();
    let outputMode = "ask";
    let outputModeUserOverride = false;
    let outputPersistTimer = null;
    let targetModeDraft = "instrument";
    let targetModeUserOverride = false;
    let rerunDraft = null;
    let sessionReadiness = null;

    function setStatus(text) {
      $("#status").textContent = text;
    }
    function toast(text) {
      const node = $("#toast");
      node.textContent = text;
      node.classList.add("show");
      clearTimeout(window.__lpToast);
      window.__lpToast = setTimeout(() => node.classList.remove("show"), 2200);
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }
    function ctxState() {
      return (((state || {}).production_context || {}).state) || {};
    }
    function capabilities() {
      return (state || {}).capabilities || {};
    }
    function targetState() {
      return (state || {}).target || {};
    }
    function currentLane() {
      return selectedLane() || ctxState().lane || "holistic";
    }
    function selectedLane() {
      const active = $("#laneRow .on");
      return active ? active.dataset.lane : "";
    }
    function savedSection() {
      const section = ctxState().section;
      return section && typeof section === "object" ? section : null;
    }
    function selectedSectionLabel() {
      const section = savedSection();
      return section ? (section.label || "Section") : "Whole song";
    }
    function liveSection() {
      const section = savedSection();
      if (!section || section.scope === "whole_song" || section.source === "whole_song") return null;
      return section;
    }
    function hasLiveSectionBounds(section = liveSection()) {
      if (!section) return false;
      const start = Number(section.start_beat);
      const end = Number(section.end_beat);
      return Number.isFinite(start) && Number.isFinite(end) && end > start;
    }
    function sectionMapState() {
      return (state || {}).section_map || {};
    }
    function selectedSectionMatches(section) {
      const saved = savedSection();
      if (!saved || !section) return false;
      const savedId = String(saved.section_id || saved.id || "");
      if (savedId && savedId === String(section.id || section.section_id || "")) return true;
      const labelMatches = normalizeToken(saved.label) === normalizeToken(section.label);
      const savedStart = Number(saved.start_beat);
      const sectionStart = Number(section.start_beat);
      const startMatches = Number.isFinite(savedStart) && Number.isFinite(sectionStart) && Math.abs(savedStart - sectionStart) < 0.2;
      return Boolean(labelMatches && startMatches);
    }
    function sectionFlex(section) {
      const duration = Number(section.duration_beats);
      if (!Number.isFinite(duration) || duration <= 0) return 6;
      return Math.max(6, Math.min(duration, 96));
    }
    function sectionBarText(section) {
      return section.bar_label || "";
    }
    function projectId() {
      return (state || {}).project_id || "unknown_project";
    }
    function draftKey() {
      return `livepilot.intent.draft.${projectId()}`;
    }
    function loadDraft() {
      try {
        return window.localStorage.getItem(draftKey()) || "";
      } catch (_error) {
        return "";
      }
    }
    function saveDraft() {
      try {
        window.localStorage.setItem(draftKey(), $("#sentence").value || "");
      } catch (_error) {
        // Ignore localStorage failures; server state remains authoritative.
      }
    }
    function clearDraft() {
      try {
        window.localStorage.removeItem(draftKey());
      } catch (_error) {
        // Ignore localStorage failures.
      }
    }
    function currentProtect() {
      return $$("#protectRow .tog.on").map(node => node.dataset.protect).filter(Boolean);
    }
    function auditionCount() {
      const node = $("#auditionCount");
      const raw = Number((node && node.value) || ctxState().audition_count || 3);
      if (!Number.isFinite(raw)) return 3;
      return Math.max(1, Math.min(8, Math.round(raw)));
    }
    function auditionLabel() {
      const count = auditionCount();
      return `${count} audition${count === 1 ? "" : "s"}`;
    }
    function outputLabel() {
      return outputMode === "auditions" ? auditionLabel() : OUTPUTS[outputMode].label;
    }
    function auditionLayerReady() {
      return targetTracks().length > 0;
    }
    function selectionFromState(payload = state) {
      const ctxIndices = (((payload || {}).production_context || {}).state || {}).target_track_indices || [];
      const savedTargetIndices = ctxIndices.map(Number).filter(Number.isFinite);
      if (savedTargetIndices.length) return new Set(savedTargetIndices);
      const targetIndices = (((payload || {}).target || {}).track_indices || []).map(Number);
      if (targetIndices.length) return new Set(targetIndices);
      const focusIndices = ((((payload || {}).focus || {}).focus || {}).track_indices || []).map(Number);
      if (focusIndices.length) return new Set(focusIndices);
      return new Set(focusIndices);
    }
    function trackByIndex(index) {
      return ((state || {}).tracks || []).find(track => Number(track.index) === Number(index));
    }
    function isMusicalTargetTrack(track) {
      if (!track) return false;
      const constraints = new Set((track.constraints || []).map(item => String(item || "").toLowerCase()));
      const role = String(track.effective_role || track.inferred_role || "").toLowerCase();
      const priority = String(track.priority || "").toLowerCase();
      if (constraints.has("folder_only") || constraints.has("metadata_only") || constraints.has("do_not_target_for_mix_decisions")) return false;
      if (role === "organizational_folder" || role === "utility_map") return false;
      if (priority === "utility") return false;
      return true;
    }
    function targetTracks() {
      const tracks = (state || {}).target_tracks || [];
      if (tracks.length) return tracks;
      const focused = (state || {}).focused_tracks || [];
      if (focused.length) return focused;
      const all = (state || {}).tracks || [];
      return all.filter(track => selected.has(Number(track.index)));
    }
    function targetTrackIndices() {
      return targetTracks().map(track => Number(track.index)).filter(Number.isFinite);
    }
    function workingTracks() {
      const tracks = targetTracks();
      const focused = tracks.filter(track => selected.has(Number(track.index)));
      return focused.length ? focused : tracks;
    }
    function currentLayerTracks() {
      const layerId = targetState().matched_layer || ctxState().target_layer || "";
      if (!layerId) return [];
      const group = ((state || {}).layer_groups || []).find(item => String(item.key || item.layer_id || "") === String(layerId));
      const indices = (group && group.track_indices || []).map(Number).filter(Number.isFinite);
      if (!indices.length) return targetTracks();
      return ((state || {}).tracks || []).filter(track => indices.includes(Number(track.index)));
    }
    function trackListTracks() {
      if (pickerMode() === "track") {
        return ((state || {}).tracks || []).filter(isMusicalTargetTrack);
      }
      if (targetMode() === "layer" || pickerMode() === "layer") {
        const layerTracks = currentLayerTracks();
        if (layerTracks.length) return layerTracks;
      }
      const targeted = targetTracks();
      return targeted.length ? targeted : ((state || {}).tracks || []);
    }
    function hasTarget() {
      const target = targetState();
      const ctx = ctxState();
      return Boolean(
        targetTracks().length ||
        target.query ||
        target.matched_group ||
        target.matched_layer ||
        ctx.target_query ||
        ctx.target_group ||
        ctx.target_layer ||
        (ctx.target_track_indices || []).length
      );
    }
    function targetLabel() {
      const target = targetState();
      return target.target_label || ctxState().target_label || target.matched_layer_label || target.matched_group_label || target.query || ctxState().target_query || "No target";
    }
    function pickerMode() {
      if (targetModeDraft === "layer") return "layer";
      if (targetModeDraft === "track" || targetModeDraft === "tracks") return "track";
      return "instrument";
    }
    function targetMode() {
      return ctxState().target_mode || targetState().target_mode || "instrument";
    }
    function savedPickerMode() {
      const mode = targetMode();
      if (mode === "layer") return "layer";
      if (mode === "query" || mode === "track" || mode === "tracks") return "track";
      return "instrument";
    }
    function pickerModeAfterRefresh(modeBeforeRefresh) {
      return targetModeUserOverride ? pickerMode() : (modeBeforeRefresh || savedPickerMode());
    }
    function outputModeFromWorkflow(workflowMode) {
      return workflowMode === "commit" ? "apply" : workflowMode === "guided" ? "ask" : "auditions";
    }
    function outputModeFromState(ctx) {
      const explicit = String((ctx || {}).output_mode || "").toLowerCase();
      if (OUTPUTS[explicit]) return explicit;
      return outputModeFromWorkflow((ctx || {}).workflow_mode);
    }
    function laneInferenceText(text) {
      return String(text || "").toLowerCase()
        .replace(/\b(?:keep|preserve|don't change|do not change|without changing|leave)\b[^.!?;]*(?:notes?|melod(?:y|ies)|harmony|chords?|timing|rhythm|groove|feel)\b/g, " ")
        .replace(/\b(?:notes?|melod(?:y|ies)|harmony|chords?|timing|rhythm|groove|feel)\b[^.!?;]*\b(?:same|intact|unchanged|safe)\b/g, " ");
    }
    function inferLane(text) {
      const lower = laneInferenceText(text);
      if (/\b(mix|level|balance|eq|compress|reverb|delay|glue|headroom|pan|stereo|tuck|pop|punch|forward)\b|cut through|stand out/.test(lower)) return "mix";
      if (/\b(sound|tone|texture|layer|device|synth|patch|distort|raw|glossy|shimmer|dark|bright|grit)\b/.test(lower)) return "sound_design";
      if (/\b(composition|notes|melody|harmony|chord|rhythm|structure|arrange|section|verse|chorus)\b/.test(lower)) return "composition";
      return currentLane();
    }
    function inferDirection(text) {
      const lower = String(text || "").toLowerCase();
      const found = [];
      if (/raw|grit|dirty|crunch|edge/.test(lower)) found.push("Rawer");
      if (/dark|dreary|sad|lower/.test(lower)) found.push("Darker");
      if (/gloss|polish|smooth|sheen/.test(lower)) found.push("Less glossy");
      if (/big|wide|huge|bigger|wider/.test(lower)) found.push("Bigger");
      if (/vocal|behind|support|tuck/.test(lower)) found.push("Behind vocal");
      if (/pop|forward|front|lead/.test(lower)) found.push("More forward");
      return found.length ? found.join(" - ") : (text ? "Custom brief" : "Waiting for brief");
    }
    function inferProtect(text) {
      const lower = String(text || "").toLowerCase();
      const flags = [];
      if (/note|melody|harmony|chord/.test(lower)) flags.push("preserve_notes");
      if (/timing|rhythm|groove|feel/.test(lower)) flags.push("preserve_timing");
      if (/vocal|vox|voice/.test(lower)) flags.push("preserve_vocal");
      if (/level|volume|balance/.test(lower)) flags.push("preserve_level");
      return flags;
    }
    function previewProtect(text) {
      const confirmed = currentProtect();
      const inferred = inferProtect(text).filter(flag => !confirmed.includes(flag));
      return {
        confirmed,
        inferred,
        all: mergeUnique(confirmed, inferred)
      };
    }
    function protectDisplay(preview) {
      const rows = [];
      (preview.confirmed || []).forEach(flag => {
        rows.push(`${PROTECT_LABELS[flag] || flag} (confirmed)`);
      });
      (preview.inferred || []).forEach(flag => {
        rows.push(`${PROTECT_LABELS[flag] || flag} (inferred)`);
      });
      return rows.length ? rows.join(" / ") : "None";
    }
    function mergeUnique(...lists) {
      const out = new Set();
      lists.flat().filter(Boolean).forEach(item => out.add(item));
      return [...out];
    }
    function normalizeToken(value) {
      return String(value || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/_+/g, "_");
    }
    function trackColor(track) {
      const colors = ["#9aa0a6", "#f06d5e", "#f0a33a", "#f4cf58", "#72bd7a", "#54c7c3", "#5da8ff", "#b08cff", "#e07ab6"];
      const raw = Number(track.color_index || 0);
      return colors[Math.abs(raw) % colors.length];
    }
    function trackLayers(track) {
      const idx = Number((track || {}).index);
      return ((state || {}).layer_groups || []).filter(group => {
        const indices = (group.track_indices || []).map(Number);
        return indices.includes(idx);
      });
    }
    function trackLayerChips(track) {
      const layers = trackLayers(track);
      if (!layers.length) return "";
      return `
        <div class="track-layers">
          ${layers.slice(0, 4).map(layer => `<span class="badge layer">${escapeHtml(layer.label || layer.key || "Layer")}</span>`).join("")}
          ${layers.length > 4 ? `<span class="badge">+${layers.length - 4}</span>` : ""}
        </div>
      `;
    }

    async function refresh() {
      try {
        setStatus("Refreshing");
        const keepPickerMode = state ? pickerMode() : "";
        state = await callTool(BACKEND_TOOLS.get_state);
        sessionReadiness = await fetchSessionReadiness();
        selected = selectionFromState();
        targetModeDraft = pickerModeAfterRefresh(keepPickerMode);
        syncControlsFromState();
        render();
        setStatus("Ready");
      } catch (error) {
        setStatus(error.message || String(error));
      }
    }
    async function refreshLive() {
      if (!HTTP_REFRESH_AVAILABLE) {
        setStatus("Live refresh is only available in the browser cockpit.");
        return;
      }
      try {
        setStatus("Refreshing from Ableton");
        const response = await fetch("/api/cockpit/refresh-live", { method: "POST" });
        const body = await response.json();
        if (!response.ok || body.status === "error") {
          throw new Error(body.hint || body.error || `Request failed: ${response.status}`);
        }
        const keepPickerMode = state ? pickerMode() : "";
        state = body;
        sessionReadiness = await fetchSessionReadiness();
        selected = selectionFromState(body);
        targetModeDraft = pickerModeAfterRefresh(keepPickerMode);
        syncControlsFromState();
        render();
        setStatus("Ready");
        toast("Live snapshot refreshed");
      } catch (error) {
        setStatus(error.message || String(error));
        toast("Snapshot not refreshed");
      }
    }
    async function fetchSessionReadiness() {
      if (!HTTP_REFRESH_AVAILABLE) return sessionReadiness;
      try {
        const response = await fetch("/api/session");
        if (!response.ok) return sessionReadiness;
        return await response.json();
      } catch (_error) {
        return sessionReadiness;
      }
    }

    function syncControlsFromState() {
      const ctx = ctxState();
      const sentence = $("#sentence");
      if (!sentence.value) sentence.value = loadDraft();
      if (!outputModeUserOverride || ctx.output_mode) outputMode = outputModeFromState(ctx);
      $("#auditionCount").value = String(Math.max(1, Math.min(5, Number(ctx.audition_count || 3))));
      $("#evidenceBudget").value = ctx.evidence_budget || "standard";
      $$("#laneRow .opt").forEach(node => node.classList.toggle("on", node.dataset.lane === (ctx.lane || "holistic")));
      $$("#outputModeRow .opt").forEach(node => node.classList.toggle("on", node.dataset.output === outputMode));
      const protect = new Set(ctx.protect || []);
      $$("#protectRow .tog").forEach(node => node.classList.toggle("on", protect.has(node.dataset.protect)));
      $("#targetQuery").value = ctx.target_query || targetState().query || "";
    }
    function outputPayload(mode = outputMode) {
      return {
        output_mode: mode,
        workflow_mode: OUTPUTS[mode].workflow,
        audition_required: OUTPUTS[mode].audition,
        audition_count: auditionCount(),
        audition_scope: targetMode() === "layer" ? "layer" : "track"
      };
    }
    function scheduleOutputPersist() {
      clearTimeout(outputPersistTimer);
      outputPersistTimer = setTimeout(persistOutputSettings, 180);
    }
    async function persistOutputSettings() {
      try {
        const mode = outputMode;
        state = await callTool(BACKEND_TOOLS.save_context, outputPayload(mode));
        outputModeUserOverride = false;
        selected = selectionFromState();
        syncControlsFromState();
        render();
      } catch (error) {
        setStatus(error.message || String(error));
        toast("Output mode not saved");
      }
    }

    function render() {
      renderTop();
      renderSectionMap();
      renderFocus();
      renderPicker();
      renderTracks();
      renderQuickMoves();
      renderBrief();
      renderMemorySuggestion();
      renderWorkingThread();
      renderNeedsYou();
      renderOrchestration();
      renderBriefFeed();
    }
    function renderTop() {
      const session = (state || {}).session || {};
      const tempo = session.tempo ? Math.round(Number(session.tempo)) + " BPM" : "tempo unknown";
      const count = session.track_count || ((state || {}).tracks || []).length || 0;
      const source = sessionSourceLabel();
      const project = compactId(projectId());
      const codex = Number((state || {}).codex_last_read_ms || 0);
      const codexText = codex ? `Codex ${formatAge(Date.now() - codex)}` : "Codex never";
      const ready = readinessText();
      $("#sessionPill").textContent = `${tempo} - ${count} tracks - ${project}${source ? " - " + source : ""}${ready ? " - " + ready : ""} - ${codexText}`;
      $("#refreshLive").style.display = HTTP_REFRESH_AVAILABLE ? "" : "none";
      const analyzerStatus = ((sessionReadiness || {}).analyzer || {}).status || "";
      $("#repairAnalyzer").style.display = HTTP_REFRESH_AVAILABLE && analyzerStatus && analyzerStatus !== "online" ? "" : "none";
    }
    function readinessText() {
      const readiness = sessionReadiness || {};
      const analyzer = (readiness.analyzer || {}).status || "";
      const memory = readiness.memory_health || {};
      const warningCount = Number(memory.foreign_or_unresolved_briefs || 0) +
        Number(memory.annotation_warnings || 0) +
        Number(memory.stale_layer_groups || 0) +
        Number(memory.unresolved_layer_members || 0);
      return [
        analyzer ? `analyzer ${analyzer}` : "",
        warningCount ? `memory ${warningCount}` : ""
      ].filter(Boolean).join(" - ");
    }
    function sessionSourceLabel() {
      const source = (state || {}).session_source || "";
      const snapshotSource = (state || {}).session_snapshot_source || "";
      const updated = Number((state || {}).session_updated_at_ms || 0);
      const age = updated ? Math.max(0, Date.now() - updated) : 0;
      const ageText = updated ? formatAge(age) : "";
      if (source === "live" || source === "live_probe") return "live";
      if (source === "snapshot") {
        return `snapshot${snapshotSource ? ":" + snapshotSource : ""}${ageText ? " " + ageText : ""}`;
      }
      return "";
    }
    function formatAge(ms) {
      const seconds = Math.round(ms / 1000);
      if (seconds < 60) return `${seconds}s old`;
      const minutes = Math.round(seconds / 60);
      if (minutes < 60) return `${minutes}m old`;
      const hours = Math.round(minutes / 60);
      return `${hours}h old`;
    }
    function dispatchStatusText(brief) {
      const dispatch = brief.dispatch || {};
      if (!dispatch.method || !dispatch.at_ms) return "";
      const age = formatAge(Math.max(0, Date.now() - Number(dispatch.at_ms || 0)));
      const thread = dispatch.codex_thread_id ? ` - thread ${compactId(dispatch.codex_thread_id)}` : "";
      return `dispatched - ${dispatch.method}${thread} - ${age}`;
    }
    function briefAgeText(brief) {
      const created = Number((brief || {}).created_at_ms || 0);
      if (!created) return "";
      return `saved ${formatAge(Math.max(0, Date.now() - created))}`;
    }
    function briefStatusText(brief) {
      const outcome = brief.outcome || {};
      if (outcome.status) {
        const count = Number(outcome.learnings_count || 0);
        if (outcome.status === "done") {
          return `done · ${count} learning${count === 1 ? "" : "s"}`;
        }
        if (outcome.status === "abandoned") return "archived";
        return outcome.status;
      }
      return (brief.status_trail || [brief.status || "saved"]).join(" -> ");
    }
    function workingThread() {
      return ctxState().working_thread || null;
    }
    function workingThreadStatus() {
      return ((state || {}).production_context || {}).working_thread_status || "unset";
    }
    function renderWorkingThread() {
      const pill = $("#workingThreadPill");
      if (!pill) return;
      const thread = workingThread();
      const status = workingThreadStatus();
      const captured = (state || {}).captured_thread || null;
      pill.classList.toggle("live", status === "live");
      pill.classList.toggle("missing", status === "missing");
      $("#pinCapturedThread").style.display = captured && captured.thread_id ? "" : "none";
      if (!thread || !thread.thread_id) {
        $("#workingThreadLabel").textContent = "No working thread";
        $("#clearWorkingThread").disabled = true;
        return;
      }
      const label = thread.label || compactId(thread.thread_id);
      $("#workingThreadLabel").textContent = `${label} - ${status}`;
      $("#clearWorkingThread").disabled = false;
    }
    function renderSectionMap() {
      const map = sectionMapState();
      const sections = Array.isArray(map.sections) ? map.sections : [];
      const source = map.source_label || "Manual scope";
      const caps = capabilities();
      const section = liveSection();
      $("#songMapTitle").textContent = source;
      $("#songMapMeta").textContent = sections.length
        ? `${sections.length} section${sections.length === 1 ? "" : "s"}`
        : "";
      $("#wholeSongButton").classList.toggle("active", !savedSection());
      $("#grabLiveSelection").disabled = !caps.live_pointing;
      $("#loopSectionLive").disabled = !caps.transport_ops || !hasLiveSectionBounds(section);
      $("#writeSectionLocator").disabled = !caps.locator_write || !section || !Number.isFinite(Number(section.start_beat));
      $("#grabLiveSelection").title = caps.live_pointing ? "Use the selected track from Ableton" : "Unavailable in snapshot mode";
      $("#loopSectionLive").title = caps.transport_ops ? "Set Live loop brace and play this section" : "Unavailable in snapshot mode";
      $("#writeSectionLocator").title = caps.locator_write ? "Create or rename a Live locator at this section start" : "Unavailable in snapshot mode";
      if (!sections.length) {
        $("#songStrip").innerHTML = '<button class="section-seg active" data-whole-song="1"><b>Whole song</b><span></span></button>';
      } else {
        $("#songStrip").innerHTML = sections.map(section => {
          const selectedSection = selectedSectionMatches(section);
          const currentSection = section.is_current || section.id === map.current_section_id;
          return `
            <button class="section-seg ${selectedSection ? "active" : ""} ${currentSection ? "current" : ""}" data-section-id="${escapeHtml(section.id || "")}" style="flex: ${sectionFlex(section)} 1 90px">
              <b title="${escapeHtml(section.label || "Section")}">${escapeHtml(section.label || "Section")}</b>
              <span>${escapeHtml(sectionBarText(section))}</span>
            </button>
          `;
        }).join("");
      }
      $$("#songStrip .section-seg").forEach(node => node.addEventListener("click", () => {
        if (node.dataset.wholeSong) chooseWholeSong();
        else chooseSection(node.dataset.sectionId || "");
      }));
    }
    function renderFocus() {
      const tracks = targetTracks();
      const target = targetState();
      const label = targetLabel();
      $("#focusTitle").textContent = tracks.length ? `${label} - ${tracks.length} track${tracks.length === 1 ? "" : "s"}` : label;
      $("#focusSub").textContent = `Section: ${((target.section || {}).label || selectedSectionLabel())}`;
      $("#clearTarget").disabled = !hasTarget();
      $("#contextLine").textContent = [
        `Target: ${hasTarget() ? (targetMode() === "layer" ? "song layer" : targetMode() === "query" ? "track/search" : "auto group") : "none"}`,
        `Lane: ${currentLane().replace("_", " ")}`,
        `Output: ${outputLabel()}`,
        `Evidence: ${ctxState().evidence_budget || "standard"}`
      ].join(" / ");
    }
    function renderPicker() {
      $$("#targetModeRow button").forEach(node => node.classList.toggle("active", node.dataset.mode === pickerMode()));
      const mode = pickerMode();
      if (mode === "track") {
        const activeKeys = new Set([...selected].map(index => String(index)));
        const tracks = ((state || {}).tracks || []).filter(isMusicalTargetTrack);
        if (!tracks.length) {
          $("#groupChips").innerHTML = '<span class="sub">No musical tracks found.</span>';
          renderLayerActions();
          return;
        }
        $("#groupChips").innerHTML = tracks.map(track => {
          const idx = Number(track.index);
          const label = `${idx + 1} ${track.name || "Track"}`;
          return `
            <button class="chip ${activeKeys.has(String(idx)) ? "active" : ""}" data-track-index="${idx}" title="${escapeHtml(label)}">
              <span class="target-chip-name">${escapeHtml(label)}</span>
            </button>
          `;
        }).join("");
        $$("#groupChips .chip").forEach(node => node.addEventListener("click", () => {
          toggleTrackTarget(Number(node.dataset.trackIndex));
        }));
        renderLayerActions();
        return;
      }
      const groups = mode === "layer" ? ((state || {}).layer_groups || []) : ((state || {}).track_groups || []);
      const activeKey = mode === "layer" ? targetState().matched_layer : targetState().matched_group;
      if (!groups.length) {
        $("#groupChips").innerHTML = mode === "layer"
          ? '<span class="sub">No layers yet - choose Tracks or Suggestions, then save the target as a layer.</span>'
          : '<span class="sub">No auto groups found.</span>';
        renderLayerActions();
        return;
      }
      $("#groupChips").innerHTML = groups.map(group => `
        <button class="chip ${group.key === activeKey ? "active" : ""}" data-key="${escapeHtml(group.key)}" data-label="${escapeHtml(group.label)}">
          ${escapeHtml(group.label)}
          ${mode === "layer" ? `<small>${escapeHtml(group.status || "layered")}</small>` : ""}
          <small>${group.count}</small>
        </button>
      `).join("");
      $$("#groupChips .chip").forEach(node => node.addEventListener("click", () => {
        if (node.classList.contains("active")) clearTarget();
        else chooseTarget(node.dataset.label, node.dataset.key);
      }));
      renderLayerActions();
    }
    function renderLayerActions() {
      const actions = $("#layerActions");
      if (!actions) return;
      const mode = pickerMode();
      const target = targetState();
      const ctx = ctxState();
      const hasTracks = targetTracks().length > 0 || selected.size > 0;
      const layerId = target.matched_layer || ctx.target_layer || "";
      const canDelete = mode === "layer" && Boolean(layerId);
      actions.style.display = mode === "layer" || hasTracks ? "flex" : "none";
      $("#saveLayer").disabled = !hasTracks;
      $("#deleteLayer").disabled = !canDelete;
    }
    function renderTracks() {
      const tracks = trackListTracks();
      const showingAll = !targetTracks().length && pickerMode() !== "track" && targetMode() !== "layer";
      if (!tracks.length) {
        $("#trackList").innerHTML = '<div class="sub">No tracks loaded yet.</div>';
        return;
      }
      const intro = showingAll
        ? '<div class="sub">Showing all tracks until a target is chosen.</div>'
        : pickerMode() === "track"
          ? '<div class="sub">Select one or more tracks to target.</div>'
          : targetMode() === "layer"
            ? '<div class="sub">Showing layer members. Select one or more to narrow the target.</div>'
        : "";
      $("#trackList").innerHTML = intro + tracks.map(track => {
        const idx = Number(track.index);
        const role = track.effective_role || track.inferred_role || track.group_label || "track";
        const kind = track.has_midi_input ? "MIDI" : track.has_audio_input ? "Audio" : "Track";
        const musical = isMusicalTargetTrack(track);
        return `
          <div class="track ${selected.has(idx) || track.focused ? "selected" : ""} ${musical ? "" : "disabled"}" data-index="${idx}" data-musical="${musical ? "1" : "0"}">
            <div class="swatch" style="background:${trackColor(track)}"></div>
            <div>
              <div class="track-name">${idx + 1} - ${escapeHtml(track.name)}</div>
              <div class="track-meta">${escapeHtml(role)} - ${kind}</div>
              ${trackLayerChips(track)}
            </div>
            <div>${track.mute ? '<span class="badge">M</span>' : ''}${track.solo ? '<span class="badge">S</span>' : ''}</div>
          </div>
        `;
      }).join("");
      $$("#trackList .track").forEach(node => node.addEventListener("click", () => handleTrackRowClick(Number(node.dataset.index))));
    }
    function renderQuickMoves() {
      $("#quickMoves").innerHTML = QUICK_MOVES.map(move => `<button class="move" data-label="${escapeHtml(move.label)}">${escapeHtml(move.label)}</button>`).join("");
      $$("#quickMoves .move").forEach((node, index) => node.addEventListener("click", () => applyQuickMove(QUICK_MOVES[index])));
    }
    function renderMemorySuggestion() {
      const node = $("#memorySuggestion");
      if (!node) return;
      const suggestion = (state || {}).memory_suggestion || null;
      if (!suggestion || !suggestion.project_id) {
        node.style.display = "none";
        node.innerHTML = "";
        return;
      }
      node.style.display = "grid";
      node.innerHTML = `
        <div><b>Similar project memory found</b><br>${escapeHtml(suggestion.identity || suggestion.project_id)}</div>
        <div>${Number(suggestion.resolved_tracks || 0)} matching track${Number(suggestion.resolved_tracks || 0) === 1 ? "" : "s"} / ${Number(suggestion.annotation_count || 0)} saved annotation${Number(suggestion.annotation_count || 0) === 1 ? "" : "s"}</div>
        <button class="soft mini" id="adoptMemory">Import memory</button>
      `;
      $("#adoptMemory").addEventListener("click", adoptMemorySuggestion);
    }
    function renderBrief() {
      const text = $("#sentence").value.trim();
      const target = targetState();
      const tracks = workingTracks();
      const protect = previewProtect(text);
      const lane = text ? inferLane(text) : currentLane();
      const banner = $("#rerunBanner");
      if (banner) {
        const showBanner = Boolean(rerunDraft && rerunDraft.banner);
        banner.style.display = showBanner ? "" : "none";
        banner.textContent = showBanner ? rerunDraft.banner : "";
      }
      $("#briefTarget").textContent = targetLabel();
      $("#briefTracks").textContent = tracks.map(track => `${Number(track.index) + 1} ${track.name}`).slice(0, 5).join(" / ");
      $("#briefLane").textContent = lane.replace("_", " ");
      $("#briefDirection").textContent = inferDirection(text);
      $("#briefScope").textContent = ((target.section || {}).label || selectedSectionLabel());
      $("#briefProtect").textContent = protectDisplay(protect);
      $("#briefOutput").textContent = outputLabel();
      $("#briefOutputSub").textContent = outputMode === "auditions"
        ? (auditionLayerReady() ? "Codex will create visible muted audition lanes." : "Choose a layer or track target before saving auditions.")
        : "Output mode selected in the brief controls.";
      $$("#outputModeRow .opt").forEach(node => node.classList.toggle("on", node.dataset.output === outputMode));
      $("#outputRow").classList.toggle("warn", outputMode !== "apply");
      $("#runBrief").textContent = outputMode === "apply"
        ? "Save apply brief for Codex"
        : outputMode === "auditions"
          ? `Save ${auditionLabel()} for Codex`
          : "Save brief for Codex";
      if (rerunDraft) $("#runBrief").textContent = "Send re-run to Codex";
      $("#runBrief").disabled = outputMode === "auditions" && !auditionLayerReady();
      $("#auditionCount").disabled = outputMode !== "auditions";
      $("#auditionControl").style.display = outputMode === "auditions" ? "inline-flex" : "none";
      $("#helperLine").textContent = outputMode === "auditions" && !auditionLayerReady()
        ? "Choose a Song Layer or Track target before saving audition variants."
        : "Briefs save to LivePilot context; Codex reads the saved state before acting.";
      $("#willList").innerHTML = planWill(text, tracks).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      $("#wontList").innerHTML = planWont(protect.all).map(item => `<li>${escapeHtml(item)}</li>`).join("");
    }
    function orchestrationState() {
      return (state || {}).orchestration || {};
    }
    function compactId(value) {
      const text = String(value || "");
      return text.length > 10 ? text.slice(0, 10) : text;
    }
    function compactObjectLabel(value) {
      if (!value) return "Unknown reference";
      if (typeof value === "string") return value;
      if (typeof value !== "object") return String(value);
      return value.track_name || value.name || value.label || value.track_ref || value.signature_key || value.id || JSON.stringify(value).slice(0, 96);
    }
    function queueActionHtml(row) {
      if (!row || !row.action) return "";
      return `
        <div class="queue-actions">
          <button class="soft mini queue-action" data-action="${escapeHtml(row.action)}" data-id="${escapeHtml(row.id || "")}">
            ${escapeHtml(row.action_label || "Clear")}
          </button>
        </div>
      `;
    }
    function needsYouRows() {
      const orchestration = orchestrationState();
      const rows = [];
      (orchestration.active_jobs || []).forEach(job => {
        if (job.status !== "awaiting_decision") return;
        rows.push({
          kind: "blocked",
          title: job.title || job.job_type || "Ableton job needs a decision",
          detail: `${job.status} - ${job.job_type || "job"} ${compactId(job.job_id) ? "#" + compactId(job.job_id) : ""}`,
          action: "cancel_job",
          action_label: "Cancel job",
          id: job.job_id || ""
        });
      });
      (orchestration.pending_proposals || []).forEach(proposal => {
        if (proposal.status !== "stale_needs_revalidation") return;
        rows.push({
          kind: "needs",
          title: proposal.summary || "Proposal needs revalidation",
          detail: `stale proposal - ${proposal.agent_role || "agent"} ${compactId(proposal.proposal_id) ? "#" + compactId(proposal.proposal_id) : ""}`,
          action: "dismiss_proposal",
          action_label: "Dismiss",
          id: proposal.proposal_id || ""
        });
      });
      const focus = (((state || {}).focus || {}).focus) || {};
      (focus.unresolved_refs || []).forEach(ref => {
        rows.push({
          kind: "blocked",
          title: compactObjectLabel(ref),
          detail: "Focused track reference no longer resolves",
          action: "clear_focus",
          action_label: "Clear target"
        });
      });
      ((state || {}).layer_groups || []).forEach(group => {
        (group.unresolved_members || []).forEach(member => {
          rows.push({
            kind: "blocked",
            title: `${group.label || group.key || "Layer"}: ${compactObjectLabel(member)}`,
            detail: "Layer member no longer resolves"
          });
        });
      });
      return rows;
    }
    function renderNeedsYou() {
      const badge = $("#needsYouBadge");
      const items = $("#needsYouItems");
      if (!badge || !items) return;
      const rows = needsYouRows();
      badge.textContent = rows.length ? `${rows.length} item${rows.length === 1 ? "" : "s"}` : "Clear";
      if (!rows.length) {
        items.innerHTML = '<div class="queue-item"><b>Nothing needs you</b><span>Queued work can continue without a decision.</span></div>';
        return;
      }
      items.innerHTML = rows.slice(0, 6).map(row => `
        <div class="queue-item ${escapeHtml(row.kind || "needs")}">
          <b>${escapeHtml(row.title)}</b>
          <span>${escapeHtml(row.detail)}</span>
          ${queueActionHtml(row)}
        </div>
      `).join("");
    }
    function renderOrchestration() {
      const orchestration = orchestrationState();
      const counts = orchestration.counts || {};
      const badge = $("#queueBadge");
      const summary = $("#queueSummary");
      const items = $("#queueItems");
      if (!badge || !summary || !items) return;
      if (orchestration.status && orchestration.status !== "ok") {
        badge.textContent = "Unavailable";
        summary.textContent = orchestration.warning || "Orchestration state is not available.";
        items.innerHTML = "";
        return;
      }
      const queued = Number(counts.queued_jobs || 0);
      const running = Number(counts.running_jobs || 0);
      const decisions = Number(counts.awaiting_decision_jobs || 0);
      const proposals = Number(counts.pending_proposals || 0);
      const stale = Number(counts.stale_proposals || 0);
      const leases = Number(counts.active_leases || 0);
      badge.textContent = queued || running || decisions
        ? `${queued} queued / ${running + decisions} active`
        : "Idle";
      if (!orchestration.has_activity) {
        summary.textContent = "No queued jobs or pending proposals for this project.";
        items.innerHTML = "";
        return;
      }
      summary.textContent = [
        `${queued} queued job${queued === 1 ? "" : "s"}`,
        `${proposals} pending proposal${proposals === 1 ? "" : "s"}`,
        stale ? `${stale} stale` : "",
        leases ? `${leases} lease${leases === 1 ? "" : "s"}` : ""
      ].filter(Boolean).join(" - ");
      const rows = [];
      (orchestration.active_tasks || []).slice(0, 4).forEach(task => {
        const title = task.instruction || task.agent_role || "Agent task";
        const canCancel = task.status === "queued";
        rows.push(`
          <div class="queue-item">
            <b>${escapeHtml(title)}</b>
            <span>${escapeHtml(task.status || "queued")} - ${escapeHtml(task.agent_role || "agent")} ${compactId(task.task_id) ? "#" + escapeHtml(compactId(task.task_id)) : ""}</span>
            ${canCancel ? queueActionHtml({action: "cancel_task", action_label: "Cancel task", id: task.task_id || ""}) : ""}
          </div>
        `);
      });
      (orchestration.active_jobs || []).slice(0, 4).forEach(job => {
        const title = job.title || job.job_type || "Ableton job";
        const canCancel = job.status === "queued" || job.status === "awaiting_decision";
        rows.push(`
          <div class="queue-item">
            <b>${escapeHtml(title)}</b>
            <span>${escapeHtml(job.status || "queued")} - ${escapeHtml(job.job_type || "job")} ${compactId(job.job_id) ? "#" + escapeHtml(compactId(job.job_id)) : ""}</span>
            ${canCancel ? queueActionHtml({action: "cancel_job", action_label: "Cancel job", id: job.job_id || ""}) : ""}
          </div>
        `);
      });
      (orchestration.pending_proposals || []).slice(0, 3).forEach(proposal => {
        const staleClass = proposal.status === "stale_needs_revalidation" ? " stale" : "";
        rows.push(`
          <div class="queue-item${staleClass}">
            <b>${escapeHtml(proposal.summary || proposal.agent_role || "Agent proposal")}</b>
            <span>${escapeHtml(proposal.status || "proposed")} - ${escapeHtml(proposal.agent_role || "agent")} ${compactId(proposal.proposal_id) ? "#" + escapeHtml(compactId(proposal.proposal_id)) : ""}</span>
            ${queueActionHtml({action: "dismiss_proposal", action_label: "Dismiss", id: proposal.proposal_id || ""})}
          </div>
        `);
      });
      if (!rows.length) {
        rows.push('<div class="queue-item"><b>No active queue items</b><span>Recent completed jobs are stored in the project queue.</span></div>');
      }
      items.innerHTML = rows.join("");
    }
    function renderBriefFeed() {
      const briefs = Array.isArray((state || {}).briefs) ? state.briefs : [];
      const pending = briefs.filter(isPendingBrief);
      const recent = briefs.filter(brief => !isPendingBrief(brief));
      renderBriefGroup("#pendingBriefBadge", "#pendingBriefFeed", pending, {
        emptyTitle: "No pending briefs",
        emptyDetail: "Saved briefs that have not been queued or archived will stay here.",
        pending: true
      });
      renderBriefGroup("#recentBriefBadge", "#recentBriefFeed", recent, {
        emptyTitle: "No recent brief activity",
        emptyDetail: "Queued, running, done, and archived briefs will appear here.",
        pending: false
      });
    }
    function renderBriefGroup(badgeSelector, feedSelector, briefs, options) {
      const badge = $(badgeSelector);
      const feed = $(feedSelector);
      if (!badge || !feed) return;
      badge.textContent = briefs.length ? `${briefs.length}` : "None";
      if (!briefs.length) {
        feed.innerHTML = `<div class="queue-item"><b>${escapeHtml(options.emptyTitle)}</b><span>${escapeHtml(options.emptyDetail)}</span></div>`;
        return;
      }
      feed.innerHTML = briefs.slice(0, 8).map(brief => briefCardHtml(brief, options)).join("");
    }
    function isPendingBrief(brief) {
      const status = String((brief || {}).status || "").toLowerCase();
      const outcome = ((brief || {}).outcome || {}).status;
      return !outcome && (status === "saved" || status === "seen");
    }
    function aimBadgeHtml(brief) {
      const aim = (brief || {}).aim_status || {};
      const status = aim.status || "";
      if (!status || status === "current" || status === "no_aim") return "";
      if (status === "foreign_set") {
        return `<span class="badge aim foreign">aimed at: ${escapeHtml(aim.label || "other set")}</span>`;
      }
      if (status === "degraded") {
        return `<span class="badge aim">aim: ${Number(aim.resolved || 0)} of ${Number(aim.total || 0)} tracks</span>`;
      }
      if (status === "unresolved") {
        return '<span class="badge aim">aim: no matching tracks</span>';
      }
      return `<span class="badge aim">aim: ${escapeHtml(status)}</span>`;
    }
    function briefCardHtml(brief, options) {
      const trail = briefStatusText(brief);
      const text = brief.request_text || "Untitled brief";
      const dispatchAction = brief.dispatch_action || {};
      const dispatchHref = dispatchAction.deeplink_new_thread || dispatchAction.deeplink_open_thread || "codex://threads/new";
      const workingHref = dispatchAction.deeplink_working_thread || "";
      const dispatchText = dispatchStatusText(brief);
      const ageText = briefAgeText(brief);
      const jobs = brief.related_jobs || [];
      const plan = jobs.flatMap(job => job.plan || []).slice(0, 3);
      const variants = jobs.flatMap(job => {
        const manifest = job.audition_manifest || {};
        return (manifest.variants || []).map(variant => ({
          source_job_id: job.job_id,
          letter: variant.letter || "",
          label: variant.label || "",
        }));
      }).slice(0, 8);
      const planText = plan.length
        ? plan.map(step => step.summary || step.tool || "step").join(" / ")
        : `${brief.related_task_count || 0} task${brief.related_task_count === 1 ? "" : "s"} / ${brief.related_job_count || 0} job${brief.related_job_count === 1 ? "" : "s"}`;
      const aim = ((brief || {}).aim_status || {}).status || "";
      const archiveFirst = aim === "foreign_set";
      const pendingActions = options.pending ? `
        <span>
          ${archiveFirst ? `<button class="soft brief-action danger" data-action="archive" data-brief-id="${escapeHtml(brief.brief_id || "")}">Archive</button>` : ""}
          <button class="soft brief-action" data-action="rerun" data-brief-id="${escapeHtml(brief.brief_id || "")}">Re-run</button>
          ${archiveFirst ? "" : `<button class="soft brief-action danger" data-action="archive" data-brief-id="${escapeHtml(brief.brief_id || "")}">Archive</button>`}
          <button class="soft brief-action danger" data-action="delete" data-brief-id="${escapeHtml(brief.brief_id || "")}">Delete</button>
        </span>
      ` : "";
      const dispatchActions = !options.pending ? `
        <span>
          <a class="link-button brief-dispatch" href="${escapeHtml(dispatchHref)}" data-action="open_codex" data-brief-id="${escapeHtml(brief.brief_id || "")}">New Codex thread</a>
          ${workingHref ? `<a class="link-button brief-dispatch" href="${escapeHtml(workingHref)}" data-action="open_working_thread" data-brief-id="${escapeHtml(brief.brief_id || "")}">Open working thread</a>` : ""}
          <button class="soft brief-dispatch" data-action="copy_prompt" data-brief-id="${escapeHtml(brief.brief_id || "")}">Copy prompt</button>
          <button class="soft brief-action danger" data-action="delete" data-brief-id="${escapeHtml(brief.brief_id || "")}">Delete</button>
        </span>
      ` : "";
      const variantsHtml = variants.length ? `<span>${variants.map(variant => `
        ${escapeHtml(variant.letter)} ${escapeHtml(variant.label)}
        <button class="soft audition-action" data-action="play" data-job-id="${escapeHtml(variant.source_job_id)}" data-variant="${escapeHtml(variant.letter)}">Play</button>
        <button class="soft audition-action" data-action="promote" data-job-id="${escapeHtml(variant.source_job_id)}" data-variant="${escapeHtml(variant.letter)}">Promote</button>
        <button class="soft audition-action" data-action="discard" data-job-id="${escapeHtml(variant.source_job_id)}" data-variant="${escapeHtml(variant.letter)}">Discard</button>
      `).join(" ")}</span>` : "";
      return `
        <div class="queue-item">
          <b>${escapeHtml(text)}</b>
          <span>${escapeHtml(trail)} - #${escapeHtml(String(brief.seq || ""))}</span>
          ${ageText ? `<span>${escapeHtml(ageText)}</span>` : ""}
          ${aimBadgeHtml(brief)}
          <span>${escapeHtml(planText)}</span>
          ${pendingActions}
          ${dispatchActions}
          ${dispatchText ? `<span>${escapeHtml(dispatchText)}</span>` : ""}
          ${variantsHtml}
        </div>
      `;
    }
    function planWill(text, tracks) {
      const direction = inferDirection(text).toLowerCase();
      const count = tracks.length || targetState().track_count || 0;
      const items = [`Use ${count || "the focused"} target track${count === 1 ? "" : "s"} as context`];
      if (outputMode === "auditions") items.push(`Create ${auditionLabel()} as visible muted Arrangement lanes`);
      if (outputMode === "apply") items.push("Apply one careful pass to the selected target");
      if (direction && direction !== "waiting for brief") items.push(`Aim for: ${direction}`);
      return items.slice(0, 3);
    }
    function planWont(protect) {
      const items = [];
      if (protect.includes("preserve_notes")) items.push("Change notes or harmony");
      if (protect.includes("preserve_timing")) items.push("Change timing or groove");
      if (protect.includes("preserve_vocal")) items.push("Touch the vocal unless it is targeted");
      if (protect.includes("preserve_arrangement")) items.push("Change arrangement structure");
      if (!items.length) items.push("Overwrite originals without an explicit commit decision");
      return items.slice(0, 4);
    }

    async function chooseTarget(label, key) {
      const mode = pickerMode();
      const payload = {
        target_mode: mode,
        target_query: label || key || "",
        target_group: mode === "instrument" ? key || "" : "",
        target_layer: mode === "layer" ? key || "" : "",
        target_track_indices: [],
        target_track_refs: [],
        target_label: label || key || ""
      };
      state = await callTool(BACKEND_TOOLS.save_context, payload);
      selected = new Set((((state || {}).target || {}).track_indices || []).map(Number));
      render();
      await saveFocus(label || key || "target");
      toast("Target saved");
    }
    async function chooseWholeSong() {
      state = await callTool(BACKEND_TOOLS.save_context, {
        section_scope: "whole_song"
      });
      syncControlsFromState();
      render();
      toast("Whole song scoped");
    }
    async function chooseSection(sectionId) {
      const section = (sectionMapState().sections || []).find(item => String(item.id || "") === String(sectionId || ""));
      if (!section) return;
      const payload = {
        section: {
          section_id: section.id || section.section_id || "",
          label: section.label || "Section",
          start_beat: Number.isFinite(Number(section.start_beat)) ? Number(section.start_beat) : null,
          end_beat: Number.isFinite(Number(section.end_beat)) ? Number(section.end_beat) : null,
          source: section.source || "manual"
        }
      };
      state = await callTool(BACKEND_TOOLS.save_context, payload);
      syncControlsFromState();
      render();
      toast("Section scoped");
    }
    async function chooseFreeQuery(query) {
      const label = query || "target";
      state = await callTool(BACKEND_TOOLS.save_context, {
        target_mode: "query",
        target_query: label,
        target_group: "",
        target_layer: "",
        target_track_indices: [],
        target_track_refs: [],
        target_label: label
      });
      selected = selectionFromState();
      await saveFocus(label);
      toast("Target saved");
    }
    async function saveCurrentLayer() {
      const tracks = targetTracks();
      const indices = selected.size
        ? [...selected].map(Number)
        : tracks.map(track => Number(track.index));
      if (!indices.length) {
        toast("Choose tracks first");
        return;
      }
      const currentLayer = targetState().matched_layer || ctxState().target_layer || "";
      const defaultLabel = targetLabel() && targetLabel() !== "No target"
        ? targetLabel()
        : "New Layer";
      const label = window.prompt("Layer name", defaultLabel);
      if (!label) return;
      state = await callTool(BACKEND_TOOLS.save_layer, {
        label,
        layer_id: pickerMode() === "layer" ? currentLayer : "",
        track_indices: indices,
        status: indices.length > 1 ? "layered" : "singleton"
      });
      const savedLayer = (((state || {}).layer_save || {}).layer || {});
      const layerId = savedLayer.layer_id || savedLayer.key || normalizeToken(label);
      state = await callTool(BACKEND_TOOLS.save_context, {
        target_mode: "layer",
        target_query: savedLayer.label || label,
        target_group: "",
        target_layer: layerId,
        target_track_indices: indices,
        target_label: savedLayer.label || label
      });
      targetModeDraft = "layer";
      targetModeUserOverride = true;
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast("Layer saved");
    }
    async function deleteCurrentLayer() {
      const layerId = targetState().matched_layer || ctxState().target_layer || "";
      if (!layerId) return;
      if (!window.confirm(`Delete layer "${targetLabel()}"?`)) return;
      state = await callTool(BACKEND_TOOLS.delete_layer, {layer_id: layerId});
      state = await callTool(BACKEND_TOOLS.save_context, {
        target_mode: "instrument",
        target_query: "",
        target_group: "",
        target_layer: "",
        target_track_indices: [],
        target_track_refs: [],
        target_label: ""
      });
      targetModeDraft = "layer";
      targetModeUserOverride = true;
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast("Layer deleted");
    }
    async function submitAuditionAction(action, sourceJobId, variantLetter) {
      if (!sourceJobId || !action) return;
      state = await callTool(BACKEND_TOOLS.audition_action, {
        source_job_id: sourceJobId,
        action,
        variant_letter: variantLetter || ""
      });
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast(`Queued audition ${action}`);
    }
    function briefById(briefId) {
      return ((state || {}).briefs || []).find(brief => String(brief.brief_id || "") === String(briefId || ""));
    }
    async function rerunBrief(briefId) {
      if (!briefId) return;
      const pack = await callTool(BACKEND_TOOLS.rerun_brief, {brief_id: briefId});
      rerunDraft = {
        parent_brief_id: pack.parent_brief_id || briefId,
        thread_id: pack.thread_id || "",
        banner: pack.banner || ""
      };
      $("#sentence").value = pack.request_text || "";
      saveDraft();
      if (pack.output_mode || pack.workflow_mode) {
        outputMode = OUTPUTS[pack.output_mode]
          ? pack.output_mode
          : outputModeFromWorkflow(pack.workflow_mode);
        outputModeUserOverride = true;
      }
      if (pack.audition_count) {
        $("#auditionCount").value = String(Math.max(1, Math.min(5, Number(pack.audition_count || 3))));
      }
      if (pack.lane) {
        $$("#laneRow .opt").forEach(node => node.classList.toggle("on", node.dataset.lane === pack.lane));
      }
      if (pack.evidence_budget) $("#evidenceBudget").value = pack.evidence_budget;
      const protect = new Set(pack.protect || []);
      if (protect.size) {
        $$("#protectRow .tog").forEach(node => node.classList.toggle("on", protect.has(node.dataset.protect)));
      }
      const contextPayload = {
        target_mode: pack.target_mode || "query",
        target_query: pack.target_query || "",
        target_group: pack.target_group || "",
        target_layer: pack.target_layer || "",
        lane: pack.lane || "holistic",
        output_mode: outputMode,
        workflow_mode: pack.workflow_mode || "guided",
        audition_required: OUTPUTS[outputMode].audition,
        audition_count: pack.audition_count || 3,
        audition_scope: pack.audition_scope || "layer",
        evidence_budget: pack.evidence_budget || "standard",
        protect: pack.protect || []
      };
      if (pack.section) contextPayload.section = pack.section;
      else contextPayload.section_scope = "whole_song";
      const nextState = await callTool(BACKEND_TOOLS.save_context, contextPayload);
      state = nextState;
      selected = new Set((pack.resolved_track_indices || []).map(Number));
      if (selected.size) {
        state = await callTool(BACKEND_TOOLS.set_focus, {
          track_indices: [...selected],
          label: (pack.resolved_track_names || []).join(", ") || "re-run aim"
        });
      }
      targetModeDraft = pack.target_mode === "layer" ? "layer" : pack.target_mode === "query" ? "track" : "instrument";
      targetModeUserOverride = true;
      syncControlsFromState();
      render();
      toast("Brief loaded for re-run");
    }
    async function archiveBrief(briefId) {
      if (!briefId) return;
      const brief = briefById(briefId) || {};
      const label = brief.request_text || briefId;
      if (!window.confirm(`Archive brief "${label}"?`)) return;
      state = await callTool(BACKEND_TOOLS.archive_brief, {brief_id: briefId});
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast("Brief archived");
    }
    async function deleteBrief(briefId) {
      if (!briefId) return;
      const brief = briefById(briefId) || {};
      const label = brief.request_text || briefId;
      if (!window.confirm(`Delete brief "${label}"? This hides test junk but keeps lineage.`)) return;
      try {
        state = await callTool(BACKEND_TOOLS.delete_brief, {brief_id: briefId});
        selected = selectionFromState();
        syncControlsFromState();
        render();
        toast("Brief deleted");
      } catch (error) {
        setStatus(error.message || String(error));
        toast("Delete blocked");
      }
    }
    async function performQueueAction(action, id) {
      try {
        if (action === "clear_focus") {
          await clearTarget();
          return;
        }
        if (action === "cancel_task") {
          if (!id || !window.confirm("Cancel this queued agent task?")) return;
          state = await callTool(BACKEND_TOOLS.cancel_queue_task, {
            task_id: id,
            reason: "canceled from cockpit"
          });
          toast("Task canceled");
        } else if (action === "cancel_job") {
          if (!id || !window.confirm("Cancel this queued Ableton job?")) return;
          state = await callTool(BACKEND_TOOLS.cancel_queue_job, {
            job_id: id,
            reason: "canceled from cockpit"
          });
          toast("Job canceled");
        } else if (action === "dismiss_proposal") {
          if (!id || !window.confirm("Dismiss this agent proposal?")) return;
          state = await callTool(BACKEND_TOOLS.dismiss_queue_proposal, {
            proposal_id: id,
            reason: "dismissed from cockpit"
          });
          toast("Proposal dismissed");
        } else {
          return;
        }
        selected = selectionFromState();
        syncControlsFromState();
        render();
      } catch (error) {
        setStatus(error.message || String(error));
        toast("Queue action blocked");
      }
    }
    async function adoptMemorySuggestion() {
      const suggestion = (state || {}).memory_suggestion || {};
      if (!suggestion.project_id) return;
      state = await callTool(BACKEND_TOOLS.adopt_memory, {project_id: suggestion.project_id});
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast("Project memory imported");
    }
    async function recordBriefDispatch(briefId, method, codexThreadId = "") {
      if (!briefId || !method) return;
      state = await callTool(BACKEND_TOOLS.record_dispatch, {
        brief_id: briefId,
        method,
        codex_thread_id: codexThreadId
      });
      selected = selectionFromState();
      syncControlsFromState();
      render();
    }
    async function openBriefInCodex(briefId, href) {
      try {
        await recordBriefDispatch(briefId, "deeplink");
      } catch (error) {
        setStatus(error.message || String(error));
      }
      window.location.href = href || "codex://threads/new";
    }
    async function openWorkingThread(briefId, href) {
      const brief = briefById(briefId);
      const action = (brief || {}).dispatch_action || {};
      try {
        if (!action.existing_thread_prefill) {
          await copyText(action.sweep_prompt || action.prompt || "");
        }
        await recordBriefDispatch(briefId, "deeplink_existing", action.working_thread_id || "");
        toast(action.existing_thread_prefill ? "Thread opened - press Enter" : "Thread opened - prompt copied, paste and send");
      } catch (error) {
        setStatus(error.message || String(error));
      }
      window.location.href = href || "codex://threads/new";
    }
    async function copyBriefPrompt(briefId) {
      const brief = briefById(briefId);
      const prompt = ((brief || {}).dispatch_action || {}).prompt || "";
      if (!prompt) {
        toast("No prompt available");
        return;
      }
      await copyText(prompt);
      await recordBriefDispatch(briefId, "copy_prompt");
      toast("Prompt copied");
    }
    async function clearWorkingThread() {
      state = await callTool(BACKEND_TOOLS.set_working_thread, {clear: true});
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast("Working thread cleared");
    }
    async function pinCapturedThread() {
      const captured = (state || {}).captured_thread || {};
      if (!captured.thread_id) {
        toast("No captured thread yet");
        return;
      }
      state = await callTool(BACKEND_TOOLS.set_working_thread, {
        thread_id: captured.thread_id,
        label: `Brief ${captured.brief_id || ""}`.trim()
      });
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast("Working thread pinned");
    }
    async function copyText(text) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return;
      }
      const node = document.createElement("textarea");
      node.value = text;
      node.setAttribute("readonly", "readonly");
      node.style.position = "fixed";
      node.style.left = "-9999px";
      document.body.appendChild(node);
      node.select();
      document.execCommand("copy");
      document.body.removeChild(node);
    }
    async function grabLiveSelection() {
      if (!capabilities().live_pointing) {
        toast("Live pointing unavailable in snapshot mode");
        return;
      }
      const result = await callTool(BACKEND_TOOLS.get_live_selection);
      const selection = result.selection || result || {};
      const index = Number(selection.track_index);
      if (!Number.isInteger(index) || index < 0) {
        setStatus("Select a regular track in Ableton first.");
        toast("No regular Live track selected");
        return;
      }
      await selectTrackTarget(index);
      toast("Grabbed Live selection");
    }
    async function loopSelectedSectionLive() {
      const section = liveSection();
      if (!capabilities().transport_ops) {
        toast("Live transport unavailable in snapshot mode");
        return;
      }
      if (!hasLiveSectionBounds(section)) {
        toast("Choose a bounded section first");
        return;
      }
      state = await callTool(BACKEND_TOOLS.loop_live_section, {
        section,
        play: true
      });
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast("Looped section in Live");
    }
    async function writeSelectedSectionLocator() {
      const section = liveSection();
      if (!capabilities().locator_write) {
        toast("Locator write unavailable in snapshot mode");
        return;
      }
      if (!section || !Number.isFinite(Number(section.start_beat))) {
        toast("Choose a section first");
        return;
      }
      const label = section.label || "Section";
      if (!window.confirm(`Write "${label}" to Live locators?`)) return;
      state = await callTool(BACKEND_TOOLS.write_live_locator, {
        section,
        name: label,
        confirm: true
      });
      selected = selectionFromState();
      syncControlsFromState();
      render();
      toast("Locator written");
    }
    async function repairAnalyzer() {
      if (!HTTP_REFRESH_AVAILABLE) {
        toast("Analyzer repair is only available in the browser cockpit.");
        return;
      }
      setStatus("Repairing analyzer");
      try {
        const response = await fetch("/api/analyzer/repair", { method: "POST" });
        const body = await response.json();
        if (!response.ok || body.status === "error" || body.status === "blocked") {
          throw new Error(body.message || body.error || body.reason || `Request failed: ${response.status}`);
        }
        sessionReadiness = await fetchSessionReadiness();
        renderTop();
        setStatus("Ready");
        toast(body.analyzer && body.analyzer.status === "online" ? "Analyzer online" : `Analyzer ${body.analyzer.status}`);
      } catch (error) {
        setStatus(error.message || String(error));
        sessionReadiness = await fetchSessionReadiness();
        renderTop();
        toast("Analyzer repair blocked");
      }
    }
    async function clearTarget() {
      const keepPickerMode = pickerMode();
      setStatus("Clearing target");
      selected.clear();
      state = await callTool(BACKEND_TOOLS.save_context, {
        target_mode: "instrument",
        target_query: "",
        target_group: "",
        target_layer: "",
        target_track_indices: [],
        target_track_refs: [],
        target_label: ""
      });
      state = await callTool(BACKEND_TOOLS.clear_focus, {});
      targetModeDraft = keepPickerMode;
      syncControlsFromState();
      targetModeDraft = keepPickerMode;
      selected = selectionFromState();
      render();
      setStatus("Ready");
      toast("Target cleared");
    }
    async function saveExplicitTrackTarget(indices, label = "") {
      const clean = [...new Set((indices || []).map(Number).filter(Number.isFinite))];
      if (!clean.length) {
        await clearTarget();
        return;
      }
      const layerId = targetState().matched_layer || ctxState().target_layer || "";
      const layerLabel = targetState().matched_layer_label || targetLabel();
      const layerMode = targetMode() === "layer" && layerId;
      const mode = layerMode ? "layer" : clean.length === 1 ? "track" : "tracks";
      const names = clean.map(index => {
        const track = trackByIndex(index);
        return track ? `${index + 1} ${track.name}` : `${index + 1}`;
      });
      const targetLabelText = label || (layerMode ? layerLabel : names.join(", "));
      state = await callTool(BACKEND_TOOLS.save_context, {
        target_mode: mode,
        target_query: layerMode ? layerLabel : targetLabelText,
        target_group: "",
        target_layer: layerMode ? layerId : "",
        target_track_indices: clean,
        target_label: targetLabelText
      });
      selected = new Set(clean);
      state = await callTool(BACKEND_TOOLS.set_focus, {
        track_indices: clean,
        label: targetLabelText
      });
      syncControlsFromState();
      render();
    }
    async function toggleTrackTarget(index) {
      const track = trackByIndex(index);
      if (!isMusicalTargetTrack(track)) {
        setStatus("That row is a folder or map, not a musical target.");
        toast("Choose a musical track");
        return;
      }
      const next = new Set(selected);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      await saveExplicitTrackTarget([...next], [...next].map(trackIndex => {
        const item = trackByIndex(trackIndex);
        return item ? `${trackIndex + 1} ${item.name}` : `${trackIndex + 1}`;
      }).join(", "));
      toast(next.size ? "Track target updated" : "Target cleared");
    }
    async function selectTrackTarget(index) {
      const track = trackByIndex(index);
      if (!isMusicalTargetTrack(track)) {
        setStatus("That row is a folder or map, not a musical target.");
        toast("Choose a musical track");
        return;
      }
      const currentTracks = targetTracks();
      if (
        currentTracks.length === 1 &&
        Number(currentTracks[0].index) === Number(index) &&
        targetMode() === "query"
      ) {
        await clearTarget();
        return;
      }
      const label = track.name || String(index + 1);
      await saveExplicitTrackTarget([index], `${index + 1} ${label}`);
      if (capabilities().live_pointing) {
        try {
          state = await callTool(BACKEND_TOOLS.select_live_track, {
            track_index: index
          });
        } catch (error) {
          setStatus(error.message || String(error));
          toast("Cockpit target saved; Live selection not changed");
        }
      }
      toast("Track target saved");
    }
    async function handleTrackRowClick(index) {
      if (pickerMode() === "track" || targetMode() === "track" || targetMode() === "tracks") {
        await toggleTrackTarget(index);
        return;
      }
      const targetIndices = currentLayerTracks().map(track => Number(track.index));
      const layerLikeTarget = targetMode() === "layer" && targetIndices.length > 1 && targetIndices.includes(index);
      if (!layerLikeTarget) {
        await selectTrackTarget(index);
        return;
      }
      const next = new Set(selected);
      if (next.has(index) && next.size > 1) next.delete(index);
      else next.add(index);
      await saveExplicitTrackTarget([...next], [...next].map(trackIndex => {
        const track = trackByIndex(trackIndex);
        return track ? `${trackIndex + 1} ${track.name}` : `${trackIndex + 1}`;
      }).join(", "));
      toast("Layer focus updated");
    }
    async function saveFocus(label = "") {
      if (!selected.size) return;
      state = await callTool(BACKEND_TOOLS.set_focus, {
        track_indices: [...selected],
        label: label || targetLabel() || [...selected].map(index => Number(index) + 1).join(",")
      });
      syncControlsFromState();
      render();
    }
    function applyQuickMove(move) {
      $("#sentence").value = move.text;
      $$("#laneRow .opt").forEach(node => node.classList.toggle("on", node.dataset.lane === move.lane));
      const merged = mergeUnique(currentProtect(), move.protect || []);
      $$("#protectRow .tog").forEach(node => node.classList.toggle("on", merged.includes(node.dataset.protect)));
      renderBrief();
    }
    async function saveBrief(mode = outputMode) {
      outputMode = mode;
      if (outputMode === "auditions" && !auditionLayerReady()) {
        setStatus("Choose a layer or track target before saving auditions.");
        toast("Choose a target first");
        renderBrief();
        return;
      }
      const text = $("#sentence").value.trim();
      const ctx = ctxState();
      const lane = text ? inferLane(text) : currentLane();
      $$("#laneRow .opt").forEach(node => node.classList.toggle("on", node.dataset.lane === lane));
      const protect = mergeUnique(currentProtect(), inferProtect(text));
      $$("#protectRow .tog").forEach(node => node.classList.toggle("on", protect.includes(node.dataset.protect)));
      const payload = {
        ...outputPayload(outputMode),
        lane,
        evidence_budget: $("#evidenceBudget").value || ctx.evidence_budget || "standard",
        protect,
        request_text: text,
        target_query: $("#targetQuery").value || targetState().query || ctx.target_query || "",
        target_mode: targetMode(),
        target_group: targetMode() === "instrument" ? (targetState().matched_group || ctx.target_group || "") : "",
        target_layer: targetMode() === "layer" ? (targetState().matched_layer || ctx.target_layer || "") : "",
        target_track_indices: [...selected].map(Number).filter(Number.isFinite),
        target_label: targetLabel() === "No target" ? "" : targetLabel(),
        section: savedSection()
      };
      if (rerunDraft) {
        payload.parent_brief_id = rerunDraft.parent_brief_id || "";
        payload.thread_id = rerunDraft.thread_id || "";
      }
      if (selected.size) {
        state = await callTool(BACKEND_TOOLS.set_focus, {
          track_indices: [...selected],
          label: targetLabel() || [...selected].map(index => Number(index) + 1).join(",")
        });
      }
      state = await callTool(BACKEND_TOOLS.send_brief, payload);
      selected = selectionFromState();
      $("#sentence").value = "";
      clearDraft();
      rerunDraft = null;
      render();
      const queued = (((state || {}).orchestration_submission || {}).job || {}).title;
      toast(queued ? `Queued: ${queued}` : "Brief sent to Codex");
    }

    $("#refresh").addEventListener("click", refresh);
    $("#refreshLive").addEventListener("click", refreshLive);
    $("#repairAnalyzer").addEventListener("click", repairAnalyzer);
    $("#grabLiveSelection").addEventListener("click", grabLiveSelection);
    $("#loopSectionLive").addEventListener("click", loopSelectedSectionLive);
    $("#writeSectionLocator").addEventListener("click", writeSelectedSectionLocator);
    $("#clearTarget").addEventListener("click", clearTarget);
    $("#saveLayer").addEventListener("click", saveCurrentLayer);
    $("#deleteLayer").addEventListener("click", deleteCurrentLayer);
    $("#pinCapturedThread").addEventListener("click", pinCapturedThread);
    $("#clearWorkingThread").addEventListener("click", clearWorkingThread);
    $("#wholeSongButton").addEventListener("click", chooseWholeSong);
    $("#targetModeRow").addEventListener("click", event => {
      const button = event.target.closest("button[data-mode]");
      if (!button) return;
      targetModeDraft = button.dataset.mode || "instrument";
      targetModeUserOverride = true;
      renderPicker();
    });
    $("#targetQuery").addEventListener("keydown", event => {
      if (event.key !== "Enter") return;
      const query = $("#targetQuery").value.trim();
      const normalized = normalizeToken(query);
      if (pickerMode() === "track") {
        const tracks = ((state || {}).tracks || []).filter(isMusicalTargetTrack);
        const match = tracks.find(track => {
          const idx = Number(track.index);
          return normalizeToken(track.name) === normalized ||
            normalizeToken(`${idx + 1} ${track.name}`) === normalized ||
            String(idx + 1) === query ||
            String(idx) === query;
        });
        if (match) selectTrackTarget(Number(match.index));
        else chooseFreeQuery(query);
        return;
      }
      const groups = pickerMode() === "layer" ? ((state || {}).layer_groups || []) : ((state || {}).track_groups || []);
      const match = groups.find(group => normalizeToken(group.key) === normalized || normalizeToken(group.label) === normalized);
      if (match) chooseTarget(match.label || query, match.key);
      else chooseFreeQuery(query);
    });
    $("#sentence").addEventListener("input", () => {
      saveDraft();
      renderBrief();
    });
    $("#auditionCount").addEventListener("change", () => {
      renderBrief();
      if (outputMode === "auditions") scheduleOutputPersist();
    });
    $("#evidenceBudget").addEventListener("change", renderBrief);
    $("#outputModeRow").addEventListener("click", event => {
      const button = event.target.closest("button[data-output]");
      if (!button) return;
      outputMode = button.dataset.output || "ask";
      outputModeUserOverride = true;
      scheduleOutputPersist();
      renderBrief();
    });
    function handleBriefFeedClick(event) {
      const dispatchNode = event.target.closest(".brief-dispatch");
      if (dispatchNode) {
        const action = dispatchNode.dataset.action || "";
        const briefId = dispatchNode.dataset.briefId || "";
        if (action === "open_codex") {
          event.preventDefault();
          openBriefInCodex(briefId, dispatchNode.getAttribute("href") || "");
        }
        if (action === "open_working_thread") {
          event.preventDefault();
          openWorkingThread(briefId, dispatchNode.getAttribute("href") || "");
        }
        if (action === "copy_prompt") copyBriefPrompt(briefId);
        return;
      }
      const briefButton = event.target.closest("button.brief-action");
      if (briefButton) {
        const action = briefButton.dataset.action || "";
        const briefId = briefButton.dataset.briefId || "";
        if (action === "rerun") rerunBrief(briefId);
        if (action === "archive") archiveBrief(briefId);
        if (action === "delete") deleteBrief(briefId);
        return;
      }
      const button = event.target.closest("button.audition-action");
      if (!button) return;
      submitAuditionAction(
        button.dataset.action || "",
        button.dataset.jobId || "",
        button.dataset.variant || ""
      );
    }
    $("#pendingBriefFeed").addEventListener("click", handleBriefFeedClick);
    $("#recentBriefFeed").addEventListener("click", handleBriefFeedClick);
    function handleQueueClick(event) {
      const button = event.target.closest("button.queue-action");
      if (!button) return;
      performQueueAction(button.dataset.action || "", button.dataset.id || "");
    }
    $("#needsYouItems").addEventListener("click", handleQueueClick);
    $("#queueItems").addEventListener("click", handleQueueClick);
    $("#fineTuneHead").addEventListener("click", () => $("#fineTune").classList.toggle("open"));
    $("#laneRow").addEventListener("click", event => {
      const button = event.target.closest("button[data-lane]");
      if (!button) return;
      $$("#laneRow .opt").forEach(node => node.classList.remove("on"));
      button.classList.add("on");
      renderBrief();
    });
    $("#protectRow").addEventListener("click", event => {
      const button = event.target.closest("button[data-protect]");
      if (!button) return;
      button.classList.toggle("on");
      renderBrief();
    });
    $("#runBrief").addEventListener("click", () => saveBrief(outputMode));

    refresh();
    setInterval(() => {
      if (!document.hidden) refresh();
    }, 4000);
