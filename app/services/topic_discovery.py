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
from app.services.open_research_copy import fetch_topic_source
from app.services.topic_retrieval import VERSION, QueryPlan, retrieve

_LOCK = threading.Lock()
CACHE_SECONDS = 1800
CAPTURE_VERSION = 'topic-capture-v13'  # Credit-free discovery and exact deposited/document captures.
MAX_CAPTURE_CANDIDATES = 40


def geographic_query_variant(plan: QueryPlan, entities: dict | None) -> str | None:
    """One registered place-name alternative, without altering quoted scope.

    Search providers can return different coverage for a country's long name
    and its abbreviation. This changes discovery wording, never the local
    evidence/date/geography checks or entity identities.
    """
    places = [e for e in (entities or {}).values()
              if e.get('entity_type') == 'geography' and e.get('status') == 'active']
    owners: dict[str, set[str]] = {}
    for entity in places:
        for name in [entity.get('name') or '', *(entity.get('aliases') or [])]:
            owners.setdefault(name.casefold(), set()).add(entity['id'])
    pieces = re.split(r'("[^"]*")', plan.interpreted_query)
    for entity in sorted(places, key=lambda e: (-len(e.get('name') or ''), e['id'])):
        names = list(dict.fromkeys(filter(None, [entity.get('name'), *(entity.get('aliases') or [])])))
        for name in names:
            if len(name) < 2 or len(owners[name.casefold()]) != 1:
                continue
            alternate = next((n for n in names if n.casefold() != name.casefold()
                              and len(owners[n.casefold()]) == 1), None)
            if not alternate:
                continue
            # Short aliases retain their registered case ('us' is not US),
            # and cannot rewrite a code such as UK-821 or UK 821. An ISO date
            # after the country remains a separate, unchanged date expression.
            code_suffix = r'|\s+\d+(?![\d-])' if len(name) <= 3 else ''
            pattern = re.compile(r'(?<![\w-])' + re.escape(name) + r'(?![\w-]' + code_suffix + r')',
                                 0 if len(name) <= 3 else re.I)
            for index in range(0, len(pieces), 2):
                if pattern.search(pieces[index]):
                    changed = list(pieces)
                    changed[index] = pattern.sub(lambda _: alternate, changed[index], count=1)
                    return ''.join(changed)
    return None


def cultivar_code_query_variant(plan: QueryPlan, entities: dict | None) -> str | None:
    """Format one unambiguous registered code without editing quoted scope."""
    from app.services.topic_retrieval import _query_identifiers
    pieces=re.split(r'(-"[^"]*"|"[^"]*"|(?<!\w)-[\w-]+)',plan.interpreted_query)
    for identifier in _query_identifiers(plan,entities):
        if len(identifier['entities'])!=1:continue
        entity=next(iter(identifier['entities'].values()))
        aliases=[str(v).strip("'\u2018\u2019\"") for v in [entity.get('name') or '',*(entity.get('aliases')or[])]]
        canonical=next((v for v in aliases if identifier['pattern'].fullmatch(v) and (' 'in v or '-'in v)),None)
        if not canonical:continue
        for i in range(0,len(pieces),2):
            # Exclusions never become positive discovery queries.
            if identifier['pattern'].search(pieces[i]):
                changed=list(pieces);changed[i]=identifier['pattern'].sub(lambda m:canonical,pieces[i],count=1)
                variant=''.join(changed)
                if variant!=plan.interpreted_query:return variant
    return None


