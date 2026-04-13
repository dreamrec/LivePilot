# SpliceAgent + Composer Mode Design Spec

**Date:** 2026-04-13
**Status:** Draft
**Author:** Claude + Silviu

## Problem

LivePilot's Sample Engine has intelligence (critics, techniques, planning) but cannot autonomously find and acquire samples. The user must manually download samples from Splice before the engine can use them. Wonder Mode can suggest sample-based creative rescues but cannot execute them end-to-end. There is no way to go from a text prompt ("dark minimal techno with ghostly vocals") to a multi-layered composition automatically.

## Goal

1. **SpliceAgent** — Connect to Splice's local gRPC API to search the full 4M+ sample catalog, download samples on demand, and manage collections. LivePilot becomes the first AI that can autonomously acquire professional samples.

2. **Composer Mode** — An auto-composition engine that turns a text prompt into a multi-layered Ableton session. Uses SpliceAgent + Sample Engine + all existing LivePilot tools. Two modes: full composition from scratch, or intelligent augmentation of existing tracks.

## Non-Goals

- No scraping of Splice web UI (we use their official local gRPC API)
- No circumventing Splice's credit system (downloads cost credits as designed)
- No audio generation (we compose with real professional samples, not AI-generated audio)
- No MIDI generation from scratch (we use sample slicing + existing generative tools)

---

## Architecture

### New Modules

```
mcp_server/
├── splice_client/              # Splice gRPC client
│   ├── __init__.py
│   ├── client.py               # SpliceGRPCClient — connect, search, download, wait
│   ├── models.py               # SpliceSample, SpliceSearchRequest, SpliceSearchResult
│   └── protos/                 # Generated Python stubs
│       ├── app_pb2.py          # Message classes from app.proto
│       ├── app_pb2_grpc.py     # Service stubs from app.proto
│       └── __init__.py
│
├── composer/                   # Auto-composition engine
│   ├── __init__.py
│   ├── tools.py                # 3 MCP tools: compose, augment_with_samples, get_composition_plan
│   ├── engine.py               # ComposerEngine — prompt → layers → execution
│   ├── layer_planner.py        # Intent → layer specifications
│   ├── prompt_parser.py        # Natural language → structured CompositionIntent
│   └── executor.py             # Executes layer plans via existing MCP tools
│
├── sample_engine/              # EXISTING — enhanced
│   ├── sources.py              # SpliceSource gains splice_live search via gRPC
│   └── tools.py                # search_samples gains splice_live source
```

### Relationship to Existing Code

- **SpliceAgent uses:** Splice gRPC `App` service (SearchSamples, DownloadSample, SampleInfo, StreamEvents)
- **Composer uses:** All sample_engine tools + SpliceAgent + existing LivePilot tools (create_midi_track, load_sample_to_simpler, set_simpler_playback_mode, add_notes, insert_device, set_device_parameter, set_track_volume, set_track_pan, create_arrangement_clip, set_arrangement_automation, plan_arrangement)
- **Wonder Mode enhanced:** Sample-domain variants now auto-search and auto-download via SpliceAgent

---

## Module 1: SpliceGRPCClient

### Connection

```python
class SpliceGRPCClient:
    """Connect to Splice desktop's local gRPC server."""

    def __init__(self):
        self.channel = None
        self.stub = None
        self.connected = False

    async def connect(self) -> bool:
        """Auto-discover port from port.conf, load TLS certs, connect."""
        port = self._read_port()        # from port.conf
        cert = self._read_cert()        # from .certs/cert.pem
        key = self._read_key()          # from .certs/key.pem
        # Create TLS channel to localhost
        credentials = grpc.ssl_channel_credentials(root_certificates=cert)
        self.channel = grpc.aio.secure_channel(f"127.0.0.1:{port}", credentials)
        self.stub = app_pb2_grpc.AppStub(self.channel)
        self.connected = True
```

Port: dynamic, read from `~/Library/Application Support/com.splice.Splice/port.conf`
TLS: self-signed cert at `~/.../com.splice.Splice/.certs/cert.pem`

