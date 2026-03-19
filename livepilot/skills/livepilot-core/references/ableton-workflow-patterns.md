# Ableton Live Workflow Patterns & Production Knowledge

Comprehensive reference for Ableton Live workflow techniques, session management, and production patterns. This is timeless knowledge about how Ableton Live works, independent of any specific version.

---

## 1. Session View vs Arrangement View

### Session View
- **Purpose**: Improvisation, jamming, sketching ideas, live performance
- **Layout**: Grid of clip slots — columns are tracks, rows are scenes
- **Clips**: Non-linear — any clip can launch at any time
- **Best for**: Trying out different combinations, building loops, live sets, generating ideas
- **Key behavior**: Clips in the same column (track) are mutually exclusive — only one plays at a time

### Arrangement View
- **Purpose**: Linear composition, detailed editing, final arrangement, automation
- **Layout**: Traditional timeline — left to right
- **Best for**: Fine-tuning transitions, detailed automation, mixing, finalizing a track
- **Key behavior**: Provides precise control over when things start, stop, and change

### Session-to-Arrangement Recording
- **How**: Press the Global Record button while in Session View, then trigger scenes/clips
- **Result**: Live copies all launched clips into the Arrangement at the correct positions and times
- **This is the primary workflow for transitioning from improvisation to a finished arrangement**

### Critical Rule: Mutual Exclusivity
- Session clips and Arrangement clips on the same track are mutually exclusive
- When you launch a Session clip, Arrangement playback on that track stops
- To return to Arrangement playback, click the "Back to Arrangement" button (orange) in the Control Bar

### Typical Creative Workflow
1. **Session View**: Sketch ideas — create loops, try combinations, build sections
2. **Session-to-Arrangement**: Record a performance of your Session clips into Arrangement
3. **Arrangement View**: Edit the recorded performance — fix transitions, add automation, refine structure
4. **Arrangement View**: Mix, polish, export

---

## 2. Scene Organization

### Scenes as Song Sections
Scenes = rows in Session View. Each scene represents a moment or section of the song.

**Naming convention** — Prefix with section name:
```
Scene 0: "Intro"
Scene 1: "Verse 1"
Scene 2: "Chorus 1"
Scene 3: "Verse 2"
Scene 4: "Chorus 2"
Scene 5: "Bridge"
Scene 6: "Chorus 3"
Scene 7: "Outro"
```

### Scene Tempo and Time Signature
- Scenes can have their own tempo and time signature values
- When a scene is launched, the project automatically adjusts to those parameters
- Scenes with tempo/time signature changes show a colored Scene Launch button
- Access by dragging the left edge of the Main track's title header

### Color Coding Strategy
Use consistent colors for section types:
- **Intro/Outro**: Gray or muted color
- **Verse**: Blue or cool color
- **Chorus**: Red or warm color (high energy)
- **Bridge**: Green or distinct contrasting color
- **Drop**: Orange or bright accent
- **Break**: Purple or subdued

### Organization Tips
- Keep empty scenes between sections for clarity
- Name scenes descriptively (e.g., "Verse 1 - Full" vs "Verse 1 - Stripped")
- Use scene follow actions to automate song flow in live performance

---

## 3. Resampling

### What Is Resampling
Routing the output of one or more tracks into another track to capture the processed audio.

### Methods

**Resampling Input Type:**
- Create an Audio track
- Set its Input Type to "Resampling"
- This captures the Main (Master) output
- Safety: Live automatically prevents feedback loops when "Resampling" is selected

**Track-to-Track Routing:**
- Create an Audio track (destination)
- Set its Input Type to the source track name
- Set monitoring to "In"
- Arm the destination track and record
- Captures that specific track's output including all devices

**Freeze and Flatten (now Bounce Track in Place):**
- Right-click track > Bounce Track in Place (Live 12.2+)
- Renders the track's content including all device processing to audio
- Replaces the source track with the rendered audio
- Destructive but frees CPU

### Live 12.2+ Bounce Commands
- **Bounce Track in Place** [Cmd+Shift+B]: Commits entire track as audio, replaces source
- **Bounce to New Track** [Cmd+B]: Renders selection to a new audio track, preserves source
- **Bounce Group in Place** (12.3+): Bounces entire Group track
- **Paste Bounced Audio** [Cmd+Alt+V]: Pastes copied clip as bounced audio

