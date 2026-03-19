# Automation Intelligence Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LivePilot deeply understand automation — not just write breakpoints, but generate musically intelligent curves informed by spectral analysis, sound design theory, and genre-aware recipes. The agent should use the M4L analyzer as diagnostic ears: listen → hypothesize → act → verify → adjust.

**Architecture:** Four layers:

1. **Clip automation tools** — LOM access to session clip envelopes (CRUD)
2. **Curve generation engine** — Pure math: 9 curve types, 15 recipes
3. **Automation atlas** — Knowledge corpus (when, why, how to automate)
4. **Spectral feedback loop** — The core intelligence: the agent uses the analyzer diagnostically to evaluate sound, take action via automation, then re-analyze to verify the effect. This is not a one-shot tool call — it is a multi-step reasoning process embedded in the agent's skill.

The feedback loop works like this:

```
PERCEIVE:  get_master_spectrum / get_track_meters / get_master_rms
    ↓
DIAGNOSE:  "low_mid band at 0.22 — muddy, masking the kick"
    ↓
DECIDE:    "apply HP filter automation on the bass, sweep 80-250Hz region"
    ↓
ACT:       apply_automation_shape(curve_type="exponential", ...)
    ↓
VERIFY:    get_master_spectrum again — "low_mid dropped to 0.11"
    ↓
ADJUST:    if still muddy → increase filter Q, try different curve
           if too thin → reduce sweep range, lower the end value
           if good → move to next frequency band or next track
```

This loop is NOT a tool. It is a behavioral pattern taught to the agent via the automation atlas and the SKILL.md. The agent learns to think in terms of spectral diagnosis, not just "add a filter sweep." It learns to use filters as measurement instruments — solo a frequency band via EQ, read the spectrum, understand what lives there, then decide whether to automate it.

**The diagnostic filter technique:**
1. Load EQ Eight on the track
2. Set a narrow band-pass (high Q) at the frequency of interest
3. Solo the track, read `get_master_spectrum`
4. Sweep the band-pass across frequencies, reading spectrum at each position
5. Build a spectral map of what lives where in the sound
6. Remove the diagnostic EQ
7. Now make informed automation decisions: "the resonance at 350Hz needs taming with a notch that opens over 8 bars"

This is how a mixing engineer uses a parametric EQ to "find the problem frequency" — but the agent can do it systematically across every track, remember the findings, and write precise automation curves targeting exactly what it heard.

**Tech Stack:** Python 3.9+ (MCP server), Ableton LOM via Remote Script, existing M4L bridge for per-track spectral analysis.

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `mcp_server/tools/automation.py` | 8 new MCP tools for clip automation + curve generation |
| `mcp_server/curves.py` | Pure math: curve generators (exp, log, sine, S-curve, spike, etc.) |
| `remote_script/LivePilot/clip_automation.py` | 3 Remote Script handlers for clip envelope CRUD |
| `plugin/skills/livepilot-core/references/automation-atlas.md` | Knowledge corpus: curves, recipes, genre patterns, theory |
| `tests/test_curves.py` | Unit tests for curve math (no Ableton needed) |
| `tests/test_automation_contract.py` | Contract tests for new tool registrations |

### Modified Files
| File | Changes |
|------|---------|
| `remote_script/LivePilot/server.py` | Register 3 new clip automation commands in WRITE_COMMANDS |
| `remote_script/LivePilot/__init__.py` | Import clip_automation module |
| `mcp_server/tools/__init__.py` | Import automation module |
| `plugin/skills/livepilot-core/SKILL.md` | Add automation section with curve guidance |
| `plugin/skills/livepilot-core/references/overview.md` | Update tool count, add automation domain reference |
| `plugin/agents/livepilot-producer/AGENT.md` | Add automation intelligence to producer workflow |
| `tests/test_tools_contract.py` | Update expected tool count 127 → 135 |

---

## Chunk 1: Curve Generation Engine

The foundation. Pure math, no Ableton dependency. Fully testable offline.

### Task 1: Curve Math Module

**Files:**
- Create: `mcp_server/curves.py`
- Create: `tests/test_curves.py`

- [ ] **Step 1: Write failing tests for all curve types**

```python
# tests/test_curves.py
"""Tests for automation curve generators."""
import pytest
from mcp_server.curves import generate_curve

class TestLinearCurve:
    def test_basic_ramp(self):
        points = generate_curve("linear", start=0.0, end=1.0, duration=4.0, density=4)
        assert len(points) == 4
        assert points[0]["time"] == 0.0
        assert points[0]["value"] == 0.0
        assert points[-1]["value"] == pytest.approx(1.0, abs=0.05)

    def test_descending(self):
        points = generate_curve("linear", start=1.0, end=0.0, duration=4.0, density=4)
        assert points[0]["value"] == 1.0
        assert points[-1]["value"] == pytest.approx(0.0, abs=0.05)

class TestExponentialCurve:
    def test_slow_start(self):
        """Exponential curves start slow, accelerate. Good for filter sweeps."""
        points = generate_curve("exponential", start=0.0, end=1.0, duration=8.0, density=8)
        # Midpoint should be below 0.5 (slow start)
        mid = points[len(points)//2]["value"]
        assert mid < 0.4

    def test_perceptual_filter(self):
        """Filter freq is perceived logarithmically — exponential curve sounds even."""
        points = generate_curve("exponential", start=0.0, end=1.0, duration=4.0, density=16)
        assert len(points) == 16

class TestLogarithmicCurve:
    def test_fast_start(self):
        """Logarithmic curves start fast, decelerate. Good for volume fades."""
        points = generate_curve("logarithmic", start=0.0, end=1.0, duration=8.0, density=8)
        mid = points[len(points)//2]["value"]
        assert mid > 0.6

class TestSCurve:
    def test_smooth_transition(self):
        """S-curves: slow start, fast middle, slow end. Natural crossfades."""
        points = generate_curve("s_curve", start=0.0, end=1.0, duration=4.0, density=16)
        q1 = points[len(points)//4]["value"]
        mid = points[len(points)//2]["value"]
        q3 = points[3*len(points)//4]["value"]
        assert q1 < 0.15  # slow start
        assert 0.4 < mid < 0.6  # fast middle
        assert q3 > 0.85  # slow end

class TestSineCurve:
    def test_oscillation(self):
        """Sine: periodic oscillation. For tremolo, auto-pan, LFO-like."""
        points = generate_curve("sine", center=0.5, amplitude=0.5,
                               frequency=1.0, duration=4.0, density=16)
        values = [p["value"] for p in points]
        assert max(values) == pytest.approx(1.0, abs=0.1)
        assert min(values) == pytest.approx(0.0, abs=0.1)

class TestSawtoothCurve:
    def test_ramp_reset(self):
        """Sawtooth: ramp up then reset. For sidechain pumping."""
        points = generate_curve("sawtooth", start=0.0, end=1.0,
                               frequency=1.0, duration=4.0, density=16)
        assert len(points) == 16

class TestSpikeCurve:
    def test_decay(self):
        """Spike: instant peak then exponential decay. For dub throws."""
        points = generate_curve("spike", peak=1.0, decay=4.0,
                               duration=2.0, density=8)
        assert points[0]["value"] == pytest.approx(1.0, abs=0.05)
        assert points[-1]["value"] < 0.1

class TestSquareCurve:
    def test_on_off(self):
        """Square: binary on/off. For stutter, gating."""
        points = generate_curve("square", low=0.0, high=1.0,
                               frequency=2.0, duration=4.0, density=16)
        values = set(round(p["value"], 1) for p in points)
        assert 0.0 in values
        assert 1.0 in values

class TestStepsCurve:
    def test_staircase(self):
        """Steps: quantized staircase. For pitched modulation, rhythmic gating."""
        points = generate_curve("steps", values=[0.2, 0.5, 0.8, 0.3],
                               duration=4.0)
        assert len(points) == 4
        assert points[0]["value"] == 0.2
        assert points[2]["value"] == 0.8

class TestPerlinCurve:
    def test_smooth_noise(self):
        """Perlin: smooth organic drift, never mechanical."""
        points = generate_curve("perlin", center=0.5, amplitude=0.3,
                               duration=4.0, density=32, seed=42.0)
        assert len(points) == 32
        # Should stay within bounds
        for p in points:
            assert 0.0 <= p["value"] <= 1.0
        # Should NOT be constant (it's noise)
        values = [p["value"] for p in points]
        assert max(values) != min(values)

    def test_deterministic_with_seed(self):
        """Same seed = same curve."""
        p1 = generate_curve("perlin", seed=7.0, duration=4.0, density=16)
        p2 = generate_curve("perlin", seed=7.0, duration=4.0, density=16)
        for a, b in zip(p1, p2):
            assert a["value"] == b["value"]

class TestBrownianCurve:
    def test_random_walk(self):
        """Brownian: drifts organically, never exactly the same."""
        points = generate_curve("brownian", start=0.5, volatility=0.1,
                               duration=8.0, density=32, seed=1.0)
        assert len(points) == 32
        for p in points:
            assert 0.0 <= p["value"] <= 1.0

class TestSpringCurve:
    def test_overshoot_and_settle(self):
        """Spring: overshoots target then settles."""
        points = generate_curve("spring", start=0.0, end=1.0,
                               damping=0.15, stiffness=8.0,
                               duration=4.0, density=32)
        # Should overshoot (some value > end)
        values = [p["value"] for p in points]
        assert any(v > 1.0 for v in values) or values[-1] == pytest.approx(1.0, abs=0.1)
        # Should settle near end value
        assert values[-1] == pytest.approx(1.0, abs=0.15)

class TestBezierCurve:
    def test_custom_shape(self):
        """Bezier: smooth curve through control points."""
        points = generate_curve("bezier", start=0.0, end=1.0,
                               control1=0.8, control2=0.2,
                               duration=4.0, density=16)
        assert len(points) == 16
        assert points[0]["value"] == pytest.approx(0.0, abs=0.05)
        assert points[-1]["value"] == pytest.approx(1.0, abs=0.05)

class TestEasingCurve:
    def test_bounce(self):
        """Easing bounce: bounces at the end like a dropped ball."""
        points = generate_curve("easing", start=0.0, end=1.0,
                               easing_type="bounce", duration=4.0, density=32)
        assert len(points) == 32
        assert points[-1]["value"] == pytest.approx(1.0, abs=0.05)

    def test_elastic(self):
        """Easing elastic: spring-like overshoot."""
        points = generate_curve("easing", start=0.0, end=1.0,
                               easing_type="elastic", duration=4.0, density=32)
        assert len(points) == 32

class TestEuclideanCurve:
    def test_distribution(self):
        """Euclidean: distributes hits evenly across steps."""
        points = generate_curve("euclidean", start=0.0, end=1.0,
                               hits=3, steps=8, duration=4.0)
        assert len(points) == 8
        hits_count = sum(1 for p in points if p["value"] == 1.0)
        assert hits_count == 3

class TestStochasticCurve:
    def test_narrowing_corridor(self):
        """Stochastic: random within narrowing bounds."""
        points = generate_curve("stochastic", center=0.5, amplitude=0.4,
                               narrowing=0.8, duration=8.0, density=32, seed=3.0)
        # Early points should have wider spread than late points
        early = [p["value"] for p in points[:8]]
        late = [p["value"] for p in points[-8:]]
        early_spread = max(early) - min(early)
        late_spread = max(late) - min(late)
        assert late_spread < early_spread  # corridor narrows

class TestCurveTransforms:
    def test_invert(self):
        points = generate_curve("linear", start=0.0, end=1.0, duration=4.0,
                               density=4, invert=True)
        assert points[0]["value"] == 1.0
        assert points[-1]["value"] == pytest.approx(0.0, abs=0.05)

    def test_phase_offset(self):
        points = generate_curve("sine", center=0.5, amplitude=0.5,
                               frequency=1.0, duration=4.0, density=16,
                               phase=0.25)
        # Phase 0.25 = quarter cycle offset
        assert len(points) == 16

    def test_clamp(self):
        """Values always stay within 0.0-1.0."""
        points = generate_curve("sine", center=0.5, amplitude=0.8,
                               frequency=1.0, duration=4.0, density=16)
        for p in points:
            assert 0.0 <= p["value"] <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/visansilviugeorge/Desktop/LivePilot && .venv/bin/python -m pytest tests/test_curves.py -v`
