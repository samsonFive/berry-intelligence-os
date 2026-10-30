"""Bounded public discovery and source capture for topic reports.

Uses the existing Search API and safe public reader. Cache lives in private
runtime, never generated/. No research model, subscriptions, or trust writes.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import threading
import time
from typing import Any, Callable
from urllib.parse import urlsplit

from app.services.ai_gateway.credentials import resolve_perplexity_api_key, MissingCredentialError
from app.services.ai_gateway.perplexity_search import PerplexitySearchClient
from app.services.article_dedup import normalize_canonical_url
from app.services.feed_first_reader import fetch_public_article, is_public_http_url
from app.services.topic_retrieval import VERSION, QueryPlan, retrieve

_LOCK = threading.Lock()
CACHE_SECONDS = 1800
CAPTURE_VERSION = 'topic-capture-v4'  # Recommendation tails are not owned article evidence.
MAX_CAPTURE_CANDIDATES = 40


def discover_topic(plan: QueryPlan, *, inbox_dir: Path, client: Any = None, fetcher: Callable = fetch_public_article, constraints: dict[str, Any] | None = None, progress: Callable | None = None, entities: dict | None = None) -> dict[str, Any]:
    constraints = constraints or {}
    identity_basis = [{k:e.get(k) for k in ('id','name','aliases','berry_ids')} for e in (entities or {}).values() if e.get('entity_type')=='variety']
    key = hashlib.sha256(json.dumps([VERSION, CAPTURE_VERSION, plan.as_dict(), constraints, sorted(identity_basis,key=lambda e:e['id'])], sort_keys=True).encode()).hexdigest()
    path = inbox_dir / "topic_research_cache" / f"{key}.json"
    # Serialize cold starts so repeated requests do not buy the same search.
    with _LOCK:
        if path.is_file() and time.time() - path.stat().st_mtime < CACHE_SECONDS:
            try:
                return {**json.loads(path.read_text(encoding="utf-8")), "cache_hit": True, "queries_this_request": 0}
            except (OSError, ValueError):
                pass
        if client is None:
            try:
                client = PerplexitySearchClient(api_key=resolve_perplexity_api_key(), timeout_seconds=20)
            except MissingCredentialError:
                return {"items": [], "status": "unavailable", "failures": ["PERPLEXITY_API_KEY is not configured"], "queries_this_request": 0, "cache_hit": False}
        started = time.monotonic()
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        variants = [plan.raw_query, plan.interpreted_query]
        if plan.cane_type:
            variants.extend([plan.interpreted_query + " new variety releases trials", plan.interpreted_query + " licensing international development"])
        queries = list(dict.fromkeys(variants))[:4]
        # Constraints are additional terms, never replacements for the question.
        suffix = " ".join(str(v) for v in constraints.get("public_labels", []) if v)
        failures: list[str] = []
        candidates: dict[str, dict[str, Any]] = {}
        successes = 0
        for query in queries:
            try:
                response = client.search((query + " " + suffix).strip(), max_results=10)
                successes += 1
                for rank, hit in enumerate(response.hits, 1):
                    url = hit.url
                    identity = normalize_canonical_url(url)
                    if not identity or not is_public_http_url(url):
                        continue
                    candidates.setdefault(identity, {"id": "web-" + hashlib.sha256(identity.encode()).hexdigest()[:16], "title": hit.title, "source_url": url, "url": url, "source_name": urlsplit(url).hostname, "snippet": hit.snippet, "published_date": hit.published_date or "", "provider": response.provider, "provider_rank": rank, "retrieved_at": stamp, "trust_class": "LIVE / UNREVIEWED"})
            except Exception as exc:
                # Error class only: provider exception text can contain secrets.
                failures.append(type(exc).__name__)
            if progress:
                progress({'stage':'search', 'searches_completed':successes+len(failures), 'candidates':len(candidates), 'items':[]})

        # Follow at most two registry names actually present in discovered
        # titles. No topic-specific result URLs or invented cultivar traits.
        from app.services.topic_retrieval import normalize
        titles = " ".join(normalize(r["title"]) for r in candidates.values())
        followed = [str(name) for name in constraints.get("public_variety_names", []) if len(str(name)) >= 4 and re.search(r"(?<!\w)" + re.escape(normalize(str(name))) + r"(?!\w)", titles)][:2]
        for name in followed:
            query = name + " " + plan.interpreted_query
            queries.append(query)
            try:
                response = client.search(query, max_results=10)
                successes += 1
                for rank, hit in enumerate(response.hits, 1):
                    identity = normalize_canonical_url(hit.url)
                    if identity and is_public_http_url(hit.url):
                        candidates.setdefault(identity, {"id": "web-" + hashlib.sha256(identity.encode()).hexdigest()[:16], "title": hit.title, "source_url": hit.url, "url": hit.url, "source_name": urlsplit(hit.url).hostname, "snippet": hit.snippet, "published_date": hit.published_date or "", "provider": response.provider, "provider_rank": rank, "retrieved_at": stamp, "trust_class": "LIVE / UNREVIEWED"})
            except Exception as exc:
                failures.append(type(exc).__name__)

        def capture(row):
            try:
                captured = fetcher(row["source_url"])
                row = {**row, "search_title": row['title'], "title": captured.get('headline') or row['title']}
                body = captured.get("passages") or []
                canonical = captured.get("canonical_url") or row["source_url"]
                if not is_public_http_url(canonical):
                    canonical = row['source_url']
                identity = normalize_canonical_url(canonical)
                locators = captured.get('passage_locators') or []
                paragraphs = [{'index':i,'text':str(p), **({'locator':locators[i]} if i<len(locators) else {})} for i,p in enumerate(body)]
                return {**row, "id": "web-" + hashlib.sha256(identity.encode()).hexdigest()[:16], "source_url": canonical, "search_date": row.get("published_date") or "", "published_date": captured.get("published_date") or "", "publication_date_basis": captured.get("published_date_basis") if captured.get("published_date") else "unknown", "article": {"paragraphs": paragraphs}, "capture_status": captured.get("availability") or "metadata_only", "capture_reason": captured.get("reason") or "", "source_version": hashlib.sha256("\n".join(str(p) for p in body).encode()).hexdigest() if body else None}
            except Exception as exc:
                return {**row, "search_date": row.get("published_date") or "", "published_date": "", "publication_date_basis": "unknown", "capture_status": "snippet_only", "capture_reason": type(exc).__name__}

        with ThreadPoolExecutor(max_workers=4) as pool:
            # Follow-up candidates precede generic gardening results for body
            # acquisition, while ranking still uses the original topic plan.
            ordered = sorted(candidates.values(), key=lambda r: any(normalize(n) in normalize(r["title"]) for n in followed), reverse=True)
            bounded = ordered[:MAX_CAPTURE_CANDIDATES]
            positions = {pool.submit(capture, row):i for i,row in enumerate(bounded)}
            completed = {}
            for future in as_completed(positions):
                completed[positions[future]] = future.result()
                # Completion order must not change final ranking or the cache.
                captured = [completed[i] for i in sorted(completed)]
                if progress:
                    preview = retrieve(captured, plan, entities=entities, limit=20)
                    groups = constraints.get('required_label_groups') or []
                    if groups:
                        from app.services.topic_retrieval import record_passages
                        preview = [r for r in preview if all(any(normalize(label) in normalize(' '.join(p for _,p in record_passages(r))) for label in group) for group in groups)]
                    progress({'stage':'capture', 'captured':len(completed), 'capture_total':len(bounded),
                              'items':[{k:r.get(k) for k in ('id','title','source_url','published_date','capture_status','relevance','passage','passage_locator')} for r in preview]})
            captured = [completed[i] for i in sorted(completed)]
        rows = retrieve(captured, plan, entities=entities, limit=20)
        # Label literal geographic constraints conservatively. Unknown dates do
        # not satisfy explicit date restrictions in match_record().
        required_groups = constraints.get("required_label_groups") or []
        if required_groups:
            from app.services.topic_retrieval import normalize, record_passages
            rows = [r for r in rows if all(any(normalize(label) in normalize(" ".join(p for _, p in record_passages(r))) for label in group) for group in required_groups)]
        result = {"items": rows, "status": "partial" if failures and successes else "failed" if failures else "complete", "failures": failures, "queries": queries, "queries_this_request": len(queries), "candidate_count": len(candidates), "capture_count": sum(bool(r.get("source_version")) for r in captured), "cache_hit": False, "retrieved_at": stamp, "latency_seconds": round(time.monotonic() - started, 3), "cost": None, "provider": "perplexity_search"}
        # Cache successful searches, including honest empty results. Failures
        # remain retryable immediately after credentials/provider recovery.
        if not failures:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path)
        return result
