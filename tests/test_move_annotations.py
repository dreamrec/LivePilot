"""Verify every semantic move plan_template step has a backend annotation."""

from mcp_server.semantic_moves import registry
from mcp_server.runtime.execution_router import classify_step


def test_all_plan_template_steps_have_backend():
    """Every step in every move's plan_template must have a 'backend' field."""
    missing = []
    for move_id, move in registry._REGISTRY.items():
        for i, step in enumerate(move.plan_template):
            if "backend" not in step:
                missing.append(f"{move_id} compile step {i}: {step.get('tool', '?')}")
    assert not missing, f"Steps missing backend annotation:\n" + "\n".join(missing)


def test_all_verification_steps_have_backend():
    """Every verification_plan step should also have backend."""
    missing = []
    for move_id, move in registry._REGISTRY.items():
        for i, step in enumerate(move.verification_plan):
            if "backend" not in step:
                missing.append(f"{move_id} verify step {i}: {step.get('tool', '?')}")
    assert not missing, f"Verify steps missing backend:\n" + "\n".join(missing)


def test_backend_annotations_match_classifier():
    """Declared backend must agree with the automatic classifier.

    Previously this test silently skipped when classify_step returned
    'unknown'. That meant a move step declaring backend='remote_command'
    for a tool the classifier has never heard of (typo, rename, missing
    set entry) would pass this test and then fail at dispatch time with
    'Unknown command type'. The fix treats 'unknown' as a hard failure:
    if the backend is declared, the tool MUST resolve in one of
    REMOTE_COMMANDS / BRIDGE_COMMANDS / MCP_TOOLS.
    """
    mismatches = []
    unknowns = []

    def _check(plans: list, kind: str) -> None:
        for move_id, move in registry._REGISTRY.items():
            plan = getattr(move, plans, [])
            for i, step in enumerate(plan):
                declared = step.get("backend", "")
                if not declared:
                    continue  # un-annotated steps are allowed — router classifies at runtime
                tool = step.get("tool", "")
                classified = classify_step(tool)
                if classified == "unknown":
                    unknowns.append(
                        f"{move_id} {kind} step {i}: tool={tool!r} "
                        f"declared={declared} but classifier returns 'unknown'. "
                        f"Add the tool to the appropriate set in "
                        f"mcp_server/runtime/execution_router.py or rename it."
                    )
                elif declared != classified:
                    mismatches.append(
                        f"{move_id} {kind} step {i}: tool={tool!r} "
                        f"declared={declared} but classifier returns {classified}."
                    )

    _check("plan_template", "plan")
    _check("verification_plan", "verify")

    assert not unknowns, "Unknown classifications (silent-escape bug):\n" + "\n".join(unknowns)
    assert not mismatches, "Backend mismatches:\n" + "\n".join(mismatches)
