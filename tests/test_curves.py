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
        assert q1 < 0.2  # slow start
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
        """Spring: raw curve overshoots target then settles.

        Note: generate_curve() clamps to [0,1], so we test the raw
        _spring generator directly to verify overshoot physics.
        """
        from mcp_server.curves import _spring
        points = _spring(duration=4.0, density=64, start=0.0, end=1.0,
                        damping=0.1, stiffness=8.0)
        values = [p["value"] for p in points]
        # Raw spring MUST overshoot with moderate damping
        assert any(v > 1.0 for v in values), "Spring should overshoot with damping=0.1"
        # Should settle near end value
        assert values[-1] == pytest.approx(1.0, abs=0.1)

    def test_clamped_spring_stays_in_range(self):
        """Spring through generate_curve is clamped to [0,1]."""
        points = generate_curve("spring", start=0.0, end=1.0,
                               damping=0.05, stiffness=8.0,
                               duration=4.0, density=64)
        values = [p["value"] for p in points]
        assert all(0.0 <= v <= 1.0 for v in values)

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
