# LivePilot MIDI Tool — Max for Live Build Guide

Step-by-step instructions to build `LivePilot_MIDITool.amxd` in Max 9.
The device is a Live 12 MIDI Tool (Generator or Transformation) that
bridges a clip's note list + context to LivePilot's MCP server, so
LivePilot generators (euclidean, tintinnabuli, humanize, ...) run
inside Live's native scale / selection / seed / tuning context.

Budget: ~15 minutes in Max if you follow the steps verbatim.

## Prerequisites

- Ableton Live 12 Suite (includes Max for Live 9)
- `miditool_bridge.js` in the same directory as the `.amxd` (or added
  to Max's File Preferences)
- Analyzer bridge already works end-to-end (shares UDP 9880/9881)
  — this is not strictly required, but it's the quickest way to confirm
  your local UDP path is healthy before you start.

## Step 1: Create a new Max MIDI Effect

1. In Live, add a fresh **MIDI** track (Shift+Cmd+T).
2. In the browser, drag **Max MIDI Effect** onto the track.
3. Click the **pencil (Edit)** icon on the device title bar to open the
   Max editor.

You'll see an empty patcher with `[midiin]` and `[midiout]` passing
through. Leave those — a MIDI Tool still lives inside a MIDI Effect
wrapper, and MIDI pass-through keeps the device usable outside of
Transformation/Generator mode.

## Step 2: Add the MIDI Tool endpoints

These two objects are what make this a MIDI Tool rather than a
plain MIDI Effect.

1. Add `[live.miditool.in]`. Its **right outlet** emits a
   **context dictionary**: `grid`, `selection` (`start`/`end`),
   `scale` (`root`, `name`, `mode`), `seed`, `tuning`.
   Its **left outlet** emits the **notes list** (dict-per-note).
2. Add `[live.miditool.out]`. The left inlet accepts dictionary
   notes one at a time, plus a final `done` bang to commit the batch.

**Generator vs. Transformation** — in `live.miditool.in`'s Max
Inspector, the `Mode` attribute picks which slot this device fills:

- `Transformation` — runs over an existing selection, receives the
  selection's notes in `notes`. Best for humanize/tintinnabuli.
- `Generator` — runs over an empty selection, receives an empty
  `notes` list plus the selection range in `context.selection`.
  Best for euclidean_rhythm.

For our bridge, either mode works because the JS passes the full
note list + context through unchanged. Pick **Transformation** to
start — it's easier to test.

## Step 3: Add the JS bridge

1. Add `[js miditool_bridge.js]`.
   Copy `miditool_bridge.js` from this repo's `m4l_device/` folder
   into the same folder as the `.amxd` you're about to save, or add
   that folder to Max's File Preferences so Max can find it.

   The JS object has **3 inlets** and **2 outlets** by `autowatch`.

2. Wire the context + notes:
   - `live.miditool.in` **right** outlet → `[js]` **inlet 1** (context)
   - `live.miditool.in` **left** outlet → `[js]` **inlet 2** (notes)

3. Wire the notes back to Live:
   - `[js]` **outlet 1** → `live.miditool.out` **left inlet**

## Step 4: Add the UDP transport

1. Add `[udpreceive 9881]` — incoming OSC from the MCP server.
2. Add `[udpsend 127.0.0.1 9880]` — outgoing OSC to the MCP server.

Wire them:
- `[udpreceive 9881]` outlet → `[js]` **inlet 0** (OSC commands)
- `[js]` **outlet 0** → `[udpsend 127.0.0.1 9880]`

**Note** — these are the same ports the LivePilot Analyzer uses.
That's intentional; the OSC address prefix (`/miditool/*` vs
`/spectrum`, `/response`, ...) distinguishes traffic. No port
collision with the analyzer, and a user who already has the analyzer
bridge running loses no capability.

## Step 5: Fire initialization on device load

1. Add `[live.thisdevice]`.
2. Connect its **left outlet** (bang on load) → `[js]` **inlet 0**.

The JS `bang()` handler announces itself to the server with
`/miditool/ready`, which flips the server's `MidiToolCache.is_connected`
to `True` so `get_miditool_context()` reports a healthy bridge.

## Step 6: Freeze the device

1. **File → Freeze Device** (this is critical — without freezing, Live
   will refuse to save the patcher as an .amxd).
2. When prompted, include `miditool_bridge.js` in the dependency list
   so the .amxd carries its JS inside the file, not as a sibling path.
3. Verify: click the **snowflake** icon in the Max title bar — should
   say "Frozen".

If the device was already frozen before you last edited the JS, you
MUST re-freeze to pick up source changes. A known pitfall (the
"Simpler Snap" drift problem from the analyzer history): Max caches
frozen JS inside the .amxd, so a source edit doesn't re-export unless
you explicitly freeze again.

## Step 7: Save as LivePilot_MIDITool.amxd

1. **File → Save As** (Cmd+Shift+S in Max).
2. Filename: `LivePilot_MIDITool.amxd` (exact name — the installer
   looks for it).
3. Location: either the repo's `m4l_device/` folder (so
   `install_miditool_device()` can copy it into User Library), or
   directly at
   `~/Music/Ableton/User Library/Presets/MIDI Effects/Max MIDI Effect/`.

## Step 8: Install into Ableton's User Library

