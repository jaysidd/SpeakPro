"""Pluggable TTS backends. Default: macOS `say`. Future: Piper, Kokoro."""
import os
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod


class TTSBackend(ABC):
    @abstractmethod
    def speak(self, text: str) -> subprocess.Popen:
        """Start speaking and return a Popen handle the daemon can stop."""

    @property
    @abstractmethod
    def name(self) -> str: ...


class SayBackend(TTSBackend):
    """macOS `say`. Zero install, decent quality with Personal/Premium voices."""

    def __init__(self, voice: str = "Samantha", rate: int = 220):
        self.voice = voice
        self.rate = rate

    @property
    def name(self) -> str:
        return f"say:{self.voice}@{self.rate}"

    def set_rate(self, rate: int) -> None:
        self.rate = max(50, min(400, int(rate)))

    def set_voice(self, voice: str) -> None:
        self.voice = voice

    def speak(self, text: str) -> subprocess.Popen:
        # Drop lone surrogates / undecodable chars defensively — the
        # preprocessor should have done this already, but losing a worker
        # thread to a single bad byte is not worth the risk.
        payload = text.encode("utf-8", errors="replace")
        p = subprocess.Popen(
            ["say", "-v", self.voice, "-r", str(self.rate)],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        p.stdin.write(payload)
        p.stdin.close()
        return p


class PiperBackend(TTSBackend):
    """Piper neural TTS via the pip package. Synthesizes to a temp WAV
    and plays with macOS `afplay` so we don't need ffmpeg.

    Pause/resume work because SIGSTOP/SIGCONT are sent to the afplay process.
    """

    DEFAULT_PIPER_BIN_PATHS = [
        os.path.expanduser("~/Library/Python/3.9/bin/piper"),
        os.path.expanduser("~/Library/Python/3.10/bin/piper"),
        os.path.expanduser("~/Library/Python/3.11/bin/piper"),
        os.path.expanduser("~/Library/Python/3.12/bin/piper"),
        os.path.expanduser("~/Library/Python/3.13/bin/piper"),
        "/opt/homebrew/bin/piper",
        "/usr/local/bin/piper",
    ]

    def __init__(self, model_path: str, piper_bin: str = "", length_scale: float = 1.0):
        bin_path = piper_bin or shutil.which("piper") or ""
        if not bin_path:
            for candidate in self.DEFAULT_PIPER_BIN_PATHS:
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    bin_path = candidate
                    break
        if not bin_path or not os.path.isfile(bin_path):
            raise RuntimeError(
                "piper binary not found — install with: pip3 install --user piper-tts"
            )
        if not os.path.exists(model_path):
            raise RuntimeError(f"Piper model not found: {model_path}")
        self.piper_bin = bin_path
        self.model_path = model_path
        self.length_scale = float(length_scale)

    @property
    def name(self) -> str:
        return f"piper:{os.path.basename(self.model_path).replace('.onnx', '')}@ls={self.length_scale}"

    def set_rate(self, rate: int) -> None:
        # `say` uses words-per-minute; piper uses length-scale (>1 = slower).
        # Map the user's familiar wpm-style number onto length-scale: 175 ~ 1.0,
        # 140 ~ 1.25, 220 ~ 0.8, etc. Linear inverse around 175.
        rate = max(80, min(400, int(rate)))
        self.length_scale = round(175.0 / rate, 3)

    def set_voice(self, voice: str) -> None:
        """Switch model. `voice` is either a full path to an .onnx file or just
        a basename like 'en_US-amy-medium' inside ~/.speakpro/voices/."""
        if os.path.exists(voice):
            self.model_path = voice
            return
        candidate = os.path.expanduser(f"~/.speakpro/voices/{voice}")
        if not candidate.endswith(".onnx"):
            candidate += ".onnx"
        if not os.path.exists(candidate):
            raise RuntimeError(f"voice not found: {candidate}")
        self.model_path = candidate

    def speak(self, text: str) -> subprocess.Popen:
        wav_path = tempfile.mktemp(prefix="speakpro-", suffix=".wav")
        synth = subprocess.run(
            [self.piper_bin, "--model", self.model_path,
             "--output-file", wav_path,
             "--length-scale", str(self.length_scale)],
            input=text.encode("utf-8", errors="replace"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if synth.returncode != 0 or not os.path.exists(wav_path):
            raise RuntimeError(
                f"piper synth failed (rc={synth.returncode}): "
                f"{synth.stderr.decode('utf-8', errors='replace')[:300]}"
            )
        player = subprocess.Popen(
            ["afplay", wav_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        player._wav_tempfile = wav_path  # daemon cleans up after wait()
        return player


def make_backend(name: str = "say", **kwargs) -> TTSBackend:
    name = name.lower()
    if name == "say":
        return SayBackend(**kwargs)
    if name == "piper":
        return PiperBackend(**kwargs)
    raise ValueError(f"unknown backend: {name}")
