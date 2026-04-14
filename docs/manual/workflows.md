# Workflows

This chapter walks through real production workflows, start to finish. Each one uses actual LivePilot tool calls so you can see exactly what's happening under the hood. You don't need to type tool calls yourself — just describe what you want in plain language and the AI translates — but knowing the tools helps you understand what's possible and troubleshoot when something feels off.

## 1. Building a Beat from Scratch

Let's build a complete drum pattern from nothing. This is the workflow you'll use most often, so we'll go step by step.

### Check what you're working with

Always start here. Every single time.

```
get_session_info
```

This tells you the current tempo, how many tracks exist, what scenes are set up, and whether anything is playing. It's the AI's way of "looking at the screen" before touching anything. If you skip this, the AI is working blind — it might create a track at the wrong index or set a tempo that's already set.

### Set the tempo

```
set_tempo(tempo=126)
```

Pick your tempo before building anything. Changing tempo later won't break your MIDI (it's all beat-relative), but it's good practice to start where you mean to finish.

### Create and set up the track

```
create_midi_track(index=-1, name="DRUMS", color=13)
```

This appends a new MIDI track at the end, names it "DRUMS", and gives it a color. The `index=-1` means "put it at the end" — you don't have to count your existing tracks.

Color indices run 0-69 across Ableton's palette. You'll develop your own convention over time. A common one: warm colors for drums, cool colors for melodic elements, greys for utility.

### Load a drum kit

This is where a lot of people trip up. You want a **preset kit**, not a bare Drum Rack. A bare Drum Rack is empty — no samples, no sounds. It's like loading a Simpler with no sample in it.

```
search_browser(path="drums", name_filter="Kit")
```

This searches Ableton's browser under the drums category for anything with "Kit" in the name. You'll get back results like "606 Core Kit", "808 Core Kit", "Acoustic Kit", "Kit-Boutique Bubbly" — real kits with samples already mapped.

Pick one and load it:

```
load_browser_item(track_index=0, uri="<uri from search results>")
```

The `track_index` is whichever index your DRUMS track ended up at. If it's the only track, that's 0.

### Verify the kit loaded correctly

This step is not optional. Drum Rack loading can silently fail — the device appears but with no chains (no pads mapped). Always check:

```
get_track_info(track_index=0)
```

This shows you the devices on the track. You should see a Drum Rack. Then:

```
get_rack_chains(track_index=0, device_index=0)
```

If this returns chains (Kick, Snare, HiHat, etc.), you're good. If it returns an empty list, the kit didn't load properly — undo and try a different kit.

### Create a clip

```
create_clip(track_index=0, clip_index=0, length=8.0)
```

This creates an empty 8-beat (2-bar) MIDI clip in the first clip slot. The length is in beats — so 4.0 = 1 bar, 8.0 = 2 bars, 16.0 = 4 bars.

For drum patterns, 8 or 16 beats is typical. Start with 8 — you can always extend later.

### Program the pattern

Now the fun part. Here are the standard General MIDI drum pitches that Ableton's kits use:

| Pitch | Sound |
|-------|-------|
| 36 | Kick |
| 38 | Snare |
| 42 | Closed Hi-Hat |
| 46 | Open Hi-Hat |
| 49 | Crash Cymbal |

A basic house pattern — four-on-the-floor kick, snares on 2 and 4, eighth-note hi-hats:

