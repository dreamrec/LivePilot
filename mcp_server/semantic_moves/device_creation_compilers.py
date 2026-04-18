"""Family compiler for device-creation semantic moves.

Device-creation moves generate custom M4L devices via the Device Forge
(``generate_m4l_effect``). Unlike mix/sound-design moves — where the
compiler inspects the kernel's track topology — device-creation moves
are parametric: the plan_template already contains the tool call and
concrete arguments.

We therefore use a single family-level compiler that just maps
``plan_template`` → ``CompiledStep`` objects. This keeps the registry
honest (every move is either compilable or analytical_only) without
duplicating templates into per-move compilers.
"""
from __future__ import annotations

from .compiler import CompiledPlan, CompiledStep, register_family_compiler
from .models import SemanticMove


def _compile_device_creation(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Map plan_template steps straight to CompiledStep.

    plan_template is trusted for this family: each step already has
    ``tool``, ``params``, ``description``, and ``backend`` annotated.
    """
    steps: list[CompiledStep] = []
    for step in move.plan_template:
        steps.append(CompiledStep(
            tool=step.get("tool", ""),
            params=step.get("params", {}),
            description=step.get("description", ""),
            verify_after=bool(step.get("verify_after", True)),
            backend=step.get("backend"),
        ))

    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=steps,
        risk_level=move.risk_level,
        summary=move.intent,
        requires_approval=(kernel.get("mode", "improve") != "explore"),
        warnings=[],
    )


register_family_compiler("device_creation", _compile_device_creation)
