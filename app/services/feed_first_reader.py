"""Public reader capture for feed-first items.

Fetches a publisher URL only when it is a public http(s) address. Does not
bypass paywalls, robots, CSP, or X-Frame-Options. Live Page is offered only
when the publisher permits framing. Firecrawl / Jina stay unused until those
keys exist — this is the direct-http lane of the reader bake-off.
"""

from __future__ import annotations

import ipaddress
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.services.html_text import decode_html_text
from app.services.source_body import looks_like_interstitial

CAPTURE_SUBDIR = "feed_first_reader"
MAX_BYTES = 800_000
FETCH_TIMEOUT = 4.0
USER_AGENT = "BerryIntelligenceOS-Reader/1.0 (+https://github.com/samsonFive/berry-intelligence-os)"
_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_ON_EVENT_RE = re.compile(r"\son\w+\s*=\s*(['\"]).*?\1", re.IGNORECASE | re.DOTALL)
_JS_URL_RE = re.compile(r"javascript:", re.IGNORECASE)
_P_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
_TITLE_RE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
}


def capture_path(inbox_dir: Path, item_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._:-]+", "-", item_id)[:200]
    return Path(inbox_dir) / CAPTURE_SUBDIR / f"{safe}.json"


def is_public_http_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS:
        return False
    if host.endswith((".local", ".internal", ".localhost")):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return bool(ip.is_global)


def frame_allowed(headers: dict[str, str]) -> bool:
    xfo = str(headers.get("x-frame-options") or headers.get("X-Frame-Options") or "").casefold()
    if xfo in {"deny", "sameorigin"}:
        return False
    csp = str(headers.get("content-security-policy") or headers.get("Content-Security-Policy") or "")
    hay = csp.casefold()
    if "frame-ancestors" not in hay:
        return True
    if "frame-ancestors 'none'" in hay or 'frame-ancestors "none"' in hay:
        return False
    if "frame-ancestors 'self'" in hay or 'frame-ancestors "self"' in hay:
        return False
    return "*" in hay


def sanitize_reader_html(html: str) -> str:
    """Drop active scripts, styles, handlers, and javascript: URLs."""
    cleaned = _SCRIPT_RE.sub(" ", html or "")
    cleaned = _STYLE_RE.sub(" ", cleaned)
    cleaned = _ON_EVENT_RE.sub("", cleaned)
    return _JS_URL_RE.sub("", cleaned)


def paragraphs_from_html(html: str) -> list[str]:
    cleaned = sanitize_reader_html(html)
    found = [decode_html_text(chunk) for chunk in _P_RE.findall(cleaned)]
    passages = [row for row in found if len(row) >= 40]
    if passages:
        return passages[:24]
    blob = decode_html_text(cleaned)
    if len(blob) >= 80:
        return [blob[:2000]]
    return []


def _paragraphs_from_html(html: str) -> list[str]:
    return paragraphs_from_html(html)


def classify_capture(passages: list[str], *, status_code: int) -> str:
    text = " ".join(passages)
    if status_code in {401, 403, 451} or looks_like_interstitial(text):
        return "blocked"
    if not passages:
        return "metadata_only"
    if status_code >= 400:
        return "error"
    if len(text) < 280:
        return "excerpt_only"
    if len(text) < 900 or len(passages) < 3:
        return "partial"
    return "full"


def empty_capture(url: str, *, reason: str) -> dict[str, Any]:
    return {
        "url": url,
        "ok": False,
        "availability": "error" if reason != "blocked" else "blocked",
        "reason": reason,
        "headline": "",
        "passages": [],
        "frame_allowed": False,
        "reader_modes": ["structured_fallback"],
        "method": "direct_http",
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "status_code": 0,
    }


