"""Decode HTML entities in analyst-facing source text without changing meaning."""

from __future__ import annotations

import html
import re

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def decode_html_text(value: str | None) -> str:
    text = html.unescape(str(value or ""))
    text = TAG_RE.sub(" ", text)
    return WS_RE.sub(" ", text).replace("\xa0", " ").strip()
