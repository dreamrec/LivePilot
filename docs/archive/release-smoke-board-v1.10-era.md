# Release Smoke Board

Manual validation checklist for LivePilot releases. Run through these scenarios
in a real Ableton Live 12 session before tagging a release.

## Scenarios

### 1. Empty Ableton Set
- [ ] `get_session_info` returns valid response
- [ ] `build_song_brain` returns with `capability: analytical_only` or `fallback`
- [ ] `enter_wonder_mode "I'm stuck"` returns diagnosis with low confidence
- [ ] `detect_stuckness` returns `flowing` (no action history)
- [ ] No crashes or unhandled exceptions

### 2. Drum Loop (4 tracks)
- [ ] Beat creation via `/beat` produces playable MIDI
- [ ] `find_primary_hook` detects groove pattern
- [ ] `get_motif_graph` runs without TCP errors
- [ ] `build_song_brain` includes motif evidence in `evidence_breakdown`
- [ ] `detect_repetition_fatigue` reports if looping

### 3. Arranged Song (8+ scenes)
- [ ] `build_song_brain` infers section purposes
- [ ] `score_emotional_arc` produces meaningful arc
- [ ] `detect_hook_neglect` checks section placement
- [ ] `enter_wonder_mode "make it more interesting"` generates distinct variants
- [ ] Transition analysis works between scenes

### 4. Plugin-Heavy Set (AU/VST)
- [ ] `find_and_load_device` works for native devices
- [ ] `get_device_parameters` works for plugins
- [ ] Plugin health check detects dead plugins (parameter_count <= 1)
- [ ] No crashes when walking deep rack chains

### 5. M4L Absent
- [ ] All 210+ core tools work
- [ ] Perception tools report `unavailable` in capability
- [ ] `render_preview_variant` returns `metadata_only_preview` mode
- [ ] No unhandled exceptions from missing bridge

### 6. M4L Active (Analyzer on master)
- [ ] `get_master_spectrum` returns 8-band data
- [ ] `get_detected_key` returns key estimate
- [ ] `render_preview_variant` attempts `audible_preview` mode
- [ ] Spectral comparison included in preview result when available

### 7. Server Restart
- [ ] Taste persists in `~/.livepilot/taste.json` after restart
- [ ] Technique library intact after restart
- [ ] `--doctor` reports persistence status correctly
- [ ] Project continuity threads available after restart (if same project)

## Pass Criteria

All scenarios must complete without unhandled exceptions.
Capability-dependent features must clearly report their mode.
No silent failures — every degradation must be visible in the response.
