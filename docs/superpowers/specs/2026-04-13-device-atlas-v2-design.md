# Device Atlas v2 — Embedded Knowledge Database for LivePilot

**Date:** 2026-04-13
**Status:** Draft
**Author:** Claude + Silviu
**Target:** LivePilot v1.10.0

## Problem

LivePilot claims a "Device Atlas" with 280+ devices, but the actual implementation is scattered hand-written markdown files with parameter descriptions for ~12 instruments and ~30 effects. There is no structured, queryable database. The agent must either do a live browser search (slow, no sonic context) or rely on incomplete reference files that miss the majority of the library.

Ableton Live 12.3.6 Suite with 44 packs contains **far more** than what's documented:
- 32 instruments (6 new in 12.x: Emit, Poli, Tree Tone, Vector FM, Vector Grain, Drum Sampler)
- 70 audio effects (16+ new in 12.x including Roar, PitchLoop89, Vector Delay/Map, Spectral Blur, etc.)
- 23 MIDI effects (10+ new including Bouncy Notes, Melodic Steps, Rhythmic Steps, Step Arp, etc.)
- 469 Max for Live devices (287 audio FX, 93 instruments, 114 MIDI FX)
- 683 drum kit presets
- 141 AU/VST plugins
- 22,274 samples, 3,262 clips
- 44 content packs

The agent can't recommend devices it doesn't know exist, can't describe their character, and can't suggest appropriate combinations.

## Solution

An embedded JSON database (`mcp_server/atlas/device_atlas.json`) loaded at server startup, combining ground-truth scan data from the browser with hand-curated production intelligence. New MCP tools expose semantic search and suggestion capabilities.

## Architecture

```
mcp_server/atlas/
├── __init__.py              # AtlasManager — loads JSON, builds indexes, exposes query API
├── device_atlas.json        # The database (generated, committed)
├── scanner.py               # Runtime scanner — walks browser tree via Remote Script
├── enrichments/             # Hand-curated sonic knowledge per device (YAML)
│   ├── instruments/
│   │   ├── analog.yaml
│   │   ├── wavetable.yaml
│   │   ├── operator.yaml
│   │   ├── drift.yaml
│   │   ├── meld.yaml
│   │   ├── collision.yaml
│   │   ├── tension.yaml
│   │   ├── electric.yaml
│   │   ├── emit.yaml
│   │   ├── poli.yaml
│   │   ├── tree_tone.yaml
│   │   ├── vector_fm.yaml
│   │   ├── vector_grain.yaml
│   │   ├── simpler.yaml
│   │   ├── sampler.yaml
│   │   └── bass.yaml
│   ├── audio_effects/
│   │   ├── compressor.yaml
│   │   ├── eq_eight.yaml
│   │   ├── reverb.yaml
│   │   ├── delay.yaml
│   │   ├── saturator.yaml
│   │   ├── roar.yaml
│   │   ├── ... (one per stock effect)
│   │   └── _effects_index.yaml
│   ├── midi_effects/
│   │   ├── arpeggiator.yaml
│   │   ├── ... (one per stock MIDI effect)
│   │   └── _midi_index.yaml
│   └── max_for_live/
│       ├── lfo.yaml
│       ├── envelope_follower.yaml
│       ├── ... (key M4L devices)
│       └── _m4l_index.yaml
└── tools.py                 # MCP tools — atlas_search, atlas_suggest, etc.
```

### Data Flow

```
                    One-time scan
                    ┌─────────────┐
Ableton Browser ──► │  scanner.py  │ ──► raw_scan.json (all URIs, names, categories)
                    └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   merge()   │ ◄── enrichments/*.yaml (sonic descriptions, recipes)
                    └─────────────┘
                           │
                           ▼
                    ┌──────────────────┐
                    │ device_atlas.json │ ◄── committed to repo
                    └──────────────────┘
                           │
                    ┌──────┴──────┐
                    │ AtlasManager │ ◄── loaded at server startup
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        atlas_search  atlas_suggest  atlas_chain_suggest
```

## Database Schema

### Top-Level Structure

```json
{
  "version": "2.0.0",
  "live_version": "12.3.6",
  "scanned_at": "2026-04-13T12:00:00Z",
  "stats": {
    "total_devices": 1418,
    "instruments": 32,
    "audio_effects": 70,
    "midi_effects": 23,
    "max_for_live": 469,
    "drum_kits": 683,
    "plugins": 141,
    "packs": 44,
    "enriched_devices": 125
  },
  "devices": [ ... ],
  "packs": [ ... ]
}
```

