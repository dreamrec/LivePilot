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
- `get_master_spectrum` — 9-band spectral analysis (sub_low → air), real-time
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

Call `get_capability_state` at the start of any evaluation session. The response is a nested `domains` dict keyed by capability name — NOT the flat shape older docs described.

```json
{
  "capability_state": {
    "generated_at_ms": 1776929160866,
    "overall_mode": "normal",
    "domains": {
      "session_access": {"name": "session_access", "available": true,  "confidence": 1.0, "mode": "healthy",     "reasons": []},
      "analyzer":       {"name": "analyzer",       "available": true,  "confidence": 0.9, "mode": "available",   "reasons": []},
      "memory":         {"name": "memory",         "available": true,  "confidence": 1.0, "mode": "available",   "reasons": []},
      "web":            {"name": "web",            "available": true,  "confidence": 0.7, "mode": "available",   "reasons": []},
      "research":       {"name": "research",       "available": true,  "confidence": 0.9, "mode": "available",   "reasons": []},
      "flucoma":        {"name": "flucoma",        "available": false, "confidence": 0.0, "mode": "unavailable", "reasons": ["flucoma_not_installed"]}
    }
  }
}
```

### Top-level fields

- `capability_state.generated_at_ms`: Unix-ms timestamp of the probe.
- `capability_state.overall_mode`: one of `"normal"`, `"measured_degraded"`, `"judgment_only"`, `"read_only"` — the global evaluation-quality tier computed from the per-domain signals.
- `capability_state.domains`: dict keyed by domain name; each value is a capability-domain record.

### Per-domain fields

Every entry in `domains` has the same shape:

- `name`: the domain key (`"session_access"`, `"analyzer"`, `"memory"`, `"web"`, `"research"`, `"flucoma"`).
- `available`: boolean — is this capability ready to use right now?
- `confidence`: 0.0–1.0 — how much to trust the `available` flag (e.g. stale analyzer data lowers confidence).
- `mode`: short human label specific to the domain (`"healthy"`, `"available"`, `"measured"`, `"stale"`, `"targeted_only"`, `"full"`, `"unavailable"`).
- `reasons`: list of short machine-readable tokens explaining why the domain is in its current state (`"analyzer_offline"`, `"web_unavailable"`, `"flucoma_not_installed"`, …). Empty when healthy.
- `freshness_ms`: optional — milliseconds since the domain last received fresh data (currently only the analyzer domain populates this).

### Domain definitions

- **session_access** — live TCP connectivity to the Ableton Remote Script on port 9878. `available=true` means a `get_session_info` round-trip succeeded.
- **analyzer** — the M4L bridge + spectral cache. `available=true` requires the bridge to be connected AND the spectral cache to have recently received data.
- **memory** — the local technique-store / taste memory. `available=true` means the persistent stores can be read and written.
- **web** — server-side outbound HTTP capability. True when the MCP host can reach an arbitrary public URL (probed by a 500 ms HEAD request to `https://api.github.com`). Does NOT imply curated research corpora are installed — see the `research` domain for that.
- **research** — composite over `session_access`, `memory`, and `web`. `mode="full"` when all three are available; `"targeted_only"` when at least one source is up; `"unavailable"` when nothing is reachable.
- **flucoma** — whether the optional `flucoma` Python package is importable (probed via `importlib.util.find_spec`). FluCoMa-backed tools (`check_flucoma`, `extract_timbre_fingerprint`, etc.) degrade gracefully when this domain is unavailable.

## Collaborative Mode (Live 12.4+)

Live 12.4 introduces a new capability tier that unlocks native LOM access for sample replacement. This tier is separate from the evaluation modes above — it affects routing behavior in the MCP server, not spectral measurement.

**Version gate:** Live 12.4.0+

**Detection flag:** `LiveVersionCapabilities.has_replace_sample_native == True`
(exposed on `LiveVersionCapabilities.capability_tier == "collaborative"`)

**What changes at this tier:**
- `SimplerDevice.replace_sample(path)` is available as a native LOM call.
  The MCP tools `replace_simpler_sample` and `load_sample_to_simpler`
  route to this native path automatically.
- The native path handles empty Simplers — the long-standing limitation
  (documented in `feedback_load_browser_item_is_source_of_truth.md`)
  that required `load_browser_item` as a workaround no longer applies
  on Live 12.4+.

**Backward compatibility:**
- Live 12.0–12.3.x: `has_replace_sample_native == False`. All sample
  replacement still routes through the M4L bridge. Zero behavior change.
- Live 12.4+: native path preferred; M4L bridge used only on fallback.

**Tool signatures:** unchanged. Callers do not need to detect the tier —
routing is transparent.

**Follow-up plans (not yet shipped):**
- Link Audio (tempo-sync sharing between Live sets) — tracked as a
  future Collaborative-tier feature.
- Stem Separation v2 — tracked as a future Collaborative-tier feature.
Neither is available in the 1.23.4 release — still pending.