```
add_notes(track_index=0, clip_index=0, notes=[
  // Kicks - every beat
  {"pitch": 36, "start_time": 0.0, "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 1.0, "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 2.0, "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 3.0, "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 4.0, "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 5.0, "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 6.0, "duration": 0.5, "velocity": 110},
  {"pitch": 36, "start_time": 7.0, "duration": 0.5, "velocity": 110},

  // Snares - beats 2 and 6 (the "2" and "4" of each bar)
  {"pitch": 38, "start_time": 1.0, "duration": 0.5, "velocity": 100},
  {"pitch": 38, "start_time": 5.0, "duration": 0.5, "velocity": 100},

  // Hi-hats - every eighth note
  {"pitch": 42, "start_time": 0.0,  "duration": 0.25, "velocity": 80},
  {"pitch": 42, "start_time": 0.5,  "duration": 0.25, "velocity": 60},
  {"pitch": 42, "start_time": 1.0,  "duration": 0.25, "velocity": 80},
  {"pitch": 42, "start_time": 1.5,  "duration": 0.25, "velocity": 60},
  {"pitch": 42, "start_time": 2.0,  "duration": 0.25, "velocity": 80},
  {"pitch": 42, "start_time": 2.5,  "duration": 0.25, "velocity": 60},
  {"pitch": 42, "start_time": 3.0,  "duration": 0.25, "velocity": 80},
  {"pitch": 42, "start_time": 3.5,  "duration": 0.25, "velocity": 60}
  // ... and so on for beats 4-7
])
```

Notice the velocity variation on the hi-hats — downbeats at 80, upbeats at 60. This simple alternation already gives the pattern a sense of groove. Without it, the hi-hats sound robotic.

### Fire it and listen

```
fire_clip(track_index=0, clip_index=0)
```

Now it's playing. Listen. This is the most important step — your ears are the final authority.

### Iterate

Maybe the hi-hats are too loud. Read the notes back first:

```
get_notes(track_index=0, clip_index=0, from_pitch=42, pitch_span=1)
```

This returns all hi-hat notes with their `note_id` values. Use those IDs to modify specific notes:

```
modify_notes(track_index=0, clip_index=0, modifications=[
  {"note_id": 12, "velocity": 65},
  {"note_id": 13, "velocity": 45},
  // ... etc
])
```

Want to add ghost notes on the snare? Those are quiet snare hits on the "e" and "ah" of each beat (the sixteenth-note subdivisions):

```
add_notes(track_index=0, clip_index=0, notes=[
  {"pitch": 38, "start_time": 0.75, "duration": 0.25, "velocity": 35},
  {"pitch": 38, "start_time": 2.25, "duration": 0.25, "velocity": 30},
  {"pitch": 38, "start_time": 4.75, "duration": 0.25, "velocity": 35},
  {"pitch": 38, "start_time": 6.25, "duration": 0.25, "velocity": 30}
])
```

Ghost notes should be quiet — velocity 25-40 — or they stop being ghosts and start competing with your main snare hits.

Want to humanize the timing? You could ask the AI to add small random offsets to start times (shifting notes a few ticks early or late). Or use the quantize tool with a partial amount to pull notes slightly toward the grid without snapping them hard:

```
quantize_clip(track_index=0, clip_index=0, grid=5, amount=0.5)
```

That's grid=5 for sixteenth notes, amount=0.5 for 50% quantize strength — notes move halfway to the grid, keeping some human feel.


## 2. Session Setup

A well-organized session template saves you time on every project. Here's how to build one from scratch.

### Create your tracks

Build a basic multi-track setup:

```
create_midi_track(index=-1, name="DRUMS", color=13)
create_midi_track(index=-1, name="BASS", color=15)
create_midi_track(index=-1, name="KEYS", color=22)
create_midi_track(index=-1, name="PAD", color=24)
create_midi_track(index=-1, name="LEAD", color=26)
create_audio_track(index=-1, name="VOX", color=56)
```

Each call creates one track. The AI can batch these, but they execute one at a time to ensure consistent indexing.

### Load instruments

The fastest way to find the right instrument is through the Device Atlas:

```
atlas_suggest(intent="warm analog bass", genre="house")
→ device: Analog, recipe: specific parameter values

atlas_chain_suggest(role="bass", genre="house")
→ Analog + EQ Eight + Compressor + Saturator (complete chain)
```

Then load:

```
find_and_load_device(track_index=1, device_name="Analog")

search_browser(path="instruments", name_filter="Electric Piano")
load_browser_item(track_index=2, uri="<uri for keys preset>")
```

After loading each one, verify with `get_track_info` to make sure the device landed on the right track.