### Device Entry (Enriched)

For stock devices with full production knowledge:

```json
{
  "id": "drift",
  "name": "Drift",
  "uri": "query:Synths#Drift",
  "category": "instruments",
  "subcategory": "synths",
  "source": "native",
  "enriched": true,
  "sonic_description": "Analog-modeled synth with built-in instability. Single oscillator with continuous shape morphing, resonant filter, and character-defining drift parameter. Warm, alive, imperfect — the opposite of digital sterility.",
  "synthesis_type": "analog_modeling",
  "character_tags": ["warm", "organic", "unstable", "intimate", "analog"],
  "use_cases": ["bass", "leads", "pads", "keys", "mono_lines"],
  "genre_affinity": {
    "primary": ["techno", "house", "ambient", "minimal", "lo-fi"],
    "secondary": ["synthwave", "downtempo", "experimental"]
  },
  "complexity": "beginner",
  "self_contained": true,
  "mcp_controllable": true,
  "key_parameters": [
    {
      "name": "Shape",
      "description": "Continuous oscillator shape morph — sine through triangle through saw through square",
      "range": [0.0, 1.0],
      "type": "float",
      "sweet_spots": {
        "sub_bass": 0.0,
        "warm_bass": 0.25,
        "bright_lead": 0.75,
        "hollow_pad": 0.5
      }
    },
    {
      "name": "Drift",
      "description": "Amount of analog-style pitch and filter instability",
      "range": [0.0, 1.0],
      "type": "float",
      "sweet_spots": {
        "clean": 0.0,
        "subtle_warmth": 0.15,
        "obvious_analog": 0.4,
        "broken_tape": 0.8
      }
    },
    {
      "name": "Filter Freq",
      "description": "Low-pass filter cutoff frequency",
      "range": [20, 20000],
      "unit": "Hz",
      "type": "float"
    },
    {
      "name": "Filter Res",
      "description": "Filter resonance — self-oscillates at high values",
      "range": [0.0, 1.0],
      "type": "float"
    },
    {
      "name": "Voice Mode",
      "description": "Mono, Poly, or Unison voicing",
      "options": ["Mono", "Poly", "Unison"]
    }
  ],
  "pairs_well_with": [
    {"device": "Chorus-Ensemble", "reason": "Adds width to mono patches"},
    {"device": "Saturator", "reason": "Drives the analog character further"},
    {"device": "Echo", "reason": "The modulated delay complements Drift's instability"},
    {"device": "Reverb", "reason": "Space for pads and ambient textures"}
  ],
  "starter_recipes": [
    {
      "name": "Deep Sub Bass",
      "description": "Warm sub bass for techno/house",
      "params": {"Shape": 0.0, "Drift": 0.1, "Filter Freq": 300, "Voice Mode": "Mono"},
      "genre": "techno"
    },
    {
      "name": "Drifting Pad",
      "description": "Evolving ambient pad with natural movement",
      "params": {"Shape": 0.5, "Drift": 0.35, "Filter Freq": 4000, "Voice Mode": "Poly", "Attack": 2.0, "Release": 4.0},
      "genre": "ambient"
    },
    {
      "name": "Wonky Lead",
      "description": "Unstable mono lead with character",
      "params": {"Shape": 0.7, "Drift": 0.5, "Filter Freq": 8000, "Filter Res": 0.3, "Voice Mode": "Mono"},
      "genre": "experimental"
    }
  ],
  "gotchas": [
    "High Drift values make pitch unpredictable — not suitable for precise melodic passages",
    "Unison mode is CPU-intensive with many voices"
  ],
  "health_flags": [],
  "introduced_in": "11.0"
}
```

### Device Entry (Scanned Only)

For non-enriched items (pack presets, M4L, plugins):

```json
{
  "id": "m4l_convolution_reverb_pro",
  "name": "Convolution Reverb Pro",
  "uri": "query:AudioFx#Convolution%20Reverb%20Pro",
  "category": "audio_effects",
  "subcategory": "reverb",
  "source": "native",
  "enriched": false,
  "character_tags": ["reverb", "convolution", "realistic", "spaces"],
  "self_contained": true,
  "mcp_controllable": true,
  "health_flags": []
}
```

### Drum Kit Entry