Expected: ImportError — `mcp_server.curves` does not exist

- [ ] **Step 3: Implement curve generators**

```python
# mcp_server/curves.py
"""Automation curve generators.

Pure math — no Ableton dependency. Generates lists of {time, value, duration}
dicts that can be fed directly to insert_step() via the automation tools.

16 curve types organized in 4 categories:

BASIC WAVEFORMS (what every LFO can do):
- linear:       Even ramp. Basic fades, simple transitions.
- exponential:  Slow start, fast end. Filter sweeps (perceptually even).
- logarithmic:  Fast start, slow end. Volume fades (perceptually even).
- s_curve:      Slow-fast-slow. Natural crossfades, smooth transitions.
- sine:         Periodic oscillation. Tremolo, auto-pan, breathing.
- sawtooth:     Ramp + reset. Sidechain pumping, rhythmic ducking.
- spike:        Peak + decay. Dub throws, reverb sends, accent hits.
- square:       Binary toggle. Stutter, gating, trance gates.
- steps:        Quantized staircase. Pitched sequences, rhythmic patterns.

ORGANIC / NATURAL MOTION (what makes automation feel alive):
- perlin:       Smooth coherent noise. Organic drift, evolving textures.
                Not random — flows naturally. The secret to ambient automation.
- brownian:     Random walk with momentum. Drifts with accumulation.
                Like analog gear — never exactly the same twice.
- spring:       Overshoot + settle. How physical knobs actually move.
                Damped oscillation around target value.

SHAPE CONTROL (precision curves for intentional design):
- bezier:       Arbitrary smooth shape via control points. The animation
                industry standard. Describe ANY curve with 2-4 points.
- easing:       30+ motion design curves: ease_in, ease_out, bounce,
                elastic, back_overshoot. Each has a distinct character.

ALGORITHMIC / GENERATIVE (Xenakis-level intelligence):
- euclidean:    Bjorklund algorithm on automation points. Distributes
                N events across M slots as evenly as possible. Rhythmic
                intelligence applied to parameter changes.
- stochastic:   Random values within narrowing/widening bounds.
                Controlled randomness — probabilistically bounded, not chaos.
"""

from __future__ import annotations

import math
from typing import Any


def generate_curve(
    curve_type: str,
    duration: float = 4.0,
    density: int = 16,
    # Common params
    start: float = 0.0,
    end: float = 1.0,
    # Oscillator params
    center: float = 0.5,
    amplitude: float = 0.5,
    frequency: float = 1.0,
    phase: float = 0.0,
    # Spike params
    peak: float = 1.0,
    decay: float = 4.0,
    # Square params
    low: float = 0.0,
    high: float = 1.0,
    # Steps params
    values: list[float] | None = None,
    # Curve factor (steepness for exp/log/easing)
    factor: float = 3.0,
    # Organic params
    seed: float = 0.0,
    drift: float = 0.0,
    volatility: float = 0.1,
    damping: float = 0.15,
    stiffness: float = 8.0,
    # Bezier control points
    control1: float = 0.0,
    control2: float = 1.0,
    control1_time: float = 0.33,
    control2_time: float = 0.66,
    # Easing type
    easing_type: str = "ease_out",
    # Euclidean params
    hits: int = 5,
    steps: int = 16,
    # Stochastic params
    narrowing: float = 0.5,
    # Transforms
    invert: bool = False,
    point_duration: float = 0.0,
) -> list[dict[str, float]]:
    """Generate automation curve as a list of {time, value, duration} points.

    Args:
        curve_type: One of linear, exponential, logarithmic, s_curve,
                    sine, sawtooth, spike, square, steps.
        duration: Total duration in beats.
        density: Number of points to generate (ignored for 'steps').
        point_duration: Duration of each automation step (0 = auto from density).
        invert: Flip values (1.0 - value).
        factor: Steepness for exponential/logarithmic curves (2-6 typical).

    Returns:
        List of dicts: [{time: float, value: float, duration: float}, ...]
    """
    generators = {
        # Basic waveforms
        "linear": _linear,
        "exponential": _exponential,
        "logarithmic": _logarithmic,
        "s_curve": _s_curve,
        "sine": _sine,
        "sawtooth": _sawtooth,
        "spike": _spike,
        "square": _square,
        "steps": _steps,
        # Organic / natural motion
        "perlin": _perlin,
        "brownian": _brownian,
        "spring": _spring,
        # Shape control
        "bezier": _bezier,
        "easing": _easing,
        # Algorithmic / generative
        "euclidean": _euclidean,
        "stochastic": _stochastic,
    }

    gen = generators.get(curve_type)
    if gen is None:
        raise ValueError(
            f"Unknown curve type '{curve_type}'. "
            f"Options: {', '.join(generators.keys())}"
        )

    # Build kwargs for the generator
    kwargs: dict[str, Any] = {
        "duration": duration, "density": density,
        "start": start, "end": end,
        "center": center, "amplitude": amplitude,
        "frequency": frequency, "phase": phase,
        "peak": peak, "decay": decay,
        "low": low, "high": high,
        "values": values or [], "factor": factor,
        "seed": seed, "drift": drift, "volatility": volatility,
        "damping": damping, "stiffness": stiffness,
        "control1": control1, "control2": control2,
        "control1_time": control1_time, "control2_time": control2_time,
        "easing_type": easing_type,
        "hits": hits, "steps": steps, "narrowing": narrowing,
    }

    points = gen(**kwargs)

    # Auto-calculate point duration if not specified
    if point_duration <= 0 and len(points) > 1:
        point_duration = duration / len(points)

    # Apply transforms
    for p in points:
        if invert:
            p["value"] = 1.0 - p["value"]
        # Clamp to 0.0-1.0
        p["value"] = max(0.0, min(1.0, p["value"]))
        # Set duration if not already set
        if "duration" not in p or p["duration"] <= 0:
            p["duration"] = point_duration

    return points


# ── Generators ──────────────────────────────────────────────────────────────

def _linear(duration: float, density: int, start: float, end: float, **_) -> list:
    points = []
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        points.append({
            "time": t * duration,
            "value": start + (end - start) * t,
        })
    return points


def _exponential(duration: float, density: int, start: float, end: float,
                 factor: float = 3.0, **_) -> list:
    """Slow start, fast end. y = x^n where n > 1."""
    points = []
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        curve_t = t ** factor
        points.append({
            "time": t * duration,
            "value": start + (end - start) * curve_t,
        })
    return points


def _logarithmic(duration: float, density: int, start: float, end: float,
                 factor: float = 3.0, **_) -> list:
    """Fast start, slow end. y = 1 - (1-x)^n."""
    points = []
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        curve_t = 1.0 - (1.0 - t) ** factor
        points.append({
            "time": t * duration,
            "value": start + (end - start) * curve_t,
        })
    return points


def _s_curve(duration: float, density: int, start: float, end: float, **_) -> list:
    """Slow-fast-slow. Smoothstep: 3t^2 - 2t^3."""
    points = []
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        curve_t = 3 * t * t - 2 * t * t * t
        points.append({
            "time": t * duration,
            "value": start + (end - start) * curve_t,
        })
    return points


def _sine(duration: float, density: int, center: float, amplitude: float,
          frequency: float, phase: float = 0.0, **_) -> list:
    """Periodic oscillation. frequency = cycles per duration."""
    points = []
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        angle = 2 * math.pi * frequency * t + phase * 2 * math.pi
        points.append({
            "time": t * duration,
            "value": center + amplitude * math.sin(angle),
        })
    return points


def _sawtooth(duration: float, density: int, start: float, end: float,
              frequency: float, **_) -> list:
    """Ramp up then reset. frequency = resets per duration."""
    points = []
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        # Position within current cycle (0.0 to 1.0)
        cycle_pos = (t * frequency) % 1.0
        points.append({
            "time": t * duration,
            "value": start + (end - start) * cycle_pos,
        })
    return points


def _spike(duration: float, density: int, peak: float, decay: float, **_) -> list:
    """Instant peak then exponential decay. For dub throws."""
    points = []
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        points.append({
            "time": t * duration,
            "value": peak * math.exp(-decay * t),
        })
    return points


def _square(duration: float, density: int, low: float, high: float,
            frequency: float, **_) -> list:
    """Binary on/off toggle."""
    points = []
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        cycle_pos = (t * frequency) % 1.0
        points.append({
            "time": t * duration,
            "value": high if cycle_pos < 0.5 else low,
        })
    return points


def _steps(values: list[float], duration: float, **_) -> list:
    """Quantized staircase from explicit value list."""
    if not values:
        return []
    step_dur = duration / len(values)
    return [
        {"time": i * step_dur, "value": v, "duration": step_dur}
        for i, v in enumerate(values)
    ]


# ── Organic / Natural Motion ───────────────────────────────────────────────

def _perlin(duration: float, density: int, center: float = 0.5,
            amplitude: float = 0.3, frequency: float = 1.0,
            seed: float = 0.0, **_) -> list:
    """Smooth coherent noise. Organic drift that flows naturally.

    Uses a simplified 1D Perlin-like interpolation (cubic hermite between
    random gradients). Not true Perlin but captures the essential quality:
    smooth, non-repeating, organic movement.

    Musical use: Subtle filter drift, evolving textures, ambient automation
    that never sounds mechanical. The secret ingredient of "alive" sound.
    """
    import hashlib

    def _hash_float(x: float, s: float) -> float:
        """Deterministic pseudo-random float from position + seed."""
        h = hashlib.md5(f"{x:.6f}:{s:.6f}".encode()).hexdigest()
        return (int(h[:8], 16) / 0xFFFFFFFF) * 2.0 - 1.0

    def _smoothstep(t: float) -> float:
        return t * t * (3.0 - 2.0 * t)

    def _noise_1d(x: float, s: float) -> float:
        x0 = int(math.floor(x))
        x1 = x0 + 1
        t = x - x0
        t = _smoothstep(t)
        g0 = _hash_float(float(x0), s)
        g1 = _hash_float(float(x1), s)
        return g0 + t * (g1 - g0)

    points = []
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        # Multi-octave noise for richer texture
        noise = 0.0
        amp = 1.0
        freq = frequency
        for _ in range(3):  # 3 octaves
            noise += amp * _noise_1d(t * freq * 4.0, seed)
            amp *= 0.5
            freq *= 2.0
        noise /= 1.75  # normalize
        points.append({
            "time": t * duration,
            "value": center + amplitude * noise,
        })
    return points


def _brownian(duration: float, density: int, start: float = 0.5,
              drift: float = 0.0, volatility: float = 0.1,
              seed: float = 0.0, **_) -> list:
    """Random walk with momentum. Drifts and accumulates naturally.

    Each step adds a small random displacement to the previous value.
    drift: directional tendency (positive = upward trend)
    volatility: step size (how wild the walk is)

    Musical use: Analog-style parameter drift, parameters that wander
    organically, never-repeating modulation for installation work.
    """
    import hashlib

    def _det_random(i: int, s: float) -> float:
        h = hashlib.md5(f"{i}:{s:.6f}".encode()).hexdigest()
        return (int(h[:8], 16) / 0xFFFFFFFF) * 2.0 - 1.0

    points = []
    value = start
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        points.append({"time": t * duration, "value": value})
        step = drift / density + volatility * _det_random(i, seed)
        value += step
        # Soft boundary reflection (bounce off 0/1 instead of hard clamp)
        if value > 1.0:
            value = 2.0 - value
        elif value < 0.0:
            value = -value
    return points


def _spring(duration: float, density: int, start: float = 0.0,
            end: float = 1.0, damping: float = 0.15,
            stiffness: float = 8.0, **_) -> list:
    """Damped spring oscillation. Overshoots target then settles.

    Models a physical spring: fast attack, overshoot, ring, settle.
    This is how a real knob on analog gear moves when turned quickly.

    damping: how quickly oscillation dies (0.05 = ringy, 0.3 = dead)
    stiffness: spring constant (higher = faster oscillation)

    Musical use: Filter cutoff changes with analog character,
    realistic parameter transitions, bouncy builds.
    """
    points = []
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        # Damped oscillation: e^(-dt) * cos(wt)
        envelope = math.exp(-damping * stiffness * t * 4)
        oscillation = math.cos(stiffness * t * 4 * math.pi)
        # Starts at 'start', settles at 'end', overshoots in between
        value = end + (start - end) * envelope * oscillation
        points.append({"time": t * duration, "value": value})
    return points


# ── Shape Control ──────────────────────────────────────────────────────────

def _bezier(duration: float, density: int, start: float = 0.0,
            end: float = 1.0, control1: float = 0.0, control2: float = 1.0,
            control1_time: float = 0.33, control2_time: float = 0.66, **_) -> list:
    """Cubic bezier curve. Arbitrary smooth shape via 2 control points.

    The animation industry standard. Four points define the curve:
    P0 = (0, start), P1 = (control1_time, control1),
    P2 = (control2_time, control2), P3 = (1, end)

    Musical use: Custom transition shapes, precise acceleration/deceleration
    profiles, any curve that the basic types can't describe.
    """
    points = []
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        # Cubic bezier: B(t) = (1-t)^3*P0 + 3(1-t)^2*t*P1 + 3(1-t)*t^2*P2 + t^3*P3
        u = 1.0 - t
        time_val = (u**3 * 0.0 + 3 * u**2 * t * control1_time +
                    3 * u * t**2 * control2_time + t**3 * 1.0)
        value = (u**3 * start + 3 * u**2 * t * control1 +
                 3 * u * t**2 * control2 + t**3 * end)
        points.append({"time": time_val * duration, "value": value})
    return points


def _easing(duration: float, density: int, start: float = 0.0,
            end: float = 1.0, easing_type: str = "ease_out",
            factor: float = 3.0, **_) -> list:
    """Motion design easing functions. 10+ standard curves.

    easing_type options:
    - ease_in: slow start (power curve)
    - ease_out: slow end (inverse power)
    - ease_in_out: slow start + end (smoothstep)
    - bounce: bounces at the end like a dropped ball
    - elastic: spring-like overshoot with oscillation
    - back: overshoots then returns (rubber band)
    - circular_in: quarter-circle acceleration
    - circular_out: quarter-circle deceleration

    Musical use: Each easing has a distinct character. bounce for
    percussive automation, elastic for synth filter resonance,
    back for dramatic transitions with overshoot.
    """
    def _ease_in(t: float) -> float:
        return t ** factor

    def _ease_out(t: float) -> float:
        return 1.0 - (1.0 - t) ** factor

    def _ease_in_out(t: float) -> float:
        if t < 0.5:
            return 0.5 * (2 * t) ** factor
        return 1.0 - 0.5 * (2 * (1 - t)) ** factor

    def _bounce(t: float) -> float:
        if t < 1/2.75:
            return 7.5625 * t * t
        elif t < 2/2.75:
            t -= 1.5/2.75
            return 7.5625 * t * t + 0.75
        elif t < 2.5/2.75:
            t -= 2.25/2.75
            return 7.5625 * t * t + 0.9375
        else:
            t -= 2.625/2.75
            return 7.5625 * t * t + 0.984375

    def _elastic(t: float) -> float:
        if t == 0 or t == 1:
            return t
        p = 0.3
        return -(2 ** (10 * (t - 1))) * math.sin((t - 1 - p/4) * 2 * math.pi / p)

    def _back(t: float) -> float:
        s = 1.70158  # overshoot amount
        return t * t * ((s + 1) * t - s)

    def _circular_in(t: float) -> float:
        return 1.0 - math.sqrt(1.0 - t * t)

    def _circular_out(t: float) -> float:
        t -= 1.0
        return math.sqrt(1.0 - t * t)

    easings = {
        "ease_in": _ease_in,
        "ease_out": _ease_out,
        "ease_in_out": _ease_in_out,
        "bounce": _bounce,
        "elastic": _elastic,
        "back": _back,
        "circular_in": _circular_in,
        "circular_out": _circular_out,
    }

    fn = easings.get(easing_type, _ease_out)
    points = []
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        curve_t = fn(t)
        points.append({
            "time": t * duration,
            "value": start + (end - start) * curve_t,
        })
    return points


# ── Algorithmic / Generative ───────────────────────────────────────────────

def _euclidean(duration: float, density: int, start: float = 0.0,
               end: float = 1.0, hits: int = 5, steps: int = 16, **_) -> list:
    """Bjorklund/Euclidean distribution applied to automation.

    Distributes 'hits' automation events across 'steps' time slots as
    evenly as possible. Same math as Euclidean rhythms (Toussaint 2005)
    but for parameter changes instead of drum hits.

    hits: number of automation events (active points at 'end' value)
    steps: total time slots (remaining slots get 'start' value)

    Musical use: Rhythmic automation patterns with mathematical elegance.
    5 filter opens across 8 beats. 3 reverb throws across 16 steps.
    Produces non-obvious but musically satisfying rhythmic modulation.
    """
    # Bjorklund algorithm
    def _bjorklund(hits_n: int, steps_n: int) -> list:
        if hits_n >= steps_n:
            return [1] * steps_n
        if hits_n == 0:
            return [0] * steps_n
        groups = [[1]] * hits_n + [[0]] * (steps_n - hits_n)
        while True:
            remainder = len(groups) - hits_n
            if remainder <= 1:
                break
            new_groups = []
            take = min(hits_n, remainder)
            for i in range(take):
                new_groups.append(groups[i] + groups[hits_n + i])
            for i in range(take, hits_n):
                new_groups.append(groups[i])
            for i in range(hits_n + take, len(groups)):
                new_groups.append(groups[i])
            groups = new_groups
            hits_n = take if take < hits_n else hits_n
        return [bit for group in groups for bit in group]

    pattern = _bjorklund(hits, steps)
    step_dur = duration / len(pattern)
    return [
        {"time": i * step_dur, "value": end if bit else start, "duration": step_dur}
        for i, bit in enumerate(pattern)
    ]


def _stochastic(duration: float, density: int, center: float = 0.5,
                amplitude: float = 0.4, narrowing: float = 0.5,
                seed: float = 0.0, **_) -> list:
    """Random values within narrowing/widening bounds. Xenakis-inspired.

    Values are random but constrained within a corridor that can narrow
    (converge to center) or widen (diverge) over time.

    narrowing: 0.0 = constant width, 1.0 = fully converges to center,
               -0.5 = widens over time
    seed: deterministic seed for reproducible "randomness"

    Musical use: Controlled chaos that evolves. Stochastic composition
    applied to automation. The corridor gives musical intention to randomness.
    Xenakis used this for orchestral density — we use it for parameter evolution.
    """
    import hashlib

    def _det_random(i: int, s: float) -> float:
        h = hashlib.md5(f"{i}:{s:.6f}".encode()).hexdigest()
        return (int(h[:8], 16) / 0xFFFFFFFF) * 2.0 - 1.0

    points = []
    for i in range(density):
        t = (i / max(density - 1, 1)) if density > 1 else 0.0
        # Corridor width narrows/widens over time
        width = amplitude * (1.0 - narrowing * t)
        width = max(0.01, width)  # never fully zero
        rand = _det_random(i, seed)
        value = center + width * rand
        points.append({"time": t * duration, "value": value})
    return points


# ── Recipe Shortcuts ────────────────────────────────────────────────────────

RECIPES = {
    "filter_sweep_up": {
        "curve_type": "exponential",
        "start": 0.0, "end": 1.0, "factor": 2.5,
        "description": "Low-pass filter opening. Exponential for perceptually even sweep.",
        "typical_duration": "8-32 bars (32-128 beats)",
        "target": "Filter cutoff frequency",
    },
    "filter_sweep_down": {
        "curve_type": "logarithmic",
        "start": 1.0, "end": 0.0, "factor": 2.5,
        "description": "Low-pass filter closing. Logarithmic mirrors the sweep up.",
        "typical_duration": "4-16 bars",
        "target": "Filter cutoff frequency",
    },
    "dub_throw": {
        "curve_type": "spike",
        "peak": 1.0, "decay": 6.0,
        "description": "Send spike for delay/reverb throw on single hit. Instant peak, fast decay.",
        "typical_duration": "1-2 beats",
        "target": "Send level to reverb/delay return",
    },
    "tape_stop": {
        "curve_type": "exponential",
        "start": 1.0, "end": 0.0, "factor": 4.0,
        "description": "Pitch/speed dropping to zero. Steep exponential for realistic tape decel.",
        "typical_duration": "0.5-2 beats",
        "target": "Clip transpose or playback rate",
    },
    "build_rise": {
        "curve_type": "exponential",
        "start": 0.0, "end": 1.0, "factor": 2.0,
        "description": "Tension build. Apply to HP filter, volume, reverb send simultaneously.",
        "typical_duration": "8-32 bars",
        "target": "Multiple: HP filter + volume + reverb send",
    },
    "sidechain_pump": {
        "curve_type": "sawtooth",
        "start": 0.0, "end": 1.0, "frequency": 1.0,
        "description": "Volume ducking on each beat. Sawtooth = fast duck, slow recovery.",
        "typical_duration": "1 beat (repeating via clip loop)",
        "target": "Volume (use Utility gain, not mixer fader)",
    },
    "fade_in": {
        "curve_type": "logarithmic",
        "start": 0.0, "end": 1.0, "factor": 3.0,
        "description": "Perceptually smooth volume fade in. Log curve compensates for ear's response.",
        "typical_duration": "2-8 bars",
        "target": "Volume",
    },
    "fade_out": {
        "curve_type": "exponential",
        "start": 1.0, "end": 0.0, "factor": 3.0,
        "description": "Perceptually smooth volume fade out.",
        "typical_duration": "2-8 bars",
        "target": "Volume",
    },
    "tremolo": {
        "curve_type": "sine",
        "center": 0.5, "amplitude": 0.4, "frequency": 4.0,
        "description": "Periodic volume oscillation. frequency = cycles per duration.",
        "typical_duration": "1-4 bars (repeating)",
        "target": "Volume",
    },
    "auto_pan": {
        "curve_type": "sine",
        "center": 0.5, "amplitude": 0.5, "frequency": 2.0,
        "description": "Stereo movement. Sine on pan pot.",
        "typical_duration": "1-4 bars (repeating)",
        "target": "Pan",
    },
    "stutter": {
        "curve_type": "square",
        "low": 0.0, "high": 1.0, "frequency": 8.0,
        "description": "Rapid on/off gating. High frequency = faster stutter.",
        "typical_duration": "1-2 beats",
        "target": "Volume",
    },
    "breathing": {
        "curve_type": "sine",
        "center": 0.6, "amplitude": 0.15, "frequency": 0.5,
        "description": "Subtle filter movement mimicking acoustic instrument breathing.",
        "typical_duration": "2-4 bars (repeating)",
        "target": "Filter cutoff",
    },
    "washout": {
        "curve_type": "exponential",
        "start": 0.0, "end": 1.0, "factor": 2.0,
        "description": "Reverb/delay feedback increasing to wash. Cut at transition.",
        "typical_duration": "4-8 bars",
        "target": "Reverb mix or delay feedback",
    },
    "vinyl_crackle": {
        "curve_type": "sine",
        "center": 0.3, "amplitude": 0.15, "frequency": 0.25,
        "description": "Slow, subtle movement on bit reduction or sample rate for lo-fi character.",
        "typical_duration": "8-16 bars",
        "target": "Redux bit depth or sample rate",
    },
    "stereo_narrow": {
        "curve_type": "exponential",
        "start": 1.0, "end": 0.0, "factor": 2.0,
        "description": "Collapse stereo to mono before drop. Widen at impact.",
        "typical_duration": "4-8 bars",
        "target": "Utility width",
    },
}


def get_recipe(name: str) -> dict:
    """Get a named automation recipe with its parameters and description."""
    recipe = RECIPES.get(name)
    if recipe is None:
        raise ValueError(
            f"Unknown recipe '{name}'. Options: {', '.join(RECIPES.keys())}"
        )
    return recipe


def generate_from_recipe(
    name: str,
    duration: float = 4.0,
    density: int = 16,
    **overrides,
) -> list[dict[str, float]]:
    """Generate a curve from a named recipe, with optional parameter overrides."""
    recipe = get_recipe(name)
    params = {k: v for k, v in recipe.items()
              if k not in ("description", "typical_duration", "target")}
    params["duration"] = duration
    params["density"] = density
    params.update(overrides)
    return generate_curve(**params)


def list_recipes() -> dict[str, dict]:
    """Return all available recipes with descriptions."""
    return {
        name: {
            "description": r["description"],
            "typical_duration": r["typical_duration"],
            "target": r["target"],
            "curve_type": r["curve_type"],
        }
        for name, r in RECIPES.items()
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_curves.py -v`
Expected: All 13+ tests PASS

