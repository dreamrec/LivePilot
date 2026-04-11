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

Current: **292 tools across 39 domains**.
Core (no M4L): **149**. Analyzer (M4L): **29**. Perception (offline): **4**. V2 engines: **86+**.

Verify: `grep -rc "@mcp.tool" mcp_server/tools/ | grep -v ":0" | awk -F: '{sum+=$2} END{print sum}'`

Files that reference tool count:
- [ ] `README.md` — header, PERCEPTION section ("207 core...30 analyzer"), Analyzer table header "(29)", Perception table header "(4)"
- [ ] `package.json` → `"description"` (292 tools, 39 domains)
- [ ] `server.json` → `"description"`
- [ ] `livepilot/.Codex-plugin/plugin.json` → `"description"` (primary Codex manifest)
- [ ] `livepilot/.claude-plugin/plugin.json` → `"description"` (must match Codex plugin)
- [ ] `.claude-plugin/marketplace.json` → `"description"`
- [ ] `CLAUDE.md` → "292 tools across 39 domains"
- [ ] `livepilot/skills/livepilot-core/SKILL.md` — "292 tools across 39 domains", Analyzer (30), Perception (4)
- [ ] `livepilot/skills/livepilot-core/references/overview.md` — "292 tools across 39 domains"
- [ ] `docs/manual/index.md` — domain table: Analyzer (30), Perception (4)
- [ ] `docs/manual/getting-started.md` — "207 core tools...30 analyzer"
- [ ] `docs/manual/tool-reference.md` — all domains present with correct counts
- [ ] `docs/TOOL_REFERENCE.md` — all domains present
- [ ] `docs/M4L_BRIDGE.md` — "207 core tools...30 analyzer"
- [ ] `docs/social-banner.html`
- [ ] `mcp_server/tools/analyzer.py` → module docstring
- [ ] `tests/test_tools_contract.py` → expected total count

**How to check:** `grep -rn "168\|139\|135\|127\|115\|107" --include="*.md" --include="*.json" --include="*.py" --include="*.html" . | grep -v node_modules | grep -v .git | grep -v __pycache__ | grep -v CHANGELOG`

## 3. Domain Count

Current: **39 domains**: transport, tracks, clips, notes, devices, scenes, mixing, browser, arrangement, memory, analyzer, automation, theory, generative, harmony, midi_io, perception, agent_os, composition, motif, research, planner, project_brain, runtime, evaluation, mix_engine, sound_design, transition_engine, reference_engine, translation_engine, performance_engine, song_brain, preview_studio, hook_hunter, stuckness_detector, wonder_mode, session_continuity, creative_constraints.

- [ ] All files that mention domain count say "39 domains"
- [ ] Domain lists include ALL 39 (especially newer domains — they're the most often omitted)

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
- [ ] `docs/manual/tool-reference.md` — all 39 domains listed, all 292 tools present
- [ ] `docs/TOOL_REFERENCE.md` — all 39 domains present
- [ ] `docs/M4L_BRIDGE.md` — architecture accurate, core tool count correct

## 9. Derived Artifacts

- [ ] `m4l_device/LivePilot_Analyzer.amxd` — frozen JS matches source? All commands present?
- [ ] If `livepilot_bridge.js` changed → amxd needs rebuilding in Max editor

## 10. Code Consistency

- [ ] `@mcp.tool()` count matches documented tool count: `grep -r "@mcp.tool" mcp_server/tools/ | wc -l`
- [ ] No dead imports or unused code in recently changed files
- [ ] Remote script version matches MCP server version
- [ ] All tests pass: `python3 -m pytest tests/ -v`

## Quick Verify Command

```bash
echo "=== Versions ===" && grep -h '"version"' package.json server.json livepilot/.Codex-plugin/plugin.json livepilot/.claude-plugin/plugin.json .claude-plugin/marketplace.json | head -7 && grep __version__ mcp_server/__init__.py remote_script/LivePilot/__init__.py && echo "=== Tool count ===" && grep -rc "@mcp.tool" mcp_server/tools/ | grep -v ":0" | awk -F: '{sum+=$2} END{print "Total:", sum}' && echo "=== Tests ===" && python3 -m pytest tests/ -q 2>&1 | tail -1
```
