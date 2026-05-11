"""Strip markdown/tool noise so TTS reads only what humans want to hear.

Order matters in `clean()`: tool blocks and code fences come out first
(they contain content we never want re-processed), then structural
elements like tables / headers / lists, then inline elements, then
URLs/paths, then last-mile decoration cleanup.
"""
import re
import unicodedata

# --- Block-level patterns ---
TOOL_BLOCK = re.compile(
    r"<(tool_use|tool_result|function_calls|invoke|parameter|fnresult)[^>]*>[\s\S]*?</\1>",
    re.IGNORECASE,
)
# Fenced code with optional language: ```python\n...\n```
CODE_FENCE = re.compile(r"```([\w+.-]*)\n([\s\S]*?)```", re.MULTILINE)
# Bare triple-backtick fence with no newline (rare but seen)
BARE_FENCE = re.compile(r"```[\s\S]*?```")
INLINE_CODE = re.compile(r"`([^`\n]+)`")

ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# YAML/TOML front matter at file start
FRONT_MATTER = re.compile(r"\A---\n[\s\S]*?\n---\n")

# Markdown table lines: start AND end with a pipe (after trim)
TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP = re.compile(r"^\s*\|[\s:|-]+\|\s*$")

# Headers / structural
ATX_HEADER = re.compile(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
SETEXT_HEADER = re.compile(r"^([^\n]+)\n(=+|-+)\s*$", re.MULTILINE)
HORIZONTAL_RULE = re.compile(r"^\s*([-*_=])\1{2,}\s*$", re.MULTILINE)
BLOCKQUOTE = re.compile(r"^\s*>+\s?", re.MULTILINE)
TASK_CHECKBOX = re.compile(r"\[[ xX]\]\s*")
LIST_BULLET = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
NUMBERED = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)

# Inline elements
IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
INLINE_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
REF_LINK = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
REF_LINK_DEF = re.compile(r"^\s*\[[^\]]+\]:\s*\S.*$", re.MULTILINE)
FOOTNOTE_REF = re.compile(r"\[\^[^\]]+\]")
EMPHASIS = re.compile(r"(\*\*|__|\*|_)(.+?)\1")
STRIKETHROUGH = re.compile(r"~~(.+?)~~")
# Unpaired/leftover emphasis markers that survived EMPHASIS/STRIKETHROUGH —
# common when EMPHASIS partially consumed a decorative run like ******.
STRAY_EMPHASIS = re.compile(r"\*\*+|__+|~~+")
BACKTICK_RUN = re.compile(r"`+")

# URLs and filesystem paths
URL = re.compile(r"https?://\S+")
PATH_HEAVY = re.compile(r"(?:^|\s)(/[\w./_-]{8,})")

# Decoration / leftover junk
PUNCT_DECORATION = re.compile(r"([-=*_~])\1{2,}")
HTML_TAG = re.compile(r"<[^>]+>")
EMOJI = re.compile(r"[\U0001F000-\U0001FFFF☀-➿]")
MULTI_BLANK = re.compile(r"\n{3,}")
MULTI_SPACE = re.compile(r"[ \t]{2,}")

# Sanitization
BOX_DRAWING = re.compile(r"[─-▟■-◿]")
LONE_SURROGATE = re.compile(r"[\ud800-\udfff]")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Languages we'll name in code-block announcements (otherwise just "code block")
_LANG_NAMES = {
    "py": "Python", "python": "Python",
    "js": "JavaScript", "javascript": "JavaScript", "jsx": "JavaScript",
    "ts": "TypeScript", "typescript": "TypeScript", "tsx": "TypeScript",
    "go": "Go", "rs": "Rust", "rust": "Rust",
    "java": "Java", "kt": "Kotlin", "swift": "Swift",
    "c": "C", "cpp": "C plus plus", "cxx": "C plus plus", "h": "C header",
    "cs": "C sharp", "rb": "Ruby", "php": "PHP",
    "sh": "shell", "bash": "Bash", "zsh": "Zsh", "fish": "Fish",
    "sql": "SQL", "html": "HTML", "css": "CSS", "scss": "SCSS",
    "json": "JSON", "yaml": "YAML", "yml": "YAML", "toml": "TOML", "xml": "XML",
    "md": "Markdown", "markdown": "Markdown",
    "diff": "diff", "patch": "patch",
    "dockerfile": "Dockerfile", "make": "Makefile", "makefile": "Makefile",
}


