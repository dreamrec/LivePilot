---
name: livepilot-devices
description: This skill should be used when the user asks to "load a device", "add an effect", "find a plugin", "device chain", "rack", "preset", "sound design setup", "load instrument", "find a synth", or wants to browse, load, and configure devices in Ableton Live.
---

# Device Loading and Configuration

Load instruments, effects, and plugins into Ableton Live tracks. Every device operation follows one discipline: search first, verify after.

## Primary Workflow — Atlas-Driven

The device atlas contains 1,305 devices with sonic descriptions, recipes, and recommendations. Always start here:

1. **Discover:** `atlas_search(query)` — find devices by name, sound character, or genre
2. **Learn:** `atlas_device_info(device_id)` — full parameters, recipes, gotchas, pairings
3. **Suggest:** `atlas_suggest(intent, genre)` — "I need a warm pad" → ranked device+recipe combos
4. **Chain:** `atlas_chain_suggest(role, genre)` — full device chain for a track role (instrument + effects)
5. **Load:** Use the URI from atlas results → `load_browser_item(uri)` or `find_and_load_device(name)`
6. **Recipe:** Apply starter recipe params → `batch_set_parameters(params)` from the atlas entry
7. **Verify:** `get_device_info(track_index, device_index)` — check health flags

If the atlas doesn't have a device (newly installed plugin, user sample), fall back to the browser workflow below.

## Browser Workflow — The Fallback Path

Use the browser workflow when the atlas doesn't have what you need:

1. **Search:** `search_browser(path, name_filter)` — returns a list of matching items with exact URIs
2. **Inspect:** Read the results. Confirm the item name, type, and path match what you need
3. **Load:** `load_browser_item(uri)` — pass the exact URI string from search results

Common search paths:
- `path="Instruments"` — synths, samplers, instrument racks
- `path="Drums"` — drum racks, drum kits, percussion
- `path="Audio Effects"` — reverb, delay, compressor, EQ, saturator
- `path="MIDI Effects"` — arpeggiator, chord, scale, random
- `path="Sounds"` — preset sounds organized by category
- `path="Samples"` — audio samples, one-shots, loops

Combine path with `name_filter` to narrow results. Example: `search_browser(path="Drums", name_filter="808 Kit")`.

NEVER invent device or preset names. A hallucinated name like "echomorph-hpf" or "Drift Pad Wonk" will crash the load. Always search first, then use the exact URI from results.

## find_and_load_device — The Shortcut

Use `find_and_load_device(name)` ONLY for these simple built-in effects:
- "Reverb"
- "Delay"
- "Compressor"
- "EQ Eight"
- "Saturator"
- "Utility"

For everything else — instruments, racks, presets, AU/VST plugins — use the browser workflow. The shortcut matches greedily and can load a sample file instead of a synth when names overlap (e.g., "Drift" matches "Synth Bass Drift Pad Wonk Bass.wav" before the Drift synthesizer).

## Plugin Health Verification

After loading any device, verify it actually works:

1. Call `get_device_info(track_index, device_index)` on the newly loaded device
2. Check `parameter_count` — if the device is an AU/VST plugin (`class_name` contains "PluginDevice") and `parameter_count` is 1 or less, the plugin is dead. The shell loaded but the DSP engine crashed.
3. Check `health_flags` for `opaque_or_failed_plugin` (dead or untweakable AU/VST) or `sample_dependent` (needs source audio)
4. Check `plugin_host_status` and `mcp_sound_design_ready`
5. If `mcp_sound_design_ready` is `false`: delete the device with `delete_device`, replace it with a native Ableton alternative, and report the failure to the user

Dead plugin recovery pattern:
```
get_device_info → parameter_count <= 1 on PluginDevice?
  → delete_device(track_index, device_index)
  → search_browser for native alternative
  → load_browser_item with replacement URI
  → report failure and substitution to user
```

## Rack Introspection

Use `walk_device_tree(track_index)` to see the full nested structure of racks on a track — Instrument Racks, Audio Effect Racks, and Drum Racks with all their chains and sub-devices.

Use `get_rack_chains(track_index, device_index)` to inspect individual rack chain contents. For Drum Racks, this reveals which pads have samples loaded and which chains exist. An empty Drum Rack (zero chains) produces silence.

Set chain volumes with `set_chain_volume(track_index, device_index, chain_index, volume)` to balance rack layers.

## Drum Rack Rule

NEVER load a bare "Drum Rack" — it is an empty container with zero chains and produces silence. Always load a kit preset through the browser:

```
search_browser(path="Drums", name_filter="Kit")
```

Pick a real kit from results: "909 Core Kit", "808 Core Kit", "Boom Bap Kit", "Lo-Fi Kit", etc. These come pre-loaded with samples on their pads.

