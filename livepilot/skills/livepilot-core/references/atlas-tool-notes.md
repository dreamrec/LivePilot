# Atlas Tool Notes

Implementation history and rationale for `mcp_server/atlas/tools.py`
tools. The tool docstrings carry the operational contract (params,
return shape, behavior); this file carries the bug history and
step-by-step internals that explain *why* a tool behaves a certain way,
for when that context is actually needed.

## `scan_full_library` — scan cap history

`max_per_category` defaults to 25000, matching the remote script's own
default. The original hardcoded 1000 cap silently truncated large
categories in browser-tree (alphabetical) order — e.g. `drum_kits`
stopped at "Crash" (0 kicks, 2 hats), and the `samples` category alone
has ~22,000 items per the browser tree, so a "1000 samples" count was
wrong by a factor of 22 (BUG-2026-04-22#12). Raise the cap further for
even bigger libraries; lower it for fast smoke scans.

`truncated_categories` / `stats.category_truncated` are persisted into
`device_atlas.json` so `AtlasManager` can warn future
`atlas_search`/`atlas_suggest` calls that touch a truncated category
without requiring a fresh scan first (P3-47).

Scans always write to the user atlas path
(`~/.livepilot/atlas/device_atlas.json`), never the bundled baseline —
this keeps personal inventories (packs, user_library, plugins) out of
the repo and surviving npm updates (v1.22.0). Enrichments are still
read from the bundled package.

## `atlas_describe_chain` — internals

Free-text → chain proposal pipeline, mirroring `splice_describe_sound`
for the device library (`atlas_chain_suggest` is the structured-input
sibling — role + genre instead of a sentence):

1. Parse role hints from the description (bass/lead/pad/keys/
   percussion/drums/vocal/fx keyword buckets)
2. Parse aesthetic hints — artist names map to genre/character tags
   (cross-reference `artist-vocabularies.md`), plus explicit genre
   names and character words (warm/cold/bright/dark/lush/...)
3. Search the atlas (factory + user overlay namespaces) with those terms
4. Propose the top devices per role with brief rationale, then take the
   top suggestion per role as a simple ordered `chain_proposal`

Does not autoload anything — the caller reviews/adjusts, then executes
via `load_browser_item` + effects.

## `atlas_techniques_for_device` — index

Backed by the reverse-index file `device_techniques_index.json`
(auto-generated from the knowledge base — regenerate via the
post-v1.17 reverse-index builder script when adding new techniques;
rare, since most additions happen through enrichment YAMLs that the
index reads directly). `kind` values: `signature_technique` (from the
device's own atlas entry), `sample_technique` (from
`sample-techniques.md`), `sound_design_principle` (from
`sound-design-deep.md`).

## `atlas_search` — overlay budget split

Searches both the bundled factory atlas (5,264 browser entries / 33 packs) and
the user-local overlay corpus (`~/.livepilot/atlas-overlays/` — user-
scanned Max devices, racks, plugin presets, AI-synthesized plugin
identity YAMLs). When both sources have hits, `limit` splits roughly
50/50 (factory gets the rounding-up extra slot); a source with zero
hits doesn't consume budget. M4L pack instruments occasionally carry a
bogus `query:Synths#` URI in the atlas — `atlas_search` clears it and
surfaces a `browse_hint` so callers don't hit `INVALID_PARAM` from
`load_browser_item` (LIVE#3).
