# Concept Packet Schema

Concept packets are structured YAML files that turn prose entries in
`artist-vocabularies.md` and `genre-vocabularies.md` into machine-readable
payloads the Creative Director compiles into briefs and diversity seeds.

Files live in:

```
livepilot/skills/livepilot-core/references/concepts/
├── artists/<slug>.yaml       # per-artist packets
├── genres/<slug>.yaml        # per-genre packets
└── _schema.md                # this file
```

The narrative .md files stay — they are human-facing overviews. The YAML
is the source-of-truth for director compilation.

## Loading

The director's Phase 1 concept-packet load step resolves user references
as follows:

1. Normalize the user's reference (artist or genre, lowercase, hyphenate spaces).
2. Check `artists/<slug>.yaml` first, then `genres/<slug>.yaml`.
3. If no exact match, check the `aliases` field of each packet.
4. If still no match, fall back to the narrative .md file and flag
   the packet as unstructured.

## Schema

```yaml
# REQUIRED
id: str                          # e.g. "dub_techno__basic_channel"
name: str                        # human-readable, e.g. "Basic Channel / Rhythm & Sound"
type: artist | genre | hybrid
aliases: list[str]               # alternate names for lookup (can be [])

# The sound IS — not what to do, what it sounds like
sonic_identity: list[str]        # bullet points describing the sound

# What the director reaches for — populates Phase 3 candidate pool
reach_for:
  instruments: list[str]         # Ableton/pack device names — must exist in atlas
  effects: list[str]             # effect device names
  packs: list[str]               # pack names for atlas_pack_info lookup
  utilities: list[str]           # Utility, Spectrum, EQ Eight, etc. for diagnostic chain

# Hard filter — candidate plans failing these get dropped in Phase 3
avoid: list[str]

# Stylistic tendencies — inform plan descriptions, not mandatory
rhythm_idioms: list[str]
harmony_idioms: list[str]
arrangement_idioms: list[str]
texture_idioms: list[str]

# For sample-heavy aesthetics — what the sample plays in the track
sample_roles: list[str]          # texture_bed | transient_ghost | dub_tail_source | ...

# Cross-reference to the technique catalog
key_techniques:
  - name: str                    # e.g. "dub_throw"
    source: str                  # sample-techniques.md | sound-design-deep.md | atlas
    device: str                  # when source is atlas — the device name
    notes: str                   # optional inline hint

# How the director weights the goal vector for this aesthetic
evaluation_bias:
  target_dimensions:             # weights (sum loosely to 1.0)
    depth: float
    groove: float
    motion: float
    contrast: float
    novelty: float
    cohesion: float
    clarity: float
  protect:                       # floor values — below these = identity break
    clarity: float
    cohesion: float
    low_end: float               # packets that require bass weight

# How the director biases the 3-plan family diversity
move_family_bias:
  favor: list[str]               # families to prefer (subset of the six canonical)
  deprioritize: list[str]        # families to avoid unless user explicitly asks

# 4-move rule coverage expectation
dimensions_in_scope: list[str]   # from {structural, rhythmic, timbral, spatial}
dimensions_deprioritized: list[str]  # from the same set — for narrow-idiom packets
                                      # (dub-techno deprioritizes rhythmic; ambient
                                      # deprioritizes rhythmic + structural; beat-
                                      # focused deprioritizes spatial)

# Default novelty budget when no user framing is present
novelty_budget_default: float    # 0.0 – 1.0

# Tempo hints — optional, mainly for genre packets
tempo_hint:
  min: int
  max: int
  time_signature: str            # "4/4", "2-step", etc.

# Cross-links
canonical_artists: list[str]     # genre packets list representative artists
canonical_genres: list[str]      # artist packets list their genres (slugs from genres/)

# Free-form prose the director can read when composing the brief identity line
notes: str
```

## Field rules

- `type: artist` packets MUST have `canonical_genres` populated.
  `canonical_artists` is optional for artist packets (typically `[]` or
  omitted — putting `[]` is redundant but accepted for schema symmetry).
- `type: genre` packets MUST have `canonical_artists` populated.
  `canonical_genres` is optional for genre packets.
- `move_family_bias.favor` + `move_family_bias.deprioritize` should not
  overlap.
- `dimensions_in_scope` + `dimensions_deprioritized` should together
  cover all four dimensions (structural / rhythmic / timbral / spatial).
- `evaluation_bias.target_dimensions` weights should loosely sum to 1.0
  (not strictly enforced — they're ratios).
- `evaluation_bias.protect` floor values are 0.0 – 1.0 where higher
  means more strictly protected.
- `novelty_budget_default` applies only when the user's turn contains
  NO explicit framing mapping to the `creative-brief-template.md`
  novelty table. User framing always wins.
- `tempo_hint` should reflect the actual artist's / genre's canonical
  tempo range, not a genre-general band. If you set 120-130 for an
  artist whose tracks are 95-110, the agent will send the wrong tempo.

## Relationship to narrative .md files

- `artist-vocabularies.md` — narrative overview, human-facing
- `genre-vocabularies.md` — narrative overview, human-facing
- `concepts/artists/*.yaml` — structured, machine-loaded
- `concepts/genres/*.yaml` — structured, machine-loaded

When a new artist or genre is added, update BOTH. The narrative .md
gives a reader an overview; the YAML gives the director an executable
packet. They should not disagree.

## Sync check (future CI)

A test in `tests/test_concept_packets.py` should verify:

1. Every `### <name>` heading in `artist-vocabularies.md` has a matching
   `artists/<slug>.yaml`.
2. Every `## <name>` heading in `genre-vocabularies.md` has a matching
   `genres/<slug>.yaml`.
3. Every YAML parses cleanly and has all required fields.
4. Every `canonical_artists` / `canonical_genres` cross-reference
   resolves to an existing packet.
5. Every `key_techniques.name` resolves to either a line in
   `sample-techniques.md` / `sound-design-deep.md` or an atlas
   `signature_techniques` entry.
