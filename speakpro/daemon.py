"""SpeakPro daemon: long-lived TTS server over a Unix socket.

Accepts newline-delimited JSON commands. Holds a playback queue so the user can
queue up multiple selections and skip between them.
"""
import json
import os
import signal
import socket
import sys
import threading
import time
from collections import deque
from pathlib import Path

from .preprocess import clean, split_for_speech
from .tts import make_backend, TTSBackend


# Default inter-utterance pauses (seconds). Combined with the natural
# ~150-250 ms gap from afplay/Piper startup, these produce roughly a
# half-second pause at sentence ends and ~one second at paragraph ends.
DEFAULT_SENTENCE_PAUSE = 0.4
DEFAULT_PARAGRAPH_PAUSE = 0.7


SOCKET_PATH = Path(os.environ.get(
    "SPEAKPRO_SOCKET",
    str(Path.home() / ".speakpro" / "daemon.sock"),
))
PID_PATH = SOCKET_PATH.with_suffix(".pid")
LOG_PATH = SOCKET_PATH.with_suffix(".log")


class Player:
    """Owns the current subprocess and a queue of pending paragraphs."""

    def __init__(self, backend: TTSBackend):
        self.backend = backend
        self.lock = threading.Lock()
        # Queue items: (text, pause_after_seconds)
        self.queue: deque = deque()
        self.current = None  # Popen
        self.worker: threading.Thread | None = None
        self.paused = False
        self.sentence_pause = DEFAULT_SENTENCE_PAUSE
        self.paragraph_pause = DEFAULT_PARAGRAPH_PAUSE

    def status(self) -> dict:
        with self.lock:
            return {
                "backend": self.backend.name,
                "playing": self.current is not None and self.current.poll() is None,
                "paused": self.paused,
                "queued": len(self.queue),
            }

    def enqueue(self, text: str, *, replace: bool = False) -> int:
        items = split_for_speech(
            text,
            sentence_pause=self.sentence_pause,
            paragraph_pause=self.paragraph_pause,
        )
        if not items:
            return 0
        with self.lock:
            if replace:
                self.queue.clear()
                self._stop_current_locked()
            self.queue.extend(items)
            if not self.worker or not self.worker.is_alive():
                self.worker = threading.Thread(target=self._run, daemon=True)
                self.worker.start()
        return len(items)

    def _run(self):
        import traceback
        while True:
            with self.lock:
                if not self.queue:
                    return
                text, pause_after = self.queue.popleft()
                try:
                    self.current = self.backend.speak(text)
                    proc = self.current
                except Exception:
                    # One bad sentence must not kill the worker — log and skip.
                    sys.stderr.write(
                        f"speakpro: skipping sentence (backend error)\n"
                        f"{traceback.format_exc()}"
                    )
                    self.current = None
                    continue
            try:
                proc.wait()
            except Exception:
                pass
            # Backend may have stashed a temp file path on the proc handle for cleanup.
            tmp = getattr(proc, "_wav_tempfile", None)
            if tmp:
                try:
                    os.remove(tmp)
                except FileNotFoundError:
                    pass
            # Negative returncode → killed by signal (skip/stop). Don't pad
            # the gap when the user explicitly asked to move on.
            killed = proc.returncode is not None and proc.returncode < 0
            with self.lock:
                self.current = None
                # Only sleep if there's more in the queue — don't pad the tail.
                more_queued = bool(self.queue)
            if pause_after > 0 and more_queued and not killed:
                time.sleep(pause_after)

    def _stop_current_locked(self):
        if self.current and self.current.poll() is None:
            try:
                # Kill helper process tree (piper -> ffplay)
                helper = getattr(self.current, "_piper_handle", None)
                if helper and helper.poll() is None:
                    helper.terminate()
                self.current.terminate()
                try:
                    self.current.wait(timeout=1.5)
                except Exception:
                    self.current.kill()
            except ProcessLookupError:
                pass
        self.current = None

    def stop(self):
        with self.lock:
            self.queue.clear()
            self._stop_current_locked()
            self.paused = False

    def skip(self):
        with self.lock:
            self._stop_current_locked()

    def pause(self):
        # `say` doesn't expose pause; SIGSTOP works on the child process.
        with self.lock:
            if self.current and self.current.poll() is None and not self.paused:
                try:
                    os.kill(self.current.pid, signal.SIGSTOP)
                    helper = getattr(self.current, "_piper_handle", None)
                    if helper and helper.poll() is None:
                        os.kill(helper.pid, signal.SIGSTOP)
                    self.paused = True
                except ProcessLookupError:
                    pass

    def resume(self):
        with self.lock:
            if self.current and self.paused:
                try:
                    os.kill(self.current.pid, signal.SIGCONT)
                    helper = getattr(self.current, "_piper_handle", None)
                    if helper and helper.poll() is None:
                        os.kill(helper.pid, signal.SIGCONT)
                    self.paused = False
                except ProcessLookupError:
                    pass

    def toggle(self):
        with self.lock:
            playing = self.current is not None and self.current.poll() is None
            paused = self.paused
        if playing and not paused:
            self.pause()
        elif playing and paused:
            self.resume()


