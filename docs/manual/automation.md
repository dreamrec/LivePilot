# Automation

LivePilot has 8 automation tools covering clip envelopes, arrangement automation, 16 curve types, and 15 named recipes. This chapter covers all of it.

---

## Two Types of Automation

### Clip automation (session clips)

Automation envelopes attached to session clips. Each clip can automate any parameter on its track.

```
set_clip_automation(
    track_index=0,
    clip_index=0,
    parameter_type="device",
    device_index=0,
    parameter_index=3,
    points=[
        {"time": 0.0, "value": 0.2},
        {"time": 4.0, "value": 0.8},
        {"time": 8.0, "value": 0.2}
    ]
)
```

### Arrangement automation (arrangement clips)

Automation written directly into the arrangement timeline.

```
set_arrangement_automation(
    track_index=0,
    clip_index=0,
    parameter_type="volume",
    points=[
        {"time": 0.0, "value": 0.5},
        {"time": 16.0, "value": 0.85}
    ]
)
```

### Parameter types

Both tools use the same `parameter_type` system:

| Type | What it automates | Extra params needed |
|------|------------------|-------------------|
| `"volume"` | Track volume fader | — |
| `"panning"` | Track pan | — |
| `"send"` | Send level | `send_index` (0=A, 1=B, ...) |
| `"device"` | Any device parameter | `device_index` + `parameter_index` |

---

## 16 Curve Types

`apply_automation_shape` generates a curve and writes it to a clip envelope in one call:

```
apply_automation_shape(
    track_index=0,
    clip_index=0,
    parameter_type="device",
    device_index=0,
    parameter_index=3,
    curve_type="sine",
    cycles=2.0,
    min_value=0.2,
    max_value=0.8
)
```

### Basic curves

| Type | Shape | Best for |
|------|-------|----------|
| `linear` | Straight ramp up or down | Fades, simple builds |
| `exponential` | Slow start, fast finish | Natural-feeling volume ramps |
| `logarithmic` | Fast start, slow finish | Frequency sweeps (matches hearing) |
| `s_curve` | Smooth S-shape | Crossfades, gentle transitions |
| `sine` | Smooth wave | LFO-style modulation |
| `sawtooth` | Ramp + reset | Rhythmic filter sweeps |
| `spike` | Sharp peak | Accent hits, transient emphasis |
| `square` | On/off | Gating, tremolo |
| `steps` | Staircase | Stepped filter, quantized modulation |

### Organic curves

| Type | Shape | Best for |
|------|-------|----------|
| `perlin` | Smooth random noise | Organic drift, subtle movement |
| `brownian` | Drunken walk | Unpredictable but continuous motion |
| `spring` | Damped oscillation | Bouncing effects, elastic releases |

### Shape curves

| Type | Shape | Best for |
|------|-------|----------|
| `bezier` | Custom control points | Precise custom shapes |
| `easing` | 8 sub-types (ease_in, ease_out, bounce, elastic, ...) | UI-style motion curves |

### Algorithmic curves

| Type | Shape | Best for |
|------|-------|----------|
| `euclidean` | Evenly-spaced hits | Rhythmic gating patterns |
| `stochastic` | Probability-based | Generative, evolving textures |

### Preview without writing

```
generate_automation_curve(curve_type="perlin", length=16.0, resolution=64)
→ points: [{time: 0.0, value: 0.45}, {time: 0.25, value: 0.52}, ...]
```

Returns the curve as point data without writing it to a clip. Use this to preview shapes before committing.

---

## 15 Named Recipes

`apply_automation_recipe` applies a pre-built automation pattern:

```
apply_automation_recipe(
    track_index=0,
    clip_index=0,
    parameter_type="device",
    recipe="filter_sweep_up"
)
```

### The recipes

| Recipe | What it does |
|--------|-------------|
| `filter_sweep_up` | Low-pass filter opens gradually over the clip |
| `filter_sweep_down` | Low-pass filter closes gradually |
| `dub_throw` | Delay send spikes briefly then cuts — classic dub echo |
| `tape_stop` | Pitch drops to zero — tape machine stopping effect |
| `build_rise` | Multiple params rise together for tension build |
| `sidechain_pump` | Volume ducks rhythmically — sidechain compression feel |
| `fade_in` | Volume ramps from silence |
| `fade_out` | Volume ramps to silence |
| `tremolo` | Volume oscillates at rate — classic tremolo |
| `auto_pan` | Pan sweeps left-right rhythmically |
| `stutter` | Rapid volume gating — glitch/stutter effect |
| `breathing` | Volume swells and recedes — breathing rhythm |
| `washout` | Reverb/delay sends increase while volume drops |
| `vinyl_crackle` | Noise parameter rises then falls — vinyl texture |
| `stereo_narrow` | Stereo width narrows to mono then widens back |

### Spectral suggestions

```
analyze_for_automation(track_index=0)
→ suggestions: [
    {parameter: "Filter 1 Freq", recipe: "filter_sweep_up", reason: "static spectrum — movement needed"},
    {parameter: "Send A", recipe: "breathing", reason: "dry signal — add spatial depth"}
]
```

Uses spectral analysis (when the M4L analyzer is available) to suggest which parameters would benefit from automation and which recipes fit.

---

## Workflow: Adding Movement to a Static Sound

### 1. Check what needs movement

```
analyze_for_automation(track_index=2)
→ "Filter is static at 800Hz — consider filter_sweep_up or perlin modulation"
```

### 2. Apply a recipe

```
apply_automation_recipe(
    track_index=2,
    clip_index=0,
    parameter_type="device",
    device_index=0,
    parameter_index=3,
    recipe="filter_sweep_up"
)
```

### 3. Or use a curve for more control

```
apply_automation_shape(
    track_index=2,
    clip_index=0,
    parameter_type="device",
    device_index=0,
    parameter_index=3,
    curve_type="perlin",
    min_value=0.3,
    max_value=0.7
)
```

### 4. Listen and adjust

Fire the clip and listen. If the sweep is too dramatic, narrow the `min_value`/`max_value` range. If it's too predictable, try `brownian` instead of `perlin`.

---

## Workflow: Building a Transition

Transitions need multiple parameters moving at once. Layer automation across several tracks:

```
# Build: filter opens, reverb increases, volume rises
apply_automation_recipe(track_index=0, clip_index=0, parameter_type="device", recipe="build_rise")
apply_automation_recipe(track_index=1, clip_index=0, parameter_type="send", send_index=0, recipe="fade_in")

# Drop: everything resets
# (Use new clips in the next scene with different automation)
```

---

## Managing Automation

### Read existing envelopes

```
get_clip_automation(track_index=0, clip_index=0)
→ envelopes: [{parameter: "Volume", point_count: 8}, {parameter: "Filter Freq", point_count: 24}]
```

### Clear automation

```
clear_clip_automation(track_index=0, clip_index=0)
→ clears ALL envelopes on the clip

clear_clip_automation(track_index=0, clip_index=0, parameter_type="device", device_index=0, parameter_index=3)
→ clears only that specific parameter's envelope
```

---

## Tips

- **Recipes are starting points.** Apply one, listen, then adjust the envelope points manually if needed.
- **Perlin and brownian are your friends for organic movement.** Static sounds with subtle random modulation feel alive.
- **Layer automation across tracks for transitions.** A build isn't one parameter moving — it's five parameters coordinated.
- **Use generate_automation_curve to preview.** See the shape before writing it.
- **analyze_for_automation tells you what needs movement.** Don't automate randomly — let the spectral analysis guide you.

---

Next: [Composition & Arrangement](composition.md) | Back to [Manual](index.md)
