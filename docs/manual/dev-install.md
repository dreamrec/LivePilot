# Dev install — running LivePilot from a local checkout

Use this when you're editing `mcp_server/` or `remote_script/` and want to
verify your changes against live Ableton before publishing. End users should
use the standard `npx livepilot --install` flow in
[getting-started.md](getting-started.md) instead — that path resolves
`livepilot` against the npm registry and installs the published package.

> **Why not just `npx livepilot --install` from inside my checkout?**
> Because npm ignores your local tree when `livepilot` resolves to a
> published package. Your edits are silently overridden by whatever's on
> the registry, and the Remote Script copied into Ableton points at the
> published MCP server, not the one you're editing.

---

## 1. Clone and set up the Python venv

```bash
git clone https://github.com/dreamrec/LivePilot
cd LivePilot

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

LivePilot targets Python 3.11+ (matches CI). If `python3 --version` reports
3.10 or earlier, install a newer Python before creating the venv — the
FastMCP server uses PEP 604 union syntax that won't parse on older runtimes.

## 2. Install the Remote Script from your checkout

```bash
node bin/livepilot.js --install
```

Important: **use `node bin/livepilot.js --install`, not `npx livepilot --install`**.
The `npx` form downloads a fresh copy of the published package into its cache
and runs the installer *from there* — so even if you're sitting in a git
checkout, your local edits to `remote_script/LivePilot/` aren't what ends up
in Ableton. The `node bin/livepilot.js` form runs the installer from your
current tree, so the files copied into Ableton match your checkout exactly.

After the copy succeeds, restart Ableton and enable the Control Surface as
described in [getting-started.md](getting-started.md) Step 2.

## 3. Point your MCP client at the local server

The MCP server is just a Python module — `python -m mcp_server`. Your
client launches this directly instead of going through `npx livepilot`.

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "LivePilot-dev": {
      "command": "/absolute/path/to/LivePilot/.venv/bin/python",
      "args": ["-m", "mcp_server"]
    }
  }
}
```

Use the absolute path to your venv's Python, not just `python` — Claude
Desktop runs with a different shell environment and may not have your
venv on `PATH`.

### Claude Code

```bash
claude mcp add LivePilot-dev -- \
  /absolute/path/to/LivePilot/.venv/bin/python -m mcp_server
```

### Cursor / VS Code / Other MCP clients

Add an entry to your client's MCP config file (`.cursor/mcp.json`,
`.vscode/mcp.json`, etc.) with the same `command` + `args` shape as the
Claude Desktop block above.

---

Once configured, restart the client. You'll have `LivePilot-dev` listed
alongside (or instead of) the published `LivePilot` entry — tool calls to
`LivePilot-dev` route through your local Python. The published entry still
works in parallel; nothing here touches it.

## 3a. User atlas vs bundled atlas (v1.22.0+)

Your personal atlas lives at `~/.livepilot/atlas/device_atlas.json` —
**not** inside the repo. The repo's `mcp_server/atlas/device_atlas.json`
is the bundled baseline that new installs inherit. `AtlasManager` prefers
the user path if it exists, else falls back to the bundled baseline.

When you run `scan_full_library(force=true)` against live Ableton, it
writes to `~/.livepilot/atlas/device_atlas.json` — regardless of whether
you're running the dev install or the published package. So:

- **Your dev scans can't pollute the repo.** The bundled atlas in the
  worktree stays at whatever version you checked out from main.
- **Your personal atlas survives `git checkout`, `git reset --hard`,
  and worktree churn.** It lives in your home directory.
- **To reset your personal atlas**, delete it: `rm ~/.livepilot/atlas/device_atlas.json`.
  Next client restart falls back to the bundled baseline until you rescan.
- **To regenerate the bundled baseline** (rare — contributor work when
  shipping a new version of the canonical shipped atlas), run the scan
  from a stock Ableton install (no third-party packs, no User Library
  additions), then manually copy the result from
  `~/.livepilot/atlas/device_atlas.json` into
  `mcp_server/atlas/device_atlas.json` and commit. This path is
  deliberately manual so accidental personal-scan leaks don't happen.