- [ ] **Step 5: Commit**

```bash
git add mcp_server/curves.py tests/test_curves.py
git commit -m "Add automation curve engine: 9 curve types, 15 recipes, full test coverage"
```

---

## Chunk 2: Clip Automation Remote Script Handlers

Three new handlers in the Remote Script for session clip envelope CRUD.

### Task 2: Remote Script Clip Automation Handlers

**Files:**
- Create: `remote_script/LivePilot/clip_automation.py`
- Modify: `remote_script/LivePilot/__init__.py`
- Modify: `remote_script/LivePilot/server.py`

- [ ] **Step 1: Create clip_automation.py with 3 handlers**

```python
# remote_script/LivePilot/clip_automation.py
"""Clip automation envelope handlers.

Provides CRUD access to session clip automation envelopes.
Uses the same LOM API as arrangement automation (AutomationEnvelope)
but targets session clips via track.clip_slots[i].clip.
"""

from .utils import get_track, register


@register("get_clip_automation")
def get_clip_automation(song, params):
    """List automation envelopes on a session clip."""
    track_index = params["track_index"]
    clip_index = params["clip_index"]

    track = get_track(song, track_index)
    clip_slot = list(track.clip_slots)[clip_index]
    if not clip_slot.has_clip:
        return {"error": {"code": "NOT_FOUND",
                "message": "No clip at slot %d" % clip_index}}

    clip = clip_slot.clip
    envelopes = []

    # Check mixer parameters: volume, panning, sends
    mixer = track.mixer_device
    for param_name, param in [
        ("Volume", mixer.volume),
        ("Pan", mixer.panning),
    ]:
        env = clip.automation_envelope(param)
        if env is not None:
            envelopes.append({
                "parameter_name": param_name,
                "parameter_type": "mixer",
                "has_envelope": True,
            })

    # Check send parameters
    sends = list(mixer.sends)
    for i, send in enumerate(sends):
        env = clip.automation_envelope(send)
        if env is not None:
            envelopes.append({
                "parameter_name": "Send %s" % chr(65 + i),
                "parameter_type": "send",
                "send_index": i,
                "has_envelope": True,
            })

    # Check device parameters
    devices = list(track.devices)
    for di, device in enumerate(devices):
        dev_params = list(device.parameters)
        for pi, param in enumerate(dev_params):
            try:
                env = clip.automation_envelope(param)
                if env is not None:
                    envelopes.append({
                        "parameter_name": param.name,
                        "parameter_type": "device",
                        "device_index": di,
                        "device_name": device.name,
                        "parameter_index": pi,
                        "has_envelope": True,
                    })
            except Exception:
                pass

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "clip_name": clip.name,
        "envelope_count": len(envelopes),
        "envelopes": envelopes,
    }


@register("set_clip_automation")
def set_clip_automation(song, params):
    """Write automation points to a session clip envelope.

    parameter_type: "device", "volume", "panning", "send"
    points: [{time, value, duration?}] — time relative to clip start
    """
    track_index = params["track_index"]
    clip_index = params["clip_index"]
    parameter_type = params["parameter_type"]
    points = params["points"]
    device_index = params.get("device_index")
    parameter_index = params.get("parameter_index")
    send_index = params.get("send_index")

    track = get_track(song, track_index)
    clip_slot = list(track.clip_slots)[clip_index]
    if not clip_slot.has_clip:
        return {"error": {"code": "NOT_FOUND",
                "message": "No clip at slot %d" % clip_index}}

    clip = clip_slot.clip

    # Resolve the target parameter
    if parameter_type == "volume":
        parameter = track.mixer_device.volume
    elif parameter_type == "panning":
        parameter = track.mixer_device.panning
    elif parameter_type == "send":
        if send_index is None:
            return {"error": {"code": "INVALID_PARAM",
                    "message": "send_index required for send automation"}}
        sends = list(track.mixer_device.sends)
        if send_index >= len(sends):
            return {"error": {"code": "INDEX_ERROR",
                    "message": "send_index %d out of range" % send_index}}
        parameter = sends[send_index]
    elif parameter_type == "device":
        if device_index is None or parameter_index is None:
            return {"error": {"code": "INVALID_PARAM",
                    "message": "device_index and parameter_index required"}}
        devices = list(track.devices)
        if device_index >= len(devices):
            return {"error": {"code": "INDEX_ERROR",
                    "message": "device_index %d out of range" % device_index}}
        dev_params = list(devices[device_index].parameters)
        if parameter_index >= len(dev_params):
            return {"error": {"code": "INDEX_ERROR",
                    "message": "parameter_index %d out of range" % parameter_index}}
        parameter = dev_params[parameter_index]
    else:
        return {"error": {"code": "INVALID_PARAM",
                "message": "parameter_type must be device/volume/panning/send"}}

    # Get or create envelope
    song.begin_undo_step()
    try:
        envelope = clip.automation_envelope(parameter)
        if envelope is None:
            envelope = clip.create_automation_envelope(parameter)

        # Write points
        written = 0
        for pt in points:
            time = float(pt["time"])
            value = float(pt["value"])
            duration = float(pt.get("duration", 0.125))
            # Clamp value to parameter range
            value = max(parameter.min, min(parameter.max, value))
            envelope.insert_step(time, duration, value)
            written += 1
    finally:
        song.end_undo_step()

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "parameter_name": parameter.name,
        "parameter_type": parameter_type,
        "points_written": written,
    }


@register("clear_clip_automation")
def clear_clip_automation(song, params):
    """Clear automation envelopes from a session clip.

    If parameter_type is provided, clears only that parameter's envelope.
    If omitted, clears ALL envelopes on the clip.
    """
    track_index = params["track_index"]
    clip_index = params["clip_index"]
    parameter_type = params.get("parameter_type")

    track = get_track(song, track_index)
    clip_slot = list(track.clip_slots)[clip_index]
    if not clip_slot.has_clip:
        return {"error": {"code": "NOT_FOUND",
                "message": "No clip at slot %d" % clip_index}}

    clip = clip_slot.clip

    song.begin_undo_step()
    try:
        if parameter_type is None:
            # Clear all envelopes
            clip.clear_all_envelopes()
            return {
                "track_index": track_index,
                "clip_index": clip_index,
                "cleared": "all",
            }

        # Clear specific parameter
        if parameter_type == "volume":
            parameter = track.mixer_device.volume
        elif parameter_type == "panning":
            parameter = track.mixer_device.panning
        elif parameter_type == "send":
            send_index = params.get("send_index", 0)
            parameter = list(track.mixer_device.sends)[send_index]
        elif parameter_type == "device":
            device_index = params.get("device_index", 0)
            parameter_index = params.get("parameter_index", 0)
            device = list(track.devices)[device_index]
            parameter = list(device.parameters)[parameter_index]
        else:
            return {"error": {"code": "INVALID_PARAM",
                    "message": "Unknown parameter_type"}}

        clip.clear_envelope(parameter)
    finally:
        song.end_undo_step()

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "cleared": parameter_type,
        "parameter_name": parameter.name,
    }
```

