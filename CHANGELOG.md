# Changelog

## [1.4.3] — 2026-03-18

### Fixes
- **`find_and_load_device` now finds raw instruments** — two-pass search: exact name match first (finds "Operator" before "Hello Operator.adg"), then partial match for M4L devices (e.g., "Kickster" matches "trnr.Kickster")
- **Browser now searches plugins and Max for Live categories** — added `browser.plugins` and `browser.max_for_live` to all browser operations. AU/VST/AUv3 plugins (Moog, Drambo, BYOD, etc.) are now discoverable and loadable via `find_and_load_device` and `search_browser("plugins")`
- **`load_browser_item` handles Sounds FileId URIs** — URIs containing internal FileId references (e.g., `query:Sounds#Pad:FileId_6343`) now trigger a deep URI search instead of failing with "not found"
- **`load_browser_item` URI category prioritization** — parses category hint from URI (e.g., `query:Drums#...` searches drums first), reducing search time from 10K+ iterations to under 1K for most loads
- **Iteration limit increased** — `load_browser_item` and `load_device_by_uri` now search up to 50K iterations (was 10K), preventing timeouts on large browser categories
- **Case-insensitive parameter matching** — `set_device_parameter` and `batch_set_parameters` now try exact match first, then case-insensitive fallback. Error messages list available parameter names for debugging
- **Track index validation relaxed** — `_validate_track_index` in arrangement, browser, clips, notes, and tracks MCP tools now allows negative indices for return tracks (-1=A, -2=B) and -1000 for master, consistent with the remote script's `get_track()` behavior

### Added
- `search_browser("plugins")` — browse all installed AU/VST/AUv3 plugins
- `search_browser("max_for_live")` — browse all M4L devices directly
- `search_browser("clips")` and `search_browser("current_project")` — additional browser categories

## [1.4.2] — 2026-03-18

### Fixes
- `memory_recall` multi-word search now works — queries are split into words and matched across name, tags, and qualities (was treating entire query as single substring)
- `set_session_loop` returns correct loop state — echoes requested value instead of reading stale LOM property
- `jump_to_time` returns correct position — echoes requested beat_time instead of reading stale `current_song_time`

## [1.4.1] — 2026-03-18

### Fixes
- Browser search now enforces global 10,000 iteration budget across all categories (was resetting per-category)
- `_search_recursive` returns early when `max_results` is reached instead of scanning remaining siblings
- Narrowed 29 broad `except Exception` catches to specific types (`AttributeError`, `OSError`, `ValueError`) across browser, devices, mixing, and server modules
- Kept `except Exception` only at the 3 outermost dispatch boundaries (router, command processor, logger)

## [1.4.0] — 2026-03-18

### Added
- **Technique Memory System** — 8 new MCP tools (`memory_learn`, `memory_recall`, `memory_get`, `memory_replay`, `memory_list`, `memory_favorite`, `memory_update`, `memory_delete`) for persistent technique storage with agent-written stylistic qualities
- Memory guide reference (`references/memory-guide.md`) with qualities template and examples
- `/memory` command for browsing the technique library
- Producer agent now consults memory by default before creative decisions (override with "fresh" / "ignore history")
- Three memory modes: Informed (default), Fresh (override), Explicit Recall

### Changed
- Tool count: 96 → 104 (10 domains, was 9)
- Commands: 4 → 5 (added /memory)

## 1.3.0 — 2026-03-17

### Enhancements
- **Device tools now support return tracks and master track** — use negative `track_index` for return tracks (-1=A, -2=B) and -1000 for master track. Works with all 12 device tools: `get_device_info`, `get_device_parameters`, `set_device_parameter`, `batch_set_parameters`, `toggle_device`, `delete_device`, `load_device_by_uri`, `find_and_load_device`, `get_rack_chains`, `set_simpler_playback_mode`, `set_chain_volume`, `get_device_presets`
- **Mixing tools now support return tracks** — `set_track_volume`, `set_track_pan`, `get_track_routing`, `set_track_routing` accept negative indices for return tracks
- Fixed `quantize_clip` grid parameter documentation — was incorrectly documented as float beats, now correctly documented as integer enum (0-8)
- Fixed tempo range typo in SKILL.md (was 20-969, corrected to 20-999)