def _sanitize_for_tts(text):
    """Last-mile safety: drop anything that won't survive UTF-8 encoding."""
    text = LONE_SURROGATE.sub("", text)
    text = BOX_DRAWING.sub(" ", text)
    text = CONTROL_CHARS.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    return text.encode("utf-8", errors="replace").decode("utf-8")


def _replace_code_fence(match):
    lang = match.group(1).strip().lower()
    if lang and lang in _LANG_NAMES:
        return f" ({_LANG_NAMES[lang]} code block) "
    if lang:
        return f" ({lang} code block) "
    return " (code block) "


def _readable_table(rows):
    """Convert table rows into spoken sentences. First row is treated as header."""
    if not rows:
        return ""
    n_cols = max(len(r) for r in rows)
    if len(rows) > 8 or n_cols > 6:
        body_rows = max(len(rows) - 1, 1)
        return f" (table with {body_rows} {'row' if body_rows == 1 else 'rows'}) "
    header, *body = rows
    if not body:
        return " Table: " + ", ".join(c for c in header if c.strip()) + ". "
    parts = ["Table with columns " + ", ".join(c for c in header if c.strip()) + "."]
    for i, row in enumerate(body, 1):
        cells = []
        for col, val in zip(header, row):
            v = val.strip()
            if v:
                cells.append(f"{col} is {v}" if col.strip() else v)
        if cells:
            parts.append(f"Row {i}: {'; '.join(cells)}.")
    return " " + " ".join(parts) + " "


def _strip_tables(text):
    """Find contiguous table blocks and replace with readable speech."""
    if "|" not in text:
        return text
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        if TABLE_LINE.match(lines[i]):
            j = i
            while j < len(lines) and TABLE_LINE.match(lines[j]):
                j += 1
            # Need at least 2 contiguous table lines to count as a real table
            if j - i >= 2:
                rows = []
                for line in lines[i:j]:
                    if TABLE_SEP.match(line):
                        continue
                    cells = [c.strip() for c in line.strip().strip("|").split("|")]
                    rows.append(cells)
                out.append(_readable_table(rows))
                i = j
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def clean(text):
    """Make raw terminal/markdown text speakable.

    Drops fenced code blocks, tool-use XML, tables, headers, list markers,
    horizontal rules, front matter, footnotes, link/image syntax,
    emphasis, strikethrough, ANSI escapes, and emoji. Inline code is
    unwrapped. Long URLs/paths get short placeholders.
    """
    text = _sanitize_for_tts(text)
    text = ANSI.sub("", text)
    text = TOOL_BLOCK.sub(" ", text)
    text = FRONT_MATTER.sub("", text)
    text = CODE_FENCE.sub(_replace_code_fence, text)
    text = BARE_FENCE.sub(" (code block) ", text)
    text = _strip_tables(text)
    # Setext before HR — they share `---`. Setext: end with sentence period.
    text = SETEXT_HEADER.sub(r"\1.", text)
    text = HORIZONTAL_RULE.sub("", text)
    text = ATX_HEADER.sub(r"\1.", text)
    text = REF_LINK_DEF.sub("", text)
    text = BLOCKQUOTE.sub("", text)
    text = TASK_CHECKBOX.sub("", text)
    text = LIST_BULLET.sub("", text)
    text = NUMBERED.sub("", text)
    text = IMAGE.sub(lambda m: f" (image{': ' + m.group(1) if m.group(1).strip() else ''}) ", text)
    text = INLINE_LINK.sub(r"\1", text)
    text = REF_LINK.sub(r"\1", text)
    text = FOOTNOTE_REF.sub("", text)
    text = INLINE_CODE.sub(r"\1", text)
    text = STRIKETHROUGH.sub(r"\1", text)
    text = EMPHASIS.sub(r"\2", text)
    text = STRAY_EMPHASIS.sub("", text)
    text = BACKTICK_RUN.sub("", text)
    text = URL.sub("(link)", text)
    text = PATH_HEAVY.sub(" (path) ", text)
    text = PUNCT_DECORATION.sub(" ", text)
    text = HTML_TAG.sub("", text)
    text = EMOJI.sub("", text)
    text = MULTI_BLANK.sub("\n\n", text)
    text = MULTI_SPACE.sub(" ", text)
    return text.strip()


