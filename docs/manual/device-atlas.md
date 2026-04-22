# Device Atlas

The Device Atlas is an in-memory indexed database of every device in
Ableton's library — **1305 devices** with browser URIs, **135 enriched**
with sonic-intelligence profiles, **641 indexed by pack** (Core Library
auto-indexing + explicit-pack YAML declarations). It replaces guessing
device names with querying a knowledge base — and as of v1.17 it's the
primary bridge between the LLM's producer knowledge and LivePilot's
tool surface.

New in v1.17:
- **`atlas_pack_info`** — inspect an entire pack's device list + enrichment coverage
- **`atlas_describe_chain`** — free-text "a granular pad like Tim Hecker" → device chain proposal
- **`atlas_techniques_for_device`** — reverse-lookup: which techniques reference this device?
- **Artist + genre vocabularies** — structured "producer → LivePilot devices" mapping in
  `livepilot/skills/livepilot-core/references/artist-vocabularies.md` and `genre-vocabularies.md`
- **47 enrichments now have `signature_techniques`** — aesthetic-tagged technique entries
  (up from 32 pre-v1.17) with 45 new native-synth entries covering Hawtin, Villalobos,
  Akufen, Dilla, Basinski, Hecker, and other canonical production styles

---

## Why Use the Atlas

Without the atlas, loading a device requires searching the browser by
name and hoping for the right match. The atlas gives you:

- **Exact names and URIs** — no hallucinated device names
- **Intent-based suggestions** — "warm pad for ambient" → Drift + specific preset + recipe
- **Full device chains** — "bass track for techno" → instrument + EQ + compressor + saturator
- **Free-text describe** (v1.17+) — "sound like Villalobos" → chain proposal
- **Reverse-lookup** (v1.17+) — "what can I do with Granulator III?" → all techniques that reference it
- **Side-by-side comparison** — Drift vs. Wavetable for a specific role
- **Pack-level inspection** (v1.17+) — "what's in Drone Lab?" → pack device list + enrichment stats
- **Sonic intelligence** — mood, genre fit, sweet spots, anti-patterns, recommended pairings,
  **signature techniques tagged by producer / aesthetic**

---

## The 10 Atlas Tools

### atlas_search — Find devices by keyword or character

```
atlas_search(query="reverb", category="audio_effects")
→ Reverb, Hybrid Reverb, Convolution Reverb, …

atlas_search(query="warm analog bass")
→ Analog, Drift, Wavetable (ranked by relevance)
```

Search by name, sonic character, use case, or genre. The `category`
filter narrows results: `instruments`, `audio_effects`, `midi_effects`,
`max_for_live`, `drum_kits`. Scoring weights exact-name (+45),
character-tag (+35), use-case (+25), genre (+20), description (+15).

### atlas_suggest — Intent-driven recommendation

```
atlas_suggest(intent="warm pad for ambient", genre="ambient")
→ device: Drift
→ recipe: "Start with Triangle osc, filter at 800Hz, slow LFO on filter, drift amount 40%"
→ rationale: "Drift's built-in instability creates organic movement ideal for ambient pads"
```

The recommended way to find devices. Describe what you want musically,
not technically.

### atlas_describe_chain — Free-text describe-a-chain **[v1.17+]**

```
atlas_describe_chain(description="a granular pad that sounds like Tim Hecker")
→ detected_roles: ["pad"]
→ detected_aesthetic: ["ambient", "drone", "experimental"]
→ chain_proposal:
    0: Granulator III  — "Granulator III is an instrument suited for ambient, drone"
    1: Convolution Reverb — (from pad chain companions)
→ next_steps: "Cross-reference artist-vocabularies.md and genre-vocabularies.md"
```

The **mirror of `splice_describe_sound`** for the device library — when
you want an aesthetic description turned into a concrete device chain
without manually orchestrating search + suggest + chain_suggest.

Parses role hints (bass/pad/lead/percussion/drums/vocal/fx), artist
hints (maps ~20 producers to aesthetic tag lists), genre keywords,
and character words (warm/dark/granular/metallic/etc).

### atlas_chain_suggest — Full device chain from structured role

```
atlas_chain_suggest(role="bass", genre="techno")
→ instrument: Analog (saw + sub layer)
→ effects: [EQ Eight (HPF 30Hz), Compressor (4:1), Saturator (Analog Clip)]
→ rationale: "Clean low end from EQ, consistent dynamics from compression, harmonics from saturation"
```

Returns a complete chain for a track role. Roles: `bass`, `lead`,
`pad`, `keys`, `drums`, `percussion`, `texture`, `vocal`. When you
already know the role but want the genre-appropriate chain, this is
faster than `atlas_describe_chain`.

