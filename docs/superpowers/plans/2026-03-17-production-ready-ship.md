# LivePilot Production-Ready Ship — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LivePilot v1.0.0 production-ready and publishable to npm, GitHub, and Claude Code plugin registry.

**Architecture:** No new features. Commit 13 existing audit fixes, add production scaffolding (LICENSE, CI, npm config), rewrite README for discovery by Ableton power users. All changes are to existing files or minimal new files (LICENSE, ci.yml).

**Tech Stack:** Node.js (CLI), Python/FastMCP (MCP server), GitHub Actions (CI), npm (packaging)

**Spec:** `docs/superpowers/specs/2026-03-17-production-ready-ship-design.md`

---

## File Structure

### Files to modify
- `CLAUDE.md` — fix tool count checklist, fix design spec path
- `README.md` — full rewrite for discovery
- `package.json` — add repository/homepage/bugs/keywords/type fields
- `.npmignore` — remove CHANGELOG.md exclusion

### Files to create
- `LICENSE` — MIT license file
- `.github/workflows/ci.yml` — GitHub Actions CI

### Files already modified (uncommitted audit fixes — commit as-is)
- `CHANGELOG.md`
- `bin/livepilot.js`
- `mcp_server/connection.py`
- `plugin/plugin.json`
- `plugin/skills/livepilot-core/SKILL.md`
- `plugin/skills/livepilot-core/references/overview.md`
- `remote_script/LivePilot/arrangement.py`
- `remote_script/LivePilot/devices.py`
- `remote_script/LivePilot/diagnostics.py`
- `remote_script/LivePilot/notes.py`
- `remote_script/LivePilot/server.py`
- `requirements.txt`
- `tests/test_domain_contracts.py`

---

## Chunk 1: Commit Audit Fixes + Production Scaffolding

### Task 1: Commit the 13 audit fixes

**Files:**
- All 13 modified files listed above (already changed and tested)

- [ ] **Step 1: Run tests to confirm everything passes**

```bash
python3 -m pytest tests/ -v
```

Expected: 38 passed

- [ ] **Step 2: Stage and commit all audit fixes**

```bash
git add CHANGELOG.md bin/livepilot.js mcp_server/connection.py plugin/plugin.json plugin/skills/livepilot-core/SKILL.md plugin/skills/livepilot-core/references/overview.md remote_script/LivePilot/arrangement.py remote_script/LivePilot/devices.py remote_script/LivePilot/diagnostics.py remote_script/LivePilot/notes.py remote_script/LivePilot/server.py requirements.txt tests/test_domain_contracts.py
git commit -m "$(cat <<'EOF'
fix: audit fixes — threading safety, undo guards, note properties, validation

- server.py: threading.Lock for _client_connected race condition
- connection.py: remove ping-before-every-command, fix dict mutation, preserve recv buffer
- notes.py: undo guards on modify/transpose, pass probability/velocity_deviation/release_velocity, handle zero-length clips
- devices.py: toggle_device finds Device On by name, reset iterations per browser category
- arrangement.py: reject negative beat_time
- diagnostics.py: cache clip_slots to avoid TOCTOU
- livepilot.js: proper exit codes for --doctor/--status
- requirements.txt: pin fastmcp<4.0.0
- Tool counts: 76→78 in CHANGELOG, overview.md, SKILL.md
- plugin.json: add skills/commands/agents arrays
- test: MockAbletonServer.stop() handles OSError

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Verify clean working tree**

```bash
git status
```

Expected: `nothing to commit, working tree clean`

---

### Task 2: Add LICENSE file

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: Create MIT LICENSE file**

```
MIT License

Copyright (c) 2026 Pilot Studio

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Commit**

```bash
git add LICENSE
git commit -m "$(cat <<'EOF'
chore: add MIT LICENSE file

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Add GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create CI workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "$(cat <<'EOF'
ci: add GitHub Actions workflow for pytest

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Harden package.json + fix .npmignore + update CLAUDE.md

**Files:**
- Modify: `package.json`
- Modify: `.npmignore`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update package.json**

Add these fields to the existing package.json:

```json
{
  "name": "livepilot",
  "version": "1.0.0",
  "description": "AI copilot for Ableton Live 12 — 78 MCP tools for production, sound design, and mixing",
  "author": "Pilot Studio",
  "license": "MIT",
  "type": "commonjs",
  "bin": {
    "livepilot": "./bin/livepilot.js"
  },
  "repository": {
    "type": "git",
    "url": "https://github.com/pilotstudio/livepilot"
  },
  "homepage": "https://github.com/pilotstudio/livepilot",
  "bugs": {
    "url": "https://github.com/pilotstudio/livepilot/issues"
  },
  "keywords": [
    "ableton",
    "live",
    "mcp",
    "ai",
    "music",
    "production",
    "midi",
    "daw",
    "claude",
    "copilot"
  ],
  "engines": {
    "node": ">=18.0.0"
  }
}
```

Note: The `repository` URL is a placeholder. Replace `pilotstudio/livepilot` with the actual GitHub org/repo once the repo is created.

- [ ] **Step 2: Remove CHANGELOG.md from .npmignore**

Remove the line `CHANGELOG.md` from `.npmignore`. The file should look like:

```
# Python artifacts
__pycache__
*.pyc
*.pyo
.pytest_cache/
.venv/
*.egg-info/

