---
name: mix
description: Mixing assistant — analyze and balance track levels, panning, and sends
---

Help the user mix their session. Follow these steps:

1. **Read the session** — `get_session_info` to see all tracks
2. **Ensure analyzer** — check if M4L Analyzer is on master. If `get_master_spectrum` errors, load it: `find_and_load_device(track_index=-1000, device_name="LivePilot_Analyzer")`. If bridge disconnected, try `reconnect_bridge`.
3. **Analyze each track** — `get_track_info` for clip and device details, `get_track_meters(include_stereo=true)` for actual output levels
4. **Quick mix status** — `get_mix_summary` for a fast overview (track count, dynamics, stereo, issues)
5. **Run critics** — `get_mix_issues` to detect problems (masking, dynamics, stereo width, headroom). For frequency collisions: `get_masking_report`
6. **Spectral check** — `get_master_spectrum` for 8-band frequency balance. Typical targets:
   - Hip-hop: sub dominant, centroid 400-800 Hz
   - Electronic: balanced, centroid 800-1500 Hz
   - Ambient: mid-focused, low sub, centroid 500-1000 Hz
7. **Suggest a mix** — propose volume levels, panning positions, and send amounts based on the track types, instruments, and detected issues
8. **Apply with verification** — after EVERY volume/pan/send change:
   - Read `value_string` in the response
   - Call `get_track_meters(include_stereo=true)` to verify no track went silent
   - Check master spectrum to verify the balance improved
9. **Check return tracks** — `get_return_tracks` to see shared effects
10. **Master chain** — `get_master_track` to review the master. Typical chain: Glue Compressor → EQ Eight → Utility → LivePilot_Analyzer
11. **Capture + analyze** — `capture_audio` then `analyze_loudness` for LUFS/peak/LRA, `analyze_spectrum_offline` for centroid/rolloff/balance
12. **Evaluate** — `evaluate_mix_move` with before/after snapshots to verify improvement. If `keep_change` is false, `undo` immediately.

Present suggestions in a clear table format. Always explain the reasoning (e.g., "panning the hi-hats slightly right to create stereo width"). Use `undo` if the user doesn't like a change.

For deeper critic-driven iterative improvement, use the livepilot-mix-engine skill.
