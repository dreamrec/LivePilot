"""Creative Director MCP tools — v1.18.3+ brief compliance.

Exposes `check_brief_compliance` as an MCP tool so the
`livepilot-creative-director` skill can call it before each risky
Phase 6 tool execution. Caller passes the compiled brief dict + the
intended tool call; the tool returns a violations report.

Stateless by design: no session storage of the active brief. The
director passes the brief each time. Full session-state active-brief
storage is v1.19 scope.
"""

from __future__ import annotations

from typing import Any, Optional

from fastmcp import Context

from ..server import mcp
from .compliance import check_brief_compliance as _check_brief_compliance
from .hybrid import compile_hybrid_brief as _compile_hybrid_brief


@mcp.tool()
def check_brief_compliance(
    ctx: Context,
    brief: dict,
    tool_name: str,
    tool_args: Optional[dict] = None,
) -> dict:
    """Check whether an intended tool call complies with the active creative brief.

    v1.18.3 #7 + #8 runtime enforcement for the director's anti_patterns
    and locked_dimensions brief fields. Call this BEFORE executing any
    risky tool from director's Phase 6 — especially when the brief has
    non-empty anti_patterns or locked_dimensions.

    brief: the compiled Creative Brief dict. May contain anti_patterns
           (list of prose phrases), locked_dimensions (list of:
           structural/rhythmic/timbral/spatial), reference_anchors, etc.
    tool_name: the MCP tool name you're about to call.
    tool_args: dict of arguments you'll pass to that tool.

    Returns:
        {
          "ok": bool,
          "violations": [
            {
              "rule": "anti_pattern" | "locked_dimension",
              "detail": <the anti_pattern phrase OR the locked dimension>,
              "reason": "Why this call appears to violate the brief",
              "suggestion": "What to do about it",
            },
            ...
          ],
        }

    Violations are NEVER automatic blocks — they're reports. The
    director decides whether to proceed, surface to user, or abandon.
    Empty brief (no anti_patterns, no locked_dimensions) always
    returns ok=True.

    Best-effort keyword heuristic, NOT semantic understanding. Will
    miss subtle violations (e.g., 'too muddy' → 300 Hz cut needs
    judgment this checker doesn't have). Will catch obvious ones
    (e.g., 'bright top-end' → Hi Gain positive boost).
    """
    result = _check_brief_compliance(
        brief=brief,
        tool_name=tool_name,
        tool_args=tool_args or {},
    )
    return result


@mcp.tool()
def compile_hybrid_brief(
    ctx: Context,
    packet_ids: list,
    weights: Optional[list] = None,
) -> dict:
    """Merge 2+ concept packets into a single hybrid brief (v1.19 Item B).

    When the user says "Basic Channel meets Dilla swing" or
    "Villalobos but sparse like Gas", the director needs an explicit
    merge algorithm — not LLM ad-hoc reasoning. This tool loads the
    named concept packets from
    ``livepilot/skills/livepilot-core/references/concepts/`` and merges
    them per the rules in
    ``livepilot/skills/livepilot-creative-director/references/hybrid-compilation.md``.

    Merge rule summary:
      - ``sonic_identity`` / ``avoid`` / ``reach_for.*`` / ``*_idioms``:
        UNION, deduplicated, first-packet order preserved.
      - ``dimensions_deprioritized`` and
        ``move_family_bias.deprioritize``: INTERSECTION — only
        deprioritize if ALL source packets do. Safer default for
        hybrids where one packet may want what the other ignores.
      - ``move_family_bias.favor``: INTERSECTION when non-empty
        (hybrid focuses where both agree); UNION fallback otherwise
        with a warning.
      - ``evaluation_bias.target_dimensions``: WEIGHTED AVERAGE
        (default uniform weights).
      - ``evaluation_bias.protect``: MAX per dimension — stricter
        floor wins.
      - ``novelty_budget_default``: MAX (hybrids skew exploratory).
      - ``tempo_hint``: NEAREST-OVERLAP — intersect overlapping
        ranges, or warn + midpoint on disjoint ranges.

    Args:
      packet_ids: list of ≥2 packet IDs. Accepts filename stems
        (``"basic-channel"``), aliases (``"dilla"``), or packet ``id``
        values (``"dub_techno__basic_channel"``).
      weights: optional per-packet weights for the
        ``target_dimensions`` average. Must match ``packet_ids``
        length. Normalized internally; defaults to uniform.

    Returns:
      A brief dict structurally compatible with
      ``check_brief_compliance``. Exposes the merged ``avoid`` list
      both as ``avoid`` (packet semantic) and ``anti_patterns``
      (brief semantic). Includes a ``warnings`` list surfacing any
      ambiguity the merge algorithm couldn't resolve cleanly.

    Raises:
      ValueError (surfaced as an error-dict response) on fewer than
      2 packets, an unresolvable packet id, or a weights-length
      mismatch.
    """
    try:
        pid_list = [str(x) for x in (packet_ids or [])]
        w_list = [float(x) for x in weights] if weights else None
        return _compile_hybrid_brief(packet_ids=pid_list, weights=w_list)
    except ValueError as exc:
        return {"error": str(exc)}