# Development
tests/
docs/
.git/
.github/
.gitignore
.eslintrc*
.prettierrc*
CLAUDE.md

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: Update CLAUDE.md**

One change: add CHANGELOG.md and `plugin/skills/livepilot-core/references/overview.md` to the tool count update checklist.

Note: The design spec path `docs/specs/2026-03-17-livepilot-design.md` is correct — it exists on disk and points to the original design spec. No path change needed.

The Tool Count section should read:

```
## Tool Count
Currently 78 tools. If adding/removing tools, update: README.md, package.json description, plugin/plugin.json, plugin/skills/livepilot-core/SKILL.md, plugin/skills/livepilot-core/references/overview.md, CLAUDE.md, CHANGELOG.md, tests/test_tools_contract.py
```

- [ ] **Step 4: Verify npm pack**

```bash
npm pack --dry-run 2>&1 | tail -10
```

Expected: CHANGELOG.md now included, package size <500KB, total files ~50

- [ ] **Step 5: Verify CLI**

```bash
node bin/livepilot.js --help
node bin/livepilot.js --version
```

Expected: Help text prints, version shows 1.0.0

- [ ] **Step 6: Run tests**

```bash
python3 -m pytest tests/ -v
```

Expected: 38 passed

- [ ] **Step 7: Commit**

```bash
git add package.json .npmignore CLAUDE.md docs/superpowers/
git commit -m "$(cat <<'EOF'
chore: harden package.json for npm, fix .npmignore, update CLAUDE.md

- Add repository, homepage, bugs fields to package.json
- Add claude, copilot to keywords
- Add type: commonjs
- Remove CHANGELOG.md from .npmignore exclusion
- Add CHANGELOG.md and overview.md to tool count checklist in CLAUDE.md
- Include production ship spec and plan docs

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 2: README Rewrite for Discovery

### Task 5: Rewrite README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite README.md**

Full content (replaces entire file):

```markdown
# LivePilot

AI copilot for Ableton Live 12 — 78 MCP tools for production, sound design, and mixing.

Control your entire Ableton session from Claude Code. Create tracks, program MIDI, load instruments, tweak parameters, mix levels, navigate arrangements — all through natural language. Built for power users who want to move faster without leaving the keyboard.

## Quick Start

```bash
# Install the Remote Script into Ableton Live
npx livepilot --install

# Restart Ableton Live, then enable LivePilot in:
# Preferences > Link, Tempo & MIDI > Control Surface

# Check connection
npx livepilot --status
```

### Claude Code Plugin

Add LivePilot as a Claude Code plugin for skills, slash commands, and the producer agent:

```bash
claude plugin add ./plugin
```

### MCP Configuration

Add to your MCP client config (`.mcp.json`):

```json
{
  "mcpServers": {
    "LivePilot": {
      "command": "npx",
      "args": ["livepilot"]
    }
  }
}
```

## 78 Tools Across 9 Domains

| Domain | Count | Key Tools |
|--------|-------|-----------|
| **Transport** | 12 | get_session_info, set_tempo, play/stop, undo/redo, action log, diagnostics |
| **Tracks** | 12 | create/delete/duplicate, name, color, mute/solo/arm |
| **Clips** | 10 | create/delete/duplicate, fire/stop, loop, launch mode |
| **Notes** | 8 | add/get/remove/modify, transpose, quantize, duplicate |
| **Devices** | 10 | parameters, load by name/URI, racks, batch set |
| **Scenes** | 6 | create/delete/duplicate, fire, rename |
| **Mixing** | 8 | volume, pan, sends, routing, master, return tracks |
| **Browser** | 4 | tree, items, search, load |
| **Arrangement** | 8 | clips, recording, cue points, navigation |

## Slash Commands

| Command | Description |
|---------|-------------|
| `/session` | Full session overview |
| `/beat` | Guided beat creation |
| `/mix` | Mixing assistant |
| `/sounddesign` | Sound design workflow |

## What It's Good At

**Session overview and navigation** — Summarize the set, find important tracks, report clip density, locate empty or duplicate sections. You often lose time understanding your own session state. LivePilot reads the whole session in one call.

**Repetitive build tasks** — Create track templates, duplicate and recolor tracks, load device chains, rename scenes, arm and route tracks. Repetitive actions are high-friction and low-creativity. This is where AI assistance feels immediately valuable.

**MIDI refinement** — Tighten timing, transpose selected notes, duplicate motifs, simplify busy passages, humanize or regularize a phrase. The AI improves your existing intent instead of pretending to invent taste from nothing.

**Session hygiene** — Detect tracks left armed, mute/solo leftovers, empty clips and unused scenes, inconsistent naming, MIDI tracks without instruments. Run `get_session_diagnostics` for a full health check.