def discover_topic(plan: QueryPlan, *, inbox_dir: Path, client: Any = None, fetcher: Callable = fetch_topic_source, constraints: dict[str, Any] | None = None, progress: Callable | None = None, entities: dict | None = None, data_dir: Path | None = None) -> dict[str, Any]:
    constraints = constraints or {}
    from app.services.public_research_search import registered_primary_sources,registered_primary_terms
    primary_sources=registered_primary_sources(data_dir,entities or {}) if data_dir is not None else {}
    primary_terms=registered_primary_terms(data_dir,entities or {})if data_dir is not None else {}
    identity_basis = [{**{k:e.get(k) for k in ('id','name','aliases','berry_ids')},
        'identity_source':((e.get('attributes') or {}).get('identity_review') or {}).get('source_url'),
        'removed':bool((e.get('attributes') or {}).get('catalog_removed'))}
        for e in (entities or {}).values() if e.get('entity_type')=='variety']
    geography_variant = geographic_query_variant(plan, entities)
    from app.services.resilient_topic_search import credit_free_mode
    key = hashlib.sha256(json.dumps([VERSION, CAPTURE_VERSION, credit_free_mode(), plan.as_dict(), constraints, sorted(identity_basis,key=lambda e:e['id']), geography_variant,primary_sources,primary_terms], sort_keys=True).encode()).hexdigest()
    path = inbox_dir / "topic_research_cache" / f"{key}.json"
    from app.services.research_source_cache import cached_sources,remember_sources,merge_source_records
    history,history_status=cached_sources(inbox_dir,plan)

    def scoped_rows(records):
        selected=retrieve(records,plan,entities=entities,limit=20)
        groups=constraints.get('required_label_groups')or[]
        if groups:
            from app.services.topic_retrieval import normalize,record_passages
            selected=[r for r in selected if all(any(normalize(label)in normalize(' '.join(p for _,p in record_passages(r)))for label in group)for group in groups)]
        for row in selected:
            if row.get('research_cache_reused'):
                row['match_reason']=str(row.get('match_reason')or'')+'; previously captured public source, unreviewed'
        return selected
    # Serialize cold starts so repeated requests do not buy the same search.
    with _LOCK:
        if path.is_file() and time.time() - path.stat().st_mtime < CACHE_SECONDS:
            try:
                cached=json.loads(path.read_text(encoding="utf-8"))
                if time.time()-path.stat().st_mtime < min(CACHE_SECONDS,cached.get('cache_ttl_seconds',CACHE_SECONDS)):
                    counters={k:0 for k in ('primary_requests_this_request','fallback_requests_this_request','primary_page_requests_this_request') if k in cached}
                    return {**cached, **counters,'items':scoped_rows(merge_source_records(cached.get('items',[]),history)),
                            'history_status':history_status,'history_candidates_count':len(history),"cache_hit": True, "queries_this_request": 0}
            except (OSError, ValueError):
                pass
        if client is None:
            from app.services.resilient_topic_search import ResilientTopicSearchClient
            try:
                credential=resolve_perplexity_api_key()
                primary=PerplexitySearchClient(api_key=credential, timeout_seconds=20)
            except MissingCredentialError:
                credential='';primary=None
            client=ResilientTopicSearchClient(primary,credential=credential,entities=entities,primary_sources=primary_sources,primary_terms=primary_terms)
        started = time.monotonic()
        if progress and history:
            progress({'stage':'research_history','history_candidates_count':len(history),
                'items':[{k:r.get(k)for k in ('id','title','source_url','published_date','capture_status','relevance','match_reason')}for r in scoped_rows(history)]})
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        variants = [plan.raw_query, plan.interpreted_query]
        code_variant=cultivar_code_query_variant(plan,entities)
        if code_variant:
            variants.append(code_variant)
        if geography_variant:
            variants.append(geography_variant)
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
                row['capture_provenance'] = {k:captured[k] for k in ('method','copy_scope','original_url','repository_identifiers','original_capture_status','original_capture_reason') if k in captured}
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
                              'items':[{k:(('Quotation withheld · verification required' if k=='capture_status' else None) if k in {'capture_status','passage','passage_locator'} and r.get('support_status') in {'scope_unverified','source_review_hold'} else r.get(k)) for k in ('id','title','source_url','published_date','capture_status','relevance','passage','passage_locator')} for r in preview]})
            captured = [completed[i] for i in sorted(completed)]
        try:history_write=remember_sources(inbox_dir,captured)
        except (OSError,ValueError):history_write={'status':'unavailable','stored':0}
        rows = scoped_rows(merge_source_records(history,captured))
        # Label literal geographic constraints conservatively. Unknown dates do
        # not satisfy explicit date restrictions in match_record().
        required_groups = constraints.get("required_label_groups") or []
        if required_groups:
            from app.services.topic_retrieval import normalize, record_passages
            rows = [r for r in rows if all(any(normalize(label) in normalize(" ".join(p for _, p in record_passages(r))) for label in group) for group in required_groups)]
        diagnostics=client.diagnostics() if hasattr(client,'diagnostics') else {}
        degraded=bool(diagnostics.get('fallback_used'))
        result = {"items": rows, "status": "partial" if (failures or degraded) and successes else "failed" if failures else "complete", "failures": failures, "queries": queries, "queries_this_request": len(queries), "candidate_count": len(candidates), "capture_count": sum(bool(r.get("source_version")) for r in captured), "cache_hit": False, "retrieved_at": stamp, "latency_seconds": round(time.monotonic() - started, 3), "cost": None, "provider": "public_metadata_fallback" if degraded else "perplexity_search",'history_status':history_status,'history_candidates_count':len(history),'history_write':history_write, **diagnostics}
        # Cache successful searches, including honest empty results. Failures
        # remain retryable immediately after credentials/provider recovery.
        if not failures:
            # A working fallback with one unavailable index is still a useful
            # partial result. Briefly reuse it to avoid repeated free requests;
            # a total search failure remains immediately retryable.
            result['cache_ttl_seconds']=120 if diagnostics.get('fallback_failures')or diagnostics.get('primary_page_failures') else CACHE_SECONDS
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path)
        return result