### atlas_compare — Side-by-side

```
atlas_compare(device_a="Drift", device_b="Wavetable", role="pad")
→ Drift: simpler, faster results, built-in movement, limited modulation
→ Wavetable: deeper modulation, more unison options, steeper learning curve
→ recommendation: "Drift for quick organic pads, Wavetable for evolving cinematic textures"
```

### atlas_device_info — Inward-looking device profile

```
atlas_device_info(device_id="drift")
→ parameters, sweet spots, anti-patterns, genre fit, recommended chains,
   starter_recipes, signature_techniques (if enriched), pairs_well_with
```

Returns the full enriched profile for devices that have sonic
intelligence (135 out of 1305). For non-enriched devices, returns basic
parameter info and browser URI.

### atlas_techniques_for_device — Reverse-lookup **[v1.17+]**

```
atlas_techniques_for_device(device_id="granulator_iii")
→ techniques: [
    {technique: "Arpiar bell through Convolution Reverb", kind: "signature_technique", …},
    {technique: "Grain cloud (Tim Hecker)", kind: "signature_technique", …},
    {technique: "extreme_stretch", kind: "sample_technique",
        source: "sample-techniques.md", …},
    {technique: "Space as Composition", kind: "sound_design_principle", …},
    …
  ]
```

The inverse of `atlas_device_info`. Instead of "what does THIS device
do?" it answers "what techniques across the whole knowledge base
REACH FOR this device?" — pulling from the device's own
`signature_techniques`, from `sample-techniques.md` principles, and
from `sound-design-deep.md` references.

The underlying `device_techniques_index.json` is auto-generated — **146
cross-references across 58 devices** as of v1.17.

### atlas_pack_info — Pack-level inspection **[v1.17+]**

```
atlas_pack_info(pack_name="Drone Lab")
→ device_count: 2
→ enriched_count: 2
→ devices: [
    {id: "harmonic_drone_generator", name: "Harmonic Drone Generator", category: "sounds", enriched: true},
    {id: "harmonic_drone_generator", name: "Harmonic Drone Generator", category: "max_for_live", enriched: true}
  ]

atlas_pack_info()  # no arg → full pack list
→ packs: [
    {name: "Core Library", device_count: 614, enriched_count: 82},
    {name: "Creative Extensions", device_count: 15, enriched_count: 15},
    …
  ]
```

Indexes 641 devices by pack — Core Library heuristic (all native
instruments, effects, MIDI effects, and M4L devices without an
explicit pack) plus 27 explicit-pack enrichment YAMLs (Drone Lab,
Creative Extensions, Inspired by Nature, CV Tools, Performance Pack,
PitchLoop89, Granulator III, Microtuner, Sequencers, Generators by
Iftah, Expressive Chords, Surround Panner, Building Max Devices).

### scan_full_library — Rebuild the atlas

```
scan_full_library()
```

Scans Ableton's browser and rebuilds the atlas from scratch. Run this
after installing new packs or Max for Live devices. Takes 10-30
seconds depending on library size.

### reload_atlas — Force reload from disk

```
reload_atlas()
```

Re-read `device_atlas.json` after an out-of-band edit (rare). Normally
`scan_full_library` handles reload internally.

---

## The Concept Surface (v1.17+)

The atlas alone is 1305 device entries with character tags. The
concept surface bridges the LLM's **training** to those entries — so
queries like "sound like Wolfgang Voigt" or "microhouse chord stab"
have a concrete path.

Three files:

### `references/artist-vocabularies.md`

~25 producers with four-field structured entries:

```
### Wolfgang Voigt (Gas)
**Sonic fingerprint:** Orchestral loops sampled, crushed into 4/4 kick,
blurred by heavy reverb into undifferentiated harmonic drone.
**Reach for:** Granulator III (Cloud mode), Harmonic Drone Generator,
Convolution Reverb (cathedral IR), Auto Filter.
**Avoid:** Crisp transients, bright EQ, dry tails.
**Key techniques:** `"Grain cloud (Tim Hecker)"`, `"Basinski tape degradation"`,
`"extreme_stretch"`, `"tail_harvest"`, `"drum_to_pad"`.
```

The LLM reads "sound like Gas" and has a direct path: read the entry,
query `atlas_search` for each Reach-for device, call
`atlas_techniques_for_device` on each to see applicable techniques.

### `references/genre-vocabularies.md`

15 genres with tempo + kick + bass + percussion + harmonic + texture
+ reach-for + avoid structure. Example:

