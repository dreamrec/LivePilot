"""gen~ DSP building block library — GenExpr code as reusable templates.

Each template is a complete, working gen~ codebox program with parameters.
Templates are organized by category and can be used directly with
generate_m4l_effect or as starting points for custom devices.
"""

from __future__ import annotations

from .models import GenExprParam, GenExprTemplate, UNIT_STYLE_HERTZ, UNIT_STYLE_PERCENT, UNIT_STYLE_FLOAT

TEMPLATES: dict[str, GenExprTemplate] = {}


def _register(t: GenExprTemplate) -> GenExprTemplate:
    TEMPLATES[t.template_id] = t
    return t


def get_template(template_id: str) -> GenExprTemplate | None:
    return TEMPLATES.get(template_id)


def list_templates(category: str = "") -> list[dict]:
    items = list(TEMPLATES.values())
    if category:
        items = [t for t in items if t.category == category]
    return [t.to_dict() for t in items]


def list_categories() -> list[str]:
    return sorted({t.category for t in TEMPLATES.values()})


# ═══════════════════════════════════════════════════════════════════════
# UTILITY
# ═══════════════════════════════════════════════════════════════════════

_register(GenExprTemplate(
    template_id="passthrough",
    name="Passthrough",
    description="Clean audio passthrough — useful as a starting skeleton",
    category="utility",
    code="out1 = in1;",
    params=[],
))

# ═══════════════════════════════════════════════════════════════════════
# CHAOS
# ═══════════════════════════════════════════════════════════════════════

_register(GenExprTemplate(
    template_id="lorenz_attractor",
    name="Lorenz Attractor",
    description="Three coupled differential equations producing chaotic modulation. "
                "Smooth but unpredictable — great for filter cutoff, pan, and send modulation.",
    category="chaos",
    code="""\
Param sigma(10);
Param rho(28);
Param beta(2.667);
Param speed(0.001);

History x(0.1);
History y(0);
History z(0);

dx = sigma * (y - x);
dy = x * (rho - z) - y;
dz = x * y - beta * z;

x += dx * speed;
y += dy * speed;
z += dz * speed;

out1 = x * 0.02;""",
    params=[
        GenExprParam(name="sigma", default=10, min_val=0.1, max_val=50),
        GenExprParam(name="rho", default=28, min_val=0.1, max_val=100),
        GenExprParam(name="beta", default=2.667, min_val=0.1, max_val=10),
        GenExprParam(name="speed", default=0.001, min_val=0.0001, max_val=0.01),
    ],
))

_register(GenExprTemplate(
    template_id="henon_map",
    name="Henon Map",
    description="Discrete chaotic map — produces noise textures at some parameters, "
                "pitched tones at others. The edge-of-chaos zone is musically rich.",
    category="chaos",
    code="""\
Param a(1.4);
Param b(0.3);
Param speed(0.01);

History x(0.1);
History y(0);

nx = 1 - a * x * x + y;
ny = b * x;

x = nx;
y = ny;

out1 = x * speed;""",
    params=[
        GenExprParam(name="a", default=1.4, min_val=0.1, max_val=2.0),
        GenExprParam(name="b", default=0.3, min_val=0.0, max_val=1.0),
        GenExprParam(name="speed", default=0.01, min_val=0.001, max_val=0.1),
    ],
))

# ═══════════════════════════════════════════════════════════════════════
# SYNTHESIS
# ═══════════════════════════════════════════════════════════════════════

_register(GenExprTemplate(
    template_id="karplus_strong",
    name="Karplus-Strong String",
    description="Plucked string physical model — noise burst excitation through "
                "a filtered delay line. Classic digital waveguide synthesis.",
    category="synthesis",
    code="""\
Param freq(220);
Param damping(0.996);
Param brightness(0.5);

delaySamples = samplerate / max(freq, 20);
History h1(0);

trigger = in1 > 0.5;
excitation = noise() * trigger;

delayed = delay(h1, delaySamples);
filtered = delayed * brightness + h1 * (1 - brightness);
h1 = excitation + filtered * damping;

out1 = h1;""",
    params=[
        GenExprParam(name="freq", default=220, min_val=20, max_val=20000, unit_style=UNIT_STYLE_HERTZ),
        GenExprParam(name="damping", default=0.996, min_val=0.9, max_val=0.9999),
        GenExprParam(name="brightness", default=0.5, min_val=0.0, max_val=1.0),
    ],
))

