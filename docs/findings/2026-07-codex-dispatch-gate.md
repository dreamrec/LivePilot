# Codex Dispatch Gate Findings

Date: 2026-07-03
Spec: `docs/specs/2026-07-03-codex-dispatch-spec-a-gate-and-deeplink.md`
Status: v1.5 dispatch shipped; manual interop gate checks pending.

Pending manual checks:

- H1: confirm Codex.app opened thread `019f28e9-3b8a-7b62-b8af-7abbee5583d5`.
- H2: send exactly `GATE-HUMAN-TURN` in that app thread and confirm it completes.
- H3: from the cockpit, save a small brief and click `Open in Codex`; confirm the app opens with the pickup prompt prefilled.

## Surface

### Versions

- Codex CLI: `codex-cli 0.130.0` at `/Users/terencemahon/.npm-global/bin/codex`.
- Codex.app: `/Applications/Codex.app`, `CFBundleVersion=4674`.
- URL scheme registration: `/Applications/Codex.app/Contents/Info.plist` declares `CFBundleURLSchemes = ["codex"]`.

### App-server transport and invocation

Observed from `codex app-server --help` and the current Codex manual:

- Default app-server transport: `stdio://`.
- Supported `--listen` values: `stdio://`, `unix://`, `unix://PATH`, `ws://IP:PORT`, `off`.
- `codex app-server --listen stdio://` and `codex app-server --stdio` are the JSONL-over-stdio path.
- `codex app-server --listen ws://127.0.0.1:<port>` exposes a local WebSocket transport plus `/readyz` and `/healthz`.
- `codex app-server --listen unix://` uses the default Unix-socket app-server endpoint; `unix://PATH` uses a custom socket path.
- Clients must send `initialize`, then `initialized`, before calling thread/turn methods.
- Experimental methods or fields require `initialize.params.capabilities.experimentalApi = true`.

Observed from `codex remote-control --help` and a 3-second local run:

- `codex remote-control` is described as starting a headless app-server with remote control enabled.
- It has no documented socket/listen flags.
- The default control socket `/Users/terencemahon/.codex/app-server-control/app-server-control.sock` was absent before the run and still absent while `remote-control` was running.
- On termination, the process logged remote-control websocket reader/writer shutdown warnings. This suggests remote-control does not create the previously expected control socket in this environment.

### Data home and isolation mechanism

- Real Codex home: `/Users/terencemahon/.codex`.
- Observed real-home layout includes `auth.json` implicitly required for authenticated CLI/app-server use, plus `sessions/`, `archived_sessions/`, `plugins/`, `skills/`, `memories/`, `log/`, `browser/`, `automations/`, and cache directories.
- Official environment variable: `CODEX_HOME`. The current Codex manual says it applies to CLI, IDE extension, app-server, and installers, defaults to `~/.codex`, and controls config, auth, logs, sessions, skills, and package metadata. The directory must already exist.
- `CODEX_SQLITE_HOME` defaults to `CODEX_HOME` for CLI/app-server SQLite state unless overridden.
- Phase 1 will use `CODEX_HOME=/Users/terencemahon/.livepilot/tmp/codex-gate-home` and copy only `auth.json` there for the isolated mechanics rehearsal.
- The Mac app gate in Phase 2 must use the real home because the app reads local app threads from the real Codex state.

### Deep-link grammar

Observed from the current Codex manual and the installed app bundle scheme registration:

- Existing local thread: `codex://threads/<thread-id>`, where `<thread-id>` is the thread/session UUID.
- New local thread: `codex://threads/new`.
- New local thread with query parameters: `codex://threads/new?prompt=<encoded>&path=<encoded>` or `codex://new?prompt=<encoded>&path=<encoded>`.
- `prompt=` sets the initial composer text.
- `path=` opens the new thread in an absolute local workspace path.
- `originUrl=` can match a workspace by Git remote URL; if `path` is also present, `path` wins.
- Query string values must be URL-encoded.
- There is no documented deep-link form that sends a message into an existing thread.

## Mechanics

Harness: `scripts/codex_gate/harness.mjs`
Isolated home: `/Users/terencemahon/.livepilot/tmp/codex-gate-home`
Successful isolated thread: `019f28e4-bdab-7f20-919e-10449da66d45`
Successful isolated model turns: 2 (`GATE-OK`, `GATE-OK-2`)