### Key RPCs

**SearchSamples** — The core power. Searches Splice's full catalog.

```python
async def search_samples(
    self,
    query: str = "",
    key: str = "",           # "c#", "a", "f" (lowercase)
    chord_type: str = "",    # "major", "minor"
    bpm_min: int = 0,
    bpm_max: int = 0,
    tags: list[str] = None,
    genre: str = "",
    sample_type: str = "",   # "loop" or "oneshot"
    sort: str = "relevance", # "relevance", "popular", "newest"
    per_page: int = 20,
    page: int = 1,
    purchased_only: bool = False,
) -> SpliceSearchResult:
    """Search Splice catalog. Returns samples with full metadata."""
    request = SearchSampleRequest(
        SearchTerm=query,
        Key=key,
        ChordType=chord_type,
        BPMMin=bpm_min,
        BPMMax=bpm_max,
        Tags=tags or [],
        Genre=genre,
        SampleType=sample_type,
        SortFn=sort,
        PerPage=per_page,
        Page=page,
        Purchased=1 if purchased_only else 0,
    )
    response = await self.stub.SearchSamples(request)
    return SpliceSearchResult.from_proto(response)
```

**DownloadSample** — Downloads a sample using credits.

```python
async def download_sample(self, file_hash: str) -> str:
    """Download a sample by file_hash. Returns local file path when complete."""
    await self.stub.DownloadSample(DownloadSampleRequest(FileHash=file_hash))
    # Wait for download to complete by polling SampleInfo
    return await self._wait_for_download(file_hash, timeout=30)

async def _wait_for_download(self, file_hash: str, timeout: float) -> str:
    """Poll SampleInfo until LocalPath is populated."""
    import asyncio
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        info = await self.stub.SampleInfo(SampleInfoRequest(FileHash=file_hash))
        if info.Sample.LocalPath:
            return info.Sample.LocalPath
        await asyncio.sleep(0.5)
    raise TimeoutError(f"Download timed out for {file_hash}")
```

**SampleInfo** — Get metadata for a specific sample.

**GetSession** — Check auth status and credit balance.

### Credit Safety

```python
async def get_credits_remaining(self) -> int:
    """Read credits from Splice session."""
    session = await self.stub.ValidateLogin(ValidateLoginRequest())
    return session.User.Credits

def check_credit_budget(self, needed: int, budget: int) -> bool:
    """Verify we have enough credits within the budget limit."""
    return needed <= budget
```

### Graceful Degradation

If Splice is not running, port.conf doesn't exist, or grpcio is not installed:
- `SpliceGRPCClient.connect()` returns `False`
- All search/download methods return empty results
- System falls back to existing sources (SQLite DB, browser, filesystem)

---

## Module 2: Enhanced Sample Engine

### New source: splice_live

```python
# In sources.py — SpliceSource gains a live_client parameter
class SpliceSource:
    def __init__(self, db_path=None, live_client=None):
        self.live_client = live_client  # SpliceGRPCClient instance
        # ... existing DB logic ...

    async def search_live(self, query, key=None, bpm_min=None, bpm_max=None,
                          genre=None, sample_type=None, max_results=20):
        """Search full Splice catalog via gRPC (not just downloaded samples)."""
        if not self.live_client or not self.live_client.connected:
            return []
        result = await self.live_client.search_samples(
            query=query, key=key, bpm_min=bpm_min, bpm_max=bpm_max,
            genre=genre, sample_type=sample_type, per_page=max_results,
        )
        return [self._proto_to_candidate(s) for s in result.samples]
```

### Updated search_samples tool — source priority

```
1. splice_live  — gRPC: full Splice catalog (4M+ samples, requires Splice running)
2. splice_db    — SQLite: downloaded samples only (always available if Splice installed)
3. browser      — Ableton's built-in browser (samples, drums, packs, user_library)
4. filesystem   — Local directory scan
```

