"""Explicit, hash-bound research mapping decisions, separate from claim trust."""
from copy import deepcopy
from datetime import date

from app.services import competitive_evaluation as ce
from app.services.living_workspaces import digest


def reviewed_payload(batch_id, payload, reviews):
    rows = ce.unpack_return(payload)
    used = set()
    for number, review in enumerate(reviews):
        if review.get('batch_id') != batch_id:
            continue
        if review.get('disposition') not in {'corrected', 'context_only', 'hold'}:
            raise ValueError('Choose an explicit research mapping disposition')
        if not str(review.get('rationale') or '').strip():
            raise ValueError('Research mapping review requires a rationale')
        date.fromisoformat(review['reviewed_at'])
        matches = [r for r in rows if r.get('record_kind') == review.get('record_kind')
                   and r.get('local_id') == review.get('local_id')
                   and digest(r.get('fields')) == review.get('expected_fields_sha256')]
        if len(matches) != 1:
            raise ValueError('Research mapping review is stale or ambiguous: '+str(review.get('local_id')))
        row = matches[0]
        identity = (row['record_kind'], row['local_id'], review['expected_fields_sha256'])
        if identity in used:
            raise ValueError('Repeated mapping review for the same returned row')
        used.add(identity)
        updates = review.get('field_updates') or {}
        if not isinstance(updates, dict) or any(k not in row['fields'] or not isinstance(v, str) for k,v in updates.items()):
            raise ValueError('Mapping corrections must update existing explicit text fields')
        if review['disposition'] != 'corrected' and updates:
            raise ValueError('Context/hold decisions cannot change returned fields')
        if updates and not review.get('source_urls'):
            raise ValueError('Mapping corrections require traceable source references')
        if any(not ce.safe_original_url(url) for url in review.get('source_urls', [])):
            raise ValueError('Mapping source references must be public HTTP(S) URLs')
        row['returned_fields'] = deepcopy(row['fields'])
        row['mapping_review'] = deepcopy(review)
        row['fields'].update(updates)
    return {**{k:deepcopy(v) for k,v in payload.items() if k not in {'records','tables'}}, 'records':rows}


def context_review_usable(row, reasons, entities):
    """Context can close a non-peer mapping, never a source or identity hold."""
    review = row.get('mapping_review') or {}
    if not isinstance(review,dict) or not isinstance(row.get('record_kind'),str) or not isinstance(row.get('fields'),dict):
        return False
    if row.get('record_kind') not in {'observation','support_context','person','gap','hiring_event'}:
        return False
    if review.get('disposition') != 'context_only' or not review.get('rationale'):
        return False
    fields = row.get('fields') or {}
    if row.get('returned_fields') != fields or digest(fields) != review.get('expected_fields_sha256'):
        return False
    try:
        date.fromisoformat(review['reviewed_at'])
    except (KeyError, ValueError, TypeError):
        return False
    allowed = {'Peer role is ineligible for the mapped capability', 'Capability mapping requires resolution'}
    if row.get('record_kind') == 'support_context':
        allowed |= {'Unrecognized or malformed row', 'Entity identity requires resolution; no name or multi-entity merge inferred'}
    if row.get('record_kind') == 'person':
        allowed.add('Conflicting versions retained for resolution')
    if row.get('record_kind') == 'gap' or (row.get('record_kind') == 'hiring_event' and 'not a hiring event' in str(fields.get('event_type','')).lower()):
        ids = review.get('context_entity_ids')
        if isinstance(ids,list) and ids and all(key in entities for key in ids):
            allowed.add('Entity identity requires resolution; no name or multi-entity merge inferred')
    return not (set(reasons)-allowed)
