"""Read-only source operations alongside explicitly scoped News contribution."""
import json
from collections import Counter, defaultdict

from app.services.chronology import parse_stamp
from app.services.media_discovery import read_source_discovery_state
from app.services.source_freshness import classify_source_freshness, source_execution_status
from app.services.source_lifecycle import lifecycle_state


def model(sources, records, matching_ids, inbox_dir, exclusions=None):
    discovered = defaultdict(list)
    issues = 0
    for path in (inbox_dir / 'discovered_media').glob('*.json'):
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(item, dict) or not isinstance(item.get('source_id'), str):
                raise ValueError('invalid item')
            discovered[item['source_id']].append(item)
        except (OSError, ValueError):
            issues += 1
    retained = defaultdict(list)
    for item in records.values():
        if isinstance(item.get('source_id'), str):
            retained[item['source_id']].append(item)
    visible = Counter(records[key].get('source_id') for key in matching_ids)
    rows = []
    for source in sources:
        key = source['id']
        corrupt = False
        try:
            state = read_source_discovery_state(inbox_dir, key)
            if state is not None and not isinstance(state, dict):
                raise ValueError('invalid state')
            execution = source_execution_status(source, discovery_state=state)
            freshness = classify_source_freshness(source, discovery_state=state).as_dict()
            if (source.get('discovery') or {}).get('adapter') and not source.get('update_cadence') and freshness['label'] == 'Current':
                freshness['label'] = 'Unscheduled; inspect last successful check'
        except (OSError, ValueError, TypeError, AttributeError):
            corrupt, state = True, {}
            execution = {'label': 'Runtime state unreadable'}
            freshness = {'label': 'Unknown', 'last_checked_at': None, 'last_success_at': None}
        items = discovered[key]
        dated = [item for item in items if parse_stamp(item.get('published_date'))]
        latest = max(dated, key=lambda item: parse_stamp(item['published_date']).timestamp(), default={})
        publications = retained[key]
        excluded = Counter((exclusions or {}).get(item['id']) for item in publications if (exclusions or {}).get(item['id']))
        drafts = sum(item.get('status') == 'unreviewed' for item in publications)
        transcripts = sum(item.get('transcript_status') in {'ready', 'partial', 'captured', 'available'} for item in publications)
        if visible[key]:
            reason = 'Contributes to the current News selection.'
        elif publications:
            reason = 'Retained publications exist; none pass the current media, relevance, date, geography, tag and review selection.'
        elif items:
            reason = 'Discovered items exist without an active publication in the News corpus. Inspect review, duplicate, backlog and relevance dispositions.'
        elif corrupt:
            reason = 'Runtime state is unreadable; collection health cannot be established.'
        else:
            reason = {'NEVER_RUN': 'No successful collection run recorded.',
                      'MANUAL': 'Manual reference; no discovery adapter.',
                      'DISABLED': 'Collection disabled or source retired.',
                      'BLOCKED': 'Operator action or publisher access restriction.',
                      'RETRYABLE_FAILURE': 'Last collection attempt failed; inspect source operations.',
                      'INVALID_INCOMPLETE': 'Discovery configuration is incomplete.'}.get(execution.get('state'), 'No retained discoveries or active publications.')
        rows.append(dict(id=key, label=source.get('label') or key,
                         adapter=(source.get('discovery') or {}).get('adapter') or 'Manual / reference',
                         lifecycle=lifecycle_state(source), cadence=source.get('update_cadence') or 'Unspecified',
                         execution=execution['label'], health=freshness['label'],
                         last_attempt=freshness.get('last_checked_at'), last_success=freshness.get('last_success_at'),
                         latest_title=latest.get('title'), latest_date=latest.get('published_date'),
                         discovered=len(items), drafts=drafts, transcripts=transcripts,
                         visible=visible[key], reason=reason))
        rows[-1]['exclusions'] = [{'reason': reason, 'count': count} for reason, count in sorted(excluded.items())]
    return {'health_rows': sorted(rows, key=lambda row: row['label'].casefold()), 'health_issues': issues}
