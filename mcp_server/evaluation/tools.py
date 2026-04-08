"""Evaluation Fabric MCP tools — unified evaluation entry points.

Provides evaluate_with_fabric as a generic evaluation tool that routes
to the appropriate engine-specific evaluator.
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

    Routes to the appropriate engine-specific evaluator (sonic or composition).

    Args:
        engine: "sonic" or "composition"
        before_snapshot: State before the move (sonic spectrum or issue list)
        after_snapshot: State after the move (sonic spectrum or issue list)
        targets: Goal targets — for sonic: {dimension: weight}, ignored for composition
        protect: Protected dimensions — for sonic: {dimension: threshold}

    Returns:
        EvaluationResult as dict with score, keep_change, goal_progress,
        collateral_damage, dimension_changes, notes, etc.
    """
    targets = targets or {}
    protect = protect or {}

    if engine == "composition":
        # Composition engine: before/after are issue lists
        before_issues = before_snapshot.get("issues", [])
        after_issues = after_snapshot.get("issues", [])
        result = fabric.evaluate_composition_move(before_issues, after_issues)
    else:
        # Sonic engine (default): before/after are spectral snapshots
        request = EvaluationRequest(
            engine=engine or "sonic",
            goal={"targets": targets},
            before=before_snapshot,
            after=after_snapshot,
            protect=protect,
        )
        result = fabric.evaluate_sonic_move(request)

    return result.to_dict()