After loading any Drum Rack preset, verify with `get_rack_chains` that chains exist and have named pads like "Bass Drum", "Snare", "Hi-Hat".

## Sample-Dependent Devices

These devices load "successfully" with many parameters but produce zero audio without source material. Since MCP tools cannot load samples into third-party plugin UIs, NEVER use these as standalone instruments:

- **Granular synths:** iDensity, Tardigrain, Koala Sampler, Burns Audio Granular
- **Bare samplers:** Simpler (empty), Sampler (empty) — always load a preset, never the empty shell
- **Sample players:** AudioLayer, sEGments

Use self-contained synthesizers instead — these produce sound immediately from MIDI input alone:
- **Wavetable** — versatile wavetable synthesis
- **Operator** — FM synthesis, 4 operators
- **Drift** — analog-modeled, warm and organic
- **Analog** — subtractive analog modeling
- **Meld** — MPE-ready, two engines
- **Collision** — physical modeling, mallet/resonator
- **Tension** — physical modeling, string/exciter

If granular textures are needed: use Wavetable with aggressive wavetable position modulation, Operator with FM feedback and short envelopes, or load a Simpler/Sampler **preset** (not the bare instrument) from the Sounds browser.

## Simpler Operations

For Simpler devices that already have samples loaded:

- `load_sample_to_simpler(track_index, device_index, file_path)` — load audio into Simpler
- `replace_simpler_sample(track_index, device_index, file_path)` — swap the current sample. Only works on Simplers that already have a sample loaded.
- `crop_simpler(track_index, device_index)` — trim sample to current start/end points
- `reverse_simpler(track_index, device_index)` — reverse the loaded sample
- `get_simpler_slices(track_index, device_index)` — retrieve auto-detected slice points (Slice mode)
- `set_simpler_playback_mode(track_index, device_index, playback_mode)` — switch modes: 0=Classic, 1=One-Shot, 2=Slice. Optional: `slice_by` (0=Transient, 1=Beat, 2=Region, 3=Manual), `sensitivity` (0.0-1.0, Transient only)
- `warp_simpler(track_index, device_index, beats)` — warp sample to fit N beats

### Slice Workflow

For slice-based production, use `plan_slice_workflow`:
1. `plan_slice_workflow(file_path=..., intent="rhythm")` — generates a complete workflow with Simpler setup, slice mapping, and MIDI notes
2. Intents: `rhythm`, `hook`, `texture`, `percussion`, `melodic`
3. The tool returns a step-by-step plan — execute each tool call in sequence

Manual slice workflow: load sample → `set_simpler_playback_mode(playback_mode=2)` → `get_simpler_slices` → program MIDI notes targeting slice indices (C3 = slice 0, C#3 = slice 1, etc.)

### New Device Operations (12.3+)

- `insert_device(track_index, device_name)` — insert native device by name (10x faster than browser, 12.3+)
- `insert_rack_chain(track_index, device_index)` — add chain to Instrument/Audio/Drum Rack
- `set_drum_chain_note(track_index, device_index, chain_index, note)` — assign MIDI note to Drum Rack chain
- `move_device(track_index, device_index, new_index)` — reorder devices on a track

### Plugin Deep Control

- `get_plugin_parameters(track_index, device_index)` — all AU/VST plugin parameters
- `map_plugin_parameter(track_index, device_index, parameter_index)` — map for automation
- `get_plugin_presets(track_index, device_index)` — list plugin presets

## Effect Chain Best Practices

After loading any effect, verify its key parameters are not at pass-through defaults:
- **Reverb:** `Dry/Wet` should be > 0 (typically 20-40% for subtle, 60-100% for creative)
- **Delay:** `Dry/Wet` > 0, `Feedback` set appropriately
- **Compressor:** `Threshold` below signal level, `Ratio` > 1:1
- **EQ Eight:** At least one band with non-zero gain
- **Saturator:** `Drive` > 0 dB
- **Utility:** `Gain` at target value, `Width` as needed

Use `get_device_parameters` to read current values, then `set_device_parameter` or `batch_set_parameters` to configure. Use `toggle_device` to bypass/enable devices for A/B comparison.

## Device Presets

- `get_device_presets(track_index, device_index)` — list available presets for the loaded device
- `get_plugin_parameters(track_index, device_index)` — see all AU/VST plugin parameters
- `get_plugin_presets(track_index, device_index)` — list presets for AU/VST plugins
- `map_plugin_parameter(track_index, device_index, parameter_index)` — map a plugin parameter for automation

## Device Atlas Reference

Consult `references/device-atlas/` in the livepilot-core skill for the full corpus of 280+ instruments, 139 drum kits, and 350+ impulse responses. The atlas contains real browser URIs, preset names, and sonic descriptions. Use it as your lookup table before loading any device — never guess a name that is not in the atlas or in browser search results.
