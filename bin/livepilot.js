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

function findOtherLiveClient(host, port) {
  try {
    const out = execFileSync("lsof", ["-nP", `-iTCP:${port}`], {
      encoding: "utf-8",
      timeout: 3000,
      stdio: ["pipe", "pipe", "ignore"],
    });
    const target = `->${host}:${port}`;
    const lines = out.trim().split("\n").slice(1);
    for (const line of lines) {
      if (!line.includes(target) || !line.includes("(ESTABLISHED)")) {
        continue;
      }
      const parts = line.trim().split(/\s+/);
      const pid = parseInt(parts[1], 10);
      if (!Number.isNaN(pid) && pid !== process.pid) {
        return `PID ${pid} (${parts[0]})`;
      }
    }
  } catch {
    // best-effort only
  }
  return null;
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
      execFileSync(venvPy, ["-c", "import fastmcp; import midiutil; import pretty_midi; import numpy; import pyloudnorm; import soundfile; import scipy; import mutagen"], {
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
        let ok = false;
        try {
          const resp = JSON.parse(buf.split("\n")[0]);
          if (resp.ok === true && resp.result && resp.result.pong) {
            console.log("  Ableton Live: connected on %s:%d", HOST, PORT);
            ok = true;
          } else if (resp.ok === false && resp.error && resp.error.code === "STATE_ERROR") {
            // Ableton IS reachable — it just has another client connected.
            // Report as reachable (exit 0) so --status and --doctor don't
            // falsely report failure in a healthy single-client deployment.
            console.log(
              "  Ableton Live: reachable on %s:%d (another LivePilot client is connected)", HOST, PORT
            );
            if (resp.error.message) {
              console.log("    Detail: %s", resp.error.message);
            }
            ok = true;
          } else {
            console.log("  Ableton Live: unexpected response:", JSON.stringify(resp));
          }
        } catch {
          console.log("  Ableton Live: invalid response");
        }
        sock.destroy();
        resolve(ok);
      }
    });

    sock.on("timeout", () => {
      const otherClient = findOtherLiveClient(HOST, PORT);
      if (otherClient) {
        // Ableton IS reachable — it just didn't reply to ping because
        // another client holds the session. Resolve true (reachable).
        console.log(
          "  Ableton Live: reachable on %s:%d (another client connected: %s)",
          HOST, PORT, otherClient
        );
        sock.destroy();
        resolve(true);
      } else {
        console.log("  Ableton Live: connection timed out on %s:%d", HOST, PORT);
        sock.destroy();
        resolve(false);
      }
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

function probeAnalyzer(venvPy) {
  const probeCode = `
import asyncio
import json
import sys
from types import SimpleNamespace

sys.path.insert(0, ${JSON.stringify(ROOT)})

from mcp_server.server import lifespan, _master_has_livepilot_analyzer
from mcp_server.runtime.capability_probe import probe_capabilities

async def main():
    async with lifespan(None) as ctx:
        loaded = _master_has_livepilot_analyzer(ctx["ableton"])
        report = probe_capabilities(
            ableton=ctx["ableton"],
            ctx=SimpleNamespace(lifespan_context=ctx),
        )
        print(json.dumps({
            "loaded_on_master": loaded,
            "m4l_bridge": report["m4l_bridge"],
            "tier": report["tier"]["active"],
        }))

asyncio.run(main())
`;

  const out = execFileSync(venvPy, ["-c", probeCode], {
    cwd: ROOT,
    encoding: "utf-8",
    timeout: 15000,
    stdio: ["pipe", "pipe", "pipe"],
  }).trim();

  const lines = out.split(/\r?\n/).filter(Boolean);
  return JSON.parse(lines[lines.length - 1]);
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

  // 9. Analyzer / bridge capability
  if (connected && fs.existsSync(venvPy)) {
    const HOST = process.env.LIVE_MCP_HOST || "127.0.0.1";
    const PORT = parseInt(process.env.LIVE_MCP_PORT || "9878", 10);
    const otherClient = findOtherLiveClient(HOST, PORT);

    if (otherClient) {
      console.log("  Analyzer: skipped (another LivePilot client is connected: %s)", otherClient);
    } else {
      try {
        const analyzer = probeAnalyzer(venvPy);
        if (analyzer.loaded_on_master) {
          console.log(
            "  Analyzer: %s",
            analyzer.m4l_bridge.status === "ok"
              ? "loaded on master and bridge is active"
              : `loaded on master but bridge unavailable (${analyzer.m4l_bridge.detail})`,
          );
          if (analyzer.m4l_bridge.status !== "ok") {
            ok = false;
          }
        } else {
          console.log("  Analyzer: not detected on master track (optional)");
        }
      } catch (err) {
        console.log("  Analyzer: could not probe (%s)", err.message || String(err));
        ok = false;
      }
    }
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
// FluCoMa installer
// ---------------------------------------------------------------------------

/**
 * Detect whether Max (major version) is installed on the system. Returns the
 * highest installed major version number, or 0 if Max is not installed.
 *
 * macOS: checks /Applications/Max.app/Contents/Info.plist for CFBundleShortVersionString.
 * Windows: checks standard install locations under Program Files.
 */
function detectMaxMajorVersion() {
  try {
    if (process.platform === "darwin") {
      const infoPlist = "/Applications/Max.app/Contents/Info.plist";
      if (!fs.existsSync(infoPlist)) return 0;
      const out = execFileSync("defaults", ["read", infoPlist, "CFBundleShortVersionString"], {
        encoding: "utf-8",
        timeout: 3000,
      }).trim();
      const m = out.match(/^(\d+)/);
      return m ? parseInt(m[1], 10) : 0;
    }
    if (process.platform === "win32") {
      const candidates = [
        "C:\\Program Files\\Cycling '74\\Max 9",
        "C:\\Program Files\\Cycling '74\\Max 8",
      ];
      for (const candidate of candidates) {
        if (fs.existsSync(candidate)) {
          const m = candidate.match(/Max (\d+)/);
          if (m) return parseInt(m[1], 10);
        }
      }
      return 0;
    }
  } catch {
    return 0;
  }
  return 0;
}

async function setupFlucoma() {
  const os = require("os");
  const https = require("https");

  const home = os.homedir();

  // Max 9 is the current release (the Ableton Live 12.3+ default); Max 8 is
  // the legacy path. Select based on which major Max is actually installed —
  // NOT on whether the Packages directory exists. A fresh Max 9 install often
  // has no Packages folder yet, so the old fs.existsSync() check silently
  // steered fresh Max 9 machines onto the Max 8 legacy path.
  const docsBase = process.platform === "darwin"
    ? path.join(home, "Documents")
    : path.join(process.env.USERPROFILE || home, "Documents");

  const max9PackagesDir = path.join(docsBase, "Max 9", "Packages");
  const max8PackagesDir = path.join(docsBase, "Max 8", "Packages");

  const maxMajor = detectMaxMajorVersion();
  let packagesDir;
  if (maxMajor >= 9) {
    packagesDir = max9PackagesDir;
  } else if (maxMajor === 8) {
    packagesDir = max8PackagesDir;
  } else {
    // Max not detected — fall back to whichever Packages dir already exists,
    // preferring Max 9. If neither exists, default to Max 9 (future-proof).
    if (fs.existsSync(max9PackagesDir)) {
      packagesDir = max9PackagesDir;
    } else if (fs.existsSync(max8PackagesDir)) {
      packagesDir = max8PackagesDir;
    } else {
      console.log("Could not detect Max installation. Defaulting to Max 9 Packages path.");
      packagesDir = max9PackagesDir;
    }
  }
  const flucomaDir = path.join(packagesDir, "FluidCorpusManipulation");

  // Check BOTH locations for an existing install — a user may have Max 8
  // FluCoMa from a prior install that still works
  const altFlucomaDir = path.join(
    packagesDir === max9PackagesDir ? max8PackagesDir : max9PackagesDir,
    "FluidCorpusManipulation"
  );

  for (const candidateDir of [flucomaDir, altFlucomaDir]) {
    if (!fs.existsSync(candidateDir)) continue;
    const pkgInfo = path.join(candidateDir, "package-info.json");
    if (fs.existsSync(pkgInfo)) {
      try {
        const info = JSON.parse(fs.readFileSync(pkgInfo, "utf-8"));
        console.log("FluCoMa already installed: v%s", info.version || "unknown");
        console.log("Location: %s", candidateDir);
        return;
      } catch {}
    }
    console.log("FluCoMa already installed at %s", candidateDir);
    return;
  }

  // Ensure the parent Packages directory exists for the install target — Max
  // lazily creates Packages/ on first package install, so it may be absent on
  // a fresh Max 9 system.
  fs.mkdirSync(packagesDir, { recursive: true });

  console.log("FluCoMa not found. Downloading from GitHub...");
  const crypto = require("crypto");

  // Pin to a known release tag for reproducibility and security.
  //
  // IMPORTANT: FluCoMa 1.0.7 ships as a single universal zip that contains
  // both the macOS externals (.mxo) and the Windows externals (.mxe64).
  // There is ONE hash to pin, not two. If a future release reverts to
  // per-platform zips, convert FLUCOMA_SHA256 back to a {Mac, Windows}
  // dict and restore the platform-specific asset finder.
  //
  // To re-pin after a version bump:
  //   curl -L -o flucoma.zip <release-zip-url>
  //   shasum -a 256 flucoma.zip      # macOS
  //   CertUtil -hashfile flucoma.zip SHA256   # Windows
  // then paste the 64-char hex digest into FLUCOMA_SHA256 below.
  const FLUCOMA_TAG = "1.0.7";
  const FLUCOMA_SHA256 = "1a5cb7340e8816a9983b981a5a84ddb95b63e6d71446f278b9dc81c3cc1206a2";
  const FLUCOMA_URL = `https://api.github.com/repos/flucoma/flucoma-max/releases/tags/${FLUCOMA_TAG}`;

  // Fetch pinned release info
  const releaseInfo = await new Promise((resolve, reject) => {
    https.get(FLUCOMA_URL, {
      headers: { "User-Agent": "LivePilot" }
    }, (res) => {
      if (res.statusCode === 302 || res.statusCode === 301) {
        https.get(res.headers.location, {
          headers: { "User-Agent": "LivePilot" }
        }, (res2) => {
          let data = "";
          res2.on("data", (c) => data += c);
          res2.on("end", () => resolve(JSON.parse(data)));
        }).on("error", reject);
        return;
      }
      let data = "";
      res.on("data", (c) => data += c);
      res.on("end", () => resolve(JSON.parse(data)));
    }).on("error", reject);
  });

  // FluCoMa 1.0.7 publishes a single universal zip — pick the first .zip
  // asset on the release page. If upstream starts shipping per-platform
  // zips again, reintroduce the filename filter here.
  const platform = process.platform === "darwin" ? "macOS" : "Windows";
  const zipAsset = (releaseInfo.assets || []).find(a => a.name.endsWith(".zip"));
  if (!zipAsset) {
    console.error("Error: no .zip asset found in FluCoMa release %s", FLUCOMA_TAG);
    process.exit(1);
  }
  console.log("Target platform: %s (zip contains externals for both)", platform);

  console.log("Downloading %s (v%s, %sMB)...", zipAsset.name, FLUCOMA_TAG,
    Math.round(zipAsset.size / 1024 / 1024));

  // Download to temp
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "flucoma-"));
  const zipPath = path.join(tmpDir, zipAsset.name);

  await new Promise((resolve, reject) => {
    const downloadUrl = zipAsset.browser_download_url;
    const download = (url, depth) => {
      if (depth > 5) { reject(new Error("Too many redirects")); return; }
      if (!url.startsWith("https://")) { reject(new Error("Refusing non-HTTPS redirect")); return; }
      https.get(url, { headers: { "User-Agent": "LivePilot" } }, (res) => {
        if (res.statusCode === 302 || res.statusCode === 301) {
          download(res.headers.location, depth + 1);
          return;
        }
        const file = fs.createWriteStream(zipPath);
        res.pipe(file);
        file.on("finish", () => { file.close(); resolve(); });
      }).on("error", reject);
    };
    download(downloadUrl, 0);
  });

  // Verify download integrity via SHA256
  const hash = crypto.createHash("sha256");
  hash.update(fs.readFileSync(zipPath));
  const sha256 = hash.digest("hex");
  const expectedHash = FLUCOMA_SHA256;
  console.log("SHA256: %s", sha256);

  const isPinned = expectedHash && expectedHash !== "UNPINNED"
    && /^[0-9a-f]{64}$/i.test(expectedHash);

  if (isPinned) {
    if (sha256.toLowerCase() !== expectedHash.toLowerCase()) {
      console.error("");
      console.error("  SHA256 MISMATCH — refusing to install.");
      console.error("  expected: %s", expectedHash);
      console.error("  actual:   %s", sha256);
      console.error("");
      console.error("  The downloaded file does not match the pinned hash.");
      console.error("  Either the release changed upstream, or the download was tampered with.");
      console.error("  Verify at https://github.com/flucoma/flucoma-max/releases/tag/%s", FLUCOMA_TAG);
      console.error("");
      try { fs.rmSync(tmpDir, { recursive: true }); } catch {}
      process.exit(1);
    }
    console.log("Checksum verified ✓");
  } else {
    // Hash is not yet pinned. Require an explicit opt-in so unverified
    // installs are never silent — the previous "ACCEPT_FIRST_RUN" sentinel
    // auto-accepted every run.
    const allowUnverified = process.env.LIVEPILOT_ALLOW_UNVERIFIED_FLUCOMA === "1";
    if (!allowUnverified) {
      console.error("");
      console.error("  FluCoMa SHA256 is not pinned.");
      console.error("  Downloaded hash: %s", sha256);
      console.error("");
      console.error("  Refusing to install an unverified binary by default.");
      console.error("  To proceed (and help pin the hash), re-run with:");
      console.error("    LIVEPILOT_ALLOW_UNVERIFIED_FLUCOMA=1 npx livepilot --setup-flucoma");
      console.error("");
      console.error("  Then open a PR that sets FLUCOMA_SHA256 in bin/livepilot.js to:");
      console.error("    '%s'", sha256);
      console.error("");
      try { fs.rmSync(tmpDir, { recursive: true }); } catch {}
      process.exit(1);
    }
    console.warn("⚠ Installing unverified FluCoMa — LIVEPILOT_ALLOW_UNVERIFIED_FLUCOMA=1 was set.");
    console.warn("  Record this SHA256 in FLUCOMA_SHA256:");
    console.warn("    '%s'", sha256);
  }

  console.log("Extracting to %s...", packagesDir);
  fs.mkdirSync(packagesDir, { recursive: true });

  if (process.platform === "win32") {
    // Escape single quotes for PowerShell: ' → ''
    const psZip = zipPath.replace(/'/g, "''");
    const psDest = packagesDir.replace(/'/g, "''");
    execFileSync("powershell", [
      "-Command",
      `Expand-Archive -Path '${psZip}' -DestinationPath '${psDest}' -Force`
    ], { stdio: "inherit", timeout: 120000 });
  } else {
    execFileSync("unzip", ["-o", "-q", zipPath, "-d", packagesDir], {
      stdio: "inherit",
      timeout: 120000,
    });
  }

  // macOS: strip quarantine on FluCoMa externals only (not on arbitrary paths)
  if (process.platform === "darwin" && fs.existsSync(flucomaDir)) {
    console.log("Removing macOS quarantine from FluCoMa externals...");
    try {
      execFileSync("xattr", ["-d", "-r", "com.apple.quarantine", flucomaDir], {
        stdio: "pipe",
        timeout: 30000,
      });
    } catch {
      // xattr may fail if no quarantine attribute — that's fine
    }
  }

  // Clean up temp
  try { fs.rmSync(tmpDir, { recursive: true }); } catch {}

  if (fs.existsSync(flucomaDir)) {
    console.log("");
    console.log("FluCoMa v%s installed successfully!", FLUCOMA_TAG);
    console.log("Restart Ableton Live for real-time DSP tools.");
  } else {
    console.error("Error: FluCoMa directory not found after extraction.");
    console.error("The zip may have a different structure. Check %s manually.", packagesDir);
    process.exit(1);
  }
}

// ---------------------------------------------------------------------------
// Setup wizard — unified installer
// ---------------------------------------------------------------------------

async function setup() {
  console.log("LivePilot Setup Wizard v%s", PKG.version);
  console.log("═".repeat(50));
  console.log("");

  let ok = true;

  // 1. Python
  console.log("Step 1/5: Checking Python...");
  const pyInfo = findPython();
  if (pyInfo) {
    console.log("  ✓ %s", pyInfo.version);
  } else {
    console.log("  ✗ Python >= 3.9 not found");
    console.log("    Install: brew install python@3.12 (macOS) or python.org (Windows)");
    ok = false;
  }

  // 2. Install Remote Script
  console.log("");
  console.log("Step 2/5: Installing Remote Script...");
  try {
    const { install, InstallerAbort } = require(path.join(ROOT, "installer", "install.js"));
    try {
      install();
      console.log("  ✓ Remote Script installed");
    } catch (err) {
      if (err instanceof InstallerAbort && err.recoverable) {
        // Recoverable — don't bail the wizard. The user can rerun
        // --install manually, and later steps (Python env, M4L Analyzer,
        // diagnostics) may still succeed or at least inform them.
        console.log("  ⚠ Skipped: %s", err.message.split("\n")[0]);
        console.log("    (Continuing with remaining setup steps.)");
        ok = false;
      } else {
        throw err;
      }
    }
  } catch (err) {
    console.log("  ✗ Failed: %s", err.message);
    ok = false;
  }

  // 3. Bootstrap Python venv
  console.log("");
  console.log("Step 3/5: Setting up Python environment...");
  if (pyInfo) {
    try {
      ensureVenv(pyInfo.cmd, pyInfo.prefixArgs);
      console.log("  ✓ Virtual environment ready");
    } catch (err) {
      console.log("  ✗ Failed: %s", err.message);
      ok = false;
    }
  } else {
    console.log("  ⊘ Skipped (no Python)");
  }

  // 4. Copy M4L Analyzer to User Library
  console.log("");
  console.log("Step 4/5: Installing M4L Analyzer...");
  const analyzerSrc = path.join(ROOT, "m4l_device", "LivePilot_Analyzer.amxd");
  if (fs.existsSync(analyzerSrc)) {
    const home = require("os").homedir();
    let dest;
    if (process.platform === "darwin") {
      dest = path.join(home, "Music", "Ableton", "User Library", "Presets",
                        "Audio Effects", "Max Audio Effect");
    } else {
      dest = path.join(home, "Documents", "Ableton", "User Library", "Presets",
                        "Audio Effects", "Max Audio Effect");
    }
    try {
      fs.mkdirSync(dest, { recursive: true });
      fs.copyFileSync(analyzerSrc, path.join(dest, "LivePilot_Analyzer.amxd"));
      console.log("  ✓ Analyzer copied to %s", dest);
    } catch (err) {
      console.log("  ✗ Failed: %s", err.message);
    }
  } else {
    console.log("  ⊘ Analyzer not found in package (optional)");
  }

  // 5. Connection test
  console.log("");
  console.log("Step 5/5: Testing Ableton connection...");
  const reachable = await checkStatus();
  if (reachable) {
    console.log("  ✓ Ableton Live is running and reachable");
  } else {
    console.log("  ⊘ Ableton not running (start it and select LivePilot as Control Surface)");
  }

  // Summary
  console.log("");
  console.log("═".repeat(50));
  if (ok) {
    console.log("✓ Setup complete! Next steps:");
    console.log("");
    console.log("  1. Open Ableton Live 12");
    console.log("  2. Go to Preferences → Link, Tempo & MIDI");
    console.log("  3. Set Control Surface to 'LivePilot'");
    console.log("  4. Start making music with AI!");
    console.log("");
    console.log("  Codex App:      npx livepilot --install-codex-plugin");
    console.log("  Claude Code:    claude mcp add LivePilot -- npx livepilot");
    console.log("  Claude Desktop: Already configured if using Desktop Extension");
  } else {
    console.log("⚠ Setup completed with issues. Run 'npx livepilot --doctor' for details.");
  }
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
    console.log("  --setup       Full setup wizard (install + configure + test)");
    console.log("  --install     Install Remote Script into Ableton Live");
    console.log("  --uninstall   Remove Remote Script from Ableton Live");
    console.log("  --install-codex-plugin   Install the bundled Codex plugin locally");
    console.log("  --uninstall-codex-plugin Remove the locally installed Codex plugin");
    console.log("  --status      Check if Ableton Live is reachable");
    console.log("  --doctor      Run diagnostics (Python, deps, connection)");
    console.log("  --version     Show version");
    console.log("  --setup-flucoma  Install FluCoMa package for real-time DSP");
    console.log("  --help        Show this help");
    console.log("");
    console.log("Environment:");
    console.log("  LIVE_MCP_HOST   Remote Script host (default: 127.0.0.1)");
    console.log("  LIVE_MCP_PORT   Remote Script port (default: 9878)");
    return;
  }

  // --install
  if (flag === "--install") {
    const { install, InstallerAbort } = require(path.join(ROOT, "installer", "install.js"));
    try {
      install();
    } catch (err) {
      if (err instanceof InstallerAbort) {
        console.error(err.message);
        process.exit(err.recoverable ? 2 : 1);
      }
      throw err;
    }
    return;
  }

  // --uninstall
  if (flag === "--uninstall") {
    const { uninstall } = require(path.join(ROOT, "installer", "install.js"));
    uninstall();
    return;
  }

  // --install-codex-plugin
  if (flag === "--install-codex-plugin") {
    const { installCodexPlugin } = require(path.join(ROOT, "installer", "codex.js"));
    installCodexPlugin();
    return;
  }

  // --uninstall-codex-plugin
  if (flag === "--uninstall-codex-plugin") {
    const { uninstallCodexPlugin } = require(path.join(ROOT, "installer", "codex.js"));
    uninstallCodexPlugin();
    return;
  }

  // --status
  if (flag === "--status") {
    const reachable = await checkStatus();
    process.exit(reachable ? 0 : 1);
  }

  // --setup-flucoma
  if (flag === "--setup-flucoma") {
    await setupFlucoma();
    return;
  }

  // --doctor
  if (flag === "--doctor") {
    const passed = await doctor();
    process.exit(passed ? 0 : 1);
  }

  // --setup (unified installer wizard)
  if (flag === "--setup") {
    await setup();
    return;
  }

  // Auto-install Remote Script when launched from Desktop Extension
  if (process.env.LIVEPILOT_AUTO_INSTALL === "true") {
    try {
      const { install } = require(path.join(ROOT, "installer", "install.js"));
      const { findAbletonPaths } = require(path.join(ROOT, "installer", "paths.js"));
      const candidates = findAbletonPaths();
      if (candidates.length > 0) {
        // Check if already installed
        const target = path.join(candidates[0].path, "LivePilot");
        if (!fs.existsSync(target)) {
          console.error("LivePilot: auto-installing Remote Script to %s", candidates[0].path);
          install();
          console.error("LivePilot: Remote Script installed. Select 'LivePilot' in Ableton > Preferences > Link, Tempo & MIDI > Control Surface.");
        }
      }
    } catch (err) {
      console.error("LivePilot: auto-install skipped (%s)", err.message);
    }
  }

  // Custom TCP port from Desktop Extension config
  if (process.env.LIVEPILOT_TCP_PORT && process.env.LIVEPILOT_TCP_PORT !== "9878") {
    process.env.LIVE_MCP_PORT = process.env.LIVEPILOT_TCP_PORT;
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
