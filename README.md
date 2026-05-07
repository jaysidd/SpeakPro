# SpeakPro

**Highlight any text in your Mac terminal, hit a hotkey, hear it spoken in a natural neural voice.** A lightweight, fully-local text-to-speech (TTS) add-on for **iTerm2** (and Terminal.app, Warp, Ghostty, kitty — anything that copies selection to clipboard) built around the [Piper](https://github.com/rhasspy/piper) neural TTS engine.

> Designed to be the missing "speaker icon" you have in Claude Desktop / ChatGPT — but for the terminal.

```
   you select text in iTerm2
              │
              ▼
       ⌘⌃S  (hotkey)
              │
              ▼
   speakpro daemon strips code blocks,
   ANSI escapes, tool XML, long URLs
              │
              ▼
   Piper neural TTS  →  afplay  →  your speakers
```

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![macOS](https://img.shields.io/badge/macOS-13%2B-blue)
![Apple Silicon](https://img.shields.io/badge/Apple%20Silicon-arm64-orange)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![offline](https://img.shields.io/badge/offline-100%25-success)

---

## Why SpeakPro

**Claude Desktop, ChatGPT, and Perplexity all have a speaker icon next to each AI response — press it, hear the answer.** macOS terminals don't. If you spend hours in iTerm2 with Claude Code, Cursor's terminal, the OpenAI CLI, or any AI tool that streams text to your shell, you have no easy way to *listen* to those responses.

SpeakPro fills that gap. It runs as a tiny background daemon (Unix socket, ~50 ms cold start), accepts text on stdin, strips terminal noise (code fences, tool calls, ANSI color codes, long file paths), and speaks the rest with a high-quality neural voice that runs entirely on your Mac. No cloud, no API keys, no telemetry, no subscription.

---

## What it sounds like

Voices ship via the Piper open-source catalog ([listen to samples here](https://rhasspy.github.io/piper-samples/)). Default install includes:

| Voice | Locale | Vibe |
|---|---|---|
| `en_US-amy-medium` | US female | Warm conversational — default |
| `en_US-ryan-high` | US male | Polished, clear, "AI assistant" feel |
| `en_GB-alan-medium` | UK male | Neutral British |

Hundreds more available — multi-speaker, multilingual, child voices, audiobook narrators. Drop a `.onnx` into `~/.speakpro/voices/` and it's available immediately.

---

## Real-world scenarios

These are the use cases SpeakPro was built for. If any of these sound like your day, this tool will pay back its install time inside an hour:

- **Listening to AI assistant responses** while walking, driving, or doing dishes — you no longer have to stay glued to the terminal to hear what Claude Code or the OpenAI CLI just generated.
- **Code review on long debugging sessions** — give your eyes a break by ear-reading function summaries, error logs, or PR descriptions piped from `gh pr view`.
- **Accessibility** — for developers with dyslexia, low vision, or chronic eye strain, hearing terminal output is dramatically faster and less fatiguing than reading it.
- **Documentation & man pages** — `man curl | speakpro speak` and listen while you keep typing.
- **Learning a new language or dialect** — switch to a British, Indian, or German voice and use the terminal as a passive listening source.
- **ESL professionals** — hear how unfamiliar technical terms are pronounced.
- **Pair programming with yourself** — sometimes hearing your own commit messages or function comments read aloud surfaces typos and ambiguity that scanning misses.
- **Remote / distributed teams** — paste a Slack message into the terminal and have it read aloud on speakerphone for a meeting.
- **Long-running build & test loops** — pipe `make test` failures into SpeakPro for an audio summary while you switch contexts.
- **Reading articles in `w3m` or `lynx`** — narrate web content from the terminal without leaving your keyboard flow.
- **Note review** — `cat ~/notes/today.md | speakpro speak` to hear yesterday's notes during a morning walk.

---

## Features

- **System-wide hotkey** — `⌘⌃S` reads the current selection from any Mac app, not just iTerm2.
- **Smart text cleaning** — strips Markdown code fences, inline code, tool-use XML, ANSI color codes, long URLs, file paths, headings, list bullets, emoji, and lone Unicode surrogates *before* sending to TTS. You won't hear "backtick backtick backtick python."
- **Pause / resume / skip / stop** via hotkeys or CLI. Real `SIGSTOP`/`SIGCONT` pause — not a fake "wait until queue ends."
- **Pluggable TTS backends** — ships with macOS `say` and Piper. Drop-in interface for Kokoro, F5-TTS, or any future neural TTS.
- **Paragraph-level queue** — long answers are spoken one paragraph at a time, so you can `speakpro skip` past the part you don't care about.
- **Robust to bad bytes** — terminal selections often contain partial multi-byte chars or escape sequences. SpeakPro sanitizes lone surrogates, control bytes, and box-drawing chars so a single bad byte never kills playback mid-paragraph.
- **Long-lived daemon** — neural model stays warm in memory; auto-starts on login via launchd; auto-restarts on crash; clean shutdown sticks.
- **Interactive TUI** — `speakpro ui` opens a single-screen control panel with status, voice picker, rate control, and a paste-ready cheatsheet of file paths.
- **Fully local, fully private** — no network, no telemetry, no API key.

---

## Comparison

| | macOS Speak Selection | Cloud TTS (ElevenLabs / OpenAI) | **SpeakPro** |
|---|---|---|---|
| Strips code/tool/ANSI noise | ❌ | ❌ | ✅ |
| Works on terminal selection | ⚠ partial | ❌ | ✅ |
| Pause / resume / skip from hotkey | ⚠ overlay UI | ❌ | ✅ |
| Voice quality | classic robotic | top-tier | **near-top-tier (Piper)** |
| Privacy | local | cloud | **local** |
| Recurring cost | $0 | $$ | **$0** |
| Latency | instant | network round-trip | **~1 sec (model load)** |
| Works offline | ✅ | ❌ | ✅ |

---

## Quick install

```bash
git clone https://github.com/jaysidd/SpeakPro.git ~/Projects/Tools/SpeakPro
cd ~/Projects/Tools/SpeakPro
./install.sh
```

This:
1. Symlinks `speakpro`, `speakpro-daemon`, and three iTerm2 hotkey scripts into `~/.local/bin`.
2. Installs a `launchd` agent so the daemon auto-starts at login (and auto-restarts on crash, but **not** after a clean `speakpro shutdown`).
3. Prints next steps.

Make sure `~/.local/bin` is on your `PATH`:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

### Add the neural voice (recommended)

```bash
# Piper (the Python wheel ships everything, including the native libs)
pip3 install --user piper-tts

# A high-quality starter voice (~63 MB)
mkdir -p ~/.speakpro/voices && cd ~/.speakpro/voices
curl -fL -O https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx
curl -fL -O https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json

# Switch the daemon to Piper
PLIST=~/Library/LaunchAgents/com.speakpro.daemon.plist
/usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:SPEAKPRO_BACKEND string piper" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:SPEAKPRO_PIPER_MODEL string $HOME/.speakpro/voices/en_US-amy-medium.onnx" "$PLIST"
launchctl unload "$PLIST" && launchctl load "$PLIST"
```

(If `Add` fails because the key already exists, use `Set` instead.)

### Bind the iTerm2 hotkey

See [docs/iterm2-setup.md](docs/iterm2-setup.md). 30-second version using **macOS Shortcuts.app**:

1. iTerm2 → Settings → General → Selection → ☑ "Copy to clipboard on selection"
2. Open **Shortcuts.app** → New Shortcut named "Speak Selection" → action **Run Shell Script** with body `~/.local/bin/speak-selection.sh`
3. Click the `i` info button → ☑ Use as Quick Action, ☑ Services Menu
4. System Settings → Keyboard → Keyboard Shortcuts → Services → assign `⌘⌃S`

Repeat for `~/.local/bin/speak-toggle.sh` (`⌘⇧P`) and `~/.local/bin/speak-stop.sh` (`⌘⇧X`).

---

## Daily usage

### Hotkeys

| Hotkey | Action |
|---|---|
| `⌘⌃S` | Speak the currently selected text |
| `⌘⇧P` | Pause / resume |
| `⌘⇧X` | Stop and clear queue |

### CLI

```bash
echo "hello" | speakpro speak       # speak from stdin
speakpro speak "hello there"        # speak from args
pbpaste | speakpro speak            # speak the clipboard

speakpro pause / resume / toggle / skip / stop
speakpro status                     # JSON: backend, playing, paused, queued
speakpro voice en_US-ryan-high      # switch voice (any .onnx in ~/.speakpro/voices/)
speakpro rate 175                   # set rate (140 slow, 175 normal, 220 fast)
speakpro shutdown                   # stop the daemon
```

### TUI — when you forget commands

```bash
speakpro ui
```

A single-screen control panel showing status, numbered actions, hotkeys, and a copy-paste cheatsheet of file locations. Designed for "I have 7 terminals open and I forget where things live."

---

## Voices

Pick before you download by listening at the official samples site:
**https://rhasspy.github.io/piper-samples/**

Once you've picked one, get its `<locale>-<name>-<quality>` id (e.g. `en_US-libritts-high`) and download from HuggingFace:

```bash
cd ~/.speakpro/voices && \
LOC=en_US NAME=libritts Q=high && \
curl -fL -O "https://huggingface.co/rhasspy/piper-voices/resolve/main/${LOC%_*}/${LOC}/${NAME}/${Q}/${LOC}-${NAME}-${Q}.onnx" && \
curl -fL -O "https://huggingface.co/rhasspy/piper-voices/resolve/main/${LOC%_*}/${LOC}/${NAME}/${Q}/${LOC}-${NAME}-${Q}.onnx.json"
```

Then `speakpro voice en_US-libritts-high` to switch.

Notable voices:

- `en_US-amy-medium` — natural female, modest size
- `en_US-ryan-high` — best male, larger model
- `en_US-libritts-high` — multi-speaker, very versatile
- `en_US-lessac-high` — audiobook clarity (female)
- `en_GB-alan-medium` — polished British male
- `en_GB-northern_english_male-medium` — distinct regional accent
- `en_US-hfc_male-medium` — alternate American male

---

## Architecture

```
iTerm2 selection ──Cmd+Ctrl+S──► macOS Shortcut ──► speak-selection.sh
                                                          │
                                                       pbpaste
                                                          ▼
                                                   speakpro speak
                                                  (CLI client, JSON
                                                   over Unix socket)
                                                          │
                                                          ▼
                                                  speakpro daemon
                                                 ┌──────────────────┐
                                                 │ preprocess: drop │
                                                 │ code, tool XML,  │
                                                 │ ANSI, surrogates │
                                                 ├──────────────────┤
                                                 │ paragraph queue  │
                                                 ├──────────────────┤
                                                 │ TTS backend      │
                                                 │  └─ Piper        │
                                                 │     └─ temp WAV  │
                                                 │        └─ afplay │
                                                 └──────────────────┘
```

**Why this design:**

- **Selection-based capture** — the user picks what's narrated. No fragile screen scraping.
- **Long-lived daemon** — neural model stays warm; first-paragraph latency is ~1 sec, subsequent paragraphs are immediate.
- **Unix socket protocol** (newline-delimited JSON) — fast, local, no port conflicts, no firewall prompts.
- **`SIGSTOP`/`SIGCONT`** on the playback subprocess gives true pause/resume even though `say` and `afplay` don't expose it natively.
- **Per-paragraph isolation** — a bad byte in paragraph 2 doesn't kill paragraphs 3, 4, 5.

---

## Configuration

All persistent settings live in the launchd plist at `~/Library/LaunchAgents/com.speakpro.daemon.plist`:

| Env var | Purpose | Example |
|---|---|---|
| `SPEAKPRO_BACKEND` | `say` or `piper` | `piper` |
| `SPEAKPRO_PIPER_MODEL` | Absolute path to `.onnx` voice file | `~/.speakpro/voices/en_US-amy-medium.onnx` |
| `SPEAKPRO_RATE` | Speech rate (wpm-style int) | `175` |
| `SPEAKPRO_VOICE` | Voice name for `say` backend | `Samantha` |

To change one and reload:

```bash
PLIST=~/Library/LaunchAgents/com.speakpro.daemon.plist
/usr/libexec/PlistBuddy -c "Set :EnvironmentVariables:SPEAKPRO_RATE 175" "$PLIST"
launchctl unload "$PLIST" && launchctl load "$PLIST"
```

Runtime-only changes (don't survive daemon restart): `speakpro rate <N>` and `speakpro voice <name>`.

---

## Troubleshooting

| Symptom | Try |
|---|---|
| Hotkey does nothing | `speakpro status` — if "could not reach daemon", run `speakpro speak "test"` once; the daemon auto-starts on first call. |
| Speech stops mid-paragraph | `tail ~/.speakpro/daemon.log`. Bad clipboard bytes *should* be sanitized; the log is the proof. |
| Selection isn't being read | iTerm2 → Settings → General → Selection → ☑ "Copy to clipboard on selection" |
| Wrong voice playing | `speakpro status`. Plist may have a different startup default than your runtime change. |
| Daemon respawns after `shutdown` | Edit the plist's `KeepAlive` to `<dict><key>SuccessfulExit</key><false/></dict>` (already set if installer ran after May 2026). |
| Piper not found | `pip3 install --user piper-tts` and ensure `~/Library/Python/3.9/bin` is on PATH. |

The TUI's option **8** ("Tail daemon log") is the fastest way to see what the daemon is actually doing.

---

## Roadmap

- **Kokoro TTS backend** — newer, ~80M params, even more natural. Drop-in with the existing `TTSBackend` interface.
- **Menubar widget** — current voice + transport in the macOS menu bar.
- **Whisper Desk integration** — single chord toggles dictation (Whisper → terminal stdin) and narration (selection → SpeakPro).
- **"Narrate last response" mode** — tee Claude Code stdout into a ring buffer; one hotkey reads the most recent block without manual selection.
- **Localhost web UI** — voice picker with sample buttons.
- **Linux port** — daemon is portable; only the `pbpaste`/`afplay`/`launchd` shims need swapping.

---

## FAQ

**Q: Does SpeakPro send my terminal text to a server?**
No. Everything runs locally on your Mac. There's no network call anywhere in the speak path.

**Q: Will it work with the built-in macOS `say` voices instead of Piper?**
Yes. Set `SPEAKPRO_BACKEND=say` in the launchd plist (no Piper install required). Quality is lower but install is zero.

**Q: Does it work on Intel Macs?**
The architecture is portable, but the bundled Piper wheel targets `arm64`. On Intel, install the `x86_64` wheel from PyPI (`pip3 install --user piper-tts` should pick the right one) — same workflow.

**Q: Can I use it outside iTerm2?**
Yes. The `⌘⌃S` macOS Shortcut works in any app — Safari, Mail, Notes, your IDE, anywhere.

**Q: How big is the install?**
~3 MB of code + 60–120 MB per voice. The default Amy voice is 63 MB.

**Q: Does pause actually pause, or does it queue and finish?**
True pause — `SIGSTOP` is sent to the playback subprocess. Resume sends `SIGCONT`. Tested with both `say` and Piper-via-`afplay`.

**Q: Why isn't this on Homebrew?**
It might be later. For now, `git clone && ./install.sh` is the path.

**Q: Can it read non-English text?**
Yes — Piper has voices for German, French, Spanish, Italian, Polish, Russian, Hindi, Arabic, Mandarin, and many more. Same install path, just pick a different voice id.

**Q: How do I uninstall?**

```bash
launchctl unload ~/Library/LaunchAgents/com.speakpro.daemon.plist
rm ~/Library/LaunchAgents/com.speakpro.daemon.plist
rm ~/.local/bin/speakpro ~/.local/bin/speakpro-daemon ~/.local/bin/speak-*.sh
rm -rf ~/.speakpro
# Optionally: rm -rf ~/Projects/Tools/SpeakPro
```

---

## Project layout

```
SpeakPro/
├── README.md
├── LICENSE
├── install.sh                      # symlinks + launchd registration
├── bin/
│   ├── speakpro                    # CLI launcher
│   ├── speakpro-daemon             # daemon launcher
│   ├── speak-selection.sh          # iTerm2/Shortcuts hotkey: pbpaste → speak
│   ├── speak-toggle.sh             # pause/resume hotkey
│   └── speak-stop.sh               # stop hotkey
├── speakpro/
│   ├── __init__.py
│   ├── __main__.py                 # python -m speakpro
│   ├── client.py                   # CLI argparse + Unix socket client
│   ├── daemon.py                   # Unix socket server, queue, signals
│   ├── tts.py                      # SayBackend, PiperBackend
│   ├── preprocess.py               # markdown / tool / ANSI stripping
│   └── tui.py                      # interactive control panel
├── docs/
│   └── iterm2-setup.md             # exhaustive hotkey-binding guide
└── KB/
    └── SpeakPro-Guide.md           # printable founder's reference
```

---

## Contributing

Bug reports and PRs welcome. Useful contribution areas:

- New TTS backends (Kokoro, F5-TTS, XTTS-v2, ElevenLabs adapter for those who want cloud quality).
- Linux/Windows port of the OS shims.
- Additional preprocessors (e.g. expand abbreviations, spell-out numbers).
- Voice model packaging / curation.

Open an issue first if you're planning a substantial change.

---

## License

[MIT](LICENSE) — do whatever, no warranty.

## Author

Built by **Junaid Siddiqi** ([@jaysidd](https://github.com/jaysidd)) because Claude Desktop has a speaker icon and iTerm2 doesn't.

If SpeakPro is useful to you, a ⭐ on the repo helps other people find it.

---

## Keywords

macOS text-to-speech, iTerm2 TTS, terminal narration, Piper neural TTS, Claude Code voice, AI assistant speak aloud, accessibility for developers, dyslexia developer tools, local TTS macOS, offline TTS Apple Silicon, M1 M2 M3 M4 TTS, speak selection terminal, hear claude responses, neural voice macOS, free ChatGPT voice alternative, OpenAI CLI text to speech, narrate terminal output, eyes-free coding, screen reader iTerm2, macos shortcuts speak, voice for iterm.
