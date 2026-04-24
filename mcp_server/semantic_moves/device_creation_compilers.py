"""Family compiler for device-creation semantic moves.

Device-creation moves generate custom M4L devices via the Device Forge
(``generate_m4l_effect``). Unlike mix/sound-design moves — where the
compiler inspects the kernel's track topology — device-creation moves
are parametric: the plan_template already contains the tool call and
concrete arguments.

v1.20.2 (BUG #1 fix): the compiler now injects ``gen_code`` at compile
time by looking up a GenExpr template from ``mcp_server/device_forge/
templates.py``. Pre-fix, each move's plan_template emitted
``generate_m4l_effect`` WITHOUT ``gen_code``, and the tool failed with
'missing 1 required positional argument: gen_code'. The templates
already existed in the device_forge module; this compiler just routes
the right template to the right move.

The v1.20.2 hybrid moves — ``build_send_chain`` + ``create_drum_rack_pad``
— don't use generate_m4l_effect, so their plan_template params pass
through unchanged.
"""
from __future__ import annotations

from .compiler import CompiledPlan, CompiledStep, register_family_compiler
from .models import SemanticMove


# BUG #1 fix (v1.20.2 / campaign report 2026-04-24).
#
# Each of the 7 Device Forge moves corresponds to one pre-existing
# GenExpr template. The compiler injects the template's `code` into the
# `gen_code` param of any `generate_m4l_effect` step belonging to the
# move. Adding a new create_* move to this map must also register a
# matching template in mcp_server/device_forge/templates.py.
_MOVE_TO_TEMPLATE: dict[str, str] = {
    "create_chaos_modulator": "lorenz_attractor",
    "create_feedback_resonator": "resonator",
    "create_wavefolder_effect": "wavefolder",
    "create_bitcrusher_effect": "bitcrusher",
    "create_karplus_string": "karplus_strong",
    "create_stochastic_texture": "stochastic_resonance",
    "create_fdn_reverb": "feedback_delay_network",
}


def _compile_device_creation(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Map plan_template steps to CompiledStep, injecting Device Forge
    `gen_code` and threading `track_index` through `find_and_load_device`."""
    # v1.21 parity-gate fix: thread track_index from seed_args into
    # find_and_load_device steps. Pre-fix, plan_templates emitted the
    # ergonomic key ``query`` with no track_index — broken at runtime
    # since pre-v1.20 because the ``remote_command`` backend bypasses
    # MCP normalization and Ableton's handler requires
    # ``track_index`` + ``device_name``.
    seed_args = kernel.get("seed_args") or {}
    track_index = seed_args.get("track_index")
    needs_load_step = any(
        s.get("tool") == "find_and_load_device" for s in move.plan_template
    )
    if needs_load_step and track_index is None:
        return CompiledPlan(
            move_id=move.move_id,
            intent=move.intent,
            steps=[],
            risk_level=move.risk_level,
            summary=f"{move.move_id} requires seed_args.track_index",
            warnings=[
                f"{move.move_id} requires seed_args.track_index (int) to "
                "load the generated device onto a track. Example: "
                f"apply_semantic_move(\"{move.move_id}\", mode=\"explore\", "
                "args={\"track_index\": 0})"
            ],
        )

    # Resolve the GenExpr template once per compile (idempotent).
    template_code: str | None = None
    template_id = _MOVE_TO_TEMPLATE.get(move.move_id)
    if template_id is not None:
        # Local import so the semantic_moves package doesn't hard-depend on
        # device_forge; the branch is only taken for the 7 create_* moves.
        from ..device_forge.templates import get_template
        template = get_template(template_id)
        if template is not None:
            template_code = template.code

    warnings: list[str] = []
    steps: list[CompiledStep] = []
    for step in move.plan_template:
        params = dict(step.get("params") or {})
        tool = step.get("tool", "")

        # Inject gen_code for Device Forge moves. Done BEFORE CompiledStep
        # construction so the step snapshot is correct, not mutated later.
        if template_code is not None and tool == "generate_m4l_effect":
            params["gen_code"] = template_code

        # v1.21: inject track_index into find_and_load_device. plan_templates
        # now emit {"device_name": ...} (wire-format key); compiler adds
        # {"track_index": ...} from seed_args so the remote_command backend
        # sends a handler-compatible payload.
        if tool == "find_and_load_device":
            params["track_index"] = track_index

        steps.append(CompiledStep(
            tool=tool,
            params=params,
            description=step.get("description", ""),
            verify_after=bool(step.get("verify_after", True)),
            backend=step.get("backend"),
        ))

    # Guard: if the move expected template injection but the template
    # went missing, surface a clear warning instead of letting the move
    # ship with an empty gen_code. Shouldn't fire under normal operation.
    if template_id is not None and template_code is None:
        warnings.append(
            f"Device Forge template {template_id!r} not found — "
            f"generate_m4l_effect call will fail. Check "
            f"mcp_server/device_forge/templates.py"
        )

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level=move.risk_level,
        summary=move.intent,
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=warnings,
    )


register_family_compiler("device_creation", _compile_device_creation)
