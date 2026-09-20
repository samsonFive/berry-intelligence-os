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
_PDF_TJ_RE = re.compile(rb"\(((?:\\.|[^\\)])+)\)\s*Tj")
_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)',
    re.IGNORECASE,
)
_OG_IMAGE_REV_RE = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    re.IGNORECASE,
)
_IMG_SRC_RE = re.compile(
    r'<img\b[^>]*\bsrc=["\'](https?://[^"\']+)["\']',
    re.IGNORECASE,
)
_LOGO_HOST_RE = re.compile(r"logo|favicon|sprite", re.IGNORECASE)
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


def extract_pdf_text(raw: bytes) -> list[str]:
    """Best-effort literals from a public PDF. Never claims a full article."""
    if not raw.lstrip().startswith(b"%PDF"):
        return []
    passages: list[str] = []
    for match in _PDF_TJ_RE.finditer(raw[:MAX_BYTES]):
        chunk = match.group(1).decode("latin-1", errors="replace")
        chunk = (
            chunk.replace("\\n", " ")
            .replace("\\r", " ")
            .replace("\\(", "(")
            .replace("\\)", ")")
            .replace("\\\\", "\\")
        )
        text = " ".join(chunk.split())
        if len(text) >= 20:
            passages.append(text)
        if len(passages) >= 12:
            break
    return passages


def looks_like_pdf(url: str, *, content_type: str = "", body: bytes = b"") -> bool:
    if body.lstrip().startswith(b"%PDF"):
        return True
    if "application/pdf" in (content_type or "").casefold():
        return True
    path = urlparse(str(url or "")).path.casefold()
    return path.endswith(".pdf")


def extract_article_images(html: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    candidates = [
        *_OG_IMAGE_RE.findall(html or ""),
        *_OG_IMAGE_REV_RE.findall(html or ""),
        *_IMG_SRC_RE.findall(html or ""),
    ]
    for raw in candidates:
        url = str(raw or "").strip()
        if not is_public_http_url(url) or url in seen:
            continue
        host = (urlparse(url).hostname or "").lower()
        if _LOGO_HOST_RE.search(host) or _LOGO_HOST_RE.search(url):
            continue
        if any(token in host for token in ("linkedin", "facebook", "instagram")):
            continue
        seen.add(url)
        found.append({"url": url, "alt": ""})
        if len(found) >= 8:
            break
    return found


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
        "images": [],
        "content_kind": "article",
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
        headers = {k: v for k, v in response.headers.items()}
        content_type = str(headers.get("content-type") or headers.get("Content-Type") or "")
        if looks_like_pdf(final, content_type=content_type, body=raw):
            passages = extract_pdf_text(raw)
            availability = "excerpt_only" if passages else "metadata_only"
            return {
                "url": final,
                "ok": bool(passages),
                "availability": availability,
                "reason": "" if passages else "pdf-text-unavailable",
                "headline": "",
                "passages": passages,
                "images": [],
                "content_kind": "pdf",
                "frame_allowed": False,
                "reader_modes": ["structured_fallback"],
                "method": "direct_http_pdf",
                "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "status_code": response.status_code,
            }
        html = raw.decode(response.encoding or "utf-8", errors="replace")
        title_match = _TITLE_RE.search(html)
        headline = decode_html_text(title_match.group(1)) if title_match else ""
        passages = _paragraphs_from_html(html)
        images = extract_article_images(html)
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
            "images": images,
            "content_kind": "article",
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
    images = [row for row in (capture.get("images") or []) if isinstance(row, dict) and row.get("url")]
    if images:
        merged["images"] = images
        article = dict(merged.get("article") or {}) if isinstance(merged.get("article"), dict) else {}
        if not article.get("image_url"):
            article["image_url"] = images[0]["url"]
            merged["article"] = article
    if capture.get("content_kind"):
        merged["content_kind"] = capture.get("content_kind")
    merged["reader_capture"] = {
        "availability": capture.get("availability"),
        "frame_allowed": capture.get("frame_allowed"),
        "reader_modes": capture.get("reader_modes") or ["structured_fallback"],
        "method": capture.get("method"),
        "retrieved_at": capture.get("retrieved_at"),
        "reason": capture.get("reason") or "",
        "content_kind": capture.get("content_kind") or "article",
    }
    return merged


def bakeoff_report(
    *,
    firecrawl: bool,
    jina: bool,
    cascade: dict[str, Any] | None = None,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cascade = cascade or {}
    stats = stats or {}
    return {
        "direct_http": {
            "available": True,
            "job": "Public article body, PDF text, and article images",
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
        "coverage_audit": {
            "unique_finds": int(stats.get("week") or 0),
            "clustered": int(stats.get("clustered_stories") or 0),
            "readable_yield": "direct_http on open; Firecrawl/Jina unused unless keyed",
            "latency": "not timed in this environment",
            "cost": cascade.get("reason")
            or "secondary vendors fire only when primary unique stories are thin",
        },
        "disclosure": (
            "Reader bake-off is bounded to credentials present in this environment. "
            "Missing optional lanes do not invent coverage."
        ),
    }
