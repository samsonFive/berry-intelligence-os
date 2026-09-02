"""Background CatchAll recall → shared live discovery cache.

Uses CollectionRunner / pipeline_scheduler. Never called from request-time
/week. Without a key the job succeeds as awaiting_key so the scheduler
stays green until the operator sets NEWSCATCHER_API_KEY or CATCHALL_API_KEY.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

import httpx

from app.services.industry_pulse.catchall_cache import serialize_hits, write_cache
from app.services.industry_pulse.catchall_provider import (
    CATCHALL_BASE,
    PULL_PATH,
    STATUS_PATH,
    SUBMIT_PATH,
    records_to_hits,
)
from app.services.industry_pulse.credentials import catchall_key, has_catchall
from app.services.industry_pulse.matrix import GEO_EDITIONS, PulseQuery
from app.services.industry_pulse.query_text import semantic_query_text

# Bounded event enumeration. Not the Pulse 32. Not request-time.
CATCHALL_RECALL_QUERIES: tuple[PulseQuery, ...] = (
    PulseQuery(
        id="catchall:genetics-licensing",
        text=(
            "blueberry OR strawberry OR raspberry OR blackberry cultivar "
            "licensing OR breeding partnership OR new variety commercialization"
        ),
        berry=None,
        geography="global",
        topic="catchall_recall",
        kind="catchall_recall",
        hl="en-US",
        gl="US",
        ceid="US:en",
        date_window="7d",
    ),
    PulseQuery(
        id="catchall:apac-supply",
        text=(
            "blueberry OR strawberry China OR Japan OR Korea OR Australia "
            "OR Vietnam harvest OR export OR price OR market access"
        ),
        berry=None,
        geography="apac",
        topic="catchall_recall",
        kind="catchall_recall",
        hl=GEO_EDITIONS["apac"]["hl"],
        gl=GEO_EDITIONS["apac"]["gl"],
        ceid=GEO_EDITIONS["apac"]["ceid"],
        date_window="7d",
    ),
)

AWAITING_KEY = "awaiting_key"
DEFAULT_LIMIT = 10
POLL_ATTEMPTS = 2  # scheduled job records submit; next cadence pulls


def _headers(key: str) -> dict[str, str]:
    return {"x-api-key": key, "x-api-token": key, "Accept": "application/json"}


def submit_job(
    query: PulseQuery,
    *,
    key: str,
    post: Callable[..., Any],
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    body = {
        "query": semantic_query_text(query),
        "mode": "base",
        "limit": min(max(limit, 1), 25),
    }
    response = post(
        urljoin(CATCHALL_BASE, SUBMIT_PATH),
        headers=_headers(key),
        json=body,
        timeout=45.0,
    )
    response.raise_for_status()
    payload = response.json() if hasattr(response, "json") else {}
    return payload if isinstance(payload, dict) else {}


def pull_job(job_id: str, *, key: str, get: Callable[..., Any]) -> dict[str, Any]:
    response = get(
        urljoin(CATCHALL_BASE, PULL_PATH.format(job_id=job_id)),
        headers=_headers(key),
        timeout=45.0,
    )
    response.raise_for_status()
    payload = response.json() if hasattr(response, "json") else {}
    return payload if isinstance(payload, dict) else {}


def run_catchall_recall(
    *,
    inbox_dir: Path,
    key: str | None = None,
    submit: Callable[..., Any] | None = None,
    pull: Callable[..., Any] | None = None,
    prefetched_records: list[dict[str, Any]] | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Write cache. Never Evidence. Succeeds without a key as awaiting_key."""
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    secret = (key if key is not None else catchall_key()).strip()
    if not secret and prefetched_records is None:
        report = {
            "state": AWAITING_KEY,
            "available": False,
            "reason": "SET NEWSCATCHER_API_KEY or CATCHALL_API_KEY → scheduled recall becomes live",
            "queries": [query.id for query in CATCHALL_RECALL_QUERIES],
            "hit_count": 0,
            "job_ids": [],
            "updated_at": stamp,
        }
        write_cache({**report, "hits": [], "status": AWAITING_KEY}, inbox_dir=inbox_dir)
        return report

    records = list(prefetched_records or [])
    job_ids: list[str] = []
    if prefetched_records is None:
        poster = submit or httpx.post
        getter = pull or httpx.get
        for query in CATCHALL_RECALL_QUERIES:
            submitted = submit_job(query, key=secret, post=poster, limit=limit)
            job_id = str(submitted.get("job_id") or submitted.get("id") or "")
            if job_id:
                job_ids.append(job_id)
                pulled = pull_job(job_id, key=secret, get=getter)
                records.extend(pulled.get("records") or pulled.get("results") or [])

    hits = []
    for query in CATCHALL_RECALL_QUERIES:
        hits.extend(records_to_hits(records, query=query, provider_name="newscatcher_catchall"))
    unique: dict[str, Any] = {}
    for hit in hits:
        unique[hit.url] = hit
    stored = list(unique.values())
    write_cache(
        {
            "status": "ready",
            "reason": None,
            "job_ids": job_ids,
            "hits": serialize_hits(stored),
            "updated_at": stamp,
        },
        inbox_dir=inbox_dir,
    )
    return {
        "state": "ok",
        "available": True,
        "reason": None,
        "queries": [query.id for query in CATCHALL_RECALL_QUERIES],
        "hit_count": len(stored),
        "job_ids": job_ids,
        "updated_at": stamp,
        "berry_relevant": len(stored),
    }


def available() -> bool:
    return has_catchall()
