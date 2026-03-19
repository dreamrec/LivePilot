#!/usr/bin/env node
"use strict";

const { execFileSync, execSync, spawn } = require("child_process");
const fs = require("fs");
const net = require("net");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const PKG = require(path.join(ROOT, "package.json"));
const VENV_DIR = path.join(ROOT, ".venv");
const REQUIREMENTS = path.join(ROOT, "requirements.txt");

// ---------------------------------------------------------------------------
// Python detection
// ---------------------------------------------------------------------------

function findPython() {
  // On Windows, also try the "py -3" launcher which avoids the
  // Microsoft Store stub that "python3" resolves to.
  const candidates = process.platform === "win32"
    ? ["python", "python3", "py"]
    : ["python3", "python"];

  for (const cmd of candidates) {
    try {
      const args = cmd === "py" ? ["-3", "--version"] : ["--version"];
      const out = execFileSync(cmd, args, {
        encoding: "utf-8",
        timeout: 5000,
      }).trim();
      const match = out.match(/Python\s+(\d+)\.(\d+)/);
      if (match) {
        const major = parseInt(match[1], 10);
        const minor = parseInt(match[2], 10);
        if (major === 3 && minor >= 9) {
          // For "py" launcher, the actual command to use is "py -3"
          const actualCmd = cmd === "py" ? "py" : cmd;
          const actualArgs = cmd === "py" ? ["-3"] : [];
          return { cmd: actualCmd, version: out, prefixArgs: actualArgs };
        }
      }
    } catch {
      // command not found or failed — try next
    }
  }
  return null;
}

/**
 * Return the path to the Python binary inside the venv.
 */
function venvPython() {
  const isWin = process.platform === "win32";
  return path.join(VENV_DIR, isWin ? "Scripts" : "bin", isWin ? "python.exe" : "python3");
}

// ---------------------------------------------------------------------------
// Virtual environment bootstrap
// ---------------------------------------------------------------------------

/**
 * Ensure a local .venv exists with dependencies installed.
 * Returns the path to the venv Python binary.
 */
function ensureVenv(systemPython, prefixArgs) {
  const prefix = prefixArgs || [];
  const venvPy = venvPython();

  // Check if venv already exists and has our deps
  if (fs.existsSync(venvPy)) {
    try {
      execFileSync(venvPy, ["-c", "import fastmcp; import midiutil; import pretty_midi"], {
        encoding: "utf-8",
        timeout: 10000,
        stdio: "pipe",
      });
      return venvPy; // venv exists and all deps importable
    } catch {
      // venv exists but deps missing — reinstall
      console.error("LivePilot: reinstalling Python dependencies...");
      execFileSync(venvPy, ["-m", "pip", "install", "-q", "-r", REQUIREMENTS], {
        cwd: ROOT,
        stdio: ["pipe", "pipe", "inherit"],
        timeout: 120000,
      });
      return venvPy;
    }
  }

  // Create venv from scratch
  console.error("LivePilot: setting up Python environment (first run)...");
  execFileSync(systemPython, [...prefix, "-m", "venv", VENV_DIR], {
    cwd: ROOT,
    stdio: ["pipe", "pipe", "inherit"],
    timeout: 30000,
  });

  console.error("LivePilot: installing dependencies...");
  execFileSync(venvPython(), ["-m", "pip", "install", "-q", "-r", REQUIREMENTS], {
    cwd: ROOT,
    stdio: ["pipe", "pipe", "inherit"],
    timeout: 120000,
  });

  return venvPython();
}

// ---------------------------------------------------------------------------
// Status check — TCP ping to Remote Script
// ---------------------------------------------------------------------------

