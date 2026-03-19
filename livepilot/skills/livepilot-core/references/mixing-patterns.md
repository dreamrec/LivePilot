# Mixing Patterns Reference

Timeless mixing knowledge for Ableton Live 12, structured as actionable recipes with specific parameter values.

---

## 1. Gain Staging

### Principles

- **Headroom target:** Keep master bus peaking at -6 dB before mastering; -3 dB minimum
- **Individual tracks:** Aim for peaks around -12 to -8 dBFS per track
- **Floating-point safety:** Live's 32-bit float engine has near-infinite internal headroom — tracks can go "into the red" without clipping internally. Clipping only occurs at physical outputs (sound card D/A) or when exporting/rendering
- **Gain before processing:** Set source gain (sample volume, synth output) before effects chains. Plugins modeled on analog hardware (tape, consoles, compressors) respond differently at different input levels
- **Utility for staging:** Place Utility device first in chain; use its Gain knob to trim signal to target level before downstream effects

### API Volume Mapping

| API Value | Approximate dB | Use Case |
|-----------|---------------|----------|
| `0.0` | -inf (silence) | Muted |
| `0.50` | ~ -12 dB | Conservative mix level |
| `0.70` | ~ -6 dB | Typical track level |
| `0.85` | ~ 0 dB | Unity gain (fader at 0 dB) |
| `1.0` | +6 dB | Maximum fader position |

> **Note:** The fader range is 0.0-1.0 in the API, where 1.0 = +6 dB. The scale is logarithmic. 0.85 is the commonly referenced value for 0 dB (unity gain).

---

## 2. Parallel Compression (New York Compression)

### Concept

Blend a heavily compressed copy of a signal with the dry original to add density and sustain without destroying transients.

### Setup Method A: Send/Return (Preferred)

1. Create a return track (`create_return_track`)
2. Load Compressor on return track (`find_and_load_device`)
3. Set Compressor to aggressive settings (see below)
4. Set sends from source tracks to the return (`set_track_send`)
5. Blend with return track volume (`set_track_volume`)

### Setup Method B: Audio Effect Rack

1. Drop an Audio Effect Rack on the track
2. Create two chains: "Dry" (empty) and "Compressed" (with Compressor)
3. Adjust chain volumes to blend (`set_chain_volume`)

### Compressor Settings for Parallel Compression

| Parameter | Value | Notes |
|-----------|-------|-------|
| Threshold | -30 to -20 dB | Very low — catch everything |
| Ratio | 8:1 to 20:1 | Heavy compression |
| Attack | 0.5 - 5 ms | Fast to catch transients |
| Release | 50 - 150 ms | Medium, follows groove |
| Knee | 0 dB | Hard knee for aggressive character |
| Makeup Gain | +6 to +12 dB | Compensate for heavy GR |
| Dry/Wet | 100% (on return) | Full wet; blend via send/return levels |

### Enhancement: Mid-Scoop EQ After Compressor

Add EQ Eight after the compressor on the return track:
- Cut 200-500 Hz by -3 to -6 dB (reduce mud from compressed signal)
- This adds punch without muddiness

### Typical Applications

- **Drums:** Send all drum tracks to parallel compression return; adds body and sustain
- **Bass:** Light send amount adds density
- **Vocals:** Brings out detail and presence
- **Full mix:** Subtle parallel compression on master (use with caution)

---

## 3. Sidechain Compression

### Concept

Use one signal (trigger) to control compression on another signal (target). Classic use: kick drum ducks bass/pads for rhythmic pumping.

### Setup in Ableton Live

1. Place Compressor on the target track (e.g., bass)
2. Enable Sidechain section (toggle triangle)
3. Set sidechain Audio From to the trigger track (e.g., kick drum track)
4. Adjust compressor to taste

### Settings by Genre

#### EDM / House / Techno (Heavy Pump)

| Parameter | Value |
|-----------|-------|
| Threshold | -30 to -20 dB |
| Ratio | Inf:1 (limiter mode) |
| Attack | 0.01 - 0.1 ms |
| Release | 100 - 300 ms |
| Knee | 0 dB (hard) |
| Mode | Peak |