## Architecture

```
Claude Code / AI Client
       │ MCP Protocol (stdio)
       ▼
┌─────────────────────┐
│   MCP Server        │  Python (FastMCP)
│   mcp_server/       │  Input validation, auto-reconnect
└────────┬────────────┘
         │ JSON over TCP (port 9878)
         ▼
┌─────────────────────┐
│   Remote Script     │  Runs inside Ableton's Python
│   remote_script/    │  Thread-safe command queue
│   LivePilot/        │  ControlSurface base class
└─────────────────────┘
```

Single-client TCP connection by design — Ableton's Live Object Model is not thread-safe.

## Compatibility

| Feature | Live 12 (all) | Suite only | Notes |
|---------|:-:|:-:|-------|
| Transport, tracks, clips, scenes | Yes | — | Core API, stable across all 12.x |
| MIDI notes (add, modify, remove) | Yes | — | Uses Live 12 note API |
| Device parameters, toggle, delete | Yes | — | Works with any device |
| Browser search & load | Yes | — | Results depend on installed content |
| Mixing (volume, pan, sends, routing) | Yes | — | |
| Arrangement (cue points, recording) | Yes | — | |
| Stock instruments (Analog, Operator, Wavetable, Drift, Meld) | — | Yes | Drift and Meld are Suite instruments |
| Max for Live devices | — | Yes | Requires Suite or M4L add-on |
| Stock effects (Compressor, Reverb, EQ Eight, etc.) | Yes | — | All editions include audio effects |
| Third-party VST/AU plugins | Yes | — | Loads via browser if installed |

**Python version:** Ableton Live 12 bundles Python 3.11. The MCP server runs outside Ableton and requires Python 3.10+.

## CLI

```bash
npx livepilot              # Start MCP server (stdio)
npx livepilot --install    # Install Remote Script
npx livepilot --uninstall  # Remove Remote Script
npx livepilot --status     # Check Ableton connection
npx livepilot --doctor     # Full diagnostic check
npx livepilot --version    # Version info
npx livepilot --help       # Show all commands
```

## Requirements

- **Ableton Live 12** (minimum)
- **Python 3.10+** (auto-detected; venv created on first run)
- **Node.js 18+**

## Development

```bash
# Set up Python environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Run tests
.venv/bin/pytest tests/ -v
```

## License

MIT
```

Key changes from current README:
- Added value proposition paragraph at top
- Added "What It's Good At" section (new — pulled from positioning doc)
- Fixed Development section to use venv
- Tightened Connection Model into one line under Architecture
- Removed stale TDPilot sister project link (placeholder URL)
- Trimmed Compatibility table to essentials

- [ ] **Step 2: Run tests** (README changes shouldn't break tests, but verify)

```bash
python3 -m pytest tests/ -v
```

Expected: 38 passed

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs: rewrite README for discovery by Ableton power users

- Add value proposition paragraph
- Add "What It's Good At" section from positioning doc
- Fix Development section to use venv
- Tighten Connection Model into Architecture note
- Remove stale placeholder URLs

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 3: Final Verification

### Task 6: End-to-end verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: 38 passed

- [ ] **Step 2: Verify npm pack is clean**

```bash
npm pack --dry-run 2>&1
```

Check:
- CHANGELOG.md is included
- No tests/, docs/, .github/, CLAUDE.md, __pycache__/ in output
- Package size <500KB
- Total files ~50

- [ ] **Step 3: Verify CLI commands**

```bash
node bin/livepilot.js --help
node bin/livepilot.js --version
```

Expected: Help text prints correctly, version shows 1.0.0

- [ ] **Step 4: Verify LICENSE exists**

```bash
cat LICENSE | head -3
```

Expected: `MIT License` header

- [ ] **Step 5: Verify CI file exists**

```bash
cat .github/workflows/ci.yml | head -5
```

Expected: `name: CI`

- [ ] **Step 6: Verify working tree is clean**

```bash
git status
```

Expected: `nothing to commit, working tree clean`

- [ ] **Step 7: Verify git log shows all commits**

```bash
git log --oneline -6
```

Expected: 5 new commits on top (audit fixes, LICENSE, CI, package+CLAUDE.md+docs, README) plus the spec commit

---

## Summary

| Task | What | Commit |
|------|------|--------|
| 1 | Commit 13 audit fixes | `fix: audit fixes — threading safety, undo guards, ...` |
| 2 | Add LICENSE file | `chore: add MIT LICENSE file` |
| 3 | Add GitHub Actions CI | `ci: add GitHub Actions workflow for pytest` |
| 4 | Harden package.json + .npmignore + CLAUDE.md | `chore: harden package.json for npm, ...` |
| 5 | Rewrite README for discovery | `docs: rewrite README for discovery ...` |
| 6 | End-to-end verification | (no commit — verify only) |

After all tasks complete, the user can:
- `npm publish` to ship to npm
- Push to GitHub and create a release
- Submit plugin to Claude Code registry
