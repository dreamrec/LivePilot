# Samples & Slicing

LivePilot searches three sample sources simultaneously, scores every result with 6 fitness critics, and offers 29 processing techniques. This chapter covers the full sample workflow — from finding a sound to slicing it into a playable instrument.

---

## Three Sample Sources

| Source | What it searches | Requirements |
|--------|-----------------|--------------|
| **BrowserSource** | Ableton's built-in library — factory samples, installed packs | None (always available) |
| **SpliceSource** | Your downloaded Splice samples with full metadata (key, BPM, genre, tags) | Splice desktop app installed with downloaded samples |
| **FilesystemSource** | Any directory on your machine | Configured paths |

All three are searched in parallel. Results are merged and ranked.

### Splice integration (plan-aware, v1.16.0)

LivePilot talks to Splice through **two** paths:

1. **Local SQLite** (`sounds.db`) — every sample you've downloaded, instant search, zero network.
2. **Local gRPC** (Splice desktop app on localhost TLS) — online catalog search, downloads, previews, user collections, presets.

The gRPC path detects your plan via `User.Features` / `User.SoundsPlan` / `SoundsStatus` and exposes a two-pocket model:

- **Daily sample quota** — 100/day on the Splice x Ableton Live plan. Sample downloads deplete this counter, NOT credits.
- **Splice.com credits** — reserved for presets, MIDI, and Splice Instrument content. Protected by `CREDIT_HARD_FLOOR=5`.

Free samples (`Sample.IsPremium==False` or `Price==0`) bypass both gates — they cost nothing under any plan.

Every sample carries a `preview_url` that streams for free. Use `splice_preview_sample` to audition before spending anything.

If you don't have Splice, the Sample Engine still works — it just searches Ableton's browser and your filesystem.

---

## The 7 Tools

### search_samples — Find samples

```
search_samples(query="dark vocal chop", material_type="vocal", key="Cm")
→ results from Splice, browser, and filesystem
→ each result has: name, file_path, source, key, bpm, material_type, tags
```

Optional filters: `material_type`, `key`, `bpm_range` ("120-130"), `source` ("splice", "browser", "filesystem").

### analyze_sample — Build a profile

```
analyze_sample(file_path="/path/to/sample.wav")
→ material_type: "percussion"
→ spectral_centroid: 2400 Hz
→ estimated_key: "none" (percussive)
→ estimated_bpm: 128
→ simpler_mode_recommendation: "slice"
```

Analyzes a sample's characteristics from its filename and metadata. Returns a `SampleProfile` with material classification, spectral estimates, and a Simpler mode recommendation.

### evaluate_sample_fit — 6-critic fitness scoring

```
evaluate_sample_fit(
    file_path="/path/to/sample.wav",
    target_key="Dm",
    target_bpm=128,
    target_role="texture",
    target_genre="techno"
)
→ key_fit: 0.9
→ tempo_fit: 1.0
→ frequency_fit: 0.7
→ role_fit: 0.8
→ vibe_fit: 0.6
→ intent_fit: 0.75
→ overall: 0.79
```

The 6 critics score how well a sample fits your specific context. Use this to compare candidates objectively.

### suggest_sample_technique — Processing recommendation

```
suggest_sample_technique(file_path="/path/to/break.wav", intent="rhythm")
→ technique: "transient_slice"
→ philosophy: "surgeon"
→ steps: ["load into Simpler", "set Slice mode", "slice by transients", "program groove pattern"]
```

The 29-technique library spans two philosophies:
- **Surgeon** — precision integration, transparent processing
- **Alchemist** — creative transformation, experimental mangling

### plan_sample_workflow — Full pipeline

```
plan_sample_workflow(
    file_path="/path/to/vocal.wav",
    intent="vocal",
    philosophy="alchemist",
    section_type="chorus",
    desired_role="hook_sample"
)
→ compiled plan with tool calls: analyze → load → process → place
```

