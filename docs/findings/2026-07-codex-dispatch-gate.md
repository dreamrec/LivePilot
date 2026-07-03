# Codex Dispatch Gate Findings

Date: 2026-07-03
Spec: `docs/specs/2026-07-03-codex-dispatch-spec-a-gate-and-deeplink.md`
Status: Phase 0 complete; Phases 1-4 pending.

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

Pending Phase 1. This section will record observed JSON-RPC request/response payloads for `initialize`, `thread/start`, `turn/start`, `thread/read`, and `thread/resume`.

## Gate matrix

| ID | Verdict | Evidence excerpt |
|----|---------|------------------|
| A | pending-human | Phase 2 not run yet. |
| B | pending-human | Phase 2 not run yet. |
| C | pending-human | Phase 2 not run yet. |
| D | pending-human | Phase 2 not run yet. |
| E | pending-human | Phase 2 not run yet. |

## Verdict

Pending Phase 2. Spec B must not choose a branch until this section names Branch 1, Branch 2, or Branch 3.

## Marker threads

| Thread id | Created | Purpose |
|-----------|---------|---------|
| pending | pending | Phase 2 real-home gate thread has not been created yet. |

## Anomalies

- `codex remote-control` did not create `/Users/terencemahon/.codex/app-server-control/app-server-control.sock` while running on this machine, despite prior expectations that a default control socket might appear.
- The global Codex config emitted one startup warning during the remote-control probe: `unknown variant default, expected fast or flex` for a local config field. The command still started and stayed alive until terminated.
