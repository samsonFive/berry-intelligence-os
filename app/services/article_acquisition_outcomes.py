"""Durable operational outcomes for article-body acquisition attempts.

The ledger stores compact diagnostics only. It never stores fetched HTML or
wall content and never changes publication trust.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.services.article_acquisition import ARTICLE_ACQUISITION_VERSION, ArticleAcquisitionError, ArticleBody
from app.services.source_completeness import RETRYABLE_FAILURES, normalize_failure_category


OUTCOME_VERSION = "article-acquisition-outcome-v1"
SENSITIVE_QUERY_KEYS = frozenset({"api_key", "apikey", "key", "token", "access_token", "password", "signature"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-_") or "unknown"


def safe_attempted_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        hostname = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return "[invalid URL]"
    query = urlencode([
        (key, "[redacted]" if key.casefold() in SENSITIVE_QUERY_KEYS else val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
    ])
    return urlunsplit((parts.scheme, hostname + port, parts.path, query, ""))


def _safe_message(message: str, attempted_url: str) -> str:
    safe_url = safe_attempted_url(attempted_url)
    cleaned = message.replace(attempted_url, safe_url) if attempted_url else message
    cleaned = re.sub(
        r"(?i)\b(api[_-]?key|token|password|signature)\s*[=:]\s*[^\s&]+",
        r"\1=[redacted]",
        cleaned,
    )
    return " ".join(cleaned.split())[:400]


def _failure_outcome(error: ArticleAcquisitionError) -> tuple[str, str, bool, bool]:
    raw = error.category.casefold()
    message = str(error).casefold()
    normalized = normalize_failure_category(raw)
    retryable = normalized in RETRYABLE_FAILURES
    if raw == "interstitial":
        return "cookie_or_consent_page", "UNUSABLE_INTERSTITIAL", False, True
    if raw == "blocked":
        category = "bot_wall" if error.http_status == 403 or any(x in message for x in ("bot", "captcha", "cloudflare", "human")) else "access_denied"
        return category, "UNAVAILABLE_ACCESS", False, True
    if raw == "paywall":
        return "manual_acquisition_required", "UNAVAILABLE_ACCESS", False, True
    if raw == "empty_body":
        category = "navigation_only_shell" if "too short" in message or "not a real article" in message else "empty_page"
        return category, "UNUSABLE_EMPTY", False, category == "navigation_only_shell"
    if raw == "script_rendered":
        return "unsupported_source", "UNSUPPORTED", False, True
    if raw == "http_error":
        return "http_failure", "NOT_ACQUIRED", retryable, not retryable
    if raw in {"timeout", "transport_error", "redirect_error"}:
        return "network_failure", "NOT_ACQUIRED", True, False
    if raw in {"malformed_html", "repeated_body"}:
        return "parser_failure", "UNUSABLE_PARSE", False, True
    return "retryable_failure" if retryable else "manual_acquisition_required", "NOT_ACQUIRED", retryable, not retryable


def build_outcome(
    item: dict[str, Any], *, body: ArticleBody | None = None,
    error: ArticleAcquisitionError | None = None, publication_id: str | None = None,
    content_quality: str | None = None, diagnostic: str | None = None,
    acquisition_stage: str = "article_body",
) -> dict[str, Any]:
    if (body is None) == (error is None):
        raise ValueError("exactly one of body or error is required")
    attempted_url = str(item.get("resolved_canonical_url") or item.get("canonical_url") or "")
    attempted_at = body.fetched_at if body else _now_iso()
    if body:
        category, quality, retryable, manual = "readable_article_body", "READABLE", False, False
        message = diagnostic or f"Readable article body acquired ({body.word_count} words)."
        extractor = body.extractor
        extractor_version = body.extractor_version
    else:
        category, quality, retryable, manual = _failure_outcome(error)
        message = diagnostic or str(error)
        extractor = "trafilatura"
        extractor_version = None
    return {
        "version": OUTCOME_VERSION,
        "source_id": str(item.get("source_id") or ""),
        "item_id": str(item.get("id") or ""),
        "publication_or_draft_id": publication_id,
        "attempted_url": safe_attempted_url(attempted_url),
        "attempted_at": attempted_at,
        "article_published_date": body.published_date if body else None,
        "acquisition_stage": acquisition_stage,
        "outcome_category": category,
        "http_status": error.http_status if error else None,
        "retryable": retryable,
        "manual_acquisition_required": manual,
        "content_quality": content_quality or quality,
        "extractor": extractor,
        "extractor_version": extractor_version,
        "acquisition_version": ARTICLE_ACQUISITION_VERSION,
        "diagnostic": _safe_message(message, attempted_url),
    }


def persist_outcome(
    inbox_dir: Path,
    item: dict[str, Any],
    outcome: dict[str, Any],
    *,
    update_staged_item: bool = True,
) -> dict[str, Any]:
    """Persist one immutable attempt plus a latest pointer on the staged item."""
    source_id = str(outcome.get("source_id") or "unknown")
    item_id = str(outcome.get("item_id") or "unknown")
    folder = inbox_dir / "operations" / "article_acquisition_outcomes" / _slug(source_id) / _slug(item_id)
    folder.mkdir(parents=True, exist_ok=True)
    attempt_count = len(list(folder.glob("*.json"))) + 1
    record = dict(outcome) | {"attempt_count": attempt_count, "recorded_at": _now_iso()}
    identity = hashlib.sha256(
        f"{record['attempted_at']}|{item_id}|{attempt_count}".encode("utf-8")
    ).hexdigest()[:12]
    path = folder / f"{_slug(str(record['attempted_at']))}-{identity}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if update_staged_item:
        item_path = inbox_dir / "discovered_media" / f"{item_id}.json"
        staged = dict(item)
        if item_path.exists():
            staged = json.loads(item_path.read_text(encoding="utf-8"))
        staged["article_acquisition_attempt_count"] = attempt_count
        staged["latest_article_acquisition"] = record
        item_path.parent.mkdir(parents=True, exist_ok=True)
        item_path.write_text(json.dumps(staged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def source_acquisition_summary(inbox_dir: Path, source_id: str) -> dict[str, Any]:
    folder = inbox_dir / "operations" / "article_acquisition_outcomes" / _slug(source_id)
    outcomes: list[dict[str, Any]] = []
    if folder.exists():
        for path in folder.glob("*/*.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                outcomes.append(value)
    outcomes.sort(key=lambda row: str(row.get("recorded_at") or row.get("attempted_at") or ""))
    latest = outcomes[-1] if outcomes else None
    readable = [row for row in outcomes if row.get("outcome_category") == "readable_article_body"]
    readable_publication_dates = [
        str(row["article_published_date"])
        for row in readable
        if row.get("article_published_date")
    ]
    return {
        "attempts": len(outcomes),
        "readable": sum(row.get("outcome_category") == "readable_article_body" for row in outcomes),
        "blocked_or_unusable": sum(bool(row.get("manual_acquisition_required")) for row in outcomes),
        "retryable": sum(bool(row.get("retryable")) for row in outcomes),
        "latest": latest,
        "latest_readable_acquired_at": (readable[-1].get("attempted_at") if readable else None),
        "most_recent_readable_article": max(readable_publication_dates, default=None),
        "state": (latest or {}).get("outcome_category") or "never_attempted",
        "label": ((latest or {}).get("outcome_category") or "never_attempted").replace("_", " ").title(),
    }


def aggregate_acquisition_summaries(values: dict[str, dict[str, Any]]) -> dict[str, int]:
    return {
        "attempts": sum(int(row.get("attempts") or 0) for row in values.values()),
        "readable": sum(int(row.get("readable") or 0) for row in values.values()),
        "blocked_or_unusable": sum(int(row.get("blocked_or_unusable") or 0) for row in values.values()),
        "retryable": sum(int(row.get("retryable") or 0) for row in values.values()),
        "sources_with_attempts": sum(bool(row.get("attempts")) for row in values.values()),
    }
