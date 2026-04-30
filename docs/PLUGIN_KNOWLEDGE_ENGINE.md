# Plugin Knowledge Engine

Beyond the file-level corpus (`docs/USER_CORPUS_GUIDE.md`) — a multi-stage
pipeline that *learns about installed plugins* the way a producer would:
detect them, find their manuals, find their examples, research techniques,
and synthesize a producer-oriented identity yaml that an AI agent can reason
over.

This is the architectural complement to the user-corpus builder. The corpus
builder indexes **files on disk**; the knowledge engine indexes **what those
files MEAN**.

---

## What's covered today vs the full vision

The user corpus skeleton ([docs/USER_CORPUS_GUIDE.md](USER_CORPUS_GUIDE.md))
covers exactly one thing: filesystem scanning of preset files (`.als`, `.adg`,
`.amxd`, `.vstpreset`/`.aupreset`/`.fxp`/`.nksf`).

The Plugin Knowledge Engine covers seven additional things:

| Phase | Capability | Status |
|-------|-----------|--------|
| 2.1 | Detect installed plugins from system folders | **shipping** |
| 2.2 | Extract identity from VST3 / AU / VST2 bundles | **shipping** |
| 2.3 | Discover local manual PDFs / HTML / .md | **shipping** |
| 2.4 | Extract text from local manuals | **shipping** |
| 2.5 | Index example / preset folders per plugin | **shipping** |
| 3 | Online manual + technique research (WebSearch + WebFetch) | **agent-driven** (returns search targets, agent executes) |
| 4 | AI synthesis of plugin identity from all sources | **agent-driven** (returns synthesis brief, agent dispatches sonnet) |

Phase 2 runs deterministically without an LLM. Phases 3 and 4 use the same
subagent pattern the rest of LivePilot uses — Python emits structured tasks,
the Claude agent fulfills them via tools it already has (WebSearch, WebFetch,
Agent dispatch).

---

## Pipeline architecture

```
                     ┌─────────────────────────────────┐
                     │  PHASE 2.1 — Plugin Detector    │
                     │  Scan system plugin folders:    │
                     │   /Library/Audio/Plug-Ins/VST3  │
                     │   /Library/Audio/Plug-Ins/Comp. │
                     │   /Library/Audio/Plug-Ins/VST   │
                     │  + Windows + Linux equivalents  │
                     └────────────────┬────────────────┘
                                      │   detected plugins (VST3/AU/VST2 bundles)
                                      ▼
                     ┌─────────────────────────────────┐
                     │  PHASE 2.2 — Identity Extractor │
                     │  VST3: parse moduleinfo.json    │
                     │  AU:   parse Info.plist         │
                     │  VST2: read CcnK header         │
                     │  All:  vendor, name, version,   │
                     │        unique_id, format, sdk   │
                     └────────────────┬────────────────┘
                                      │   plugins/_inventory.json
                                      ▼
                     ┌─────────────────────────────────┐
                     │  PHASE 2.3 — Manual Discovery   │
                     │  Glob common locations:         │
                     │   /Applications/<vendor>.app/   │
                     │   /Library/.../Plug-Ins/.../    │
                     │     Documentation/              │
                     │   ~/Documents/<vendor>/         │
                     │   <bundle>/Contents/Resources/  │
                     │  Find: .pdf .html .md .txt      │
                     └────────────────┬────────────────┘
                                      │   plugin → list of manual paths
                                      ▼
                     ┌─────────────────────────────────┐
                     │  PHASE 2.4 — Manual Extractor   │
                     │  pypdf  → text                  │
                     │  bs4    → text from HTML        │
                     │  Cache: plugins/<slug>/manual.* │
                     │  Section-aware splitter         │
                     └────────────────┬────────────────┘
                                      │   plugins/<slug>/manual.txt + sections.json
                                      ▼
                     ┌─────────────────────────────────┐
                     │  PHASE 2.5 — Example Indexer    │
                     │  Cross-reference user-corpus    │
                     │  plugin_presets sidecars with   │
                     │  detected plugins by vendor +   │
                     │  unique_id. Link factory banks. │
                     └────────────────┬────────────────┘
                                      │   plugins/<slug>/presets_index.json
                                      ▼
                ── deterministic output complete ──
                                      │
                                      ▼
                     ┌─────────────────────────────────┐
                     │  PHASE 3 — Online Research      │
                     │  Tool returns search TARGETS:   │
                     │   [{type:'manual',  q:'u-he     │
                     │      Diva user manual pdf'},    │
                     │    {type:'tutorial', q:'Diva    │
                     │      sound design'}]            │
                     │  Agent (in Claude Code) calls   │
                     │  WebSearch + WebFetch.          │
                     │  Results cached + provenance-   │
                     │  stamped under plugins/<slug>/  │
                     │  research/                      │
                     └────────────────┬────────────────┘
                                      │
                                      ▼
                     ┌─────────────────────────────────┐
                     │  PHASE 4 — AI Synthesis         │
                     │  Tool emits a brief packet:     │
                     │   - identity stub               │
                     │   - manual extract              │
                     │   - research cache              │
                     │   - factory preset list         │
                     │  Agent dispatches sonnet sub-   │
                     │  agent → identity.yaml with     │
                     │   sonic_fingerprint             │
                     │   reach_for / avoid             │
                     │   key_techniques (recipes)      │
                     │   parameter_glossary            │
                     │   comparable_plugins            │
                     │   genre_affinity                │
                     │   producer_anchors              │
                     └────────────────┬────────────────┘
                                      │
                                      ▼
                ┌────────────────────────────────────────┐
                │   ~/.livepilot/atlas-overlays/user/    │
                │      plugins/                          │
                │      ├── _inventory.json               │
                │      └── <slug>/                       │
                │          ├── identity.yaml             │
                │          ├── manual.txt                │
                │          ├── manual_sections.json      │
                │          ├── presets_index.json        │
                │          ├── research/                 │
                │          │   ├── search_log.json       │
                │          │   ├── manual_url.txt        │
                │          │   └── techniques.md         │
                │          └── synthesis_brief.json      │
                └────────────────────────────────────────┘
                                      │
                                      ▼
                ┌─────────────────────────────────┐
                │  QUERY SURFACE                  │
                │  extension_atlas_search(        │
                │    namespace="user.plugins")    │
                │  atlas_chain_suggest(           │
                │    role="bass" — recommends     │
                │    user's installed plugins     │
                │    based on identity.yaml)      │
                └─────────────────────────────────┘
```