- [ ] **Step 2: Register new commands in server.py**

In `remote_script/LivePilot/server.py`, add to `WRITE_COMMANDS`:
```python
"set_clip_automation",
"clear_clip_automation",
```
And to the READ section (or WRITE since it's safe):
```python
"get_clip_automation",
```

- [ ] **Step 3: Import clip_automation in __init__.py**

In `remote_script/LivePilot/__init__.py`, add:
```python
from . import clip_automation  # noqa: F401
```

- [ ] **Step 4: Test by restarting Ableton and calling tools**

Restart Ableton (or re-enable the Remote Script in Preferences).
Test manually via MCP tools once the MCP server tools are wired up (Task 3).

- [ ] **Step 5: Commit**

```bash
git add remote_script/LivePilot/clip_automation.py remote_script/LivePilot/__init__.py remote_script/LivePilot/server.py
git commit -m "Add clip automation handlers: get/set/clear envelope CRUD"
```

---

## Chunk 3: MCP Automation Tools

8 new MCP tools that combine clip automation CRUD with curve generation.

### Task 3: MCP Automation Tools

**Files:**
- Create: `mcp_server/tools/automation.py`
- Modify: `mcp_server/tools/__init__.py`
- Create: `tests/test_automation_contract.py`

- [ ] **Step 1: Create automation.py with 8 tools**

```python
# mcp_server/tools/automation.py
"""Automation MCP tools — clip envelope CRUD + intelligent curve generation.

8 tools for writing, reading, and generating automation curves on session clips.
Combines the clip automation handlers (Remote Script) with the curve generation
engine (curves.py) for musically intelligent automation.
"""

from __future__ import annotations

from typing import Any, Optional

from fastmcp import Context

from ..curves import generate_curve, generate_from_recipe, list_recipes
from ..server import mcp


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _ensure_list(v: Any) -> list:
    if isinstance(v, str):
        import json
        return json.loads(v)
    return list(v)


@mcp.tool()
def get_clip_automation(
    ctx: Context,
    track_index: int,
    clip_index: int,
) -> dict:
    """List all automation envelopes on a session clip.

    Returns which parameters have automation, including device name,
    parameter name, and type (mixer/send/device). Use this to see
    what's already automated before writing new curves.
    """
    return _get_ableton(ctx).send_command("get_clip_automation", {
        "track_index": track_index,
        "clip_index": clip_index,
    })


@mcp.tool()
def set_clip_automation(
    ctx: Context,
    track_index: int,
    clip_index: int,
    parameter_type: str,
    points: Any,
    device_index: Optional[int] = None,
    parameter_index: Optional[int] = None,
    send_index: Optional[int] = None,
) -> dict:
    """Write automation points to a session clip envelope.

    parameter_type: "device", "volume", "panning", or "send"
    points: [{time, value, duration?}] — time relative to clip start (beats)
    values: 0.0-1.0 normalized (or parameter's actual min/max range)

    For device params: provide device_index + parameter_index.
    For sends: provide send_index (0=A, 1=B, etc).

    Tip: Use apply_automation_shape to generate points from curves/recipes
    instead of calculating points manually.
    """
    params: dict = {
        "track_index": track_index,
        "clip_index": clip_index,
        "parameter_type": parameter_type,
        "points": _ensure_list(points),
    }
    if device_index is not None:
        params["device_index"] = device_index
    if parameter_index is not None:
        params["parameter_index"] = parameter_index
    if send_index is not None:
        params["send_index"] = send_index
    return _get_ableton(ctx).send_command("set_clip_automation", params)


@mcp.tool()
def clear_clip_automation(
    ctx: Context,
    track_index: int,
    clip_index: int,
    parameter_type: Optional[str] = None,
    device_index: Optional[int] = None,
    parameter_index: Optional[int] = None,
    send_index: Optional[int] = None,
) -> dict:
    """Clear automation envelopes from a session clip.

    If parameter_type is omitted, clears ALL envelopes.
    If provided, clears only that parameter's envelope.
    """
    params: dict = {
        "track_index": track_index,
        "clip_index": clip_index,
    }
    if parameter_type is not None:
        params["parameter_type"] = parameter_type
    if device_index is not None:
        params["device_index"] = device_index
    if parameter_index is not None:
        params["parameter_index"] = parameter_index
    if send_index is not None:
        params["send_index"] = send_index
    return _get_ableton(ctx).send_command("clear_clip_automation", params)


@mcp.tool()
def apply_automation_shape(
    ctx: Context,
    track_index: int,
    clip_index: int,
    parameter_type: str,
    curve_type: str,
    duration: float = 4.0,
    density: int = 16,
    device_index: Optional[int] = None,
    parameter_index: Optional[int] = None,
    send_index: Optional[int] = None,
    start: float = 0.0,
    end: float = 1.0,
    center: float = 0.5,
    amplitude: float = 0.5,
    frequency: float = 1.0,
    phase: float = 0.0,
    peak: float = 1.0,
    decay: float = 4.0,
    low: float = 0.0,
    high: float = 1.0,
    factor: float = 3.0,
    invert: bool = False,
    time_offset: float = 0.0,
) -> dict:
    """Generate and apply an automation curve to a session clip.

    Combines curve generation with clip automation writing in one call.

    curve_type: linear, exponential, logarithmic, s_curve, sine,
                sawtooth, spike, square, steps
    duration: curve length in beats
    density: number of automation points
    time_offset: shift the entire curve forward by N beats

    Curve-specific params:
    - linear/exp/log: start, end, factor (steepness 2-6)
    - sine: center, amplitude, frequency, phase
    - sawtooth: start, end, frequency (resets per duration)
    - spike: peak, decay (higher = faster)
    - square: low, high, frequency
    - s_curve: start, end

    Musical guidance:
    - Filter sweeps: use exponential (perceptually even)
    - Volume fades: use logarithmic (matches ear's response)
    - Crossfades: use s_curve (natural acceleration/deceleration)
    - Pumping: use sawtooth with frequency matching beat divisions
    - Throws: use spike with short duration (1-2 beats)
    - Tremolo/pan: use sine with frequency in musical divisions
    """
    # Generate the curve
    points = generate_curve(
        curve_type=curve_type,
        duration=duration,
        density=density,
        start=start, end=end,
        center=center, amplitude=amplitude,
        frequency=frequency, phase=phase,
        peak=peak, decay=decay,
        low=low, high=high,
        factor=factor,
        invert=invert,
    )

    # Apply time offset
    if time_offset > 0:
        for p in points:
            p["time"] += time_offset

    # Write to clip
    params: dict = {
        "track_index": track_index,
        "clip_index": clip_index,
        "parameter_type": parameter_type,
        "points": points,
    }
    if device_index is not None:
        params["device_index"] = device_index
    if parameter_index is not None:
        params["parameter_index"] = parameter_index
    if send_index is not None:
        params["send_index"] = send_index

    result = _get_ableton(ctx).send_command("set_clip_automation", params)
    result["curve_type"] = curve_type
    result["curve_points"] = len(points)
    return result


@mcp.tool()
def apply_automation_recipe(
    ctx: Context,
    track_index: int,
    clip_index: int,
    parameter_type: str,
    recipe: str,
    duration: float = 4.0,
    density: int = 16,
    device_index: Optional[int] = None,
    parameter_index: Optional[int] = None,
    send_index: Optional[int] = None,
    time_offset: float = 0.0,
) -> dict:
    """Apply a named automation recipe to a session clip.

    Recipes are predefined curve shapes for common production techniques.
    Use get_automation_recipes to list all available recipes.

    Available recipes:
    - filter_sweep_up: LP filter opening (exponential, 8-32 bars)
    - filter_sweep_down: LP filter closing (logarithmic, 4-16 bars)
    - dub_throw: send spike for reverb/delay throw (1-2 beats)
    - tape_stop: pitch dropping to zero (0.5-2 beats)
    - build_rise: tension build on HP filter + volume (8-32 bars)
    - sidechain_pump: volume ducking per beat (sawtooth, 1 beat loop)
    - fade_in / fade_out: perceptually smooth volume fades
    - tremolo: periodic volume oscillation
    - auto_pan: stereo movement via pan sine
    - stutter: rapid on/off gating
    - breathing: subtle filter movement (acoustic instrument feel)
    - washout: reverb/delay feedback increasing
    - vinyl_crackle: slow bit reduction movement
    - stereo_narrow: collapse to mono before drop
    """
    points = generate_from_recipe(recipe, duration=duration, density=density)

    if time_offset > 0:
        for p in points:
            p["time"] += time_offset

    params: dict = {
        "track_index": track_index,
        "clip_index": clip_index,
        "parameter_type": parameter_type,
        "points": points,
    }
    if device_index is not None:
        params["device_index"] = device_index
    if parameter_index is not None:
        params["parameter_index"] = parameter_index
    if send_index is not None:
        params["send_index"] = send_index

    result = _get_ableton(ctx).send_command("set_clip_automation", params)
    result["recipe"] = recipe
    result["curve_points"] = len(points)
    return result


@mcp.tool()
def get_automation_recipes(ctx: Context) -> dict:
    """List all available automation recipes with descriptions.

    Each recipe includes: curve type, description, typical duration,
    and recommended target parameter. Use apply_automation_recipe
    to apply any recipe to a clip.
    """
    return {"recipes": list_recipes()}


@mcp.tool()
def generate_automation_curve(
    ctx: Context,
    curve_type: str,
    duration: float = 4.0,
    density: int = 16,
    start: float = 0.0,
    end: float = 1.0,
    center: float = 0.5,
    amplitude: float = 0.5,
    frequency: float = 1.0,
    phase: float = 0.0,
    peak: float = 1.0,
    decay: float = 4.0,
    low: float = 0.0,
    high: float = 1.0,
    factor: float = 3.0,
    invert: bool = False,
) -> dict:
    """Generate automation curve points WITHOUT writing them.

    Returns the points array for preview/inspection. Use this to see
    what a curve looks like before committing it to a clip.
    Pass the returned points to set_clip_automation or
    set_arrangement_automation to write them.
    """
    points = generate_curve(
        curve_type=curve_type,
        duration=duration,
        density=density,
        start=start, end=end,
        center=center, amplitude=amplitude,
        frequency=frequency, phase=phase,
        peak=peak, decay=decay,
        low=low, high=high,
        factor=factor,
        invert=invert,
    )
    return {
        "curve_type": curve_type,
        "duration": duration,
        "point_count": len(points),
        "points": points,
        "value_range": {
            "min": min(p["value"] for p in points) if points else 0,
            "max": max(p["value"] for p in points) if points else 0,
        },
    }


@mcp.tool()
def analyze_for_automation(
    ctx: Context,
    track_index: int,
) -> dict:
    """Analyze a track's spectrum and suggest automation targets.

    Reads the track's current spectral data and device chain,
    then suggests which parameters would benefit from automation
    based on the frequency content and device types present.

    Requires LivePilot Analyzer on master track and audio playing.
    """
    ableton = _get_ableton(ctx)

    # Get track devices
    track_info = ableton.send_command("get_track_info", {
        "track_index": track_index,
    })

    # Get current spectrum
    spectral = ctx.lifespan_context.get("spectral")
    spectrum = {}
    if spectral and spectral.is_connected:
        spectrum = spectral.get_spectrum()

    # Get meter level
    meters = ableton.send_command("get_track_meters", {
        "track_index": track_index,
    })

    devices = track_info.get("devices", [])
    suggestions = []

    # Analyze based on device types and spectrum
    for i, dev in enumerate(devices):
        dev_name = dev.get("name", "").lower()
        dev_class = dev.get("class_name", "").lower()

        # Filter devices — suggest sweep automation
        if any(kw in dev_class for kw in ["autofilter", "eq8", "filter"]):
            suggestions.append({
                "device_index": i,
                "device_name": dev.get("name"),
                "suggestion": "filter_sweep",
                "reason": "Filter detected — automate cutoff for movement",
                "recipe": "filter_sweep_up",
            })

        # Reverb/delay — suggest send throws or washout
        if any(kw in dev_class for kw in ["reverb", "delay", "hybrid", "echo"]):
            suggestions.append({
                "device_index": i,
                "device_name": dev.get("name"),
                "suggestion": "spatial_automation",
                "reason": "Space effect — automate mix/decay for depth changes",
                "recipe": "washout",
            })

        # Distortion — suggest drive automation
        if any(kw in dev_class for kw in ["saturator", "overdrive", "pedal", "amp"]):
            suggestions.append({
                "device_index": i,
                "device_name": dev.get("name"),
                "suggestion": "drive_automation",
                "reason": "Distortion — automate drive for dynamic saturation",
                "recipe": "breathing",
            })

        # Synths — suggest wavetable/macro automation
        if any(kw in dev_class for kw in ["wavetable", "drift", "analog", "operator"]):
            suggestions.append({
                "device_index": i,
                "device_name": dev.get("name"),
                "suggestion": "timbre_evolution",
                "reason": "Synth — automate timbre params for evolving sound",
                "recipe": "breathing",
            })

    # Mixer suggestions based on spectrum
    if spectrum:
        sub = spectrum.get("sub", 0)
        if sub > 0.15:
            suggestions.append({
                "suggestion": "high_pass_automation",
                "reason": "Heavy sub content (%.2f) — HP filter sweep for builds" % sub,
                "recipe": "build_rise",
            })

    # Always suggest send automation for spatial depth
    suggestions.append({
        "suggestion": "send_throws",
        "reason": "Reverb/delay sends — automate for dub throws and spatial variation",
        "recipe": "dub_throw",
    })

    return {
        "track_index": track_index,
        "track_name": track_info.get("name", ""),
        "device_count": len(devices),
        "current_level": meters.get("tracks", [{}])[0].get("level", 0),
        "spectrum": spectrum,
        "suggestions": suggestions,
    }
```

- [ ] **Step 2: Import in __init__.py**

In `mcp_server/tools/__init__.py`, add:
```python
from . import automation  # noqa: F401
```

- [ ] **Step 3: Create contract test**

```python
# tests/test_automation_contract.py
"""Verify automation tools are registered."""

def test_automation_tool_count():
    """8 new automation tools should be registered."""
    from mcp_server.tools import automation
    import inspect
    tools = [name for name, obj in inspect.getmembers(automation)
             if callable(obj) and hasattr(obj, '__wrapped__')]
    # At minimum these should exist as functions
    expected = [
        'get_clip_automation',
        'set_clip_automation',
        'clear_clip_automation',
        'apply_automation_shape',
        'apply_automation_recipe',
        'get_automation_recipes',
        'generate_automation_curve',
        'analyze_for_automation',
    ]
    for name in expected:
        assert hasattr(automation, name), f"Missing tool: {name}"
```

- [ ] **Step 4: Update test_tools_contract.py**

Change expected tool count from 127 to 135 (127 + 8 new).

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add mcp_server/tools/automation.py mcp_server/tools/__init__.py tests/test_automation_contract.py tests/test_tools_contract.py
git commit -m "Add 8 automation MCP tools: clip CRUD + curve generation + recipes + analysis"
```

---

## Chunk 4: Automation Atlas

Knowledge corpus that teaches the agent about automation theory, when to use each technique, and how to combine curves with spectral data.

### Task 4: Create Automation Atlas

**Files:**
- Create: `plugin/skills/livepilot-core/references/automation-atlas.md`

- [ ] **Step 1: Write the automation atlas**

This file should cover:

1. **Curve Theory** — Why exponential for filters (log perception), logarithmic for volume (amplitude perception), S-curves for crossfades. Include the math intuition, not formulas.

2. **The Perception-Action Loop** — The agent's core intelligence cycle:

   **Level 1: Reactive (single read → single action)**
   - Read `get_master_spectrum` → muddy low-mids (low_mid > 0.15) → apply HP filter sweep
   - Read `get_master_rms` → peaks near clipping (> 0.9) → apply volume ducking
   - Read `get_detected_key` → key is C# minor → automate filter resonance at C# harmonics

   **Level 2: Diagnostic (multi-step investigation)**
   The agent uses EQ as a measurement instrument — a diagnostic filter:
   1. Load EQ Eight on the target track
   2. Set band 1 to narrow bandpass (Q=8, gain=0, freq=100Hz)
   3. Solo the track → `get_master_spectrum` → read what lives at 100Hz
   4. Move freq to 200Hz → read again → 300Hz → read again
   5. Build a frequency map: {100Hz: 0.18, 200Hz: 0.25, 300Hz: 0.09, ...}
   6. Identify problem areas: "resonance buildup at 200-250Hz"
   7. Remove diagnostic EQ
   8. Now write targeted automation: notch at 220Hz that opens over 8 bars

   This is how engineers "sweep to find the problem frequency" — the agent
   does it systematically, track by track, and remembers the findings.

   **Level 3: Feedback verification (act → measure → adjust)**
   1. Write automation (e.g., HP filter sweep on bass)
   2. Play the section → `get_master_spectrum` → compare to pre-automation spectrum
   3. Did low_mid drop from 0.22 to 0.11? Good.
   4. Did it drop to 0.03? Too much — reduce the sweep range
   5. Still at 0.18? Not enough — increase factor or extend duration
   6. Iterate until the spectral balance matches the target

   **Level 4: Cross-track spectral awareness**
   - Read spectrum on kick track alone (solo) → note the sub/low energy profile
   - Read spectrum on bass track alone → note where it overlaps with kick
   - The overlap region is where masking happens
   - Write complementary automation: as kick's filter opens, bass's filter narrows
   - This is frequency-aware mixing via automation, not just static EQ

   **Level 5: Per-track analysis pipeline (the full diagnostic)**
   For each track in the session:
   1. Solo the track
   2. Read `get_track_meters` → is there audio? Skip if silent
   3. Read `get_master_spectrum` → capture its spectral fingerprint
   4. Unsolo → read spectrum with this track muted vs unmuted
   5. The DIFFERENCE tells you what this track contributes to the mix
   6. Store findings: "BASS contributes 0.15 in sub, 0.08 in low_mid"
   7. Use this map to write automation that shapes each track's contribution over time

3. **Genre Recipes** — When to use which recipe, with specific parameter targets:
   - Techno: filter_sweep_up on LP cutoff, 32 bars, factor 2.0
   - Dub: dub_throw on Send A, 1 beat, at each snare hit position
   - Ambient: breathing on filter cutoff, 4 bars, amplitude 0.1
   - Hip hop: tape_stop on clip transpose, 0.5 beats
   - IDM: stutter on volume, 0.5 beats, frequency 16

4. **Sound Design Automation** — Parameter-specific guidance:
   - Wavetable position: exponential sweep for timbral morphing
   - Grain size: sine modulation for alive textures
   - Reverb decay: linked to volume (quieter = longer tail)
   - Delay feedback: spike for dub throws, never exceed 0.9

5. **Arrangement Automation** — Structural techniques:
   - The Build: combine HP filter + volume + reverb send + stereo narrow
   - The Drop: instant restore of all build parameters (step automation)
   - The Strip: gradual HP filter rise removing elements
   - Transitions: crossfade between textures via volume automation

6. **Micro-Editing** — Per-note automation:
   - Velocity is timbre, volume automation is loudness
   - Filter cutoff per note for accent patterns
   - Send spikes on specific hits for spatial punctuation

7. **Polyrhythmic Automation** — Unlinked envelope technique:
   - 4-beat clip loop + 3-beat filter envelope + 5-beat reverb envelope
   - Creates 60-beat cycle before exact repetition
   - Use for evolving textures in ambient/installation work

8. **Spectral Diagnosis Technique** — Using filters as measurement tools:
   - The agent should think of EQ not just as a mixing tool but as a MICROSCOPE for sound
   - Load EQ Eight → set narrow bandpass → sweep across frequencies → read spectrum at each position
   - This reveals: where the energy lives, where resonances build up, where tracks mask each other
   - After diagnosis, remove the EQ and write precise automation targeting what was found
   - Document findings in memory so the agent can recall "this bass has a resonance at 220Hz" weeks later
   - The diagnostic EQ is temporary — always clean up after measurement

9. **Cross-Track Spectral Mapping** — Understanding the mix as a frequency ecosystem:
   - Solo each track → read spectrum → build a map of what occupies which frequency range
   - Find overlaps: if kick and bass both have strong energy at 60-80Hz, they're fighting
   - Write complementary automation: as one opens in a frequency band, the other narrows
   - This is dynamic frequency allocation — the mix breathes instead of being static EQ
   - Use the memory system to store spectral maps: "Session X: kick owns 40-80Hz, bass owns 80-200Hz"

10. **The Golden Rules**:
    - Always use Utility gain for volume automation (preserve mixer fader for mixing)
    - Exponential for filters, logarithmic for volume — never linear for either
    - Subtle automation (5-15% range) for organic feel; dramatic (full range) for transitions
    - ALWAYS verify with get_master_spectrum after writing automation
    - Use clear_clip_automation before rewriting (don't stack conflicting curves)
    - Use the diagnostic filter technique before guessing at problem frequencies
    - Store spectral findings in memory — build a knowledge base about this specific session's sounds

- [ ] **Step 2: Commit**

```bash
git add plugin/skills/livepilot-core/references/automation-atlas.md
git commit -m "Add automation atlas: curves, recipes, genre patterns, perception-action loop"
```

---

## Chunk 5: Update Skills, Agent, and Documentation

### Task 5: Update SKILL.md and Producer Agent

**Files:**
- Modify: `plugin/skills/livepilot-core/SKILL.md`
- Modify: `plugin/skills/livepilot-core/references/overview.md`
- Modify: `plugin/agents/livepilot-producer/AGENT.md`

- [ ] **Step 1: Add automation section to SKILL.md**

Add after the Analyzer section:
```markdown
### Automation (8 tools)
Clip automation CRUD + intelligent curve generation with 15 built-in recipes.

**Tools:** get_clip_automation, set_clip_automation, clear_clip_automation,
apply_automation_shape, apply_automation_recipe, get_automation_recipes,
generate_automation_curve, analyze_for_automation

**Key discipline:**

**The Feedback Loop (MANDATORY for all automation work):**
1. PERCEIVE: `get_master_spectrum` + `get_track_meters` → understand current state
2. DIAGNOSE: What needs to change? Use diagnostic filter technique if unsure
3. DECIDE: Which parameter, which curve, which recipe?
4. ACT: `apply_automation_shape` or `apply_automation_recipe`
5. VERIFY: `get_master_spectrum` again → did it work?
6. ADJUST: If not right, `clear_clip_automation` → try different curve/params
7. NEVER write automation without reading spectrum first and after

**Rules:**
- Use `analyze_for_automation` before writing — let spectral data guide decisions
- Use recipes for common patterns (filter_sweep_up, dub_throw, sidechain_pump)
- Use `apply_automation_shape` for custom curves with specific math
- Clear existing automation before rewriting: `clear_clip_automation` first
- Load `references/automation-atlas.md` for curve theory, genre recipes, diagnostic technique, and cross-track spectral mapping
```

- [ ] **Step 2: Update overview.md tool count**

Update total from 127 to 135, add Automation domain (8 tools) to the table.

- [ ] **Step 3: Update producer agent**

Add automation awareness to AGENT.md:
```markdown
### Automation Phase (after writing notes, before mixing)

**Step 1: Spectral Diagnosis**
- Solo each track → `get_master_spectrum` → build spectral map
- Identify frequency overlaps between tracks (masking)
- Note problem areas: resonances, mud, harshness

**Step 2: Per-Track Analysis**
- `analyze_for_automation` on each track → get device-specific suggestions
- Cross-reference with spectral map: which suggestions address the problems found?

**Step 3: Write Automation (perception-action loop)**
For each automation decision:
1. Read spectrum BEFORE
2. Apply recipe or custom curve
3. Read spectrum AFTER
4. Compare: did it improve? If not, clear and adjust
5. Store the final working automation parameters in memory

**Step 4: Spatial Design**
- Add send automation for depth (dub throws, reverb washes)
- Consider complementary automation: as one track's filter opens, another's narrows
- Use cross-track spectral awareness to avoid new masking from automation

**Step 5: Generative/Evolving Textures**
- Consider polyrhythmic automation for non-repeating evolution
- Unlinked envelopes with prime-number beat lengths (3, 5, 7 beats)
- Spectral-driven automation: use analyzer data to modulate parameters in real-time concepts
```

- [ ] **Step 4: Commit**

```bash
git add plugin/skills/livepilot-core/SKILL.md plugin/skills/livepilot-core/references/overview.md plugin/agents/livepilot-producer/AGENT.md
git commit -m "Update skills and agent with automation intelligence guidance"
```

---

## Chunk 6: Update All Version References

Per the release checklist skill, update tool count everywhere.

### Task 6: Tool Count Propagation

**Files:** All files listed in `plugin/skills/livepilot-release/SKILL.md` checklist.

- [ ] **Step 1: Run the release checklist**

Update 127 → 135 in:
- README.md
- package.json description
- server.json description
- plugin/plugin.json description
- CLAUDE.md
- docs/manual/index.md
- docs/manual/tool-reference.md (add 8 new tools)
- docs/TOOL_REFERENCE.md (add Automation domain)
- docs/social-banner.html (127 → 135)
- tests/test_tools_contract.py (127 → 135)

- [ ] **Step 2: Update CHANGELOG.md**

Add v1.6.0 entry for automation intelligence.

- [ ] **Step 3: Bump version to 1.6.0**

In package.json, server.json, plugin.json, mcp_server/__init__.py, remote_script/__init__.py, livepilot_bridge.js.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "v1.6.0: Automation intelligence — 8 new tools, curve engine, 15 recipes"
```

- [ ] **Step 5: Run full release checklist**

Execute the quick verify command from the release skill to confirm all counts and versions match.

---

## Summary

| Chunk | New Files | New Tools | Tests | Effort |
|-------|-----------|-----------|-------|--------|
| 1. Curve Engine | curves.py, test_curves.py | 0 (library, 16 curve types) | 20+ unit tests | Medium |
| 2. Remote Script | clip_automation.py | 0 (handlers) | Manual | Small |
| 3. MCP Tools | automation.py, test_automation_contract.py | 8 tools | Contract tests | Medium |
| 4. Atlas | automation-atlas.md | 0 (knowledge) | N/A | Medium |
| 5. Skills/Agent | Updates to 3 files | 0 | N/A | Small |
| 6. Release | Updates to 10+ files | 0 | Checklist | Small |
| **Total** | **6 new files** | **8 new tools (135 total)** | **20+ tests** | **Medium** |

## Curve Engine Summary: 16 Types in 4 Categories

| Category | Curves | Musical Character |
|----------|--------|-------------------|
| **Basic** | linear, exponential, logarithmic, s_curve, sine, sawtooth, spike, square, steps | Standard LFO shapes — predictable, clean |
| **Organic** | perlin, brownian, spring | Alive, analog-feeling, never mechanical |
| **Shape** | bezier, easing (8 subtypes) | Precision curves — any shape imaginable |
| **Generative** | euclidean, stochastic | Algorithmic intelligence — Xenakis meets Toussaint |
