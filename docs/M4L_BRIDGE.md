# LivePilot M4L Bridge — Technical Reference

The M4L Bridge is a Max for Live Audio Effect (`LivePilot_Analyzer.amxd`) that sits on the master track and gives LivePilot deep access to Ableton's Live Object Model via Max's `LiveAPI` JavaScript interface. It also streams real-time spectral analysis data.

## Architecture

```
                TCP:9878
MCP Server  <=============>  Remote Script (ControlSurface)
  (Python)                     (Ableton Python)
     |
     |   UDP:9880 (M4L -> Server)      ┌─────────────────────┐
     |<---------------------------------| LivePilot Analyzer   |
     |   OSC:9881 (Server -> M4L)      | (.amxd on master)    |
     |--------------------------------->|                      |
                                        └─────────────────────┘
```

**Three communication channels:**
- **TCP 9878** — existing LivePilot command channel (Remote Script <-> MCP Server)
- **UDP 9880** — M4L device sends spectral data stream and LiveAPI responses to MCP Server
- **OSC 9881** — MCP Server sends LiveAPI commands to M4L device

The bridge is optional. All 149 core tools work without it. The 29 analyzer tools require the device on the master track.

## Audio Signal Chain

```
[plugin~] ──L──┬── [plugout~]              (pass-through, zero latency)
          ──R──┤
               ├── [+~] (L+R mono sum)
               │    ├── [fffb~ 8]          (8-band filter bank)
               │    │    └── 8x [abs~] -> [snapshot~ 200] -> udpsend /spectrum
               │    │
               │    ├── [peakamp~ 200]     (peak amplitude)
               │    │    └── [snapshot~ 200] -> udpsend /peak
               │    │
               │    ├── [average~ 200 rms] (RMS level)
               │    │    └── [snapshot~ 200] -> udpsend /rms
               │    │
               │    └── [sigmund~ pitch env npts 2048]  (pitch tracking)
               │         └── [snapshot~ 200] -> livepilot_bridge.js pitch_in()
               │
               └── [js livepilot_bridge.js]
                    ├── [udpreceive 9881]   (incoming commands)
                    └── [udpsend 127.0.0.1 9880] (responses)
```

### 8-Band Spectrum (fffb~)

| Band | Range | Musical Content |
|------|-------|-----------------|
| 0 | Sub (20-60 Hz) | Sub bass, kick fundamental |
| 1 | Low (60-200 Hz) | Bass body, kick body |
| 2 | Low-mid (200-500 Hz) | Warmth, mud zone |
| 3 | Mid (500-2000 Hz) | Body, presence |
| 4 | High-mid (2000-4000 Hz) | Presence, attack |
| 5 | High (4000-8000 Hz) | Brightness, air |
| 6 | Presence (8000-12000 Hz) | Shimmer, sibilance |
| 7 | Air (12000-20000 Hz) | Air, sparkle |

Sampling rate: 5 Hz (200ms snapshots). CPU impact: ~3-4% total.

## OSC Protocol

### Outgoing (M4L -> Server, UDP 9880)

```
/spectrum  f f f f f f f f    8 band amplitudes (0.0-1.0)
/peak      f                  Peak amplitude (0.0-1.0)
/rms       f                  RMS amplitude (0.0-1.0)
/pitch     f f                MIDI note (fractional), amplitude
/key       s s                Key name, scale name
/response  s                  Base64-encoded JSON (single packet)
/response_chunk  i i s        Chunk index, total chunks, base64 data
```

### Incoming (Server -> M4L, OSC 9881)

Commands are sent WITHOUT a leading `/` in the OSC address. This is critical — see "OSC Address Dispatch" below.

## Bridge Commands (28 total)

### Phase 1: Core LOM Access

