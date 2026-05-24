# LivePilot Context

> Shared language and stable architectural decisions for LivePilot — the
> Ableton Live MCP plugin (465 tools, three-layer architecture: Device
> Atlas + M4L Analyzer + Technique Memory). Consumed by Claude Code
> sessions before any work on this repo.
>
> A companion `CONTEXT-local.md` (gitignored) captures session-specific
> discoveries that aren't appropriate for public distribution.

## Language

Use these terms exactly. LivePilot has a deep vocabulary because Ableton
itself does — the agent must speak both Live's language and ours.

### Live-domain terms (Ableton's vocabulary)

**Clip** — A unit of MIDI or audio playback. Lives in a slot on a track,
or on the arrangement timeline. _Avoid_: loop (overloaded with the loop
flag of a clip).

**Scene** — A horizontal row across all tracks in session view, with
its own tempo and time-signature fields. _Avoid_: snapshot (that's a TD
term).

**Track** — Audio / MIDI / Return / Master, plus group folds. The
**master** track is special: routing terminus and the home of the
**LivePilot_Analyzer**. _Avoid_: channel (Live calls them tracks).

**Device** — Anything in a track's device chain: an instrument, audio
effect, MIDI effect, plug-in (VST/AU), or rack. _Avoid_: plugin (too
narrow — racks are devices too).

**Rack** — A container device with internal **chains**. Four types:
instrument rack, drum rack, audio-effect rack, MIDI-effect rack. Has
**macros** (1–16 controllable knobs) that map to internal parameters.

**Chain** — One parallel path inside a rack. Distinct from a device
chain (the linear track-level sequence). _Avoid_: lane (which is a
take-lane thing).

**Take lane** — A nested clip lane on a track for capture takes. Created
by `create_take_lane`. _Avoid_: layer.

**Simpler** — Live's bundled sampler. Has **slices** (transient-sliced
chops), playback modes, and a `sample` child holding the audio source.

**Send / Return** — Tracks of type `Return` receive sends from other
tracks; the `Master` receives everything. Sends are on tracks, returns
are tracks.

**Warp marker** — A time-domain anchor on an audio clip's warping grid.
Manipulated via `add_warp_marker`, `move_warp_marker`,
`remove_warp_marker`.

### LivePilot-domain terms (ours)

**MCP server** — Python FastMCP at `mcp_server/`. Validates inputs,
forwards commands to the Remote Script over JSON-over-TCP (port 9878).

**Remote Script** — `remote_script/LivePilot/`, a Live ControlSurface
loaded inside Ableton's Python. Single-TCP-client architecture. Reload
via the `reload_handlers` tool, never via the Live Preferences toggle.

**M4L Bridge** — `m4l_device/` Audio Effect on the master track,
UDP/OSC bridge (9880 / 9881) for deep LiveAPI access. Optional — all
core tools work without it.

**Device Atlas** — `mcp_server/atlas/`. In-memory indexed JSON database
of 5264 devices (URIs, categories, tags, genres). 7 indexes. Resolves
from `~/.livepilot/atlas/device_atlas.json` (user scan) if present, else
the bundled baseline. _Avoid_: catalog (overloaded with the device-corpus
markdown).

**Concept surface** — `livepilot/skills/livepilot-core/references/`. The
translation layer between LLM training (artist / genre vocabularies)
and LivePilot tools. Read these before device selection when the user
says "sound like X."

**Sample Engine** — `mcp_server/sample_engine/`. Three sources (Browser,
Splice, Filesystem), 6-critic fitness battery, 29-technique library.

**Composer** — `mcp_server/composer/`. Prompt → plan pipeline. Compiles
`CompositionIntent` to executable tool sequences.

**Corpus** — `mcp_server/corpus/`. Parsed device-knowledge markdown
turned into queryable Python structures (EmotionalRecipe, GenreChain,
PhysicalModelRecipe, AutomationGesture). Distinct from the Atlas.

**Engine** — One of the named LivePilot subsystems with its own skill
and tool family: `mix_engine`, `sound_design_engine`, `composition_engine`,
`arrangement_engine`, `performance_engine`, `sample_engine`,
`wonder_engine`, `evaluation_engine`. Routing decisions in the
**Execution Router** classify steps to the right engine.

**Experiment** — A named, snapshotable variation of session state,
created via `create_experiment`, compared via `compare_experiments`,
committed via `commit_experiment` or discarded via `discard_experiment`.

**Preview set / preview variant** — A set of rendered variations for
A/B audition, created via `create_preview_set` and `render_preview_variant`.

**Critic** — A diagnostic function (e.g. `get_mix_issues`,
`analyze_synth_patch`) that returns structured problems without
modifying state. Critics are the foundation of evaluation loops.

**Action ledger** — The history of mutating operations available via
`get_recent_actions` and `get_action_ledger_summary`. Drives `undo`,
`redo`, and post-hoc analysis.

**Tool count** — 465 tools across 56 domains. Source of truth lives in the
release-checklist skill (`livepilot-release`).

