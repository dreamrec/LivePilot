# Performance Safety Reference

Complete classification of every LivePilot action for live performance contexts.

## Safe Actions (No Confirmation Needed)

| Action | Tool | Notes |
|--------|------|-------|
| Launch scene | `fire_scene` | Core performance action |
| Launch clip | `fire_clip` | Individual clip triggering |
| Stop clip | `stop_clip` | Individual clip stop |
| Stop track clips | `stop_track_clips` | Clear a track |
| Volume nudge (small) | `set_track_volume` | Delta <= 3 dB only |
| Send nudge | `set_track_send` | Small adjustments to reverb/delay throws |
| Macro nudge | `set_device_parameter` | On mapped macro controls only |
| Filter sweep | `set_device_parameter` | On Auto Filter frequency parameter |
| Mute toggle | `set_track_mute` | Non-destructive, reversible |
| Solo toggle | `set_track_solo` | Non-destructive, reversible |
| Pan nudge (small) | `set_track_pan` | Delta <= 0.2 only |
| Master volume | `set_master_volume` | For overall level control |
| Continue playback | `continue_playback` | Resume from pause |
| Jump to cue | `jump_to_cue` | Navigate arrangement cue points |
| Get state | `get_performance_state` | Read-only, always safe |
| Get playing clips | `get_playing_clips` | Read-only |
| Get scene matrix | `get_scene_matrix` | Read-only |
| Any get_* tool | various | All read-only tools are safe |

## Caution Actions (Require Confirmation)

| Action | Tool | Risk |
|--------|------|------|
| Tempo nudge | `set_tempo` | May destabilize warped audio, synced plugins |
| Device toggle | `toggle_device` | May cause audio pop, click, or silence |
| Large pan move | `set_track_pan` | Disorienting for audience if sudden |
| Large volume jump | `set_track_volume` | Jarring if delta > 3 dB |
| Fire scene clips | `fire_scene_clips` | Selective scene launch, less predictable |
| Set scene tempo | `set_scene_tempo` | Changes tempo on next scene fire |

### Confirmation Protocol

Present as: "[Action description]. Risk: [what could go wrong]. Confirm?"

Keep confirmations short during performance. One line maximum.

## Blocked Actions (Never During Performance)

### Device Chain Surgery
- `find_and_load_device` — loading causes audio thread hiccup
- `delete_device` — removing active device causes dropout
- `load_device_by_uri` — same as find_and_load
- `load_browser_item` — browser loading is unpredictable latency

### Track Structure
- `create_midi_track` / `create_audio_track` / `create_return_track` — track creation pauses audio engine momentarily
- `delete_track` — data loss, audio interruption
- `duplicate_track` — CPU spike
- `set_track_routing` — routing changes can cause feedback or silence

### Clip Editing
- `create_clip` / `delete_clip` / `duplicate_clip` — structural changes while playing
- `set_clip_loop` / `set_clip_warp_mode` / `quantize_clip` — property changes on playing clips
- `add_notes` / `modify_notes` / `remove_notes` — note editing mid-playback

### Arrangement Editing
- All `*_arrangement_*` tools — arrangement view editing during performance
- `set_arrangement_automation` — automation lane changes

### Heavy Operations
- `freeze_track` / `flatten_track` — CPU-intensive, blocks audio thread
- `start_recording` — may cause unexpected monitoring behavior
- `capture_audio` / `capture_midi` — resource-intensive

### Data Operations
- `undo` / `redo` — unpredictable state reversion during live playback
- `memory_learn` / `memory_delete` — non-urgent, save for after the show
- `import_midi_to_clip` — file I/O during performance

## Emergency Procedures

### Audio Problem
1. `set_track_mute(track_index, true)` on the problem track
2. If problem persists: `set_master_volume(0.0)` for fade to silence
3. Last resort: `stop_all_clips` for emergency silence

### Feedback Loop
1. `set_track_mute` on the suspected track immediately
2. `set_track_send` to zero on all sends for that track
3. Gradually unmute after identifying the routing issue

### Wrong Scene Launched
1. Immediately `fire_scene` on the correct scene
2. Or `stop_all_clips` and restart from the correct point
3. Do not use `undo` — it may revert more than intended

### CPU Spike
1. `set_track_mute` on the most CPU-heavy tracks (check `get_session_info` for device counts)
2. `toggle_device` to bypass heavy effects (with caution confirmation skipped in emergency)
3. If critical: `stop_all_clips` and restart with fewer active tracks
