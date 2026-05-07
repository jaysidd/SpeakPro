"""SpeakPro interactive TUI: control panel + cheatsheet.

No curses, no third-party deps — just menu + input loop. Designed for the
case where you have many terminals open and need a single place to:
  - see daemon status at a glance
  - change voice / rate without remembering CLI flags
  - copy-paste useful one-liners (file paths, launchctl, voice download)
"""
import os
import subprocess
import sys
from pathlib import Path

from . import client

HOME = Path.home()
VOICES_DIR = HOME / ".speakpro" / "voices"
LOG = HOME / ".speakpro" / "daemon.log"
PLIST = HOME / "Library" / "LaunchAgents" / "com.speakpro.daemon.plist"
PROJECT_DIR = HOME / "Projects" / "Tools" / "SpeakPro"
PIPER_BIN = HOME / "Library" / "Python" / "3.9" / "bin" / "piper"

# ANSI codes — kept inline so we don't pull in a deps.
B = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
RED = "\033[31m"
MAGENTA = "\033[35m"
R = "\033[0m"
CLEAR = "\033[2J\033[H"


def _status():
    try:
        return client.send({"op": "status"}, autostart=True)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _voices():
    if not VOICES_DIR.exists():
        return []
    return sorted(p.stem for p in VOICES_DIR.glob("*.onnx"))


def _wrap(label: str, value: str, width: int = 18) -> str:
    return f"  {DIM}{label:<{width}}{R}{value}"


def render(state: dict) -> None:
    print(CLEAR, end="")
    print(f"{B}{CYAN}━━━━━━━━━━━━━━━━━━━━━━ SpeakPro Control ━━━━━━━━━━━━━━━━━━━━━━{R}")

    if state.get("ok"):
        if state.get("paused"):
            badge = f"{YELLOW}⏸ paused{R}"
        elif state.get("playing"):
            badge = f"{GREEN}▶ playing{R}"
        else:
            badge = f"{DIM}■ idle{R}"
        print(_wrap("Backend:", f"{B}{state['backend']}{R}"))
        print(_wrap("Status:", f"{badge}    Queue: {state['queued']}"))
    else:
        print(f"  {RED}daemon unreachable: {state.get('error','?')}{R}")

    print()
    print(f"{B}ACTIONS{R}")
    print(f"  {YELLOW}1{R}  Speak clipboard now        {DIM}pbpaste | speakpro speak{R}")
    print(f"  {YELLOW}2{R}  Pause / resume             {DIM}speakpro toggle{R}")
    print(f"  {YELLOW}3{R}  Stop & clear queue         {DIM}speakpro stop{R}")
    print(f"  {YELLOW}4{R}  Skip current paragraph     {DIM}speakpro skip{R}")
    print(f"  {YELLOW}5{R}  Set speech rate")
    print(f"  {YELLOW}6{R}  Switch voice               {DIM}(lists installed voices){R}")
    print(f"  {YELLOW}7{R}  Test current voice         {DIM}plays a sample{R}")
    print(f"  {YELLOW}8{R}  Tail daemon log            {DIM}live error stream{R}")
    print(f"  {YELLOW}9{R}  Restart daemon (launchd reload)")
    print(f"  {YELLOW}q{R}  Quit")

    print()
    print(f"{B}iTERM2 HOTKEYS{R}  {DIM}(via Shortcuts.app){R}")
    print(f"  {MAGENTA}⌘⌃S{R} speak selection    {MAGENTA}⌘⇧P{R} pause/resume    {MAGENTA}⌘⇧X{R} stop")

    print()
    print(f"{B}CHEATSHEET{R}  {DIM}— select a line and copy it{R}")
    lines = [
        f"cd {PROJECT_DIR}",
        f"tail -f {LOG}",
        f"ls {VOICES_DIR}",
        f"open {PLIST.parent}",
        f"launchctl unload {PLIST} && launchctl load {PLIST}",
        f"/usr/libexec/PlistBuddy -c \"Print :EnvironmentVariables\" {PLIST}",
        f"/usr/libexec/PlistBuddy -c \"Set :EnvironmentVariables:SPEAKPRO_RATE 175\" {PLIST}",
        f"/usr/libexec/PlistBuddy -c \"Set :EnvironmentVariables:SPEAKPRO_PIPER_MODEL "
        f"$HOME/.speakpro/voices/en_US-ryan-high.onnx\" {PLIST}",
        f"# More voices: https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US",
    ]
    for line in lines:
        print(f"  {CYAN}{line}{R}")
    print()