### When to Resample
- Capturing a live performance of effects/automation
- Creating new samples from your own material
- Committing CPU-heavy processing
- Layering processed audio with the original
- Creating variations and happy accidents

---

## 4. Freeze and Flatten / Bounce

### Freeze Track
- **Purpose**: Reduce CPU load without committing permanently
- **How**: Right-click track > Freeze Track
- **What happens**: Live renders a sample file for each clip (Session) and one for Arrangement
- **Result**: Clips play back freeze files instead of computing devices in real-time
- **Reversible**: Unfreeze to make changes again
- **Limitations**: Cannot record into frozen tracks, cannot edit devices or clip settings

### Flatten / Bounce Track in Place (Live 12.2+)
- **Purpose**: Permanently commit to the frozen sound
- **How**: Right-click frozen track > Flatten (or Bounce Track in Place in 12.2+)
- **Result**: Replaces MIDI + devices with rendered audio
- **Irreversible**: Use `undo` if you change your mind immediately

### When to Freeze
- CPU meter getting high
- You have heavy synths or effects you're happy with
- You want to free resources for more tracks
- Before a live performance for stability

### When to Bounce/Flatten
- You're done sound-designing a part
- You need to apply audio-only effects (e.g., manual warp editing)
- You're preparing stems for collaboration
- You want to simplify the project

---

## 5. Clip Launch Modes

### Launch Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| **Trigger** | Click starts clip; it plays until stopped or another clip starts | Default. Standard clip launching |
| **Gate** | Mouse/key down starts; mouse/key up stops | Live performance — hold to play, release to stop |
| **Toggle** | First press starts; second press stops | DJ-style — tap on, tap off |
| **Repeat** | Re-triggers at quantization rate while held | Stutter/roll effects, rhythmic re-triggering |

### Launch Quantization
Controls when a launched clip actually starts playing:

| Setting | Behavior |
|---------|----------|
| **Global** | Uses the Control Bar's global quantization setting |
| **None** | Clip starts immediately (no sync) |
| **1 Bar** | Waits until next bar boundary |
| **1/2 Bar** | Waits until next half-bar |
| **1/4** | Waits until next beat |
| **1/8** | Waits until next eighth note |
| **1/16** | Waits until next sixteenth note |

### Legato Mode
- When enabled, a newly launched clip inherits the play position from the previous clip
- Clips stay in sync even with quantization off
- Useful for switching between variations without losing position

### Velocity-Controlled Launch
- Clip volume can respond to launch velocity
- Useful for dynamic live performance with MIDI controllers

---

## 6. Follow Actions

### What Are Follow Actions
Automated transitions between clips — after a clip plays for a set duration, it triggers another action.

### Follow Action Types

| Action | What It Does |
|--------|-------------|
| **No Action** | Nothing happens — clip keeps playing |
| **Stop** | Clip stops |
| **Play Again** | Restarts the same clip |
| **Previous** | Launches the clip above |
| **Next** | Launches the clip below |
| **First** | Launches the first clip in the group |
| **Last** | Launches the last clip in the group |
| **Any** | Randomly launches any clip in the group |
| **Other** | Randomly launches any other clip in the group |
| **Jump** | Launches a specific clip (by index) |

### Follow Action Configuration
- **Follow Action Time**: Duration before the action triggers (bars.beats.sixteenths)
- **Follow Action A / B**: Two possible actions with probability weighting
- **Chance A / Chance B**: Probability slider controlling which action fires
- **Linked**: When enabled, follow actions apply to all clips in a group simultaneously

### Scene Follow Actions (Live 11+)
- Scenes can also have follow actions
- Double-click a scene to access follow action settings
- Same action types as clip follow actions (excluding clip-specific ones)
- Enables automated scene progression for live performance

### Creative Uses

**Linear Song Playback:**
- Set each section clip to "Next" with 100% chance
- Set follow action time to match clip length
- Song plays through automatically

**Generative/Evolving Music:**
- Multiple variations of a part in consecutive slots
- Follow Action: "Any" or "Other" with equal probability
- Music evolves and never repeats exactly