Results from `splice_live` include `"downloadable": true` when not yet on disk. The `file_hash` field enables subsequent download.

---

## Module 3: Composer Engine

### Prompt Parser

Converts natural language to structured intent:

```python
@dataclass
class CompositionIntent:
    genre: str = ""              # "techno", "house", "hip hop", "ambient"
    sub_genre: str = ""          # "minimal", "deep", "lo-fi"
    mood: str = ""               # "dark", "euphoric", "melancholic", "aggressive"
    tempo: int = 0               # 0 = auto-detect from genre
    key: str = ""                # "" = auto-pick based on mood
    descriptors: list[str] = []  # ["industrial", "ghostly", "warm"]
    explicit_elements: list[str] = []  # ["vocals", "strings", "808"]
    energy: float = 0.5          # 0.0-1.0, derived from mood
    layer_count: int = 0         # 0 = auto (genre determines)
    duration_bars: int = 64      # total arrangement length
```

**Genre → tempo/key/energy mapping:**

| Genre | Default Tempo | Default Key | Energy | Typical Layers |
|-------|---------------|-------------|--------|----------------|
| techno | 128 | Am/Cm | 0.7 | 5-7 |
| house | 124 | Cm/Fm | 0.6 | 5-6 |
| hip hop | 90 | Cm/Gm | 0.5 | 4-6 |
| ambient | 80 | C/Am | 0.2 | 3-5 |
| drum and bass | 174 | Am/Em | 0.8 | 5-7 |
| trap | 140 | Cm/Bbm | 0.6 | 4-6 |
| lo-fi | 85 | Fm/Cm | 0.3 | 3-5 |

**Mood → key preference + energy:**

| Mood | Key Bias | Energy |
|------|----------|--------|
| dark | minor keys | 0.4-0.6 |
| euphoric | major keys | 0.8-1.0 |
| melancholic | minor keys, Fm/Cm | 0.2-0.4 |
| aggressive | minor keys, Am/Em | 0.8-0.9 |
| dreamy | major 7ths, Cmaj/Fmaj | 0.2-0.3 |

### Layer Planner

Each composition is a set of **layers**, each with a role and source specification:

```python
@dataclass
class LayerSpec:
    role: str               # "drums", "bass", "lead", "pad", "texture", "vocal", "fx", "percussion"
    search_query: str       # Splice search query
    splice_filters: dict    # key, bpm_range, genre, tags, sample_type
    technique_id: str       # from the 29-recipe library
    processing: list[dict]  # devices to add + parameter targets
    volume_db: float        # mix level
    pan: float              # -1.0 to 1.0
    sections: list[str]     # which arrangement sections ("intro", "drop", "breakdown")
    priority: int           # download order (drums first, fx last)
```

**Role → layer template mapping:**

| Role | Splice Search | Type | Technique | Processing | Volume |
|------|---------------|------|-----------|------------|--------|
| drums | "{genre} drums {tempo}bpm" | loop | slice_and_sequence | EQ, Compressor | -3dB |
| bass | "{genre} bass {key} oneshot" | oneshot | key_matched_layer | Saturator, EQ HP | -5dB |
| lead | "{genre} {mood} melody {key}" | loop | counterpoint_from_chops | Auto Filter, Delay | -6dB |
| pad | "{mood} pad {key}" | loop | extreme_stretch | Reverb, Chorus | -10dB |
| texture | "{mood} texture ambient" | loop | granular_scatter | Grain Delay, Reverb | -15dB |
| vocal | "vocal {mood} {key}" | loop | vocal_chop_rhythm | Auto Filter, Reverb | -8dB |
| percussion | "{genre} percussion loop" | loop | ghost_note_texture | EQ HP, Compressor | -12dB |
| fx | "{genre} riser fx" | oneshot | one_shot_accent | — | -6dB |

### Executor

The executor walks the layer plan and calls existing MCP tools:

