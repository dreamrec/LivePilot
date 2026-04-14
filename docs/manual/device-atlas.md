# Device Atlas

The Device Atlas is an in-memory indexed database of every device in Ableton's library — 1305 devices with browser URIs, 81 enriched with sonic intelligence profiles. It replaces guessing device names with querying a knowledge base.

---

## Why Use the Atlas

Without the atlas, loading a device requires searching the browser by name and hoping for the right match. The atlas gives you:

- **Exact names and URIs** — no hallucinated device names
- **Intent-based suggestions** — "warm pad for ambient" → Drift + specific preset + recipe
- **Full device chains** — "bass track for techno" → instrument + EQ + compressor + saturator
- **Side-by-side comparison** — Drift vs. Wavetable for a specific role
- **Sonic intelligence** — mood, genre fit, sweet spots, anti-patterns, recommended pairings

---

## The 6 Tools

### atlas_search — Find devices

```
atlas_search(query="reverb", category="audio_effects")
→ Reverb, Hybrid Reverb, Convolution Reverb, ...

atlas_search(query="warm analog bass")
→ Analog, Drift, Wavetable (ranked by relevance)
```

Search by name, sonic character, use case, or genre. The `category` filter narrows results: `instruments`, `audio_effects`, `midi_effects`, `max_for_live`, `drum_kits`.

### atlas_suggest — Intent-driven recommendation

```
atlas_suggest(intent="warm pad for ambient", genre="ambient")
→ device: Drift
→ recipe: "Start with Triangle osc, filter at 800Hz, slow LFO on filter, drift amount 40%"
→ rationale: "Drift's built-in instability creates organic movement ideal for ambient pads"
```

This is the recommended way to find devices. Describe what you want musically, not technically.

### atlas_chain_suggest — Full device chain

```
atlas_chain_suggest(role="bass", genre="techno")
→ instrument: Analog (saw + sub layer preset)
→ effects: [EQ Eight (HPF 30Hz, cut 200Hz), Compressor (4:1), Saturator (Analog Clip)]
→ rationale: "Clean low end from EQ, consistent dynamics from compression, harmonics from saturation"
```

Returns a complete chain for a track role. Roles: `bass`, `lead`, `pad`, `keys`, `drums`, `texture`, `vocal`.

### atlas_compare — Side-by-side

```
atlas_compare(device_a="Drift", device_b="Wavetable", role="pad")
→ Drift: simpler, faster results, built-in movement, limited modulation
→ Wavetable: deeper modulation, more unison options, steeper learning curve
→ recommendation: "Drift for quick organic pads, Wavetable for evolving cinematic textures"
```

### atlas_device_info — Deep knowledge

```
atlas_device_info(device_id="drift")
→ parameters, sweet spots, anti-patterns, genre fit, recommended chains, recipes
```

Returns the full enriched profile for devices that have sonic intelligence (81 out of 1305). For non-enriched devices, returns basic parameter info and browser URI.

### scan_full_library — Rebuild the atlas

```
scan_full_library()
```

Scans Ableton's browser and rebuilds the atlas from scratch. Run this after installing new packs or Max for Live devices. Takes 10-30 seconds depending on library size.

---

## Workflow: Loading Devices with the Atlas

### Before (browser search)

```
search_browser(path="instruments", name_filter="Drift")
→ multiple results, some are samples named "drift"
load_browser_item(track_index=0, uri="<hope it's the right one>")
get_track_info(track_index=0)  → verify it loaded correctly
```

### After (atlas)

```
atlas_suggest(intent="organic analog pad")
→ Drift, preset: "Slow Evolve", recipe: specific parameter values
find_and_load_device(track_index=0, device_name="Drift")
```

The atlas is faster, more reliable, and gives you starting parameter values.

### Building a full track setup

```
atlas_chain_suggest(role="drums", genre="house")
→ Drum Rack (808 Core Kit), EQ Eight, Drum Buss

atlas_chain_suggest(role="bass", genre="house")
→ Analog, EQ Eight, Compressor, Saturator

atlas_chain_suggest(role="pad", genre="house")
→ Wavetable, Chorus-Ensemble, Reverb (send)
```

Load each chain in order using `find_and_load_device` for each device.

---

## What's Enriched

81 devices have deep sonic intelligence profiles:

| Category | Count | Examples |
|----------|-------|---------|
| Audio Effects | 35 | Compressor, Reverb, Echo, Saturator, EQ Eight, Auto Filter |
| Instruments | 16 | Drift, Analog, Wavetable, Operator, Simpler, Tension |
| MIDI Effects | 12 | Arpeggiator, Scale, Chord, Random |
| Utility | 8 | Utility, Vocoder, External Instrument |

Non-enriched devices (1224) still have name, URI, category, and basic parameter info — enough for search and loading.

---

## Tips

- **Always use atlas_suggest for new sounds.** It's the fastest path from musical intent to loaded device.
- **Use atlas_chain_suggest when building tracks from scratch.** It gives you instrument + effects in one call.
- **Run scan_full_library after installing packs.** The atlas only knows about devices it has scanned.
- **atlas_compare before A/B decisions.** "Should I use Drift or Wavetable for this pad?" — let the atlas answer.

---

Next: [Samples & Slicing](samples.md) | Back to [Manual](index.md)
