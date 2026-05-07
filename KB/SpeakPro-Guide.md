# SpeakPro — Founder's Guide

A printable reference for SpeakPro: a TTS narration add-on for iTerm2 (and any Mac terminal) that lets you highlight text and listen to it via a system-wide hotkey, with code/markdown noise stripped out before speech.

**Author:** Junaid Siddiqi
**Last updated:** 2026-05-07
**Project location:** `~/Projects/Tools/SpeakPro`

---

## 1. What this solves

Claude Desktop has a "speaker icon" next to each AI response — press it, the response is read aloud. iTerm2 has no equivalent. SpeakPro fills that gap:

- Highlight any text in iTerm2 → press `⌘⌃S` → hear it spoken with a natural neural voice.
- Pause / resume / stop with other hotkeys.
- Code blocks, tool-use XML, ANSI escapes, and long URLs are stripped *before* speech so you don't have to listen to "backtick backtick backtick python."

It's local-only (no cloud), free, and uses Piper neural TTS (the same class of voice technology behind modern AI assistants).

---

## 2. What's installed and where

| Thing | Path |
|---|---|
| Project source | `~/Projects/Tools/SpeakPro` |
| Daemon socket / log / pid | `~/.speakpro/daemon.{sock,log,pid}` |
| Voice models | `~/.speakpro/voices/*.onnx` |
| Piper binary | `~/Library/Python/3.9/bin/piper` (installed via `pip3 install --user piper-tts`) |
| Auto-start agent | `~/Library/LaunchAgents/com.speakpro.daemon.plist` |
| CLI symlinks | `~/.local/bin/speakpro`, `~/.local/bin/speak-selection.sh`, etc. |

**Voices currently installed:**

| Voice | Locale | Quality | Notes |
|---|---|---|---|
| `en_US-amy-medium` | US female | medium (63 MB) | Default natural voice |
| `en_US-ryan-high` | US male | high (121 MB) | Best male voice — current pick |
| `en_GB-alan-medium` | UK male | medium (63 MB) | Polished British male |

---

## 3. Daily use — hotkeys

These were assigned via macOS Shortcuts.app and live under System Settings → Keyboard → Keyboard Shortcuts → Services.

| Hotkey | What it does | Underlying script |
|---|---|---|
| `⌘⌃S` | Speak the currently selected text | `speak-selection.sh` |
| `⌘⇧P` | Pause / resume current playback | `speak-toggle.sh` |
| `⌘⇧X` | Stop and clear the queue | `speak-stop.sh` |

Selection auto-copies to clipboard via iTerm2 → Settings → General → Selection → ☑ "Copy to clipboard on selection."

---

## 4. CLI cheatsheet

Every action also has a CLI command. Useful when you're already at the prompt.

```bash
# speak text
echo "hello" | speakpro speak       # from stdin
speakpro speak "hello there"        # from args
pbpaste | speakpro speak            # from clipboard

# transport controls
speakpro pause
speakpro resume
speakpro toggle                     # pause if playing, resume if paused
speakpro skip                       # skip current paragraph
speakpro stop                       # stop and clear queue
speakpro status                     # JSON: backend, playing, paused, queued

# voice / rate (runtime only — see Section 8 for persistence)
speakpro voice en_US-ryan-high      # switch voice
speakpro rate 175                   # set rate (wpm-style number)

# daemon
speakpro shutdown                   # stop the daemon (launchd will not auto-restart on clean exit)
```

Speech rate reference points:
- `140` slow, very clear
- `175` natural conversational (current default)
- `200` brisk
- `220` fast

For Piper, this number maps internally to `length-scale = 175 / rate`. A rate of 140 produces `ls=1.25` (slower); 220 produces `ls≈0.80` (faster).

---

## 5. The TUI — when you forget commands

```bash
speakpro ui
```

Single screen with:
- Live status (backend, voice, playing, queue)
- Numbered actions 1–9 (speak clipboard, pause, voice switch, rate, test sample, tail log, restart daemon)
- iTerm2 hotkey reminder
- Cheatsheet block with full absolute paths — every line is copy-pasteable

**Press `q` to exit.** When you're juggling many terminal windows and don't remember where things live, this is the fastest way back into context.

---

## 6. Voices — pick one, switch one, find more