**Probability-Based Transitions:**
- Action A: "Next" (70% chance) — usually advances
- Action B: "Play Again" (30% chance) — sometimes repeats
- Creates natural-feeling variation in repetition

**Building Tension:**
- Short clips with "Next" follow actions that gradually build
- Last clip in sequence transitions to the full drop/chorus

---

## 7. Tempo and Time Signature

### Tempo Fundamentals
- **Range**: 20-999 BPM
- **Tap Tempo**: Tap the tempo field repeatedly to set tempo by feel
- **Tempo automation**: Can be automated in Arrangement View for gradual changes
- **Scene tempo**: Individual scenes can override the global tempo

### How Tempo Affects Clip Playback
- **Warped audio clips**: Automatically stretch/compress to match project tempo
- **Unwarped audio clips**: Play at their original speed regardless of project tempo
- **MIDI clips**: Always follow project tempo (they are tempo-independent data)

### Warp Modes (for audio clips)

| Mode | Best For | Notes |
|------|----------|-------|
| **Beats** | Drums, percussion, rhythmic material | Cuts and reassembles — artifacts on sustained sounds |
| **Tones** | Monophonic melodic content (vocals, bass, leads) | Grain size is signal-dependent |
| **Texture** | Ambient, pads, complex textures | Grain size is fixed, flux adds randomness |
| **Re-Pitch** | DJ-style speed changes | Changes pitch proportional to tempo change |
| **Complex** | Full mixes, polyphonic material | High CPU — use sparingly |
| **Complex Pro** | Full mixes needing highest quality | Highest CPU — use on bounced stems or final audio |

### Time Signature
- **Format**: Numerator/Denominator (e.g., 4/4, 3/4, 6/8, 7/8)
- **Denominator**: Must be a power of 2 (1, 2, 4, 8, 16)
- **Numerator**: 1-99
- **Time signature changes**: Can be automated in Arrangement via time signature markers
- **Scene time signatures**: Scenes can have their own time signature (applies on launch)

### Bars and Beats Math (at 4/4 time)
```
1 bar    = 4 beats    = 4.0 in beat units
2 bars   = 8 beats    = 8.0
4 bars   = 16 beats   = 16.0
8 bars   = 32 beats   = 32.0
16 bars  = 64 beats   = 64.0
32 bars  = 128 beats  = 128.0

Half note     = 2.0 beats
Quarter note  = 1.0 beats
Eighth note   = 0.5 beats
Sixteenth     = 0.25 beats
Triplet 8th   = 0.333... beats
Dotted quarter = 1.5 beats
```

### At 3/4 time:
```
1 bar = 3 beats = 3.0
4 bars = 12 beats = 12.0
```

### At 6/8 time:
```
1 bar = 6 eighth notes = 3.0 beats (in quarter-note units)
4 bars = 12.0 beats
```

---

## 8. Track Types

### MIDI Tracks
- **Input**: MIDI data (from controllers, other tracks, or clips)
- **Output**: Audio (after instruments process the MIDI)
- **Contains**: MIDI clips, instruments, MIDI effects (before instrument), audio effects (after instrument)
- **Device chain order**: MIDI Effects → Instrument → Audio Effects
- **Use for**: Synthesizers, drum machines, samplers, any virtual instrument

### Audio Tracks
- **Input**: Audio signal (from interface, other tracks, or resampling)
- **Output**: Audio
- **Contains**: Audio clips, audio effects only
- **Use for**: Recorded audio, samples, vocals, guitars, resampling

### Return Tracks (Send/Return)
- **Input**: Receives audio from track sends (proportional to send level)
- **Output**: Audio (routed to Master by default)
- **Contains**: Audio effects only (no clips)
- **Purpose**: Shared effects processing — one reverb/delay serves many tracks
- **Efficiency**: One reverb on a return track vs. separate reverb on every track
- **Convention**: Return A = Reverb, Return B = Delay (common starting point)

### Master Track
- **Input**: Sum of all track outputs (and return tracks)
- **Output**: Audio interface / speakers
- **Contains**: Audio effects only
- **Purpose**: Final processing — limiting, EQ, metering, stereo imaging
- **Caution**: Keep processing minimal — heavy processing here affects everything

