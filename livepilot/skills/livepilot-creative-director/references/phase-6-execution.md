# Phase 6 — Execution Contracts (v1.20+)

Full contracts for the 10 semantic moves shipped in v1.20.0, plus the
escape-hatch policy for patterns not yet covered. Read this alongside
the Phase 6 decision table in `SKILL.md`.

Every NEW move listed here takes its user targets via
`apply_semantic_move(move_id, mode, args)`, where `args` is threaded
into the compiler's kernel as `kernel["seed_args"]`. The pre-v1.20 33
moves (mix / arrangement / transition / sound_design / performance /
sample families) still read only from `session_info` and ignore args.

---

## Routing family (v1.20 commit 1)

### `build_send_chain`

Load an ordered device chain onto a return track. The Basic Channel /
dub-techno / ambient send-architecture primitive.

| Field | Type | Required | Notes |
|---|---|---|---|
| `return_track_index` | int | yes | 0 = Return A, 1 = Return B, ... (0-based) |
| `device_chain` | list[str] | yes | Device names in load order. Duplicates allowed (e.g., two Echos stacked). |

Compiled steps (per device in order, then a final verify read):

1. `find_and_load_device(track_index=-(return_track_index+1), device_name=<name>, allow_duplicate=True)`
2. ... (one per device)
3. `get_track_info(track_index=-(return_track_index+1))` — read-only verify.

Risk: **medium** (return chains affect every track routing sends there).
Protect: `low_end=0.6` (dub returns can accumulate sub mud).
Family: `device_creation`.

**Typical caller:** "build me a Basic Channel dub architecture on
Return A" → build_send_chain({return_track_index: 0, device_chain:
["Echo", "Auto Filter", "Convolution Reverb"]}).

---

### `configure_send_architecture`

Set send levels across a set of source tracks in a single move.

| Field | Type | Required | Notes |
|---|---|---|---|
| `source_track_indices` | list[int] | yes | 0-based; negative indices for returns |
| `send_index` | int | yes | Which send slot (0 = Send A, 1 = Send B, ...) |
| `levels` | list[float] | yes | 0.0-1.0. Must be same length as source_track_indices. Out-of-range values are clamped with a warning. |

Compiled steps: one `set_track_send` per (track, level) pair.

Risk: **low**. Protect: `clarity=0.5` (overdone sends muddy the mix).
Family: `mix`.

**Typical caller:** "route all percussion to the dub reverb at -10 dB" →
configure_send_architecture({source_track_indices: [2, 3, 4], send_index: 0, levels: [0.35, 0.35, 0.35]}).

---

### `set_track_routing`

Rewire a track's output routing. Useful for setting up bus architectures
("Sends Only") or routing a track to a specific return.

| Field | Type | Required | Notes |
|---|---|---|---|
| `track_index` | int | yes | 0-based; negative for returns |
| `output_routing_type` | str | at least one of output_* required | e.g., "Sends Only", "Master" |
| `output_routing_channel` | str | | Display name from Live (e.g., "Post Mixer") |

Compiled steps: single `set_track_routing` call.

Risk: **medium** (a bad routing silences or feedback-loops audio).
Protect: `clarity=0.5`. Family: `mix`.

**Typical caller:** "send track 0 to bus-only so it only feeds the return" →
set_track_routing({track_index: 0, output_routing_type: "Sends Only"}).

---

## Device-mutation family (v1.20 commit 2)

### `configure_device`

Reconfigure an existing device in bulk — set N parameters in one
undoable move. The ergonomic replacement for a chain of
`set_device_parameter` raw calls.

| Field | Type | Required | Notes |
|---|---|---|---|
| `track_index` | int | yes | Negative allowed (returns, master=-1000) |
| `device_index` | int | yes | Position in the track's chain |
| `param_overrides` | dict[str, Any] | yes | `{param_name: value}`. At least one entry required. |

Compiled steps: single `batch_set_parameters` call. Each
`{param_name, value}` pair is normalized into Live's preferred shape
(`parameter_name` key).

Risk: **low**. Protect: `{}` — caller declares via the specific
param_overrides. Family: `sound_design`.

**Preset library note (v1.21 scope):** the plan originally called for
`preset_name` + an affordance-YAML library. v1.20 ships `param_overrides`
only — once a preset library lands, the preset simply resolves to the
same dict and the move contract stays identical.

