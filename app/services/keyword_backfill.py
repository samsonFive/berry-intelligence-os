"""Explicit historical discovery into the existing untrusted publication inbox."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import uuid

from app.services import collection_settings as settings
from app.services.topic_retrieval import plan_query, normalize
from app.services.topic_discovery import discover_topic


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def folder(inbox):
    return Path(inbox) / 'operations' / 'keyword_backfills'


def read(inbox, run_id):
    if not re.fullmatch(r'[a-f0-9]{32}', run_id):
        raise ValueError('Invalid backfill ID.')
    path = folder(inbox) / (run_id + '.json')
    if not path.exists():
        raise ValueError('Backfill not found.')
    try:
        row = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(row, dict) or not {'status', 'updated_at', 'items', 'counts'} <= row.keys():
            raise ValueError()
    except (OSError, ValueError):
        raise ValueError('Backfill record could not be read; no saved articles were changed.') from None
    if row['status'] in {'queued', 'running'} and datetime.now(timezone.utc) - datetime.fromisoformat(row['updated_at']) > timedelta(minutes=20):
        return {**row, 'status': 'interrupted', 'error': 'This run stopped responding. Inspect its saved items before retrying.'}
    return row


def recent(inbox):
    rows = []
    for path in sorted(folder(inbox).glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
        try:
            rows.append(read(inbox, path.stem))
        except ValueError as exc:
            rows.append(dict(id=path.stem, label='Unreadable backfill record', start='', end='',
                             status='failed', error=str(exc), counts={}, items=[]))
    return rows


def resume(inbox, run_id, *, actor):
    """Called under the collection lease; never authorizes another provider search."""
    job = read(inbox, run_id)
    if job['status'] not in {'interrupted', 'failed'}:
        raise ValueError('Only interrupted or failed backfills can be resumed.')
    if not isinstance(job.get('candidates'), list):
        raise ValueError('No completed search was saved. Start a new backfill with an explicit provider choice.')
    monitor(inbox, job['key'], job['revision'])
    if any(r['id'] != run_id and r['status'] in {'queued', 'running'} for r in recent(inbox)):
        raise ValueError('A keyword backfill is already running. Wait for it to finish.')
    job.update(status='queued', updated_at=datetime.now(timezone.utc).isoformat(), resumed_by=actor)
    job.pop('error', None)
    _write(folder(inbox) / (run_id + '.json'), job)
    return job


def monitor(inbox, key, revision):
    stored = settings.load(inbox)['entries'].get(key, {})
    row = {**settings.catalog().get(key, {}), **stored}
    if not row or row.get('kind') != 'query' or not row.get('query_builder') or row.get('removed'):
        raise ValueError('Backfill requires a saved monitor with Berry and Region controls. Create one with Add keyword monitor first.')
    if settings.fingerprint(stored) != revision:
        raise ValueError('This monitor changed since you opened it. Reload before backfilling.')
    return row


def enqueue(inbox, *, key, revision, start, end, limit, actor):
    row = monitor(inbox, key, revision)
    if row.get('input_mode') == 'advanced':
        from app.services.monitor_expression import parse
        parse(row['query_input'])
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        limit = int(limit)
    except (ValueError, TypeError):
        raise ValueError('Enter valid start/end dates and an article limit.') from None
    if first > last or last > date.today() or (last - first).days > 1826 or not 1 <= limit <= 20:
        raise ValueError('Choose up to five years through today and an article limit from 1 to 20.')
    if any(r['status'] in {'queued', 'running'} for r in recent(inbox)):
        raise ValueError('A keyword backfill is already running. Wait for it to finish.')
    stamp = datetime.now(timezone.utc).isoformat()
    job = dict(id=uuid.uuid4().hex, key=key, revision=revision, label=row['label'], monitor=row,
               start=start, end=end, limit=limit, actor=actor, provider='perplexity_search',
               status='queued', updated_at=stamp, created_at=stamp, items=[], counts={})
    _write(folder(inbox) / (job['id'] + '.json'), job)
    return job


def _scope_matches(row, candidate):
    """Enforce simple Any/All terms on captured text, not provider snippets."""
    text = normalize(' '.join(p.get('text', '') for p in (candidate.get('article') or {}).get('paragraphs', [])))
    if not text:
        return False
    if len(text) < 200:
        return False
    if row.get('input_mode') == 'simple':
        matches = [(' ' + normalize(term) + ' ') in (' ' + text + ' ') for term in row.get('query_terms', [])]
        if not matches or not (all(matches) if row.get('term_match') == 'all' else any(matches)):
            return False
    else:
        from app.services.monitor_expression import matches
        if not matches(row['query_input'], text):
            return False
    berry = row.get('scope_berry', 'all')
    if berry != 'all':
        from app.services.industry_pulse.matrix import BERRY_TERMS
        crop_terms = BERRY_TERMS[berry].replace(' OR caneberry', '').strip('()').split(' OR ')
        if not any((' ' + normalize(term) + ' ') in (' ' + text + ' ') for term in crop_terms):
            return False
    from app.services.collection_regions import article_matches_region
    if not article_matches_region(row.get('scope_region', 'global'), title=candidate.get('title', ''), body=text):
        return False
    return True


def execute(inbox, run_id, data_dir, schemas_dir, *, discoverer=None):
    from app.services.pipeline_lock import pipeline_lock
    from app.services.collection_runner import CollectionLockedError
    job = read(inbox, run_id)
    if job['status'] != 'queued':
        return job
    path = folder(inbox) / (run_id + '.json')
    def persist():
        job['updated_at'] = datetime.now(timezone.utc).isoformat()
        _write(path, job)
    try:
        with pipeline_lock(inbox, 'keyword-backfill'):
            # Another worker may have completed this job while we waited for the lease.
            job = read(inbox, run_id)
            if job['status'] != 'queued':
                return job
            row = monitor(inbox, job['key'], job['revision'])
            job['status'] = 'running'; persist()
            from app.composition import get_repositories
            repos = get_repositories(Path(data_dir), Path(schemas_dir))
            entities = repos.entities.list()
            berry = row.get('scope_berry', 'all')
            topic = row['query_input'].replace('\n', ' OR ')
            wording = topic + (' berries' if berry == 'all' else ' ' + berry)
            plan = replace(plan_query(wording), start=job['start'], end=job['end'])
            if row.get('input_mode') == 'advanced' or len(row.get('query_terms', [])) > 1:
                # The topic retriever's concept threshold is not Boolean Any/All.
                # Capture crop candidates; enforce the saved matching rule on bodies below.
                plan = replace(plan, terms=(berry,) if berry != 'all' else ('blackberry', 'blueberry', 'raspberry', 'strawberry'),
                               cane_type=None, phrases=())
            until = (date.fromisoformat(job['end']) + timedelta(days=1)).isoformat()
            # Explicit range is sent to the provider and checked again against source dates.
            suffix = f" after:{job['start']} before:{until}"
            plan = replace(plan, raw_query=plan.raw_query + suffix, interpreted_query=plan.interpreted_query + suffix)
            from app.services.industry_pulse.matrix import GEO_EDITIONS
            region = row.get('scope_region', 'global')
            labels = [GEO_EDITIONS[region]['terms']] if region != 'global' else []
            varieties = [e['name'] for e in entities if e.get('entity_type') == 'variety'
                         and (berry == 'all' or 'berry-' + berry in e.get('berry_ids', []))]
            if isinstance(job.get('candidates'), list):
                discovery = {**job['discovery'], 'items': job['candidates']}
            else:
                discovery = (discoverer or discover_topic)(plan, inbox_dir=Path(inbox),
                    constraints={'public_labels': labels, 'public_variety_names': varieties})
                job['discovery'] = {k: v for k, v in discovery.items() if k != 'items'}
                if discovery['status'] not in {'failed', 'unavailable'}:
                    job['candidates'] = discovery.get('items', [])
                    job['next_candidate'] = 0
                job['counts'] = dict(candidates=len(discovery.get('items', [])), collected=0, duplicates=0,
                                     skipped=0, failed=0, selected=0)
                # Private checkpoint includes acquired bodies, never public/static output.
                persist()
            counts = job['counts']
            if discovery['status'] in {'failed', 'unavailable'}:
                job.update(status='failed', error='Historical search unavailable. Check provider access and retry.'); persist(); return job
            from app.services.media_discovery import NormalizedItem, upsert_discovered_item, list_discovered_items
            from app.services.media_orchestration import MediaOrchestrationService, JsonStagedTranscriptAdapter
            from app.services.article_acquisition import ArticleBody, ArticleParagraph
            from app.services.article_refresh import process_discovered_article
            from app.services.feed_first_reader import is_public_http_url
            from jsonschema import Draft202012Validator, FormatChecker
            schema = json.loads((Path(schemas_dir) / 'evidence.schema.json').read_text(encoding='utf-8'))
            validator = Draft202012Validator(schema, format_checker=FormatChecker())
            orchestrator = MediaOrchestrationService(repositories=repos, inbox_dir=Path(inbox),
                evidence_errors=lambda record: [e.message for e in validator.iter_errors(record)],
                transcript_adapter=JsonStagedTranscriptAdapter(Path(inbox)))
            source_id = 'source-keyword-' + hashlib.sha256(job['key'].encode()).hexdigest()[:16]
            source_created = False
            existing = {r.get('canonical_url'): r for r in list_discovered_items(Path(inbox)) if r.get('canonical_url')}
            offset = job.get('next_candidate', 0)
            seen = {item['url'] for item in job['items']}
            for index, candidate in enumerate(discovery.get('items', [])[offset:], start=offset):
                url = candidate.get('source_url', '')
                stamp = candidate.get('published_date', '')
                if (not stamp or not job['start'] <= stamp[:10] <= job['end'] or not is_public_http_url(url)
                        or not _scope_matches(row, candidate) or url in seen):
                    counts['skipped'] += 1
                    job['next_candidate'] = index + 1
                    persist()
                    continue
                if counts['selected'] >= job['limit']:
                    break
                seen.add(url); counts['selected'] += 1
                try:
                    if not source_created and not repos.sources.get(source_id):
                        repos.sources.create(dict(id=source_id, type='reference', label='Keyword monitor · ' + row['label'],
                            value=row['text'], enabled=False, created_at=date.today().isoformat(), last_checked_at=None,
                            last_status=None))
                    source_created = True
                    paragraphs = tuple(ArticleParagraph(i, p['text']) for i, p in enumerate(candidate['article']['paragraphs']))
                    full_text = '\n\n'.join(p.text for p in paragraphs)
                    body = ArticleBody(source_url=url, final_url=url, paragraphs=paragraphs,
                        word_count=len(full_text.split()), content_sha256=hashlib.sha256(full_text.encode()).hexdigest(),
                        fetched_at=candidate.get('retrieved_at') or job['created_at'], extractor='public-reader',
                        extractor_version='keyword-backfill-v1', title=candidate['title'], published_date=stamp[:10],
                        published_date_basis=candidate.get('publication_date_basis', 'publisher_metadata'))
                    item = NormalizedItem(title=candidate['title'], media_format='web_article', canonical_url=url,
                        external_id=None, platform_item_id=None, published_date=stamp[:10], description=candidate.get('passage', ''),
                        duration_seconds=None, transcript_availability={'status': 'not_applicable'},
                        raw_metadata={'keyword_monitor_id': job['key'], 'backfill_run_id': run_id, 'provider': job['provider'],
                                      'publication_date_basis': body.published_date_basis})
                    staged, outcome = upsert_discovered_item(Path(inbox), source_id, item, existing_by_url=existing)
                    existing[url] = staged
                    prior = orchestrator.resolve_publication_artifact(staged)
                    result, extra = process_discovered_article(staged, orchestrator=orchestrator, inbox_dir=Path(inbox),
                        acquired_body=body, berries=[e for e in entities if e.get('entity_type') == 'berry'])
                    duplicate = bool(result.duplicate_rejected_late) or prior.status in {'trusted', 'trusted_publication', 'pending_draft', 'rejected_draft'}
                    state = 'duplicate' if duplicate else 'collected' if result.publication_draft_id and extra.get('acquired') else 'failed'
                    counts['duplicates' if state == 'duplicate' else state] += 1
                    job['items'].append(dict(title=candidate['title'], url=url, published_date=stamp[:10],
                        state=state, item_id=staged['id'], draft_id=result.publication_draft_id,
                        detail=result.state))
                except Exception as exc:
                    counts['failed'] += 1
                    job['items'].append(dict(title=candidate.get('title', ''), url=url, state='failed', detail=type(exc).__name__))
                job['next_candidate'] = index + 1
                persist()
            job['status'] = 'partial' if counts['failed'] or discovery['status'] == 'partial' else 'complete'
            persist()
    except CollectionLockedError:
        # A live owner must not have its state overwritten by a competing worker.
        return read(inbox, run_id)
    except Exception as exc:
        job.update(status='failed', error=type(exc).__name__ + ': backfill stopped; saved items are preserved.')
        persist()
    return job
