# LivePilot Fix List

Date: March 17, 2026

This is the practical fix list for turning LivePilot from a strong prototype into a reliable release. It is ordered by impact, not by engineering neatness.

## Release blockers

### 1. Make `npx livepilot` work on a clean machine

Current state:
- The CLI launches `python -m mcp_server`.
- The MCP server imports `fastmcp`.
- `fastmcp` is only declared in `requirements.txt`.
- A clean Python environment fails at startup with `ModuleNotFoundError: No module named 'fastmcp'`.

Why this matters:
- The headline install path does not actually work unless the user has already prepared Python dependencies manually.
- This creates the worst kind of trust failure: the first command looks supported but breaks immediately.

Fix:
- Pick one official path and support it end to end.
- Best option: create a local venv on first run and install Python deps automatically.
- Minimum option: fail with a clean guided error that explains exactly how to install deps.

Definition of done:
- `npm pack`
- install package into a clean temp environment
- run `livepilot --version`
- run `livepilot`
- startup either succeeds or prints a polished dependency bootstrap message

### 2. Add a proper `doctor` command

Current state:
- The project can tell whether the TCP port responds.
- It cannot explain the full install state in one place.

Why this matters:
- Most user pain will be setup pain, not music logic.
- Right now debugging setup requires too much guessing.

Fix:
- Add `livepilot --doctor`
- Check:
  - Python version
  - `fastmcp` import
  - package root visibility
  - Remote Script install path
  - Ableton TCP connection
  - environment overrides like `LIVE_MCP_HOST` and `LIVE_MCP_PORT`

Definition of done:
- One command explains exactly what is healthy and what is missing

### 3. Decide whether single-client access is a feature or a bug

Current state:
- The Remote Script accepts a client and handles it inline before accepting another one.
- A long-lived MCP connection can monopolize the port.

Why this matters:
- This will surprise users the moment they run two AI clients, a second assistant, or a debugging tool.

Fix:
- If single-client is intentional:
  - document it clearly
  - reject additional clients with an explicit message
- If multi-client is desired:
  - move client handling to separate threads
  - keep the Ableton main-thread queue shared and serialized

Definition of done:
- Concurrent access behavior is deliberate and documented

## High-value hardening

### 4. Stop shipping Python cache files in the npm package

Current state:
- `npm pack --dry-run` includes `__pycache__` and `.pyc` files.

Why this matters:
- It is not fatal, but it looks unfinished.
- It increases package noise and weakens release quality.

Fix:
- Add `.npmignore` or tighten the published file list
- Exclude:
  - `__pycache__/`
  - `*.pyc`
  - `.pytest_cache/`
  - any local-only artifacts

### 5. Add packaging and installation smoke tests in CI

Current state:
- Tests prove imports and tool registration.
- They do not prove the shipped product works.

Fix:
- Add CI checks for:
  - `npm pack --dry-run`
  - clean install test
  - clean Python env startup
  - CLI `--version`, `--status`, and `--doctor`

### 6. Improve user-facing error language

Current state:
- Core protocol errors are cleaner than before, but some failures still feel developer-oriented.

Fix:
- Normalize errors into:
  - what failed
  - likely reason
  - next action

Best targets:
- missing Python dependency
- Remote Script not installed
- Ableton not running
- TCP connection refused
- unsupported browser/device load path

### 7. Add a compatibility matrix

Current state:
- The project says "Ableton Live 12 minimum", but not every feature has the same confidence across Live 12 point releases or editions.

Fix:
- Document:
  - what is expected to work on all Live 12 versions
  - what depends on newer Live 12 updates
  - what likely needs Suite or specific Browser content

## Product safety fixes

### 8. Add safer behavior around destructive commands

Current state:
- Delete and overwrite actions are powerful but not especially guarded.

Fix:
- Prefer read-first summaries before destructive sequences
- Encourage explicit confirmation language in higher-level agent prompts
- Make undo part of the documented recovery path

### 9. Add command logging for traceability

Fix:
- Keep a rolling in-memory log of the last commands and responses
- Expose a read-only tool or debug command for recent actions

Why this matters:
- Users need to know what the AI actually changed
- This is especially important during creative iteration

### 10. Add end-to-end domain tests, not just registration tests

Current state:
- The test suite mainly proves that 76 tools exist and that a mocked connection envelope works.

Fix:
- Add one contract test per domain that verifies:
  - parameter names
  - required fields
  - error handling
  - result shape

## Nice-to-have after the release path is stable

### 11. Session snapshots for recovery

Idea:
- Before major batch changes, capture a lightweight session summary
- Use it for audit, undo guidance, and human review

### 12. Performance diagnostics

Idea:
- Add tools for:
  - oversized track counts
  - suspicious routing
  - muted/soloed leftovers
  - empty clips
  - possible organization issues

This is one of the best future usability upgrades because it improves real sessions without trying to be magical.

## Recommended implementation order

1. Clean-machine startup
2. `--doctor`
3. Packaging smoke tests
4. Single-client decision
5. Better user-facing errors
6. Compatibility matrix
7. Destructive-action safety
8. Deeper tests

## Bottom line

LivePilot is already structured like a serious tool. The main gap is not the internal domain map anymore. The main gap is release hardening: installation, diagnostics, packaging confidence, and predictable runtime behavior.