| Command | Args | Description |
|---------|------|-------------|
| `ping` | (none) | Health check, returns `{ok: true, version: "1.9.14"}` |
| `get_params` | track_idx, device_idx | All parameters with value, range, automation state |
| `get_hidden_params` | track_idx, device_idx | All parameters including hidden ones, with display string |
| `get_auto_state` | track_idx, device_idx | Only parameters that have automation (active or overridden) |
| `walk_rack` | track_idx, device_idx | Recursive device tree (racks, drum pads, 6 levels deep) |
| `get_chains_deep` | track_idx, device_idx | Detailed chain info with all device metadata |
| `get_track_cpu` | (none) | CPU performance impact per track |
| `get_selected` | (none) | Currently selected track, scene, device (blue hand) |
| `get_key` | (none) | Detected musical key from Krumhansl-Schmuckler algorithm |

### Phase 2: Sample Operations

| Command | Args | Description |
|---------|------|-------------|
| `get_clip_file_path` | track_idx, clip_idx | Audio file path on disk for a clip |
| `replace_simpler_sample` | track_idx, device_idx, file_path | Replace loaded sample in Simpler |
| `get_simpler_slices` | track_idx, device_idx | Slice points from Simpler's sample child |
| `crop_simpler` | track_idx, device_idx | Crop sample to active region |
| `reverse_simpler` | track_idx, device_idx | Reverse sample |
| `warp_simpler` | track_idx, device_idx, beats | Warp sample to N beats |

### Phase 2: Warp Markers

| Command | Args | Description |
|---------|------|-------------|
| `get_warp_markers` | track_idx, clip_idx | All warp markers (beat_time + sample_time) |
| `add_warp_marker` | track_idx, clip_idx, beat_time | Add warp marker |
| `move_warp_marker` | track_idx, clip_idx, old_beat, new_beat | Move warp marker |
| `remove_warp_marker` | track_idx, clip_idx, beat_time | Remove warp marker |

### Phase 2: Clip & Display

| Command | Args | Description |
|---------|------|-------------|
| `scrub_clip` | track_idx, clip_idx, beat_time | Preview audio at position |
| `stop_scrub` | track_idx, clip_idx | Stop preview |
| `get_display_values` | track_idx, device_idx | Human-readable parameter values ("440 Hz", "-6 dB") |

## SpectralCache

Thread-safe, time-expiring cache on the MCP server side (`mcp_server/m4l_bridge.py`).

- `update(key, value)` — stores with monotonic timestamp
- `get(key)` — returns `{value, age_ms}` or `None` if stale (>5 seconds)
- `is_connected` — `True` if any data received within the last 5 seconds
- `get_all()` — all non-stale cached data

When the M4L device is removed from the master track, data stops arriving. After 5 seconds, `is_connected` becomes `False` and all tools return a helpful error message.

## SpectralReceiver

Asyncio `DatagramProtocol` that parses incoming OSC packets.

- Parses OSC type tags: `f` (float), `i` (int), `s` (string)
- Handles response chunking: large JSON responses are split into 1400-byte base64 chunks by the M4L device and reassembled server-side
- Sets a `Future` for request/response correlation via `set_response_future()`

## M4LBridge

Sends commands to the M4L device and awaits responses.

- Builds minimal OSC packets (address + type tags + args)
- 5-second timeout per command
- Returns `{"error": "..."}` on timeout or if device is not connected

## Key LiveAPI Insights

These were discovered during development and are important for anyone working with Max JS `LiveAPI`:

### 1. `get()` Returns Arrays

Every `get()` call on a LiveAPI object in Max JS returns an array, even for scalar properties:
```javascript
cursor.get("name")   // Returns ["Track 1"], not "Track 1"
cursor.get("value")  // Returns [0.5], not 0.5
```
Always call `.toString()` or `parseFloat()` on the result.

### 2. `call()` vs `get()` for Functions vs Properties

`str_for_value` is a function, not a property. Using `get()` on it returns garbage. Must use `call()`:
```javascript
// WRONG:
cursor.get("str_for_value")

// CORRECT:
cursor.call("str_for_value", parseFloat(cursor.get("value")))
```

### 3. `warp_markers` is a Dict Property

Returns a JSON string (not LOM children). Must parse:
```javascript
var raw = cursor.get("warp_markers");
var parsed = JSON.parse(raw);
var markers = parsed["warp_markers"];
```
The `get()` may return the string directly or as a single-element array depending on context.

### 4. Simpler Slices Live on the Sample Child

