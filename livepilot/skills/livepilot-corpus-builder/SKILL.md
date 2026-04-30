---
name: livepilot-corpus-builder
description: Build a private knowledge corpus from your own Live projects, rack library, Max devices, and plugin presets. Use when the user says "build my corpus", "scan my projects", "index my racks", "make atlas of my library", "private atlas from my files", or wants Claude to know their personal sound (not just Ableton's factory content).
version: 1
---

# LivePilot — Private Corpus Builder

Use this skill when the user wants to create a private corpus-atlas from
their own filesystem content. The result becomes queryable through the same
`atlas_*` and `extension_atlas_*` MCP tools that already index Ableton's
factory packs.

**You are NOT scanning anything blindly.** Every step needs the user to
confirm a path, a scanner type, and (optionally) opt in to AI annotation.

---

## When to invoke

Trigger words: "build my corpus", "scan my projects", "index my racks",
"make atlas of my library", "private atlas", "know my own sound", "my
production knowledge", "scan my plugin presets".

This skill is the right entry point for the FIRST time a user wants to
build their corpus. For subsequent runs (incremental scans, adding sources)
the user can just call `corpus_*` tools directly — the skill is about
ergonomics for newcomers.

---

## Workflow (6 steps)

### Step 1 — Confirm intent + state

Read [docs/USER_CORPUS_GUIDE.md](../../../docs/USER_CORPUS_GUIDE.md) for
the architecture (don't paste it back to the user — assume they want
results, not docs). Tell the user:

> "I'll set up a private corpus at `~/.livepilot/atlas-overlays/user/`,
> scan whatever folders you point me at, and make the result queryable
> via the same atlas tools. Mechanical scan first (fast, deterministic).
> AI annotation is optional and runs as a separate step."

Then call:

```
corpus_status()
```

If `sources: []`, this is a fresh setup — call `corpus_setup_wizard()`
(step 1.5 below) to detect candidates. If sources already exist, ask
whether to add new ones, rescan existing, or both.

### Step 1.5 — First-run wizard (NEW — recommended for new users)

```
corpus_setup_wizard()
```

This surveys the user's filesystem for sensible scan targets and returns
a candidate packet — no scanning happens yet. Walk the user through each
candidate one at a time:

> "I found a User Library folder with 1,234 .adg rack presets — should I
> index it? (default: yes)"
>
> "I see 431 .amxd Max devices in MAX MONTY/m4l_2024 — index them too?"
>
> "Also a bundle of plugin presets at ~/Library/Audio/Presets — these
> tend to be noisy (5,000+ files often). Skip or include?"

For each YES, call `corpus_add_source(...)` with the candidate's suggested_id, type, path. Then ask the separate plugin-detection question:

> "Want me to also detect installed VST3/AU/VST2 plugins via
> corpus_detect_plugins? Independent of file scanning — different layer."

If yes, call `corpus_detect_plugins()` after the file scan completes.

Personal `.als` project folders are NEVER auto-suggested — privacy-sensitive.
The user must point at any specific session they want indexed.

### Step 2 — Initialize

```
corpus_init()
```

Idempotent. Creates the output dir + a default manifest if absent.

### Step 3 — Discover what to scan

Ask the user:

> "Which folders should I index? Common places (you can pick any combo):
> - Live projects: typically `~/Music/<your-folder>` or wherever you save .als files
> - Rack library: `~/Music/Ableton/User Library/Presets`
> - Max devices: `~/Documents/Max <N>/Max for Live Devices`
> - Plugin presets: `~/Library/Audio/Presets` (macOS) or `%APPDATA%\VST3 Presets` (Windows)
> Tell me a path + what type of content it has, and I'll add it."

Run `corpus_list_scanners()` to show the user what types are supported
on this install.

For each path the user names:

```
corpus_add_source(
    source_id="<short-id-they-pick>",
    type="<als | adg | amxd | plugin-preset>",
    path="<absolute path>",
    recursive=True,
)
```

**Recommendations:**
- Use short, lowercase, hyphenated source IDs: `my-projects`, `my-racks`,
  `m4l-devices`. They become part of every entity_id and namespace.
- For very large libraries (>2000 files), suggest scanning a subset first
  to validate before doing the full sweep.
- Ask about exclude patterns for backup folders, version-control checkouts,
  and `.als-archive` files.

### Step 4 — Run the scan

```
corpus_scan()    # all sources
# OR
corpus_scan(source_id="my-projects")   # one source
```

Show the user the per-source progress + error counts. If any source had
errors, surface the first 3 with paths so they can see whether to ignore
or fix them. Common error causes:
- Live 11 corruption sentinel files
- Password-protected projects
- Symlink loops
- Filesystem permissions

If a path doesn't exist, the manifest still keeps the source — the user
can fix the path with `corpus_remove_source` then re-add.

### Step 5 — Verify queryability

After scanning, the new sidecars are on disk but the running MCP server
hasn't loaded them yet (overlays are read at boot). Tell the user:

> "Restart the MCP server to load the new sidecars into the overlay
> index. After restart you can query via:
> - `extension_atlas_search(query='...', namespace='user.<source_id>')`
> - `extension_atlas_get(...)`
> - `atlas_*` tools that respect overlay namespaces"

If they're inside Claude Code, the MCP server is already restarted on
each session start, so the next session sees the new corpus.

Demonstrate one search after restart:

```
extension_atlas_search(query="pad", namespace="user.<their-source-id>")
```

If matches return: green light. If no matches: check that wrappers
were written (look at `~/.livepilot/atlas-overlays/user/<output_subdir>/`
for `*.yaml` files), check the wrapper's tags, and verify the namespace
is `user.<source_id>` not `user/<source_id>`.

### Step 6 — Optional: AI annotation

If the user wants the corpus to have free-form descriptions (sonic
fingerprint, reach-for, key-techniques — like the factory pack identity
YAMLs), do an AI annotation pass.

Per the [feedback rule on subagents](../../../../../.claude/projects/-Users-visansilviugeorge-Desktop-DREAM-AI-LivePilot/memory/feedback_use_sonnet_subagents_for_token_economy.md),
this MUST use parallel sonnet subagents. Pattern:

1. Read the source's `_parses/*.json` directory.
2. Group sidecars into batches of ~20 entries.
3. For each batch, dispatch ONE sonnet agent with:
   - The batch's JSON sidecars
   - The artist + genre vocabulary references from
     `livepilot/skills/livepilot-core/references/`
   - The annotation YAML schema (see USER_CORPUS_GUIDE.md §"AI annotation")
4. Each agent writes one `annotated/<slug>.yaml` per sidecar in its batch.
5. Synthesize a summary in main: total annotated, failures, sample preview.

**Brief template for the annotation subagent:** "You are writing producer-
oriented annotation YAMLs for these N sidecars. Read each sidecar's
device list + scale + BPM. Read the artist/genre vocabularies for register
matching. Write one YAML per sidecar with sonic_fingerprint (3-5 sentences),
reach_for / avoid bullet lists, genre_affinity tags, producer_anchors when
the device combo or aesthetic register clearly maps to a known producer."

Cap subagents at 3 in flight at once to avoid context bloat in main.

---

## Anti-patterns (don't do these)

1. **Don't auto-scan without confirmation.** The user's filesystem is
   private; ask before every new path.
2. **Don't recurse into protected folders.** Watch for paths like
   `~/Library/Application Support/com.ableton.live/Drm` or anything in
   `/System/...`. Filter via `exclude_globs`.
3. **Don't apply AI annotation to ALL sources by default.** It's expensive
   in tokens and the user may only care about annotations for their .als
   projects, not their .adg rack library.
4. **Don't suggest deleting the manifest** to "start over" — `corpus_remove_source`
   preserves sidecars on disk so they can be reused. Manifest delete is
   destructive only to the source-list, not to indexed data.
5. **Don't try to write to the bundled atlas tree.** Always write under
   `~/.livepilot/atlas-overlays/user/`. The factory atlas at `packs/` is
   read-only from this skill's perspective.

---

## Quick reference — corpus tools (14 total)

| Tool | When |
|------|------|
| **File scanning (Phase 1)** | |
| `corpus_setup_wizard` | First-run filesystem survey + approval prompts (recommended entry point) |
| `corpus_init` | First-time setup |
| `corpus_add_source` | After wizard approval — for each folder |
| `corpus_remove_source` | When a source's path changes or you want to redefine |
| `corpus_scan` | After every batch of source additions; periodically for incremental |
| `corpus_status` | Whenever the user asks "what do I have" |
| `corpus_list_scanners` | When the user asks "what file types can I scan" |
| **Plugin knowledge (Phase 2-4)** | |
| `corpus_detect_plugins` | Enumerate installed VST3/AU/VST2/AAX (Mac: also runs `auval -a` for AUv3) |
| `corpus_canonicalize_plugins` | Dedupe inventory: prefer VST3, merge "Valhalla DSP, LLC" + "Valhalladsp" via canonical-vendor key |
| `corpus_cluster_plugins` | Group canonical plugins by vendor → dispatch manifest for efficient research |
| `corpus_discover_manuals` | Find + extract local manual PDFs/HTML for one plugin |
| `corpus_research_targets` | Emit WebSearch task packet for one plugin (no local manual or to verify) |
| `corpus_emit_synthesis_briefs` | Emit sonnet-subagent briefs to write `identity.yaml` per plugin |
| `corpus_trim_plugin_identity` | Slim a plugin's identity to overlay-required minimum + `research-priority:low` tag |

For querying the built corpus, use the existing `atlas_*` and
`extension_atlas_*` tools with `namespace="user.<source_id>"`.

---

## Plugin knowledge engine — Phase 2-4 agent flow

When the user asks: *"learn about my installed plugins"*, *"index my VST library"*,
*"build knowledge of all my plugins"* — this is the Plugin Knowledge Engine.
See [docs/PLUGIN_KNOWLEDGE_ENGINE.md](../../../docs/PLUGIN_KNOWLEDGE_ENGINE.md)
for full architecture.

### Step P1 — Detect (deterministic)

```
corpus_detect_plugins()
```

Walks OS-standard plugin folders, parses each bundle's identity metadata
(VST3 `moduleinfo.json` / AU `Info.plist` / VST2 CcnK / AAX manifest), writes
`~/.livepilot/atlas-overlays/user/plugins/_inventory.json`. On macOS expect
30-200 plugins typical; runtime <2 seconds.

Show the user the count + format breakdown. Ask if they want to proceed with
all detected plugins or filter to a subset (by vendor, format, size).

### Step P2 — Local manuals (deterministic)

For each plugin (or the priority subset):

```
corpus_discover_manuals(plugin_id="<id>")
```

Globs the standard manual locations + extracts text from the top candidate
via pypdf / bs4 / pdfplumber. Section splitter detects chapter headings.

Many modern plugins won't have local manuals (vendors point to web docs).
That's expected — Step P3 picks up the slack.

### Step P2.5 — Canonicalize + cluster the inventory (NEW — efficiency step)

After `corpus_detect_plugins` returns the raw inventory (often 100-200 plugins
on a populated Mac with iOS-port apps), call:

```
corpus_canonicalize_plugins()      # dedupes by vendor+name, prefers VST3
corpus_cluster_plugins()           # groups by vendor for efficient research
```

`corpus_canonicalize_plugins` collapses cross-format duplicates ("Valhalla DSP,
LLC" + "Valhalladsp" → one record with `formats_available: [AU, VST3]`) and
filters utility/system entries (Apple system AUs, Splice loaders) by default.
On a real machine this typically reduces ~120 raw plugins → ~50-70 canonical.

`corpus_cluster_plugins` groups by canonical vendor + flags singletons. The
result tells the agent which vendors to research as CLUSTERS (one shared
WebSearch pass + N lean identity yamls) vs SINGLETONS (independent research).
Typical clustering: Cem Olcay (9 MIDI tools = 1 shared pass), Moog (6 = 1
pass), chowdsp (4 = 1 pass) — vs flagship singletons like Drambo / Audulus 4
that warrant their own research.

**Wave-dispatch pattern from real-world testing:**
- ~5-8 cluster agents in parallel + 1-2 singleton-batch agents = ~7-10 total
  parallel sonnet subagents.
- Each cluster agent is briefed with: plugin IDs from `corpus_cluster_plugins`
  output, the existing reference identity (e.g., Valhalla Supermassive's), the
  shared-research strategy from the cluster manifest's `research_strategy`
  field.
- Singleton-batch agents handle 5-7 unrelated plugins each with independent
  research per plugin.
- Token cost: ~80K per flagship singleton; ~30K-50K per cluster plugin (after
  research-sharing amortization). 60 plugins ≈ 700K-1M total.

### Step P3 — Web research (agent-driven, dispatch sonnet subagents)

For each plugin without a local manual (or to supplement an outdated one):

```
corpus_research_targets(plugin_id="<id>")
```

Returns a structured packet of search queries the agent fulfills via
**WebSearch + WebFetch**. **Per the standing rule on subagents**, dispatch
parallel sonnet agents — one per plugin OR one per query type — to:

1. Run `WebSearch(query=<query>)` for each query in `research_targets`
2. Pick the top relevant URL per result set (skip paywalls, marketing pages)
3. `WebFetch(url=<url>, prompt="extract concrete sound design techniques + parameter recipes")`
4. Cache the extracted text to `<cache_root>/<target_type>/<n>.txt` with the source URL stamped in the first line

Cap parallel subagents at 5 to avoid main-context bloat. Each subagent writes
to disk + returns a one-paragraph summary.

### Step P4 — AI synthesis (agent-driven, dispatch sonnet subagents)

After research is cached for a batch of plugins:

```
corpus_emit_synthesis_briefs(plugin_ids=[...])
```

Returns one `synthesis_brief` per plugin — a self-contained packet with all
identity + manual + research data plus a YAML schema to fill. Dispatch one
sonnet subagent per brief (or batches of 3 in parallel) using the `Agent`
tool with `subagent_type="general-purpose"` and `model="sonnet"`. Each
subagent:

1. Reads `brief["synthesis_inputs"]`
2. Writes a YAML at `brief["output_path"]` matching `brief["synthesis_schema"]`
3. Returns a 200-word summary of what they wrote

Result: per-plugin `~/.livepilot/atlas-overlays/user/plugins/<plugin_id>/identity.yaml`
with `sonic_fingerprint`, `reach_for`, `avoid`, `key_techniques`,
`parameter_glossary`, `comparable_plugins`, `genre_affinity`, `producer_anchors`.

### Querying after the engine completes

The plugin identity YAMLs are picked up by the overlay loader on next MCP
server boot. Then:

```
extension_atlas_search(query="warm pad analog", namespace="user.plugins")
extension_atlas_get(namespace="user.plugins", entity_id="u-he-diva")
atlas_chain_suggest(role="bass", genre="dub_techno")
  # may now return user-installed plugins ranked by reach_for / genre_affinity
```

The agent has knowledge of *the user's* sound, not just Ableton's defaults.

---

## Universal extensibility

If the user has a content type the built-in scanners don't cover (Reaper
.rpp, Bitwig .bwproject, custom JSON metadata files, etc.) tell them they
can add a Scanner subclass to `mcp_server/user_corpus/scanners/` —
documented in [docs/USER_CORPUS_GUIDE.md](../../../docs/USER_CORPUS_GUIDE.md)
under "Scanner abstraction (write your own)". The 4 built-in scanners
are the reference implementations; the pattern is plugin-style — drop in
a file with `@register_scanner`, name a `type_id`, implement `scan_one`
+ `derive_tags` + `derive_description`. The runner picks it up.
