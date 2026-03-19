# README + Manual Rewrite — Design Spec

## Context

LivePilot v1.7.2. 155 tools, 16 domains, 3 new domains (Generative, Harmony, MIDI I/O).
Current README is 561 lines — marketing-oriented, beginner-friendly, includes a comparison
table against competing MCP servers. The audience has shifted: LivePilot users are producers
who think systematically about sound. The docs need to reflect that.

## Scope

**Rewrite:** `README.md`, `docs/manual/index.md`
**Update (counts/descriptions only):** `package.json`, `plugin/plugin.json`, `server.json`,
`plugin/skills/livepilot-core/SKILL.md`, `plugin/skills/livepilot-core/references/overview.md`
**Do NOT touch:** CHANGELOG.md, docs/TOOL_REFERENCE.md, docs/manual/tool-reference.md,
research docs, test files, engine code.

## Audience

The intersection of:
- **Producers** who know Max/MSP, think in LFOs and probability, care about neo-Riemannian
  transforms and Bjorklund algorithms
- **Creative coders** from Processing/TouchDesigner/SuperCollider who see Ableton as another
  node in a generative pipeline

Not beginners. Not API consumers. Artists who want to understand the machine.

## Tone

- Direct, no fluff, no marketing language
- Expose the theory/math behind tools — Bjorklund, PRL transforms, Krumhansl-Schmuckler,
  species counterpoint, hexatonic poles
- "To the point" — present what we built, not what it could be
- Art-oriented, not tutorial-oriented
- No "make a boom bap loop" examples

## Visual Style

- Keep existing ASCII logo
- Use ASCII box-drawing for diagrams and section separators
- Markdown renders in monospace — lean into that
- No emoji. No badges at the top (push to footer or remove).

---

## README.md Structure

### 1. HEADER (above the fold)

```
[ASCII LOGO — keep existing]

An agentic production system for Ableton Live 12.
155 tools. Device atlas. Spectral perception. Technique memory.
Neo-Riemannian harmony. Euclidean rhythm. Species counterpoint.
```

No badges above the fold. Identity statement only.

### 2. ARCHITECTURE

ASCII box diagram showing the 3-layer system:
- Knowledge (Device Atlas: 280+ devices, 139 kits, 350+ IRs)
- Perception (M4L Analyzer: 8-band spectrum, RMS/peak, key detection)
- Memory (Technique Store: recall by mood, genre, texture)

Below diagram: 3-4 dense lines explaining the layers. No sub-headers.

Connection details: Remote Script TCP 9878, M4L Bridge UDP 9880 / OSC 9881.

### 3. TOOLS BY DOMAIN

Four category groups, each with domains listed.

#### CORE (8 domains, ~57 tools)

Compact table. Tool names + one-line descriptions. No theory needed.

| Domain | Tools | What |
|--------|-------|------|
| Transport | 5 | playback, tempo, time sig, metronome, cue points |
| Tracks | 10 | create/delete/duplicate, arm, mute, solo, color, routing |
| Clips | 8 | create/delete/duplicate, loop, launch, warp mode, quantize |
| Notes | 8 | add/remove/modify/duplicate/transpose, get, probability |
| Devices | 9 | load, params, racks, chains, toggle, presets, browser URI |
| Scenes | 6 | create/delete/duplicate, fire, name, color, tempo |
| Browser | 3 | search, browse tree, load items |
| Mixing | 8 | volume, pan, send, mute/solo, routing, mix snapshot |

#### PERCEPTION (1 domain, 20 tools)

Paragraph: what the M4L Analyzer does, how it connects (UDP/OSC),
graceful degradation (all core tools work without it).

Sub-groups listed:
- Spectral Analysis (3): spectrum, RMS, key detection
- Deep LOM (4): hidden params, automation state, device tree, display values
- Simpler Operations (7): replace/load sample, slices, crop, reverse, warp, file path
- Warp Markers (4): get/add/move/remove
- Clip Preview (2): scrub, stop scrub

#### INTELLIGENCE (4 domains, 24 tools)

Each domain gets a theory paragraph + tool list.

**Theory (7 tools)**
Krumhansl-Schmuckler key detection with 7 mode profiles. Roman numeral analysis
via scale-degree chord matching. Voice leading checks (parallel 5ths/8ves, crossing).
Species counterpoint (1st and 2nd species). Diatonic transposition preserving scale
relationships.

Tools: analyze_harmony, suggest_next_chord, detect_theory_issues, identify_scale,
harmonize_melody, generate_countermelody, transpose_smart

**Harmony (4 tools)**
Neo-Riemannian PRL transforms on the Tonnetz. P flips the third (Cm ↔ C).
L shifts by semitone (C ↔ Em). R by whole tone (C ↔ Am). All involutions.
BFS through PRL space finds shortest voice-leading paths. Chromatic mediants
for film-score harmony — maximum color shift, minimal voice movement.

