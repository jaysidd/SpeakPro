#!/usr/bin/env bash
# Read the current macOS pasteboard (iTerm2 with "copy on selection" enabled
# puts your selection there automatically) and pipe it into SpeakPro.
#
# Bind this to a hotkey in iTerm2 Settings -> Keys -> Key Bindings:
#   - First send Cmd+C (so even without copy-on-selection, the selection lands
#     on the clipboard), then trigger this script via a Shell Integration
#     coprocess or via a system Service.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

text="$(pbpaste)"
if [ -z "${text// /}" ]; then
  exit 0
fi

exec "$HERE/speakpro" speak <<<"$text"