```python
async def execute_layer(self, spec: LayerSpec, track_index: int, ctx: Context):
    """Execute a single layer: search → download → load → process → arrange."""

    # 1. Search Splice for the best sample
    results = await splice_client.search_samples(
        query=spec.search_query,
        **spec.splice_filters,
        per_page=10,
    )
    if not results.samples:
        # Fallback to browser
        results = search_browser(spec.search_query)

    # 2. Score candidates with SampleCritic
    scored = []
    for sample in results.samples:
        profile = build_profile_from_splice(sample)
        critics = run_all_sample_critics(profile, intent, song_key, tempo)
        scored.append((sample, profile, critics))
    scored.sort(key=lambda x: -x[2].overall_score)
    best = scored[0]

    # 3. Download if needed
    if not best.sample.LocalPath:
        file_path = await splice_client.download_sample(best.sample.FileHash)
    else:
        file_path = best.sample.LocalPath

    # 4. Load into Ableton
    load_sample_to_simpler(track_index, file_path)

    # 5. Apply technique
    technique = get_technique(spec.technique_id)
    for step in technique.steps:
        execute_tool(step.tool, resolve_params(step.params, ...))

    # 6. Add processing chain
    for device in spec.processing:
        insert_device(track_index, device["name"])
        for param, value in device.get("params", {}).items():
            set_device_parameter(track_index, ...)

    # 7. Set mix levels
    set_track_volume(track_index, spec.volume_db)
    set_track_pan(track_index, spec.pan)
    set_track_name(track_index, f"{spec.role}: {best.sample.Filename}")
```

### Section Arrangement (compose mode)

For full compositions, the engine plans sections:

```python
SECTION_TEMPLATES = {
    "techno": [
        {"name": "Intro",     "bars": 8,  "layers": ["drums:-6dB", "texture"]},
        {"name": "Build",     "bars": 8,  "layers": ["drums", "bass", "percussion"]},
        {"name": "Drop",      "bars": 16, "layers": ["drums", "bass", "lead", "percussion", "texture"]},
        {"name": "Breakdown", "bars": 8,  "layers": ["texture", "vocal", "pad"]},
        {"name": "Drop 2",   "bars": 16, "layers": ["drums", "bass", "lead", "percussion", "vocal", "texture"]},
        {"name": "Outro",     "bars": 8,  "layers": ["drums:-6dB", "texture", "pad"]},
    ],
    "hip hop": [
        {"name": "Intro",  "bars": 4,  "layers": ["texture"]},
        {"name": "Verse",  "bars": 16, "layers": ["drums", "bass", "texture"]},
        {"name": "Hook",   "bars": 8,  "layers": ["drums", "bass", "lead", "vocal"]},
        {"name": "Verse 2","bars": 16, "layers": ["drums", "bass", "percussion", "texture"]},
        {"name": "Hook 2", "bars": 8,  "layers": ["drums", "bass", "lead", "vocal", "fx"]},
        {"name": "Outro",  "bars": 4,  "layers": ["texture", "vocal:-10dB"]},
    ],
}
```

Sections are realized as arrangement clips using `create_arrangement_clip` and `set_arrangement_automation` for volume fades at section boundaries.

---

## New MCP Tools (3 tools)

### `compose`

```python
@mcp.tool()
async def compose(
    ctx: Context,
    prompt: str,
    max_credits: int = 10,
    dry_run: bool = False,
) -> dict:
    """Create a full multi-layer composition from a text prompt.

    Searches Splice's catalog, downloads matching samples, loads them into
    Ableton, applies processing techniques, and arranges into sections.

    prompt: "dark minimal techno 128bpm with industrial textures and ghostly vocals"
    max_credits: maximum Splice credits to spend (default 10, 0 = use only downloaded)
    dry_run: if True, return the plan without executing (same as get_composition_plan)
    """
```

### `augment_with_samples`

