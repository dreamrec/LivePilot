"use strict";

const fs = require("fs");
const path = require("path");
const { findAbletonPaths } = require("./paths");

const ROOT = path.resolve(__dirname, "..");
const SOURCE_DIR = path.join(ROOT, "remote_script", "LivePilot");

// Files / dirs to skip during copy
const SKIP = new Set(["__pycache__", ".DS_Store"]);

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
 * Install the LivePilot Remote Script into Ableton's Remote Scripts folder.
 */
function install() {
  const candidates = findAbletonPaths();

  if (candidates.length === 0) {
    console.log("Could not auto-detect an Ableton Live Remote Scripts directory.");
    console.log("");
    console.log("Manual install:");
    console.log("  1. Open Ableton Live > Preferences > File/Folder");
    console.log("  2. Find the User Remote Scripts folder path");
    console.log("  3. Copy the 'remote_script/LivePilot' folder into that directory");
    console.log("  4. Restart Ableton Live");
    console.log("  5. In Preferences > Link/Tempo/MIDI, set a Control Surface to 'LivePilot'");
    process.exit(1);
  }

  // Use the first valid candidate
  const target = candidates[0];
  const targetBase = target.path;
  const destDir = path.join(targetBase, "LivePilot");

  // Ensure target base exists
  fs.mkdirSync(targetBase, { recursive: true });

  console.log("Installing LivePilot Remote Script...");
  console.log("  Source: %s", SOURCE_DIR);
  console.log("  Target: %s", destDir);
  console.log("  Location: %s", target.description);
  console.log("");

  copyDirSync(SOURCE_DIR, destDir);

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

module.exports = { install, uninstall };
