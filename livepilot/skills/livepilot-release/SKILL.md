---
name: livepilot-release
description: Release checklist for LivePilot — run before ANY push, publish, or "update everything" request. Covers every file, channel, and artifact that references version numbers, tool counts, or project state.
---

# LivePilot Release Checklist

Run this checklist EVERY time the user says "update everything", "push", "release", "make sure everything is current", or similar.

## 1. Version Strings (must ALL match)

- [ ] `package.json` → `"version"`
- [ ] `package-lock.json` → `"version"` (run `npm install --package-lock-only` if stale)
- [ ] `server.json` → `"version"` (TWO locations: top-level and package)
- [ ] `livepilot/.Codex-plugin/plugin.json` → `"version"` (primary Codex manifest)
- [ ] `livepilot/.claude-plugin/plugin.json` → `"version"` (must match Codex plugin)
- [ ] `.claude-plugin/marketplace.json` → `"version"` in plugins array
- [ ] `mcp_server/__init__.py` → `__version__`
- [ ] `remote_script/LivePilot/__init__.py` → `__version__` (log message auto-uses it)
- [ ] `m4l_device/livepilot_bridge.js` → version in ping response
- [ ] `CLAUDE.md` → header line
- [ ] `livepilot/skills/livepilot-core/references/overview.md` → header line
- [ ] `CHANGELOG.md` → latest version header
- [ ] `docs/social-banner.html` → version display
- [ ] `docs/M4L_BRIDGE.md` → ping response example

**How to check:** `grep -rn "1\.[0-9]\.[0-9]" package.json server.json livepilot/.Codex-plugin/plugin.json livepilot/.claude-plugin/plugin.json .claude-plugin/marketplace.json mcp_server/__init__.py remote_script/LivePilot/__init__.py m4l_device/livepilot_bridge.js CHANGELOG.md CLAUDE.md livepilot/skills/livepilot-core/references/overview.md docs/social-banner.html docs/M4L_BRIDGE.md`

## 2. Tool Count (must ALL match)

Current: **433 tools across 53 domains**.
Spectral/analyzer (bridge-only): **38**. All others: **292** (work without bridge, some with graceful fallbacks). Backed by 32 bridge commands.

Verify: `grep -rc "@mcp.tool" mcp_server/tools/ | grep -v ":0" | awk -F: '{sum+=$2} END{print sum}'`

Files that reference tool count:
- [ ] `README.md` — header ("433 tools. 53 domains"), bridge section ("38 spectral/analyzer tools require bridge")
- [ ] `package.json` → `"description"`
- [ ] `server.json` → `"description"`
- [ ] `manifest.json` → `"description"`
- [ ] `livepilot/.Codex-plugin/plugin.json` → `"description"` (primary Codex manifest)
- [ ] `livepilot/.claude-plugin/plugin.json` → `"description"` (must match Codex plugin)
- [ ] `.claude-plugin/marketplace.json` → `"description"`
- [ ] `CLAUDE.md` → "433 tools across 53 domains"
- [ ] `CONTRIBUTING.md` → tool count in intro
- [ ] `livepilot/skills/livepilot-core/SKILL.md` — tool/domain count
- [ ] `livepilot/skills/livepilot-core/references/overview.md` — tool/domain count
- [ ] `docs/manual/index.md` — domain table with correct per-domain counts
- [ ] `docs/manual/getting-started.md` — bridge copy (avoid hard numeric core/bridge split — use "38 spectral tools require bridge")
- [ ] `docs/manual/tool-reference.md` — all domains present with correct counts
- [ ] `docs/manual/tool-catalog.md` — regenerated from source
      (`python3 scripts/generate_tool_catalog.py > docs/manual/tool-catalog.md`)
- [ ] `docs/M4L_BRIDGE.md` — bridge copy (avoid hard numeric core/bridge split — use "38 spectral tools require bridge")
- [ ] `docs/social-banner.html`
- [ ] `tests/test_tools_contract.py` → expected total count
- [ ] `tests/test_skill_contracts.py` → catalog sync test passes

**How to check:** `grep -rn "168\|139\|135\|127\|115\|107" --include="*.md" --include="*.json" --include="*.py" --include="*.html" . | grep -v node_modules | grep -v .git | grep -v __pycache__ | grep -v CHANGELOG`

## 3. Domain Count

Current: **53 domains**: transport, tracks, clips, notes, devices, scenes, mixing, browser, arrangement, memory, analyzer, automation, theory, generative, harmony, midi_io, perception, agent_os, composition, motif, research, planner, project_brain, runtime, evaluation, mix_engine, sound_design, transition_engine, reference_engine, translation_engine, performance_engine, song_brain, preview_studio, hook_hunter, stuckness_detector, wonder_mode, session_continuity, creative_constraints, device_forge, sample_engine, atlas, composer, experiment, musical_intelligence, semantic_moves, diagnostics, follow_actions, grooves, scales, take_lanes, miditool, synthesis_brain, creative_director.