def split_paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


# --- Sentence splitting (for inserting natural pauses between sentences) ---

# Common abbreviations whose trailing period must NOT end a sentence.
_ABBREVIATIONS = frozenset({
    "Mr", "Mrs", "Ms", "Dr", "Prof", "Sr", "Jr", "St",
    "vs", "etc", "Inc", "Ltd", "Co", "Corp",
    "Ave", "Blvd", "Rd", "Mt",
    "eg", "ie",
})

# Sentence boundary: a sentence-ending punctuation mark, preceded by a letter
# or closing punctuation (NOT a digit — protects version numbers like v1.0),
# followed by whitespace and the start of the next sentence.
_SENTENCE_BOUNDARY = re.compile(
    r"""(?<=[a-zA-Z"')\]])  # previous char: letter or closing punct
        ([.!?]+)            # capture sentence-ending punctuation
        \s+                 # consume whitespace
        (?=[A-Z"'(\[])      # next: uppercase or opening punct
    """,
    re.VERBOSE,
)


def _ends_with_abbreviation(s):
    """True if `s` ends with a known abbreviation (so the period isn't terminal)."""
    m = re.search(r"\b([A-Za-z]+)\.\s*[\"')\]]*$", s)
    if not m:
        return False
    word = m.group(1)
    if word in _ABBREVIATIONS:
        return True
    # Single-letter capitals like "U." in "U.S." — likely an abbreviation.
    if len(word) == 1 and word.isupper():
        return True
    return False


def split_sentences(paragraph):
    """Split one paragraph into sentences, guarding against common abbreviations.

    Imperfect by design — over-splitting is fine (a small extra pause is
    harmless), under-splitting is the problem we're solving.
    """
    if not paragraph or not paragraph.strip():
        return []
    parts = _SENTENCE_BOUNDARY.split(paragraph)
    # parts layout: [pre_text, punct1, mid_text, punct2, ..., post_text]
    # Each sentence i = parts[2i] + parts[2i+1]; trailing parts[-1] (if even index) is final fragment.
    raw = []
    for i in range(0, len(parts) - 1, 2):
        chunk = (parts[i] + parts[i + 1]).strip()
        if chunk:
            raw.append(chunk)
    if len(parts) % 2 == 1:
        tail = parts[-1].strip()
        if tail:
            raw.append(tail)
    # Merge back across boundaries that landed inside an abbreviation.
    merged = []
    for s in raw:
        if merged and _ends_with_abbreviation(merged[-1]):
            merged[-1] = merged[-1].rstrip() + " " + s
        else:
            merged.append(s)
    return merged


def split_for_speech(text, sentence_pause=0.4, paragraph_pause=0.7):
    """Return [(sentence, pause_after_seconds), ...] for queueing.

    Last item in the whole text has pause=0 (nothing to pause for).
    Last sentence in each non-final paragraph gets `paragraph_pause`.
    Every other sentence gets `sentence_pause`.
    """
    paragraphs = split_paragraphs(text) or ([text.strip()] if text.strip() else [])
    items = []
    for p_idx, para in enumerate(paragraphs):
        sentences = split_sentences(para) or [para]
        last_para = (p_idx == len(paragraphs) - 1)
        for s_idx, sent in enumerate(sentences):
            last_sent = (s_idx == len(sentences) - 1)
            if last_para and last_sent:
                pause = 0.0
            elif last_sent:
                pause = paragraph_pause
            else:
                pause = sentence_pause
            items.append((sent, pause))
    return items
