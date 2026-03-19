# LivePilot Analyzer — Max for Live Build Guide

Step-by-step instructions to build the `.amxd` device in Max for Live.
The device analyzes the master bus audio and streams data to LivePilot.

## Prerequisites

- Ableton Live 12 Suite (includes Max for Live)
- The `livepilot_bridge.js` file from this directory

## Step 1: Create New Device

1. In Live, go to an empty Audio track
2. Click **Create** → **Max Audio Effect** (or drag "Max Audio Effect" from browser)
3. Click the **pencil icon** on the device title bar to open the Max editor

## Step 2: Audio Pass-Through

The device MUST pass audio through unchanged.

1. You'll see `[plugin~]` and `[plugout~]` already connected
2. Verify: left outlet of `plugin~` → left inlet of `plugout~`
3. Verify: right outlet of `plugin~` → right inlet of `plugout~`

## Step 3: Mono Sum for Analysis

We tap the audio for analysis without affecting the pass-through.

1. Add object: `[+~]` (adds L+R to mono)
2. Connect: `plugin~` left outlet → `[+~]` left inlet
3. Connect: `plugin~` right outlet → `[+~]` right inlet
4. Add object: `[*~ 0.5]` (scale to prevent clipping)
5. Connect: `[+~]` outlet → `[*~ 0.5]` inlet

## Step 4: 8-Band Spectrum Analysis

1. Add object: `[fffb~ 8]` (fast 8-band filter bank)
2. Connect: `[*~ 0.5]` outlet → `[fffb~ 8]` inlet
3. Set `fffb~` frequencies in Inspector or via message:
   - Band 1: 40 Hz (sub)
   - Band 2: 130 Hz (low)
   - Band 3: 350 Hz (low-mid)
   - Band 4: 1000 Hz (mid)
   - Band 5: 3000 Hz (high-mid)
   - Band 6: 6000 Hz (high)
   - Band 7: 10000 Hz (presence)
   - Band 8: 16000 Hz (air)

   To set: add `[loadmess 40 130 350 1000 3000 6000 10000 16000]` → `[fffb~ 8]` right inlet

4. For each of the 8 outlets of `[fffb~ 8]`:
   - Add `[abs~]` (rectify to positive)
   - Add `[snapshot~ 200]` (sample at 5 Hz)

5. Add `[pack f f f f f f f f]` and connect all 8 `[snapshot~]` outlets to it
6. Add `[prepend /spectrum]` → connect from `[pack]`
7. Add `[udpsend 127.0.0.1 9880]` → connect from `[prepend]`

## Step 5: Peak and RMS Metering

1. Add `[peakamp~ 200]` → connect from `[*~ 0.5]`
2. Add `[snapshot~ 200]` → connect from `[peakamp~]`
3. Add `[prepend /peak]` → `[udpsend]` (same udpsend as spectrum)

4. Add `[average~ 200 rms]` → connect from `[*~ 0.5]`
5. Add `[snapshot~ 200]` → connect from `[average~]`
6. Add `[prepend /rms]` → `[udpsend]`

## Step 6: Pitch Tracking

1. Add `[sigmund~ pitch env @npts 2048]`
2. Connect from `[*~ 0.5]` outlet
3. Left outlet (pitch as MIDI note) → `[snapshot~ 200]` → wire to JS (see Step 7)
4. Right outlet (envelope/amplitude) → `[snapshot~ 200]` → wire to JS

## Step 7: JavaScript Bridge

1. Add `[js livepilot_bridge.js]`
   - Copy `livepilot_bridge.js` into the same folder as the `.amxd`
   - Or use Max's File Preferences to add the m4l_device folder

2. Add `[live.thisdevice]`
   - Connect its left outlet (bang on load) → `[js]` inlet

3. Add `[udpreceive 9881]` (incoming commands from MCP server)
   - Connect outlet → `[js]` inlet (messages route via `anything()`)

4. Connect `[js]` outlet 0 → `[udpsend 127.0.0.1 9880]` (responses)

5. Connect pitch tracking to JS for key detection:
   - `[sigmund~]` pitch → `[prepend pitch_in]` → `[js]` inlet
   - Wire amplitude after pitch: pack both into the prepend

   Specifically:
   - `[sigmund~ pitch env]` left outlet → first inlet of `[pack f f]`
   - `[sigmund~ pitch env]` right outlet → second inlet of `[pack f f]`
   - `[pack f f]` → `[prepend pitch_in]` → `[js livepilot_bridge.js]` inlet

## Step 8: UI (Optional but Recommended)

### Status LED
1. Add `[live.text]` — set to "Connected" in Inspector
2. Connect `[js]` outlet 1 → route "status" messages to `[live.text]`

### Spectrum Display (cosmetic)
1. Add `[multislider]` — 8 sliders, vertical, range 0-1
2. Connect the same `[pack f f f f f f f f]` from Step 4 → `[multislider]`
3. Set size to ~100x40px, no border, dark theme colors

### Key Display
1. Add `[live.text]` or `[comment]` — shows detected key
2. Route "key" messages from `[js]` outlet 1

### LivePilot Branding
1. Add `[fpic]` with a small LivePilot logo PNG (white on dark)
2. Or add `[comment]` with text "LivePilot Analyzer"

### Device Size
- In Max Inspector, set presentation mode dimensions: **258 × 80 px** (standard M4L width)
- Switch to Presentation Mode (Cmd+Alt+E) and arrange UI elements

## Step 9: Save and Install

1. Click **Save** (Cmd+S) in Max editor
2. Name it `LivePilot_Analyzer.amxd`
3. Save to: `~/Music/Ableton/User Library/Presets/Audio Effects/Max Audio Effect/`
4. Close the Max editor
5. The device now appears in Live's browser under Audio Effects → Max Audio Effect

## Step 10: Test

1. Drop `LivePilot Analyzer` on the **master track**
2. Play some audio
3. In Claude Code, run: `get_master_spectrum` — should return 8 band values
4. Run: `get_master_rms` — should return RMS and peak
5. After 8+ bars: `get_detected_key` — should return key and scale

## Signal Flow Summary

```
          ┌─────────────────────────────────────────────────┐
          │          LivePilot_Analyzer.amxd                 │
          │                                                  │
plugin~ ──┤──L+R──► plugout~     (pass-through)             │
          │                                                  │
          │──L+R──► +~ ──► *~ 0.5 ──┬──► fffb~ 8 ──► UDP   │
          │                          ├──► peakamp~ ──► UDP   │
          │                          ├──► average~ ──► UDP   │
          │                          └──► sigmund~ ──► JS    │
          │                                                  │
          │         udpreceive 9881 ──► JS ──► udpsend 9880  │
          │         live.thisdevice ──► JS                    │
          └─────────────────────────────────────────────────┘
```

## Troubleshooting

- **"JS file not found"**: Copy `livepilot_bridge.js` to the same folder as the `.amxd`, or add the folder to Max's File Preferences
- **No spectrum data**: Check that audio is playing through the master, and `udpsend` is targeting `127.0.0.1 9880`
- **High CPU**: Remove any `spectroscope~` or `meter~` objects — these are GUI-heavy. Our analysis uses no GUI.
- **Clicks/artifacts**: The `+~` and analysis chain should NOT feed back into `plugout~`. Only the direct plugin~ → plugout~ connection carries audio.
