#!/usr/bin/env node
"use strict";

const { execFileSync, spawn } = require("child_process");
const net = require("net");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const PKG = require(path.join(ROOT, "package.json"));

// ---------------------------------------------------------------------------
// Python detection
// ---------------------------------------------------------------------------

function findPython() {
  for (const cmd of ["python3", "python"]) {
    try {
      const out = execFileSync(cmd, ["--version"], {
        encoding: "utf-8",
        timeout: 5000,
      }).trim();
      // e.g. "Python 3.12.1"
      const match = out.match(/Python\s+(\d+)\.(\d+)/);
      if (match) {
        const major = parseInt(match[1], 10);
        const minor = parseInt(match[2], 10);
        if (major === 3 && minor >= 10) {
          return cmd;
        }
      }
    } catch {
      // command not found or failed — try next
    }
  }
  return null;
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
            console.log("LivePilot: connected to Ableton Live on %s:%d", HOST, PORT);
          } else {
            console.log("LivePilot: unexpected response from Ableton:", JSON.stringify(resp));
          }
        } catch {
          console.log("LivePilot: invalid response from Ableton");
        }
        sock.destroy();
        resolve();
      }
    });

    sock.on("timeout", () => {
      console.log("LivePilot: connection timed out — is Ableton Live running with LivePilot Remote Script?");
      sock.destroy();
      resolve();
    });

    sock.on("error", (err) => {
      if (err.code === "ECONNREFUSED") {
        console.log("LivePilot: connection refused on %s:%d — Ableton Live is not running or Remote Script is not loaded.", HOST, PORT);
      } else {
        console.log("LivePilot: connection error —", err.message);
      }
      resolve();
    });

    sock.connect(PORT, HOST);
  });
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
    await checkStatus();
    return;
  }

  // Default: start MCP server
  const python = findPython();
  if (!python) {
    console.error("Error: Python >= 3.10 is required but was not found.");
    console.error("Install Python 3.10+ and ensure 'python3' or 'python' is on your PATH.");
    process.exit(1);
  }

  const child = spawn(python, ["-m", "mcp_server"], {
    cwd: ROOT,
    stdio: "inherit",
  });

  child.on("error", (err) => {
    console.error("Failed to start MCP server:", err.message);
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
