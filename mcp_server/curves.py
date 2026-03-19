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


# -- Generators ----------------------------------------------------------------

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


# -- Organic / Natural Motion -------------------------------------------------

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
        # Soft boundary reflection (bounce off 0/1 until within range)
        while value > 1.0 or value < 0.0:
            if value > 1.0:
                value = 2.0 - value
            if value < 0.0:
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


# -- Shape Control -------------------------------------------------------------

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


# -- Algorithmic / Generative -------------------------------------------------

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


# -- Recipe Shortcuts ----------------------------------------------------------

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