**Typical caller:** apply an affordance preset (affordance YAML →
resolved param dict) → configure_device({track_index: -1, device_index: 0,
param_overrides: {"Decay Time": 4000.0, "Dry/Wet": 0.35, "Size": 1.0}}).

---

### `remove_device`

Delete a device with a required audit reason. Destructive but undoable
via Live's undo stack.

| Field | Type | Required | Notes |
|---|---|---|---|
| `track_index` | int | yes | |
| `device_index` | int | yes | |
| `reason` | str | **yes** | Non-empty, non-whitespace. Destructive ops must be justified. |

Compiled steps:

1. `delete_device(track_index, device_index)`
2. `add_session_memory(category="device_removal", content="Removed track=<ti> device_index=<di>: <reason>")`

Risk: **medium**. Protect: `signal_integrity=0.9` (live signal-path
removal can silence audio). Family: `sound_design`.

---

## Content family (v1.20 commit 3)

### `load_chord_source`

Create a named MIDI clip at a specific slot with chord voicing notes.
Feeds a `build_send_chain` return chain for dub-chord workflows.

| Field | Type | Required | Notes |
|---|---|---|---|
| `track_index` | int | yes | |
| `clip_slot` | int | yes | Non-negative |
| `notes` | list[dict] | yes | `[{pitch, start_time, duration, velocity?, probability?}]`; non-empty |
| `name` | str | yes | Non-whitespace |
| `length_beats` | float | no | Default 4.0 (one bar 4/4) |

Compiled steps (ordered, all remote_command):

1. `create_clip(track_index, clip_index=clip_slot, length=length_beats)`
2. `add_notes(track_index, clip_index=clip_slot, notes=...)`
3. `set_clip_name(track_index, clip_index=clip_slot, name=...)`

Risk: **low**. Protect: `cohesion=0.6`. Family: `sound_design`.

---

### `create_drum_rack_pad`

Add one pad (chain) to a Drum Rack, loading a sample + setting Snap=0
post-load. Wraps the Live 12.4 native `replace_sample_native` flow.
Build kits one pad at a time à la Dilla.

| Field | Type | Required | Notes |
|---|---|---|---|
| `track_index` | int | yes | Track containing the Drum Rack |
| `pad_note` | int | yes | MIDI 0-127. Standard drum map: 36=Kick, 38=Snare, 42=CHH, 46=OHH. |
| `file_path` | str | yes | Absolute path to the audio file |
| `rack_device_index` | int | no | Auto-detects first Drum Rack if omitted |
| `chain_name` | str | no | Display name for the new chain |

Compiled steps: single `add_drum_rack_pad` call (backend=`mcp_tool`,
async — it composes insert_rack_chain + set_drum_chain_note +
insert_device + replace_sample_native + hygiene internally).

Risk: **low**. Family: `device_creation`.

---

## Metadata family (v1.20 commit 4)

### `configure_groove`

Assign a groove to clips and optionally tune its timing_amount. The
Dilla-swing primitive; pre-resolve the groove_id via `list_grooves()`
before calling.

| Field | Type | Required | Notes |
|---|---|---|---|
| `track_index` | int | yes | |
| `clip_indices` | list[int] | yes | Non-empty; non-negative entries |
| `groove_id` | int | yes | From `list_grooves()` |
| `timing_amount` | float | no | 0.0-1.0; clamped with warning on out-of-range |

Compiled steps:

1. `assign_clip_groove(track_index, clip_index=<each>, groove_id)` — one per clip
2. `set_groove_params(groove_id, timing_amount=<clamped>)` — only if provided

Risk: **low**. Protect: `clarity=0.5`. Family: `arrangement`.

---

### `set_scene_metadata`

Set scene name / color / tempo in one conditional move. Each field is
optional; at least one required.

| Field | Type | Required | Notes |
|---|---|---|---|
| `scene_index` | int | yes | Non-negative |
| `name` | str | no | |
| `color_index` | int | no | |
| `tempo` | float | no | BPM. **set_scene_tempo DOES affect playback timing on scene fire — use cautiously inside a performance context.** |

Compiled steps: one tool call per provided field (`set_scene_name` /
`set_scene_color` / `set_scene_tempo`). Zero-field calls reject.

Risk: **low**. Family: `arrangement`.

---