### Listening to options before downloading

Official samples site: **https://rhasspy.github.io/piper-samples/**

Every voice in the Piper catalog has a play button on this page. Listen, decide, then download.

### Downloading a new voice

Once you know the voice id from the samples page (e.g. `en_US-libritts-high`), break it into three parts:

- locale (e.g. `en_US`)
- name (e.g. `libritts`)
- quality (`low`, `medium`, or `high`)

Download both the `.onnx` model and the `.onnx.json` config. Replace `LOC`, `NAME`, `Q` in this template:

```bash
cd ~/.speakpro/voices && \
LOC=en_US NAME=libritts Q=high && \
curl -fL -O "https://huggingface.co/rhasspy/piper-voices/resolve/main/${LOC%_*}/${LOC}/${NAME}/${Q}/${LOC}-${NAME}-${Q}.onnx" && \
curl -fL -O "https://huggingface.co/rhasspy/piper-voices/resolve/main/${LOC%_*}/${LOC}/${NAME}/${Q}/${LOC}-${NAME}-${Q}.onnx.json"
```

### Switching voice at runtime

```bash
speakpro voice en_US-ryan-high      # by basename, no extension
```

Or in the TUI: option **6** lists all installed voices with numbers — type the number.

### Notable voices worth trying

| Voice | Why |
|---|---|
| `en_US-amy-medium` | Solid baseline female, modest size |
| `en_US-ryan-high` | Best male voice, larger model = more natural |
| `en_US-libritts-high` | Multi-speaker, very versatile |
| `en_US-lessac-high` | Audiobook-narrator clarity (female) |
| `en_GB-alan-medium` | Polished British male |
| `en_GB-northern_english_male-medium` | Distinct regional accent |
| `en_US-hfc_male-medium` | Alternate American male |

---

## 7. Speed — runtime and permanent

### Runtime change (lasts until daemon restart)

```bash
speakpro rate 175
# or via TUI: option 5
```

### Permanent change (survives reboot)

```bash
PLIST=~/Library/LaunchAgents/com.speakpro.daemon.plist
/usr/libexec/PlistBuddy -c "Set :EnvironmentVariables:SPEAKPRO_RATE 175" "$PLIST"
launchctl unload "$PLIST" && launchctl load "$PLIST"
```

---

## 8. Persistence — making any setting stick

The launchd plist at `~/Library/LaunchAgents/com.speakpro.daemon.plist` is the source of truth on reboot. Three settings live there:

| Key | What it controls |
|---|---|
| `SPEAKPRO_BACKEND` | `say` (macOS classic) or `piper` (neural — current) |
| `SPEAKPRO_PIPER_MODEL` | Absolute path to the `.onnx` voice file used at startup |
| `SPEAKPRO_RATE` | Speech rate (wpm-style number) |

To inspect:

```bash
/usr/libexec/PlistBuddy -c "Print :EnvironmentVariables" ~/Library/LaunchAgents/com.speakpro.daemon.plist
```