From the MCP server (Codex, Claude Code, etc.):

```
install_miditool_device()
```

This copies `m4l_device/LivePilot_MIDITool.amxd` into
`~/Music/Ableton/User Library/Presets/MIDI Effects/Max MIDI Effect/`.
The tool returns `{installed_path, existed_before, ...}` — check
`existed_before: false` on the first install.

If you saved directly into the User Library in Step 7, skip this.

## Step 9: Drop it into a clip's MIDI Tool slot

1. In Live, select a MIDI clip. Open its **Clip view**.
2. In the **MIDI Transformations** or **MIDI Generators** rack
   (depending on which `Mode` you chose in Step 2), click the
   **+** button.
3. Choose **LivePilot_MIDITool** from the list.

## Step 10: Configure the target generator

From the MCP server:

```
set_miditool_target(
    tool_name="euclidean_rhythm",
    params={"steps": 16, "pulses": 5}
)
```

The server stores the config and pushes it to the JS bridge too.
Call `list_miditool_generators()` to see the full registry.

## Step 11: Fire the tool

1. In Live, select the clip region you want to transform.
2. Click the **Fire / Apply** button on the MIDI Tool rack.

Live:
- emits the selection's notes + context via `live.miditool.in`,
- our JS bundles them with a fresh `request_id` and ships them
  to the server over `/miditool/request`,
- the server runs the configured generator (`euclidean_rhythm`,
  `tintinnabuli`, or `humanize`),
- the server replies with `/miditool/response` carrying the
  transformed notes,
- our JS emits them back to `live.miditool.out`, which writes
  them into the clip.

End-to-end round-trip is typically under 10 ms on loopback UDP.

## Signal Flow Summary

```
     ┌────────────────────────────────────────────────────────────┐
     │             LivePilot_MIDITool.amxd                         │
     │                                                             │
     │  Live clip                                                  │
     │    │                                                        │
     │    ▼                                                        │
     │  [live.miditool.in]                                         │
     │    │ left (notes)     right (context dict)                  │
     │    │                  │                                     │
     │    ▼                  ▼                                     │
     │  ┌──────────────────────────────────┐                       │
     │  │ [js miditool_bridge.js]           │                       │
     │  │   inlet 0 ← [udpreceive 9881]     │                       │
     │  │   outlet 0 → [udpsend 9880]       │─▶ MCP server          │
     │  │   outlet 1 ──┐                    │◀─ /miditool/response  │
     │  └──────────────┼────────────────────┘                       │
     │                 ▼                                            │
     │        [live.miditool.out] → Live clip                       │
     └────────────────────────────────────────────────────────────┘
```

## Troubleshooting

**`get_miditool_context()` returns `{"connected": false}`**
- Drop the device into a clip's MIDI Tool slot (not just onto a track).
- Check Max Console for "LivePilot MIDI Tool Bridge: initialized" — if
  missing, `live.thisdevice` isn't wired to the JS.
- Check UDP port 9881 isn't already held by something else:
  `lsof -i UDP:9881`.

**Notes aren't coming back to Live (clip unchanged after Fire)**
- Confirm `set_miditool_target` was called and returned
  `config_pushed_to_bridge: true`. If `false`, the JS bridge can't
  be reached — re-open the clip and fire again to trigger a new
  `/miditool/ready`.
- Check Max Console for `LivePilot MIDI Tool Bridge: bad response`
  — the JSON came through but the JS couldn't parse it. File a bug.
- Verify the MCP server is running and bound to UDP 9880. If the
  analyzer bridge works, this path works too.

**Server logs "miditool generator 'X' failed"**
- Your `params` dict is missing a required field, or a value is out
  of range. Call `list_miditool_generators()` to see each
  generator's required/optional params. The bridge falls back to
  passing the original notes through unchanged when a generator
  raises.

**Port conflict with the Analyzer**
- None by design — the analyzer uses `/spectrum`, `/peak`, `/rms`,
  `/pitch`, `/response`, `/capture_complete`. The MIDI Tool uses
  `/miditool/request`, `/miditool/ready`. Both share the same UDP
  sockets; only the OSC prefix differs.

**"LivePilot_MIDITool.amxd not found" when calling install**
- You haven't built the .amxd yet, or you saved it under a
  different filename. The installer looks for the exact name
  `LivePilot_MIDITool.amxd` in `m4l_device/`. Rename and retry.

**Windows install**
- Not yet supported by `install_miditool_device()`. Copy the
  `.amxd` manually to
  `%USERPROFILE%\Documents\Ableton\User Library\Presets\MIDI Effects\Max MIDI Effect\`.

## Editing Checklist — When You Modify `miditool_bridge.js`

Max freezes the JS inside the .amxd binary. Source edits do NOT
re-export automatically. After editing:

1. Open the .amxd in Max editor (pencil icon).
2. **File → Unfreeze Device** so Max re-reads the source.
3. Edit / save the JS.
4. **File → Freeze Device** (include `miditool_bridge.js` in deps).
5. Save the .amxd.
6. Re-run `install_miditool_device()` so the User Library copy
   picks up your changes.

This is the same "Simpler Snap drift" problem that bit the analyzer
bridge twice during v1.10.x — the source doesn't refresh the frozen
copy without manual action.