def fetch_public_article(url: str, *, client: httpx.Client | None = None) -> dict[str, Any]:
    if not is_public_http_url(url):
        return empty_capture(url, reason="url-not-public")
    closer = None
    http = client
    if http is None:
        http = httpx.Client(timeout=FETCH_TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        closer = http
    try:
        response = http.get(url)
        final = str(response.url)
        if not is_public_http_url(final):
            return empty_capture(url, reason="redirect-not-public")
        raw = response.content[:MAX_BYTES]
        html = raw.decode(response.encoding or "utf-8", errors="replace")
        title_match = _TITLE_RE.search(html)
        headline = decode_html_text(title_match.group(1)) if title_match else ""
        passages = _paragraphs_from_html(html)
        headers = {k: v for k, v in response.headers.items()}
        allowed = frame_allowed(headers)
        availability = classify_capture(passages, status_code=response.status_code)
        modes = ["structured_fallback"]
        if availability in {"full", "partial", "excerpt_only"}:
            modes.insert(0, "native")
        if allowed:
            modes.append("live_page")
        return {
            "url": final,
            "ok": availability in {"full", "partial", "excerpt_only"},
            "availability": availability,
            "reason": "" if availability != "error" else f"http-{response.status_code}",
            "headline": headline,
            "passages": passages,
            "frame_allowed": allowed,
            "reader_modes": modes,
            "method": "direct_http",
            "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "status_code": response.status_code,
        }
    except httpx.HTTPError as exc:
        return empty_capture(url, reason=f"{type(exc).__name__}")
    finally:
        if closer is not None:
            closer.close()


def load_capture(inbox_dir: Path, item_id: str) -> dict[str, Any] | None:
    path = capture_path(inbox_dir, item_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def save_capture(inbox_dir: Path, item_id: str, capture: dict[str, Any]) -> Path:
    path = capture_path(inbox_dir, item_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(capture, indent=2) + "\n", encoding="utf-8")
    return path


def load_captures(inbox_dir: Path) -> dict[str, dict[str, Any]]:
    folder = Path(inbox_dir) / CAPTURE_SUBDIR
    if not folder.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for path in folder.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("item_id"):
            out[str(payload["item_id"])] = payload
    return out


def capture_item(
    inbox_dir: Path,
    record: dict[str, Any],
    *,
    client: httpx.Client | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    item_id = str(record.get("id") or "")
    if item_id and not refresh:
        existing = load_capture(inbox_dir, item_id)
        if existing:
            return existing
    url = str(record.get("source_url") or "")
    capture = fetch_public_article(url, client=client)
    capture["item_id"] = item_id
    if item_id:
        save_capture(inbox_dir, item_id, capture)
    return capture


def merge_capture(record: dict[str, Any], capture: dict[str, Any] | None) -> dict[str, Any]:
    """Copy captured passages onto the live record without writing Evidence."""
    if not capture:
        return record
    merged = dict(record)
    passages = [str(row) for row in (capture.get("passages") or []) if str(row).strip()]
    if passages:
        article = dict(merged.get("article") or {}) if isinstance(merged.get("article"), dict) else {}
        existing = article.get("paragraphs") if isinstance(article.get("paragraphs"), list) else []
        if not existing:
            article["paragraphs"] = [{"text": row} for row in passages]
            merged["article"] = article
        if not merged.get("summary") and passages:
            merged["summary"] = passages[0][:280]
    merged["reader_capture"] = {
        "availability": capture.get("availability"),
        "frame_allowed": capture.get("frame_allowed"),
        "reader_modes": capture.get("reader_modes") or ["structured_fallback"],
        "method": capture.get("method"),
        "retrieved_at": capture.get("retrieved_at"),
        "reason": capture.get("reason") or "",
    }
    return merged


def bakeoff_report(*, firecrawl: bool, jina: bool) -> dict[str, Any]:
    return {
        "direct_http": {
            "available": True,
            "job": "Public article body for Native Reader",
            "notes": "Used on item open. Does not bypass paywalls or frame locks.",
        },
        "firecrawl": {
            "available": firecrawl,
            "job": "JS-heavy public pages",
            "notes": "Key absent — unused." if not firecrawl else "Keyed; not the Today default.",
        },
        "jina": {
            "available": jina,
            "job": "Readable public extract",
            "notes": "Key absent — unused." if not jina else "Keyed; not the Today default.",
        },
        "winner_for_now": "direct_http",
        "disclosure": (
            "Reader bake-off is bounded to credentials present in this environment. "
            "Missing optional lanes do not invent coverage."
        ),
    }
