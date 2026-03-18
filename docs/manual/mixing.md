# Mixing

This chapter covers practical mixing techniques using LivePilot's tools. All values shown are what you pass to LivePilot commands directly.

---

## 1. Volume and Gain Staging

LivePilot uses a **0.0 to 1.0 linear scale** for volume, not decibels. Here are the reference points you need to know:

| LivePilot Value | Approximate dB |
|-----------------|----------------|
| 0.00            | -inf (silence) |
| 0.50            | -12 dB         |
| 0.70            | -6 dB          |
| 0.85            | 0 dB (unity)   |
| 1.00            | +6 dB          |

**Do not set everything to 1.0.** That is +6dB per track. With 20 tracks all at 1.0, your master will clip hard.

### Gain Staging Strategy

Start with your kick or bass as the reference point, then mix everything relative to it.

```
set_track_volume  track_index=0  volume=0.75   # kick — reference
set_track_volume  track_index=1  volume=0.70   # snare — 1-3dB below kick
set_track_volume  track_index=2  volume=0.68   # bass — 2-4dB below kick
set_track_volume  track_index=3  volume=0.50   # hi-hats — 6-10dB below kick
set_track_volume  track_index=4  volume=0.40   # pads — 10-15dB below kick
```

**Target:** Master peak around -6dB before mastering. That means `set_master_volume` around **0.70-0.80** depending on your track count and density.

### Relative Volume Guidelines

| Element         | Relative to Kick |
|-----------------|-------------------|
| Kick            | Reference         |
| Snare           | -1 to -3 dB      |
| Bass            | -2 to -4 dB      |
| Hi-hats         | -6 to -10 dB     |
| Percussion      | -6 to -12 dB     |
| Pads/atmosphere | -10 to -15 dB    |
| Lead melody     | -2 to -6 dB      |
| Vocals          | -1 to -4 dB      |

---

## 2. Panning

Pan range in LivePilot: **-1.0** (full left) to **1.0** (full right). **0.0** is dead center.

```
set_track_pan  track_index=3  pan=-0.30   # hi-hats slightly left
set_track_pan  track_index=5  pan=0.40    # percussion right
```

### What Stays Centered (0.0)

- Kick
- Snare
- Bass
- Lead vocal or lead melody
- Sub-bass elements

### What Gets Panned

| Element            | Suggested Pan Range    |
|--------------------|------------------------|
| Hi-hats            | -0.15 to -0.30         |
| Open hats/rides    | 0.15 to 0.30           |
| Percussion loops   | -0.40 to 0.40          |
| Stereo pads        | Hard pan L/R copies    |
| Doubled guitars    | -0.70 / 0.70           |
| Background vocals  | -0.50 / 0.50           |
| Effects/risers     | Automate across field   |

### Stereo Width

Use the **Utility** device to control stereo width:

```
find_and_load_device  track_index=4  device_name="Utility"
set_device_parameter  track_index=4  device_index=0  parameter_name="Width"  value=120.0
```

- **0%** = mono (use this to check mono compatibility)
- **100%** = normal stereo
- **>100%** = wider (use sparingly, causes phase issues)

---

## 3. Return Tracks and Sends

### Why Use Returns

Shared effects on return tracks accomplish two things:

1. **Save CPU** — one reverb instance instead of eight
2. **Create cohesion** — multiple elements passing through the same reverb sound like they exist in the same space

### Setting Up Returns

Return track effects should always be set to **100% wet** since the dry signal comes from the source track.

```
create_return_track
# Use negative indices for return tracks: -1 = Return A, -2 = Return B, etc.
find_and_load_device  track_index=-1  device_name="Reverb"
set_device_parameter  track_index=-1  device_index=0  parameter_name="Dry/Wet"  value=100.0
```

Then control how much of each track reaches that return:

```
set_track_send  track_index=0  send_index=0  value=0.40   # kick: light reverb
set_track_send  track_index=1  send_index=0  value=0.55   # snare: more reverb
set_track_send  track_index=4  send_index=0  value=0.70   # pads: heavy reverb
```

### Standard 4-Return Template

This is a reliable starting point for most productions:

