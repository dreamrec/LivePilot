"""v1.20.2 BUG #4 regression: batch_set_parameters must surface
snapped quantized-enum params in its response.

Pre-fix: calling batch_set_parameters with param_overrides like
``{"Gate": 0.3}`` on a quantized enum parameter would silently
snap to the nearest enum step (``Gate=0`` = "1/16"). The response
contained the snapped value but no indication a snap occurred, so
callers had no way to learn their intent didn't match the outcome.

Fix: batch_set_parameters post-processes Ableton's response, compares
each returned ``value`` to the originally requested value, and when
they differ by >SNAP_EPSILON adds an entry to a ``snapped_params``
list in the response — with the name, requested, actual, and
display_value for caller visibility.

Campaign source: ~/Desktop/DREAM AI/demo Project/REPORT.md §BUG #3
(Test 4 — Aphex Destruction, Beat Repeat Gate/Variation snap).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def _make_ctx(response_parameters):
    """Build a minimal ctx that makes ableton.send_command return a
    fake batch_set_parameters response with the given parameter list."""

    class _Ableton:
        def send_command(self, cmd, params=None):
            # Ableton's Remote Script returns {parameters: [...]} where each
            # entry has name, value (actual stored), value_string, display_value.
            return {"parameters": response_parameters}

    return SimpleNamespace(lifespan_context={"ableton": _Ableton()})


class TestBatchSetParametersSnapDetection:
    def test_no_snap_means_no_snapped_params_field(self):
        """When all requested values round-trip exactly, response should
        NOT include a snapped_params field (or it should be empty)."""
        from mcp_server.tools.devices import batch_set_parameters

        response_params = [
            {"name": "Freq", "value": 440.0, "value_string": "440 Hz", "display_value": 440},
            {"name": "Q", "value": 0.7, "value_string": "0.7", "display_value": 0.7},
        ]
        ctx = _make_ctx(response_params)
        result = batch_set_parameters(
            ctx, track_index=0, device_index=0,
            parameters=[
                {"parameter_name": "Freq", "value": 440.0},
                {"parameter_name": "Q", "value": 0.7},
            ],
        )
        assert result.get("snapped_params", []) == []

    def test_quantized_enum_snap_surfaced_in_response(self):
        """Beat Repeat Gate=0.3 snaps to 0 — response must flag this
        with the name, requested, actual values."""
        from mcp_server.tools.devices import batch_set_parameters

        response_params = [
            {"name": "Chance", "value": 0.7, "value_string": "70.0 %", "display_value": 70},
            {"name": "Gate", "value": 0, "value_string": "1/16", "display_value": 0},  # snapped from 0.3
            {"name": "Interval", "value": 4, "value_string": "1/2", "display_value": 4},
        ]
        ctx = _make_ctx(response_params)
        result = batch_set_parameters(
            ctx, track_index=0, device_index=0,
            parameters=[
                {"parameter_name": "Chance", "value": 0.7},
                {"parameter_name": "Gate", "value": 0.3},      # REQUESTED 0.3, Ableton returned 0
                {"parameter_name": "Interval", "value": 4},
            ],
        )
        snapped = result.get("snapped_params", [])
        assert len(snapped) == 1, (
            f"expected 1 snapped param, got {len(snapped)}: {snapped}"
        )
        entry = snapped[0]
        assert entry["name"] == "Gate"
        assert entry["requested"] == 0.3
        assert entry["actual"] == 0
        # display_value is useful for humans understanding the outcome
        assert "display_value" in entry

    def test_multiple_snaps_all_reported(self):
        from mcp_server.tools.devices import batch_set_parameters

        response_params = [
            {"name": "Gate", "value": 0, "value_string": "1/16", "display_value": 0},
            {"name": "Variation", "value": 0, "value_string": "0", "display_value": 0},
        ]
        ctx = _make_ctx(response_params)
        result = batch_set_parameters(
            ctx, track_index=0, device_index=0,
            parameters=[
                {"parameter_name": "Gate", "value": 0.3},
                {"parameter_name": "Variation", "value": 0.8},
            ],
        )
        snapped = result.get("snapped_params", [])
        assert len(snapped) == 2
        names = {e["name"] for e in snapped}
        assert names == {"Gate", "Variation"}

    def test_integer_param_no_false_snap(self):
        """Integer params (Interval=4) should not trigger snap detection
        when the returned value matches exactly."""
        from mcp_server.tools.devices import batch_set_parameters

        response_params = [
            {"name": "Interval", "value": 4, "value_string": "1/2", "display_value": 4},
        ]
        ctx = _make_ctx(response_params)
        result = batch_set_parameters(
            ctx, track_index=0, device_index=0,
            parameters=[{"parameter_name": "Interval", "value": 4}],
        )
        assert result.get("snapped_params", []) == []

    def test_float_epsilon_tolerance(self):
        """Ableton stores floats with tiny precision drift (0.4000000059...)
        — this is NOT a snap, don't flag it."""
        from mcp_server.tools.devices import batch_set_parameters

        response_params = [
            {"name": "Dry/Wet", "value": 0.4000000059604645,
             "value_string": "40 %", "display_value": 40},
        ]
        ctx = _make_ctx(response_params)
        result = batch_set_parameters(
            ctx, track_index=0, device_index=0,
            parameters=[{"parameter_name": "Dry/Wet", "value": 0.4}],
        )
        assert result.get("snapped_params", []) == [], (
            "float precision drift (<1e-5) must not be flagged as snap"
        )

    def test_response_still_contains_parameters_list(self):
        """Snap detection is additive — original response fields preserved."""
        from mcp_server.tools.devices import batch_set_parameters

        response_params = [
            {"name": "Freq", "value": 440.0, "value_string": "440 Hz", "display_value": 440},
        ]
        ctx = _make_ctx(response_params)
        result = batch_set_parameters(
            ctx, track_index=0, device_index=0,
            parameters=[{"parameter_name": "Freq", "value": 440.0}],
        )
        assert "parameters" in result
        assert result["parameters"] == response_params
