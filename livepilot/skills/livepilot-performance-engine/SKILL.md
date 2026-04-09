---
name: livepilot-performance-engine
description: This skill should be used when the user asks to "perform live", "what's safe to do during a show", "scene handoff", "energy flow", "performance mode", "safe moves", or wants live performance support with safety constraints.
---

# Performance Engine — Safety-First Live Performance

The performance engine enforces a strict safety model for live performance. Every action is classified before execution. Destructive operations are blocked. Risky operations require user confirmation. Only safe operations execute freely.

## Safety Classification

Every performance action falls into one of four tiers.

### Safe — Execute Freely

These actions are non-destructive and audience-invisible if they fail. Execute without asking.

- `fire_scene` / `fire_clip` — launch scenes or clips (the core of live performance)
- `set_track_send` with small delta — nudge send levels (reverb/delay throws)
- `set_device_parameter` on mapped macros — macro knob adjustments
- `set_track_mute` / `set_track_solo` — mute/solo toggles
- `set_track_volume` with delta <= 3 dB — volume nudges
- `set_track_pan` with delta <= 0.2 — subtle pan shifts
- Filter sweeps via `set_device_parameter` on Auto Filter — smooth frequency movement

### Caution — Require User Confirmation

These actions are audible and may cause a noticeable glitch if wrong. Always ask before executing.

- `set_tempo` with delta <= 5 BPM — tempo nudge (can destabilize synced elements)
- `toggle_device` — enable/disable effects (may cause pops or silence)
- `set_track_pan` with delta > 0.2 — large pan moves are disorienting live
- `set_track_volume` with delta > 3 dB — large volume jumps

Present the action to the user: "I will [action]. This may [risk]. Confirm?"

### Blocked — Never Execute During Performance

These actions risk audible disasters, data loss, or session corruption during a live show.

- `delete_device` / `find_and_load_device` — device chain surgery causes audio interruption
- `create_arrangement_clip` / `create_clip` / `delete_clip` — clip creation/deletion
- `create_midi_track` / `create_audio_track` / `delete_track` — track structure changes
- `add_notes` / `modify_notes` / `remove_notes` — note editing while playing
- `set_clip_loop` / `set_clip_warp_mode` — clip property changes while playing
- `flatten_track` / `freeze_track` — CPU-intensive operations
- Any arrangement-view editing tools

If the user requests a blocked action during performance mode, explain why it is blocked and suggest a safe alternative: "That requires editing the device chain, which can cause audio dropouts during a live show. Instead, try [safe alternative]."

### Unknown — Treat as Blocked

Any action not explicitly classified above defaults to blocked. Do not experiment with unclassified actions during a live performance.

## Performance Loop

### Step 1 — Get State

Call `get_performance_state` to read the current session state:
- Playing status, current tempo, time signature
- Which scenes and clips are currently playing
- Track arm states, solo/mute states
- Current energy level estimate

### Step 2 — Get Safe Moves

Call `get_performance_safe_moves` to get a list of contextually appropriate safe actions based on the current state. The response is filtered by what makes musical sense right now — not just what is technically safe.

### Step 3 — Check Safety

Before executing any user request, call `check_safety(move_type)` to verify the classification. The response confirms: `safe`, `caution`, or `blocked` with an explanation.

### Step 4 — Execute Safe/Caution Only

- Safe: execute immediately
- Caution: present to user, wait for confirmation, then execute
- Blocked: refuse with explanation and alternative

### Step 5 — Scene Handoff

For transitioning between scenes (the primary live performance action), call `plan_scene_handoff(from_scene, to_scene)` to get a transition plan:

- Which clips change between the scenes
- Recommended launch timing (quantization)
- Volume/send adjustments to smooth the handoff
- Any tempo changes between scenes

Execute the handoff plan using safe actions only.

## Energy Flow

During a live set, track the energy trajectory:

1. `get_performance_state` includes an `energy_estimate` (0.0-1.0)
2. Use scene ordering to build energy arcs: low-energy scenes for intros/breakdowns, high-energy for drops/peaks
3. `plan_scene_handoff` accounts for energy delta — large energy jumps get transition suggestions

## Performance Mode Entry

When the user says "performance mode", "going live", or "starting the show":

1. Call `get_performance_state` to verify the session is ready
2. Confirm the safety model with the user: "Performance mode active. I will only execute safe actions freely and ask before caution-level moves. Destructive edits are blocked."
3. Switch to a response style optimized for speed: short confirmations, no lengthy explanations mid-performance
4. Prioritize scene launches and safe parameter nudges

## Performance Mode Exit

When the user says "done performing", "show's over", or "exit performance mode":

1. Confirm: "Performance mode ended. Full editing capabilities restored."
2. Resume normal operation with all tools available

## Emergency Actions

If something goes wrong during a live show:

- `stop_all_clips` — emergency silence (use only if requested)
- `set_master_volume(0.0)` — fade to silence
- `set_track_mute` on the problem track — isolate the issue

Never call `undo` during a live performance — it may revert a scene launch or clip state in unpredictable ways.
