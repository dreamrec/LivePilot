# Capability Modes Reference

The evaluation engine adapts its behavior based on what measurement capabilities are available. Call `get_capability_state` to determine the current mode.

## Mode: normal

Full measurement capabilities available.

**Requirements:**
- Ableton Live connected via TCP port 9878
- M4L analyzer bridge running on master track
- UDP 9880 (M4L -> Server) and OSC 9881 (Server -> M4L) active
- SpectralCache receiving fresh data (age < 5 seconds)

**Available measurements:**
- `get_master_spectrum` — 8-band spectral analysis, real-time
- `get_master_rms` — RMS and peak levels
- `get_detected_key` — key detection from audio
- `get_mel_spectrum` — mel-scaled spectral representation
- `get_chroma` — chromagram for harmonic analysis
- `get_onsets` — transient detection
- `get_momentary_loudness` — short-term loudness
- `get_spectral_shape` — centroid, spread, skewness, kurtosis
- All device parameter reads and session state tools

**Evaluation quality:** Highest. Critics use measured spectral evidence. Before/after comparisons are numerically precise.

## Mode: measured_degraded

Analyzer data is present but stale or intermittent.

**Indicators:**
- SpectralCache age > 5 seconds
- Intermittent UDP packet loss from M4L device
- M4L bridge loaded but analyzer section not receiving audio

**Available measurements:**
- All session state tools (tracks, clips, devices, parameters)
- Cached spectral data (may not reflect current audio)
- Device parameter reads (always fresh)

**Evaluation quality:** Moderate. Spectral comparisons may be inaccurate if data is stale. Always check cache age before trusting spectrum values.

**User notification:** "Analyzer data may be stale. For accurate spectral evaluation, play audio through the master bus and wait 2-3 seconds for the cache to refresh."

## Mode: judgment_only

No M4L analyzer connected. The evaluation engine operates on structural and parametric data only.

**Indicators:**
- M4L bridge not loaded on master track
- UDP 9880 not receiving data
- `get_master_spectrum` returns error or empty data

**Available measurements:**
- All session state tools
- Device parameter reads
- Track structure (names, types, device chains)
- Note and clip data
- Role-based heuristics (bass tracks should have low content, etc.)

**Evaluation quality:** Limited. No spectral evidence for masking, balance, or loudness judgments. Critics infer from:
- Track names and roles (a track named "Bass" should have low-frequency content)
- Device chains (a track with EQ Eight + Compressor is likely processed)
- Parameter values (filter cutoff position, compressor threshold)
- Volume/pan/send positions

**User notification:** "M4L analyzer is not connected. Evaluation is based on track structure and parameter analysis only. For spectral verification, load the LivePilot Bridge device on the master track."

## Mode: read_only

Session disconnected or in an error state.

**Indicators:**
- TCP connection to port 9878 failed or timed out
- Remote Script not responding
- Ableton Live not running or crashed

**Available measurements:**
- Cached session data from last successful connection
- Memory system (technique recall, preferences)
- No live reads from the session

**Evaluation quality:** None for current state. Can only reference cached data and memory.

**User notification:** "Session disconnected. Cannot evaluate current state. Reconnect to Ableton Live to resume."

## Capability Fallback Chain

When a measurement fails, fall back gracefully:

1. Try the primary measurement tool
2. If it fails, check if degraded data is available in cache
3. If no cache, use parametric/structural heuristics
4. If no session connection, report inability and suggest reconnection

Never silently skip evaluation. Always inform the user which capability mode is active and how it affects the quality of judgment.

## Checking Capability State

Call `get_capability_state` at the start of any evaluation session. The response includes:

```json
{
  "mode": "normal",
  "analyzer_connected": true,
  "bridge_version": "1.9.18",
  "spectral_cache_age_ms": 1200,
  "flucoma_available": false,
  "session_connected": true
}
```

- `mode`: one of "normal", "measured_degraded", "judgment_only", "read_only"
- `analyzer_connected`: whether M4L bridge is active
- `spectral_cache_age_ms`: milliseconds since last spectral update
- `flucoma_available`: whether FluCoMa analysis tools are installed
- `session_connected`: whether TCP connection to Ableton is active