### Isolation proof

- The app-server `initialize` response reported `codexHome=/Users/terencemahon/.livepilot/tmp/codex-gate-home`.
- The successful thread rollout path was `/Users/terencemahon/.livepilot/tmp/codex-gate-home/sessions/2026/07/03/rollout-2026-07-03T12-51-47-019f28e4-bdab-7f20-919e-10449da66d45.jsonl`.
- `find /Users/terencemahon/.codex/sessions -name '*019f28e4-bdab-7f20-919e-10449da66d45*'` returned no matches; the matching rollout exists only under the isolated home.
- The literal sentinel check against all of `/Users/terencemahon/.codex` was noisy because this active Codex thread and local caches wrote shell snapshots, logs, and cache files during the same period. Treat the targeted thread-id and `initialize.codexHome` evidence as the meaningful isolation check for this interactive run.
- Phase 4 cleanup deleted `/Users/terencemahon/.livepilot/tmp/codex-gate-home`, including the copied `auth.json`.

### Observed request/response contract

Initialize:

```json
{"method":"initialize","id":1,"params":{"clientInfo":{"name":"livepilot_codex_gate","title":"LivePilot Codex Gate Harness","version":"0.1.0"},"capabilities":{"experimentalApi":true}}}
{"id":1,"result":{"userAgent":"Codex Desktop/0.130.0 (Mac OS 15.7.3; arm64) dumb (livepilot_codex_gate; 0.1.0)","codexHome":"/Users/terencemahon/.livepilot/tmp/codex-gate-home","platformFamily":"unix","platformOs":"macos"}}
{"method":"initialized","params":{}}
```

Start thread:

```json
{"method":"thread/start","id":2,"params":{"model":"gpt-5.5","cwd":"/Users/terencemahon/Documents/audio-assistant/external-research/github/dreamrec/LivePilot"}}
{"id":2,"result":{"thread":{"id":"019f28e4-bdab-7f20-919e-10449da66d45","sessionId":"019f28e4-bdab-7f20-919e-10449da66d45","ephemeral":false,"path":"/Users/terencemahon/.livepilot/tmp/codex-gate-home/sessions/2026/07/03/rollout-2026-07-03T12-51-47-019f28e4-bdab-7f20-919e-10449da66d45.jsonl","cwd":"/Users/terencemahon/Documents/audio-assistant/external-research/github/dreamrec/LivePilot","cliVersion":"0.130.0","source":"vscode","turns":[]},"model":"gpt-5.5","modelProvider":"openai","cwd":"/Users/terencemahon/Documents/audio-assistant/external-research/github/dreamrec/LivePilot"}}
```

Start first turn on the same connection:

```json
{"method":"turn/start","id":3,"params":{"threadId":"019f28e4-bdab-7f20-919e-10449da66d45","input":[{"type":"text","text":"Reply with exactly: GATE-OK"}],"cwd":"/Users/terencemahon/Documents/audio-assistant/external-research/github/dreamrec/LivePilot"}}
{"id":3,"result":{"turn":{"id":"019f28e4-bdc6-7742-841c-c84347102645","items":[],"itemsView":"notLoaded","status":"inProgress","error":null}}}
```

Completion notifications included `item/agentMessage/delta` chunks spelling `GATE-OK`, followed by:

```json
{"method":"turn/completed","params":{"threadId":"019f28e4-bdab-7f20-919e-10449da66d45","turn":{"id":"019f28e4-bdc6-7742-841c-c84347102645","status":"completed","error":null}}}
```

Read thread:

```json
{"method":"thread/read","id":2,"params":{"threadId":"019f28e4-bdab-7f20-919e-10449da66d45","includeTurns":true}}
{"id":2,"result":{"thread":{"id":"019f28e4-bdab-7f20-919e-10449da66d45","preview":"Reply with exactly: GATE-OK","turns":[{"id":"019f28e4-bdc6-7742-841c-c84347102645","items":[{"type":"userMessage","content":[{"type":"text","text":"Reply with exactly: GATE-OK"}]},{"type":"agentMessage","text":"GATE-OK","phase":"final_answer"}],"itemsView":"full","status":"completed","error":null}]}}}
```

