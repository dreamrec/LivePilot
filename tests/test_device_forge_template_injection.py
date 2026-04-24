"""v1.20.2 BUG #1 regression: Device Forge create_* moves must inject
gen_code at compile time.

Pre-fix state: the 7 create_* moves in device_creation_moves.py emitted
plan_templates like:
    {"tool": "generate_m4l_effect",
     "params": {"name": "Wonder FDN Verb", "device_type": "audio_effect", ...}}

But `generate_m4l_effect` requires a `gen_code` positional argument. At
explore-mode execution, the move failed with:
    generate_m4l_effect() missing 1 required positional argument: 'gen_code'

Fix: device_creation_compilers.py consults a move_id→template_id map
and injects the template's `code` into each step's params. The 7
template IDs already exist in mcp_server/device_forge/templates.py.

This suite pins the injection contract so the bug cannot regress.

Campaign surface: see
`/Users/visansilviugeorge/Desktop/DREAM AI/demo Project/REPORT.md` §BUG #1.
"""

from __future__ import annotations

import pytest

import mcp_server.semantic_moves  # noqa: F401 — triggers registrations
from mcp_server.semantic_moves import compiler as move_compiler
from mcp_server.semantic_moves.registry import get_move


_DEVICE_FORGE_MOVES = [
    "create_chaos_modulator",
    "create_feedback_resonator",
    "create_wavefolder_effect",
    "create_bitcrusher_effect",
    "create_karplus_string",
    "create_stochastic_texture",
    "create_fdn_reverb",
]


class TestDeviceForgeTemplateInjection:
    @pytest.mark.parametrize("move_id", _DEVICE_FORGE_MOVES)
    def test_compiled_step_includes_non_empty_gen_code(self, move_id):
        """Every Device Forge move's first emitted step must have a non-empty
        gen_code in its params — otherwise generate_m4l_effect will fail with
        'missing 1 required positional argument: gen_code'."""
        move = get_move(move_id)
        assert move is not None, f"Move {move_id} not registered"
        # v1.21: compiler now requires seed_args.track_index for Device
        # Forge moves (threaded into find_and_load_device step). Pass 0 so
        # this test continues to exercise gen_code injection — the actual
        # invariant under test here.
        plan = move_compiler.compile(
            move,
            {"session_info": {}, "seed_args": {"track_index": 0}, "mode": "improve"},
        )
        gen_steps = [s for s in plan.steps if s.tool == "generate_m4l_effect"]
        assert gen_steps, f"{move_id} emits no generate_m4l_effect step"
        gen_code = gen_steps[0].params.get("gen_code")
        assert isinstance(gen_code, str) and gen_code.strip(), (
            f"{move_id}: gen_code is missing or empty in compiled step params. "
            f"Got: {gen_code!r}. Required for generate_m4l_effect to succeed."
        )
        # Sanity: gen_code is long enough to be real GenExpr (>100 chars).
        assert len(gen_code) > 100, (
            f"{move_id}: gen_code looks too short ({len(gen_code)} chars) "
            f"to be a real GenExpr program"
        )

    def test_template_id_map_covers_all_7_moves(self):
        """The compiler's move_id→template_id map must name a real template
        for each of the 7 Device Forge moves."""
        from mcp_server.semantic_moves import device_creation_compilers as dcc
        from mcp_server.device_forge.templates import get_template

        mapping = getattr(dcc, "_MOVE_TO_TEMPLATE", None)
        assert mapping is not None, (
            "device_creation_compilers._MOVE_TO_TEMPLATE map missing — "
            "Device Forge injection won't work"
        )
        for mid in _DEVICE_FORGE_MOVES:
            assert mid in mapping, f"{mid} absent from _MOVE_TO_TEMPLATE"
            template_id = mapping[mid]
            template = get_template(template_id)
            assert template is not None, (
                f"{mid} maps to template_id={template_id!r} which doesn't "
                f"exist in mcp_server/device_forge/templates.py"
            )