```python
@mcp.tool()
async def augment_with_samples(
    ctx: Context,
    request: str,
    max_credits: int = 3,
    max_layers: int = 3,
) -> dict:
    """Add sample-based layers to the existing session.

    Analyzes the current song state, finds gaps, searches Splice for
    complementary samples, downloads and loads them with appropriate processing.

    request: "add organic textures" or "layer a vocal chop over the verse"
    max_credits: maximum Splice credits to spend (default 3)
    max_layers: maximum number of new tracks to add (default 3)
    """
```

### `get_composition_plan`

```python
@mcp.tool()
async def get_composition_plan(
    ctx: Context,
    prompt: str,
) -> dict:
    """Preview what compose would do without executing or spending credits.

    Returns the full layer plan with search queries, technique selections,
    processing chains, and arrangement sections. Use to review before committing.
    """
```

---

## Wonder Mode Integration

### Enhanced sample-domain variants

When Wonder Mode generates a sample variant, the compiled plan now includes Splice search:

```python
# Before (old): plan assumed a file_path existed
{"tool": "load_sample_to_simpler", "params": {"file_path": "???"}}

# After (new): plan includes search → download → load chain
{"tool": "search_samples", "params": {"query": "vocal {key}", "source": "splice_live"}},
{"tool": "_splice_download", "params": {"file_hash": "{best_match.file_hash}"}},
{"tool": "load_sample_to_simpler", "params": {"file_path": "{downloaded_path}"}},
```

The `render_preview_variant` path gains a `"sample"` family handler in the preview studio that:
1. Calls SpliceAgent to search with context-aware queries
2. Downloads the top-scoring match (1 credit)
3. Loads and processes per the technique
4. Returns preview-ready state for A/B comparison

### `augment_with_samples` as Wonder Mode action

When Wonder Mode runs and detects sample opportunities, one of the executable variants can be:
```
Variant B (sample): "Add ghostly vocal texture layer"
  → augment_with_samples("ghostly vocal texture")
  → searches Splice → downloads → loads → processes → mix-ready
```

This makes Wonder Mode's sample variants fully autonomous — from "I'm stuck" to "here's a new vocal texture layer, previewed and ready to commit."

---

## Credit Safety Model

| Guard | Value | Purpose |
|-------|-------|---------|
| `compose` default max | 10 credits | Full composition budget |
| `augment_with_samples` default max | 3 credits | Augmentation budget |
| Wonder Mode variant | 1 credit | Single sample preview |
| `get_composition_plan` | 0 credits | Dry run, free |
| Hard floor | 5 credits remaining | Never drain below 5 credits |
| User override | `max_credits` parameter | Can increase/decrease per call |

Before any download:
```python
credits = await splice_client.get_credits_remaining()
if credits <= HARD_FLOOR:
    return {"error": "Credits too low", "credits": credits, "fallback": "using_downloaded_only"}
if credits_needed > budget:
    return {"error": "Over budget", "credits": credits, "budget": budget}
```

---

## Dependency: grpcio

```
grpcio>=1.60.0
grpcio-tools>=1.60.0  # for proto compilation (dev only)
```

**Graceful degradation:** If `grpcio` not installed:
- `SpliceGRPCClient` import returns a no-op stub
- All gRPC methods return empty results
- System falls back to SQLite DB + browser + filesystem
- No crash, no import error

---

## Tool Count Impact

- Current: 303 tools
- New: 3 tools (compose, augment_with_samples, get_composition_plan)
- New total: **306 tools** across **42 domains** (adding `composer`)

---

## Implementation Order

1. **Proto compilation** — Extract .proto files, generate Python stubs
2. **SpliceGRPCClient** — connect, search, download, credits check
3. **Client tests** — mock gRPC server for unit tests
4. **Enhanced SpliceSource** — add `search_live` method
5. **Prompt parser** — text → CompositionIntent
6. **Layer planner** — intent → LayerSpec list
7. **Executor** — execute layers via existing tools
8. **MCP tools** — compose, augment_with_samples, get_composition_plan
9. **Wonder Mode integration** — sample variant executor
10. **Section arrangement** — genre templates, automation
11. **Tool count + skill updates**
12. **End-to-end test** — full compose pipeline with Ableton connected
