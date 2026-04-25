# Contributing to LivePilot

Thank you for your interest in contributing to LivePilot. This guide will help you get started.

## Quick Links

- [Bug reports](https://github.com/dreamrec/LivePilot/issues/new?template=bug_report.yml)
- [Feature requests](https://github.com/dreamrec/LivePilot/issues/new?template=feature_request.yml)
- [Questions & help](https://github.com/dreamrec/LivePilot/discussions)

## Development Setup

```bash
git clone https://github.com/dreamrec/LivePilot.git
cd LivePilot
python3 -m venv .venv
source .venv/bin/activate          # macOS/Linux
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install pytest pytest-asyncio
```

### Install the Remote Script

```bash
npx livepilot --install
```

Restart Ableton → Preferences → Link, Tempo & MIDI → Control Surface → **LivePilot**

### Run Tests

```bash
pytest tests/ -v
```

Tests run without Ableton — they validate tool contracts, schema, and pure Python logic.
Integration testing with a live session is done manually.

## Architecture Overview

```
remote_script/LivePilot/   Python ControlSurface inside Ableton (main thread)
mcp_server/                FastMCP server — validates inputs, sends TCP to Ableton
m4l_device/                Max for Live analyzer — UDP/OSC bridge for deep LOM access
livepilot/                 Plugin — skills, slash commands, producer agent
installer/                 Auto-detects Ableton path, copies Remote Script
```

All Live Object Model (LOM) calls execute on Ableton's main thread via `schedule_message`.
Communication is JSON over TCP, newline-delimited, port 9878.

## How to Contribute

### Reporting Bugs

Use the [bug report template](https://github.com/dreamrec/LivePilot/issues/new?template=bug_report.yml).
Include:

- LivePilot version (`npx livepilot --version`)
- Ableton Live version
- Diagnostics output (`npx livepilot --doctor`)
- Steps to reproduce

### Suggesting Features

Use the [feature request template](https://github.com/dreamrec/LivePilot/issues/new?template=feature_request.yml).
Explain the workflow problem before describing the solution.

### Submitting Code

1. **Fork** the repository
2. **Create a branch** from `main` (`git checkout -b feat/your-feature`)
3. **Make your changes** — keep commits focused and atomic
4. **Run tests** — `pytest tests/ -v` must pass
5. **Update documentation** if you add or remove tools:
   - Update tool count in `README.md`, `CLAUDE.md`, `package.json`
   - Add an entry to `CHANGELOG.md`
6. **Open a PR** against `main`

### Code Style

- **Python:** Follow existing conventions in `mcp_server/`. No linter is enforced yet, but keep it clean.
- **Remote Script:** All LOM calls must use `schedule_message` — never call the LOM directly from a non-main thread.
- **M4L Bridge (JS):** Changes to `livepilot_bridge.js` must be tested with the analyzer loaded on the master track in a live Ableton session.
- **Error codes:** Use structured errors: `INDEX_ERROR`, `NOT_FOUND`, `INVALID_PARAM`, `STATE_ERROR`, `TIMEOUT`, `INTERNAL`.

### Commit Messages

Use concise, descriptive messages:

```
fix: bridge UTF-8 OSC args, KeyError→INVALID_PARAM
feat: add per-track loudness analysis
docs: update tool reference for v1.9.11
```

Prefix with `fix:`, `feat:`, `docs:`, `refactor:`, `test:`, or `chore:`.

## Tool Count Discipline

Currently **433 tools**. If you add or remove a `@mcp.tool()` decorator, the
`sync_metadata.py` script will propagate the new count automatically:

```bash
# Update the expected count in tests/test_tools_contract.py first:
#   assert len(tools) == 325   # for example
python scripts/sync_metadata.py --fix
```

This updates `README.md`, `CLAUDE.md`, `package.json`, both `plugin.json`
files, `server.json`, SKILL.md, overview.md, tool-catalog.md, and the
related docs in one pass.

CI enforces sync — `python scripts/sync_metadata.py --check` runs on every
PR and fails if any file is out of date. Version string bumps still require
a manual edit to `package.json` (the source of truth).

## Areas Where Help Is Welcome

- **Windows testing** — The installer and Remote Script are tested primarily on macOS
- **Documentation** — Guides, tutorials, workflow examples
- **New automation recipes** — Add to the 15 built-in recipes
- **Theory tools** — Additional modes, non-Western scales, extended harmony
- **Test coverage** — More contract tests, edge cases

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you agree to uphold this code.

## License

By contributing, you agree that your contributions will be licensed under the [Business Source License 1.1](LICENSE).