```json
{
  "id": "808_core_kit",
  "name": "808 Core Kit",
  "uri": "<scanned URI>",
  "category": "drum_kits",
  "subcategory": "electronic",
  "source": "core_library",
  "enriched": true,
  "character_tags": ["808", "electronic", "boomy", "classic", "hip-hop"],
  "genre_affinity": {"primary": ["hip-hop", "trap", "r&b"], "secondary": ["house", "techno"]},
  "pad_map_hint": "Standard GM-style: C1=kick, D1=snare, F#1=hi-hat",
  "pairs_well_with": ["Drum Buss", "Glue Compressor"],
  "health_flags": []
}
```

### Plugin Entry

```json
{
  "id": "auv3_moog_model_d",
  "name": "Model D",
  "uri": "query:Plugins#AUv3:Moog:Model%20D",
  "category": "plugins",
  "subcategory": "instruments",
  "source": "auv3",
  "vendor": "Moog",
  "plugin_format": "AUv3",
  "enriched": false,
  "self_contained": true,
  "mcp_controllable": false,
  "health_flags": ["external_plugin"],
  "gotchas": ["AU/VST plugin — parameter visibility depends on host integration. Check parameter_count after loading."]
}
```

### Pack Entry

```json
{
  "id": "pack_drone_lab",
  "name": "Drone Lab",
  "description": "Evolving drones and atmospheric textures built with Drift and Wavetable",
  "device_count": 0,
  "preset_count": 0,
  "sample_count": 0,
  "genre_affinity": ["ambient", "experimental", "cinematic"]
}
```

## New MCP Tools (6 tools)

### 1. `atlas_search(query, category?, limit?)`

Fuzzy search across all indexed devices by name, sonic description, character tags, use cases, or genre. Returns ranked matches with relevance scores.

```python
@mcp.tool()
def atlas_search(ctx: Context, query: str, category: str = "all", limit: int = 10) -> dict:
    """Search the device atlas for instruments, effects, kits, or plugins.

    query:    natural language search — name, sonic character, use case, or genre
              Examples: "warm analog bass", "reverb", "808 kit", "granular"
    category: filter by category (all, instruments, audio_effects, midi_effects,
              max_for_live, drum_kits, plugins)
    limit:    max results (default 10)
    """
```

**Search strategy:**
1. Exact name match (highest score)
2. Name substring match
3. Character tag match
4. Sonic description keyword match
5. Use case / genre match
6. Fuzzy name match (Levenshtein)

### 2. `atlas_device_info(device_id)`

Returns the full atlas entry for a single device — all parameters, recipes, gotchas, pairings.

```python
@mcp.tool()
def atlas_device_info(ctx: Context, device_id: str) -> dict:
    """Get complete atlas knowledge about a device — parameters, recipes, pairings, gotchas.

    device_id: the atlas ID (e.g., "drift", "compressor", "808_core_kit")
    """
```

### 3. `atlas_suggest(intent, genre?, energy?, key?)`

Intent-driven device recommendation. "I need a warm pad for ambient" returns top device+recipe combos with rationale.

```python
@mcp.tool()
def atlas_suggest(
    ctx: Context,
    intent: str,
    genre: str = "",
    energy: str = "medium",
    key: str = "",
) -> dict:
    """Suggest devices for a production intent.

    intent: what you're trying to achieve — "warm bass", "crispy hi-hats", "evolving texture",
            "punchy kick", "ethereal pad", "aggressive lead"
    genre:  target genre for better recommendations
    energy: low/medium/high — affects sonic character suggestions
    key:    musical key context (e.g., "Cm", "F#m") for tuned percussion suggestions
    """
```

### 4. `atlas_chain_suggest(role, genre?)`

Suggests a complete device chain (instrument + MIDI effects + audio effects) for a given role.

```python
@mcp.tool()
def atlas_chain_suggest(ctx: Context, role: str, genre: str = "") -> dict:
    """Suggest a full device chain for a track role.

    role:  the musical role — "bass", "lead", "pad", "drums", "percussion", "texture",
           "vocal_processing", "master_bus"
    genre: target genre for style-appropriate choices
    """
```

Returns ordered chain with rationale:
```json
{
  "role": "bass",
  "genre": "dub_techno",
  "chain": [
    {"position": "midi_effect", "device": "Note Length", "reason": "Ensures consistent note lengths for rhythmic bass"},
    {"position": "instrument", "device": "Drift", "recipe": "Deep Sub Bass", "reason": "Warm analog character with natural drift"},
    {"position": "effect_1", "device": "Saturator", "reason": "Adds harmonics for speaker presence"},
    {"position": "effect_2", "device": "Compressor", "reason": "Tames dynamics for consistent low end"},
    {"position": "effect_3", "device": "EQ Eight", "reason": "High-pass at 30Hz, notch mud at 200Hz"}
  ]
}
```

