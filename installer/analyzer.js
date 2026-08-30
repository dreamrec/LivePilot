"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const ANALYZER_FILES = ["LivePilot_Analyzer.amxd", "livepilot_bridge.js"];

function defaultAnalyzerDir() {
  const libraryRoot = process.platform === "darwin"
    ? path.join(os.homedir(), "Music", "Ableton", "User Library")
    : path.join(os.homedir(), "Documents", "Ableton", "User Library");
  return path.join(libraryRoot, "Presets", "Audio Effects", "Max Audio Effect");
}

function analyzerDir() {
  return process.env.LIVEPILOT_ANALYZER_DIR || defaultAnalyzerDir();
}

function filesEqual(source, destination) {
  if (!fs.existsSync(destination)) return false;
  const sourceStat = fs.statSync(source);
  const destinationStat = fs.statSync(destination);
  if (sourceStat.size !== destinationStat.size) return false;
  return fs.readFileSync(source).equals(fs.readFileSync(destination));
}

function installAnalyzer() {
  const destination = analyzerDir();
  fs.mkdirSync(destination, { recursive: true });

  const copied = [];
  for (const filename of ANALYZER_FILES) {
    const source = path.join(ROOT, "m4l_device", filename);
    if (!fs.existsSync(source)) {
      throw new Error(`Analyzer package is missing ${source}`);
    }
    const target = path.join(destination, filename);
    if (!filesEqual(source, target)) {
      fs.copyFileSync(source, target);
      copied.push(filename);
    }
  }

  return {
    destination,
    changed: copied.length > 0,
    copied,
    files: ANALYZER_FILES.slice(),
  };
}

module.exports = {
  ANALYZER_FILES,
  analyzerDir,
  defaultAnalyzerDir,
  installAnalyzer,
};
