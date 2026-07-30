# Pending .amxd Re-Freeze Batch — LivePilot_Analyzer

**Status: PREPARED, NOT FROZEN.** All JS source changes below are committed in
`m4l_device/livepilot_bridge.js`, but the frozen JS inside
`LivePilot_Analyzer.amxd` is authoritative at runtime — nothing here takes
effect until the device is re-frozen in Max (a USER action). This note exists
so that ONE re-freeze ships the whole batch.

Freeze procedure: `docs/MAX_FREEZE_WORKFLOW.md`. Remember the two classic
traps: Max freezes JS from its search-path cache (sync the copy in
`~/Documents/Max 9/` first), and every install target is a separate snapshot —
verify the frozen bytes via OSC ping + MD5 across all three locations before
declaring done.

---

## Batch contents

### 1. OSC 9881 shared-secret token auth (security fix, 2026-07-30 review)

**Problem:** `udpreceive 9881` binds on ALL interfaces (it takes no
bind-interface argument; verified live — `lsof -nP -iUDP:9881` shows
`Live ... UDP *:9881`). A LAN-adjacent host can blindly fire any of the 32
bridge commands (crop/reverse/re-sample a Simpler, remap plugin params,
trigger `capture_audio` WAV writes). TCP 9878 and UDP 9880 are loopback-only;
this was the one exposed channel.

**Scheme:**
- `mcp_server/m4l_bridge.py` generates a random token per server startup
  (`secrets.token_hex(16)`) and the server lifespan publishes it to
  `~/Documents/LivePilot/bridge_token` (mode 0600). The JS derives the same
  path from `max.appsupportpath` (the `_get_captures_dir()` home-derivation
  pattern) — see `_auth_token_path()` / `default_bridge_token_path()`.
- Every OSC command carries `__livepilot_token:<hex>` as its **first**
  argument. The JS strips + validates it in `anything()` (`_auth_check`) and
  silently drops non-matching commands with a throttled `post()` log. The
  token only ever travels over loopback UDP + the local filesystem, so a LAN
  host can neither sniff nor read it.
- `ping` / `get_version` stay exempt — they are the version handshake.
- Token file absent/unreadable → legacy compat: untokened commands accepted
  (pre-token servers never write the file).
- On token mismatch the JS re-reads the file (throttled, 500ms floor) before
  rejecting, so a server restart that rotates the token self-heals.

**Python compat flag (version gate):** the token is attached only once the
device's `ping` response reports a build ≥ `TOKEN_AUTH_MIN_BRIDGE_VERSION`
(currently `(1, 28, 0)` in `mcp_server/m4l_bridge.py`). A pre-token frozen
device would misparse the token as its first positional arg, so old devices
never receive it. A non-ping command on a fresh bridge runs a one-time ping
handshake first (`_ensure_bridge_version_known`). Manual kill switch:
`LIVEPILOT_BRIDGE_TOKEN_DISABLE=1` restores the pre-1.28 wire format exactly.

### 2. `/capture_error` reply channel (busy-guard fix)

`cmd_capture_audio`'s busy branch (and its invalid-filename branch) used to
reply via `send_response` → `/response`, but `send_capture` on the Python
side only resolves via the capture future — the caller ate the full 35s
timeout, and the stray un-id'd `/response` could even resolve an UNRELATED
pending command's future. New JS replies via `send_capture_error()` →
`/capture_error`; `SpectralReceiver._handle_message` routes that address to
the capture future. Old device + new Python: `/capture_error` never arrives
(no regression). New device + old Python: address ignored → timeout (same as
before, no regression).

### 3. `captured_request_id` for `cmd_get_display_values` + `cmd_get_plugin_params`

The batched readers reschedule via `Task.schedule(20)`; an interleaved command
in that gap clobbers the module-level `current_response_request_id`, so the
final `send_response` went out with the wrong (or no) id and was dropped by
the Python correlator. Both functions now capture the id in a closure — the
same pattern `cmd_get_params` / `cmd_get_hidden_params` already use.

**Note:** the `spike/12.4.5` branch (64d165a) carries this same fix for these
same two functions. Merging that branch later will be a semantic no-op here —
if it conflicts textually, keep either side, they are equivalent.

---

## Pre-freeze checklist (do IN ORDER)

1. **Version bump first.** The freeze must happen at the release version that
   ships this batch (≥ 1.28.0): `var VERSION` in `livepilot_bridge.js` is the
   ping version the Python gate reads. Freezing while it still says `1.27.3`
   leaves token auth permanently off. If the batch slips to a later release,
   also bump `TOKEN_AUTH_MIN_BRIDGE_VERSION` in `mcp_server/m4l_bridge.py` to
   the first frozen version.
2. Sync `livepilot_bridge.js` into the Max search-path cache
   (`~/Documents/Max 9/`) so the freeze picks up the NEW source, not a stale
   cached copy (dep-cache trap).
3. Re-freeze `LivePilot_Analyzer.amxd` in Max; export; copy to all install
   targets; MD5-verify ×3 locations.
4. Update at release time: `docs/M4L_BRIDGE.md` (ping version string is in
   `scripts/sync_metadata.py::VERSION_FILES`, plus document the token scheme),
   `CHANGELOG.md` top entry.

## Freeze-time verification (user, in Ableton)

- `ping` returns the new version; server log/`get_capability_state` shows the
  bridge alive.
- **Max File API check:** the JS reads the token with
  `new File("/Users/<name>/Documents/LivePilot/bridge_token", "read")` —
  confirm a POSIX absolute path opens from a frozen-device context (Max 9
  accepts POSIX paths, but this is the one assumption not testable outside
  Max). If `f.isopen` is false with the file present, the fallback is
  compat-accept mode — commands still work but UNAUTHENTICATED; fix before
  shipping.
- Tokened round-trip: `get_device_parameters` (or any bridge tool) works with
  the running MCP server.
- Busy guard: start a long `capture_audio`, immediately fire a second one —
  the second must return the busy error instantly (not a 35s hang).
- Token rotation: restart the MCP server mid-session; the next bridge command
  must still succeed (JS re-reads the rotated token file on mismatch).
- Negative test (the actual vulnerability): from another machine on the LAN,
  fire a blind OSC command at UDP 9881 — the Max console should show one
  throttled "dropped unauthenticated command" line and nothing must execute.

## Known limitations / follow-up batch candidates

- **MIDITool devices are still untokened.** `miditool_bridge.js`
  (`LivePilot_MIDITool_Generate/Transform.amxd`) also listens on UDP 9881 and
  accepts `miditool/config` + `miditool/response` (the latter injects notes).
  The Python side deliberately does NOT token `send_miditool_config` /
  `send_miditool_response` — those devices have no ping/version handshake, so
  tokening would break every existing frozen MIDITool device. Follow-up:
  add the same `_auth_check` to `miditool_bridge.js`, add a version
  handshake, then token those sends.
- **Elektron bridge:** `livepilot_elektron_bridge.js` listens on UDP 9883
  (raw sysex forwarded to hardware MIDI) — same all-interfaces exposure
  class. Assess in the follow-up batch.
- Rejected commands are dropped with no reply by design; on the server side a
  genuine token mismatch surfaces as an ordinary bridge timeout.

## Test coverage

`tests/test_bridge_token_auth.py` — compat flag both ways (legacy device
never sees the token; 1.28+ device gets it as first arg on `send_command`
AND `send_capture`), ping handshake ordering, token-file publication
(0600, lifespan-only, non-fatal failure), env kill switch,
`/capture_error` routing, and frozen-JS source contracts pinning items
1–3 so the batch can't silently lose a piece before the freeze.
