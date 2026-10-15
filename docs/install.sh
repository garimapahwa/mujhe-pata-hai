#!/usr/bin/env bash
# Side Eye installer — https://garimapahwa.github.io/side-eye
#
#   Install / update:  curl -fsSL https://garimapahwa.github.io/side-eye/install.sh | bash
#   Uninstall:         curl -fsSL https://garimapahwa.github.io/side-eye/install.sh | bash -s -- --uninstall
#
# No admin password. Everything lives in your user folder:
#   ~/Applications/Side Eye.app                     the menu bar app
#   ~/Library/Application Support/SideEye/          code, Python environment, your settings
set -euo pipefail

REPO="garimapahwa/side-eye"
BRANCH="main"
APP_NAME="Side Eye"
LABEL="com.sideeye.agent"
SUPPORT="$HOME/Library/Application Support/SideEye"
SRC="$SUPPORT/app"
VENV="$SUPPORT/venv"
APP="$HOME/Applications/$APP_NAME.app"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"
# before the rename the app was called "Mujhe Pata Hai"
OLD_SUPPORT="$HOME/Library/Application Support/MujhePataHai"
OLD_APP="$HOME/Applications/Mujhe Pata Hai.app"
OLD_LABEL="com.mujhepatahai.agent"

bold=$'\033[1m'; dim=$'\033[2m'; red=$'\033[31m'; green=$'\033[32m'; yellow=$'\033[33m'; reset=$'\033[0m'
say()  { printf "%s\n" "${bold}›${reset} $*"; }
ok()   { printf "%s\n" "${green}✓${reset} $*"; }
warn() { printf "%s\n" "${yellow}!${reset} $*"; }
die()  { printf "%s\n" "${red}✗ $*${reset}" >&2; exit 1; }

quit_running_app() {
  pkill -f "$SRC/app.py" 2>/dev/null || true
}

remove_old_install() {  # carry the API key and settings over from "Mujhe Pata Hai", then remove it
  [[ -d "$OLD_SUPPORT" || -d "$OLD_APP" ]] || return 0
  launchctl bootout "gui/$(id -u)/$OLD_LABEL" 2>/dev/null || true
  pkill -f "$OLD_SUPPORT/app/app.py" 2>/dev/null || true
  mkdir -p "$SUPPORT"
  [[ -f "$OLD_SUPPORT/app/.env" && ! -f "$SRC/.env" ]] && mkdir -p "$SRC" && cp "$OLD_SUPPORT/app/.env" "$SRC/.env"
  [[ -f "$OLD_SUPPORT/prefs.json" && ! -f "$SUPPORT/prefs.json" ]] && cp "$OLD_SUPPORT/prefs.json" "$SUPPORT/prefs.json"
  rm -rf "$OLD_APP" "$OLD_SUPPORT"
  rm -f "$HOME/Library/LaunchAgents/$OLD_LABEL.plist"
  ok "Replaced the old Mujhe Pata Hai app"
}

uninstall() {
  say "Removing ${APP_NAME}…"
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  quit_running_app
  rm -rf "$APP" "$SUPPORT"
  rm -f "$AGENT"
  ok "Uninstalled. Phone उठा सकती हो… पर मुझे पता चल जाएगा।"
  exit 0
}

[[ "${1:-}" == "--uninstall" ]] && uninstall
[[ "$(uname -s)" == "Darwin" ]] || die "$APP_NAME is macOS-only (it reads macOS idle time and lives in the menu bar)."

printf "\n%s\n%s\n\n" "${bold}  $APP_NAME${reset}" "${dim}  your Hinglish voice focus buddy · powered by Sarvam AI${reset}"

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
remove_old_install
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
  <key>CFBundleIdentifier</key><string>com.sideeye.app</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>side-eye</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSUIElement</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>She listens for your excuse for a few seconds, only right after she catches you.</string>
  <key>NSAppleEventsUsageDescription</key><string>Reads the title of your active Chrome/Safari tab to check if you're really studying.</string>
</dict></plist>
PLIST
# Run Python from *inside* the bundle so macOS treats the process as "Side Eye" (not "Python"):
# that's what makes the menu bar icon show up and the microphone prompt name the app.
FRAMEWORK_PY="$("$VENV/bin/python" -c 'import os, sys; print(os.path.join(sys.base_prefix, "Resources/Python.app/Contents/MacOS/Python"))')"
if [[ -x "$FRAMEWORK_PY" ]]; then
  cp "$FRAMEWORK_PY" "$APP/Contents/MacOS/SideEye"
  RUNNER='export __PYVENV_LAUNCHER__="'"$VENV/bin/python"'"; exec "$(dirname "$0")/SideEye"'
else
  RUNNER='exec "'"$VENV/bin/python"'"'
fi
cat > "$APP/Contents/MacOS/side-eye" <<LAUNCHER
#!/bin/bash
# Opened from Finder/Spotlight? Hand off to launchd: macOS 26 only shows the menu bar icon
# of this (non-notarized) app when launchd starts it.
if [[ -z "\$MPH_VIA_LAUNCHD" ]]; then
  launchctl kickstart "gui/\$(id -u)/$LABEL" 2>/dev/null \\
    || { launchctl bootstrap "gui/\$(id -u)" "$AGENT" 2>/dev/null; launchctl kickstart "gui/\$(id -u)/$LABEL"; }
  exit 0
fi
export MPH_APP_BUNDLE="$APP"
cd "$SRC"
$RUNNER "$SRC/app.py" "\$@"
LAUNCHER
chmod +x "$APP/Contents/MacOS/side-eye"

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

# ---------------------------------------------------------------- 6. start with launchd (now and at every login)
"$VENV/bin/python" - "$AGENT" "$APP/Contents/MacOS/side-eye" "$LABEL" <<'AGENTPY'
import plistlib, sys, os
path, launcher, label = sys.argv[1], sys.argv[2], sys.argv[3]
run_at_load = True
if os.path.exists(path):  # keep the user's "Launch at Login" choice
    try:
        run_at_load = plistlib.load(open(path, "rb")).get("RunAtLoad", True)
    except Exception:
        pass
os.makedirs(os.path.dirname(path), exist_ok=True)
plistlib.dump({"Label": label, "ProgramArguments": [launcher],
               "EnvironmentVariables": {"MPH_VIA_LAUNCHD": "1"}, "RunAtLoad": run_at_load,
               "ProcessType": "Interactive"}, open(path, "wb"))
AGENTPY
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$AGENT"
launchctl kickstart "gui/$(id -u)/$LABEL" 2>/dev/null || true
cat <<DONE

${green}${bold}  Ho gaya ✓${reset}  Click the ${bold}eye${reset} in your menu bar and flip the switch.
  ${dim}Allow the microphone when macOS asks. Run this command again to update.${reset}

DONE
