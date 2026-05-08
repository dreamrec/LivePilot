#!/usr/bin/env python3
"""Phase 2c-α deep test — runs all 5 rubrics against the live Ableton session.

Usage:
    .venv/bin/python scripts/grader_deep_test.py

Briefly takes the TCP 9878 slot. Kill the MCP first (per the standing rule:
the active session wins). The MCP's parent node process will respawn the
MCP after this script exits.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp_server.connection import AbletonConnection  # noqa: E402
from mcp_server.grader import client as grader_client  # noqa: E402
from mcp_server.grader import iterator as grader_iterator  # noqa: E402


def build_light_state(ableton: AbletonConnection) -> dict:
    """Mirror of mcp_server.grader.tools._build_light_state."""
    session = ableton.send_command("get_session_info") or {}
    track_count = int(session.get("track_count") or 0)

    tracks: list[dict] = []
    for idx in range(track_count):
        info = ableton.send_command("get_track_info", {"track_index": idx})
        if not info:
            continue
        if info.get("is_foldable") and info.get("is_master"):
            continue
        if info.get("is_return"):
            continue
        tracks.append({
            "index": idx,
            "name": info.get("name") or f"track_{idx}",
            "mixer": info.get("mixer") or {},
            "devices": info.get("devices") or [],
        })
    return {"tracks": tracks, "session_meta": {
        "tempo": session.get("tempo"),
        "is_playing": session.get("is_playing"),
        "track_count_total": track_count,
    }}


def render_verdict(rubric_id: str, verdict: dict, brief: str) -> str:
    lines = [
        "",
        "=" * 72,
        f"  RUBRIC: {rubric_id}",
        f"  passed={verdict['passed']}",
        "=" * 72,
    ]
    for c in verdict["criteria"]:
        sev = c["severity"].upper().rjust(4)
        lines.append(f"  [{sev}] {c['id']}: {c['summary']}")
        if c["severity"] in ("warn", "fail") and c.get("issues"):
            for issue in c["issues"][:6]:
                track_ref = (
                    f" (track {issue['track_index']})"
                    if issue.get("track_index") is not None
                    else ""
                )
                lines.append(f"        - {issue['code']}{track_ref}: {issue['detail']}")
            if len(c["issues"]) > 6:
                lines.append(f"        ... +{len(c['issues']) - 6} more")
    if brief:
        lines.append("")
        lines.append("  REVISION BRIEF:")
        for ln in brief.splitlines():
            lines.append(f"    {ln}")
    return "\n".join(lines)


def main() -> int:
    print(f"[deep-test] connecting to Ableton on 127.0.0.1:9878 ...")
    ab = AbletonConnection()
    started = time.time()
    try:
        ab.connect()
    except Exception as exc:
        print(f"[deep-test] FAILED to connect: {exc}")
        print(f"[deep-test] Hint: kill the running MCP server first.")
        return 2

    try:
        print(f"[deep-test] connected in {(time.time() - started) * 1000:.0f}ms")
        state = build_light_state(ab)
        meta = state["session_meta"]
        print(
            f"[deep-test] session: {meta['track_count_total']} tracks total, "
            f"{len(state['tracks'])} non-master/return after filter, "
            f"tempo={meta['tempo']}, playing={meta['is_playing']}"
        )

        # Print track summary (so user can correlate to verdicts)
        print()
        print(f"  {'idx':>4} {'name':<38} {'volume':>7}  {'devices'}")
        for t in state["tracks"]:
            vol = t["mixer"].get("volume")
            vol_s = f"{vol:.3f}" if isinstance(vol, (int, float)) else str(vol)
            dev_classes = ", ".join(d.get("class_name", "?") for d in t["devices"][:4])
            if len(t["devices"]) > 4:
                dev_classes += f" +{len(t['devices']) - 4}"
            print(f"  {t['index']:>4} {t['name'][:38]:<38} {vol_s:>7}  {dev_classes}")

        rubric_state = {"tracks": state["tracks"]}
        for rubric_id in grader_client.list_rubrics():
            verdict = grader_client.evaluate(rubric_id, rubric_state)
            brief = grader_iterator.format_revision_brief(verdict)
            print(render_verdict(rubric_id, verdict, brief))

    finally:
        ab.disconnect()
        print()
        print(f"[deep-test] disconnected; total {(time.time() - started) * 1000:.0f}ms")

    return 0


if __name__ == "__main__":
    sys.exit(main())