### Set up return tracks for shared effects

Return tracks let multiple instruments share the same reverb or delay. This saves CPU and glues your mix together — everything going through the same reverb sounds like it's in the same room.

```
create_return_track()
create_return_track()
```

These appear as Return A and Return B. Name them:

```
// Return tracks are accessed by get_return_tracks — their index is separate
// You'll need to find them first
get_return_tracks()
```

The return tracks won't have names by default. You can load effects onto them using `find_and_load_device`:

```
find_and_load_device(track_index=<return_A_index>, device_name="Reverb")
find_and_load_device(track_index=<return_B_index>, device_name="Delay")
```

Then send any track to these returns:

```
set_track_send(track_index=2, send_index=0, value=0.35)  // Keys -> Reverb
set_track_send(track_index=3, send_index=0, value=0.50)  // Pad -> Reverb
set_track_send(track_index=4, send_index=1, value=0.25)  // Lead -> Delay
```

Send values are 0.0 (no send) to 1.0 (full send). Start conservative — 0.2-0.4 for reverb, 0.15-0.3 for delay. You can always turn them up.

### Name your scenes for song sections

Scenes in Session View can represent song sections. Name them to keep your structure clear:

```
set_scene_name(scene_index=0, name="Intro")
set_scene_name(scene_index=1, name="Verse 1")
set_scene_name(scene_index=2, name="Chorus")
set_scene_name(scene_index=3, name="Verse 2")
set_scene_name(scene_index=4, name="Chorus 2")
set_scene_name(scene_index=5, name="Bridge")
set_scene_name(scene_index=6, name="Outro")
```

You may need to create scenes first if you don't have enough:

```
create_scene()  // creates at the end
```

### Color coding convention

Develop a consistent system. Here's one that works well:

- **Red/Orange (0-13):** Drums and percussion
- **Yellow/Green (14-26):** Melodic elements (bass, keys, synths)
- **Blue/Purple (27-45):** Pads, atmospheres, textures
- **Pink/Magenta (46-55):** Vocals, samples
- **Grey/White (56-69):** Utility (effects returns, buses)

The exact numbers don't matter. What matters is that you can glance at your session and immediately know what's what.


## 3. Sound Design Workflow

LivePilot gives you access to Ableton's entire browser and every tweakable parameter on every device. Here's how to use that for sound design.

### Browsing Ableton's library

The browser is organized in a tree. You can explore it at different levels:

```
// See the top-level categories
get_browser_tree()

// Drill into instruments
get_browser_items(path="instruments")

// Search for something specific
search_browser(path="instruments", name_filter="Wavetable")
```

The `search_browser` tool is your workhorse. It recurses into subfolders (up to `max_depth` levels deep) and filters by name. Some useful searches:

```
// Find all bass presets
search_browser(path="instruments", name_filter="Bass")

// Find specific effect presets
search_browser(path="audio_effects", name_filter="Compressor")

// Find drum kits
search_browser(path="drums", name_filter="Kit")
```

### Loading instruments and effects

Once you find something you like, load it by URI:

```
load_browser_item(track_index=1, uri="<uri from search>")
```

Or use the shortcut if you know the device name:

```
find_and_load_device(track_index=1, device_name="Wavetable")
```

`find_and_load_device` searches the browser and loads the first match. It's quick for loading stock Ableton devices but less precise than searching first and picking a specific preset.

### Tweaking parameters

Every device parameter is accessible. First, see what's available:

```
get_device_parameters(track_index=1, device_index=0)
```

This returns every parameter with its current value, min, max, and name. For a synth like Wavetable, you'll get dozens of parameters — oscillator shapes, filter cutoff, envelope times, LFO rates, and more.

Change one:

```
set_device_parameter(
  track_index=1, device_index=0,
  parameter_name="Filter 1 Freq",
  value=0.45
)
```

Parameter values are normalized between the device's min and max. The exact range depends on the parameter — `get_device_parameters` tells you.

To change several at once (faster, fewer round trips):

