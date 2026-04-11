# Sample Engine Design Spec

**Date:** 2026-04-12  
**Status:** Draft  
**Author:** Claude + Silviu

## Problem

LivePilot has 12+ MCP tools for sample manipulation (Simpler loading, slicing, warping, warp markers) but no intelligence layer that ties them into creative workflows. A producer asking "find me a vocal and chop it into a rhythm" must manually orchestrate 8+ tool calls with no guidance on key matching, frequency fitness, or technique selection. Wonder Mode cannot suggest sample-based creative rescues. The gap: **tools exist, craft knowledge doesn't.**

## Goal

Build a Sample Engine — a new domain engine that makes LivePilot the most advanced AI sample manipulation system. It should:

1. **Discover** samples from Ableton's browser, local filesystem, and Freesound
2. **Analyze** material type, key, BPM, spectral character, and structural properties
3. **Critique** fitness against the current song (key, tempo, frequency, role, vibe, intent)
4. **Plan** the optimal technique and processing chain, with both surgeon (precise integration) and alchemist (creative transformation) approaches
5. **Execute** via compiled plans using existing MCP tools — no new Ableton communication
6. **Integrate with Wonder Mode** as first-class sample-domain variants with full preview support

## Non-Goals

- No new MCP tools that communicate with Ableton (reuse existing 12+)
- No new dependencies (Python stdlib + existing spectral tools)
- No Splice integration yet (architecture supports it, implementation deferred)
- No real-time audio processing (all manipulation via Ableton's engine)

## Architecture

### Directory Structure

```
mcp_server/sample_engine/
    __init__.py
    tools.py          # 6 MCP tool definitions (intelligence API)
    analyzer.py       # SampleAnalyzer — type detection, metadata, fitness
    critics.py        # SampleCritic — 6-critic battery
    planner.py        # SamplePlanner — technique selection + plan compilation
    sources.py        # SampleSource abstraction — browser, filesystem, Freesound
    models.py         # Data models (SampleProfile, SampleIntent, SampleFitReport, etc.)
    techniques.py     # Technique library — 30+ recipes indexed by intent + material
    moves.py          # 6 semantic moves for Wonder Mode registration

mcp_server/semantic_moves/
    sample_compilers.py   # Compilers for sample-domain semantic moves

livepilot/skills/livepilot-sample-engine/
    SKILL.md
    references/
        sample-techniques.md
        sample-critics.md
        sample-philosophy.md
```

### Three Layers

| Layer | Module | Role |
|-------|--------|------|
| Perception | `analyzer.py`, `sources.py` | Discover, fetch, classify, extract metadata |
| Intelligence | `critics.py`, `planner.py`, `techniques.py` | Score fitness, select technique, compile plan |
| Action | `tools.py`, `moves.py`, `sample_compilers.py` | MCP tools, Wonder Mode moves, compiled plans |

### Relationship to Existing Code

- **Uses:** `search_browser`, `load_browser_item`, `load_sample_to_simpler`, `replace_simpler_sample`, `set_simpler_playback_mode`, `get_simpler_slices`, `crop_simpler`, `reverse_simpler`, `warp_simpler`, `get/add/move/remove_warp_markers`, `get_clip_file_path`, `get_spectral_shape`, `get_mel_spectrum`, `get_chroma`, `get_onsets`, `add_notes`, `set_device_parameter`, `find_and_load_device`, `set_clip_warp_mode`
- **Extends:** `semantic_moves/registry.py` (new sample-family moves), `wonder_mode/engine.py` (sample domain in diagnosis), `stuckness_detector/detector.py` (sample opportunity patterns)
- **Follows pattern of:** `mix_engine/`, `sound_design/`, `creative_constraints/`

---

## Data Models

### SampleProfile

The complete fingerprint of a sample, built by the analyzer from all available signals.

```python
@dataclass
class SampleProfile:
    # Identity
    source: str                 # "browser", "filesystem", "freesound", "session_clip"
    file_path: str              # absolute path on disk
    name: str                   # human-readable name
    uri: str | None             # browser URI if from Ableton browser
    freesound_id: int | None    # Freesound ID if from online
    license: str | None         # license info for attribution

    # Musical properties
    key: str | None             # "Cm", "F#", None if unknown
    key_confidence: float       # 0.0-1.0
    bpm: float | None           # estimated BPM
    bpm_confidence: float       # 0.0-1.0
    time_signature: str         # "4/4" default

    # Material classification
    material_type: str          # "vocal", "drum_loop", "instrument_loop",
                                # "one_shot", "texture", "foley", "fx", "full_mix"
    material_confidence: float  # 0.0-1.0

    # Spectral fingerprint
    frequency_center: float     # Hz — energy centroid
    frequency_spread: float     # Hz — bandwidth
    brightness: float           # 0.0-1.0
    transient_density: float    # hits per beat

    # Structural
    duration_seconds: float
    duration_beats: float | None
    bar_count: float | None
    has_clear_downbeat: bool

    # Recommended handling
    suggested_mode: str         # "classic", "one_shot", "slice"
    suggested_slice_by: str     # "transient", "beat", "region", "manual"
    suggested_warp_mode: str    # "beats", "tones", "texture", "complex", "complex_pro"
```

### SampleIntent

What the user (or Wonder Mode) wants to do with a sample.

```python
@dataclass
class SampleIntent:
    intent_type: str            # "rhythm", "texture", "layer", "melody",
                                # "vocal", "atmosphere", "transform", "challenge"
    philosophy: str             # "surgeon", "alchemist", "auto" (context-decides)
    target_track: int | None    # specific track, or None for new track
    description: str            # free-text: "chop this into a rhythmic instrument"
```

### SampleFitReport

Output of the 6-critic battery — the intelligence verdict.

```python
@dataclass
class CriticResult:
    critic_name: str
    score: float                # 0.0-1.0
    rating: str                 # "excellent", "good", "fair", "poor"
    recommendation: str         # actionable text
    adjustments: list[dict]     # specific parameter changes needed

@dataclass
class SampleFitReport:
    sample: SampleProfile
    overall_score: float
    critics: dict[str, CriticResult]
    recommended_intent: str
    recommended_technique: str
    processing_chain: list[str]
    warnings: list[str]
    surgeon_plan: list[dict]    # precise integration compiled plan
    alchemist_plan: list[dict]  # creative transformation compiled plan
```

### SampleTechnique

A recipe from the technique library.

```python
@dataclass
class TechniqueStep:
    tool: str                   # MCP tool name
    params: dict                # tool parameters (some templated)
    description: str            # human-readable explanation
    condition: str | None       # optional guard: "if material_type == 'vocal'"

@dataclass
class SampleTechnique:
    technique_id: str
    name: str
    philosophy: str             # "surgeon", "alchemist", "both"
    material_types: list[str]
    intents: list[str]
    difficulty: str             # "basic", "intermediate", "advanced"
    description: str
    inspiration: str            # attribution to technique origin
    steps: list[TechniqueStep]
    success_signals: list[str]
    failure_signals: list[str]
```

---

## SampleAnalyzer — Perception

### Detection Pipeline

1. **Filename parsing** — Regex for common naming patterns:
   - `{name}_{key}_{bpm}bpm.{ext}`
   - `{bpm}_{key}_{name}.{ext}`
   - Splice-style: tags separated by underscores or hyphens
   - Extracts key, BPM, and material hints ("vocal", "kick", "pad", etc.)

2. **Spectral classification** — Using existing M4L bridge tools:
   - `get_spectral_shape` → frequency center, spread, brightness
   - `get_mel_spectrum` → mel band energy distribution
   - `get_onsets` → transient density, inter-onset intervals
   - Classification rules:
     - High transient density + sub-500Hz energy → drum_loop
     - 200-4000Hz energy + formant peaks → vocal
     - Narrow band + sustained → instrument_loop
     - Wide spread + low transients → texture
     - Duration < 0.5s → one_shot

3. **Key detection for audio** — `get_chroma` from M4L analyzer produces a 12-bin pitch-class histogram. Feed into the existing Krumhansl-Schmuckler algorithm from `_theory_engine.py`. This extends key detection from MIDI-only to audio samples.

4. **BPM estimation** — `get_onsets` returns transient positions. Compute inter-onset intervals (IOIs), build histogram, find mode cluster. Cross-reference with warp markers if available via `get_warp_markers`.

### Simpler Mode Decision Tree

```
duration < 0.5s OR material_type == "one_shot"  → Classic (one-shot)
material_type == "drum_loop"                      → Slice by Transient
material_type == "instrument_loop"                → Slice by Beat
material_type == "vocal"                          → Slice by Region
material_type == "texture" OR "foley"             → Classic (Texture warp)
material_type == "full_mix"                       → Slice by Beat
material_type == "fx"                             → Classic (one-shot)
```

---

## SampleCritic — Intelligence

Six critics, each a pure function returning `CriticResult`. Run as a battery.

### 1. Key Fit Critic

Compares `SampleProfile.key` against song key (from SongBrain or detected from MIDI tracks).

| Relationship | Score | Action |
|-------------|-------|--------|
| Same key | 1.0 | Load directly |
| Relative major/minor | 0.85 | Layer with care |
| Circle-of-fifths neighbor (4th/5th) | 0.7 | Works for most intents |
| Distantly related | 0.5 | Transpose or use as texture |
| Chromatic clash | 0.3 | Heavy filtering, or use intentionally as tension |
| Unknown key | 0.0 | Flag for ear verification |

Transpose recommendation: calculates semitone shift to nearest compatible key.

### 2. Tempo Fit Critic

Compares `SampleProfile.bpm` against session tempo.

| Relationship | Score | Action |
|-------------|-------|--------|
| Exact match (±1 BPM) | 1.0 | No warping needed |
| Half/double time | 0.9 | Set warp accordingly |
| Within ±5% | 0.7 | Light warp, preserve quality |
| ±5-15% | 0.4 | Moderate warp, choose mode carefully |
| >15% off | 0.2 | Extreme warp — use Texture mode for ambient, or don't use rhythmically |
| Unknown BPM | 0.0 | Estimate from onsets or flag |

### 3. Frequency Fit Critic

Uses `get_mix_snapshot` to map existing frequency occupation, then evaluates where the sample sits.

| Situation | Score | Action |
|-----------|-------|--------|
| Fills empty frequency gap | 1.0 | Perfect complement |
| Partial overlap, manageable | 0.7 | Suggest EQ carving |
| Heavy masking with existing tracks | 0.3 | Suggest aggressive filtering or textural use only |
| Full spectrum sample into dense mix | 0.1 | Use only as transformation source |

### 4. Role Fit Critic

Cross-references `material_type` against SongBrain's track role inventory.

| Situation | Score | Action |
|-----------|-------|--------|
| Fills missing role | 1.0 | "No percussion texture — this shaker fills the gap" |
| Complements existing | 0.7 | "Adds variety to existing drum palette" |
| Redundant role | 0.3 | "Already 3 synth layers — use as texture instead" |

### 5. Vibe Fit Critic (taste-aware)

Uses TasteGraph if evidence exists. Scores alignment between sample character and user's aesthetic preferences.

- High taste evidence: strong opinions from TasteGraph
- Low taste evidence: defaults to 0.5 (neutral)
- Considers brightness, density, complexity relative to taste profile

### 6. Intent Fit Critic

Evaluates how well the sample material serves the stated `SampleIntent`.

| Intent + Material | Score | Action |
|-------------------|-------|--------|
| "rhythm" + drum_loop | 1.0 | Natural fit |
| "rhythm" + vocal | 0.7 | "Slice by Region, staccato MIDI pattern" |
| "texture" + drum_loop | 0.6 | "Extreme stretch, Texture warp mode" |
| "layer" + instrument_loop | 0.9 | "Key-match, blend at -8dB" |

### Composite Scoring

```python
overall_score = (
    key_fit * 0.20 +
    tempo_fit * 0.20 +
    frequency_fit * 0.20 +
    role_fit * 0.15 +
    vibe_fit * 0.10 +
    intent_fit * 0.15
)
```

Weights shift based on intent — "texture" intent reduces key_fit and tempo_fit weights (pitch and tempo matter less for ambient use), increases frequency_fit.

---

## Sample Sources — Discovery

### Common Interface

```python
class SampleSource(ABC):
    @abstractmethod
    async def search(self, query: str, filters: dict) -> list[SampleCandidate]: ...

    @abstractmethod
    async def fetch(self, candidate: SampleCandidate) -> str:
        """Returns absolute file path, downloading if needed."""
        ...
```

### Browser Source

Wraps existing `search_browser` and `get_browser_items` tools. Searches across: samples, drums, sounds, packs, user_library, clips.

Smart query building from song context:
- SongBrain says "missing: rhythmic texture" → search "percussion", "shaker", "hihat loop"
- Intent is "vocal" → search "vocal", "vox", "voice" across samples and clips
- Key known → prefer results with key in filename

### Filesystem Source

Scans user-configured directories for audio files.

```python
@dataclass
class FilesystemSourceConfig:
    scan_paths: list[str]       # default: ["~/Music", "~/Documents/Samples"]
    index_on_startup: bool      # default: False (rebuild on demand)
    max_scan_depth: int         # default: 6
    extensions: set[str]        # {".wav", ".aif", ".aiff", ".mp3", ".flac", ".ogg"}
```

Filename metadata parser extracts key/BPM/type from naming conventions. Index cached at `~/Documents/LivePilot/sample_index.json`.

### Freesound Source

Uses Freesound API v2 (free key, 2000 req/day).

```python
@dataclass
class FreesoundSourceConfig:
    api_key: str | None         # from FREESOUND_API_KEY env var
    enabled: bool               # default: False
    download_dir: str           # ~/Documents/LivePilot/downloads/freesound/
    max_results: int            # default: 10
    license_filter: str         # "Attribution" or "Creative Commons 0"
```

Freesound provides AudioCommons descriptors (`ac_key`, `ac_tempo`, `ac_brightness`, `ac_depth`) — samples arrive pre-profiled. License info included in SampleFitReport.

### Discovery Orchestration

```
1. Build contextual queries from song state + user request
2. Search all enabled sources in parallel
3. Rank candidates by metadata fitness (pre-load scoring)
4. Present top 3-5 with reasons
5. User picks (or Wonder Mode auto-selects for preview)
6. Download if needed → load into Simpler → full SampleProfile
7. Run critic battery → SampleFitReport
8. Execute recommended plan
```

---

## Technique Library — Craft Knowledge

30+ techniques across 7 categories, each an executable recipe mapping to real MCP tools.

### Category 1: Rhythmic Sampling

| ID | Name | Philosophy | Material | Inspiration |
|----|------|------------|----------|-------------|
| `slice_and_sequence` | Slice & Sequence | surgeon | drum_loop | Classic MPC workflow |
| `vocal_chop_rhythm` | Vocal Chop Rhythm | alchemist | vocal | Burial's staccato vocal stabs |
| `micro_chop` | Micro-Chop | alchemist | any loop | J Dilla — 1/32 slices, disabled quantize |
| `stab_isolation` | Stab Isolation | surgeon | full_mix | DJ Premier — single chord stab |
| `euclidean_slice_trigger` | Euclidean Slice Trigger | alchemist | any | Slices mapped to Euclidean pattern |

### Category 2: Textural Transformation

| ID | Name | Philosophy | Material | Inspiration |
|----|------|------------|----------|-------------|
| `extreme_stretch` | Extreme Stretch | alchemist | any | Paulstretch via Texture warp 10x+ |
| `drum_to_pad` | Drum-to-Pad | alchemist | drum_loop, one_shot | Snare hit → ambient pad |
| `reverse_layer` | Reverse Layer | alchemist | any | Reversed pre-echo/swell |
| `granular_scatter` | Granular Scatter | alchemist | any | Grain Delay as granular engine |
| `spectral_freeze` | Spectral Freeze | alchemist | any | Capture one moment, sustain |
| `tail_harvest` | Tail Harvest | alchemist | any | Resample reverb/delay tail only |

### Category 3: Melodic/Harmonic

| ID | Name | Philosophy | Material | Inspiration |
|----|------|------------|----------|-------------|
| `key_matched_layer` | Key-Matched Layer | surgeon | instrument_loop | Transpose + filter to blend |
| `vocal_harmony_stack` | Vocal Harmony Stack | surgeon | vocal | Bon Iver pitch-shifted layers |
| `counterpoint_from_chops` | Counterpoint from Chops | alchemist | melodic | Four Tet found-sound melody |
| `chord_stab_extraction` | Chord Stab Extraction | surgeon | full_mix | Isolate + retrigger chords |

### Category 4: Drum Enhancement

| ID | Name | Philosophy | Material | Inspiration |
|----|------|------------|----------|-------------|
| `break_layering` | Break Layering | surgeon | drum_loop | Layer break under programmed drums |
| `ghost_note_texture` | Ghost Note Texture | alchemist | drum_loop | Quiet filtered loop under main beat |
| `transient_replacement` | Transient Replacement | surgeon | one_shot | Replace kick/snare transient |
| `shuffle_extract` | Shuffle Extract | alchemist | drum_loop | Extract groove, apply to MIDI |

### Category 5: Vocal Processing

| ID | Name | Philosophy | Material | Inspiration |
|----|------|------------|----------|-------------|
| `syllable_instrument` | Syllable Instrument | alchemist | vocal | Syllables played as instrument |
| `formant_shift_character` | Formant Shift Character | alchemist | vocal | Alien/robotic formant shifting |
| `vocal_freeze_drone` | Vocal Freeze Drone | alchemist | vocal | Sustain one vowel as pad |
| `phone_recording_texture` | Phone Recording Texture | alchemist | vocal, foley | Burial — lo-fi vocal ghosts |

### Category 6: Resampling Chains

| ID | Name | Philosophy | Material | Inspiration |
|----|------|------------|----------|-------------|
| `serial_resample` | Serial Resample | alchemist | any | Amon Tobin 5-pass chain |
| `parallel_resample` | Parallel Resample | alchemist | any | Wet/dry rack blend |
| `freeze_flatten_rechop` | Freeze-Flatten-Rechop | alchemist | any | Freeze → flatten → re-slice |

### Category 7: Creative Constraints

| ID | Name | Philosophy | Material | Inspiration |
|----|------|------------|----------|-------------|
| `one_sample_challenge` | One-Sample Challenge | alchemist | any | Entire beat from one sample |
| `found_sound_only` | Found Sound Only | alchemist | foley | Non-musical sources only |
| `reverse_engineering` | Reverse Engineering | both | full_mix | Recreate reference texture |

### Technique Selection

```python
technique_score = (
    material_match * 0.3 +
    intent_match * 0.3 +
    song_need_match * 0.2 +
    taste_fit * 0.1 +
    novelty_bonus * 0.1
)
```

---

## Wonder Mode Integration

### Stuckness Detector — Sample Patterns

New patterns added to `stuckness_detector/detector.py`:

| Pattern | Signal | Confidence |
|---------|--------|------------|
| `no_organic_texture` | All tracks are synthesized, no sampled content | 0.6 |
| `stale_drums` | Same drum pattern for 16+ bars, no variation | 0.5 |
| `vocal_processing_monotony` | Vocal track present, no processing variety | 0.4 |
| `dense_but_static` | Mix dense with sustained elements, low movement | 0.5 |

### Wonder Mode Diagnosis

`wonder_mode/diagnosis.py` gains `"sample"` as a candidate domain. When sample patterns are detected, diagnosis includes sample-specific context:

```python
{
    "candidate_domains": ["sample", "composition", "mix"],
    "sample_context": {
        "missing_roles": ["rhythmic_texture", "vocal_element"],
        "frequency_gaps": ["2-4kHz", "8-12kHz"],
        "suggested_material_types": ["vocal", "foley", "drum_loop"],
    }
}
```

### Semantic Moves

6 new moves registered in the semantic move registry:

| Move ID | Family | Risk | Intent |
|---------|--------|------|--------|
| `sample_chop_rhythm` | sample | medium | Chop sample into triggered rhythm |
| `sample_texture_layer` | sample | low | Stretch/transform into ambient layer |
| `sample_vocal_ghost` | sample | medium | Filtered, reversed vocal presence |
| `sample_break_layer` | sample | low | Drum break under existing percussion |
| `sample_resample_destroy` | sample | high | Destructive resample into new material |
| `sample_one_shot_accent` | sample | low | Single sample hit at key moments |

Each gets a compiler in `sample_compilers.py` that:
1. Reads session state via existing tools
2. Searches for appropriate sample material
3. Compiles a concrete tool-call sequence
4. Returns a previewable, committable plan

### Full Preview Support

Wonder Mode sample variants are fully executable:

```
enter_wonder_mode("I'm stuck, this track feels lifeless")
  → diagnosis: "no organic texture, stale drums"
  → Variant A (composition): add countermelody
  → Variant B (sample): "Chop a vocal from browser into rhythmic layer"
      compiled_plan:
        1. search_browser(path="samples", name_filter="vocal")
        2. load_sample_to_simpler(track_index=NEW, file_path=...)
        3. set_simpler_playback_mode(playback_mode=2, slice_by=2)  # Slice/Region
        4. get_simpler_slices(...)
        5. create_clip(...) + add_notes(...)  # MIDI triggering slices
        6. find_and_load_device("Auto Filter")  # processing
        7. set_device_parameter(...)  # filter settings
  → Variant C (mix): widen stereo field
```

The user can preview Variant B via `render_preview_variant`, hear it, then `commit_preview_variant` or `discard_wonder_session`.

---

## New MCP Tools

6 new tools — all intelligence-layer, no new Ableton communication.

### `analyze_sample`

Build a SampleProfile from a file path or clip reference.

**Parameters:**
- `file_path: str | None` — absolute path to audio file
- `track_index: int | None` — source clip's track (alternative to file_path)
- `clip_index: int | None` — source clip's slot

**Returns:** SampleProfile dict with all detected properties.

**Requires:** M4L Analyzer for spectral analysis. Falls back to filename-only analysis without it.

### `evaluate_sample_fit`

Run the 6-critic battery against the current song.

**Parameters:**
- `file_path: str` — path to the sample
- `intent: str` — "rhythm", "texture", "layer", "melody", "vocal", "atmosphere", "transform"
- `philosophy: str` — "surgeon", "alchemist", "auto"

**Returns:** SampleFitReport with scores, recommendations, surgeon plan, alchemist plan.

### `search_samples`

Unified search across all enabled sources.

**Parameters:**
- `query: str` — search text ("dark vocal", "breakbeat", "foley metal")
- `material_type: str | None` — filter by type
- `key: str | None` — prefer samples in this key
- `bpm_range: list[float] | None` — [min, max] BPM range
- `source: str | None` — "browser", "filesystem", "freesound", or None for all
- `max_results: int` — default 10

**Returns:** Ranked list of SampleCandidate dicts with metadata and source info.

### `suggest_sample_technique`

Recommend techniques from the library for a given sample + intent.

**Parameters:**
- `file_path: str` — path to the analyzed sample
- `intent: str` — what the user wants to do
- `philosophy: str` — "surgeon", "alchemist", "auto"
- `max_suggestions: int` — default 3

**Returns:** Ranked list of SampleTechnique summaries with executable step outlines.

### `plan_sample_workflow`

Full end-to-end plan: analyze + critique + technique + compiled tool sequence.

**Parameters:**
- `file_path: str | None` — path to sample (or search for one)
- `search_query: str | None` — find a sample matching this query
- `intent: str` — what to do with it
- `philosophy: str` — "surgeon", "alchemist", "auto"
- `target_track: int | None` — existing track or None for new

**Returns:** Complete workflow plan with compiled tool calls ready for execution.

### `get_sample_opportunities`

Analyze current song and identify where samples could improve it.

**Parameters:** None (reads session state)

**Returns:** List of opportunity dicts, each with:
- `opportunity_type`: "missing_role", "stale_element", "frequency_gap", "texture_need"
- `description`: human-readable explanation
- `suggested_material_types`: what kind of sample would help
- `suggested_techniques`: top technique matches
- `confidence`: 0.0-1.0

Used by Wonder Mode diagnosis and by the skill's "what should I sample?" workflow.

---

## Skill Structure

### SKILL.md Triggers

The skill triggers on: "sample", "chop", "slice", "loop", "break", "vocal chop", "resample", "found sound", "load a sample", "find me a sound", "texture from", "turn this into", "sample this", "flip this".

### Workflow Modes

**1. Direct Request** — User asks to do something specific with a sample:
```
User: "Chop this vocal into a rhythm"
→ analyze_sample → evaluate_sample_fit(intent="rhythm") → suggest_sample_technique
→ Execute recommended technique → evaluate result
```

**2. Discovery Mode** — User wants to find and use a sample:
```
User: "Find me a dark vocal sample for this track"
→ search_samples(query="dark vocal") → present candidates
→ User picks → analyze_sample → evaluate_sample_fit → plan_sample_workflow
→ Execute → evaluate
```

**3. Opportunity Mode** — Proactive suggestions:
```
Triggered by: get_sample_opportunities or Wonder Mode
→ "Your track has no organic textures — try a found-sound layer"
→ search_samples → analyze → critique → present options
```

**4. Wonder Mode** — Creative rescue with sample variants:
```
enter_wonder_mode → diagnosis finds sample opportunities
→ Compiled sample variant alongside other domains
→ Preview → commit or discard
```

### Philosophy Toggle

The `philosophy` field ("surgeon" / "alchemist" / "auto") flows through every layer:

- **Surgeon** emphasizes: key matching, tempo precision, clean EQ, seamless layering
- **Alchemist** emphasizes: creative destruction, unexpected transformations, happy accidents
- **Auto** (default) reads context:
  - Building a beat, need clean layers → surgeon
  - Stuck, need surprise → alchemist
  - User explicitly asked to "flip", "destroy", "mangle" → alchemist
  - User asked to "layer", "blend", "match" → surgeon

---

## Tool Count Impact

- Current: 294 tools
- New: 6 tools (analyze_sample, evaluate_sample_fit, search_samples, suggest_sample_technique, plan_sample_workflow, get_sample_opportunities)
- New total: **300 tools**

All locations requiring update per CLAUDE.md tool count rules.

---

## Implementation Order

1. **Models** (`models.py`) — data structures first
2. **Analyzer** (`analyzer.py`) — filename parsing + spectral classification
3. **Sources** (`sources.py`) — browser + filesystem + Freesound
4. **Critics** (`critics.py`) — 6-critic battery
5. **Techniques** (`techniques.py`) — technique catalog
6. **Planner** (`planner.py`) — technique selection + plan compilation
7. **Tools** (`tools.py`) — 6 MCP tools
8. **Semantic Moves** (`moves.py` + `sample_compilers.py`) — Wonder Mode integration
9. **Wonder Mode patches** — diagnosis + stuckness patterns
10. **Skill files** — SKILL.md + references
11. **Tests** — unit tests for analyzer, critics, planner, technique selection
12. **Tool count updates** — all locations per CLAUDE.md
