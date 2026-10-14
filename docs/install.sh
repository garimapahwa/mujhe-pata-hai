#!/usr/bin/env bash
# Mujhe Pata Hai installer — https://garimapahwa.github.io/mujhe-pata-hai
#
#   Install / update:  curl -fsSL https://garimapahwa.github.io/mujhe-pata-hai/install.sh | bash
#   Uninstall:         curl -fsSL https://garimapahwa.github.io/mujhe-pata-hai/install.sh | bash -s -- --uninstall
#
# No admin password. Everything lives in your user folder:
#   ~/Applications/Mujhe Pata Hai.app                     the menu bar app
#   ~/Library/Application Support/MujhePataHai/           code, Python environment, your settings
set -euo pipefail

REPO="garimapahwa/mujhe-pata-hai"
BRANCH="main"
APP_NAME="Mujhe Pata Hai"
SUPPORT="$HOME/Library/Application Support/MujhePataHai"
SRC="$SUPPORT/app"
VENV="$SUPPORT/venv"
APP="$HOME/Applications/$APP_NAME.app"
AGENT="$HOME/Library/LaunchAgents/com.mujhepatahai.agent.plist"

bold=$'\033[1m'; dim=$'\033[2m'; red=$'\033[31m'; green=$'\033[32m'; yellow=$'\033[33m'; reset=$'\033[0m'
say()  { printf "%s\n" "${bold}›${reset} $*"; }
ok()   { printf "%s\n" "${green}✓${reset} $*"; }
warn() { printf "%s\n" "${yellow}!${reset} $*"; }
die()  { printf "%s\n" "${red}✗ $*${reset}" >&2; exit 1; }

quit_running_app() {
  pkill -f "$SRC/app.py" 2>/dev/null || true
}

uninstall() {
  say "Removing ${APP_NAME}…"
  quit_running_app
  rm -rf "$APP" "$SUPPORT"
  rm -f "$AGENT"
  ok "Uninstalled. Phone उठा सकती हो… पर मुझे पता चल जाएगा। 👀"
  exit 0
}

[[ "${1:-}" == "--uninstall" ]] && uninstall
[[ "$(uname -s)" == "Darwin" ]] || die "$APP_NAME is macOS-only (it reads macOS idle time and lives in the menu bar)."

printf "\n%s\n%s\n\n" "${bold}  मुझे पता है · $APP_NAME${reset}" "${dim}  your Hinglish voice focus buddy · powered by Sarvam AI${reset}"

# ---------------------------------------------------------------- 1. Python 3.11+
find_python() {
  for cand in python3.13 python3.12 python3.11 python3; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      command -v "$cand"; return 0
    fi
  done
  for cand in /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 /Library/Frameworks/Python.framework/Versions/3.1{3,2,1}/bin/python3; do
    [[ -x "$cand" ]] && { echo "$cand"; return 0; }
  done
  return 1
}

PY="$(find_python || true)"
if [[ -z "$PY" ]]; then
  if command -v brew >/dev/null 2>&1; then
    say "Installing Python 3.12 with Homebrew (one-time)…"
    brew install python@3.12 >/dev/null
    PY="$(find_python || true)"
  fi
  [[ -n "$PY" ]] || die "Python 3.11+ is needed. Install it from https://www.python.org/downloads/macos/ and run this command again."
fi
ok "Python: $("$PY" --version 2>&1)"

# ---------------------------------------------------------------- 2. download the app (keep the user's .env on update)
quit_running_app
mkdir -p "$SUPPORT"
SAVED_ENV=""
[[ -f "$SRC/.env" ]] && SAVED_ENV="$(cat "$SRC/.env")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
if [[ -n "${MPH_SOURCE:-}" ]]; then  # local testing: install from a checkout instead of GitHub
  say "Copying from ${MPH_SOURCE}…"
  mkdir -p "$TMP/src" && (cd "$MPH_SOURCE" && git ls-files -co --exclude-standard | tar -cf - -T -) | tar -xf - -C "$TMP/src"