function checkStatus() {
  return new Promise((resolve) => {
    const sock = new net.Socket();
    const PORT = parseInt(process.env.LIVE_MCP_PORT || "9878", 10);
    const HOST = process.env.LIVE_MCP_HOST || "127.0.0.1";

    sock.setTimeout(3000);

    sock.on("connect", () => {
      const ping = JSON.stringify({ id: "ping", type: "ping" }) + "\n";
      sock.write(ping);
    });

    let buf = "";
    sock.on("data", (chunk) => {
      buf += chunk.toString();
      if (buf.includes("\n")) {
        try {
          const resp = JSON.parse(buf.split("\n")[0]);
          if (resp.ok === true && resp.result && resp.result.pong) {
            console.log("  Ableton Live: connected on %s:%d", HOST, PORT);
          } else {
            console.log("  Ableton Live: unexpected response:", JSON.stringify(resp));
          }
        } catch {
          console.log("  Ableton Live: invalid response");
        }
        sock.destroy();
        resolve(true);
      }
    });

    sock.on("timeout", () => {
      console.log("  Ableton Live: connection timed out");
      sock.destroy();
      resolve(false);
    });

    sock.on("error", (err) => {
      if (err.code === "ECONNREFUSED") {
        console.log("  Ableton Live: not running (connection refused on %s:%d)", HOST, PORT);
      } else {
        console.log("  Ableton Live: %s", err.message);
      }
      resolve(false);
    });

    sock.connect(PORT, HOST);
  });
}

// ---------------------------------------------------------------------------
// Doctor — comprehensive diagnostic
// ---------------------------------------------------------------------------