def handle_command(player: Player, cmd: dict) -> dict:
    op = cmd.get("op")
    if op == "speak":
        text = clean(cmd.get("text", ""))
        if not text:
            return {"ok": False, "error": "empty text after cleaning"}
        n = player.enqueue(text, replace=cmd.get("replace", True))
        return {"ok": True, "queued": n}
    if op == "stop":
        player.stop()
        return {"ok": True}
    if op == "skip":
        player.skip()
        return {"ok": True}
    if op == "pause":
        player.pause()
        return {"ok": True}
    if op == "resume":
        player.resume()
        return {"ok": True}
    if op == "toggle":
        player.toggle()
        return {"ok": True}
    if op == "status":
        return {"ok": True, **player.status()}
    if op == "set_rate":
        rate = cmd.get("rate")
        if not isinstance(rate, (int, float)):
            return {"ok": False, "error": "rate must be a number"}
        setter = getattr(player.backend, "set_rate", None)
        if not setter:
            return {"ok": False, "error": f"backend {player.backend.name} has no rate control"}
        setter(rate)
        return {"ok": True, "backend": player.backend.name}
    if op == "set_voice":
        voice = cmd.get("voice", "")
        setter = getattr(player.backend, "set_voice", None)
        if not setter:
            return {"ok": False, "error": f"backend {player.backend.name} has no voice control"}
        setter(voice)
        return {"ok": True, "backend": player.backend.name}
    if op == "shutdown":
        player.stop()
        return {"ok": True, "shutdown": True}
    return {"ok": False, "error": f"unknown op: {op}"}


def serve(backend_name: str = "say", **backend_kwargs):
    SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()
    PID_PATH.write_text(str(os.getpid()))

    backend = make_backend(backend_name, **backend_kwargs)
    player = Player(backend)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(SOCKET_PATH))
    os.chmod(SOCKET_PATH, 0o600)
    sock.listen(8)

    log = open(LOG_PATH, "a", buffering=1)
    log.write(f"speakpro daemon up backend={backend.name} sock={SOCKET_PATH}\n")

    shutdown = threading.Event()

    def shutdown_handler(signum, frame):
        shutdown.set()
        try:
            sock.close()
        except Exception:
            pass

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    try:
        while not shutdown.is_set():
            try:
                conn, _ = sock.accept()
            except OSError:
                break
            threading.Thread(
                target=_serve_conn, args=(conn, player, log, shutdown), daemon=True
            ).start()
    finally:
        player.stop()
        try:
            SOCKET_PATH.unlink()
        except FileNotFoundError:
            pass
        try:
            PID_PATH.unlink()
        except FileNotFoundError:
            pass
        log.write("speakpro daemon down\n")
        log.close()


def _serve_conn(conn: socket.socket, player: Player, log, shutdown: threading.Event):
    with conn:
        buf = b""
        try:
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        cmd = json.loads(line)
                    except json.JSONDecodeError as e:
                        conn.sendall(json.dumps({"ok": False, "error": str(e)}).encode() + b"\n")
                        continue
                    resp = handle_command(player, cmd)
                    log.write(f"cmd={cmd.get('op')} resp={resp}\n")
                    conn.sendall(json.dumps(resp).encode() + b"\n")
                    if resp.get("shutdown"):
                        shutdown.set()
                        # Wake the main accept() loop by self-connecting,
                        # then unblock it via socket close.
                        try:
                            os.kill(os.getpid(), signal.SIGTERM)
                        except Exception:
                            pass
                        return
        except (BrokenPipeError, ConnectionResetError):
            pass


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="SpeakPro TTS daemon")
    p.add_argument("--backend", default=os.environ.get("SPEAKPRO_BACKEND", "say"),
                   choices=["say", "piper"])
    p.add_argument("--voice", default=os.environ.get("SPEAKPRO_VOICE", "Samantha"))
    p.add_argument("--rate", type=int, default=int(os.environ.get("SPEAKPRO_RATE", "220")))
    p.add_argument("--model", default=os.environ.get("SPEAKPRO_PIPER_MODEL", ""),
                   help="Piper .onnx model path (when --backend piper)")
    args = p.parse_args(argv)

    kwargs = {}
    if args.backend == "say":
        kwargs = {"voice": args.voice, "rate": args.rate}
    else:
        model = args.model or os.path.expanduser(
            "~/.speakpro/voices/en_US-amy-medium.onnx"
        )
        if not os.path.exists(model):
            print(f"piper model not found: {model}", file=sys.stderr)
            sys.exit(2)
        kwargs = {"model_path": model}
        # Map SPEAKPRO_RATE (wpm-ish) to piper length-scale at startup.
        env_rate = os.environ.get("SPEAKPRO_RATE")
        if env_rate:
            kwargs["length_scale"] = round(175.0 / max(80, min(400, int(env_rate))), 3)

    serve(args.backend, **kwargs)


if __name__ == "__main__":
    main()
