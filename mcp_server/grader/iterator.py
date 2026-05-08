"""Revision-brief formatter.

Phase 1 — produces a markdown brief for the orchestrating agent (Claude Code
or composer planner) when a verdict fails. The agent is responsible for
deciding whether to retry; this module only formats the feedback.

Autonomous iteration loops land in Phase 2 once the rubric set is broader.
"""

from __future__ import annotations

from typing import Any


def format_revision_brief(verdict: dict[str, Any]) -> str:
    """Markdown brief surfacing non-pass criteria.

    Returns empty string only when there are zero `fail` and zero `warn`
    criteria. A verdict can pass overall (no blocking failures) yet still
    have advisory warnings worth surfacing — those produce an Advisory-only
    brief.
    """
    failed = [c for c in verdict["criteria"] if c["severity"] == "fail"]
    warns = [c for c in verdict["criteria"] if c["severity"] == "warn"]

    if not failed and not warns:
        return ""

    headline = "needs revision" if failed else "review advisory items"
    lines: list[str] = [
        f"# Rubric `{verdict['rubric_id']}` — {headline}",
        "",
    ]

    if failed:
        lines.append("## Blocking failures")
        for c in failed:
            lines.append(f"### {c['id']}")
            lines.append(f"- **summary:** {c['summary']}")
            for issue in c["issues"]:
                track = issue.get("track_index")
                track_ref = f" (track {track})" if track is not None else ""
                lines.append(f"- {issue['code']}{track_ref}: {issue['detail']}")
            lines.append("")

    if warns:
        lines.append("## Advisory (non-blocking)")
        for c in warns:
            lines.append(f"### {c['id']}")
            lines.append(f"- **summary:** {c['summary']}")
            for issue in c["issues"]:
                track = issue.get("track_index")
                track_ref = f" (track {track})" if track is not None else ""
                lines.append(f"- {issue['code']}{track_ref}: {issue['detail']}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
