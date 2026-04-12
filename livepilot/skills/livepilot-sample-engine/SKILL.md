---
name: livepilot-sample-engine
description: >
  This skill should be used when the user asks to "sample", "chop",
  "slice a loop", "find me a sample", "load a sample", "flip this",
  "resample", "vocal chop", "found sound", "texture from", "turn this into",
  "break", "one-shot", "load into Simpler", or when get_sample_opportunities
  finds gaps in the song's sample usage.
---

# Sample Engine — AI Sample Manipulation for Ableton Live

The Sample Engine is LivePilot's intelligence layer for sample discovery,
analysis, critique, and creative manipulation. It turns raw samples into
musical elements through 29 techniques drawn from Dilla, Burial, Amon Tobin,
Four Tet, and DJ Premier.

## Philosophy: Surgeon vs Alchemist

Every sample workflow is guided by one of two philosophies:

- **Surgeon** — Precision. Match key, align tempo, carve frequencies, blend
  seamlessly. The sample should sound like it was always part of the track.
- **Alchemist** — Transformation. Reverse, stretch, destroy, rebuild.
  The original creator shouldn't recognize their sample.
- **Auto** (default) — Context decides. Building a clean layer? Surgeon.
  Stuck and need surprise? Alchemist. The critics and intent determine which.

## 6 MCP Tools

| Tool | Purpose |
|------|---------|
| `analyze_sample` | Build SampleProfile — material type, key, BPM, recommendations |
| `evaluate_sample_fit` | 6-critic battery — key, tempo, frequency, role, vibe, intent fit |
| `search_samples` | Search browser, filesystem, and Freesound |
| `suggest_sample_technique` | Recommend techniques from the 29-recipe library |
| `plan_sample_workflow` | End-to-end plan: analyze + critique + technique + compiled steps |
| `get_sample_opportunities` | Analyze song for where samples could improve it |

## Workflow Modes

### Direct Request
User asks to do something specific with a sample:
```
"Chop this vocal into a rhythm"
 -> analyze_sample -> evaluate_sample_fit(intent="rhythm")
 -> suggest_sample_technique -> execute
```

### Discovery Mode
User wants to find and use a sample:
```
"Find me a dark vocal for this track"
 -> search_samples(query="dark vocal") -> present candidates
 -> user picks -> analyze -> critique -> plan -> execute
```

### Wonder Mode Integration
When stuck, Wonder Mode can suggest sample-based variants:
- 6 sample-domain semantic moves in the registry
- Fully compiled, previewable, committable plans
- Diagnosis detects: no_organic_texture, stale_drums, dense_but_static

## Golden Rules

1. **Always analyze before loading** — `analyze_sample` tells you what
   the material is before you commit to a technique
2. **Always critique before executing** — `evaluate_sample_fit` catches
   key clashes, tempo mismatches, and frequency masking before they happen
3. **Respect the intent** — "rhythm" and "texture" need different approaches
   even for the same sample
4. **Start from the nearest technique** — don't improvise a workflow when
   a proven recipe exists in the library
5. **Present both plans** — surgeon and alchemist. Let the user choose.

## Material Types

| Type | Detection | Best Simpler Mode | Best Warp Mode |
|------|-----------|-------------------|----------------|
| vocal | "vocal", "vox", "voice" in name | Slice (Region) | Complex Pro |
| drum_loop | "drum", "break", "beat" in name | Slice (Transient) | Beats |
| instrument_loop | "guitar", "piano", "synth" | Slice (Beat) | Complex Pro |
| one_shot | "kick", "snare", "clap", short | Classic | Complex |
| texture | "ambient", "pad", "drone" | Classic | Texture |
| foley | "foley", "field", "recording" | Classic | Texture |
| fx | "fx", "riser", "sweep" | Classic | Complex |
| full_mix | full mix, long duration | Slice (Beat) | Complex Pro |

## 6 Sample Critics

Each scores 0.0-1.0 on one dimension of fitness:

1. **Key Fit** — Circle-of-fifths distance from song key
2. **Tempo Fit** — BPM match including half/double time
3. **Frequency Fit** — Spectral overlap with existing mix
4. **Role Fit** — Does this fill a missing role in the song?
5. **Vibe Fit** — Taste graph alignment (if evidence exists)
6. **Intent Fit** — Does the material serve the stated goal?

## Reference Docs

- `references/sample-techniques.md` — Full 29-technique catalog
- `references/sample-critics.md` — Critic scoring details
- `references/sample-philosophy.md` — Surgeon vs Alchemist guide