---

## Folder-by-folder filesystem detection (Phase 2.1)

### macOS

| Format | Path | What's inside |
|--------|------|---------------|
| VST3 system | `/Library/Audio/Plug-Ins/VST3/` | `*.vst3` bundles |
| VST3 user | `~/Library/Audio/Plug-Ins/VST3/` | `*.vst3` bundles |
| AU system | `/Library/Audio/Plug-Ins/Components/` | `*.component` bundles |
| AU user | `~/Library/Audio/Plug-Ins/Components/` | `*.component` bundles |
| VST2 system | `/Library/Audio/Plug-Ins/VST/` | `*.vst` bundles or `.dylib` files |
| VST2 user | `~/Library/Audio/Plug-Ins/VST/` | same |
| AAX | `/Library/Application Support/Avid/Audio/Plug-Ins/` | `*.aaxplugin` bundles |

### Windows

| Format | Path |
|--------|------|
| VST3 | `C:\Program Files\Common Files\VST3\` |
| VST2 | `C:\Program Files\VstPlugins\` (varies — also user-configurable) |
| AAX | `C:\Program Files\Common Files\Avid\Audio\Plug-Ins\` |

### Linux

| Format | Path |
|--------|------|
| VST3 | `~/.vst3/` `/usr/lib/vst3/` `/usr/local/lib/vst3/` |
| LV2 | `~/.lv2/` `/usr/lib/lv2/` |

The detector walks all relevant paths for the running OS, filters by file
extension (and on macOS, treats the bundle directory as the plugin file).

---

## Identity extraction (Phase 2.2)

Each format exposes different metadata. We extract what's available without
requiring a plugin host:

### VST3 (`*.vst3`)
The VST3 SDK mandates a `Contents/Resources/moduleinfo.json` inside every
bundle. It contains:
```json
{
  "Name": "Diva",
  "Version": "1.4.5",
  "Vendor": "u-he",
  "URL": "https://u-he.com/products/diva/",
  "Email": "support@u-he.com",
  "Classes": [
    {
      "CID": "01234567ABCDEF0123456789ABCDEF01",
      "Name": "Diva",
      "Category": "Audio Module Class",
      "Vendor": "u-he",
      "Version": "1.4.5"
    }
  ]
}
```
Older VST3 bundles (pre-3.7) may not have this file — fall back to the
`.vst3` filename.

### AU (`*.component`)
`Contents/Info.plist` is XML or binary plist. Key fields:
- `CFBundleIdentifier` → reverse-domain plugin id
- `CFBundleShortVersionString` → version
- `CFBundleName` → plugin name
- `AudioComponents` array → for each: `name`, `manufacturer`, `subtype`,
  `type`, `description`

### VST2 (`*.vst` or `*.dylib`)
Has a `CcnK` chunk header readable from the binary. From the first 60 bytes:
- bytes 16–20: 4-char plugin code
- bytes 28–60: program name
- VST2 doesn't store vendor in the binary — infer from the file path
  (`/Library/Audio/Plug-Ins/VST/<vendor>/<plugin>.vst` is conventional)

### AAX (`*.aaxplugin`)
Bundle contains `Contents/Resources/PluginManifest.plist` — same key/value
shape as AU. Extract the PluginID, version, manufacturer.

---

## Manual discovery search order (Phase 2.3)

For each detected plugin, glob in priority order:

1. **Inside the bundle** (`<plugin>.vst3/Contents/Resources/`,
   `<plugin>.component/Contents/Resources/`) — most reliable
2. **`/Applications/<Vendor>*.app/Contents/Resources/`** — many vendors ship
   the manual with a companion app installer (u-he, Spectrasonics, Native
   Instruments)
3. **`/Library/Audio/Plug-Ins/<format>/<vendor>/Documentation/`**
4. **`~/Documents/<vendor>/`**, **`~/Documents/<plugin>/`**
5. **`/Library/Application Support/<vendor>/`**
6. **`/Library/Application Support/<vendor>/<plugin>/Documentation/`**

File extensions checked: `.pdf`, `.html`, `.htm`, `.md`, `.txt`, `.rtf`.

---

## Section-aware text extraction (Phase 2.4)

PDFs are extracted via `pypdf` with a `pdfplumber` fallback for tricky pages.
HTML manuals via `bs4`. Plain `.md`/`.txt` are read directly.

After extraction we run a section splitter that recognizes common chapter
headings ("Parameters", "Modulation", "Effects", "Tutorial") and produces a
`manual_sections.json` mapping section title → text range. This gives Phase 4
something more granular than 200 pages of unstructured text.

---

## Research target packet (Phase 3)

The Phase 3 tool doesn't itself call the web — it returns a structured packet
that the Claude agent fulfills. This separates "what knowledge is needed" from
"how to fetch it" and avoids tying the corpus engine to any specific search
backend.

```json
{
  "plugin_id": "u-he-diva",
  "plugin_identity": { "name": "Diva", "vendor": "u-he", "format": "VST3" },
  "local_manual_present": true,
  "research_targets": [
    {
      "type": "manual_alt",
      "rationale": "Verify local manual is current",
      "queries": [
        "site:u-he.com Diva manual",
        "u-he Diva 1.4 user guide pdf"
      ],
      "priority": 1
    },
    {
      "type": "technique_corpus",
      "rationale": "Build technique library",
      "queries": [
        "u-he Diva sound design tutorial",
        "Diva analog bass patch",
        "Diva pad evolving",
        "Diva compared to Repro-1"
      ],
      "priority": 2
    },
    {
      "type": "comparison",
      "rationale": "When to reach for vs alternatives",
      "queries": ["u-he Diva vs Repro-1 vs Reaktor Monark"],
      "priority": 3
    }
  ],
  "instructions": "Use WebSearch + WebFetch. Cache top 3 results per query under <plugin_dir>/research/. Stamp each cached file with the source URL + retrieval timestamp.",
  "next_step_tool": "corpus_synthesize_plugin_identity"
}
```

The agent's natural workflow inside Claude Code:
```
> Build knowledge for my installed plugins
[Tool returns 80 detected plugins. User picks priority subset.]
[Tool returns research targets for each.]
[Agent dispatches WebSearch + WebFetch in parallel sonnet subagents.]
[Tool collects research output + emits Phase 4 synthesis brief.]
[Agent dispatches sonnet to write identity.yaml per plugin.]
```

---

## Synthesis brief (Phase 4)

The Phase 4 tool emits a self-contained brief for a sonnet subagent:

```yaml
plugin_id: u-he-diva
synthesis_inputs:
  identity:
    name: Diva
    vendor: u-he
    format: VST3
    version: 1.4.5
  manual_extract:
    parameter_glossary:
      - {name: "Cutoff", section: "Filters", description: "..."}
      - ...
    chapter_summaries:
      - {chapter: "Modulation", text: "..."}
  research_cache:
    techniques: ["...recipe text...", "...another..."]
    comparisons: ["...prose..."]
  preset_examples:
    - {name: "Bass Brilliant", path: "..."}
    - ...