_register(GenExprTemplate(
    template_id="karplus_strong_reverb",
    name="Karplus-Strong with Reverb Feedback",
    description="KS variant with allpass diffusion in the feedback loop instead of simple "
                "lowpass. Produces sustained, evolving, richly harmonic tones.",
    category="synthesis",
    code="""\
Param freq(220);
Param damping(0.995);
Param diffusion(0.5);

delaySamples = samplerate / max(freq, 20);
History h1(0);
History ap1(0);
History ap2(0);

trigger = in1 > 0.5;
excitation = noise() * trigger;

delayed = delay(h1, delaySamples);

// Two allpass stages for diffusion
ap1_in = delayed + ap1 * diffusion;
ap1_out = ap1 * -diffusion + delay(ap1_in, 37);
ap1 = ap1_in;

ap2_in = ap1_out + ap2 * diffusion;
ap2_out = ap2 * -diffusion + delay(ap2_in, 113);
ap2 = ap2_in;

filtered = (ap2_out + delayed) * 0.5;
h1 = excitation + filtered * damping;

out1 = h1;""",
    params=[
        GenExprParam(name="freq", default=220, min_val=20, max_val=20000, unit_style=UNIT_STYLE_HERTZ),
        GenExprParam(name="damping", default=0.995, min_val=0.9, max_val=0.9999),
        GenExprParam(name="diffusion", default=0.5, min_val=0.0, max_val=0.9),
    ],
))

_register(GenExprTemplate(
    template_id="phase_distortion",
    name="Phase Distortion Synth",
    description="CZ-style phase distortion synthesis — a phasor's shape is warped "
                "before reading a cosine table, creating rich timbral evolution.",
    category="synthesis",
    code="""\
Param freq(440);
Param distortion(0.5);

History phase(0);

phase += freq / samplerate;
phase = wrap(phase, 0, 1);

// Distort the phase curve
warped = phase + distortion * sin(phase * TWOPI) * 0.5;
warped = wrap(warped, 0, 1);

out1 = cos(warped * TWOPI) * 0.5;""",
    params=[
        GenExprParam(name="freq", default=440, min_val=20, max_val=20000, unit_style=UNIT_STYLE_HERTZ),
        GenExprParam(name="distortion", default=0.5, min_val=0.0, max_val=1.0),
    ],
))

# ═══════════════════════════════════════════════════════════════════════
# DISTORTION
# ═══════════════════════════════════════════════════════════════════════

_register(GenExprTemplate(
    template_id="wavefolder",
    name="Wavefolder",
    description="Buchla-style wavefolder — folds the waveform back on itself, "
                "generating rich harmonic series. Multiple fold stages for complexity.",
    category="distortion",
    code="""\
Param drive(2);
Param symmetry(0.5);
Param mix(0.75);

input = in1 * drive;

// Three fold stages
folded = fold(input + symmetry - 0.5, -1, 1);
folded = fold(folded * 1.5, -1, 1);
folded = fold(folded * 1.2, -1, 1);

out1 = in1 * (1 - mix) + folded * mix;""",
    params=[
        GenExprParam(name="drive", default=2, min_val=1, max_val=20),
        GenExprParam(name="symmetry", default=0.5, min_val=0.0, max_val=1.0),
        GenExprParam(name="mix", default=0.75, min_val=0.0, max_val=1.0, unit_style=UNIT_STYLE_PERCENT),
    ],
))

_register(GenExprTemplate(
    template_id="bitcrusher",
    name="Bitcrusher",
    description="Sample-rate and bit-depth reducer — from subtle aliasing to full "
                "digital destruction. Modulate rate for glitch textures.",
    category="distortion",
    code="""\
Param rate(0.5);
Param bits(8);

// Sample rate reduction via sample-and-hold
reduced = latch(in1, phasor(samplerate * max(rate, 0.01)));

// Bit depth reduction
levels = pow(2, max(bits, 1));
crushed = floor(reduced * levels + 0.5) / levels;

out1 = crushed;""",
    params=[
        GenExprParam(name="rate", default=0.5, min_val=0.01, max_val=1.0),
        GenExprParam(name="bits", default=8, min_val=1, max_val=16),
    ],
))

