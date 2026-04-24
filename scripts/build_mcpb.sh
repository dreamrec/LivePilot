#!/usr/bin/env bash
# Build the livepilot-${VERSION}.mcpb bundle for Claude Desktop one-click install.
#
# The MCPB format is a ZIP archive with manifest.json at the root and the
# runtime entry point the manifest refers to (bin/livepilot.js) plus
# everything that entry point needs at runtime (the Python server, the
# Remote Script, the M4L device, the installer wrapper).
#
# Why this script exists: the README's "Easiest: Claude Desktop Extension
# (1 click)" path promises a `livepilot.mcpb` download. Every release from
# v1.17 through v1.20.2 silently shipped without the artifact because no
# build script existed. v1.20.3 fixes that by introducing this script +
# attaching the bundle to the release.
#
# Usage:
#   scripts/build_mcpb.sh                 # builds dist/livepilot-${VERSION}.mcpb
#   scripts/build_mcpb.sh --output <path> # custom output path
#
# The bundle is deliberately lean:
#   - bin/livepilot.js is pure Node stdlib (zero npm deps) so no
#     node_modules is shipped
#   - Python deps are bootstrapped into ~/.livepilot/.venv on first launch
#     from the bundled requirements.txt (the same path npm-install users take)
#   - LivePilot_Analyzer.amxd + Remote Script are shipped so the MCPB
#     install can auto-install them via the user_config.auto_install_remote_script
#     switch in manifest.json

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(python3 -c "import json; print(json.load(open('manifest.json'))['version'])")"
OUTPUT_DEFAULT="$ROOT/dist/livepilot-${VERSION}.mcpb"
OUTPUT="$OUTPUT_DEFAULT"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

STAGE="$(mktemp -d -t livepilot-mcpb.XXXXXX)"
trap "rm -rf '$STAGE'" EXIT

echo "→ Staging v${VERSION} into $STAGE"

# Files + dirs shipped inside the bundle
cp manifest.json "$STAGE/"
cp package.json "$STAGE/"
cp requirements.txt "$STAGE/"
mkdir -p "$STAGE/bin"
cp bin/livepilot.js "$STAGE/bin/"
cp -R mcp_server "$STAGE/"
cp -R remote_script "$STAGE/"
cp -R m4l_device "$STAGE/"
cp -R installer "$STAGE/"

# Exclude caches and editor cruft
find "$STAGE" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGE" -name "*.pyc" -delete 2>/dev/null || true
find "$STAGE" -name ".DS_Store" -delete 2>/dev/null || true

# Ensure output dir exists
mkdir -p "$(dirname "$OUTPUT")"

echo "→ Building $OUTPUT"
(cd "$STAGE" && zip -rq "$OUTPUT" . -x "*.DS_Store")

# Post-build verification
unzip -p "$OUTPUT" manifest.json | python3 -c "
import json, sys
m = json.load(sys.stdin)
assert m['name'] == 'livepilot', f'bad name: {m[\"name\"]}'
assert m['version'] == '${VERSION}', f'bad version: {m[\"version\"]} != ${VERSION}'
assert m['server']['entry_point'] == 'bin/livepilot.js', f'bad entry'
print(f'✓ manifest: {m[\"name\"]} v{m[\"version\"]} (entry={m[\"server\"][\"entry_point\"]})')
"

FILES="$(unzip -l "$OUTPUT" | tail -1 | awk '{print $2}')"
SIZE="$(ls -lh "$OUTPUT" | awk '{print $5}')"
echo "✓ Built $OUTPUT ($SIZE, $FILES files)"