synthesis_schema:
  sonic_fingerprint: "3-5 sentence description"
  reach_for: ["bullet list of when to use"]
  avoid: ["bullet list of when to skip"]
  key_techniques: ["concrete recipes (param + value pairs preferred)"]
  parameter_glossary: ["only the dials that matter, with what they do"]
  comparable_plugins: [{name: "Repro-1", when_better: "..."}]
  genre_affinity: ["genre slugs"]
  producer_anchors: ["producer names whose sound this plugin reaches for"]

output_path: ~/.livepilot/atlas-overlays/user/plugins/u-he-diva/identity.yaml
```

The agent dispatches one sonnet per plugin (or batches of ~5) using the
existing `Agent` tool with `subagent_type=general-purpose, model=sonnet`.

---

## What the user sees in Claude Code

```
> Detect my installed plugins.
[Claude calls corpus_detect_plugins()]
[returns: 142 plugins detected — 89 VST3, 38 AU, 15 VST2]

> Show me the top 20 by frequency in my .als projects.
[Claude correlates _inventory.json with user.projects sidecars]
[returns ranked list]

> For the top 10, find their manuals + extract them.
[Claude calls corpus_discover_manuals(plugin_ids=[...])]
[returns: 7/10 found local manuals, 3/10 require web search]
[Claude calls corpus_research_targets(plugin_ids=[...])]
[Claude dispatches WebSearch + WebFetch for the 3 missing,
 caches results, stamps provenance]