Returns a complete step-by-step plan. The agent executes each tool call in sequence.

### get_sample_opportunities — Session-aware suggestions

```
get_sample_opportunities()
→ opportunities:
  - "Add organic texture to fill sparse verse" (confidence: 0.8)
  - "Layer break over drum pattern for contrast" (confidence: 0.6)
```

Analyzes the current session and suggests where samples could improve it. Wonder Mode calls this automatically when it detects sample-related stuckness.

### plan_slice_workflow — End-to-end slicing

```
plan_slice_workflow(
    file_path="/path/to/break.wav",
    intent="rhythm",
    bars=4,
    target_section="verse"
)
→ steps: [create_midi_track, load_sample_to_simpler, set_simpler_playback_mode(Slice),
          create_clip, add_notes(real MIDI notes mapped to slices)]
→ note_map: [{slice_index: 0, midi_note: 60}, {slice_index: 1, midi_note: 61}, ...]
→ suggested_techniques: ["quantize_clip", "add reverb send"]
```

This is the canonical slice orchestrator. It generates real MIDI notes based on intent:

| Intent | Pattern style | Density |
|--------|--------------|---------|
| `rhythm` | Sparse groove, downbeat emphasis | Medium |
| `hook` | Repeated motif contour | High |
| `texture` | Long sustained notes, filtered | Low |
| `percussion` | Kick/snare/hat distribution | Medium-high |
| `melodic` | Pitch contour phrase | Medium |

You can also target an existing Simpler instead of loading a new sample:

```
plan_slice_workflow(track_index=2, device_index=0, intent="hook")
```

---

## Workflow: Sample from Scratch

### 1. Search

```
search_samples(query="dark atmospheric texture", source="splice")
```

### 2. Evaluate candidates

```
evaluate_sample_fit(file_path="result_1.wav", target_key="Dm", target_bpm=128, target_role="texture")
evaluate_sample_fit(file_path="result_2.wav", target_key="Dm", target_bpm=128, target_role="texture")
```

Pick the highest overall score.

### 3. Plan the workflow

```
plan_sample_workflow(file_path="best_match.wav", intent="texture", philosophy="surgeon")
```

### 4. Execute the plan

The agent follows the returned steps: create track → load into Simpler → set processing → add to arrangement.

---

## Workflow: Slice a Break

### 1. Find a break

```
search_samples(query="breakbeat 128bpm", material_type="loop")
```

### 2. Plan the slice workflow

```
plan_slice_workflow(file_path="/path/to/break.wav", intent="rhythm", bars=4)
```

### 3. Execute

The plan creates a track, loads the sample into Simpler in Slice mode, creates a clip, and programs MIDI notes that trigger individual slices in a groove pattern.

### 4. Refine

After the pattern is programmed, you can:
- Modify note velocities for dynamics
- Adjust timing for groove
- Add effects (reverb send, compression)
- Use `quantize_clip` to tighten or loosen timing

---

## Wonder Mode Integration

When Wonder detects sample-related stuckness patterns (stale drums, no organic texture, dense but static), it automatically:

1. Calls `get_sample_opportunities` to find where samples would help
2. Searches for candidates via `search_samples`
3. Resolves a real `file_path` before compiling the variant
4. Produces executable plans with actual sample paths — not placeholders

If no sample candidate can be found, the variant is marked `analytical_only` — honest about what it can and cannot do.

---

## Tips

- **Start with search_samples, not the browser.** It searches all three sources and returns richer metadata.
- **Use evaluate_sample_fit to compare candidates.** Don't guess — let the 6 critics score objectively.
- **plan_slice_workflow for any slicing task.** It handles Simpler setup, slice mapping, and MIDI generation in one call.
- **Splice metadata is key.** Downloaded Splice samples have key, BPM, and genre metadata that filesystem samples lack. Download strategically.

---

Next: [Automation](automation.md) | Back to [Manual](index.md)