| Return | Purpose               | Effect          | Key Settings                        |
|--------|-----------------------|-----------------|-------------------------------------|
| A      | Short reverb (room)   | Reverb          | Decay 0.5-1.2s, PreDelay 10-20ms   |
| B      | Long reverb (hall)    | Reverb          | Decay 2.5-5.0s, PreDelay 30-60ms   |
| C      | Delay                 | Delay           | Sync on, 1/8 or 3/16, feedback 30-45% |
| D      | Parallel compression  | Compressor      | Ratio 10:1, fast attack, medium release |

### High-Pass Your Returns

Low frequencies in reverbs and delays create mud. Always add an EQ Eight on each return track and high-pass at **80-150Hz**:

```
find_and_load_device  track_index=-1  device_name="EQ Eight"
# Enable band 1 as high-pass, set frequency to 100Hz
set_device_parameter  track_index=-1  device_index=0  parameter_name="1 Frequency A"  value=100.0
set_device_parameter  track_index=-1  device_index=0  parameter_name="1 Filter Type A"  value=2.0
```

---

## 4. EQ Basics

### EQ Eight

Ableton's EQ Eight is an 8-band parametric EQ. Load it on any track:

```
find_and_load_device  track_index=2  device_name="EQ Eight"
```

### The First Rule: High-Pass Everything (Except Kick and Bass)

Every track that is not kick or bass should have a high-pass filter removing unnecessary low end:

| Element      | HPF Frequency |
|--------------|---------------|
| Vocals       | 80-120 Hz     |
| Guitars      | 100-150 Hz    |
| Synth leads  | 120-200 Hz    |
| Hi-hats      | 200-400 Hz    |
| Pads         | 100-180 Hz    |
| Percussion   | 150-300 Hz    |

### Cut Narrow, Boost Wide

When removing problem frequencies, use a **narrow Q** (high Q value, 3.0-8.0) to surgically remove the issue. When boosting pleasing frequencies, use a **wide Q** (low Q value, 0.5-1.5) so it sounds natural.

### Frequency Guide

| Range       | Frequency    | Character                        |
|-------------|-------------|----------------------------------|
| Sub         | 20-60 Hz    | Felt more than heard, rumble     |
| Bass body   | 60-250 Hz   | Warmth, fullness, weight         |
| Mud zone    | 200-500 Hz  | Boxy, muddy — cut here often     |
| Low mids    | 500 Hz-1 kHz| Body of vocals and instruments   |
| Presence    | 1-4 kHz     | Clarity, definition, bite        |
| Brilliance  | 4-10 kHz    | Edge, sibilance, detail          |
| Air         | 10-20 kHz   | Sparkle, openness, shimmer       |

### The Process

1. **Cut first** — identify and remove problem frequencies (mud at 200-500Hz, harshness at 2-4kHz)
2. **Boost second** — enhance what makes the instrument sound good
3. **Bypass and compare** — toggle the device to confirm you improved it

---

## 5. Compression

### Core Parameters

| Parameter    | What It Does                                    |
|-------------|--------------------------------------------------|
| Threshold   | Level above which compression starts             |
| Ratio       | How much gain reduction is applied (2:1 = gentle, Inf:1 = limiter) |
| Attack      | How fast the compressor reacts (ms)              |
| Release     | How fast it stops compressing after signal drops (ms) |
| Makeup Gain | Compensate for volume lost during compression    |

```
find_and_load_device  track_index=0  device_name="Compressor"
set_device_parameter  track_index=0  device_index=0  parameter_name="Threshold"  value=-18.0
set_device_parameter  track_index=0  device_index=0  parameter_name="Ratio"  value=4.0
```

### Bus Compression (Glue)

Apply gentle compression to groups or the master for cohesion:

- **Ratio:** 2:1 to 4:1
- **Attack:** 10-30ms (let transients through)
- **Release:** 100-200ms
- **Gain reduction:** 1-3dB maximum

### Parallel Compression

Heavy compression on a return track, blended with the dry signal. This adds density without killing dynamics.

On return D:
- **Ratio:** 8:1 to 20:1
- **Attack:** 0.1-1ms (fast)
- **Release:** 50-150ms
- **Threshold:** low enough to get 10-15dB of gain reduction

Send drums to this return at moderate levels (0.40-0.60) to add weight.

### Sidechain Compression

Duck one element when another hits. The classic: duck bass/pads when the kick plays.

```
find_and_load_device  track_index=2  device_name="Compressor"
# Set sidechain input to kick track via the device UI or set_device_parameter
```

#### Sidechain Settings by Genre

