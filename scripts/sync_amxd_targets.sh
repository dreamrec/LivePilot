#!/usr/bin/env bash
# Propagate a freshly re-frozen LivePilot_Analyzer.amxd to every install target
# and verify the result. Run this AFTER exporting the device from Max.
#
# Why this exists: the freeze is a GUI action in Max, and every install location
# is a separate snapshot. Two releases shipped a device whose frozen JS lagged
# the repo because one target was missed or the version string never moved.
# See docs/MAX_FREEZE_WORKFLOW.md and docs/PENDING_AMXD_REFREEZE.md.
#
# Usage:
#   bash scripts/sync_amxd_targets.sh            # verify only, no writes
#   bash scripts/sync_amxd_targets.sh --apply    # copy repo .amxd to all targets
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
SRC="m4l_device/LivePilot_Analyzer.amxd"
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

[ -f "$SRC" ] || { echo "::error::missing $SRC"; exit 1; }

VERSION=$(python3 -c "import sys; sys.path.insert(0,'.'); from mcp_server import __version__; print(__version__)")
JS_VERSION=$(grep -oE 'var VERSION[[:space:]]*=[[:space:]]*"[0-9.]+"' m4l_device/livepilot_bridge.js | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')

echo "repo version      : $VERSION"
echo "bridge.js VERSION : $JS_VERSION"

fail=0

# --- Gate 1: the JS source must carry the release version -------------------
if [ "$JS_VERSION" != "$VERSION" ]; then
  echo "::error::livepilot_bridge.js says $JS_VERSION, repo is $VERSION. Bump 'var VERSION' BEFORE freezing."
  fail=1
fi

# --- Gate 2: the frozen binary must embed that same version -----------------
if strings "$SRC" | grep -qE "var VERSION[[:space:]]*=[[:space:]]*\"$VERSION\""; then
  echo "freeze version    : OK ($VERSION embedded)"
else
  FROZEN=$(strings "$SRC" | grep -oE 'var VERSION[[:space:]]*=[[:space:]]*"[0-9.]+"' | head -1)
  echo "::error::$SRC embeds [$FROZEN], expected $VERSION — the device has NOT been re-frozen."
  fail=1
fi

# --- Gate 3: every bridge command in source must be in the binary -----------
# A 6-byte version patch can satisfy Gate 2 without any real re-freeze.
MISSING=$(python3 - <<'PYEOF' 2>/dev/null
import re, subprocess
src = open("m4l_device/livepilot_bridge.js", encoding="utf-8").read()
cmds = sorted(set(re.findall(r'case\s*"([^"]+)"\s*:', src)))
blob = subprocess.check_output(["strings", "m4l_device/LivePilot_Analyzer.amxd"], text=True)
print(",".join(c for c in cmds if f'case "{c}"' not in blob))
PYEOF
)
if [ -n "$MISSING" ]; then
  echo "::error::frozen .amxd is missing bridge command(s): $MISSING"
  echo "::error::A real Max re-freeze is required (a binary version patch is not enough)."
  fail=1
else
  echo "bridge commands   : OK (all present in frozen binary)"
fi

# --- Gate 3b: identifier-level freeze check --------------------------------
# Gate 3 only compares `case "<command>":` names, so a batch that adds no NEW
# command (the v1.28 token auth adds none — it wraps the existing dispatch)
# passes it against a binary containing none of the new code. Diff a sample of
# distinctive top-level identifiers from the source against the binary instead.
STALE_IDS=$(python3 - <<'PYEOF' 2>/dev/null
import re, subprocess
src = open("m4l_device/livepilot_bridge.js", encoding="utf-8").read()
# Top-level `function name(` and `var name =` identifiers, minus trivial ones.
ids = set(re.findall(r'^function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(', src, re.M))
ids |= set(re.findall(r'^var\s+([A-Za-z_][A-Za-z0-9_]{4,})\s*=', src, re.M))
blob = subprocess.check_output(["strings", "m4l_device/LivePilot_Analyzer.amxd"], text=True)
print(",".join(sorted(i for i in ids if i not in blob)))
PYEOF
)
if [ -n "$STALE_IDS" ]; then
  echo "::error::frozen .amxd is missing source identifier(s): $STALE_IDS"
  echo "::error::The binary predates the current livepilot_bridge.js. Re-freeze in Max."
  fail=1
else
  echo "source identifiers: OK (frozen binary matches current JS)"
fi

# --- Gate 4: the freeze must stay FAT (FluCoMa externals bundled) -----------
read -r SIZE MACH PE <<<"$(python3 -c "
d=open('$SRC','rb').read()
print(len(d), d.count(b'\xfe\xed\xfa\xcf')+d.count(b'\xcf\xfa\xed\xfe'), d.count(b'PE\x00\x00'))
")"
if [ "$MACH" -gt 0 ] && [ "$PE" -gt 0 ]; then
  echo "freeze type       : FAT (${SIZE} bytes, macho=$MACH pe=$PE)"
else
  echo "::error::$SRC looks THIN (${SIZE} bytes, macho=$MACH pe=$PE). Releases must ship a FAT freeze."
  fail=1
fi

# --- Targets ----------------------------------------------------------------
TARGETS=(
  "$HOME/Documents/Max 9/Library/LivePilot_Analyzer.amxd"
  "$HOME/Music/Ableton/User Library/Presets/Audio Effects/Max Audio Effect/LivePilot_Analyzer.amxd"
  "$HOME/.claude/plugins/marketplaces/dreamrec-LivePilot/m4l_device/LivePilot_Analyzer.amxd"
)

SRC_MD5=$(md5 -q "$SRC")
echo
echo "source md5        : $SRC_MD5"
echo

for t in "${TARGETS[@]}"; do
  if [ ! -e "$t" ]; then
    echo "absent   ~/${t#$HOME/}"
    continue
  fi
  if [ "$APPLY" = "1" ]; then
    cp "$SRC" "$t" || { echo "::error::copy failed: $t"; fail=1; continue; }
  fi
  T_MD5=$(md5 -q "$t")
  if [ "$T_MD5" = "$SRC_MD5" ]; then
    echo "in sync  ~/${t#$HOME/}"
  else
    echo "STALE    ~/${t#$HOME/}  ($T_MD5)"
    [ "$APPLY" = "1" ] && fail=1
    [ "$APPLY" = "0" ] && echo "         -> rerun with --apply"
  fi
done

echo
if [ "$fail" != "0" ]; then
  echo "RESULT: FAIL — do not ship."
  exit 1
fi
if [ "$APPLY" = "0" ]; then
  echo "RESULT: verify-only pass. Rerun with --apply to propagate."
else
  echo "RESULT: OK — all targets carry the $VERSION freeze."
fi