#### Deep House / Lo-Fi (Subtle Pump)

| Parameter | Value |
|-----------|-------|
| Threshold | -20 to -15 dB |
| Ratio | 4:1 to 6:1 |
| Attack | 1 - 5 ms |
| Release | 200 - 400 ms |
| Knee | 6 dB (soft) |
| Mode | RMS |

#### Drum & Bass / Dubstep (Quick Duck)

| Parameter | Value |
|-----------|-------|
| Threshold | -25 to -15 dB |
| Ratio | 8:1 to Inf:1 |
| Attack | 0.01 ms |
| Release | 50 - 150 ms |
| Knee | 0 dB |
| Mode | Peak |

### Pro Tips

- Increase output gain on the compressor for a more dramatic "rise" at the tail of the pump
- Use the sidechain EQ to filter the trigger signal (e.g., HPF to only trigger from kick's click, not its sub)
- For transparent ducking without the pump feel: longer attack (10-30 ms), faster release (50-100 ms)
- Ghost sidechain: use a muted MIDI track with a simple kick pattern as the trigger source for consistent timing

---

## 4. Send/Return Patterns

### Standard 4-Return Template

#### Return A: Short Reverb (Room)

**Device:** Reverb (Live's stock)
**Purpose:** Glue elements together, simulate shared space

| Parameter | Value |
|-----------|-------|
| Dry/Wet | 100% (on return track) |
| Decay Time | 0.5 - 1.2 s |
| Pre-Delay | 10 - 25 ms |
| Room Size | Small to Medium |
| Diffusion | High (> 80%) |
| High Cut (Reflect) | 4 - 8 kHz |
| Low Cut (Reflect) | 200 - 400 Hz |

**Send targets:** Snare, percussion, keys, vocals (light amounts)

#### Return B: Long Reverb (Hall)

**Device:** Reverb
**Purpose:** Create depth and spaciousness

| Parameter | Value |
|-----------|-------|
| Dry/Wet | 100% |
| Decay Time | 2.5 - 5.0 s |
| Pre-Delay | 30 - 80 ms |
| Room Size | Large |
| Diffusion | High |
| High Cut (Reflect) | 3 - 6 kHz |
| Low Cut (Reflect) | 300 - 500 Hz |

**Send targets:** Pads, strings, vocals, FX (moderate amounts)

#### Return C: Delay (Sync'd)

**Device:** Delay
**Purpose:** Rhythmic echoes, width

| Parameter | Value |
|-----------|-------|
| Dry/Wet | 100% |
| Sync | On |
| Delay Time L | 3/16 or 1/8 |
| Delay Time R | 1/8 or 1/4 (offset for stereo) |
| Feedback | 30 - 50% |
| Filter On | Yes |
| HP Filter | 200 - 500 Hz |
| LP Filter | 4 - 8 kHz |
| Ping Pong | Optional (for stereo movement) |

**Enhancement:** Place EQ Eight after Delay to cut low end from echoes (HPF at 200 Hz)

**Send targets:** Vocals, synth leads, hi-hats (light), snare (light)

#### Return D: Parallel Compression

**Device:** Compressor (see Section 2 settings)
**Purpose:** Add punch and density to drums

**Chain:** Compressor -> EQ Eight (mid-scoop at 300-500 Hz, -4 dB)

**Send targets:** Kick, snare, toms, percussion

### Return Track Guidelines

- Always set effect Dry/Wet to 100% on return tracks — the send level controls the blend
- Use Pre-fader sends when you want reverb/delay tails to continue after fading out the source
- Use Post-fader sends (default) for normal mixing where effect follows source level
- High-pass the return track at 80-150 Hz to prevent low-end buildup from reverb/delay

---

## 5. Stereo Width Techniques

### Panning Strategies

| Element | Pan Position | Rationale |
|---------|-------------|-----------|
| Kick | Center (0.0) | Anchor, mono compatibility |
| Snare | Center (0.0) | Core rhythm element |
| Bass | Center (0.0) | Low-end energy, mono compat |
| Vocals (lead) | Center (0.0) | Focus point |
| Hi-hat | Slight L or R (-0.15 to 0.15) | Realism, slight offset |
| Toms | Spread L to R (-0.5 to 0.5) | Stereo drum image |
| Rhythm guitar L | Left (-0.6 to -0.8) | Stereo pair |
| Rhythm guitar R | Right (0.6 to 0.8) | Stereo pair |
| Keys / Pads | Wide (-0.4 to 0.4) or stereo | Fill the sides |
| Backing vocals | Spread (-0.3 to 0.3) | Width behind lead |
| Percussion | Various (-0.7 to 0.7) | Movement and space |
| FX / Risers | Wide or automated | Interest and motion |

> API pan range: -1.0 (full left) to 1.0 (full right), 0.0 = center

### Stereo Pan Mode

Right-click any pan knob and select "Convert Pan to Stereo Pan" for independent L/R channel panning. Useful for stereo synths and samples.

### Utility Device for Width

| Width Value | Effect |
|-------------|--------|
| 0% | Mono (collapses L+R to center) |
| 100% | Normal stereo (default) |
| 100-200% | Enhanced width (side signal boosted) |
| 200% | Side-only (mono content removed) |

### Frequency-Dependent Width ("Upside Triangle")

**Goal:** Narrow low end, wide high end. This ensures mono compatibility for bass while creating spaciousness in the upper spectrum.

**Method using Audio Effect Rack:**

1. Create Audio Effect Rack with 3 chains:
   - **Low chain:** EQ Eight (LPF at 200 Hz) -> Utility (Width 0%, mono)
   - **Mid chain:** EQ Eight (BPF 200 Hz - 4 kHz) -> Utility (Width 100%)
   - **High chain:** EQ Eight (HPF at 4 kHz) -> Utility (Width 120-150%)

**Simpler method with EQ Eight in M/S mode:**
1. Set EQ Eight to M/S mode
2. On the Side channel: apply HPF at 150-250 Hz (removes stereo info below this)
3. Optionally boost high-shelf on Side above 4 kHz for air and width

### Haas Effect (Micro-Delay Widening)

1. Place Delay on track
2. Set one channel to 10-30 ms, other to 0 ms
3. **Warning:** Check mono compatibility — Haas effect causes phase cancellation in mono

### Mid/Side Processing with Utility

- **Extract Mid (mono center):** Utility with Width at 0%
- **Extract Side (stereo difference):** Utility with Width at 200%
- Use in parallel chains to process mid and side independently

---

## 6. Low-End Management

### Bass/Kick Relationship Strategies

#### Strategy 1: Frequency Separation (EQ Carving)

Decide which element owns the sub:
- **Kick-dominant sub:** HPF bass at 60-80 Hz, let kick fill sub. Boost bass body at 100-200 Hz
- **Bass-dominant sub:** HPF kick at 50-60 Hz (gentle), boost kick attack at 2-5 kHz. Let bass fill sub range

Complementary EQ cuts:
- If kick has a bump at 60 Hz, cut bass at 60 Hz (and vice versa)
- If kick has presence at 3 kHz, cut bass at 3 kHz

#### Strategy 2: Sidechain Ducking

Place Compressor on bass with kick as sidechain input. Both can share the sub range because the bass ducks when the kick hits.

#### Strategy 3: Multiband Sidechain

Use Multiband Dynamics on bass, sidechain only the low band (below 120 Hz) from the kick. Upper bass harmonics stay unaffected.

### High-Pass Filtering Guide

| Instrument | HPF Frequency | Slope |
|------------|--------------|-------|
| Kick drum | None or 30 Hz | 24 dB/oct |
| Bass | None or 30 Hz | 24 dB/oct |
| Snare | 80 - 120 Hz | 18-24 dB/oct |
| Hi-hats | 200 - 400 Hz | 12-18 dB/oct |
| Guitars | 80 - 120 Hz | 12 dB/oct |
| Keys / Piano | 60 - 100 Hz | 12 dB/oct |
| Vocals | 80 - 120 Hz | 18 dB/oct |
| Pads / Strings | 100 - 200 Hz | 12 dB/oct |
| FX / Risers | 150 - 300 Hz | 12 dB/oct |

### Mono Below Frequency

Keep everything below ~150-250 Hz in mono for:
- Mono club playback compatibility
- Vinyl cutting (stereo bass causes needle skip)
- Cleaner low end, less phase issues

**Implementation:** See Section 5 "Frequency-Dependent Width" method

### Sub Frequency Handling

- Sub bass (20-60 Hz): Should be clean sine or triangle. Avoid complex harmonics
- One element at a time in sub range — never two sounds competing below 60 Hz
- Use spectrum analyzer to verify sub content (Spectrum device on master)

---

## 7. EQ Patterns

### Frequency Character Map

| Range | Name | Character | Common Actions |
|-------|------|-----------|----------------|
| 20-60 Hz | Sub bass | Felt more than heard, physical rumble | HPF non-bass instruments; clean up with surgical cuts |
| 60-250 Hz | Bass body | Warmth, fullness, weight | Boost for warmth, cut for clarity |
| 200-500 Hz | Low mids / "Mud" | Boxy, muddy, nasal | Cut broadly by 2-4 dB on most tracks to clean mix |
| 500 Hz-1 kHz | Mid body | Honky, hollow | Cut for space, boost for body on thin sounds |
| 1-4 kHz | Upper mids / Presence | Bite, attack, clarity, aggression | Boost vocals/guitars for presence; harsh if overdone |
| 4-8 kHz | Brilliance | Sibilance, definition, edge | De-ess vocals; boost for articulation |
| 8-12 kHz | Sparkle | Crisp, bright, shimmer | Boost cymbals/acoustic guitars for life |
| 12-20 kHz | Air | Airy, open, ethereal | Gentle shelf boost for "air"; roll off if harsh |

### Common EQ Recipes by Instrument

#### Kick Drum
- HPF: 30 Hz (remove sub rumble below tuning)
- Boost: +2-4 dB at 50-80 Hz (sub weight)
- Cut: -3-5 dB at 300-400 Hz (remove boxiness)
- Boost: +2-3 dB at 3-5 kHz (beater click/attack)

#### Snare
- HPF: 80-100 Hz
- Boost: +2-3 dB at 150-250 Hz (body)
- Cut: -2-4 dB at 400-800 Hz (boxiness)
- Boost: +2-3 dB at 2-4 kHz (crack/snap)
- Boost: +1-2 dB shelf at 8 kHz+ (sizzle/wires)

#### Bass (Synth or Electric)
- HPF: 30 Hz
- Boost: +2-3 dB at 60-100 Hz (sub foundation)
- Cut: -2-4 dB at 200-400 Hz (mud)
- Boost: +1-3 dB at 700 Hz-1.5 kHz (growl/presence)

#### Vocals
- HPF: 80-120 Hz
- Cut: -2-3 dB at 200-400 Hz (proximity effect/mud)
- Boost: +2-4 dB at 2-5 kHz (presence, intelligibility)
- De-ess: narrow cut at 5-8 kHz if sibilant
- Boost: +1-2 dB shelf at 10 kHz+ (air)

#### Pads / Strings
- HPF: 150-250 Hz (make room for bass)
- Cut: -2-3 dB at 300-500 Hz
- Shelf boost: +1-2 dB at 8 kHz+ (air and openness)

#### Hi-Hats / Cymbals
- HPF: 300-500 Hz (aggressive filtering)
- Cut: -2-3 dB at 1-3 kHz (reduce harshness)
- Boost: +1-2 dB at 8-12 kHz (shimmer)

#### Piano / Keys
- HPF: 80-120 Hz
- Cut: -2-3 dB at 300-500 Hz
- Boost: +1-2 dB at 2-4 kHz (definition)
- Boost: +1 dB shelf at 8 kHz (brightness)

### EQ Philosophy

- **Cut more than boost** — aim for 2:1 ratio of cuts to boosts
- **Subtractive first:** Cut competing frequencies on other tracks rather than boosting the one you want to hear
- **Narrow cuts, wide boosts:** Use high Q for surgical removal, low Q for tonal shaping
- **Context is everything:** Solo to find problems, but always judge in context of the full mix
- **EQ Eight Oversampling:** Enable "HiQ" mode on master/bus EQ for cleaner high-frequency processing

---

## 8. Bus Processing

### Drum Bus Chain

**Track setup:** Group all drum tracks into a group track (acts as bus)

**Typical chain order:**

1. **EQ Eight** — HPF at 30 Hz, cut 300-500 Hz by -2 dB, gentle presence boost at 4 kHz
2. **Glue Compressor** — The go-to drum bus compressor (modeled on SSL bus comp)
   - Threshold: -15 to -25 dB
   - Ratio: 2:1 to 4:1
   - Attack: 0.3 - 10 ms (longer preserves transients)
   - Release: 0.1 - 0.4 s (or Auto)
   - Makeup: compensate to match bypassed level
   - Range: -3 to -6 dB (limits max GR)
3. **Saturator** (optional) — Analog Clip or Soft Sine mode, Drive 1-3 dB for warmth
4. **Drum Buss** (Live device) — Trim, Crunch (distortion), Boom (low-end resonance), Transients

### Instrument / Synth Bus Chain

1. **EQ Eight** — HPF at 100-200 Hz (keep out of bass territory), tame 2-4 kHz if harsh
2. **Compressor** — Gentle glue
   - Ratio: 2:1 to 3:1
   - Attack: 10-30 ms
   - Release: Auto or 100-200 ms
   - GR target: 1-3 dB
3. **Utility** — Width adjustment (80-120%), level trim

### Vocal Bus Chain (if multiple vocal tracks)

1. **EQ Eight** — HPF 100 Hz, presence boost 2-4 kHz
2. **Compressor** — Ratio 3:1 to 4:1, fast-ish attack (5-15 ms), medium release
3. **De-esser** (or dynamic EQ) — Tame 5-8 kHz
4. **Saturator** — Very subtle (1-2 dB drive) for warmth

### Master Chain (Pre-Mastering)

**Typical order:**

1. **Utility** — Gain trim to hit target level into chain; mono check button
2. **EQ Eight** (HiQ mode) — Corrective: HPF at 25-30 Hz, gentle broad cuts/boosts
3. **Glue Compressor** — Very gentle bus compression
   - Ratio: 2:1
   - Attack: 10-30 ms
   - Release: Auto
   - GR target: 1-2 dB max
   - Soft Clip: On (optional gentle limiting)
4. **Multiband Dynamics** (optional) — Light upward compression per band, 1-2 dB GR max per band
5. **EQ Eight** (optional) — Final tonal polish: air boost shelf at 10 kHz
6. **Limiter** — Final brick wall
   - Gain: +2 to +4 dB (genre dependent)
   - Ceiling: -0.3 dB (headroom for codec conversion)
   - Lookahead: 1-4 ms
   - Release: Auto
   - **Target:** No more than 3-6 dB of gain reduction for transparent results

---

## 9. Volume Relationships

### Relative Level Starting Points

Build the mix from the anchor element outward. These are approximate starting relationships, not absolute values.

| Element | Relative Level | Notes |
|---------|---------------|-------|
| Kick | Reference (0 dB) | Loudest element in most electronic genres |
| Snare/Clap | -1 to -3 dB | Close to kick, sometimes equal |
| Bass | -2 to -4 dB | Sub peaks similar to kick; mid-bass quieter |
| Lead Vocal | -1 to -3 dB | Sits on top in vocal-driven genres |
| Hi-hats | -6 to -10 dB | Support, not dominate |
| Percussion | -8 to -12 dB | Texture and groove |
| Synth Lead | -4 to -8 dB | Prominent but behind vocal |
| Pads / Strings | -10 to -15 dB | Bed/texture, felt not heard prominently |
| FX / Risers | -8 to -14 dB | Momentary, automated |

### Genre-Specific Anchor

| Genre | Anchor Element | Secondary |
|-------|---------------|-----------|
| EDM / House | Kick | Bass |
| Hip-Hop / Trap | 808/Bass | Snare/Clap |
| Pop | Vocals | Kick + Snare |
| Rock | Snare | Vocals |
| Ambient | Pads | Texture |

### Mix Bus Target

- **Peak level at master:** -6 to -3 dBFS before mastering
- **RMS / LUFS:** Genre dependent, but -14 to -10 LUFS integrated is a good pre-master range
- **After mastering/limiting:** -1 to 0 dBTP; -8 to -14 LUFS integrated depending on genre and platform

---

## 10. Ableton Utility Device — Complete Reference

### Parameters

| Parameter | Range | Default | Purpose |
|-----------|-------|---------|---------|
| Gain | -35 to +35 dB | 0 dB | Level adjustment without moving fader |
| Width | 0% to 200% | 100% | Stereo field control |
| Bass Mono | Off / On + Freq | Off | Collapse frequencies below threshold to mono |
| Bass Mono Freq | 50-500 Hz | 120 Hz | Cutoff for bass mono |
| Mute | On/Off | Off | Silence output |
| Phase (Left) | Normal / Invert | Normal | Invert left channel phase |
| Phase (Right) | Normal / Invert | Normal | Invert right channel phase |
| Channel Mode | Stereo / Left / Right / Swap | Stereo | Route specific channels |
| Panorama | -50 to 50 | 0 | Pan within the device |

### Common Use Cases

1. **Gain staging:** Place first in chain, set Gain to bring signal to target level before plugins
2. **Mono bass:** Enable Bass Mono, set frequency to 120-200 Hz
3. **Mono check:** Set Width to 0% on master to check mono compatibility (then set back to 100%)
4. **Phase correction:** Invert L or R phase to fix phase cancellation issues
5. **Width reduction:** Width at 50-80% to narrow a too-wide synth
6. **Width enhancement:** Width at 120-150% to widen pads/ambience (check mono compat)
7. **Side extraction:** Width at 200% to hear only the difference signal
8. **Channel isolation:** Set to Left or Right to solo one channel; use Swap to flip L/R
9. **Silent sidechain trigger:** Place Utility at end of chain with Mute on; track still sends audio to sidechain inputs but is inaudible in mix
10. **A/B level matching:** Place at end of chain; bypass all effects, match perceived loudness using Gain to fairly compare processed vs. dry

---

## Quick-Reference: LivePilot API for Mixing

### Key Tools

| Operation | Tool | Key Params |
|-----------|------|------------|
| Set track volume | `set_track_volume` | `track_index`, `volume: 0.0-1.0` |
| Set track pan | `set_track_pan` | `track_index`, `pan: -1.0 to 1.0` |
| Set send level | `set_track_send` | `track_index`, `send_index`, `value: 0.0-1.0` |
| Create return track | `create_return_track` | — |
| Load device | `find_and_load_device` | `track_index`, `device_name` |
| Set device parameter | `set_device_parameter` | `track_index`, `device_index`, `parameter_name`, `value` |
| Batch set parameters | `batch_set_parameters` | `track_index`, `device_index`, `parameters: [...]` |
| Get return tracks | `get_return_tracks` | — |
| Get master track | `get_master_track` | — |
| Set master volume | `set_master_volume` | `volume: 0.0-1.0` |
| Set track routing | `set_track_routing` | `track_index`, `output_type`, etc. |

### Common Workflows

**Set up a reverb return:**
```
create_return_track
find_and_load_device(return_track_index, "Reverb")
batch_set_parameters(return_track_index, 0, [
    {"name": "Dry/Wet", "value": 1.0},
    {"name": "Decay Time", "value": 2.5},
    {"name": "Pre-Delay", "value": 30}
])
set_track_send(source_track, return_send_index, 0.5)
```

**Set up sidechain compression:**
```
find_and_load_device(bass_track, "Compressor")
# Sidechain routing must be configured via Ableton UI
# or set_track_routing if sidechain input routing is exposed
batch_set_parameters(bass_track, compressor_index, [
    {"name": "Threshold", "value": ...},
    {"name": "Ratio", "value": ...},
    {"name": "Attack", "value": ...},
    {"name": "Release", "value": ...}
])
```

**Quick drum bus glue:**
```
find_and_load_device(drum_group_track, "Glue Compressor")
batch_set_parameters(drum_group_track, device_index, [
    {"name": "Threshold", "value": ...},
    {"name": "Ratio", "value": 4},
    {"name": "Attack", "value": 0.3},
    {"name": "Release", "value": 0.2}
])
```
