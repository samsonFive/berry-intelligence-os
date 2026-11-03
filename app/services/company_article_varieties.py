"""Private article-name handoffs from the existing candidate universe.

No acquisition, matching, mutation or relationship inference. Publication company
links stay distinct from the portfolio source assertions beside them.
"""
from urllib.parse import quote, urlencode

from app.services.company_directory import initial
from app.services.variety_portfolio_coverage import _public_url
from app.services.variety_universe.coverage import BERRY_LABELS


def article_name_rows(*, entity_id, mentions, candidates, source_context,
                      linked_variety_ids=(), catalog_variety_ids=()):
    by_id = {str(row.get('id')): row for row in candidates if row.get('id')}
    by_name = {}
    for row in candidates:
        key = (str(row.get('candidate_name') or '').casefold(), row.get('berry_id'))
        by_name.setdefault(key, []).append(row)
    grouped, used_sources = {}, set()
    for mention in mentions:
        if mention.get('source_text_basis') != 'available_article_text' or mention.get('disposition') == 'berry_mismatch':
            continue
        name = str(mention.get('candidate_name') or '')
        berry = mention.get('berry_id')
        if not name or berry not in BERRY_LABELS:
            continue
        associated = []
        for reference in mention.get('article_text_sources') or []:
            sid = reference.get('evidence_id')
            source = source_context.get(sid)
            if (source and entity_id in source['company_ids']
                    and source['source_url'] == reference.get('source_url')
                    and _public_url(source['source_url'])):
                associated.append((sid, source))
        if not associated:
            continue
        candidate = by_id.get(str(mention.get('existing_candidate_id') or ''))
        if candidate is None:
            # Use an already-built candidate, never another identity matcher.
            matches = []
            evidence_ids = set(mention.get('evidence_ids') or [])
            for row in by_name.get((name.casefold(), berry), []):
                provenance = set((row.get('knowledge') or {}).get('evidence_ids') or []) | set(row.get('corpus_evidence_ids') or [])
                if provenance & evidence_ids and (not mention.get('breeder_code')
                        or row.get('breeder_code') == mention['breeder_code']):
                    matches.append(row)
            if len(matches) == 1:
                candidate = matches[0]
        # Stored human decisions always win over newly discovered occurrences.
        if candidate and (candidate.get('status') == 'rejected' or candidate.get('identity_state') == 'rejected'):
            continue
        canonical = mention.get('canonical_variety_id') or ''
        if candidate and candidate.get('human_gated') and candidate.get('identity_state') == 'confirmed_same':
            matched = candidate.get('candidate_canonical_match')
            if matched in catalog_variety_ids:
                canonical = matched
        if canonical in linked_variety_ids:
            continue
        if not canonical and not candidate:
            continue  # Do not provide a handoff to a nonexistent review entry.
        code = mention.get('breeder_code') or ''
        pending_catalog = bool(candidate and candidate.get('human_gated') and candidate.get('identity_state') == 'distinct')
        identity = (name, berry, code, canonical or candidate['id'])
        row = grouped.setdefault(identity, {
            'name': name, 'code': code, 'berry_id': berry, 'berry': BERRY_LABELS[berry],
            'basis_label': 'Named in captured news', 'sources': [], 'notes': [],
            'label': 'Check company connection' if canonical else ('Catalog entry pending' if pending_catalog else 'Name needs review'),
            'review_label': 'Open catalog' if canonical else ('Open candidate' if pending_catalog else 'Review name'),
            'href': '/entities/variety/'+quote(canonical, safe='') if canonical else
                    '/varieties/candidates?'+urlencode({'q':name,'berry':berry})+'#'+quote(str(candidate['id']),safe=''),
        })
        context = str(mention.get('mention_context') or '')[:240]
        if context and context not in row['notes']:
            row['notes'].append(context)
        for sid, source in associated:
            used_sources.add(sid)
            reference = {
                'id': sid, 'title': source['title'] or source['source_name'] or 'Captured article',
                'href': source['source_url'], 'reader_href': '/intelligence/'+quote(sid,safe='')+'?personal=1',
                'context': 'Source reviewed' if source['reviewed'] else 'Unreviewed source',
                'date_label': 'Published', 'date': source['published_date'], 'checked_on': '',
            }
            if reference not in row['sources']:
                row['sources'].append(reference)
    rows = sorted(grouped.values(), key=lambda row:(row['name'].casefold(),row['code'],row['berry_id']))
    for row in rows:
        row['notes'].append('This article is linked to this company. That does not establish breeding, ownership, licensing or a growing region.')
        row['search'] = ' '.join([row['name'],row['code'],*row['notes']]).casefold()
        row['letter'] = initial(row['name'])
    return rows, len(used_sources)
