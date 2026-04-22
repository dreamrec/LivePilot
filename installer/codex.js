"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SOURCE_DIR = path.join(ROOT, "livepilot");
const SOURCE_MANIFEST = path.join(SOURCE_DIR, ".Codex-plugin", "plugin.json");
const DEFAULT_PLUGIN_DIR = path.join(os.homedir(), "plugins", "livepilot");
const DEFAULT_MARKETPLACE_PATH = path.join(os.homedir(), ".agents", "plugins", "marketplace.json");

const SKIP = new Set(["__pycache__", ".DS_Store"]);

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

function targetPluginDir() {
  return process.env.LIVEPILOT_CODEX_PLUGIN_PATH || DEFAULT_PLUGIN_DIR;
}

function marketplacePath() {
  return process.env.LIVEPILOT_CODEX_MARKETPLACE_PATH || DEFAULT_MARKETPLACE_PATH;
}

function loadManifest() {
  if (!fs.existsSync(SOURCE_MANIFEST)) {
    throw new Error(`Codex plugin manifest not found at ${SOURCE_MANIFEST}`);
  }
  return JSON.parse(fs.readFileSync(SOURCE_MANIFEST, "utf-8"));
}

function writeLocalMcpConfig(destDir) {
  const file = path.join(destDir, ".mcp.json");
  const config = {
    mcpServers: {
      livepilot: {
        command: process.execPath,
        args: [path.join(ROOT, "bin", "livepilot.js")],
      },
    },
  };
  fs.writeFileSync(file, JSON.stringify(config, null, 2) + "\n");
}

function ensureMarketplace(pluginName) {
  const file = marketplacePath();
  let marketplace = {
    name: "local-plugins",
    interface: { displayName: "Local Plugins" },
    plugins: [],
  };

  if (fs.existsSync(file)) {
    const raw = JSON.parse(fs.readFileSync(file, "utf-8"));
    marketplace = {
      name: raw.name || marketplace.name,
      interface: raw.interface || marketplace.interface,
      plugins: Array.isArray(raw.plugins) ? raw.plugins : [],
    };
  }

  const entry = {
    name: pluginName,
    source: {
      source: "local",
      path: `./plugins/${pluginName}`,
    },
    policy: {
      installation: "AVAILABLE",
      authentication: "ON_INSTALL",
    },
    category: "Integration",
  };

  const idx = marketplace.plugins.findIndex((plugin) => plugin && plugin.name === pluginName);
  if (idx >= 0) {
    marketplace.plugins[idx] = entry;
  } else {
    marketplace.plugins.push(entry);
  }

  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(marketplace, null, 2) + "\n");
  return file;
}

function removeMarketplaceEntry(pluginName) {
  const file = marketplacePath();
  if (!fs.existsSync(file)) {
    return null;
  }

  const raw = JSON.parse(fs.readFileSync(file, "utf-8"));
  const marketplace = {
    name: raw.name || "local-plugins",
    interface: raw.interface || { displayName: "Local Plugins" },
    plugins: Array.isArray(raw.plugins) ? raw.plugins.filter((plugin) => plugin && plugin.name !== pluginName) : [],
  };
  fs.writeFileSync(file, JSON.stringify(marketplace, null, 2) + "\n");
  return file;
}

function installCodexPlugin() {
  const manifest = loadManifest();
  const pluginName = manifest.name || "livepilot";
  const destDir = targetPluginDir();
  const marketFile = ensureMarketplace(pluginName);

  console.log("Installing LivePilot Codex plugin...");
  console.log("  Source: %s", SOURCE_DIR);
  console.log("  Target: %s", destDir);
  console.log("  Marketplace: %s", marketFile);
  console.log("");

  fs.mkdirSync(path.dirname(destDir), { recursive: true });
  fs.rmSync(destDir, { recursive: true, force: true });
  copyDirSync(SOURCE_DIR, destDir);
  writeLocalMcpConfig(destDir);

  console.log("Done! Next steps:");
  console.log("  1. Open or refresh Codex");
  console.log("  2. Check that LivePilot appears in Local Plugins");
  console.log("  3. Start a new thread or reload tools if Codex was already open");
}

function uninstallCodexPlugin() {
  const manifest = loadManifest();
  const pluginName = manifest.name || "livepilot";
  const destDir = targetPluginDir();
  const marketFile = removeMarketplaceEntry(pluginName);

  if (fs.existsSync(destDir)) {
    console.log("Removing Codex plugin: %s", destDir);
    fs.rmSync(destDir, { recursive: true, force: true });
  } else {
    console.log("Codex plugin not found at %s", destDir);
  }

  if (marketFile) {
    console.log("Updated marketplace: %s", marketFile);
  }
  console.log("Restart or refresh Codex to remove the plugin from the UI.");
}

module.exports = {
  installCodexPlugin,
  uninstallCodexPlugin,
};