- [ ] All files that mention domain count say "53 domains"
- [ ] Domain lists include ALL 45 (especially newer domains — they're the most often omitted)

## 4. npm Registry

- [ ] `npm view livepilot version` matches local version
- [ ] If not: `npm publish`

## 5. GitHub

- [ ] Repo description matches current tool count and features
- [ ] Topics are current (should include: ai, mcp, ableton, livepilot, max-for-live, audio-analysis)
- [ ] Latest release matches current version (`gh release list`)
- [ ] Release notes are current

## 6. Plugin Cache

- [ ] `~/.claude/plugins/cache/dreamrec-LivePilot/livepilot/` has current version directory
- [ ] Old version directories removed
- [ ] `~/.claude/plugins/installed_plugins.json` → `livepilot@dreamrec-LivePilot` entry: update `version`, `installPath`, `gitCommitSha`, `lastUpdated`

## 7. Social/Promotional Assets

- [ ] `docs/social-banner.html` — tool count, version, domain list
- [ ] `docs/social-banner.png` — regenerated from HTML (must match)
- [ ] GitHub repo social preview image (Settings > Social preview)

## 8. Documentation Content

- [ ] `README.md` — features match current capabilities, "Coming" section is accurate
- [ ] `docs/manual/getting-started.md` — install instructions current
- [ ] `docs/manual/tool-reference.md` — all 53 domains listed, all 433 tools present
- [ ] `docs/M4L_BRIDGE.md` — architecture accurate, core/bridge counts correct

## 9. Derived Artifacts

- [ ] `m4l_device/LivePilot_Analyzer.amxd` — frozen JS matches source? All commands present?
- [ ] If `livepilot_bridge.js` changed → amxd needs rebuilding in Max editor
- [ ] `dist/livepilot-${VERSION}.mcpb` — MCPB bundle for Claude Desktop one-click install.
      **REQUIRED for every release** — the README's "Easiest: Claude Desktop Extension (1 click)"
      path points at this asset. From v1.17 through v1.20.2 every release silently shipped
      without it; v1.20.3+ MUST attach the bundle to the GitHub release.
      ```bash
      # Build (produces dist/livepilot-${VERSION}.mcpb — versioned, in dist/, ~4-5 MB)
      bash scripts/build_mcpb.sh

      # Attach to the release (run after `gh release create`)
      VERSION=$(python3 -c "import json; print(json.load(open('manifest.json'))['version'])")
      gh release upload "v${VERSION}" "dist/livepilot-${VERSION}.mcpb" --clobber
      ```
      The script stages `manifest.json` + `bin/livepilot.js` + `mcp_server/` + `remote_script/`
      + `m4l_device/` + `installer/` + `requirements.txt`, strips `__pycache__`/`*.pyc`/`.DS_Store`,
      zips into `dist/`, and verifies the embedded manifest name+version+entry_point.

## 10. Code Consistency

- [ ] `@mcp.tool()` count matches documented tool count: `grep -r "@mcp.tool" mcp_server/tools/ | wc -l`
- [ ] No dead imports or unused code in recently changed files
- [ ] Remote script version matches MCP server version
- [ ] All tests pass: `python3 -m pytest tests/ -v`

## 11. Automated Checks

- [ ] `python scripts/sync_metadata.py --check` — all metadata in sync
- [ ] `python -m pytest tests/test_command_boundary_audit.py` — no invalid TCP targets
- [ ] `python -m pytest tests/test_move_annotations.py` — all moves annotated
- [ ] `python -m pytest tests/test_capability.py` — capability contract works
- [ ] `python -m pytest tests/test_capability_probe.py` — doctor probe works

## 12. Release Smoke Board

- [ ] Run through `docs/archive/release-smoke-board-v1.10-era.md` scenarios
      against a real Ableton session (archived — still a useful pre-flight
      checklist even if written against v1.10 tool surface)
- [ ] All preview modes correctly labeled (audible/metadata/analytical)
- [ ] Persistence survives server restart

## Quick Verify Command

```bash
echo "=== Versions ===" && grep -h '"version"' package.json server.json manifest.json livepilot/.Codex-plugin/plugin.json livepilot/.claude-plugin/plugin.json .claude-plugin/marketplace.json | head -8 && grep __version__ mcp_server/__init__.py remote_script/LivePilot/__init__.py && echo "=== Tool count ===" && grep -rc "@mcp.tool" mcp_server/ | grep -v ":0" | awk -F: '{sum+=$2} END{print "Total:", sum}' && echo "=== Tests ===" && python3 -m pytest tests/ -q 2>&1 | tail -1
```