### Group Tracks
- **What**: A container for multiple tracks
- **Behavior**: Acts as a submix bus — grouped tracks sum into the group
- **Contains**: Audio effects on the group process the summed output
- **Use for**: Drum bus (compress all drums together), vocal stack, instrument layers
- **Fold/Unfold**: Click triangle to show/hide contained tracks
- **Limitation**: Cannot record clips directly into group tracks
- **Limitation**: Individual grouped tracks lose "track delay" functionality

### Routing Relationships
```
MIDI Track ──────────────────────► Master Track ──► Output
Audio Track ─────────────────────► Master Track
Return Track A ──────────────────► Master Track
Return Track B ──────────────────► Master Track

MIDI Track ──send──► Return Track A (shared reverb)
Audio Track ──send──► Return Track B (shared delay)

Group Track (Drums):
  ├── Kick Track ──┐
  ├── Snare Track ──┼──► Group Bus ──► Master Track
  └── HiHat Track ──┘
```

---

## 9. Grouping

### Creating Groups
- Select multiple tracks → Cmd+G (Mac) / Ctrl+G (Win)
- Tracks are nested inside a Group Track
- Group track appears as a container with fold/unfold control

### Group as Bus
- All grouped tracks route their output through the group
- Add effects on the group track = bus processing
- Common: Compressor on drum group, EQ on vocal group, saturation on bass group

### Groups vs Return Tracks for Processing

| Aspect | Group Track | Return Track |
|--------|-------------|--------------|
| **Routing** | Tracks route output through group | Tracks send proportional amount via sends |
| **Processing** | Affects only grouped tracks | Can affect any track with a send |
| **Mix** | 100% of signal passes through | Send level controls wet amount |
| **Organization** | Visual nesting, fold/unfold | Separate section of mixer |
| **Best for** | Submixing related instruments | Shared time-based effects (reverb, delay) |

### Nesting
- Groups can contain other groups (nested groups)
- Useful for complex projects: "All Drums" group containing "Acoustic Kit" and "Electronic Kit" subgroups

### Organization Patterns
```
Group: Drums
  ├── Kick
  ├── Snare
  ├── HiHats
  └── Percussion

Group: Bass
  ├── Sub Bass
  └── Mid Bass

Group: Synths
  ├── Lead
  ├── Pad
  └── Arp

Group: Vocals
  ├── Lead Vocal
  ├── Backing Vocals
  └── Vocal FX
```

---

## 10. Cue Points (Locators)

### Creating Locators
- **During playback**: Click "Set" button — creates locator at current playback position
- **While stopped**: Click "Set" — creates locator at insert marker position
- **Context menu**: Right-click in the scrub area above tracks
- **Create menu**: Insert Locator command

### Managing Locators
- **Rename**: Select locator's triangle marker → Cmd+R (Mac) / Ctrl+R (Win)
- **Move**: Drag the triangle marker, or use arrow keys
- **Delete**: Select and press Delete/Backspace
- **Navigate**: "Previous Locator" and "Next Locator" buttons, or Ctrl+Option+Left/Right arrow

### Naming Locators as Song Sections
```
[Intro]     at bar 1
[Verse 1]   at bar 9
[Chorus 1]  at bar 25
[Verse 2]   at bar 41
[Chorus 2]  at bar 57
[Bridge]    at bar 73
[Chorus 3]  at bar 81
[Outro]     at bar 97
```

### Loop Between Locators
- Right-click a locator → "Loop to Next Locator"
- Quick way to loop a specific song section for editing

### Time Signature Markers
- Separate from locators — mark time signature changes in the Arrangement
- Create menu → Insert Time Signature Change
- Can be moved with mouse or arrow keys

---

## 11. Recording Techniques

### Session View Recording

**Basic Recording:**
1. Arm the track (click the Arm button)
2. Set record quantization in the Control Bar
3. Click a clip slot's record button — or click the Session Record button
4. Play/perform — recording creates a new clip in that slot

**MIDI Overdub (Session):**
1. Arm the track
2. Enable Session Record (the circular button in the Control Bar)
3. Launch an existing clip — it loops and you add notes on each pass
4. Layer by layer, build up a pattern
5. Disable Session Record to stop overdubbing

### Arrangement View Recording

**Basic Recording:**
1. Arm the desired tracks
2. Click the Arrangement Record button (or press F9)
3. Play — new clips are created on the timeline
4. Click Stop or press Space to finish

