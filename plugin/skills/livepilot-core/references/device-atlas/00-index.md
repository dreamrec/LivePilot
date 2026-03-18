# Device Atlas — Master Index

> Last updated: 2026-03-18 | 10,600+ lines | 330+ devices | 139 drum kits | 350+ IRs | 1,850+ presets mapped

## How to Use This Atlas

**Agent loading strategy:**
1. Read this index first to understand what's available
2. Based on the user's request, load only the relevant 1-2 category files
3. For compound requests ("add compression and reverb"), load both relevant files
4. For vibe-based requests ("make it darker"), load `presets-by-vibe.md`
5. Always verify device existence via `search_browser` before loading — the atlas tells you WHAT and WHY, the browser confirms it EXISTS

## Atlas Files

### Sound Processing

| File | Scope | Devices | Lines |
|------|-------|---------|-------|
| [dynamics-and-punch.md](dynamics-and-punch.md) | Compressors, limiters, gates, transient shapers | 21 (6 native + 15 M4L) | 525 |
| [distortion-and-character.md](distortion-and-character.md) | Saturators, fuzz, amp sims, tape, IRs | 17 + 350 IRs | 687 |
| [space-and-depth.md](space-and-depth.md) | Reverbs, delays, diffusion, spatial | 19 (12 native + 7 M4L) | 571 |
| [movement-and-modulation.md](movement-and-modulation.md) | Chorus, phaser, LFOs, tremolo, auto-pan | 21 (5 native + 16 M4L) | 874 |
| [spectral-and-weird.md](spectral-and-weird.md) | Granular, glitch, spectral, experimental | 40 (5 native + 35 M4L) | 714 |
| [eq-and-filtering.md](eq-and-filtering.md) | EQs, filters, resonators, vocoder | 13 (8 native + 5 M4L) | 402 |

### Sound Generation

| File | Scope | Devices | Lines |
|------|-------|---------|-------|
| [synths-native.md](synths-native.md) | All 11 Ableton instruments in depth | 11 native | 953 |
| [synths-m4l.md](synths-m4l.md) | Fors, Mutable Instruments, Sonus Dept, Spektro, etc. | 34 M4L | 730 |
| [plugins-synths.md](plugins-synths.md) | AU/VST plugin synths, samplers, drum machines, effects, MIDI tools | 49 entries (85+ plugins) | 1,300+ |
| [drums-and-percussion.md](drums-and-percussion.md) | Drum Rack, DS synths, kits by genre, M4L drum tools | 18 + 139 kits | 753 |

### MIDI & Composition

| File | Scope | Devices | Lines |
|------|-------|---------|-------|
| [midi-tools.md](midi-tools.md) | Arpeggiators, chord tools, sequencers, generative | 45 (13 native + 32 M4L) | 963 |

### Workflow & Utility

| File | Scope | Devices | Lines |
|------|-------|---------|-------|
| [utility-and-workflow.md](utility-and-workflow.md) | Meters, mapping, routing, QOL tools | 42 (3 native + 39 M4L) | 843 |

### Cross-References

| File | Scope | Lines |
|------|-------|-------|
| [samples-and-irs.md](samples-and-irs.md) | 3,889 samples + Encoder Audio Mojo IR guide | 597 |
| [presets-by-vibe.md](presets-by-vibe.md) | 14 vibe categories mapping natural language → devices/presets | 727 |

## Quick Routing Guide

**User says something about...** → **Load this file:**