### `set_track_metadata` (bundled rename + color)

Set track name and/or color in a single bundled move. Both fields are
optional; at least one required.

| Field | Type | Required | Notes |
|---|---|---|---|
| `track_index` | int | yes | Negative indices for returns allowed |
| `name` | str | no | |
| `color_index` | int | no | |

Compiled steps: one call per provided field. Zero-field calls reject.

Risk: **low**. Family: `mix`.

**Why bundled?** Phase 6 usage always pairs rename with color (name is
what the director types; color carries aesthetic meaning — green for
analog, orange for harmonic, etc.). The bundled move replaces two
raw calls with one named intent.

---

## Escape-hatch policy (v1.20, phased cutover)

When no semantic move in Phase 6's decision table covers the pattern,
the director may fall back to raw tool calls — BUT only with the
mandatory logging contract below. The hatch is explicitly a phased-
cutover transitional state; v1.21+ closes patterns as they accumulate
tech_debt log entries.

### The three mandatory calls (in order)

1. **The raw tool call itself** — e.g., `set_device_parameter(...)`,
   `load_browser_item(...)`, `create_take_lane(...)`.
2. **`add_session_memory(category="move_executed", ...)`** — one-line
   ledger entry summarizing the move's family + target + brief
   identity. Anti-repetition is blind without this.
3. **`add_session_memory(category="tech_debt", ...)`** — tracking log
   that names the uncovered pattern. Use wording specific enough that
   v1.21 release planning can turn it into a semantic move.

### Example: the director rewires a track group (pattern not yet in decision table)

```python
# Raw tool call (no semantic move covers "rename track group")
ableton.send_command("set_group_name", {"group_index": 0, "name": "DRUMS"})

# Mandatory 2/3: ledger marker for anti-repetition
add_session_memory(
    category="move_executed",
    content="mix:group-0 rename to DRUMS — brief: stem organization for export",
    engine="creative_director",
)

# Mandatory 3/3: tech_debt log so v1.21 can close the gap
add_session_memory(
    category="tech_debt",
    content="no semantic_move for: rename a track group (set_group_name). "
            "Suggested move: set_group_metadata, family=mix, "
            "seed_args={group_index, name?, color_index?}",
    engine="creative_director",
)
```

### What the two entries do differently

| Entry | Consumer | Scrub? |
|---|---|---|
| `move_executed` | Anti-repetition Phase 3 recency table | Stable — never scrubbed |
| `tech_debt` | v1.21 release planning | Scrubbed per release after closure |

### Honesty rules for the hatch

- **Don't treat the hatch as a shortcut.** Default is always
  `apply_semantic_move`. The hatch is the branch you take once you've
  checked the decision table AND run
  `list_semantic_moves(domain="<family>")`.
- **Don't skip the tech_debt log because "that pattern is weird."**
  Weird patterns are exactly the ones v1.21 should close. The log is
  the input.
- **Don't use `category="tech_debt"` for other purposes.** It's a
  specific contract with release planning. Use a different category
  (e.g., `observation`) for general session notes.

---

## Affordance-preset resolution (bridge into configure_device)

When the plan calls for a preset-style reconfiguration (e.g., "dub
cathedral reverb", "warm tape saturation"), resolve the preset via the
affordance YAML at `livepilot-core/references/affordances/devices/<slug>.yaml`
BEFORE calling `configure_device`. The resolved preset becomes the
`param_overrides` dict:

```python
# 1. Resolve affordance → param dict (read-only filesystem lookup)
preset = load_affordance_preset("reverb", "dub-cathedral")
# preset = {"Decay Time": 4000.0, "Size": 1.0, "Dry/Wet": 0.35, ...}

# 2. Dispatch configure_device with the resolved dict
apply_semantic_move(
    "configure_device",
    mode="explore",
    args={
        "track_index": -1,
        "device_index": 0,
        "param_overrides": preset,
    },
)
```

A preset library is v1.21 scope. Until then, construct the
`param_overrides` dict inline from the affordance YAML or from the
concept packet's `sonic_fingerprint` hints.

---

## See also

- `SKILL.md` §Phase 6 — the entry-level decision table
- `references/anti-repetition-rules.md` §v1.20 update — how ledger
  entries feed the recency table
- `docs/plans/v1.20-structural-plan.md` — design rationale + §7 risks
