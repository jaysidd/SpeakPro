"""Strip markdown/tool noise so TTS reads only what humans want to hear."""
import re
import unicodedata

CODE_FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
INLINE_CODE = re.compile(r"`([^`\n]+)`")
TOOL_BLOCK = re.compile(r"<(tool_use|tool_result|function_calls|invoke|parameter|fnresult)[^>]*>[\s\S]*?</\1>", re.IGNORECASE)
ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
URL = re.compile(r"https?://\S+")
PATH_HEAVY = re.compile(r"(?:^|\s)(/[\w./_-]{8,})")
HEADER = re.compile(r"^#{1,6}\s+", re.MULTILINE)
LIST_BULLET = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
NUMBERED = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)
EMOJI = re.compile(r"[\U0001F000-\U0001FFFF☀-➿]")
MULTI_BLANK = re.compile(r"\n{3,}")
EMPHASIS = re.compile(r"(\*\*|__|\*|_)(.+?)\1")
BACKTICK_RUN = re.compile(r"`+")
# Box-drawing, block elements, geometric shapes — speak poorly and clutter TTS.
BOX_DRAWING = re.compile(r"[─-▟■-◿]")
# Lone UTF-16 surrogates (Python's surrogateescape mechanism) and other
# unpaired surrogates make subprocess stdin encoding fail.
LONE_SURROGATE = re.compile(r"[\ud800-\udfff]")
# Bare control chars (except tab/newline) that pbpaste sometimes hands us.
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize_for_tts(text: str) -> str:
    """Last-mile safety: drop anything that won't survive UTF-8 encoding."""
    text = LONE_SURROGATE.sub("", text)
    text = BOX_DRAWING.sub(" ", text)
    text = CONTROL_CHARS.sub(" ", text)
    # NFKC normalization collapses fancy ligatures / fullwidth forms.
    text = unicodedata.normalize("NFKC", text)
    # Belt-and-suspenders — re-encode through utf-8 to drop anything else weird.
    return text.encode("utf-8", errors="replace").decode("utf-8")


def clean(text: str) -> str:
    """Make raw terminal/markdown text speakable.

    - Drops fenced code blocks and tool-use XML.
    - Inline code is unwrapped: "`foo`" -> "foo" (sentence stays grammatical).
    - Strips ANSI, headers, list markers, emoji.
    - Long URLs/paths replaced with short placeholders so TTS doesn't spell them.
    """
    text = _sanitize_for_tts(text)
    text = ANSI.sub("", text)
    text = TOOL_BLOCK.sub(" ", text)
    text = CODE_FENCE.sub(" (code block) ", text)
    text = INLINE_CODE.sub(r"\1", text)
    text = URL.sub("(link)", text)
    text = PATH_HEAVY.sub(" (path) ", text)
    text = HEADER.sub("", text)
    text = LIST_BULLET.sub("", text)
    text = NUMBERED.sub("", text)
    text = EMPHASIS.sub(r"\2", text)
    text = BACKTICK_RUN.sub("", text)
    text = EMOJI.sub("", text)
    text = MULTI_BLANK.sub("\n\n", text)
    return text.strip()


def split_paragraphs(text: str):
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
