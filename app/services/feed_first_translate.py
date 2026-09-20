"""English translation pass for non-English Today items.

English is the analyst language. Global stories still enter the feed.
When PERPLEXITY_API_KEY is present, title and summary are translated with
the existing Perplexity chat transport. No new vendor keys. Firecrawl / Jina
stay unused.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable

from app.services.feed_first import is_analyst_english

TRANSLATE_SUBDIR = "live"
TRANSLATE_CACHE = "translations.json"
DEFAULT_TRANSLATE_MODEL = "perplexity/sonar"

_TRANSLATE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "english_translation",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "source_language": {"type": "string"},
            },
            "required": ["title", "summary", "source_language"],
            "additionalProperties": False,
        },
    },
}


def needs_english_translation(text: str) -> bool:
    return not is_analyst_english(text)


def guess_source_language(text: str) -> str:
    sample = str(text or "")
    if any("\u3040" <= ch <= "\u30ff" for ch in sample):
        return "ja"
    if any("\uac00" <= ch <= "\ud7af" for ch in sample):
        return "ko"
    if any("\u4e00" <= ch <= "\u9fff" for ch in sample):
        return "zh"
    return "und"


def _cache_path(inbox_dir: Path) -> Path:
    return Path(inbox_dir) / TRANSLATE_SUBDIR / TRANSLATE_CACHE


def _cache_key(title: str, summary: str) -> str:
    blob = f"{title}\n{summary}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:24]


def _load_cache(inbox_dir: Path | None) -> dict[str, Any]:
    if inbox_dir is None:
        return {}
    path = _cache_path(inbox_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_cache(inbox_dir: Path | None, payload: dict[str, Any]) -> None:
    if inbox_dir is None:
        return
    path = _cache_path(inbox_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_translation(content: str) -> dict[str, str] | None:
    raw = (content or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    title = str(data.get("title") or "").strip()
    summary = str(data.get("summary") or "").strip()
    if not title:
        return None
    return {
        "title": title,
        "summary": summary,
        "source_language": str(data.get("source_language") or "und").strip() or "und",
    }


def perplexity_translator(title: str, summary: str) -> dict[str, str] | None:
    from app.services.ai_gateway.credentials import MissingCredentialError, resolve_perplexity_api_key
    from app.services.ai_gateway.perplexity_chat import PerplexityChatTransport
    from app.services.industry_pulse.credentials import has_perplexity

    if not has_perplexity():
        return None
    try:
        key = resolve_perplexity_api_key()
    except MissingCredentialError:
        return None
    import os

    model = (os.environ.get("BIOS_PERPLEXITY_MODEL") or DEFAULT_TRANSLATE_MODEL).strip()
    transport = PerplexityChatTransport(api_key=key, timeout_seconds=20.0)
    prompt = (
        "Translate this berry-industry news item into clear English for a CI analyst. "
        "Keep proper nouns. Return JSON only.\n"
        f"Title: {title}\nSummary: {summary}"
    )
    try:
        response = transport.send(
            model=model,
            messages=[
                {"role": "system", "content": "You translate news into English. Do not add facts."},
                {"role": "user", "content": prompt},
            ],
            response_format=_TRANSLATE_FORMAT,
            temperature=0.0,
            max_tokens=400,
        )
    except Exception:  # noqa: BLE001 — translation must not abort Today
        return None
    return _parse_translation(response.content)


def apply_english_translation(
    record: dict[str, Any],
    *,
    translator: Callable[[str, str], dict[str, str] | None] | None = None,
    inbox_dir: Path | None = None,
) -> dict[str, Any]:
    """Keep the item. Translate title/summary when a translator can."""
    title = str(record.get("title") or "")
    summary = str(record.get("summary") or "")
    display = f"{title} {summary}"
    if not needs_english_translation(display):
        return record
    if record.get("translated") and is_analyst_english(title):
        return record
    updated = dict(record)
    updated["original_title"] = updated.get("original_title") or title
    updated["original_summary"] = updated.get("original_summary") or summary
    updated["source_language"] = updated.get("source_language") or guess_source_language(display)
    cache = _load_cache(inbox_dir)
    key = _cache_key(updated["original_title"], updated["original_summary"])
    result = cache.get(key) if isinstance(cache.get(key), dict) else None
    cache_hit = result is not None
    translation_started = time.perf_counter()
    if result is None:
        fn = translator if translator is not None else perplexity_translator
        try:
            result = fn(updated["original_title"], updated["original_summary"])
        except Exception:  # noqa: BLE001
            result = None
        if result:
            cache[key] = result
            _save_cache(inbox_dir, cache)
    # region agent log
    open("/opt/cursor/logs/debug.log", "a").write(json.dumps({"hypothesisId": "B", "location": "app/services/feed_first_translate.py:apply_english_translation", "message": "translation attempt completed", "data": {"cache_hit": cache_hit, "elapsed_ms": round((time.perf_counter() - translation_started) * 1000, 1), "translated": bool(result), "source_language_guess": updated["source_language"]}, "timestamp": time.time_ns() // 1_000_000}) + "\n")
    # endregion
    if result and result.get("title"):
        updated["title"] = result["title"]
        if result.get("summary"):
            updated["summary"] = result["summary"]
        updated["translated"] = True
        updated["translation_pending"] = False
        if result.get("source_language"):
            updated["source_language"] = result["source_language"]
        return updated
    updated["translated"] = False
    updated["translation_pending"] = True
    return updated


def translate_records(
    records: list[dict[str, Any]],
    *,
    translator: Callable[[str, str], dict[str, str] | None] | None = None,
    inbox_dir: Path | None = None,
) -> list[dict[str, Any]]:
    return [
        apply_english_translation(row, translator=translator, inbox_dir=inbox_dir)
        for row in records
    ]
