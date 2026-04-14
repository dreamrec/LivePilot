# Composition & Arrangement Planning

LivePilot goes beyond placing clips on a timeline. The Composition Engine analyzes song structure, the Composer generates multi-layer plans from text prompts, and arrangement planning now includes section-aware sample roles.

---

## Composition Engine — Understanding Structure

### Section analysis

```
get_section_graph()
→ sections: [
    {id: "intro", bars: 8, energy: 0.3, density: 0.2, tracks_active: [0]},
    {id: "verse", bars: 16, energy: 0.5, density: 0.5, tracks_active: [0, 1, 2]},
    {id: "chorus", bars: 16, energy: 0.8, density: 0.8, tracks_active: [0, 1, 2, 3, 4]}
]
```

Infers song structure from scene names, clip arrangement, and track activity. Returns a graph of sections with energy levels, density, and which tracks are active in each.

### Motif detection

```
get_motif_graph()
→ motifs: [
    {id: "m1", type: "rhythmic", track: 0, occurrences: 4, developed: true},
    {id: "m2", type: "melodic", track: 2, occurrences: 2, developed: false}
]
```

Finds repeated musical ideas and tracks whether they're being developed or neglected.

### Emotional arc

```
get_emotional_arc()
→ arc: [0.3, 0.5, 0.8, 1.0, 0.6, 0.3]
→ shape: "build_to_peak"
→ suggestions: ["Bridge energy dips too quickly — consider a plateau before descent"]
```

Maps the energy trajectory of the song and identifies structural imbalances.

### Section transformation

```
transform_section(transformation="intensify", section_index=2)
→ plan: [add elements, increase velocity, widen stereo, automate filter up]
```

Proposes and executes changes to a section based on the transformation type.

---

## Composer — Prompt to Plan

The Composer parses natural language into multi-layer composition plans.

```
compose(prompt="dark minimal techno 128bpm with industrial textures and ghostly vocals")
→ intent: {genre: "techno", mood: "dark", tempo: 128, key: "Dm"}
→ layers: [
    {role: "kick", search_query: "techno kick 128bpm"},
    {role: "bass", search_query: "dark bass synth"},
    {role: "percussion", search_query: "industrial percussion"},
    {role: "texture", search_query: "ghostly atmospheric pad"},
    {role: "vocal", search_query: "ghost vocal chop"}
]
→ sections: [{name: "intro", bars: 16}, {name: "build", bars: 8}, ...]
→ steps: [create_midi_track, search_samples, load_sample_to_simpler, ...]
```

The Composer returns a plan — it does NOT execute. The agent steps through each tool call in the returned sequence.

### Genre defaults

7 built-in genre profiles with tempo ranges, layer counts, and section templates:

| Genre | Tempo | Layers | Key features |
|-------|-------|--------|-------------|
| Techno | 125-135 | 5-7 | Kick-driven, sparse melody, heavy texture |
| House | 118-128 | 5-6 | Vocal-forward, chord stabs, groove focus |
| Ambient | 60-90 | 3-5 | Sparse, long pads, texture-heavy |
| Hip-hop | 80-100 | 4-6 | Sample-driven, boom-bap or trap patterns |
| Drum & Bass | 170-180 | 5-7 | Fast breaks, heavy bass, atmospheric pads |
| Dub | 65-80 | 4-5 | Heavy reverb/delay, sparse, space-focused |
| Experimental | any | 3-8 | No rules, genre-crossing |

### Dry run preview

```
get_composition_plan(prompt="lo-fi hip hop beat with vinyl texture")
→ shows the full plan without credit checks or execution
```

Use this to see what `compose` would do before committing.

### Augmenting an existing session

```
augment_with_samples(request="add organic textures and a vocal chop", max_layers=2)
→ plan to add 2 new tracks to the existing session
```

This is lighter than `compose` — it adds to what's already there instead of building from scratch.

---

## Arrangement Planning — Section-Aware

### plan_arrangement — Full blueprint

```
plan_arrangement(target_bars=128, style="electronic")
→ sections: [{type: "intro", start: 0, end: 16, sample_hints: ["texture_bed"]}, ...]
→ reveal_order: [{track: 0, enters: "intro"}, {track: 1, enters: "verse"}, ...]
→ gesture_plan: [{transition: "verse→chorus", type: "build_rise"}]
```

Each section now includes `sample_hints` — suggested roles for sample-based elements:

| Section | Default sample hints |
|---------|---------------------|
| Intro | `texture_bed`, `fill_one_shot` |
| Verse | `texture_bed`, `fill_one_shot` |
| Build | `transition_fx`, `texture_bed` |
| Chorus/Drop | `hook_sample`, `break_layer`, `fill_one_shot` |
| Bridge/Breakdown | `texture_bed`, `transition_fx` |
| Outro | `texture_bed`, `fill_one_shot` |

### Connecting arrangement to samples

After getting an arrangement plan with sample hints:

```
# For a chorus that suggests "hook_sample":
plan_sample_workflow(
    search_query="vocal chop hook",
    intent="vocal",
    section_type="chorus",
    desired_role="hook_sample"
)

# For a verse that suggests "texture_bed":
plan_slice_workflow(
    file_path="/path/to/ambient.wav",
    intent="texture",
    target_section="verse",
    bars=8
)
```

---

## Hook Hunter

The Hook Hunter identifies the most salient musical idea in your session and tracks its development.

```
find_primary_hook()
→ hook: {track: 2, type: "melodic", bars: 2-4, salience: 0.85}
→ status: "underdeveloped — appears in verse but not chorus"

detect_hook_neglect()
→ neglected: true
→ suggestion: "The main hook appears only once — consider placing it in the chorus"

develop_hook(strategy="variation")
→ plan to create a variation of the hook for a different section
```

---

## Workflow: From Loop to Full Song

### 1. Analyze what you have

```
get_section_graph()
get_emotional_arc()
find_primary_hook()
```

### 2. Plan the arrangement

```
plan_arrangement(target_bars=128, style="electronic")
```

### 3. Fill sample roles

For each section's `sample_hints`, search and plan:

```
plan_sample_workflow(section_type="chorus", desired_role="hook_sample", search_query="vocal chop")
plan_slice_workflow(file_path="/path/to/break.wav", intent="rhythm", target_section="drop")
```

### 4. Build the timeline

```
create_arrangement_clip(track_index=0, clip_slot_index=0, start_time=0, length=64)
# ... continue for each track and section
```

### 5. Add transitions

```
apply_automation_recipe(recipe="build_rise", ...)  # before the drop
apply_automation_recipe(recipe="washout", ...)      # end of chorus
```

### 6. Evaluate

```
get_emotional_arc()  # verify the energy flow makes sense
detect_hook_neglect()  # make sure the hook is developed
```

---

Next: [MIDI Guide](midi-guide.md) | Back to [Manual](index.md)
