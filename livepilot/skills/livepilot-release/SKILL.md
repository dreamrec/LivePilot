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
- [ ] `livepilot/.claude-plugin/plugin.json` → `"version"`
- [ ] `mcp_server/__init__.py` → `__version__`
- [ ] `remote_script/LivePilot/__init__.py` → version in log message
- [ ] `m4l_device/livepilot_bridge.js` → version in ping response
- [ ] `CHANGELOG.md` → latest version header
- [ ] `docs/social-banner.html` → version display

**How to check:** `grep -rn "1\.[0-9]\.[0-9]" package.json server.json livepilot/.claude-plugin/plugin.json mcp_server/__init__.py remote_script/LivePilot/__init__.py m4l_device/livepilot_bridge.js CHANGELOG.md docs/social-banner.html`

## 2. Tool Count (must ALL match)

- [ ] `README.md` — every occurrence
- [ ] `package.json` → `"description"`
- [ ] `server.json` → `"description"`
- [ ] `livepilot/.claude-plugin/plugin.json` → `"description"`
- [ ] `CLAUDE.md`
- [ ] `livepilot/skills/livepilot-core/SKILL.md` — header and domain breakdown
- [ ] `livepilot/skills/livepilot-core/references/overview.md`
- [ ] `docs/manual/index.md`
- [ ] `docs/manual/tool-reference.md`
- [ ] `docs/TOOL_REFERENCE.md`
- [ ] `docs/M4L_BRIDGE.md`
- [ ] `docs/social-banner.html`
- [ ] `mcp_server/tools/analyzer.py` → module docstring
- [ ] `tests/test_tools_contract.py` → expected count

**How to check:** `grep -rn "127\|128\|129\|130\|131\|132\|133\|134" --include="*.md" --include="*.json" --include="*.py" --include="*.html" --include="*.js" . | grep -v node_modules | grep -v .git | grep -v __pycache__`

## 3. Domain Count

- [ ] All files above that mention "11 domains" should say "12 domains"
- [ ] Domain lists should include: transport, tracks, clips, notes, devices, scenes, mixing, browser, arrangement, automation, memory, analyzer

## 4. npm Registry

- [ ] `npm view livepilot version` matches local version
- [ ] If not: `npm publish`
- [ ] Verify badge will update: badge URL in README.md points to shields.io/npm/v/livepilot

## 5. GitHub

- [ ] Repo description matches current tool count and features
- [ ] Topics are current (should include: ai, mcp, ableton, livepilot, max-for-live, audio-analysis)
- [ ] Latest release matches current version (`gh release list`)
- [ ] Release notes are current
- [ ] Old stale releases cleaned up
- [ ] Git tags: only relevant versions exist (`git tag -l`)
- [ ] No co-author or unwanted metadata in commit messages

## 6. Plugin Cache

- [ ] `~/.claude/plugins/cache/dreamrec-LivePilot/livepilot/` has current version directory
- [ ] Old version directories removed

## 7. Social/Promotional Assets

- [ ] `docs/social-banner.html` — tool count, version, domain list
- [ ] `docs/social-banner.png` — regenerated from HTML (must match)
- [ ] GitHub repo social preview image (Settings > Social preview)

## 8. Documentation Content

- [ ] `README.md` — features match current capabilities
- [ ] `docs/manual/getting-started.md` — install instructions current, mentions M4L Analyzer
- [ ] `docs/manual/tool-reference.md` — all tools listed
- [ ] `docs/M4L_BRIDGE.md` — architecture accurate
- [ ] `docs/TOOL_REFERENCE.md` — all tools listed with correct params

## 9. Derived Artifacts

- [ ] `m4l_device/LivePilot_Analyzer.amxd` — frozen JS matches source? All commands present?
- [ ] Distributable zip on Desktop — rebuilt with latest?
- [ ] Private backup repo — synced and pushed?
- [ ] `LivePilot-v*.INSTALL.txt` — updated?

## 10. Code Consistency

- [ ] `@mcp.tool()` count matches documented tool count: `grep -r "@mcp.tool" mcp_server/tools/ | wc -l`
- [ ] No dead imports or unused code in recently changed files
- [ ] Remote script version matches MCP server version

## Quick Verify Command

Run this one-liner to catch most issues:
```bash
echo "=== Versions ===" && grep -h '"version"' package.json server.json livepilot/.claude-plugin/plugin.json | head -5 && grep __version__ mcp_server/__init__.py && echo "=== Tool count ===" && grep -rc "@mcp.tool" mcp_server/tools/ | tail -1 && echo "=== npm ===" && npm view livepilot version 2>/dev/null && echo "=== GitHub release ===" && gh release list --limit 1 && echo "=== Tags ===" && git tag -l
```