# ═══════════════════════════════════════════════════════════════════════
# MODULATION
# ═══════════════════════════════════════════════════════════════════════

_register(GenExprTemplate(
    template_id="ring_modulator",
    name="Ring Modulator",
    description="Classic ring modulation — input multiplied by a carrier oscillator. "
                "Use sub-audio rates for tremolo, audio rates for metallic sidebands.",
    category="modulation",
    code="""\
Param freq(100);
Param depth(1.0);
Param mix(0.5);

carrier = cycle(freq);
modulated = in1 * (1 - depth + depth * carrier);

out1 = in1 * (1 - mix) + modulated * mix;""",
    params=[
        GenExprParam(name="freq", default=100, min_val=0.1, max_val=20000, unit_style=UNIT_STYLE_HERTZ),
        GenExprParam(name="depth", default=1.0, min_val=0.0, max_val=1.0),
        GenExprParam(name="mix", default=0.5, min_val=0.0, max_val=1.0, unit_style=UNIT_STYLE_PERCENT),
    ],
))

_register(GenExprTemplate(
    template_id="chorus",
    name="Chorus",
    description="Multi-voice micro-delay chorus — three slightly detuned delay taps "
                "create width and shimmer without muddiness.",
    category="modulation",
    code="""\
Param rate(0.5);
Param depth(0.003);
Param mix(0.5);

base_delay = 0.01 * samplerate;
mod1 = cycle(rate) * depth * samplerate;
mod2 = cycle(rate * 1.1) * depth * samplerate * 0.8;
mod3 = cycle(rate * 0.9) * depth * samplerate * 1.2;

d1 = delay(in1, base_delay + mod1);
d2 = delay(in1, base_delay + mod2);
d3 = delay(in1, base_delay + mod3);

wet = (d1 + d2 + d3) / 3;

out1 = in1 * (1 - mix) + wet * mix;""",
    params=[
        GenExprParam(name="rate", default=0.5, min_val=0.05, max_val=5, unit_style=UNIT_STYLE_HERTZ),
        GenExprParam(name="depth", default=0.003, min_val=0.0, max_val=0.02),
        GenExprParam(name="mix", default=0.5, min_val=0.0, max_val=1.0, unit_style=UNIT_STYLE_PERCENT),
    ],
))

# ═══════════════════════════════════════════════════════════════════════
# DELAY
# ═══════════════════════════════════════════════════════════════════════

_register(GenExprTemplate(
    template_id="feedback_delay",
    name="Feedback Delay",
    description="Simple delay line with filtered feedback — the backbone of "
                "echo effects, dub delays, and ambient washes.",
    category="delay",
    code="""\
Param time(0.25);
Param feedback(0.5);
Param damping(0.7);

History prev_out(0);

delay_samples = max(time, 0.001) * samplerate;
delayed = delay(in1 + prev_out * feedback, delay_samples);

// One-pole lowpass in feedback path
filtered = delayed * damping + prev_out * (1 - damping);
prev_out = filtered;

out1 = in1 * 0.5 + filtered * 0.5;""",
    params=[
        GenExprParam(name="time", default=0.25, min_val=0.001, max_val=2.0),
        GenExprParam(name="feedback", default=0.5, min_val=0.0, max_val=0.95),
        GenExprParam(name="damping", default=0.7, min_val=0.0, max_val=1.0),
    ],
))