**Arrangement Overdub (MIDI):**
1. Enable the "MIDI Arrangement Overdub" button (+ icon in transport)
2. Record into an existing section
3. New notes merge with existing notes instead of replacing

**Session-to-Arrangement Recording:**
1. Switch to Arrangement View (or press Tab)
2. Click the Global Record button
3. Switch back to Session View
4. Trigger scenes and clips — everything is captured in the Arrangement timeline
5. Stop recording
6. Switch to Arrangement to see and edit the result

### Capture MIDI
- **What**: Retroactively captures MIDI notes you played without recording enabled
- **How**: Press Shift+Cmd+C (Mac) / Shift+Ctrl+C (Win) after playing
- **Smart features**: Auto-detects tempo, sets loop boundaries, quantizes to grid
- **Tip**: End your playing on beat 1 of the next bar for best phrase detection
- **Works in**: Both Session and Arrangement View (captures to whichever is focused)

### Record Quantization
- Edit menu → Record Quantization
- Snaps incoming MIDI to the grid during recording
- Options: Off, 1/4, 1/8, 1/8T, 1/16, 1/16T, 1/32
- Different from clip quantization (which is post-recording)

---

## 12. Export Patterns

### Export Audio/Video Dialog
- File menu → Export Audio/Video (Cmd+Shift+R / Ctrl+Shift+R)

### Export Modes

**Master Track Export:**
- Rendered Track: "Master"
- Captures the final stereo mix including all processing
- Use for: Final mixdown, demo bounces, reference mixes

**All Individual Tracks:**
- Rendered Track: "All Individual Tracks"
- Exports each track as a separate audio file
- Includes return tracks and master track
- Grouped tracks: exported at group level (with group effects) AND individually (without group effects)

**Selected Tracks Only:**
- Solo or select specific tracks before exporting
- Rendered Track: "Selected Tracks Only"

### Key Export Settings

| Setting | Recommendation |
|---------|---------------|
| **Sample Rate** | Match project (44100 or 48000 for distribution, higher for stems) |
| **Bit Depth** | 32-bit float for stems (no dithering needed), 16-bit for final distribution |
| **Format** | WAV or AIFF for stems, WAV for masters |
| **Dither** | Only on final 16-bit master — never on stems |
| **Normalize** | Off for stems, optional for master |
| **Render Length** | "Render as Loop" or set specific start/end |

### Include Return and Master Effects
- **Enabled**: Each individual track export includes return track processing and master effects
- **Disabled**: Dry individual tracks without shared effects
- **For mix engineer**: Usually disabled (they want dry stems)
- **For stems/remixes**: Usually enabled (they want the processed sound)

### Stem Export Strategy
```
Strategy 1: Full stems (for remixers)
  → Export "All Individual Tracks" with return/master effects ON
  → Gives processed, ready-to-use stems

Strategy 2: Dry stems (for mix engineer)
  → Export "All Individual Tracks" with return/master effects OFF
  → Gives unprocessed tracks for full mixing control

Strategy 3: Submix stems (for collaboration)
  → Group related tracks (Drums, Bass, Synths, Vocals)
  → Export groups as stems
  → Gives organized, partially mixed stems
```

---

## 13. Song Structure Templates

### Pop / Singer-Songwriter
```
Section      | Bars | Beats | Scenes
-------------|------|-------|-------
Intro        |  8   |  32.0 | 0
Verse 1      | 16   |  64.0 | 1
Pre-Chorus 1 |  4   |  16.0 | 2
Chorus 1     | 16   |  64.0 | 3
Verse 2      | 16   |  64.0 | 4
Pre-Chorus 2 |  4   |  16.0 | 5
Chorus 2     | 16   |  64.0 | 6
Bridge       |  8   |  32.0 | 7
Chorus 3     | 16   |  64.0 | 8
Outro        |  8   |  32.0 | 9
TOTAL        | 112  | 448.0 |
```
**Typical tempo**: 100-130 BPM
**Duration at 120 BPM**: ~3:44

