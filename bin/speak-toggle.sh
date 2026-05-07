#!/usr/bin/env bash
# Pause/resume current speech. Bind to a second hotkey.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/speakpro" toggle
