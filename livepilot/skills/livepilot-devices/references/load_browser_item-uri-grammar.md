# `load_browser_item` URI Grammar

> Reference for the URI strings accepted by `load_browser_item(track_index, uri, ...)`.
> Resolves the BUG-2026-04-22 #14 friction (URI format was undocumented and required reverse-engineering).

## TL;DR

URIs are produced by `search_browser` / `get_browser_items` / `get_browser_tree` — never invent them by hand. The format is `query:<Top-Level-Folder>#<Item-Identifier>`. Three known forms in the wild:

| Form | Example | When you'll see it |
|---|---|---|
| **File ID** | `query:Drums#FileId_29738` | Browser items that resolve to a file in Live's installed packs (samples, presets, kits). The numeric FileId is stable across sessions on the same machine. |
| **Bare name** | `query:Synths#Operator` | Native devices and effects whose name is unique within the folder. Most built-in instruments. |
| **Path-like** | `query:UserLibrary#Samples:Splice:Filename.wav` | Items inside the User Library or other deep folder paths. The fragment uses `:` as a path separator within the URI's hash. |

## Discovery recipe

You almost never need to construct a URI from scratch. Always:

1. **Search:** `search_browser(path="Drums", name_filter="909 Core")` — returns each match with its exact `uri` field.
2. **Or browse:** `get_browser_tree()` for the top-level structure; `get_browser_items(path="Drums")` to drill down. Items include their URI.
3. **Use the URI verbatim:** pass the exact string from the result to `load_browser_item(uri=...)`. Do not modify, normalize, or reconstruct it.

## Why three forms exist

Live's browser is backed by multiple resolvers under the hood:

- **Pack content** is keyed by an internal FileId from a per-machine SQLite index — fast lookup, opaque names.
- **Native devices** are addressed by their stable English class name within their folder.
- **User Library / Samples** items use a path-style fragment because they're filesystem-rooted, not pack-indexed.

The URI you receive from search/browse already has the correct form for that item — there is no "preferred" or "canonical" form, only "the one Live's browser knows."

## What goes wrong if you guess

- **Guessed FileId**: silently fails or loads the wrong sample.
- **Guessed bare name** for a non-unique item: loads whatever Live's matcher hits first (e.g., `query:Synths#Drift` may match a `Drift Pad Wonk Bass.wav` sample before the `Drift` synth — see the `find_and_load_device` warning in `livepilot-devices` SKILL).
- **Path with wrong separator** (using `/` instead of `:`): URI parses but resolves to nothing.
- **Stale FileId** copied from a different machine: stale FileIds aren't portable.

## Top-level folders (current Live 12.4)

| Folder | Typical content |
|---|---|
| `Sounds` | Genre-organized presets across all native synths |
| `Drums` | Drum Racks, drum kits, percussion one-shots |
| `Instruments` | Synths, samplers, instrument racks (top-level entries) |
| `Audio Effects` | Reverb, delay, compressor, EQ, saturator, etc. |
| `MIDI Effects` | Arpeggiator, chord, scale, random, MPE Tools |
| `Max for Live` | Native + installed M4L devices |
| `Plug-ins` | Installed AU/VST plugins |
| `Clips` | Sample loops + MIDI clips that ship with packs |
| `Samples` | The big one — ~22,000 individual audio files |
| `Packs` | Pack-level entries that resolve to internal preset/sample lists |
| `User Library` | Your personal saved devices, racks, samples, sets |
| `Current Project` | Items in the current Live set's project folder |

## Behaviour after load (BUG-2026-04-22 #16)

`load_browser_item` is context-dependent — same URI, different result:

- **Empty track:** creates a Simpler with the sample loaded (instruments load directly).
- **Track with an instrument already:** drops the new device after the existing one (Live's "load to selected" behavior).
- **Track with a Drum Rack:** the FIRST `load_browser_item` of a sample creates a chain on note 36; **every subsequent call REPLACES that chain** instead of appending to the next pad. To build a kit pad-by-pad, use `add_drum_rack_pad(track_index, pad_note, file_path)` instead — it does the chain + note + Simpler + sample sequence atomically per pad.

See the "Custom Drum Rack Construction" section in `livepilot-devices` SKILL for the canonical kit-build flow.

## Role-aware defaults (BUG-2026-04-22 #17 + #18)

`load_browser_item(role=...)` applies post-load Simpler defaults so the loaded sample plays correctly without per-bug-memory hand-tweaking:

| Role | Snap | Volume | Trigger Mode | Root note |
|---|---|---|---|---|
| `"drum"` | 0 | 0 dB | 0 (Trigger / one-shot) | C1 (36) |
| `"melodic"` | 1 | 0 dB | 1 (Gate / held) | C3 (60) |
| `"texture"` | 0 | -6 dB | 1 (Gate) | C3 (60) |

Omit `role` to keep Live's raw defaults (Volume=-12 dB, Snap=1, root=C3). Useful when loading a non-Simpler device or when you want the legacy behavior.

## Trigger Mode polarity (BUG-2026-04-22 #9)

Reverse from intuition: `Trigger Mode value=0` is **Trigger** (one-shot), `value=1` is **Gate** (held). The `role="drum"` default sets it to 0, the others to 1.