```
## Microhouse
**Tempo / time:** 122-128 BPM, 4/4 with constant micro-variation.
**Kick:** Minimal, short decay, ~55 Hz fundamental. Not the feature.
**Percussion:** Hyper-chopped vocal snippets, glass/metal percussion.
**Reach for:** Simpler (slicing), Snipper, Drift, Poli, Granulator III,
PitchLoop89, Auto Filter, Voice Box pack, Chop and Swing pack.
**Avoid:** Loud kicks, sidechain, long-sustain melody, bright overtones.
**Key techniques:** `"Vocal micro-chop (Akufen)"`, `"micro_chop"`,
`"dub_throw"`, `"Hat replay pitch drift"`.
```

When asked for "microhouse", the LLM reads this before device selection.

### Per-device `signature_techniques` (in atlas enrichments)

47 enrichments have aesthetic-tagged technique entries. Example from
`analog.yaml`:

```yaml
signature_techniques:
  - name: "Hawtin subtractive pad"
    description: "Single saw, slow filter sweep from dark to bright across
                  32 bars, filter env amount negative — the pad evolves by
                  unfolding, not by adding."
    aesthetic: [minimal_techno, deep_minimal]
  - name: "303 acid bass"
    description: "Osc1 saw, octave down, LP24 with high resonance (0.8+),
                  env amount 0.9, amp decay short. Use Filter1 Freq + Res
                  as performance controls."
    aesthetic: [acid_house, acid_techno]
```

These are concept breadcrumbs — NOT recipes. Each entry tags its
aesthetic context so the LLM can reach for it when the user says
"Hawtin" or "acid".

---

## What's Enriched

135 devices have deep sonic-intelligence profiles:

| Category | Count | Examples |
|----------|-------|---------|
| Audio Effects | 52 | Compressor, Reverb, Echo, Saturator, EQ Eight, Auto Filter, Corpus, Vocoder, Utility, Amp, Cabinet, Resonators |
| Instruments | 22 | Drift, Analog, Wavetable, Operator, Simpler, Sampler, Tension, Collision, Drum Rack, Granulator III, Harmonic Drone Generator, Vector FM, Vector Grain, Meld, Bass, Poli, Emit, Electric, Bell Tower, Sting Iftah |
| MIDI Effects | 22 | Arpeggiator, Scale, Chord, Filler, Expressive Chords, Microtuner, Phase Pattern, Polyrhythm, Retrigger, Slice Shuffler, SQ Sequencer, Stages |
| Utility / CV | 24 | Utility, External Instrument, CV Tools suite (10), Performer, Variations, Arrangement Looper, Prearranger, Surround Panner, Vector Map, Rotating Rhythm Generator |

Non-enriched devices (1170) still have name, URI, category, and basic
parameter info — enough for search and loading.

---

## Workflow: Loading Devices with the Atlas

### Pattern 1 — "Sound like X" (new in v1.17)

```
atlas_describe_chain(description="warm dub techno chord stab")
→ detected_roles: ["pad", "keys"]  (chord stab is harmonic/tonal)
→ detected_aesthetic: ["dub_techno", "warm"]
→ chain_proposal: [Poli, Convolution Reverb, Echo]

# Expand with technique lookup
atlas_techniques_for_device(device_id="poli")
→ techniques including "Retro stab", "Warm pad"

# Then load
find_and_load_device(track_index=0, device_name="Poli")
```

### Pattern 2 — Structured role

```
atlas_chain_suggest(role="drums", genre="house")
→ Drum Rack (808 Core Kit), EQ Eight, Drum Buss

atlas_chain_suggest(role="bass", genre="house")
→ Analog, EQ Eight, Compressor, Saturator
```

Load each chain in order using `find_and_load_device` for each device.

### Pattern 3 — "What can I do with this?"

```
atlas_techniques_for_device(device_id="granulator_iii")
→ 4 techniques, including "Grain cloud (Tim Hecker)"
  and "granular_scatter" from sample-techniques.md

# Now the LLM has concrete technique names to compose
```

---

## Tips

- **Use `atlas_describe_chain` for aesthetic queries.** It's the
  closest atlas analog to how people talk about music.
- **Use `atlas_suggest` for specific intent.** Description-to-device
  when the user already knows the role.
- **Use `atlas_chain_suggest` for track scaffolding.** Role+genre →
  instrument + effects in one call.
- **Use `atlas_techniques_for_device` when exploring.** "What can I
  do with Granulator III?" — answered from three data sources.
- **Use `atlas_pack_info` to audit coverage.** "What's in Drone Lab?"
  or "How much of Creative Extensions do we have knowledge about?"
- **Always re-run `scan_full_library` after installing a pack.** The
  atlas only knows about devices it has scanned.

---

Next: [Samples & Slicing](samples.md) | Back to [Manual](index.md)