```
batch_set_parameters(track_index=1, device_index=0, parameters=[
  {"name_or_index": "Filter 1 Freq", "value": 0.45},
  {"name_or_index": "Filter 1 Res", "value": 0.6},
  {"name_or_index": "Osc 1 Level", "value": 0.85}
])
```

### Building an effect chain

Effects load in order onto a track's device chain. Each `find_and_load_device` or `load_browser_item` call appends the device after the existing ones:

```
// Track already has a synth at device_index 0
find_and_load_device(track_index=1, device_name="EQ Eight")     // device_index 1
find_and_load_device(track_index=1, device_name="Compressor")   // device_index 2
find_and_load_device(track_index=1, device_name="Saturator")    // device_index 3
find_and_load_device(track_index=1, device_name="Utility")      // device_index 4
```

After building the chain, verify with `get_track_info` to confirm device order and count.

You can also temporarily disable a device to A/B test it:

```
toggle_device(track_index=1, device_index=3, active=false)  // bypass Saturator
// listen...
toggle_device(track_index=1, device_index=3, active=true)   // re-enable
```

### Browsing presets for a device

If you have a device loaded but want to try different presets:

```
get_device_presets(device_name="Wavetable")
```

This returns all available presets with their URIs. To load one:

```
load_device_by_uri(track_index=1, uri="<preset uri>")
```

This replaces the existing device with the preset version — same device type, different sound.


## 4. Arrangement Workflow

Session View is great for jamming and building ideas. Arrangement View is where you structure a song. LivePilot bridges the two.

### Building arrangement from session clips

The typical workflow: build patterns in Session View, then place them on the timeline.

Say you have a drum pattern in clip slot 0 on track 0. To place it in the arrangement:

```
create_arrangement_clip(
  track_index=0,
  clip_slot_index=0,    // which session clip to use as source
  start_time=0.0,       // beat position on the timeline
  length=32.0,          // 8 bars long on the timeline
  loop_length=8.0,      // the 2-bar pattern loops within those 8 bars
  name="Drums Intro"
)
```

The key parameters:
- `clip_slot_index` is the session clip you're pulling the pattern from
- `start_time` is where it lands on the arrangement timeline (in beats)
- `length` is how long it occupies on the timeline
- `loop_length` controls the internal loop — if your source clip is 8 beats but you want it to repeat for 32 beats, set `length=32.0` and `loop_length=8.0`

Place more clips to build out the arrangement:

```
// Bass enters at bar 5 (beat 16)
create_arrangement_clip(
  track_index=1, clip_slot_index=0,
  start_time=16.0, length=64.0, loop_length=16.0,
  name="Bass Main"
)

// Pad enters at bar 9 (beat 32)
create_arrangement_clip(
  track_index=3, clip_slot_index=0,
  start_time=32.0, length=32.0,
  name="Pad Wash"
)
```

### Editing notes in arrangement clips

You can add, modify, and remove notes directly in arrangement clips. The tools mirror the session clip note tools but work on arrangement clip indices:

```
// Get notes from an arrangement clip
get_arrangement_notes(track_index=0, clip_index=0)

// Add notes to an arrangement clip (times are relative to clip start)
add_arrangement_notes(track_index=0, clip_index=0, notes=[
  {"pitch": 36, "start_time": 0.0, "duration": 0.5, "velocity": 110}
])

// Modify notes by ID
modify_arrangement_notes(track_index=0, clip_index=0, modifications=[
  {"note_id": 5, "velocity": 90}
])

// Remove specific notes
remove_arrangement_notes_by_id(track_index=0, clip_index=0, note_ids=[5, 8, 12])

// Remove all notes in a region
remove_arrangement_notes(track_index=0, clip_index=0, from_time=4.0, time_span=4.0)

// Transpose an arrangement clip up 2 semitones
transpose_arrangement_notes(track_index=1, clip_index=0, semitones=2)
```

Important: `clip_index` for arrangement tools refers to the index in the track's `arrangement_clips` list (returned by `get_arrangement_clips` or `create_arrangement_clip`), not the session clip slot.

