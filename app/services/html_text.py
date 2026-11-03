"""Decode HTML entities in analyst-facing source text without changing meaning."""

from __future__ import annotations

import html
import re
from functools import lru_cache

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
_MAX_CACHED_CHARS = 2048


def _decode_text(value, preserve_line_breaks):
    text = html.unescape(str(value or ""))
    text = TAG_RE.sub(" ", text)
    if preserve_line_breaks:
        return "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()
    return " ".join(text.split())


@lru_cache(maxsize=1024)
def _decode_short_text(value, preserve_line_breaks):
    return _decode_text(value, preserve_line_breaks)


def decode_html_text(value: str | None, *, preserve_line_breaks: bool = False) -> str:
    # Only a literal text transformation is reused. No record, identity,
    # permission or review decision enters this bounded process-local cache.
    # Other inputs keep their original coercion and truth-value behavior.
    if (type(value) is str and len(value) <= _MAX_CACHED_CHARS
            and type(preserve_line_breaks) is bool):
        return _decode_short_text(value, preserve_line_breaks)
    return _decode_text(value, preserve_line_breaks)