### Electronic / EDM / House
```
Section      | Bars | Beats | Scenes
-------------|------|-------|-------
Intro        | 16   |  64.0 | 0
Build 1      |  8   |  32.0 | 1
Drop 1       | 32   | 128.0 | 2
Break 1      | 16   |  64.0 | 3
Build 2      |  8   |  32.0 | 4
Drop 2       | 32   | 128.0 | 5
Outro        | 16   |  64.0 | 6
TOTAL        | 128  | 512.0 |
```
**Typical tempo**: 120-130 BPM (House), 126-150 BPM (EDM/Trance)
**Duration at 128 BPM**: ~4:00

### Hip-Hop / Trap
```
Section      | Bars | Beats | Scenes
-------------|------|-------|-------
Intro        |  4   |  16.0 | 0
Verse 1      | 16   |  64.0 | 1
Hook 1       |  8   |  32.0 | 2
Verse 2      | 16   |  64.0 | 3
Hook 2       |  8   |  32.0 | 4
Bridge       |  8   |  32.0 | 5
Hook 3       |  8   |  32.0 | 6
Outro        |  4   |  16.0 | 7
TOTAL        | 72   | 288.0 |
```
**Typical tempo**: 70-90 BPM (Hip-Hop), 130-170 BPM half-time (Trap)
**Duration at 80 BPM**: ~3:36

### Techno / Minimal
```
Section      | Bars | Beats | Scenes
-------------|------|-------|-------
Intro        | 16   |  64.0 | 0
Build 1      | 16   |  64.0 | 1
Peak 1       | 32   | 128.0 | 2
Breakdown    | 16   |  64.0 | 3
Build 2      | 16   |  64.0 | 4
Peak 2       | 32   | 128.0 | 5
Breakdown 2  |  8   |  32.0 | 6
Peak 3       | 16   |  64.0 | 7
Outro        | 16   |  64.0 | 8
TOTAL        | 168  | 672.0 |
```
**Typical tempo**: 125-140 BPM
**Duration at 130 BPM**: ~5:10

### Drum & Bass / Jungle
```
Section      | Bars | Beats | Scenes
-------------|------|-------|-------
Intro        | 16   |  64.0 | 0
Drop 1       | 32   | 128.0 | 1
Breakdown    | 16   |  64.0 | 2
Drop 2       | 32   | 128.0 | 3
Mid Section  |  8   |  32.0 | 4
Drop 3       | 16   |  64.0 | 5
Outro        | 16   |  64.0 | 6
TOTAL        | 136  | 544.0 |
```
**Typical tempo**: 170-180 BPM
**Duration at 174 BPM**: ~3:08

### Lo-Fi / Chill
```
Section      | Bars | Beats | Scenes
-------------|------|-------|-------
Intro        |  4   |  16.0 | 0
Section A    | 16   |  64.0 | 1
Section B    | 16   |  64.0 | 2
Section A'   | 16   |  64.0 | 3
Section C    |  8   |  32.0 | 4
Section A''  | 16   |  64.0 | 5
Outro        |  4   |  16.0 | 6
TOTAL        | 80   | 320.0 |
```
**Typical tempo**: 70-90 BPM
**Duration at 80 BPM**: ~4:00

### Ambient / Soundtrack
```
Section      | Bars | Beats | Scenes
-------------|------|-------|-------
Atmosphere   | 16   |  64.0 | 0
Development  | 32   | 128.0 | 1
Climax       | 16   |  64.0 | 2
Resolution   | 16   |  64.0 | 3
Fade         |  8   |  32.0 | 4
TOTAL        | 88   | 352.0 |
```
**Typical tempo**: 60-100 BPM (often flexible/no strict grid)
**Duration at 80 BPM**: ~4:24

---

## 14. Bars and Beats Math

### Core Conversion (4/4 Time)
```
Bars to Beats:  bars × 4 = beats
Beats to Bars:  beats ÷ 4 = bars

Examples:
  1 bar   =  4.0 beats
  2 bars  =  8.0 beats
  4 bars  = 16.0 beats
  8 bars  = 32.0 beats
 16 bars  = 64.0 beats
 32 bars  = 128.0 beats
```

### Note Duration to Beat Values
```
Whole note          = 4.0 beats
Dotted half note    = 3.0 beats
Half note           = 2.0 beats
Dotted quarter note = 1.5 beats
Quarter note        = 1.0 beats
Dotted eighth note  = 0.75 beats
Eighth note         = 0.5 beats
Eighth triplet      = 0.333... beats (1/3)
Sixteenth note      = 0.25 beats
Sixteenth triplet   = 0.1666... beats (1/6)
Thirty-second note  = 0.125 beats
```