| Style                  | Ratio  | Attack   | Release    | Effect              |
|------------------------|--------|----------|------------|---------------------|
| House/Techno (pump)    | Inf:1  | 0.01ms   | 100-300ms  | Obvious rhythmic ducking |
| Deep house (smooth)    | 6:1    | 0.5-2ms  | 200-400ms  | Gentle breathing     |
| Subtle ducking         | 4:1    | 1-5ms    | 200-400ms  | Transparent clarity  |
| EDM (extreme)          | Inf:1  | 0.01ms   | 50-150ms   | Hard pump            |

---

## 6. Routing

### Viewing Current Routing

```
get_track_routing  track_index=0
```

Returns input/output routing, monitoring state, and available routing options.

### Changing Routing

```
set_track_routing  track_index=0  output_routing="Sends Only"
set_track_routing  track_index=3  input_routing="Ext. In"  input_channel="1/2"
```

### Common Routing Scenarios

**Bus/group routing:** Route multiple drum tracks to a single group track for shared processing (EQ, compression, saturation).

**Resampling:** Set a track's input to "Resampling" to record the master output into a new clip.

**External gear:** Route a track's output to a hardware interface channel, then capture the return on another track.

**MIDI to external synth:** Set a MIDI track's output routing to your external device, set monitoring to "In" on an audio track receiving the synth's audio.

---

## 7. The Mix Workflow with LivePilot

A practical step-by-step approach:

### Step 1: Survey

```
get_session_info
```

See every track, clip, device, tempo, and time signature in one call.

### Step 2: Diagnose

```
get_session_diagnostics
```

Catches common problems: tracks left armed, forgotten solos, muted tracks you forgot about, missing devices.

### Step 3: Rough Levels

Set volume for every track relative to your kick/bass reference. Do not worry about perfection yet.

```
set_track_volume  track_index=0  volume=0.75
set_track_volume  track_index=1  volume=0.70
set_track_volume  track_index=2  volume=0.68
# ... continue for all tracks
```

### Step 4: Pan

Place elements in the stereo field. Start with the rules from Section 2.

```
set_track_pan  track_index=3  pan=-0.25
set_track_pan  track_index=5  pan=0.35
```

### Step 5: Return Tracks

Create your returns and load effects (100% wet):

```
create_return_track
create_return_track
create_return_track
create_return_track
```

Load and configure effects on each return per the template in Section 3.

### Step 6: Sends

Route each track to the appropriate returns:

```
set_track_send  track_index=1  send_index=0  value=0.45   # snare to short reverb
set_track_send  track_index=4  send_index=1  value=0.60   # pads to long reverb
set_track_send  track_index=3  send_index=2  value=0.35   # hats to delay
set_track_send  track_index=0  send_index=3  value=0.50   # kick to parallel comp
```

### Step 7: EQ and Compression

Add EQ Eight and Compressor to individual tracks that need it:

```
find_and_load_device  track_index=2  device_name="EQ Eight"
find_and_load_device  track_index=2  device_name="Compressor"
```

Configure parameters per the guidelines in Sections 4 and 5.

### Step 8: Master Headroom

```
set_master_volume  volume=0.75
```

Keep the master peaking around -6dB to leave headroom for mastering.

### Step 9: Iterate

Listen. Adjust. Repeat. Use `get_device_parameters` to check current values, `set_device_parameter` to tweak. There is no shortcut for this step.

---

## 8. Monitoring Tips

### Check Master State

```
get_master_track
```

Shows the master track's current volume and all loaded devices.

### Catch Mistakes

Run `get_session_diagnostics` regularly throughout your session. It will flag:

- Tracks still soloed from earlier debugging
- Tracks muted that you forgot about
- Armed tracks bleeding monitoring signal
- Tracks with no output routing

### Mono Compatibility Check

Many playback systems (clubs, phones, bluetooth speakers) sum to mono. Check your mix in mono by adding a Utility device to the master and setting Width to 0%:

```
find_and_load_device  track_index=-1000  device_name="Utility"
set_device_parameter  track_index=-1000  device_index=0  parameter_name="Width"  value=0.0
```

Use `track_index=-1000` to target the master track. For return tracks, use negative indices: `-1` for Return A, `-2` for Return B, etc.

If elements disappear or get dramatically quieter in mono, you have phase issues to fix. Set Width back to 100% when done checking.

---

Next: [Troubleshooting](troubleshooting.md) | Back to [Manual](index.md)