_register(GenExprTemplate(
    template_id="feedback_delay_network",
    name="Feedback Delay Network",
    description="4-line FDN with Hadamard-like cross-coupling matrix. Creates dense, "
                "diffuse reverb tails. Tune delay times to musical intervals for harmonic reverb.",
    category="delay",
    code="""\
Param size(0.05);
Param feedback(0.7);
Param damping(0.8);

History a(0);
History b(0);
History c(0);
History d(0);

base = max(size, 0.001) * samplerate;
da = delay(a, base * 1.0);
db = delay(b, base * 1.347);
dc = delay(c, base * 1.573);
dd = delay(d, base * 1.811);

// Hadamard-like mixing matrix (preserves energy)
na = ( da + db + dc + dd) * 0.5;
nb = ( da - db + dc - dd) * 0.5;
nc = ( da + db - dc - dd) * 0.5;
nd = ( da - db - dc + dd) * 0.5;

// Damping + feedback + input injection
a = (na * damping) * feedback + in1;
b = (nb * damping) * feedback;
c = (nc * damping) * feedback;
d = (nd * damping) * feedback;

out1 = (da + db + dc + dd) * 0.25;""",
    params=[
        GenExprParam(name="size", default=0.05, min_val=0.001, max_val=0.5),
        GenExprParam(name="feedback", default=0.7, min_val=0.0, max_val=0.95),
        GenExprParam(name="damping", default=0.8, min_val=0.0, max_val=1.0),
    ],
))

_register(GenExprTemplate(
    template_id="granular_delay",
    name="Granular Delay",
    description="Buffer-based granular delay — reads from a circular delay buffer "
                "at variable positions and grain sizes for textural delays.",
    category="delay",
    code="""\
Param position(0.5);
Param grain_size(0.05);
Param density(10);
Param mix(0.5);

grain_phase = phasor(density);
window = sin(grain_phase * 3.14159);

delay_samples = position * samplerate;
grain_samples = max(grain_size, 0.001) * samplerate;
read_pos = delay_samples + grain_phase * grain_samples;

wet = delay(in1, max(read_pos, 1)) * window;

out1 = in1 * (1 - mix) + wet * mix;""",
    params=[
        GenExprParam(name="position", default=0.5, min_val=0.0, max_val=2.0),
        GenExprParam(name="grain_size", default=0.05, min_val=0.001, max_val=0.5),
        GenExprParam(name="density", default=10, min_val=1, max_val=100),
        GenExprParam(name="mix", default=0.5, min_val=0.0, max_val=1.0, unit_style=UNIT_STYLE_PERCENT),
    ],
))

# ═══════════════════════════════════════════════════════════════════════
# FILTER
# ═══════════════════════════════════════════════════════════════════════

_register(GenExprTemplate(
    template_id="resonator",
    name="Comb Resonator",
    description="Tuned comb filter that resonates at a specific frequency — "
                "feed it noise for metallic tones, or audio for pitched resonance.",
    category="filter",
    code="""\
Param freq(440);
Param resonance(0.9);
Param mix(0.5);

History fb(0);

delay_samples = samplerate / max(freq, 20);
delayed = delay(fb, delay_samples);
fb = in1 + delayed * min(resonance, 0.999);

out1 = in1 * (1 - mix) + fb * mix;""",
    params=[
        GenExprParam(name="freq", default=440, min_val=20, max_val=20000, unit_style=UNIT_STYLE_HERTZ),
        GenExprParam(name="resonance", default=0.9, min_val=0.0, max_val=0.999),
        GenExprParam(name="mix", default=0.5, min_val=0.0, max_val=1.0, unit_style=UNIT_STYLE_PERCENT),
    ],
))

# ═══════════════════════════════════════════════════════════════════════
# TEXTURE
# ═══════════════════════════════════════════════════════════════════════

_register(GenExprTemplate(
    template_id="stochastic_resonance",
    name="Stochastic Resonance",
    description="Noise + threshold + feedback system — adding controlled noise to a "
                "nonlinear threshold creates granular textures and organic movement.",
    category="texture",
    code="""\
Param threshold(0.3);
Param noise_amount(0.2);
Param feedback(0.5);

History state(0);

noisy = in1 + noise() * noise_amount + state * feedback;
triggered = noisy > threshold;
state = triggered * 0.8 + state * 0.2;

out1 = (triggered * 2 - 1) * 0.5;""",
    params=[
        GenExprParam(name="threshold", default=0.3, min_val=0.0, max_val=1.0),
        GenExprParam(name="noise_amount", default=0.2, min_val=0.0, max_val=1.0),
        GenExprParam(name="feedback", default=0.5, min_val=0.0, max_val=0.95),
    ],
))