### Quantization Grid Values
```
1/4 note grid  = 1.0
1/8 note grid  = 0.5
1/8T grid      = 0.333...
1/16 note grid = 0.25
1/16T grid     = 0.1666...
1/32 note grid = 0.125
```

### Duration Formula
```
Duration in seconds = (beats × 60) / BPM

Examples at 120 BPM:
  1 beat  = 0.5 seconds
  4 beats = 2.0 seconds (1 bar)
  16 beats = 8.0 seconds (4 bars)
  64 beats = 32.0 seconds (16 bars)

Song duration at different tempos (128 bars = 512 beats at 4/4):
  80 BPM  → 6:24
  100 BPM → 5:07
  120 BPM → 4:16
  128 BPM → 4:00
  140 BPM → 3:39
  174 BPM → 2:56
```

### Non-4/4 Time Signatures
```
3/4 time: 1 bar = 3.0 beats
  4 bars = 12.0 beats
  8 bars = 24.0 beats

6/8 time: 1 bar = 3.0 beats (counted in dotted quarters)
  4 bars = 12.0 beats
  8 bars = 24.0 beats

5/4 time: 1 bar = 5.0 beats
  4 bars = 20.0 beats

7/8 time: 1 bar = 3.5 beats
  4 bars = 14.0 beats
```

### MIDI Pitch Reference
```
C-2 =  0    (lowest)
C-1 = 12
C0  = 24
C1  = 36    (kick drum in GM)
C2  = 48
C3  = 60    (middle C)
C4  = 72
C5  = 84
C6  = 96
C7  = 108
G8  = 127   (highest)

Common drum mapping (General MIDI):
  C1  (36) = Kick
  D1  (38) = Snare
  F#1 (42) = Closed Hi-Hat
  A#1 (46) = Open Hi-Hat
  C#2 (49) = Crash
  D#2 (51) = Ride
```

### Volume Reference
```
Live's volume is 0.0 to 1.0 (normalized):
  0.0   = -inf dB (silence)
  0.50  ≈ -12 dB
  0.70  ≈ -6 dB
  0.85  ≈  0 dB (unity gain)
  1.0   ≈ +6 dB (max)
```

---

## 15. Common Workflow Recipes

### Recipe: Build a Song from Scratch in Session View
1. Set tempo with `set_tempo`
2. Create tracks: drums, bass, chords, melody, vocals (as needed)
3. Name and color tracks for organization
4. Load instruments on each track
5. Create 1-bar or 2-bar clips on Scene 0 as a starting palette
6. Program notes into clips
7. Duplicate scenes, create variations for different sections
8. Name scenes after song sections (Intro, Verse, Chorus, etc.)
9. Trigger scenes to test the flow
10. Record Session-to-Arrangement for the final timeline

### Recipe: Resample a Performance
1. Create a new Audio track
2. Set input to "Resampling" (captures master output)
3. Arm the track
4. Start recording
5. Perform — trigger clips, tweak effects, automate parameters
6. Stop recording — the performance is captured as audio

### Recipe: Create a Build-Up
1. Start with a stripped-down version (e.g., just kick and hi-hats)
2. Use 8 bars of gradually adding elements
3. Automate filter cutoff (low to high) on synth tracks
4. Add a riser/sweep sample
5. Optional: automate tempo slightly upward (+2-3 BPM)
6. Cut everything on beat 1 of the drop (or let it explode)

### Recipe: Set Up Return Tracks for Mixing
1. `create_return_track` — Return A for Reverb
2. `create_return_track` — Return B for Delay
3. Load reverb on Return A, delay on Return B
4. Use `set_track_send` to control how much each track sends to returns
5. Return track volumes control overall wet level

### Recipe: Prepare Stems for Mastering
1. Organize tracks into groups (Drums, Bass, Synths, Vocals, FX)
2. Ensure each group sounds correct in solo
3. Export each group as a stem (All Individual Tracks)
4. Export master as reference
5. Include session info: BPM, key, any notes for the engineer
