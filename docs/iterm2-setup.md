# Hotkey setup

iTerm2 doesn't expose the current selection directly to a script, so the
trick is: **selection lands on the macOS pasteboard, the script reads
the pasteboard.** That's why `speak-selection.sh` calls `pbpaste`.

There are two reliable ways to wire up the hotkey. Path A (macOS Shortcuts) is
the recommended one — it's system-wide, works in any app, and doesn't depend
on iTerm2 internals. Path B uses iTerm2's Run Coprocess action and is iTerm2-only.

## Step 0 (both paths): auto-copy selection

iTerm2 → **Settings** → **General** → **Selection** →
☑ **Copy to clipboard on selection**

(If you'd rather not auto-copy, see "Manual copy" at the bottom.)

## Path A — macOS Shortcuts (recommended)

System-wide hotkey. Works in iTerm2, Terminal.app, browsers, anywhere.

1. Open **Shortcuts.app**.
2. **+** → name it "Speak Selection".
3. Add action **Run Shell Script**:
   - Shell: `/bin/bash`
   - Pass input: **as arguments** (we'll use `pbpaste` instead, simpler)
   - Script:
     ```
     ~/.local/bin/speak-selection.sh
     ```
4. In the Shortcut info pane (sidebar `i` icon):
   - **Use as Quick Action**: ☑
   - **Services Menu**: ☑
5. Open **System Settings** → **Keyboard** → **Keyboard Shortcuts** → **Services** →
   find "Speak Selection" under **Text** and assign `⌘⇧S` (or whatever you prefer).

Repeat for two more Shortcuts:
- "Speak Pause/Resume" → runs `speak-toggle.sh`, hotkey `⌘⇧P`
- "Speak Stop" → runs `speak-stop.sh`, hotkey `⌘⇧X`

That's it. Select text in iTerm2, hit `⌘⇧S`, you'll hear it.

## Path B — iTerm2 Run Coprocess (iTerm2-only)

iTerm2 → **Settings** → **Keys** → **Key Bindings** → **+**

- **Keyboard shortcut:** `⌘⇧S`
- **Action:** `Run Coprocess`
- **Coprocess command:**
  ```
  ~/.local/bin/speak-selection.sh
  ```

Click **OK**. Caveat: coprocess output is piped back into your terminal as
if the remote side typed it. The provided `speak-selection.sh` already
suppresses output, so this should be silent. If you see stray characters,
double-check the script ends with a clean `exec` and isn't echoing.

Repeat for `speak-toggle.sh` and `speak-stop.sh`.

> Note: there is **no generic "Run Command" action** in iTerm2's Key Bindings
> dropdown — that label belongs to the Trigger system (regex-fired actions on
> terminal output), not to keystrokes. Use Run Coprocess.

## Manual copy (if you don't want auto-copy on selection)

Add a wrapper that copies first:

```bash
# bin/speak-selection-copy-first.sh
#!/usr/bin/env bash
osascript -e 'tell application "System Events" to keystroke "c" using command down'
sleep 0.1
exec ~/.local/bin/speak-selection.sh
```

Bind that script instead. Requires Accessibility permission for the host app
that runs it (Shortcuts.app, iTerm2, etc.) — System Settings → Privacy &
Security → Accessibility.

## Troubleshooting

- **Nothing happens:** `speakpro status` from a shell. If it says "could not
  reach daemon", run `speakpro speak "test"` once — it auto-starts the daemon.
  Check `~/.speakpro/daemon.log`.
- **launchctl agent not starting:** `launchctl list | grep speakpro` and
  check `~/.speakpro/launchd.err.log`.
- **PATH issues in keybindings:** key bindings run in a minimal shell. Always
  use absolute paths — the install script generates absolute symlinks in
  `~/.local/bin`, and the wrappers re-exec with absolute paths.
- **Selection not on clipboard:** confirm "Copy to clipboard on selection"
  is enabled, or use the manual copy wrapper.
- **`speakpro shutdown` and the daemon comes right back:** that means the
  launchd agent is using the default `KeepAlive=true`. The installer ships
  `KeepAlive: SuccessfulExit=false` so clean shutdowns stick. If you
  upgraded from an older install, re-run `./install.sh`. To stop the daemon
  *and* keep it stopped: `launchctl unload ~/Library/LaunchAgents/com.speakpro.daemon.plist`.
