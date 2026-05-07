"""Thin client for the SpeakPro daemon."""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


SOCKET_PATH = Path(os.environ.get(
    "SPEAKPRO_SOCKET",
    str(Path.home() / ".speakpro" / "daemon.sock"),
))


def _connect(timeout: float = 1.0) -> socket.socket:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(str(SOCKET_PATH))
    return s


def send(cmd: dict, *, autostart: bool = True, timeout: float = 2.0) -> dict:
    if not SOCKET_PATH.exists():
        if autostart:
            _autostart_daemon()
        else:
            raise RuntimeError(f"daemon socket not found at {SOCKET_PATH}")

    last_err = None
    for _ in range(20):
        try:
            with _connect(timeout=timeout) as s:
                s.sendall((json.dumps(cmd) + "\n").encode())
                buf = b""
                while b"\n" not in buf:
                    chunk = s.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                line = buf.split(b"\n", 1)[0]
                return json.loads(line) if line else {"ok": False, "error": "no response"}
        except (FileNotFoundError, ConnectionRefusedError, socket.timeout) as e:
            last_err = e
            time.sleep(0.1)
    raise RuntimeError(f"could not reach daemon: {last_err}")


def _autostart_daemon():
    SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)
    log = open(SOCKET_PATH.with_suffix(".log"), "a")
    subprocess.Popen(
        [sys.executable, "-m", "speakpro.daemon"],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=log,
        start_new_session=True,
    )


def read_text(args) -> str:
    if args.text:
        return " ".join(args.text)
    if not sys.stdin.isatty():
        # Terminal selections regularly contain bytes that aren't valid UTF-8
        # (control sequences, partial multibyte characters). Reading via
        # sys.stdin.read() uses strict decoding and crashes; read raw bytes
        # and decode tolerantly so bad bytes become replacement characters
        # that the preprocessor can scrub.
        raw = sys.stdin.buffer.read()
        return raw.decode("utf-8", errors="replace")
    return ""


def cmd_speak(args):
    text = read_text(args)
    if not text.strip():
        print("speakpro: no text on stdin or args", file=sys.stderr)
        sys.exit(2)
    return send({
        "op": "speak",
        "text": text,
        "replace": not args.append,
    })


def cmd_simple(op):
    def run(args):
        return send({"op": op})
    return run


def cmd_status(args):
    return send({"op": "status"})


def main(argv=None):
    p = argparse.ArgumentParser(prog="speakpro", description="SpeakPro TTS client")
    sub = p.add_subparsers(dest="op", required=True)

    sp = sub.add_parser("speak", help="Speak text from stdin or args")
    sp.add_argument("text", nargs="*")
    sp.add_argument("--append", action="store_true",
                    help="Queue after current playback instead of replacing")
    sp.set_defaults(func=cmd_speak)

    for op, help_ in [
        ("stop", "Stop and clear queue"),
        ("skip", "Skip current paragraph"),
        ("pause", "Pause playback"),
        ("resume", "Resume playback"),
        ("toggle", "Pause/resume"),
        ("shutdown", "Stop daemon"),
    ]:
        s = sub.add_parser(op, help=help_)
        s.set_defaults(func=cmd_simple(op))

    s = sub.add_parser("status", help="Show daemon status")
    s.set_defaults(func=cmd_status)

    sr = sub.add_parser("rate", help="Set speech rate (words/min, e.g. 175)")
    sr.add_argument("rate", type=int)
    sr.set_defaults(func=lambda a: send({"op": "set_rate", "rate": a.rate}))

    sv = sub.add_parser("voice", help="Set voice (e.g. Samantha, Daniel, Karen, Ava)")
    sv.add_argument("voice")
    sv.set_defaults(func=lambda a: send({"op": "set_voice", "voice": a.voice}))

    ui = sub.add_parser("ui", help="Launch interactive control TUI")
    def _run_ui(_a):
        from . import tui
        return {"ok": True} if tui.main() == 0 else None
    ui.set_defaults(func=_run_ui)

    args = p.parse_args(argv)
    try:
        result = args.func(args)
    except RuntimeError as e:
        print(f"speakpro: {e}", file=sys.stderr)
        sys.exit(1)
    if result is not None:
        if not result.get("ok"):
            print(json.dumps(result), file=sys.stderr)
            sys.exit(1)
        if args.op == "status":
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