## Relationships

- A **session** runs a **skill**, the skill calls **tools**, tools
  dispatch via the **Execution Router** to the right **engine**.
- An **action** mutates state and lands in the **action ledger**; a
  **critic** reads state without writing and feeds back into the agent.
- An **experiment** wraps a sequence of actions in a rollback boundary;
  on commit it merges into the trunk session, on discard it reverts.
- The **Device Atlas** answers "what is this device" / "what is similar";
  the **Corpus** answers "what techniques apply"; the **Concept surface**
  answers "what does the user mean by 'X'".
- **LivePilot_Analyzer must be LAST on master** — always after all
  master-bus effects so it reads the final output, not pre-effect signal.

## Flagged ambiguities

- "chain" alone is ambiguous: rack-internal chain vs. track-level device
  chain. Qualify with "rack chain" / "device chain".
- "device" without qualifier means any thing in a track's chain. When the
  difference matters: "instrument device", "audio-effect device",
  "MIDI-effect device", "rack device".
- "scene" can mean Live's row primitive or the session-state idea — for
  our codebase it's always Live's row.

---

## Architectural decision records

### ADR-001 — Single TCP client on port 9878

**Status:** Adopted.

**Context.** Live's Remote Script Python is single-threaded; opening a
new TCP listener for every MCP call would race against the LOM main
thread.

**Decision.** Port 9878 accepts one connection at a time. The MCP server
holds the persistent connection. Direct ad-hoc TCP calls fail with
"Another client is already connected" if the MCP server is active. Tools
always go through the MCP layer.

**Consequences.** Clean single-writer semantics. Tradeoff: external
debug clients can't snoop without disconnecting the MCP server first.

### ADR-002 — All LOM calls execute on Ableton's main thread

**Status:** Adopted.

**Context.** Live's Object Model is not thread-safe. Calling LOM
operations from a background thread crashes Live unpredictably.

**Decision.** Every LOM call goes through the `schedule_message` queue,
which dispatches on the next main-thread tick. Helpers in
`remote_script/LivePilot/` wrap this pattern.

**Consequences.** All LOM operations are async at the implementation
level even when they look synchronous to the tool caller. Test fixtures
must mock the schedule queue or run in an event-loop-aware harness.

### ADR-003 — Remote Script reload via `reload_handlers` tool, never Live UI

**Status:** Adopted.

**Context.** After editing `remote_script/LivePilot/*.py`, the
ControlSurface needs to re-register handlers. Manually toggling the
Control Surface in Live → Preferences → Link/MIDI severs the persistent
TCP connection and forces a full re-handshake.

**Decision.** After any handler edit: run `npx livepilot --install` (NOT
`node installer/install.js`, which is a no-op as a script), then call
the `reload_handlers` MCP tool. The tool uses `pkgutil` + `importlib`
to re-fire `@register` decorators in place while the TCP connection
stays open.

**Consequences.** Iteration is fast — no Live restart needed for
handler changes. Cost: contributors must remember the canonical install
command vs. the file-only export.

### ADR-004 — LivePilot_Analyzer is the last device on master

**Status:** Adopted (binding rule).

**Context.** The analyzer is the perception layer — it must read the
final mastered signal, not an intermediate pre-effect bus.

**Decision.** Insertion order is enforced: LivePilot_Analyzer comes
after every master-bus effect (EQ, Compressor, Utility, etc.).
`verify_all_devices_health` flags violations.

**Consequences.** When a user complains "my mix analysis is wrong",
first check master device order.

### ADR-005 — User atlas under `~/.livepilot/`, never in the bundled atlas

**Status:** Adopted v1.22.0.

**Context.** Users have personal packs, user library, plugin inventories
that should survive npm updates and stay out of the public repo.

**Decision.** `scan_full_library` writes to `~/.livepilot/atlas/device_atlas.json`.
`_resolve_atlas_path()` in `mcp_server/atlas/__init__.py` prefers the
user path if present, else the bundled baseline.

**Consequences.** npm updates don't trample user scans. The user path
also serves as cache for slow scan operations.

---

## Live pointers

- **Tool count + version source of truth.** Release-prep skill at
  `livepilot/skills/livepilot-release/SKILL.md`.
- **CI status.** Not currently in `gh` for this repo — check
  `BUGS_TESTING_<date>.md` files for the latest manual QA pass.
- **Concept surface vocabularies.** `livepilot/skills/livepilot-core/references/artist-vocabularies.md`
  and `.../genre-vocabularies.md`. Read these BEFORE device selection
  when the user says "sound like X" or "make me a <genre>".
- **Skills index.** `livepilot/skills/*/SKILL.md` — 14 skills, one per
  engine and one core.

## How to update this document

Add to **Language** when a new term is being used inconsistently across
skills, tools, or memory entries. Add an **ADR** when a load-bearing
decision (single-TCP-client, main-thread routing, analyzer position) is
likely to be relitigated.

Session-specific findings go in `CONTEXT-local.md`.