### Setting cue points for navigation

Cue points are bookmarks in your arrangement. Jump to the playback position you want, then toggle a cue point:

```
jump_to_time(beat_time=0.0)
toggle_cue_point()    // creates a cue point at beat 0

jump_to_time(beat_time=32.0)
toggle_cue_point()    // creates a cue point at beat 32 (bar 9)
```

Later, you can jump between them:

```
get_cue_points()               // see all cue points
jump_to_cue(cue_index=1)      // jump to the second cue point
```

Cue points make it easy to navigate a long arrangement. Name your sections, mark the transitions, and jump around as you work.

### Switching to arrangement playback

If you've been playing session clips, Ableton stays in "session override" mode even when you switch to Arrangement View. The arrangement won't play unless you explicitly tell it to:

```
back_to_arranger()
```

This is the equivalent of clicking the "Back to Arrangement" button in Ableton. After calling this, playback follows the arrangement timeline instead of session clips.

### Recording into arrangement

To capture a live performance into the arrangement:

```
// Arm the tracks you want to record
set_track_arm(track_index=0, armed=true)

// Start arrangement recording
start_recording(arrangement=true)

// ... perform ...

// Stop recording
stop_recording()

// Don't forget to disarm
set_track_arm(track_index=0, armed=false)
```

You can also record session clip launches into the arrangement — fire scenes while arrangement recording is active, and Ableton captures it all on the timeline.


## 5. Mixing Workflow

Mixing is its own deep topic — see the [Mixing](mixing.md) chapter for a thorough treatment. Here's the quick version using LivePilot.

### Setting levels

Start with everything at a reasonable level. The default volume (0.85) is unity gain (0 dB). Pull things down from there:

```
set_track_volume(track_index=0, volume=0.75)   // drums, slightly below unity
set_track_volume(track_index=1, volume=0.65)   // bass
set_track_volume(track_index=2, volume=0.55)   // keys, sitting back
set_track_volume(track_index=3, volume=0.50)   // pad, further back
```

For panning:

```
set_track_pan(track_index=2, pan=-0.25)  // keys slightly left
set_track_pan(track_index=4, pan=0.20)   // lead slightly right
```

Pan is -1.0 (hard left) to 1.0 (hard right), with 0.0 being center.

### Setting up sends

Send your tracks to the return tracks you set up earlier:

```
set_track_send(track_index=2, send_index=0, value=0.30)  // keys to reverb
set_track_send(track_index=3, send_index=0, value=0.45)  // pad to reverb
set_track_send(track_index=4, send_index=1, value=0.20)  // lead to delay
```

### Running diagnostics

The diagnostics tool catches common mix issues before they bite you:

```
get_session_diagnostics()
```

