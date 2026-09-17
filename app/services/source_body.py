"""Classify persisted source artifacts for publication review.

This module does not fetch URLs and does not invent article text.
"""

from __future__ import annotations

from typing import Any

from app.services.html_text import decode_html_text
import re

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
    "this website uses a security service to protect against malicious bots",
    "this page is displayed while the website verifies you are not a bot",
)

BODY_STATE_LABELS = {
    "body_available": "FULL BODY",
    "body_partial": "BODY PARTIAL",
    "description_only": "THIN DESCRIPTION ONLY",
    "transcript_available": "TRANSCRIPT",
    "body_unavailable": "BODY UNAVAILABLE",
    "access_limited": "ACCESS-LIMITED",
    "interstitial": "CONSENT / INTERSTITIAL / BOT WALL",
}


def article_full_text(record: dict[str, Any]) -> str:
    from app.services.intelligence_feed import article_paragraphs
    paragraphs = article_paragraphs(record)
    if paragraphs:
        return "\n\n".join(decode_html_text(row.get("text") or "") for row in paragraphs if row.get("text"))
    article = record.get("article") if isinstance(record.get("article"), dict) else {}
    return decode_html_text(article.get("full_text") if isinstance(article, dict) else "")


def looks_like_interstitial(text: str) -> bool:
    haystack = decode_html_text(text).casefold()
    if not haystack:
        return False
    # An incidental footer is not an access wall. Evaluate independent prose
    # blocks so a real article mentioning a cookie policy remains usable.
    blocks = [b.strip() for b in re.split(r"\n+|(?<=[.!?])\s+", haystack) if b.strip()]
    wall = [b for b in blocks if any(s in b for s in INTERSTITIAL_SIGNALS)
            or any(s in b for s in ("accept all cookies", "manage consent", "cookie preferences", "reject all cookies"))]
    useful = [b for b in blocks if b not in wall and len(b.split()) >= 12]
    return bool(wall) and (not useful or sum(map(len, wall)) >= len(haystack) * .4)


def reader_content(record: dict[str, Any]) -> dict[str, Any]:
    """Read-time protection also covers old records without rewriting history."""
    body = classify_source_body(record)
    contaminated = body["state"] == "interstitial"
    candidates = [record.get("summary"), record.get("publisher_description")]
    summary = next((decode_html_text(s) for s in candidates
                    if s and not looks_like_interstitial(str(s))), "")
    if contaminated:
        summary = ""
    return {
        **body,
        "summary": summary,
        "contaminated": contaminated,
        "notice": ("Article text could not be recovered: the stored page contains consent or access-screen text. Open the original source to read it."
                   if contaminated else
                   "Limited source content: only a publisher description or summary is available."
                   if not body["usable_in_app"] else ""),
    }


def safe_source_record(record: dict[str, Any]) -> dict[str, Any]:
    """Template projection; original fields and review history stay on disk."""
    content = reader_content(record)
    return {**record, "summary": content["summary"], "content_notice": content["notice"],
            "why_it_matters": "" if content["contaminated"] else record.get("why_it_matters", "")}


def classify_source_body(record: dict[str, Any]) -> dict[str, Any]:
    body = article_full_text(record)
    excerpt = decode_html_text(record.get("transcript_excerpt") or "")
    publisher = decode_html_text(record.get("publisher_description") or "")
    summary = decode_html_text(record.get("summary") or "")
    transcript = record.get("transcript") if isinstance(record.get("transcript"), dict) else {}
    transcript_text = ""
    if transcript:
        segments = transcript.get("segments")
        if isinstance(segments, list) and segments:
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
        # Real acquisition output stores `acquisition_failure_category`;
        # `failure_category` is kept as a fallback for older records/fixtures.
        failure = str(
            discovery.get("acquisition_failure_category") or discovery.get("failure_category") or ""
        ).casefold()
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
            "Full source content was not captured. Review the original source before publishing."
            if state in {"description_only", "interstitial", "access_limited", "body_unavailable"}
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