`includeTurns:true` is required. Without it, `thread/read` succeeds but returns `turns: []`.

Resume thread:

```json
{"method":"thread/resume","id":2,"params":{"threadId":"019f28e4-bdab-7f20-919e-10449da66d45","model":"gpt-5.5","cwd":"/Users/terencemahon/Documents/audio-assistant/external-research/github/dreamrec/LivePilot"}}
{"id":2,"result":{"thread":{"id":"019f28e4-bdab-7f20-919e-10449da66d45","turns":[{"id":"019f28e4-bdc6-7742-841c-c84347102645","status":"completed","itemsView":"full"}]},"model":"gpt-5.5","modelProvider":"openai"}}
```

Second turn from a fresh app-server connection:

```json
{"method":"thread/resume","id":2,"params":{"threadId":"019f28e4-bdab-7f20-919e-10449da66d45","model":"gpt-5.5","cwd":"/Users/terencemahon/Documents/audio-assistant/external-research/github/dreamrec/LivePilot"}}
{"method":"turn/start","id":3,"params":{"threadId":"019f28e4-bdab-7f20-919e-10449da66d45","input":[{"type":"text","text":"Reply with exactly: GATE-OK-2"}],"cwd":"/Users/terencemahon/Documents/audio-assistant/external-research/github/dreamrec/LivePilot","model":"gpt-5.5"}}
{"id":3,"result":{"turn":{"id":"019f28e6-87fc-7b80-af76-e4e2b67bb3c4","status":"inProgress","error":null}}}
```

Completion notifications included `GATE-OK-2`. A direct `turn/start` from a fresh connection without first calling `thread/resume` failed with `thread not found`.

## Gate matrix

| ID | Verdict | Evidence excerpt |
|----|---------|------------------|
| A | pending-human | Real-home gate thread `019f28e9-3b8a-7b62-b8af-7abbee5583d5` was created and `open codex://threads/019f28e9-3b8a-7b62-b8af-7abbee5583d5` was fired. Producer confirmation pending. |
| B | pending-human | Producer has not yet sent `GATE-HUMAN-TURN` in the app. |
| C | pending-human | Backend polling waits on B. |
| D | pending-human | Backend push test waits on C. |
| E | pending-human | Resume/read/write-after-app-touch waits on B/C. |

## Verdict

Pending Phase 2. Spec B must not choose a branch until this section names Branch 1, Branch 2, or Branch 3.

## Marker threads

| Thread id | Created | Purpose |
|-----------|---------|---------|
| 019f28e4-bdab-7f20-919e-10449da66d45 | 2026-07-03 | Isolated-home mechanics rehearsal; isolated home deleted in Phase 4 cleanup. |
| 019f28e8-daa4-7501-b4d4-6b1ecc715c4c | 2026-07-03 | Real-home Phase 2 attempt; first turn failed because upstream rejected `service_tier=flex`. Disposable test thread, safe to delete. |
| 019f28e9-3b8a-7b62-b8af-7abbee5583d5 | 2026-07-03 | Real-home Phase 2 gate thread; first turn returned `GATE-OK`. Disposable test thread, safe to delete after gate. |

## Anomalies

- `codex remote-control` did not create `/Users/terencemahon/.codex/app-server-control/app-server-control.sock` while running on this machine, despite prior expectations that a default control socket might appear.
- The global Codex config emitted one startup warning during the remote-control probe: `unknown variant default, expected fast or flex` for a local config field. The command still started and stayed alive until terminated.
- A bare `thread/start` with no first turn was not durable enough for a later fresh app-server process to `turn/start`; the later call returned `thread not found`.
- `turn/start` on a persisted thread from a fresh app-server connection also returned `thread not found` until the harness first called `thread/resume`.
- The isolated home's fallback model was `gpt-5.3-codex`, which this ChatGPT account rejected. Explicit `model="gpt-5"` was also rejected. Explicit `model="gpt-5.5"` worked.
- Real-home `thread/start` failed with the user's current config because `service_tier = "default"` is invalid for app-server 0.130.0. The harness now supports `--config`; `--config 'service_tier="fast"'` allowed the real-home gate to run. `service_tier="flex"` parsed but the upstream API rejected it.
