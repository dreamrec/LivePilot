---
name: mix
description: Mixing assistant — analyze and balance track levels, panning, and sends
---

Help the user mix their session. Follow these steps:

1. **Read the session** — `get_session_info` to see all tracks
2. **Analyze each track** — `get_track_info` for clip and device details, check current volume/pan
3. **Quick mix status** — `get_mix_summary` for a fast overview (track count, dynamics, stereo, issues)
4. **Run critics** — `get_mix_issues` to detect problems (masking, dynamics, stereo width, headroom)
5. **Suggest a mix** — propose volume levels, panning positions, and send amounts based on the track types, instruments, and detected issues
6. **Apply with confirmation** — only change levels after the user approves each suggestion
7. **Check return tracks** — `get_return_tracks` to see shared effects
8. **Master chain** — `get_master_track` to review the master
9. **Evaluate** — after changes, `evaluate_mix_move` with before/after snapshots to verify improvement

Present suggestions in a clear table format. Always explain the reasoning (e.g., "panning the hi-hats slightly right to create stereo width"). Use `undo` if the user doesn't like a change.

For deeper critic-driven iterative improvement, use the livepilot-mix-engine skill.