Tools: navigate_tonnetz, find_voice_leading_path, classify_progression,
suggest_chromatic_mediants

**Generative (5 tools)**
Bjorklund distributes N pulses across M steps — Bresenham's line applied to
rhythm. E(3,8) = tresillo. E(7,16) = Brazilian necklace. Layer multiple
patterns for polyrhythmic textures. Tintinnabuli (Pärt): map melody notes
to nearest triad tone. Phase shifting (Reich): drifting canon with accumulating
offset. Additive process (Glass): melody unfolds note by note, forward and back.

Tools: generate_euclidean_rhythm, layer_euclidean_rhythms, generate_tintinnabuli,
generate_phase_shift, generate_additive_process

**Automation (8 tools)**
16 curve types in 4 categories: basic (linear, exp, log, s-curve, sine, saw,
spike, square, steps), organic (perlin, brownian, spring), shape (bezier, easing),
generative (euclidean, stochastic). 15 built-in recipes (filter sweeps, dub throws,
sidechain pump, tape stop, tremolo, auto-pan, stutter). Perception-action loop:
read spectrum → diagnose → automate → verify.

Tools: get_clip_automation, set_clip_automation, clear_clip_automation,
apply_automation_shape, apply_automation_recipe, get_automation_recipes,
generate_automation_curve, analyze_for_automation

#### MEMORY + I/O (2 domains, 12 tools)

**Memory (8 tools)**
Persistent technique library across sessions. Save beat patterns, device chains,
mix templates, browser pins, preferences. Recall by text query matching mood,
genre, texture. Favorite, rate, replay.

Tools: memory_learn, memory_recall, memory_list, memory_get, memory_update,
memory_delete, memory_favorite, memory_replay

**MIDI I/O (4 tools)**
Export clips to .mid. Import .mid into clips (auto-creates clip, tempo-aware).
Offline analysis: note count, density curve, velocity stats, key estimate.
Piano roll extraction: 2D velocity matrix at configurable resolution.
Dependencies lazy-loaded (midiutil, pretty_midi) — graceful error if missing.

Tools: export_clip_midi, import_midi_to_clip, analyze_midi_file, extract_piano_roll

### 4. INSTALL

Compact configs for each client. No prose, just code blocks with headers:
- Claude Code (one-liner)
- Claude Desktop macOS
- Claude Desktop Windows
- Cursor
- VS Code / Windsurf

Plus: M4L Analyzer install (drag to master track).

### 5. FULL TOOL LIST

All 155 tools in a single reference table grouped by domain:

| tool | description |
|------|-------------|
| **TRANSPORT** | |
| start_playback | Start playback from the beginning |
| stop_playback | Stop playback |
| ... | ... |

All 16 domains, all 155 tools. One line each.

### 6. ROADMAP

```
COMING ─────────────────────────────
□  Real-time DSP analysis via LOM meters
□  M4L bridge expansion — deeper LiveAPI access
□  Arrangement view — clip placement, tempo automation
□  Audio clip manipulation — stretch, slice, resample
□  Plugin parameter mapping — VST/AU deep control
```

### 7. FOOTER

License line. Link to GitHub issues. Sister projects (TDPilot, ComfyPilot).
Badges here if kept at all.

---

## docs/manual/index.md Structure

Same tone shift. Drop the beginner framing.

### New Structure

1. **One-line identity** (same as README)
2. **Domain map** — 16 domains with tool counts, links to tool-reference sections
3. **Architecture** — shorter version of README diagram
4. **Chapters** — keep existing chapter links but update descriptions:
   - Tool Reference
   - Workflows
   - MIDI Guide
   - Sound Design
   - Mixing
   - Troubleshooting
5. **Drop** the "Who this is for" and "Say X and it builds Y" sections

---

## Files to Update (counts/descriptions only)

These files reference tool counts, domain counts, or project descriptions.
Update the numbers and one-line descriptions to match the new tone. Do NOT
rewrite these files — just sync the metadata.

- `package.json` — description field
- `plugin/plugin.json` — description field
- `server.json` — description field
- `plugin/skills/livepilot-core/SKILL.md` — opening description, tool/domain counts
- `plugin/skills/livepilot-core/references/overview.md` — tool/domain counts, domain list

---

## What NOT to Change

- CHANGELOG.md — historical record, stays as-is
- docs/TOOL_REFERENCE.md — reference doc, stays as-is
- docs/manual/tool-reference.md — reference doc, stays as-is
- Any research docs in docs/
- Test files
- Engine code
- CLAUDE.md (already current)

---

## Success Criteria

1. README leads with the system, not marketing
2. Every non-obvious tool domain has its theory exposed in 2-4 sentences
3. Full 155-tool list is present and scannable
4. No comparison tables
5. No beginner framing ("say X and it builds Y")
6. Install section is compact (configs only)
7. Roadmap gives direction without promises
8. ASCII art used for structure, not decoration
9. Manual index matches the new tone
