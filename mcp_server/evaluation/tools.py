"""Evaluation Fabric MCP tools — unified evaluation entry points.

Provides evaluate_with_fabric as a generic evaluation tool that routes
to the appropriate engine-specific evaluator via fabric.evaluate().
"""

from __future__ import annotations

from mcp.server.fastmcp import Context

from ..server import mcp
from ..tools._evaluation_contracts import EvaluationRequest, EvaluationResult
from ..tools._snapshot_normalizer import normalize_sonic_snapshot
from . import fabric


@mcp.tool()
async def evaluate_with_fabric(
    ctx: Context,
    engine: str,
    before_snapshot: dict,
    after_snapshot: dict,
    targets: dict | None = None,
    protect: dict | None = None,
) -> dict:
    """Evaluate a move using the unified Evaluation Fabric.

    Routes to the appropriate engine-specific evaluator.

    Args:
        engine: "sonic", "composition", "mix", "transition", or "translation"
        before_snapshot: State before the move (format depends on engine)
        after_snapshot: State after the move (format depends on engine)
        targets: Goal targets — for sonic: {dimension: weight}, ignored for others
        protect: Protected dimensions — for sonic: {dimension: threshold}

    Returns:
        EvaluationResult as dict with score, keep_change, goal_progress,
        collateral_damage, dimension_changes, notes, etc.
    """
    targets = targets or {}
    protect = protect or {}

    request = EvaluationRequest(
        engine=engine or "sonic",
        goal={"targets": targets},
        before=before_snapshot,
        after=after_snapshot,
        protect=protect,
    )

    result = fabric.evaluate(request)
    return result.to_dict()
