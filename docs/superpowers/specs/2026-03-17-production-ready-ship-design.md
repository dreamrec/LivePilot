# LivePilot Production-Ready Ship — Design Spec

**Date:** 2026-03-17
**Goal:** Make LivePilot production-ready and publishable to npm, GitHub, and Claude Code plugin registry this week.
**Approach:** Fix & Ship — no new features, harden what exists, optimize for discovery by Ableton power users.

---

## Context

LivePilot v1.0.0 is functionally complete: 78 MCP tools across 9 domains, a Claude Code plugin with 1 skill + 4 commands + 1 agent, 6 reference files (~2700 lines of production knowledge), and 38 passing tests.

A full codebase audit found ~40 issues (6 CRITICAL, 5 HIGH, 2 MEDIUM). All 13 affected files have been fixed and tests pass, but fixes are uncommitted.

**Target audience:** Ableton Live 12 power users who already know the DAW and want workflow acceleration.
**Distribution:** npm (`npx livepilot`), public GitHub repo, Claude Code plugin registry.
**Timeline:** Ship this week.

---

## Section 1: Commit Audit Fixes + Production Scaffolding

### 1.1 Commit Audit Fixes

Commit the 13 modified files as a single commit. All 38 tests pass. Fixes include:

- **Remote Script (server.py):** Threading lock for `_client_connected` race condition
- **Remote Script (notes.py):** Undo guards on `modify_notes`/`transpose_notes`; `add_notes` passes `probability`/`velocity_deviation`/`release_velocity`; `get_notes`/`remove_notes` handle zero-length clips
- **Remote Script (devices.py):** `toggle_device` finds "Device On" by name; `find_and_load_device` resets iteration counter per category
- **Remote Script (arrangement.py):** `jump_to_time` rejects negative `beat_time`
- **Remote Script (diagnostics.py):** Cached `clip_slots` to avoid TOCTOU
- **MCP Server (connection.py):** Removed ping-before-every-command; `_send_raw` no longer mutates caller dict; recv buffer preserved across calls
- **CLI (bin/livepilot.js):** `--doctor`/`--status` return proper exit codes
- **Packaging:** `requirements.txt` pins `fastmcp>=3.0.0,<4.0.0`
- **Documentation:** Tool counts 76→78 in CHANGELOG, overview.md, SKILL.md
- **Plugin (plugin.json):** Added `skills`, `commands`, `agents` arrays
- **Tests:** `MockAbletonServer.stop()` handles `OSError`

### 1.2 Add LICENSE File

MIT license. README already claims MIT but no license file exists.

### 1.3 Add GitHub Actions CI

Minimal `.github/workflows/ci.yml`:
- Trigger: push to main, pull requests
- Single job: Python 3.12, install deps, run `pytest tests/ -v`
- No complex matrix, no npm build — just "do the tests pass?"

### 1.4 Harden package.json

Add fields for npm registry discovery:
- `repository` — GitHub URL (use actual repo URL once created, e.g. `https://github.com/pilotstudio/livepilot`)
- `homepage` — same as repository
- `bugs` — `{repository}/issues`
- Add `"claude"` and `"copilot"` to keywords
- Add `"type": "commonjs"` explicitly

Note: README line 5 has a placeholder `https://github.com/your-org/TDPilot` link — update it to the actual LivePilot repo URL at the same time.

### 1.5 Fix and verify .npmignore

Remove `CHANGELOG.md` from `.npmignore` — users should see the changelog in the published package.

Then run `npm pack --dry-run` to confirm published package:
- Excludes: tests/, docs/, .github/, CLAUDE.md, .pytest_cache/, .venv/, __pycache__/
- Includes: bin/, mcp_server/, remote_script/, installer/, plugin/, README.md, LICENSE, package.json, requirements.txt, CHANGELOG.md
- Target: <500KB

### 1.6 Update CLAUDE.md

- Add CHANGELOG.md to the tool count update checklist (was missing)
- Fix stale design spec path reference (currently points to `docs/specs/` but the spec lives in `docs/superpowers/specs/`)

---

## Section 2: README Rewrite for Discovery

Rewrite README.md to convert Ableton power users who find the package on npm or GitHub.

### Structure

1. **Title + tagline** — "LivePilot" + "AI copilot for Ableton Live 12"
2. **Value proposition** — 2-3 sentences targeted at power users. Direct, no hype. Emphasize: 78 tools, session control, no mouse/menus.
3. **Quick Start** — 3 commands: install, enable in Ableton, check status. Keep current structure.
4. **Claude Code Plugin** — how to add the plugin for skills/commands/agent.
5. **MCP Configuration** — JSON snippet for `.mcp.json`.
6. **Tool domains table** — 9-domain table with counts and key tools. Keep current.
7. **Slash commands table** — 4 commands. Keep current.
8. **"What it's good at" section** — Session overview & navigation, repetitive build tasks, MIDI refinement, session hygiene. Pulled from positioning doc. Honest pitch.
9. **Architecture** — ASCII diagram. Move connection model note here as a one-liner.
10. **Compatibility matrix** — Keep current table.
11. **CLI reference** — Keep current.
12. **Requirements** — Keep current.
13. **Development** — Fix to use venv: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
14. **License** — MIT

### Tone

Direct, technical, confident. No marketing language. Power users trust specificity over promises. Show the tool count, the domain coverage, the architecture. Let the substance speak.

### What changes

- Add value prop paragraph at top
- Add "What it's good at" section (new)
- Fix Development section (venv instead of system pip)
- Tighten Connection Model into a note under Architecture
- No content removed, just reorganized for scanning

---

## Section 3: npm + Plugin Registry Readiness

### 3.1 npm Publish Readiness

- `package.json` fields complete (repository, homepage, bugs, keywords)
- `.npmignore` verified via `npm pack --dry-run`
- `bin/livepilot.js` tested with `node bin/livepilot.js --help`
- Package ready for `npm publish` (user runs manually)

### 3.2 Plugin Registry Readiness

- `plugin/plugin.json` has name, version, description, author, skills, commands, agents
- `plugin/.mcp.json` configures the MCP server
- `plugin/skills/livepilot-core/SKILL.md` has frontmatter (name, description)
- `plugin/agents/livepilot-producer/AGENT.md` has frontmatter (name, description, when_to_use, model, tools)
- `plugin/commands/*.md` all have frontmatter (name, description)
- File structure matches Claude Code plugin spec

### 3.3 What We Don't Do

- We don't run `npm publish` — that's the user's decision
- We don't submit to any registry — ready but not pushed
- We don't add new features — ship what exists
- We don't create demo GIFs — can be added in v1.0.1
- We don't create a GitHub release or `git tag v1.0.0` — user does this after reviewing final state

---

## Success Criteria

1. All 38+ tests pass
2. `npm pack --dry-run` produces a clean package <500KB
3. `node bin/livepilot.js --help` works
4. `node bin/livepilot.js --doctor` exits with correct codes
5. LICENSE file exists
6. GitHub Actions CI runs on push
7. README reads as a discovery page, not internal docs
8. All tool counts consistent (78) across every file
9. `plugin/plugin.json` has complete registration arrays
10. Working tree is clean — everything committed
