"""Captured archive selection. Company ANY and tag All/Any are independent.

Only explicit destination assignments qualify as destination coverage. Geography,
headquarters, research sites and ownership never supply that assignment.
"""
from __future__ import annotations

from datetime import date
from math import ceil
from urllib.parse import urlencode

from app.services.article_dedup import normalize_canonical_url, normalize_title, find_duplicate_article
from app.services import company_source_scope
from app.services.crop_name_context import blackberry_company_noise
from app.services.berries.landscape import SEED_FIXTURE_EVIDENCE_IDS

ENABLING = {'develops', 'licenses', 'licensed_to', 'markets', 'commercializes', 'uses', 'breeds', 'provides_technology_to', 'grows', 'trials', 'sells', 'carries'}


def values(value):
    if isinstance(value, (list, tuple, set)):
        return [str(x) for x in value if x]
    return [x.strip() for x in str(value or '').split(',') if x.strip()]


def publication(record):
    raw = str(record.get('published_date') or '')[:10]
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        return ''


def select(records, params, *, relationships=(), tag_map=None, entities=None, page_size=24):
    params = dict(params)
    companies = set(values(params.get('companies')))
    berry, destination = params.get('berry', ''), params.get('destination', '')
    berries = set(values(berry))
    lane = params.get('lane', 'all')
    focus = params.get('focus', 'any')
    if lane not in {'all', 'company', 'market'} or focus not in {'any', 'one', 'shared'}:
        raise ValueError('Invalid archive lane or company focus')
    tags = set(values(params.get('tags')))
    if params.get('tag_mode', 'all') not in {'all', 'any'}:
        raise ValueError('Invalid tag matching mode')
    for field in ('after', 'before'):
        if params.get(field):
            params[field] = date.fromisoformat(params[field]).isoformat()
    if params.get('after') and params.get('before') and params['after'] > params['before']:
        raise ValueError('Start date must be before end date')
    connected, proofs = {}, {}
    for rel in relationships:
        if rel.get('status') not in {'active', 'published'}:
            continue
        a, b = rel.get('subject_id'), rel.get('object_id')
        for company, target in ((a, b), (b, a)):
            relevant_ownership = rel.get('predicate') == 'owns' and (entities or {}).get(target, {}).get('entity_type') in {'variety', 'brand', 'breeding_program', 'technology'}
            if rel.get('predicate') not in ENABLING and not relevant_ownership:
                continue
            if berries and rel.get('berry_ids') and not berries.intersection(rel['berry_ids']):
                continue
            if company in companies and target and target not in companies:
                connected.setdefault(target, []).append((company, rel['predicate'], rel.get('id', '')))
            if company in companies:
                for source_id in rel.get('evidence_ids', []):
                    proofs.setdefault(source_id, []).append(('relationship source', company, rel['predicate'], rel.get('id', '')))
    matches = []
    subjects = [entities[key] for key in companies if key in (entities or {})
                and entities[key].get('entity_type') == 'company'
                and not entities[key].get('attributes', {}).get('identity_review_required')]
    for record in records.values() if isinstance(records, dict) else records:
        if record['id'] in SEED_FIXTURE_EVIDENCE_IDS or blackberry_company_noise(' '.join(str(record.get(k) or '') for k in ('title','summary','source_name'))):
            continue
        ids, mentions = company_source_scope.links(record, subjects)
        direct = companies & ids
        links = [(target, *link) for target in ids for link in connected.get(target, [])] + proofs.get(record['id'], [])
        matched = direct | {link[1] for link in links}
        company_match = bool(matched)
        if focus == 'shared':
            company_match = len(matched) >= 2
        elif focus == 'one':
            company_match = len(matched) == 1
        attrs = record.get('attributes') or {}
        destinations = set(record.get('destination_market_ids') or attrs.get('destination_market_ids') or [])
        matched_berries = berries.intersection(record.get('berry_ids') or [])
        market_match = bool(berries and destination and matched_berries and destination in destinations)
        if berries and not destination and (not companies or lane == 'market'):
            market_match = bool(matched_berries)
        if berries and not matched_berries:
            continue
        # A destination selection scopes company and contextual stories alike.
        if destination and destination not in destinations:
            continue
        if lane == 'company' and not company_match:
            continue
        if lane == 'market' and not market_match:
            continue
        if lane == 'all' and (companies or berry or destination) and not (company_match or market_match):
            continue
        present = set((tag_map or {}).get(record['id'], record.get('tags') or []))
        if tags and not (tags <= present if params.get('tag_mode', 'all') == 'all' else tags & present):
            continue
        published = publication(record)
        if (params.get('after') and (not published or published < params['after'])) or (params.get('before') and (not published or published > params['before'])):
            continue
        recalled = {m['id'] for m in mentions}
        reason = [f'Direct company assignment: {x}' for x in sorted(direct - recalled)]
        reason += [f'Reviewed-source mention: {m["name"]} via {m["alias"]} in {m["field"]}; contextual recall, not a reviewed entity link' for m in mentions]
        reason += [f'Connected {target}: {company} / {predicate} ({rid})' for target, company, predicate, rid in links]
        if market_match:
            reason.append(f'Market context: {", ".join(sorted(matched_berries))} / destination {destination or "unspecified; berry context only"}')
        matches.append({**record, 'publication': published, 'inclusion': reason or ['Unscoped captured archive'],
                        'matched_companies': sorted(matched), 'effective_tags': sorted(present)})
    # Dedupe only explicit syndication families or canonical URL, never title similarity.
    groups = {}
    for record in matches:
        key = record.get('syndication_group_id') or normalize_canonical_url(record.get('canonical_url') or record.get('source_url')) or record['id']
        groups.setdefault(key, []).append(record)
    # Reuse the existing exact title/date/publisher identity fallback for opaque
    # Google News redirects. Different publishers with a similar title stay apart.
    merged, title_index = {}, {}
    for group in groups.values():
        candidate = group[0]
        title_key = (normalize_title(candidate.get('title')), publication(candidate))
        previous = title_index.get(title_key, []) if all(title_key) else []
        duplicate = find_duplicate_article({**candidate, 'canonical_url':candidate.get('canonical_url') or candidate.get('source_url')},
                                           existing_records=[merged[key][0] for key in previous]) if previous else None
        if duplicate:
            merged[duplicate].extend(group)
        else:
            merged[candidate['id']] = group
            title_index.setdefault(title_key, []).append(candidate['id'])
    unique = []
    for group in merged.values():
        group.sort(key=lambda r: (r.get('status') == 'published', r.get('publication', ''), r['id']), reverse=True)
        winner = dict(group[0])
        winner['duplicate_ids'] = [r['id'] for r in group[1:]]
        winner['inclusion'] = list(dict.fromkeys(reason for r in group for reason in r['inclusion']))
        unique.append(winner)
    unique.sort(key=lambda r: (r['publication'], r['id']), reverse=True)
    if params.get('empty_cohort') == '1':
        unique = []
    try:
        page = max(1, int(params.get('page') or 1))
    except ValueError as exc:
        raise ValueError('Page must be a positive integer') from exc
    pages = max(1, ceil(len(unique) / page_size))
    page = min(page, pages)
    return {'items': unique[(page-1)*page_size:page*page_size], 'total': len(unique),
            'page': page, 'pages': pages, 'all_ids': [r['id'] for r in unique],
            'scope': dict(params), 'archive_count': len(records)}
