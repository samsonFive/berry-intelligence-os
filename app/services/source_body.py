"""Classify persisted source artifacts for publication review.

This module does not fetch URLs and does not invent article text.
"""

from __future__ import annotations

from typing import Any

from app.services.html_text import decode_html_text
from app.services.intelligence_feed import article_paragraphs

INTERSTITIAL_SIGNALS = (
    "before you continue to google",
    "consent.google.com",
    "we use cookies and data to",
    "privacy reminder",
    "i agree to the use of cookies",
    "enable cookies",
    "cookie policy",
    "verify you are a human",
    "unusual traffic from your computer network",
    "checking your browser before accessing",
    "attention required! | cloudflare",
    "access to this page has been denied",
    "please log in to continue",
    "sign in to continue",
    "subscribe to continue reading",
    "this content is for subscribers only",
)

BODY_STATE_LABELS = {
    "body_available": "BODY AVAILABLE",
    "body_partial": "BODY PARTIAL",
    "description_only": "DESCRIPTION ONLY",
    "transcript_available": "TRANSCRIPT AVAILABLE",
    "body_unavailable": "BODY UNAVAILABLE",
    "access_limited": "ACCESS-LIMITED",
    "interstitial": "CONSENT / INTERSTITIAL / BOT WALL",
}


def article_full_text(record: dict[str, Any]) -> str:
    paragraphs = article_paragraphs(record)
    if paragraphs:
        return "\n\n".join(decode_html_text(row.get("text") or "") for row in paragraphs if row.get("text"))
    article = record.get("article") if isinstance(record.get("article"), dict) else {}
    return decode_html_text(article.get("full_text") if isinstance(article, dict) else "")


def looks_like_interstitial(text: str) -> bool:
    haystack = decode_html_text(text).casefold()
    if not haystack:
        return False
    return any(signal in haystack for signal in INTERSTITIAL_SIGNALS)


def classify_source_body(record: dict[str, Any]) -> dict[str, Any]:
    body = article_full_text(record)
    excerpt = decode_html_text(record.get("transcript_excerpt") or "")
    publisher = decode_html_text(record.get("publisher_description") or "")
    summary = decode_html_text(record.get("summary") or "")
    transcript = record.get("transcript") if isinstance(record.get("transcript"), dict) else {}
    transcript_text = ""
    if transcript:
        segments = transcript.get("segments") or []
        if isinstance(segments, list):
            transcript_text = "\n".join(
                decode_html_text(seg.get("text") if isinstance(seg, dict) else str(seg))
                for seg in segments
            )
        else:
            transcript_text = decode_html_text(transcript.get("text") or "")
    combined_wall_text = " ".join(part for part in (body, publisher, summary) if part)
    if body and looks_like_interstitial(body):
        state = "interstitial"
    elif looks_like_interstitial(combined_wall_text) and not body:
        state = "interstitial"
    elif body and len(body) >= 400:
        state = "body_available"
    elif body:
        state = "body_partial"
    elif transcript_text.strip() or (record.get("media_format") in {"podcast", "video", "conference_video"} and excerpt):
        state = "transcript_available"
    elif publisher and not body:
        state = "description_only"
    else:
        discovery = record.get("discovery_provenance") or {}
        failure = str(discovery.get("failure_category") or "").casefold()
        if failure in {"paywall", "blocked", "http_error", "empty_body"}:
            state = "access_limited"
        else:
            state = "body_unavailable"
    return {
        "state": state,
        "label": BODY_STATE_LABELS[state],
        "body": body,
        "publisher_description": publisher,
        "excerpt": excerpt,
        "transcript_text": decode_html_text(transcript_text),
        "word_count": int(((record.get("article") or {}) if isinstance(record.get("article"), dict) else {}).get("word_count") or 0),
        "acquisition": ((record.get("article") or {}) if isinstance(record.get("article"), dict) else {}).get("acquisition") or {},
        "usable_in_app": state in {"body_available", "body_partial", "transcript_available"},
        "warning": (
            "Source body unavailable in-app. Review original source before publishing."
            if state in {"interstitial", "access_limited", "body_unavailable"}
            else ""
        ),
    }


def atomic_extraction_source_text(record: dict[str, Any]) -> str:
    """Text a later qualified Atomic extractor should receive.

    Prefer persisted article paragraphs, then transcript, never the thin
    publication summary when richer source text exists.
    """

    body = classify_source_body(record)
    if body["state"] == "interstitial":
        return ""
    if body["body"]:
        return body["body"]
    if body["transcript_text"]:
        return body["transcript_text"]
    if body["excerpt"]:
        return body["excerpt"]
    return decode_html_text(record.get("summary") or "")