This scans your entire session and reports problems like:
- Tracks still armed (you forgot to disarm after recording)
- Solo left on (a track is soloed, so you're not hearing the full mix)
- Unnamed tracks (hard to navigate)
- Empty clips (dead weight)
- MIDI tracks without instruments (they'll be silent)

### Checking routing

If something isn't making sound, check its routing:

```
get_track_routing(track_index=0)
```

This shows the track's input source, input channel, output destination, and output channel. Common issues: output routed to the wrong bus, input monitoring set incorrectly, or a track sending to a return that doesn't exist.


## 6. Session Hygiene

A clean session is a productive session. Run diagnostics regularly, especially before mixing or exporting.

### The diagnostics tool

```
get_session_diagnostics()
```

This returns a list of issues with severity levels (warning or info) and a summary of session stats. Think of it as a health check.

### Common problems it catches

**Armed tracks.** You recorded an hour ago and forgot to disarm. Now your tracks are record-enabled and you might accidentally overwrite something. The fix:

```
set_track_arm(track_index=2, armed=false)
```

**Solo leftovers.** You soloed a track to listen to it in isolation and forgot to unsolo. Now you're only hearing one track and wondering why your mix sounds thin. The fix:

```
set_track_solo(track_index=3, soloed=false)
```

**Unnamed tracks.** "1-MIDI", "2-MIDI", "3-Audio" — once you have 15 tracks, you'll have no idea what's what. Name everything:

```
set_track_name(track_index=0, name="DRUMS")
set_track_name(track_index=1, name="BASS")
```

**Empty clips.** Clip slots with clips that have no notes in them. They play silence and take up visual space. Either delete them or populate them:

```
delete_clip(track_index=2, clip_index=3)  // remove the empty clip
```

**MIDI tracks without instruments.** A MIDI track with notes but no instrument produces no sound. The diagnostics tool flags these. Load an instrument:

```
find_and_load_device(track_index=4, device_name="Analog")
```

### Making it a habit

Run `get_session_diagnostics` at these moments:
- When you first open a project (catch stale state from your last session)
- Before mixing (make sure nothing is soloed/muted that shouldn't be)
- Before exporting (catch armed tracks, empty clips, routing issues)
- When something "just doesn't sound right" (often a solo or mute you forgot about)


## 7. Tips and Best Practices

These patterns come from real production use. They'll save you time and frustration.

### Always start with get_session_info

This is the single most important habit. Before doing anything, read the session state. It prevents:
- Creating duplicate tracks (you already have a DRUMS track)
- Setting a tempo that's already set
- Working on the wrong track index (you thought bass was track 1, but it's track 3)

Just ask: "What's in my session?" The AI will call `get_session_info` and ground itself in reality.

### Verify after every write

The **read-write-verify** loop is the foundation of reliable production with LivePilot:

1. **Read** — check the current state (`get_session_info`, `get_track_info`, `get_notes`)
2. **Write** — make the change (`add_notes`, `set_device_parameter`, `create_clip`)
3. **Verify** — read back the state to confirm it worked (`get_notes`, `get_track_info`)

This isn't paranoia. TCP connections can drop, commands can race, and Ableton can be in an unexpected state. Verifying takes a fraction of a second and catches errors before they compound.

### Use undo liberally

Every change LivePilot makes can be undone. If you don't like what happened:

```
undo()
```

If you changed your mind about undoing:

```
redo()
```

Undo works on the most recent action in Ableton's undo history, so it covers everything — notes, device changes, track creation, clip modifications. Don't be afraid to experiment aggressively. You can always go back.

### One operation at a time

When you're building something complex, break it into steps and listen between each one. Instead of "make me a complete song," try:

1. "Set up a 124 BPM session with drums and bass"
2. *Listen.* "The kick needs more punch — find a different kit"
3. *Listen.* "Good. Now add a simple bass line in D minor"
4. *Listen.* "Make the bass pattern more syncopated"

Each step gives you a chance to redirect. The AI executes fast, but creative decisions need your ears.

### Name everything

Naming tracks, clips, and scenes costs nothing and saves everything. A session full of "MIDI 1", "MIDI 2", "Audio 3" is unnavigable after 30 minutes. A session with "DRUMS", "BASS", "PAD", "Intro", "Chorus" tells you exactly where you are at a glance.

Name things as you create them (the `name` parameter in `create_midi_track`, `set_clip_name`, `set_scene_name`). If you inherit a messy session, spend two minutes naming tracks before you start working. You'll make it back in five.

### The read-write-verify loop

Worth repeating because it's that important. Here's the full pattern for adding notes to a clip:

1. `get_clip_info(track_index=0, clip_index=0)` — confirm the clip exists, check its length
2. `add_notes(track_index=0, clip_index=0, notes=[...])` — add the notes
3. `get_notes(track_index=0, clip_index=0)` — read back the notes, confirm they're there
4. `fire_clip(track_index=0, clip_index=0)` — listen to the result
5. If something's wrong: `modify_notes(...)` or `undo()` and try again

This loop applies to everything — device parameter changes, track routing, arrangement editing. Read, write, verify, listen.

---

Next: [MIDI Guide](midi-guide.md) | Back to [Manual](index.md)