else
  say "Downloading ${APP_NAME}…"
  curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" | tar -xz -C "$TMP"
  mv "$TMP"/*-"$BRANCH" "$TMP/src"
fi
rm -rf "$SRC" && mv "$TMP/src" "$SRC"
[[ -n "$SAVED_ENV" ]] && printf "%s\n" "$SAVED_ENV" > "$SRC/.env"
ok "Code in ${dim}$SRC${reset}"

# ---------------------------------------------------------------- 3. Python environment
say "Setting up the Python environment (about a minute the first time)…"
[[ -x "$VENV/bin/python" ]] || "$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip >/dev/null
"$VENV/bin/python" -m pip install --quiet -r "$SRC/requirements.txt"
ok "Dependencies installed"

# ---------------------------------------------------------------- 4. Sarvam API key
if ! grep -qs '^SARVAM_API_KEY=.\+' "$SRC/.env"; then
  printf "\n%s\n" "${bold}Sarvam AI API key${reset} ${dim}(free at https://dashboard.sarvam.ai — press Enter to add it later from the menu)${reset}"
  KEY=""
  if [[ -r /dev/tty ]]; then
    { read -r -p "  Paste key: " KEY < /dev/tty; } 2>/dev/null || true
  fi
  if [[ -n "$KEY" ]]; then
    printf "SARVAM_API_KEY=%s\n" "$KEY" > "$SRC/.env"
    chmod 600 "$SRC/.env"
    ok "Key saved (only on this Mac)"
  else
    warn "No key yet — the app will ask for it when you flip the switch."
  fi
fi

# ---------------------------------------------------------------- 5. the .app bundle
say "Creating ${bold}$APP_NAME.app${reset}…"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleDisplayName</key><string>$APP_NAME</string>
  <key>CFBundleIdentifier</key><string>com.mujhepatahai.app</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>mujhe-pata-hai</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSUIElement</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>She listens for your excuse for a few seconds, only right after she catches you.</string>
  <key>NSAppleEventsUsageDescription</key><string>Reads the title of your active Chrome/Safari tab to check if you're really studying.</string>
</dict></plist>
PLIST
cat > "$APP/Contents/MacOS/mujhe-pata-hai" <<LAUNCHER
#!/bin/bash
export MPH_APP_BUNDLE="$APP"
cd "$SRC"
exec "$VENV/bin/python" "$SRC/app.py" "\$@"
LAUNCHER
chmod +x "$APP/Contents/MacOS/mujhe-pata-hai"

# app icon: the 👀 emoji on a marigold squircle (best effort)
"$VENV/bin/python" - "$APP/Contents/Resources" <<'ICON' >/dev/null 2>&1 || true
import subprocess, sys, tempfile, os
from AppKit import (NSBezierPath, NSBitmapImageRep, NSColor, NSFont, NSFontAttributeName, NSGraphicsContext,
                    NSMakeRect, NSPNGFileType, NSString, NSCalibratedRGBColorSpace)
out = sys.argv[1]; iconset = os.path.join(tempfile.mkdtemp(), "AppIcon.iconset"); os.makedirs(iconset)
def render(px, path):
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(None, px, px, 8, 4, True, False, NSCalibratedRGBColorSpace, 0, 0)
    NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
    m = px * 0.09; r = NSMakeRect(m, m, px - 2 * m, px - 2 * m)
    NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.72, 0.18, 1).setFill()
    NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(r, px * 0.2, px * 0.2).fill()
    s = NSString.stringWithString_("👀"); attrs = {NSFontAttributeName: NSFont.systemFontOfSize_(px * 0.52)}
    size = s.sizeWithAttributes_(attrs); s.drawAtPoint_withAttributes_(((px - size.width) / 2, (px - size.height) / 2), attrs)
    NSGraphicsContext.restoreGraphicsState()
    rep.representationUsingType_properties_(NSPNGFileType, None).writeToFile_atomically_(path, True)
for base in (16, 32, 128, 256, 512):
    render(base, f"{iconset}/icon_{base}x{base}.png"); render(base * 2, f"{iconset}/icon_{base}x{base}@2x.png")
subprocess.run(["iconutil", "-c", "icns", iconset, "-o", os.path.join(out, "AppIcon.icns")], check=True)
ICON
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true
ok "Installed ${dim}$APP${reset}"

# keep "Launch at Login" pointing at the new bundle
[[ -f "$AGENT" ]] && "$VENV/bin/python" -c "
import plistlib, sys; p = sys.argv[1]
plistlib.dump({'Label': 'com.mujhepatahai.agent', 'ProgramArguments': ['/usr/bin/open', '-a', sys.argv[2]], 'RunAtLoad': True}, open(p, 'wb'))" "$AGENT" "$APP"

# ---------------------------------------------------------------- 6. launch
open "$APP"
cat <<DONE

${green}${bold}  Ho gaya! ✓${reset}  Look for the ${bold}👁 eye${reset} in your menu bar (top right).

  1. Click it → pick a ${bold}Character${reset} → flip the ${bold}switch${reset} on.
  2. macOS will ask for ${bold}Microphone${reset} access (so she can hear your excuse). Allow it.
  3. Go idle for 8 seconds… ${dim}मुझे पता है।${reset}

  Update:    run the same command again
  Uninstall: curl -fsSL https://garimapahwa.github.io/mujhe-pata-hai/install.sh | bash -s -- --uninstall

DONE
