# §7.3 — Layer Accumulation Rubric

Mechanical checks on track count and per-role volume balance, derived from
CLAUDE.md §7.3 ("no layer accumulation with low volume — 5–6 GREAT layers
prominent > 12 mediocre layers buried") and the track-meter hierarchy
feedback memory.

This rubric is graded by `mcp_server.grader.client.evaluate("layer_accumulation", state)`.
All checks are pure Python — zero LLM calls, zero token cost.

## Inputs

The grader expects a `state` dict shaped like:

```
{
  "tracks": [
    {
      "index": int,
      "name": str,
      "mixer": {"volume": 0.0–1.0, "panning": -1.0–1.0},
      "devices": [{"class_name": str, ...}, ...],
      "meter": {"peak": 0.0–1.0} | None,   # optional
    }, ...
  ],
}
```

In production this comes from `get_session_info` + per-track `get_track_info`
+ optional `get_track_meters`. In tests, synthesize the dict directly.

## Criteria

### `track_count_within_limit`

Total non-master, non-return tracks under the sustainable threshold.

- ≤ 8 tracks → **pass**
- 9–11 tracks → **warn** (approaching the §7.3 ceiling)
- ≥ 12 tracks → **fail** (delete buried layers, feature 5–6 great ones)

### `no_extreme_buried_track`

Any track with `mixer.volume < 0.15` is a buried layer that should be
deleted unless it's explicitly tagged ghost. Track-name keyword match:
`ghost`, `_g`, `gh `.

- All buried tracks are ghost-tagged → **pass**
- Any non-ghost track at volume < 0.15 → **fail** with track names

### `role_volume_hierarchy`

Per-track role inferred via `infer_role` from `audit/checks.py`. Volume
must land within the role's permitted band:

| Role  | Band         | Why |
|-------|--------------|-----|
| kick  | [0.60, 0.85] | anchor — must dominate |
| bass  | [0.60, 0.85] | anchor — must carry |
| snare | [0.55, 0.80] | groove |
| hat   | [0.40, 0.70] | groove — often quieter |
| perc  | [0.40, 0.65] | groove |
| lead  | [0.50, 0.80] | accent / anchor |
| vox   | [0.55, 0.85] | anchor |
| pad   | [0.25, 0.50] | atmosphere — hide, don't dominate |
| atmos | [0.25, 0.45] | atmosphere |
| fx    | [0.30, 0.70] | variable |
| unknown | [0.30, 0.80] | generous default |

- All tracks within role band → **pass**
- Any track outside band → **warn** (not blocking — could be deliberate;
  the grader flags it for review, not auto-undo)

## What this rubric does NOT check

§5 layer-by-layer precision (timbre, sequence, stereo, modulation, automation)
— that's `audit_layer` territory and gets its own rubric in Phase 2. This
rubric is intentionally narrow: it catches the **layer accumulation**
anti-pattern only.
