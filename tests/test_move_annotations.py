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
    """Declared backend should agree with the automatic classifier."""
    mismatches = []
    for move_id, move in registry._REGISTRY.items():
        for i, step in enumerate(move.plan_template):
            declared = step.get("backend", "")
            tool = step.get("tool", "")
            classified = classify_step(tool)
            if declared and classified != "unknown" and declared != classified:
                mismatches.append(
                    f"{move_id} step {i}: tool={tool} declared={declared} classified={classified}"
                )
    assert not mismatches, f"Backend mismatches:\n" + "\n".join(mismatches)