### 5. `atlas_compare(device_a, device_b, role?)`

Side-by-side comparison of two devices for a given purpose.

```python
@mcp.tool()
def atlas_compare(ctx: Context, device_a: str, device_b: str, role: str = "") -> dict:
    """Compare two devices — strengths, weaknesses, and recommendation for a role.

    device_a: first device name or ID
    device_b: second device name or ID
    role:     optional role context (e.g., "bass", "pad") to focus the comparison
    """
```

### 6. `scan_full_library(force?)`

One-time deep scan of the Ableton browser. Writes results to `device_atlas.json`.

```python
@mcp.tool()
def scan_full_library(ctx: Context, force: bool = False) -> dict:
    """Scan the full Ableton browser and rebuild the device atlas.

    This walks every category (instruments, audio_effects, midi_effects, max_for_live,
    drums, plugins, packs) and records every loadable item with its URI.
    Results are merged with curated enrichments and saved to device_atlas.json.

    force: if True, rescan even if atlas exists. Default False (skip if recent).
    """
```

## Integration Points

### Enhanced `find_and_load_device`

Current implementation does a live browser search every time. With the atlas:

```python
# Before (slow, no intelligence):
result = send_command("search_browser", {"path": "instruments", "name_filter": name})

# After (instant, with context):
atlas_entry = atlas_manager.lookup(name)
if atlas_entry:
    # Use cached URI — no browser search needed
    uri = atlas_entry["uri"]
    # Return enriched result with sonic context
    return {"uri": uri, "atlas": atlas_entry}
```

### Skill Updates

The `livepilot-devices` skill will reference atlas tools:

```
## Primary Workflow — Atlas-Driven

1. **Intent:** What sonic role do you need? → `atlas_suggest(intent, genre)`
2. **Choose:** Review suggestions, pick one → `atlas_device_info(device_id)` for details
3. **Load:** Use the URI from the atlas → `load_browser_item(uri)` or `find_and_load_device(name)`
4. **Recipe:** Apply a starter recipe → `batch_set_parameters(params)` from the atlas entry
5. **Verify:** `get_device_info(track_index, device_index)` — check health flags
```

### Sound Design Integration

The sound design engine can pull parameter sweet spots:
```python
atlas_entry = atlas_manager.get("drift")
recipe = atlas_entry["starter_recipes"][0]  # "Deep Sub Bass"
# Apply recipe params as starting point, then refine
```

### Project Brain Integration

When building the project brain, device atlas entries annotate tracks:
```python
# Track 1: "Drift" loaded
# Project brain knows: synthesis_type=analog_modeling, genre_affinity=techno, character=warm
```

## Enrichment Scope

### Tier 1 — Deep (every parameter, recipes, pairings, gotchas)

**Instruments (16):** Analog, Wavetable, Operator, Drift, Meld, Collision, Tension, Electric, Simpler, Sampler, Emit, Poli, Tree Tone, Vector FM, Vector Grain, Bass

**Audio Effects (35):** Compressor, Glue Compressor, Limiter, Color Limiter, Multiband Dynamics, Gate, Drum Buss, EQ Eight, EQ Three, Channel EQ, Auto Filter, Spectral Resonator, Delay, Echo, Grain Delay, Filter Delay, Gated Delay, Vector Delay, Beat Repeat, Spectral Time, Reverb, Hybrid Reverb, Convolution Reverb, Convolution Reverb Pro, Saturator, Overdrive, Pedal, Roar, Dynamic Tube, Erosion, Redux, Vinyl Distortion, Chorus-Ensemble, Phaser-Flanger, Shifter

**MIDI Effects (12):** Arpeggiator, Chord, Scale, Random, Note Echo, Note Length, Pitch, Velocity, Bouncy Notes, Melodic Steps, Rhythmic Steps, Step Arp

**Utility/Analysis (8):** Utility, Spectrum, Tuner, Amp, Cabinet, Corpus, Resonators, Vocoder

### Tier 2 — Medium (sonic description, use cases, character tags, genre)

**Audio Effects (16):** Spectral Blur, PitchLoop89, Pitch Hack, Auto Pan-Tremolo, Auto Shift, Shaper, Re-Enveloper, Variations, Vector Map, Arrangement Looper, Prearranger, Performer, Looper, LFO, Envelope Follower, Surround Panner

