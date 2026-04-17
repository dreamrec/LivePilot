# Max Freeze Workflow — producing a complete `.amxd`

This doc covers rebuilding `m4l_device/LivePilot_Analyzer.amxd` so first-time
users get a fully-functional analyzer **without** a separate FluCoMa install.

## Two freeze strategies

| Strategy | `.amxd` size | Ships with | End-user cost |
|---|---|---|---|
| **Thin freeze** (current default) | ~100 KB | Patcher + JS only | Must install FluCoMa via `npx livepilot --setup-flucoma` or Max Package Manager |
| **Fat freeze** (recommended for release) | ~6.7 MB | Patcher + JS + all FluCoMa externals for both macOS + Windows | Zero-config — works on fresh installs |

Thin freeze is faster to iterate on. Fat freeze is what you commit for a
release. Always ship fat for a version bump.

## Prerequisites

Before freezing, the JS source must be correct AND the Max 9 search path
must have the JS file that matches the repo source. This catches
`feedback_amxd_freeze_drift` (Max freezes from the search-path cache,
not the source directory).

```bash
cd /path/to/LivePilot

# Sync the JS to every Max search-path location
cp m4l_device/livepilot_bridge.js \
   "$HOME/Documents/Max 9/Max for Live Devices/LivePilot_Analyzer Project/code/livepilot_bridge.js"
cp m4l_device/livepilot_bridge.js \
   "$HOME/Documents/Max 8/Max for Live Devices/LivePilot_Analyzer Project/code/livepilot_bridge.js"
cp m4l_device/livepilot_bridge.js \
   "$HOME/Documents/Max 8/livepilot_bridge.js"
cp m4l_device/livepilot_bridge.js \
   "$HOME/Documents/Max 8/Library/livepilot_bridge.js"
cp m4l_device/livepilot_bridge.js \
   "$HOME/Documents/Max 8/Max for Live Devices/livepilot_bridge.js"

# Verify md5 parity
md5 m4l_device/livepilot_bridge.js \
    "$HOME/Documents/Max 9/Max for Live Devices/LivePilot_Analyzer Project/code/livepilot_bridge.js"
```

## Fat freeze procedure (macOS + Windows externals bundled)

This requires the `.maxproj` file that declares FluCoMa externals as
dependencies. The repo keeps the `.maxproj` in the Max 9 project
directory. If it's missing, see "First-time .maxproj setup" below.

### Step-by-step

1. **Open Max 9**
2. **File → Open Project...** — navigate to
   `~/Documents/Max 9/Max for Live Devices/LivePilot_Analyzer Project/LivePilot_Analyzer.maxproj`
   - This opens the Project Window showing patchers, code, externals
3. **In Project Window:** right-click the project root → **Consolidate...**
   - Max scans the patcher and copies all referenced dependencies
     (externals, sub-patchers, media) into the project folder
4. **Double-click `LivePilot_Analyzer.maxpat` in Project Window**
   - Patcher opens with full dependency context
5. **Patcher menu → Freeze Device**
   - Max embeds all dependencies — JS, externals (`.mxo` for macOS +
     `.mxe64` for Windows), sub-patchers — inside the `.amxd`
6. **File → Save As...** over `m4l_device/LivePilot_Analyzer.amxd`
   - Keep the same filename
7. **Verify fat freeze:**
   ```bash
   python3 -c "
   d = open('m4l_device/LivePilot_Analyzer.amxd', 'rb').read()
   mach_o = d.count(b'\\xfe\\xed\\xfa\\xcf') + d.count(b'\\xcf\\xfa\\xed\\xfe')
   pe = d.count(b'PE\\x00\\x00')
   print(f'size: {len(d):,} bytes | Mach-O: {mach_o} | PE: {pe}')
   "
   ```
   Expected: size ≥ 6 MB, Mach-O ≥ 12, PE ≥ 24. If all zero, the freeze
   missed externals — check the project folder has them.

### Troubleshooting

**Result is ~100 KB (thin):** Max didn't recognize the folder as a
project. Re-verify:
- `.maxproj` exists at `~/Documents/Max 9/Max for Live Devices/LivePilot_Analyzer Project/LivePilot_Analyzer.maxproj`
- You opened it via File → Open Project, not by double-clicking the `.maxpat`
- The project's Contents panel shows `externals/` with the FluCoMa files

**Freeze fails with "missing external":** FluCoMa externals aren't on
Max's search path. Run `npx livepilot --setup-flucoma` (installs to
`~/Documents/Max 9/Packages/FluidCorpusManipulation/`) and retry.

**Presentation mode lost on freeze:** Confirm with Patcher → Inspector
that "Open in Presentation" is checked before freezing. This writes
`"openinpresentation" : 1` into the patcher JSON.

## First-time `.maxproj` setup

If the `.maxproj` manifest is missing from the Max 9 project directory,
the repo has a reference copy at
`m4l_device/LivePilot_Analyzer.maxproj` — copy it to
`~/Documents/Max 9/Max for Live Devices/LivePilot_Analyzer Project/`
before running the fat-freeze workflow.

The manifest declares all expected FluCoMa externals with `"local": 1`,
which tells Max "bundle these on freeze."

## Thin freeze (for dev iteration)

When you're iterating on bridge JS / patcher edits and don't need a
release-ready `.amxd`:

1. Open `LivePilot_Analyzer.maxpat` directly (not the project)
2. Patcher → Freeze Device
3. Save As → `m4l_device/LivePilot_Analyzer.amxd`

Result is ~100 KB. Works on any machine that has FluCoMa installed via
Max Package Manager. Do NOT ship this for releases.

## Related

- `feedback_amxd_freeze_drift.md` — JS search-path cache trap
- `feedback_remote_script_module_cache.md` — Python side of the same pattern
- `CHANGELOG.md` — batch 19 (thin freeze lost externals), batch 20 (reload
  plumbing), batch 21 (this workflow doc + key display fix)
