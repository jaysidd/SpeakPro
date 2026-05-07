#!/usr/bin/env bash
# SpeakPro installer.
# - Symlinks `speakpro` and `speak-selection.sh` into ~/.local/bin (or BIN_DIR)
# - Optionally installs a launchd agent so the daemon auto-starts at login.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"

mkdir -p "$BIN_DIR"

for tool in speakpro speakpro-daemon speak-selection.sh speak-toggle.sh speak-stop.sh; do
  src="$ROOT/bin/$tool"
  dst="$BIN_DIR/$tool"
  ln -sf "$src" "$dst"
  echo "linked $dst -> $src"
done

# launchd agent (optional auto-start)
if [ "${INSTALL_LAUNCHD:-1}" = "1" ]; then
  PLIST_DIR="$HOME/Library/LaunchAgents"
  PLIST="$PLIST_DIR/com.speakpro.daemon.plist"
  mkdir -p "$PLIST_DIR"

  PYTHON_BIN="$(command -v python3)"
  cat >"$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.speakpro.daemon</string>
  <key>ProgramArguments</key>
  <array>
    <string>$BIN_DIR/speakpro-daemon</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$BIN_DIR</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <!-- Restart only if the daemon crashes; let `speakpro shutdown` actually stop it. -->
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key><false/>
  </dict>
  <key>StandardOutPath</key><string>$HOME/.speakpro/launchd.out.log</string>
  <key>StandardErrorPath</key><string>$HOME/.speakpro/launchd.err.log</string>
</dict>
</plist>
PLIST
  mkdir -p "$HOME/.speakpro"
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "launchd agent installed: $PLIST"
fi

echo
echo "Done."
echo "Make sure $BIN_DIR is on your PATH:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo
echo "Try it:"
echo "  echo 'Hello from SpeakPro' | speakpro speak"
echo
echo "Next: see docs/iterm2-setup.md to bind a hotkey."