def _prompt(label, default=None):
    suffix = f" [{default}]" if default else ""
    try:
        ans = input(f"{label}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    return ans or (default or "")


def _send_or_warn(cmd: dict) -> None:
    try:
        resp = client.send(cmd)
        if not resp.get("ok"):
            print(f"  {RED}error: {resp.get('error', '?')}{R}")
            input("  press enter to continue ")
    except Exception as e:
        print(f"  {RED}error: {e}{R}")
        input("  press enter to continue ")


def action_set_rate() -> None:
    print()
    print(f"  {DIM}suggestions: 140 slow / 175 normal / 200 brisk / 220 fast{R}")
    raw = _prompt("Rate", "175")
    if not raw:
        return
    try:
        rate = int(raw)
    except ValueError:
        print(f"  {RED}not a number{R}")
        input("  press enter to continue ")
        return
    _send_or_warn({"op": "set_rate", "rate": rate})


def action_switch_voice() -> None:
    voices = _voices()
    if not voices:
        print(f"\n  {RED}no .onnx voices found in {VOICES_DIR}{R}")
        print(f"  {DIM}download some from huggingface.co/rhasspy/piper-voices{R}")
        input("\n  press enter to continue ")
        return
    print()
    for i, v in enumerate(voices, 1):
        print(f"  {YELLOW}{i:>2}{R}  {v}")
    raw = _prompt("\nPick number")
    if not raw:
        return
    try:
        pick = int(raw)
    except ValueError:
        return
    if 1 <= pick <= len(voices):
        _send_or_warn({"op": "set_voice", "voice": voices[pick - 1]})


def action_test_voice() -> None:
    sample = (
        "This is a sample of the current voice. "
        "Listen for clarity and pace. If this sounds right, keep it. "
        "Otherwise, pick another voice from the menu."
    )
    _send_or_warn({"op": "speak", "text": sample, "replace": True})


def action_speak_clipboard() -> None:
    try:
        text = subprocess.run(
            ["pbpaste"], capture_output=True, text=True, errors="replace"
        ).stdout
    except FileNotFoundError:
        print(f"  {RED}pbpaste not found{R}")
        input("  press enter to continue ")
        return
    if not text.strip():
        print(f"  {DIM}clipboard is empty — copy something first{R}")
        input("  press enter to continue ")
        return
    _send_or_warn({"op": "speak", "text": text, "replace": True})


def action_tail_log() -> None:
    if not LOG.exists():
        print(f"  {DIM}no log yet at {LOG}{R}")
        input("  press enter to continue ")
        return
    print(f"\n  {DIM}Ctrl-C to return to menu{R}\n")
    try:
        subprocess.run(["tail", "-f", str(LOG)])
    except KeyboardInterrupt:
        pass


def action_restart_daemon() -> None:
    print(f"\n  {DIM}reloading launchd agent...{R}")
    subprocess.run(["launchctl", "unload", str(PLIST)], stderr=subprocess.DEVNULL)
    subprocess.run(["launchctl", "load", str(PLIST)])
    print(f"  {GREEN}done{R}")
    input("  press enter to continue ")


ACTIONS = {
    "1": action_speak_clipboard,
    "2": lambda: _send_or_warn({"op": "toggle"}),
    "3": lambda: _send_or_warn({"op": "stop"}),
    "4": lambda: _send_or_warn({"op": "skip"}),
    "5": action_set_rate,
    "6": action_switch_voice,
    "7": action_test_voice,
    "8": action_tail_log,
    "9": action_restart_daemon,
}


def main(argv=None) -> int:
    while True:
        render(_status())
        try:
            choice = input(f"Choose [1-9, q]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if choice in ("q", "quit", "exit"):
            return 0
        action = ACTIONS.get(choice)
        if action:
            action()


if __name__ == "__main__":
    sys.exit(main())