## 4. Iterate

**After editing `mcp_server/**/*.py`:**
Restart your MCP client (Claude Desktop, Claude Code, etc.). The MCP
server is relaunched on client restart, which reloads your edits.

**After editing `remote_script/LivePilot/*.py`:**
```bash
node bin/livepilot.js --install     # re-copy to Ableton
```
Then in your MCP client, call the `reload_handlers` tool. This re-fires the
`@register` decorators in Ableton's Python without toggling the Control
Surface — the TCP connection on port 9878 stays open. See the
**Remote Script reload workflow** note in the root `CLAUDE.md` for why this
works and why `reload_handlers` is the standard procedure (never manually
toggle the Control Surface in Live's Preferences — the module cache does
not behave the way you expect).

**After editing `m4l_device/LivePilot_Analyzer.*` (Max source):**
Rebuild the `.amxd` inside Max, then reload the device on the master
track. See the **Binary Patching Workflow** section of `CLAUDE.md` for
the same-byte-count swap pattern used when Max's editor refuses to
persist an attribute change.

## 5. Running the test suite locally

```bash
# From the repo root with the venv active:
python -m pytest tests/ -q
```

3128 tests as of v1.21.4. The suite takes ~30 seconds on a modern Mac.
A handful of tests depend on external binaries:
- `test_amxd_freeze_drift` requires the `.amxd` file to be committed
- `test_npm_pack_includes_expected_files` requires `npm` on PATH
- Socket-level tests in `test_remote_server_single_client.py` occasionally
  flake on macOS with `OSError [Errno 49] Can't assign requested address`
  (ephemeral-port exhaustion) — retry once; if it persists, run with
  `--forked` to isolate.

## 6. `sync_metadata` drift check

Before committing any changes that touch version strings, tool counts,
domain lists, or cross-referenced numbers in prose, run:

```bash
python scripts/sync_metadata.py --check
```

If it reports drift, `--fix` will mechanically rewrite mechanical counts
(tool, domain, semantic move, analyzer tool, bridge command, genre,
enriched device, atlas device). Prose narrative that can't be
mechanically rewritten is listed but not edited. See
[README.md](../../README.md) and the `## Version Bump`/`## Tool Count`
sections of `CLAUDE.md` for the full set of source-of-truth files
`sync_metadata` enforces.

## 7. Going back to the published version

Either remove `LivePilot-dev` from your MCP config, or just stop using it.
The published `LivePilot` entry (if present) is untouched and still
resolves to `npx livepilot` → the registry version. You can keep both
registered in your config at once and switch between them per-request by
addressing the server by name in your prompt.

To re-install the published Remote Script (overriding your local copy in
Ableton), run `npx livepilot --install` from any directory.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'mcp_server'`**
Your client is launching Python but not from the repo root. Either pass
`cwd` in the MCP config (not all clients support it) or wrap the
command in a shell snippet that `cd`s first:

```json
{
  "command": "/absolute/path/to/LivePilot/.venv/bin/python",
  "args": ["-c", "import sys; sys.path.insert(0, '/absolute/path/to/LivePilot'); from mcp_server.__main__ import main; main()"]
}
```

**`Another client is already connected` on port 9878**
The published `LivePilot` MCP server is still running and holding the TCP
socket. Fully quit all MCP clients before restarting — or disable the
published `LivePilot` entry in your client's MCP config so only
`LivePilot-dev` starts up.

**Edits to `mcp_server/` don't take effect after client restart**
Confirm your `command` points at the venv Python, not the system Python.
A stale `__pycache__` in the repo can also shadow fresh edits; clear with
`find mcp_server -name __pycache__ -exec rm -rf {} +` and restart.

**Edits to `remote_script/` don't take effect after `reload_handlers`**
The `reload_handlers` tool re-fires `@register` decorators in-place but
can't reload module-level constants computed at import time. If your
change is at module level, you need a full Ableton restart — toggle the
Control Surface off then on won't suffice either (the `sys.modules`
cache persists across toggles; see the `feedback_remote_script_module_cache`
memory note for the full mechanism).