async function doctor() {
  console.log("LivePilot Doctor v%s", PKG.version);
  console.log("─".repeat(50));

  let ok = true;

  // 1. Python
  const pyInfo = findPython();
  if (pyInfo) {
    console.log("  Python: %s (%s)", pyInfo.version, pyInfo.cmd);
  } else {
    console.log("  Python: NOT FOUND (need >= 3.9)");
    console.log("    Fix: install Python 3.9+ and add to PATH");
    ok = false;
  }

  // 2. Virtual environment
  const venvPy = venvPython();
  if (fs.existsSync(venvPy)) {
    console.log("  Venv: %s", VENV_DIR);
  } else {
    console.log("  Venv: NOT CREATED (run 'npx livepilot' to bootstrap)");
    console.log("    Fix: run 'npx livepilot' once to auto-create the virtual environment");
    ok = false;
  }

  // 3. fastmcp import
  if (fs.existsSync(venvPy)) {
    try {
      const ver = execFileSync(venvPy, ["-c", "import fastmcp; print(fastmcp.__version__)"], {
        encoding: "utf-8",
        timeout: 10000,
        stdio: "pipe",
      }).trim();
      console.log("  fastmcp: v%s", ver);
    } catch {
      console.log("  fastmcp: NOT INSTALLED in venv");
      console.log("    Fix: run 'npx livepilot' to auto-install dependencies");
      ok = false;
    }
  }

  // 4. MCP server module
  const serverInit = path.join(ROOT, "mcp_server", "__init__.py");
  if (fs.existsSync(serverInit)) {
    console.log("  MCP server: found at %s", path.join(ROOT, "mcp_server"));
  } else {
    console.log("  MCP server: MISSING (mcp_server/ directory not found)");
    ok = false;
  }

  // 5. Remote Script
  const remoteInit = path.join(ROOT, "remote_script", "LivePilot", "__init__.py");
  if (fs.existsSync(remoteInit)) {
    console.log("  Remote Script: found at %s", path.join(ROOT, "remote_script", "LivePilot"));
  } else {
    console.log("  Remote Script: MISSING");
    ok = false;
  }

  // 6. Remote Script installed in Ableton?
  try {
    const { findAbletonPaths } = require(path.join(ROOT, "installer", "paths.js"));
    const candidates = findAbletonPaths();
    let installed = false;
    for (const c of candidates) {
      const dest = path.join(c.path, "LivePilot", "__init__.py");
      if (fs.existsSync(dest)) {
        console.log("  Ableton install: %s", path.join(c.path, "LivePilot"));
        installed = true;
        break;
      }
    }
    if (!installed) {
      console.log("  Ableton install: NOT INSTALLED");
      console.log("    Fix: run 'npx livepilot --install' to copy Remote Script");
      ok = false;
    }
  } catch {
    console.log("  Ableton install: could not check (installer module error)");
  }

  // 7. Environment overrides
  if (process.env.LIVE_MCP_HOST || process.env.LIVE_MCP_PORT) {
    console.log("  Env overrides: HOST=%s PORT=%s",
      process.env.LIVE_MCP_HOST || "(default 127.0.0.1)",
      process.env.LIVE_MCP_PORT || "(default 9878)");
  }

  // 8. TCP connection to Ableton
  console.log("");
  console.log("Connection test:");
  const connected = await checkStatus();
  if (!connected) {
    ok = false;
  }

  // Summary
  console.log("");
  console.log("─".repeat(50));
  if (ok) {
    console.log("All checks passed.");
  } else {
    console.log("Some checks failed — see Fix suggestions above.");
  }
  return ok;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = process.argv.slice(2);
  const flag = args[0] || "";

  // --version / -v
  if (flag === "--version" || flag === "-v") {
    console.log("livepilot v%s", PKG.version);
    return;
  }

  // --help / -h
  if (flag === "--help" || flag === "-h") {
    console.log("livepilot v%s — agentic production system for Ableton Live 12", PKG.version);
    console.log("");
    console.log("Usage: npx livepilot [command]");
    console.log("");
    console.log("Commands:");
    console.log("  (none)        Start the MCP server");
    console.log("  --install     Install Remote Script into Ableton Live");
    console.log("  --uninstall   Remove Remote Script from Ableton Live");
    console.log("  --status      Check if Ableton Live is reachable");
    console.log("  --doctor      Run diagnostics (Python, deps, connection)");
    console.log("  --version     Show version");
    console.log("  --help        Show this help");
    console.log("");
    console.log("Environment:");
    console.log("  LIVE_MCP_HOST   Remote Script host (default: 127.0.0.1)");
    console.log("  LIVE_MCP_PORT   Remote Script port (default: 9878)");
    return;
  }

  // --install
  if (flag === "--install") {
    const { install } = require(path.join(ROOT, "installer", "install.js"));
    install();
    return;
  }

  // --uninstall
  if (flag === "--uninstall") {
    const { uninstall } = require(path.join(ROOT, "installer", "install.js"));
    uninstall();
    return;
  }

  // --status
  if (flag === "--status") {
    const reachable = await checkStatus();
    process.exit(reachable ? 0 : 1);
  }

  // --doctor
  if (flag === "--doctor") {
    const passed = await doctor();
    process.exit(passed ? 0 : 1);
  }

  // Default: start MCP server
  const pyInfo = findPython();
  if (!pyInfo) {
    console.error("Error: Python >= 3.9 is required but was not found.");
    console.error("");
    console.error("Install Python 3.9+ and ensure 'python3' or 'python' is on your PATH.");
    console.error("  macOS:   brew install python@3.12");
    console.error("  Ubuntu:  sudo apt install python3");
    console.error("  Windows: https://www.python.org/downloads/");
    process.exit(1);
  }

  // Bootstrap venv and install deps automatically
  let pythonBin;
  try {
    pythonBin = ensureVenv(pyInfo.cmd, pyInfo.prefixArgs);
  } catch (err) {
    console.error("Error: failed to set up Python environment.");
    console.error("  %s", err.message);
    if (err.stderr) {
      console.error("");
      console.error("pip output:");
      console.error("  %s", err.stderr.toString().trim());
    }
    if (err.stdout) {
      console.error("  %s", err.stdout.toString().trim());
    }
    console.error("");
    console.error("You can try manually:");
    console.error("  cd %s", ROOT);
    console.error("  %s -m venv .venv", pyInfo.cmd);
    console.error("  .venv/bin/pip install -r requirements.txt");
    process.exit(1);
  }

  const child = spawn(pythonBin, ["-m", "mcp_server"], {
    cwd: ROOT,
    stdio: "inherit",
  });

  child.on("error", (err) => {
    console.error("Failed to start MCP server: %s", err.message);
    process.exit(1);
  });

  child.on("exit", (code) => {
    process.exit(code || 0);
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
