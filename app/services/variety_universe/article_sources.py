"""Read-only article inputs for private variety identity discovery.

Uses the existing Digest source inventory and Reader captures. No fetches,
candidate persistence, canonical writes or publication/claim approvals.
"""
from __future__ import annotations

from pathlib import Path

from app.services.feed_first import SAFE_ID_RE
from app.services.feed_first_reader import capture_path, load_capture, merge_capture
from app.services.personal_digest import source_records
from app.services.source_body import article_full_text, reader_content

MAX_CAPTURE_BYTES = 2_000_000
MAX_ARTICLE_CHARS = 200_000


def available_article_sources(published: list[dict], inbox_dir: Path) -> tuple[list[dict], dict]:
    """Known published/retained news only; orphan and mismatched caches stay out.

    Text is selected only in the private identity workspace, never the feed's
    metadata projection or a public/static build. Existing stored text wins
    over a Reader capture, including operator edits.
    """
    records = source_records(published, inbox_dir)
    selected = []
    counts = {"known_sources": len(records), "readable_sources": 0,
              "reviewed_sources": 0, "unreviewed_sources": 0,
              "reader_captures": 0, "oversized_sources": 0}
    for item_id, original in records.items():
        record = original
        captured = False
        if SAFE_ID_RE.fullmatch(item_id) and original.get("source_url"):
            path = capture_path(inbox_dir, item_id)
            try:
                bounded = path.stat().st_size <= MAX_CAPTURE_BYTES
            except OSError:
                bounded = False
            if bounded:
                capture = load_capture(inbox_dir, item_id)
                if (capture and capture.get("ok") is True
                        and capture.get("item_id") == item_id
                        and capture.get("requested_url") == original["source_url"]
                        and isinstance(capture.get("passages"), list)
                        and all(isinstance(text, str) for text in capture["passages"])):
                    record = merge_capture(original, capture)
                    captured = not article_full_text(original) and bool(article_full_text(record))
        content = reader_content(record)
        if content["state"] not in {"body_available", "body_partial"}:
            continue
        text = article_full_text(record, preserve_line_breaks=True)
        if len(text) > MAX_ARTICLE_CHARS:
            counts["oversized_sources"] += 1
            continue
        # A copied synopsis is still a synopsis, not an original article.
        if " ".join(text.split()) == " ".join(content["summary"].split()):
            continue
        selected.append(record)
        counts["readable_sources"] += 1
        counts["reviewed_sources" if record.get("status") == "published" else "unreviewed_sources"] += 1
        counts["reader_captures"] += int(captured)
    return selected, counts
