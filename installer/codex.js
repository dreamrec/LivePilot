"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SOURCE_DIR = path.join(ROOT, "livepilot");
const SOURCE_MANIFESTS = [
  path.join(SOURCE_DIR, ".codex-plugin", "plugin.json"),
  path.join(SOURCE_DIR, ".Codex-plugin", "plugin.json"),
];
const DEFAULT_PLUGIN_DIR = path.join(os.homedir(), "plugins", "livepilot");
const DEFAULT_MARKETPLACE_PATH = path.join(os.homedir(), ".agents", "plugins", "marketplace.json");
const DEFAULT_CODEX_CACHE_ROOT = path.join(os.homedir(), ".codex", "plugins", "cache", "local-plugins");

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

function codexCacheRoot() {
  return process.env.LIVEPILOT_CODEX_CACHE_ROOT || DEFAULT_CODEX_CACHE_ROOT;
}

function targetCacheDir(pluginName, version) {
  if (process.env.LIVEPILOT_CODEX_CACHE_PATH) {
    return process.env.LIVEPILOT_CODEX_CACHE_PATH;
  }
  return path.join(codexCacheRoot(), pluginName, version);
}

function marketplacePath() {
  return process.env.LIVEPILOT_CODEX_MARKETPLACE_PATH || DEFAULT_MARKETPLACE_PATH;
}

function sourceManifestPath() {
  for (const candidate of SOURCE_MANIFESTS) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error(`Codex plugin manifest not found at ${SOURCE_MANIFESTS.join(" or ")}`);
}

function loadManifest() {
  return JSON.parse(fs.readFileSync(sourceManifestPath(), "utf-8"));
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

function ensureLowercaseCodexManifest(destDir) {
  const canonicalDir = path.join(destDir, ".codex-plugin");
  const canonicalManifest = path.join(canonicalDir, "plugin.json");
  if (fs.existsSync(canonicalManifest)) {
    return;
  }

  const legacyManifest = path.join(destDir, ".Codex-plugin", "plugin.json");
  if (!fs.existsSync(legacyManifest)) {
    return;
  }

  fs.mkdirSync(canonicalDir, { recursive: true });
  fs.copyFileSync(legacyManifest, canonicalManifest);
}

function copyPluginTo(destDir) {
  fs.mkdirSync(path.dirname(destDir), { recursive: true });
  fs.rmSync(destDir, { recursive: true, force: true });
  copyDirSync(SOURCE_DIR, destDir);
  ensureLowercaseCodexManifest(destDir);
  writeLocalMcpConfig(destDir);
}

function pruneStaleCacheVersions(pluginName, keepVersion) {
  if (process.env.LIVEPILOT_CODEX_CACHE_PATH) {
    return [];
  }
  const pluginCacheRoot = path.join(codexCacheRoot(), pluginName);
  if (!fs.existsSync(pluginCacheRoot)) {
    return [];
  }

  const removed = [];
  for (const entry of fs.readdirSync(pluginCacheRoot, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name === keepVersion) {
      continue;
    }
    const stalePath = path.join(pluginCacheRoot, entry.name);
    fs.rmSync(stalePath, { recursive: true, force: true });
    removed.push(stalePath);
  }
  return removed;
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
  const pluginVersion = manifest.version || "unknown";
  const destDir = targetPluginDir();
  const cacheDir = targetCacheDir(pluginName, pluginVersion);
  const marketFile = ensureMarketplace(pluginName);

  console.log("Installing LivePilot Codex plugin...");
  console.log("  Source: %s", SOURCE_DIR);
  console.log("  Target: %s", destDir);
  console.log("  Codex cache: %s", cacheDir);
  console.log("  Marketplace: %s", marketFile);
  console.log("");

  copyPluginTo(destDir);
  copyPluginTo(cacheDir);
  const removedStaleCaches = pruneStaleCacheVersions(pluginName, pluginVersion);
  for (const stalePath of removedStaleCaches) {
    console.log("  Removed stale Codex cache: %s", stalePath);
  }

  console.log("Done! Next steps:");
  console.log("  1. Open or refresh Codex");
  console.log("  2. Check that LivePilot appears in Local Plugins");
  console.log("  3. Start a new thread or reload tools if Codex was already open");
}

function uninstallCodexPlugin() {
  const manifest = loadManifest();
  const pluginName = manifest.name || "livepilot";
  const pluginVersion = manifest.version || "unknown";
  const destDir = targetPluginDir();
  const cacheDir = targetCacheDir(pluginName, pluginVersion);
  const marketFile = removeMarketplaceEntry(pluginName);

  if (fs.existsSync(destDir)) {
    console.log("Removing Codex plugin: %s", destDir);
    fs.rmSync(destDir, { recursive: true, force: true });
  } else {
    console.log("Codex plugin not found at %s", destDir);
  }

  if (fs.existsSync(cacheDir)) {
    console.log("Removing Codex plugin cache: %s", cacheDir);
    fs.rmSync(cacheDir, { recursive: true, force: true });
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