| Request Pattern | Primary File | Secondary File |
|----------------|-------------|----------------|
| "make it punchier / harder / tighter" | dynamics-and-punch | distortion-and-character |
| "add warmth / grit / saturation / fuzz" | distortion-and-character | dynamics-and-punch |
| "more space / depth / reverb / delay / echo" | space-and-depth | — |
| "add movement / modulation / wobble / pulse" | movement-and-modulation | — |
| "glitch / granular / freeze / spectral / weird" | spectral-and-weird | — |
| "EQ / filter / tone / brighten / darken" | eq-and-filtering | — |
| "I need a synth / bass / pad / lead" | synths-native | synths-m4l, plugins-synths |
| "Moog / Drambo / granular / modular / DX7 / sampler plugin" | plugins-synths | — |
| "drums / beats / kick / snare / hat" | drums-and-percussion | — |
| "arpeggio / chord / sequence / generative / random" | midi-tools | — |
| "meter / gain / routing / utility / organize" | utility-and-workflow | — |
| "dark / ethereal / aggressive / lo-fi / cinematic" | presets-by-vibe | (then load the relevant device file) |
| "sample / one-shot / loop / IR / convolution" | samples-and-irs | — |
| "what M4L devices do I have for X" | (search relevant category) | utility-and-workflow |

## Scope Notes

- **[universal]** files: synths-native, eq-and-filtering (native sections), dynamics-and-punch (native sections), space-and-depth (native sections), movement-and-modulation (native sections)
- **[user-library]** files: All M4L device entries, drums-and-percussion (kit guide), samples-and-irs, presets-by-vibe, utility-and-workflow (M4L sections), synths-m4l, spectral-and-weird (M4L sections)
- Always `search_browser` to verify M4L device availability before attempting to load
- The atlas is a strong hint system, not a guarantee — when in doubt, discover via `get_device_parameters`

## M4L Collection Mapping

| Collection | Location in User Library | Atlas Coverage |
|-----------|------------------------|----------------|
| CLX_01 (QOL GUI) | MAX MONTY/_CLX_01 | utility-and-workflow |
| CLX_02 (FX) | MAX MONTY/_CLX_02 | dynamics, distortion, space, eq, movement |
| CLX_03 (MIDI) | MAX MONTY/_CLX_03 | midi-tools |
| CLX_04 (GEN) | MAX MONTY/_CLX_04 | spectral-and-weird, synths-m4l |
| CLX_05 (MOD) | MAX MONTY/_CLX_05 | movement-and-modulation |
| Fors | MAX MONTY/M4L_fors | synths-m4l, space-and-depth |
| Mutable Instruments | MAX MONTY/M4L_Mutable Instruments | synths-m4l, midi-tools |
| Sonus Dept | MAX MONTY/M4L_Sonus Dept | synths-m4l, spectral-and-weird |
| Confetti | MAX MONTY/M4L_Confetti | spectral-and-weird |
| J74 | MAX MONTY/M4L_J74 | midi-tools |
| Isotonik | MAX MONTY/M4L_Isotonik Studios | spectral-and-weird |
| Altar of Wisdom | MAX MONTY/M4L_Altar of Wisdom | spectral-and-weird |
| Oscilloscopemusic | MAX MONTY/M4L_Oscilloscopemusic | spectral-and-weird |
| Soundmanufacture | MAX MONTY/M4L_Soundmanufacture | midi-tools |
| Robert Henke | MAX MONTY/Robert Henke | utility-and-workflow, spectral-and-weird |
| Suzuki Kentaro | MAX MONTY/M4L_Suzuki Kentaro | utility-and-workflow |
| trnr | MAX MONTY/m4l_2024/_CLX_02/trnr | drums-and-percussion, distortion-and-character |
| pATCHES | MAX MONTY/M4L_pATCHES | utility-and-workflow |
| S8JFOU | MAX MONTY/M4L_S8JFOU | utility-and-workflow |
| alexkid | MAX MONTY/M4L_alexkid | utility-and-workflow |
| Slink | MAX MONTY/M4L_Slink Devices | movement-and-modulation |
| Iris | MAX MONTY/rem4llives | movement-and-modulation |
| All MIDI Tools | MAX MONTY/2024_august | midi-tools |
| Encoder Audio Mojo | MAX MONTY/_CLX_02/Encoder Audio Mojo | distortion-and-character, samples-and-irs |