## 1.2.1 — 2026-03-17

### Fixes
- Remove 3 tools that don't work in Live 12's ControlSurface API: `create_group_track`, `freeze_track`, `flatten_track`
- Fix `set_scene_name` — now allows empty string to clear scene name
- Fix `set_scene_tempo` — removed invalid "0 to clear" (Live 12 range is 20-999 BPM)
- All 96 tools live-tested against Ableton Live 12

## 1.2.0 — 2026-03-17

### New Tools (+5, total 96)
- **`set_group_fold`** — fold/unfold a group track to show/hide children
- **`set_track_input_monitoring`** — set input monitoring state (In/Auto/Off)
- **`set_clip_warp_mode`** — set warp mode for audio clips (Beats/Tones/Texture/Re-Pitch/Complex/Complex Pro)
- **`set_scene_color`** — set scene color (0-69)
- **`set_scene_tempo`** — set per-scene tempo that triggers on launch (20-999 BPM)

### Removed Tools (-3)
- **`create_group_track`** — removed due to Live 12 API limitations
- **`freeze_track`** — removed due to Live 12 API limitations
- **`flatten_track`** — removed due to Live 12 API limitations

### Enhancements
- `get_clip_info` now returns `is_midi_clip`, `is_audio_clip`, and audio warp fields (`warping`, `warp_mode`)
- `get_track_info` now returns `is_foldable`, `is_grouped`, `fold_state`, and `current_monitoring_state`

### Fixes
- `set_scene_name` now allows empty string to clear scene name

## 1.1.2 — 2026-03-17

### Fixes
- Added missing `clip_index` validation to 4 arrangement MCP tools
- Standardized `json` import (removed `_json` alias)
- Added index range to arrangement clip error messages for consistency
- Made installer version-agnostic (`/^Live \d+/` regex instead of hardcoded "Live 12")
- Standardized project description across all config files

## 1.1.1 — 2026-03-17

### Fixes
- Fixed `create_arrangement_clip` ignoring `loop_length` parameter (was always using source clip length for tiling)
- Fixed double `end_undo_step()` calls in `create_arrangement_clip` and `set_arrangement_automation` (now uses `try/finally`)
- Fixed `back_to_arranger` setting wrong value (`False` → `True`)
- Added guard against `None` clip index after arrangement placement failure
- Fixed `--doctor` summary not reflecting connection test result in exit code

## 1.1.0 — 2026-03-17

### New Tools (+7)
- **`back_to_arranger`** — switch playback from session clips back to arrangement timeline
- **`get_arrangement_notes`** — read MIDI notes from arrangement clips
- **`remove_arrangement_notes`** — remove notes in a region of an arrangement clip
- **`remove_arrangement_notes_by_id`** — remove specific notes by ID
- **`modify_arrangement_notes`** — modify notes by ID (pitch, time, velocity, probability)
- **`duplicate_arrangement_notes`** — copy notes by ID with optional time offset
- **`get_device_presets`** — list presets for any device (audio effects, instruments, MIDI effects)

### Fixes
- Fixed arrangement tools test coverage (was missing 5 tools from expected set)
- Synchronized tool count across all documentation (was 80/81/84, now consistently 91)

## 1.0.0 — 2026-03-17

Initial release.

### Features
- **84 MCP tools** across 9 domains: transport, tracks, clips, notes, devices, scenes, mixing, browser, arrangement
- **Remote Script** for Ableton Live 12 with thread-safe command queue via `schedule_message`
- **MCP Server** (FastMCP) with input validation, auto-reconnect, and structured error messages
- **CLI** (`npx livepilot`) with `--install`, `--uninstall`, `--status`, `--doctor`, `--version`
- **Claude Code Plugin** with:
  - `livepilot-core` skill — core discipline and workflow guides
  - `livepilot-producer` agent — autonomous production from high-level descriptions
  - 4 slash commands: `/session`, `/beat`, `/mix`, `/sounddesign`
- **Installer** with auto-detection of Ableton paths on macOS and Windows
- **Live 12 modern note API** support: note IDs, probability, velocity_deviation
- **JSON over TCP** protocol on port 9878 with structured error codes
