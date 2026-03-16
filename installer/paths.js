"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

/**
 * Return an array of {path, description} for candidate Ableton Remote Scripts
 * directories on the current platform.
 */
function findAbletonPaths() {
  const candidates = [];
  const home = os.homedir();
  const platform = os.platform();

  if (platform === "darwin") {
    // macOS candidate 1: User Library default
    candidates.push({
      path: path.join(home, "Music", "Ableton", "User Library", "Remote Scripts"),
      description: "Ableton User Library (default)",
    });

    // macOS candidate 2: Preferences — scan for Live 12.* dirs
    const prefsDir = path.join(home, "Library", "Preferences", "Ableton");
    if (fs.existsSync(prefsDir)) {
      try {
        const entries = fs.readdirSync(prefsDir);
        for (const entry of entries) {
          if (entry.startsWith("Live 12")) {
            candidates.push({
              path: path.join(prefsDir, entry, "User Remote Scripts"),
              description: `Ableton Preferences (${entry})`,
            });
          }
        }
      } catch {
        // permission error — skip
      }
    }
  } else if (platform === "win32") {
    const userProfile = process.env.USERPROFILE || home;
    const appData = process.env.APPDATA || path.join(userProfile, "AppData", "Roaming");

    // Windows candidate 1: Documents User Library
    candidates.push({
      path: path.join(userProfile, "Documents", "Ableton", "User Library", "Remote Scripts"),
      description: "Ableton User Library (default)",
    });

    // Windows candidate 2: AppData — scan for Live 12.* dirs
    const abletonAppData = path.join(appData, "Ableton");
    if (fs.existsSync(abletonAppData)) {
      try {
        const entries = fs.readdirSync(abletonAppData);
        for (const entry of entries) {
          if (entry.startsWith("Live 12")) {
            candidates.push({
              path: path.join(abletonAppData, entry, "Preferences", "User Remote Scripts"),
              description: `Ableton AppData (${entry})`,
            });
          }
        }
      } catch {
        // permission error — skip
      }
    }
  }

  // Filter: keep candidate if the path itself exists, or its parent exists
  return candidates.filter((c) => {
    try {
      return fs.existsSync(c.path) || fs.existsSync(path.dirname(c.path));
    } catch {
      return false;
    }
  });
}

module.exports = { findAbletonPaths };
