"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { findAbletonPaths } = require("./paths");

const ROOT = path.resolve(__dirname, "..");
const SOURCE_DIR = path.join(ROOT, "remote_script", "LivePilot");

// Files / dirs to skip during copy
const SKIP = new Set(["__pycache__", ".DS_Store"]);

// How many previous backups to keep on disk before auto-pruning (the upgrade
// path renames the old LivePilot dir to LivePilot.backup-<ts>/ so the user can
// recover a manual edit).
const BACKUP_RETENTION = 3;

/**
 * Typed installer error. Wrappers (e.g. the --setup wizard) can catch this
 * and decide whether to continue with later steps (recoverable) or abort the
 * whole wizard (non-recoverable). The previous version called process.exit(1)
 * mid-function, which silently short-circuited the setup wizard — callers
 * had try/catch expecting exceptions, so later steps (bootstrap, M4L install,
 * diagnostics) were skipped without warning.
 */
class InstallerAbort extends Error {
  constructor(message, { recoverable = false } = {}) {
    super(message);
    this.name = "InstallerAbort";
    this.recoverable = recoverable;
  }
}

/**
 * Validate that a user-supplied install destination is somewhere safe.
 * Refuses to write outside of the user's home directory unless it matches
 * one of the known Ableton Remote Scripts paths. This closes the path-
 * traversal hole from `LIVEPILOT_INSTALL_PATH=/etc ...`.
 */
function _assertSafeInstallPath(resolvedPath, candidates) {
  const home = os.homedir();
  const allowedPrefixes = [
    home,
    // Systemwide Ableton install paths that live outside $HOME on some platforms
    "/Applications/Ableton",
    "C:\\ProgramData\\Ableton",
  ];
  // The detected Ableton candidate paths are always considered safe
  for (const c of candidates) {
    if (path.resolve(c.path).startsWith(path.resolve(resolvedPath))) {
      return;
    }
    if (path.resolve(resolvedPath).startsWith(path.resolve(c.path))) {
      return;
    }
  }
  const safe = allowedPrefixes.some((p) => resolvedPath.startsWith(path.resolve(p)));
  if (!safe) {
    throw new InstallerAbort(
      `LIVEPILOT_INSTALL_PATH=${resolvedPath} is outside permitted directories. ` +
      `Refusing to install. Allowed roots: ${allowedPrefixes.join(", ")}`,
      { recoverable: false }
    );
  }
}

/**
 * Recursively copy a directory, skipping __pycache__ and .DS_Store.
 */
function copyDirSync(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    if (SKIP.has(entry.name)) continue;
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDirSync(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

/**
 * Prune old LivePilot.backup-<ts>/ dirs, keeping the most recent N.
 */
function _pruneBackups(parentDir) {
  try {
    const entries = fs.readdirSync(parentDir, { withFileTypes: true });
    const backups = entries
      .filter((e) => e.isDirectory() && /^LivePilot\.backup-\d+$/.test(e.name))
      .map((e) => e.name)
      .sort();  // lexicographic — timestamps are monotonic, so this is age order
    while (backups.length > BACKUP_RETENTION) {
      const old = backups.shift();
      try {
        fs.rmSync(path.join(parentDir, old), { recursive: true, force: true });
      } catch {
        // best effort — don't let cleanup failure break an install
      }
    }
  } catch {
    // best effort
  }
}

/**
 * Install the LivePilot Remote Script into Ableton's Remote Scripts folder.
 *
 * Throws InstallerAbort on recoverable failures (auto-detect missing) or
 * non-recoverable ones (path-traversal attempt). Never calls process.exit.
 * This lets the setup wizard continue with later steps on a recoverable
 * failure.
 */
function install() {
  const candidates = findAbletonPaths();

  if (candidates.length === 0) {
    throw new InstallerAbort(
      "Could not auto-detect an Ableton Live Remote Scripts directory.\n\n" +
      "Manual install:\n" +
      "  1. Open Ableton Live > Preferences > File/Folder\n" +
      "  2. Find the User Remote Scripts folder path\n" +
      "  3. Copy the 'remote_script/LivePilot' folder into that directory\n" +
      "  4. Restart Ableton Live\n" +
      "  5. In Preferences > Link/Tempo/MIDI, set a Control Surface to 'LivePilot'",
      { recoverable: true }
    );
  }

  // If multiple candidates exist, let the user choose via --install-path
  // or LIVEPILOT_INSTALL_PATH env var. Otherwise use the first.
  let target;
  const explicitPath = process.env.LIVEPILOT_INSTALL_PATH;
  if (explicitPath) {
    const resolved = path.resolve(explicitPath);
    _assertSafeInstallPath(resolved, candidates);
    target = { path: resolved, description: "explicit (LIVEPILOT_INSTALL_PATH)" };
  } else if (candidates.length > 1) {
    console.log("Multiple Ableton Remote Scripts directories detected:");
    candidates.forEach((c, i) => {
      console.log("  [%d] %s", i + 1, c.description);
      console.log("      %s", c.path);
    });
    console.log("");
    console.log("Using [1] %s", candidates[0].description);
    console.log("To use a different location, set LIVEPILOT_INSTALL_PATH:");
    console.log("  LIVEPILOT_INSTALL_PATH='%s' npx livepilot --install", candidates[1].path);
    console.log("");
    target = candidates[0];
  } else {
    target = candidates[0];
  }
  const targetBase = target.path;
  const destDir = path.join(targetBase, "LivePilot");

  // Ensure target base exists
  fs.mkdirSync(targetBase, { recursive: true });

  // Clear-then-copy upgrade path. Overlay-copying on top of an existing
  // install leaves stale files when a module is removed/renamed upstream.
  // Instead, rename the previous install to a timestamped backup, copy
  // fresh, then prune old backups. The rename (not delete) preserves any
  // local edits the user may have made.
  if (fs.existsSync(destDir)) {
    const ts = new Date().toISOString().replace(/[-:T.Z]/g, "").slice(0, 14);
    const backup = path.join(targetBase, `LivePilot.backup-${ts}`);
    try {
      fs.renameSync(destDir, backup);
      console.log("Existing install backed up to: %s", backup);
    } catch (e) {
      throw new InstallerAbort(
        `Could not back up previous LivePilot install at ${destDir}: ${e.message}`,
        { recoverable: false }
      );
    }
  }

  console.log("Installing LivePilot Remote Script...");
  console.log("  Source: %s", SOURCE_DIR);
  console.log("  Target: %s", destDir);
  console.log("  Location: %s", target.description);
  console.log("");

  copyDirSync(SOURCE_DIR, destDir);
  _pruneBackups(targetBase);

  console.log("Done! Next steps:");
  console.log("  1. Restart Ableton Live (or press Cmd+, to open Preferences)");
  console.log("  2. Go to Link/Tempo/MIDI > Control Surface");
  console.log("  3. Select 'LivePilot' from the dropdown");
  console.log("  4. Run 'npx livepilot --status' to verify the connection");
}

/**
 * Remove the LivePilot Remote Script from all detected locations.
 */
function uninstall() {
  const candidates = findAbletonPaths();
  let removed = 0;

  for (const candidate of candidates) {
    const destDir = path.join(candidate.path, "LivePilot");
    if (fs.existsSync(destDir)) {
      console.log("Removing: %s", destDir);
      fs.rmSync(destDir, { recursive: true, force: true });
      removed++;
    }
  }

  if (removed === 0) {
    console.log("No LivePilot Remote Script installations found.");
  } else {
    console.log("Uninstalled %d location(s). Restart Ableton Live to complete.", removed);
  }
}

module.exports = { install, uninstall, InstallerAbort };