**MIDI Effects (11):** Expressive Chords, CC Control, Envelope MIDI, Expression Control, Melodic Steps, Microtuner, MIDI Monitor, MPE Control, Rotating Rhythm Generator, SQ Sequencer, Shaper MIDI

**Drum Kits (top 50):** Core kits (606, 707, 808, 909), Session Drums kits, Beat Tools kits, pack-specific kits — tagged with genre and character

**Max for Live (top 30):** Key stock M4L devices — Convolution Reverb Pro, Granulator III, LFO, Envelope Follower, Shaper, etc.

### Tier 3 — Light (name, URI, category, source, basic tags)

Everything else — remaining M4L devices, all plugins, remaining drum kits, pack presets. Indexed for searchability with auto-generated tags from name parsing.

## Enrichment YAML Format

Each enrichment file follows this structure:

```yaml
# enrichments/instruments/drift.yaml
id: drift
name: Drift
sonic_description: >
  Analog-modeled synth with built-in instability. Single oscillator with
  continuous shape morphing, resonant filter, and character-defining drift
  parameter. Warm, alive, imperfect.
synthesis_type: analog_modeling
character_tags: [warm, organic, unstable, intimate, analog]
use_cases: [bass, leads, pads, keys, mono_lines]
genre_affinity:
  primary: [techno, house, ambient, minimal, lo-fi]
  secondary: [synthwave, downtempo, experimental]
complexity: beginner
self_contained: true
introduced_in: "11.0"

key_parameters:
  - name: Shape
    description: Continuous oscillator shape morph
    range: [0.0, 1.0]
    type: float
    sweet_spots:
      sub_bass: 0.0
      warm_bass: 0.25
      bright_lead: 0.75

  - name: Drift
    description: Amount of analog-style pitch and filter instability
    range: [0.0, 1.0]
    type: float
    sweet_spots:
      clean: 0.0
      subtle_warmth: 0.15
      obvious_analog: 0.4

  - name: Filter Freq
    description: Low-pass filter cutoff frequency
    range: [20, 20000]
    unit: Hz
    type: float

pairs_well_with:
  - device: Chorus-Ensemble
    reason: Adds width to mono patches
  - device: Saturator
    reason: Drives the analog character further

starter_recipes:
  - name: Deep Sub Bass
    description: Warm sub bass for techno/house
    genre: techno
    params:
      Shape: 0.0
      Drift: 0.1
      Filter Freq: 300
      Voice Mode: Mono

  - name: Drifting Pad
    description: Evolving ambient pad with natural movement
    genre: ambient
    params:
      Shape: 0.5
      Drift: 0.35
      Filter Freq: 4000
      Voice Mode: Poly
      Attack: 2.0
      Release: 4.0

gotchas:
  - High Drift values make pitch unpredictable for precise melodies
  - Unison mode is CPU-intensive with many voices
```

## AtlasManager API

```python
class AtlasManager:
    """In-memory device atlas with indexed lookups."""

    def __init__(self, atlas_path: str):
        self.data = json.load(open(atlas_path))
        self._build_indexes()

    def _build_indexes(self):
        """Build name, category, tag, and genre indexes for fast lookup."""
        self.by_id: dict[str, dict] = {}
        self.by_name: dict[str, list[dict]] = {}       # name -> [entries] (case-insensitive)
        self.by_category: dict[str, list[dict]] = {}
        self.by_tag: dict[str, list[dict]] = {}
        self.by_genre: dict[str, list[dict]] = {}
        self.by_uri: dict[str, dict] = {}

    def lookup(self, name: str) -> dict | None:
        """Exact or fuzzy name lookup. Returns best match or None."""

    def search(self, query: str, category: str = "all", limit: int = 10) -> list[dict]:
        """Multi-signal search: name, tags, description, genre."""

    def suggest(self, intent: str, genre: str = "", energy: str = "medium") -> list[dict]:
        """Intent-driven suggestion with ranked results."""

    def chain_suggest(self, role: str, genre: str = "") -> dict:
        """Full device chain recommendation for a track role."""

    def compare(self, device_a: str, device_b: str, role: str = "") -> dict:
        """Side-by-side comparison of two devices."""

    @property
    def stats(self) -> dict:
        """Atlas statistics."""
```

## Remote Script Changes

### New Command: `scan_browser_deep`

Added to `remote_script/LivePilot/browser.py`:

```python
def _handle_scan_browser_deep(self, params):
    """Walk the entire browser tree and return all loadable items.

    Returns a flat list of {name, uri, category, is_loadable, parent_path}
    for every item in the browser. Used by atlas scanner.
    """
    categories = [
        ("instruments", self.song().browser.instruments),
        ("audio_effects", self.song().browser.audio_effects),
        ("midi_effects", self.song().browser.midi_effects),
        ("drums", self.song().browser.drums),
        ("max_for_live", self.song().browser.max_for_live),
        ("plugins", self.song().browser.plugins),
        ("packs", self.song().browser.packs),
        ("sounds", self.song().browser.sounds),
    ]
    # Recursive walk with depth limit, returns flat list
```

This is a long-running command (~5-30 seconds depending on library size). The MCP tool will set an appropriate timeout.

## Implementation Phases

### Phase 1 — Scanner + Raw Atlas (new files, no existing code changes)
1. `mcp_server/atlas/__init__.py` — AtlasManager class
2. `mcp_server/atlas/scanner.py` — Browser scanner logic
3. `remote_script/LivePilot/browser.py` — Add `scan_browser_deep` command
4. `mcp_server/atlas/tools.py` — `scan_full_library` tool only
5. Run initial scan → generate `device_atlas.json`

### Phase 2 — Enrichment Layer (new files only)
1. Create `mcp_server/atlas/enrichments/` directory structure
2. Write YAML enrichments for Tier 1 instruments (16 files)
3. Write YAML enrichments for Tier 1 audio effects (35 files)
4. Write YAML enrichments for Tier 1 MIDI effects (12 files)
5. Write YAML enrichments for Tier 1 utility devices (8 files)
6. Merge enrichments into atlas JSON

### Phase 3 — Query Tools (new tools, minor integration)
1. `atlas_search` tool
2. `atlas_device_info` tool
3. `atlas_suggest` tool
4. `atlas_chain_suggest` tool
5. `atlas_compare` tool
6. Register all tools in server.py

### Phase 4 — Integration (modify existing code)
1. Enhance `find_and_load_device` to consult atlas
2. Update `livepilot-devices` skill to reference atlas
3. Update `livepilot-core/references/overview.md` with real device counts
4. Update `livepilot-core/references/sound-design.md` with atlas-backed data
5. Update `livepilot-core/references/m4l-devices.md`
6. Wire atlas into sound_design engine
7. Wire atlas into project_brain

### Phase 5 — Tier 2/3 Enrichments + Polish
1. Write Tier 2 enrichments (remaining effects, MIDI effects, key M4L, top 50 kits)
2. Auto-tag Tier 3 items from name parsing
3. Update tool count (307 + 6 = 313)
4. Update all version/count references per CLAUDE.md checklist
5. Tests for AtlasManager, scanner, and all query tools

## Success Criteria

1. `atlas_search("warm pad")` returns Drift, Wavetable, Analog with sonic descriptions and recipes
2. `atlas_suggest("bass", genre="dub_techno")` returns a ranked list with Drift recipe + effect chain
3. `atlas_chain_suggest("drums", genre="trap")` returns instrument + effects with rationale
4. `atlas_device_info("operator")` returns every parameter, 3+ recipes, gotchas, pairings
5. `scan_full_library()` discovers all 1400+ devices and writes valid atlas JSON
6. `find_and_load_device` resolves from atlas cache without hitting browser (when atlas has the device)
7. All 32 instruments, 70 effects, 23 MIDI effects are in the atlas with correct URIs
8. Atlas loads in <100ms at server startup

## Non-Goals

- Real-time parameter discovery (we use curated data, not live introspection for sound descriptions)
- Sample indexing (22K samples stay browser-searchable, not in the atlas)
- Clip indexing (3K clips stay browser-searchable)
- Plugin parameter mapping (plugins are indexed for discoverability, not deep control)
- AI-generated sonic descriptions (all descriptions are hand-curated for accuracy)

## Dependencies

- Ableton Live 12.3.6 running for initial scan
- PyYAML for enrichment parsing (already in deps)
- No new external dependencies required

## Risks

- **Browser API stability**: The `browser.instruments` etc. properties are stable across Live 12.x but could change in a major version
- **URI format changes**: Device URIs (`query:Synths#...`) could change between Live versions — the scan anchors us to current reality
- **Atlas staleness**: If user installs new packs, atlas needs a rescan — `scan_full_library(force=True)` handles this
- **M4L device count**: 469 M4L devices may include tutorial patches and non-production items — Tier 3 tagging handles this via name pattern analysis