> Synthesize identity yaml for all 10.
[Claude calls corpus_emit_synthesis_briefs(plugin_ids=[...])]
[Claude dispatches 10 parallel sonnet subagents, each writes one identity.yaml]

# Now query
> What's a good bass plugin for the kind of project I made last month?
[Claude reads user.projects sidecar for that project,
 reads its plugin_inventory cross-references,
 reads identity.yaml for those plugins,
 picks the best match by reach_for / genre_affinity / producer_anchors]
```

The final state: an agent that can answer *"what plugin should I reach for"*
in terms of YOUR sound, not generic recommendations.

---

## Why the agent-driven split for Phases 3 + 4

Putting WebSearch and Anthropic-API calls inside the corpus engine would:
- Tie the engine to specific HTTP backends (search APIs, Anthropic SDK)
- Bypass Claude Code's permission model
- Lose the parallelism Claude Code already does well

Instead the engine returns *structured tasks* and lets Claude Code fulfill
them with the tools it already has. This matches the same pattern as
`browser_search_hint` for `load_browser_item`, `manual_step` for cross-pack
chains, and the sonnet-subagent dispatch the rest of the codebase uses.

The user gets the full pipeline; the engine stays portable.

---

## What's shipping in this turn

Phase 2.1 — installed plugin detector (VST3/AU/VST2 bundle parsers)
Phase 2.3 — local manual discoverer
Phase 2.4 — PDF / HTML / text extractor with section splitter

Plus the MCP tools that surface them: `corpus_detect_plugins`,
`corpus_discover_manuals`, `corpus_research_targets` (returns the Phase 3
target packet), `corpus_emit_synthesis_briefs` (returns the Phase 4 brief).

Phases 3 and 4 are the agent-driven layer documented in the SKILL — the
tools emit structured tasks; the agent fulfills them. No code change
required when you upgrade Claude's web-search tooling.
