# Device Affordance Schema

Affordance packets describe WHAT a device is for, WHEN to reach for it,
and WHEN it's a trap — in structured YAML that the director reads
during Phase 3 plan generation and Phase 6 execution.

Files live in:

```
livepilot/skills/livepilot-core/references/affordances/
├── devices/<slug>.yaml       # per-device affordance
└── _schema.md                # this file
```

Affordance packets COMPLEMENT the Device Atlas. The atlas knows what
devices exist, their URIs, their presets, their `signature_techniques`.
The affordance packets add the musical-judgment layer: which device
is the right tool for which feeling, in which context.

## Loading

The director loads an affordance packet when:

1. A candidate plan proposes loading or parameter-tuning that device
2. A concept packet's `reach_for` list names the device
3. The user explicitly requests a device ("load an Echo")

The packet's fields populate the plan's description ("use Echo for dub
tail, not bright slap") and filter out misuse ("Echo on dense high-hat
patterns is risky per the affordance").

## Schema

```yaml
# REQUIRED
id: str                          # e.g. "echo"
name: str                        # human-readable, e.g. "Echo"
type: effect | instrument | utility | rack
category: str                    # e.g. "delay", "filter", "synth", "physical_model"
aliases: list[str]               # alternate names (e.g. "ping pong delay" for Echo in mode)
atlas_search_query: str          # search hint — actual URI must be resolved via
                                  # search_browser(query=this) at runtime. The atlas
                                  # is the source of truth; hardcoding a URI here
                                  # would rot on atlas updates.

# What this device is FOR musically
musical_roles: list[str]
  # e.g. "dub space", "rhythm shadow", "tail harvesting"
  # These map onto the sonic_identity fields of concept packets.

# When this device is a strong choice
strong_for: list[str]
  # e.g. "widening sparse material", "implied groove without extra notes"
  # Each entry should describe a musical situation, not a genre name.

# When this device is a trap
risky_for: list[str]
  # e.g. "dense high-hat patterns", "muddy low-end sources"
  # Specific situations where the device DEGRADES the result.

# Parameter ranges with musical consequence
subtle_ranges:                    # what "just audible" sounds like
  <param_name>: [low, high]       # e.g. feedback: [0.15, 0.30]
moderate_ranges:                  # what "obviously there" sounds like
  <param_name>: [low, high]
aggressive_ranges:                # what "signature / dramatic" sounds like
  <param_name>: [low, high]

# Device pairings
pairings:                         # devices that work well in a chain
  - device: str                   # pair device name
    order: before | after | parallel
    purpose: str                  # why the pairing works

# Anti-pairings
anti_pairings: list[str]          # device combinations that conflict or cancel

# Post-load verification
remeasure: list[str]
  # Which diagnostics to run after this device is loaded or adjusted.
  # e.g. "spectral_balance", "low_headroom", "groove_motion", "plugin_health"

# How this device interacts with the 4 dimensions
dimensional_impact:
  structural: str                 # "low" | "moderate" | "high" | "none"
  rhythmic: str
  timbral: str
  spatial: str

# Which concept-packet aesthetics name this device in their reach_for
appears_in_packets:
  artists: list[str]
  genres: list[str]

# Free-form prose for the director to read when composing plan descriptions
notes: str
```

## Field rules

- `atlas_search_query` is a SEARCH HINT, not a URI. The actual URI is
  resolved at runtime via `search_browser(query=atlas_search_query)`.
  If the search returns multiple matches, the director picks the
  first match whose name or URI substring equals `id` (case-insensitive).
- `parameter_name` values in `subtle_ranges` / `moderate_ranges` /
  `aggressive_ranges` may differ from the parameter names that
  `get_device_parameters` returns (display name vs. internal name).
  Always resolve via `get_device_parameters` at runtime; the affordance
  YAML names are advisory, not canonical.
- `subtle_ranges` / `moderate_ranges` / `aggressive_ranges` are
  advisory numeric bands. Always confirm parameter range via
  `get_device_parameters` — these bands are for HUMAN-readable
  "what this sounds like" hints, NOT for automation-recipe bounds.
- `dimensional_impact` uses `"low"` / `"moderate"` / `"high"` / `"none"`
  — not numeric. This maps onto the four-move-rule's dimension axis.
- `remeasure` should name metrics / tools that the director is
  expected to run post-load. Listing `plugin_health` is mandatory for
  any AU/VST device (see CLAUDE.md memory).
- `pairings` and `anti_pairings` describe DEVICE-level relationships,
  not genre-level ones. A pairing like "Auto Filter before Echo for
  dub sweeps" lives here; a packet's `reach_for` list lives in
  concept/.

## Scope for PR 3

The initial affordance set covers the 20 devices most-referenced across
concept packets:

1. Echo
2. Auto Filter
3. Convolution Reverb
4. Hybrid Reverb  (if enriched in atlas; else skip)
5. Drift
6. Corpus
7. Granulator III
8. Simpler
9. Wavetable
10. Operator
11. Ping Pong Delay
12. Saturator
13. Redux (if enriched in atlas; else Vinyl Distortion)
14. Utility
15. EQ Eight
16. Compressor
17. Glue Compressor
18. Chorus-Ensemble
19. Shifter
20. Poli

## Sync with atlas

The atlas already has `signature_techniques` for 47 devices. Affordance
YAMLs SHOULD NOT duplicate those — instead, `notes` can reference them
via `See atlas signature_techniques for recipes.`

Keep the axes distinct:
- **Atlas** = what exists, what presets are available, what recipes
  work on this device
- **Affordance** = when to reach for this device, when to avoid it,
  how its parameters translate to musical consequence