```javascript
// WRONG:
cursor.goto("live_set tracks 0 devices 0 slices")

// CORRECT:
cursor.goto("live_set tracks 0 devices 0 sample")
var slices = cursor.get("slices")
```

### 5. `replace_sample` Requires Existing Sample

Loading a sample into an empty Simpler (one created via "Create empty Simpler") silently fails. The Simpler must already have a sample loaded. Workaround: load any sample via the browser first (which auto-creates a Simpler with content), then call `replace_sample`.

This is confirmed by Cycling '74 — there is no LiveAPI path to load a sample into a completely empty Simpler.

### 6. `openinpresentation` Does Not Persist

The `openinpresentation` attribute on `bpatcher` and top-level patchers does not get saved when you save from the Max editor. It reverts on reload. The only fix is binary patching the .amxd file.

## .amxd Binary Format

The Max for Live device format has this structure:

```
[24 bytes]  ampf header (magic + version + chunk sizes)
[N bytes]   ptch chunk (the patcher as compressed/encoded data)
[M bytes]   mx@c header + dependencies
[K bytes]   JSON patcher definition
[L bytes]   Frozen file dependencies (JS files, etc.)
```

### Binary Patching Technique

To change attributes that Max won't persist (like `openinpresentation`), replace byte sequences with same-length alternatives:

```python
# Example: change "openinpresentation" : 0  to  "openinpresentation" : 1
data = data.replace(
    b'"openinpresentation" : 0',
    b'"openinpresentation" : 1'
)
```

The replacement MUST be the exact same byte count. Changing the file size corrupts the chunk headers.

### Max JS Freeze/Cache Behavior

When you freeze a .amxd device, Max caches the JS file from its search path (`~/Documents/Max 8/...`), NOT from the source file's directory. This means:

1. Edit `livepilot_bridge.js` in your project directory
2. Copy it to `~/Documents/Max 8/Library/` (or wherever Max's search path points)
3. Re-freeze the .amxd device
4. The frozen device now contains the updated JS

If you skip step 2, the frozen device will contain the OLD JS code.

## OSC Address Dispatch

Max's `udpreceive` object passes the OSC address as the "messagename" to downstream objects. In Max JS, this arrives via the `anything()` handler as `messagename`.

**Critical discovery:** If the OSC address has a leading `/` (e.g., `/get_params`), Max passes `/get_params` as the messagename — including the slash. The JS `switch(cmd)` statement matching `"get_params"` will NOT match `"/get_params"`.

**Solution:** The MCP server sends OSC addresses WITHOUT leading `/`:
```python
# In M4LBridge._build_osc():
# Address is "get_params", not "/get_params"
```

The bridge JS also strips any leading `/` as a safety measure:
```javascript
function anything() {
    var cmd = messagename;
    if (cmd.charAt(0) === "/") cmd = cmd.substring(1);
    ...
}
```

## Known Limitations

1. **Max 3 LiveAPI cursors** — performance degrades with more; the bridge uses exactly 2 (`cursor_a`, `cursor_b`)
2. **Chunked parameter reads** — 4 parameters per batch with 50ms delay to avoid blocking Ableton's UI thread
3. **Single device on master** — per-track analyzers would add 2-4% CPU each
4. **5 Hz sampling** — sufficient for AI analysis but not for real-time visualization
5. **No GUI** — spectroscope~/meter~ objects consume 10-15% CPU each; the device is headless
6. **One response at a time** — the chunked response reassembly uses a simple key, so concurrent commands are not supported (commands are serialized by the async bridge)
7. **Empty Simpler limitation** — cannot load samples into empty Simplers via LiveAPI; must bootstrap via browser first

## File Locations

- `m4l_device/LivePilot_Analyzer.amxd` — compiled M4L device (binary)
- `m4l_device/livepilot_bridge.js` — bridge JS source (22 commands)
- `mcp_server/m4l_bridge.py` — SpectralCache, SpectralReceiver, M4LBridge
- `mcp_server/tools/analyzer.py` — 20 MCP tools for the analyzer domain
- `docs/specs/2026-03-18-m4l-bridge-spec.md` — original design spec
