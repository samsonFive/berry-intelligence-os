"""Shared live-discovery cache for asynchronous CatchAll recall.

Scheduled CatchAll jobs write normalized DiscoveryHit rows here.
/week reads already-fetched rows. Nothing in this module submits a
10-15 minute paid job.

Cache lives under inbox/operations so it is operator-writable and never
trusted Evidence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.runtime_config import REPO_ROOT, resolve_inbox_dir
from app.services.industry_pulse.models import DiscoveryHit

CACHE_RELATIVE = Path("operations") / "catchall_recall" / "cache.json"


def cache_path(inbox_dir: Path | None = None) -> Path:
    root = inbox_dir or resolve_inbox_dir(REPO_ROOT)
    return root / CACHE_RELATIVE


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_cache() -> dict[str, Any]:
    return {
        "schema": "catchall-recall-cache-v1",
        "updated_at": None,
        "status": "empty",
        "reason": "no CatchAll recall has written this cache",
        "job_ids": [],
        "hit_count": 0,
        "hits": [],
    }


def load_cache(inbox_dir: Path | None = None) -> dict[str, Any]:
    path = cache_path(inbox_dir)
    if not path.is_file():
        return empty_cache()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_cache()
    return payload if isinstance(payload, dict) else empty_cache()


def write_cache(payload: dict[str, Any], *, inbox_dir: Path | None = None) -> Path:
    path = cache_path(inbox_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        **empty_cache(),
        **payload,
        "updated_at": payload.get("updated_at") or _iso(),
        "hit_count": len(payload.get("hits") or []),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def hits_from_cache(inbox_dir: Path | None = None) -> list[DiscoveryHit]:
    payload = load_cache(inbox_dir)
    rows: list[DiscoveryHit] = []
    for item in payload.get("hits") or []:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        rows.append(
            DiscoveryHit(
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                source_domain=str(item.get("source_domain") or ""),
                published_date=item.get("published_date"),
                snippet=str(item.get("snippet") or "")[:500],
                query_id=str(item.get("query_id") or "catchall:cache"),
                query_text=str(item.get("query_text") or ""),
                geography=str(item.get("geography") or "global"),
                berry=item.get("berry"),
                topic=item.get("topic") or "catchall_recall",
                provider="newscatcher_catchall",
                origin_publisher_name=item.get("origin_publisher_name"),
                origin_publisher_url=item.get("origin_publisher_url"),
                wrapper_url=item.get("wrapper_url"),
                provider_metadata=dict(item.get("provider_metadata") or {"catchall_cache": True}),
            )
        )
    return rows


def serialize_hits(hits: list[DiscoveryHit]) -> list[dict[str, Any]]:
    return [hit.as_dict() for hit in hits]