To change a value, use `Set` (or `Add` if the key doesn't exist yet). After any change:

```bash
launchctl unload ~/Library/LaunchAgents/com.speakpro.daemon.plist && \
launchctl load ~/Library/LaunchAgents/com.speakpro.daemon.plist
speakpro status         # verify
```

**Example: bake Ryan as the permanent voice.**

```bash
PLIST=~/Library/LaunchAgents/com.speakpro.daemon.plist
/usr/libexec/PlistBuddy -c "Set :EnvironmentVariables:SPEAKPRO_PIPER_MODEL $HOME/.speakpro/voices/en_US-ryan-high.onnx" "$PLIST"
launchctl unload "$PLIST" && launchctl load "$PLIST"
```

---

## 9. Architecture

```
iTerm2 selection ──Cmd+Ctrl+S──► macOS Shortcut ──► speak-selection.sh
                                                          │
                                                     pbpaste piped to
                                                          ▼
                                                    speakpro speak ──► Unix socket
                                                                        ~/.speakpro/daemon.sock
                                                                            │
                                                                            ▼
                                                                  speakpro daemon
                                                                  ├─ preprocess (strip code,
                                                                  │  tool blocks, ANSI, URLs,
                                                                  │  surrogates, control chars)
                                                                  ├─ paragraph queue
                                                                  └─ TTS backend
                                                                       └─ Piper → temp WAV → afplay
```

**Why it's built this way:**

- **Selection-based capture** — you choose what's narrated. No fragile screen-scraping.
- **Long-lived daemon** keeps the model warm (matters most for neural backends).
- **Unix socket protocol** (newline-delimited JSON) — fast, local, no port conflicts, no firewall issues.
- **SIGSTOP/SIGCONT** on the playback subprocess gives true pause/resume even though `say` and `afplay` don't expose it.
- **Worker thread** isolates one paragraph at a time so a bad byte in paragraph 2 doesn't kill paragraphs 3, 4, 5.

---

## 10. Troubleshooting

| Symptom | What to check |
|---|---|
| Hotkey does nothing | `speakpro status` from a shell. If "could not reach daemon", run `speakpro speak "test"` once — it auto-starts the daemon. |
| launchd agent not loading | `launchctl list \| grep speakpro` and `tail ~/.speakpro/launchd.err.log` |
| Speech stops mid-paragraph | Look at `~/.speakpro/daemon.log` — bad bytes in clipboard *should* be sanitized but the log is the proof. |
| Selection isn't being picked up | Check iTerm2 → Settings → General → Selection → ☑ "Copy to clipboard on selection" |
| Audio plays but voice is wrong | `speakpro status` — confirms which voice is active. Plist may have a different default than your runtime change. |
| Daemon comes back after `shutdown` | Edit launchd plist `KeepAlive` to `<dict><key>SuccessfulExit</key><false/></dict>` (already set if installer was run after May 6 2026). |

---

## 11. Roadmap / future ideas

- **Kokoro TTS** — newer model, even more natural, ~80M params, fast on Apple Silicon. Drop-in replacement for the Piper backend class.
- **Menubar widget** — current voice + transport in the macOS menu bar (Hammerspoon or SwiftBar). Skipped for now in favor of the TUI.
- **Local-only web UI** — `http://127.0.0.1:8765` voice picker with sample buttons. Considered, deferred — TUI covered the main pain.
- **iPad/phone control** — bind UI to a LAN address with auth tokens. Worth it only if you want to control narration from another device.
- **Whisper Desk integration** — single chord toggles dictation (Whisper → terminal stdin) and narration (selection → SpeakPro). Same Python/MPS toolchain as the existing Whisper setup.
- **"Narrate last response" mode** — tee Claude Code stdout into a ring buffer; one hotkey reads the most recent block without needing a manual selection.

---

## 12. One-page reference card

Print this section alone if you only need a single sheet on the desk.

```
HOTKEYS
  ⌘⌃S  speak selection           ⌘⇧P  pause/resume           ⌘⇧X  stop

CLI
  speakpro speak <text> | pbpaste | speakpro speak
  speakpro pause / resume / toggle / skip / stop / status / shutdown
  speakpro voice <name>          speakpro rate <wpm>          speakpro ui

PATHS
  Project       ~/Projects/Tools/SpeakPro
  Voices        ~/.speakpro/voices/        (.onnx + .onnx.json pairs)
  Daemon log    ~/.speakpro/daemon.log
  Auto-start    ~/Library/LaunchAgents/com.speakpro.daemon.plist
  Piper bin     ~/Library/Python/3.9/bin/piper

VOICE SAMPLES (pick before downloading)
  https://rhasspy.github.io/piper-samples/

DOWNLOAD MORE VOICES
  cd ~/.speakpro/voices && LOC=en_US NAME=libritts Q=high && \
    curl -fL -O "https://huggingface.co/rhasspy/piper-voices/resolve/main/${LOC%_*}/${LOC}/${NAME}/${Q}/${LOC}-${NAME}-${Q}.onnx" && \
    curl -fL -O "https://huggingface.co/rhasspy/piper-voices/resolve/main/${LOC%_*}/${LOC}/${NAME}/${Q}/${LOC}-${NAME}-${Q}.onnx.json"

PERSIST A SETTING
  PLIST=~/Library/LaunchAgents/com.speakpro.daemon.plist
  /usr/libexec/PlistBuddy -c "Set :EnvironmentVariables:KEY VALUE" $PLIST
  launchctl unload $PLIST && launchctl load $PLIST
```
