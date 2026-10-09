"""Read-only profile-field inventory, not a completeness or trust score.

Uses existing catalog links, cited trait entries and permission-aware galleries.
Does not query footprints, acquire sources, approve identities or persist state.
"""
from collections import defaultdict
from urllib.parse import quote

from app.services.berries.variety import variety_patent_link
from app.services.variety_photos import gallery, source_photos
from app.services.variety_portfolio_coverage import reconcile_portfolios
from app.services.variety_universe.coverage import BERRY_LABELS, RIGHTS_SOURCE_TYPES

ROLE_LABELS = {
    'develops': 'Breeder', 'owns': 'Rights holder', 'licenses': 'Licensee',
    'markets': 'Marketer', 'grows': 'Grower', 'distributes': 'Distributor',
}
GAPS = (
    ('all', 'All profiles'), ('photos', 'No photo reference'),
    ('rights', 'No patent / PVR reference'), ('traits', 'No cited trait entry'),
    ('companies', 'No company role link'),
)


def _href(entity):
    return '/entities/' + quote(str(entity['entity_type']), safe='') + '/' + quote(str(entity['id']), safe='')


def profile_field_coverage(*, varieties, entities, relationships, published_evidence,
                           facts=(), portfolio_sources=(), reconciled_sources=None,
                           candidates=(), profiles=None, filters=None):
    """Inventory actual profile fields; preserve missing and unreviewed states."""
    profiles = profiles or {}
    filters = filters or {}
    index = {e['id']: e for e in entities if e.get('id')}
    patents = [e for e in entities if e.get('entity_type') == 'patent']
    published = {e['id']: e for e in published_evidence
                 if e.get('id') and e.get('status') == 'published'}
    rights_by_variety = defaultdict(list)
    roles_by_variety = defaultdict(list)
    source_by_variety = defaultdict(list)
    fact_traits_by_variety = defaultdict(set)
    for fact in facts:
        if fact.get('ai_proposed') or fact.get('status') in {'draft', 'pending', 'rejected'}:
            continue
        subjects = fact.get('entity_ids') or []
        if not str(fact.get('statement') or '').strip() or not any(
                index.get(eid, {}).get('entity_type') == 'trait' for eid in subjects):
            continue
        if any(eid in published for eid in fact.get('evidence_ids') or []):
            for vid in subjects:
                if index.get(vid, {}).get('entity_type') == 'variety' and fact.get('id'):
                    fact_traits_by_variety[vid].add(fact['id'])
    # Reuse identity/code discrepancy and saved human decision handling across
    # the entire source set, independent of the separate portfolio table filter.
    if reconciled_sources is None:
        reconciled_sources, _ = reconcile_portfolios(sources=portfolio_sources,
            varieties=varieties, entities=entities, candidates=candidates)
    for evidence in published.values():
        if evidence.get('source_type') in RIGHTS_SOURCE_TYPES:
            for entity_id in evidence.get('entity_ids') or []:
                rights_by_variety[entity_id].append(evidence)
    for relationship in relationships:
        party = index.get(relationship.get('subject_id'))
        if relationship.get('predicate') in ROLE_LABELS and party and party.get('entity_type') == 'company':
            roles_by_variety[relationship.get('object_id')].append({
                'name': party['name'], 'role': ROLE_LABELS[relationship['predicate']],
                'href': _href(party),
            })
    for source in reconciled_sources:
        for name in source.get('names') or []:
            if name.get('catalog_id') and not name.get('identity_notes'):
                source_by_variety[name['catalog_id']].append(source)

    rows = []
    for variety in varieties:
        vid = variety['id']
        attrs = variety.get('attributes') or {}
        traits = [t for t in attrs.get('traits') or [] if isinstance(t, dict)
                  and t.get('trait') and t.get('value') not in (None, '')]
        cited = sum(1 for t in traits if any(eid in published for eid in t.get('evidence_ids') or []))
        photos = gallery(variety, sourced=source_photos(variety, sources=portfolio_sources, varieties=varieties),
                         profile=profiles.get(vid), authoring=True)
        patent = variety_patent_link(variety, patents)
        # A number without a linked record is not a usable reference. Neither
        # a reference nor its publication state establishes current legal status.
        rights_refs = {('publication', e['id']) for e in rights_by_variety[vid]}
        if patent:
            rights_refs.add(('entity', patent['id']))
        for key in ('patent_id', 'rights_id'):
            explicit = index.get(attrs.get(key))
            if explicit and explicit.get('entity_type') == 'patent':
                rights_refs.add(('entity', explicit['id']))
        unreviewed_refs = {s['url'] for s in source_by_variety[vid]
                           if s.get('source_type') in {'plant_patent', 'national_register'}}
        roles = list({(r['name'], r['role'], r['href']): r for r in roles_by_variety[vid]}.values())
        missing = []
        if not photos:
            missing.append('photos')
        if not rights_refs and not unreviewed_refs:
            missing.append('rights')
        if not cited and not fact_traits_by_variety[vid]:
            missing.append('traits')
        if not roles:
            missing.append('companies')
        rows.append({
            'id': vid, 'name': variety['name'], 'href': _href(variety),
            'berries': [BERRY_LABELS.get(b, b) for b in variety.get('berry_ids') or []],
            'berry_ids': list(variety.get('berry_ids') or []),
            'status': str(variety.get('status') or 'unverified').replace('_', ' ').title(),
            'photos': len(photos), 'held_photos': sum(p['reuse'] == 'unknown' for p in photos),
            'rights_refs': len(rights_refs), 'unreviewed_rights_refs': len(unreviewed_refs),
            'patent_number_only': bool((attrs.get('patent_number') or attrs.get('us_plant_patent'))
                                      and not patent and not rights_refs and not unreviewed_refs),
            'cited_traits': cited + len(fact_traits_by_variety[vid]),
            'uncited_traits': len(traits) - cited,
            'company_links': roles, 'breeder_text_only': bool(attrs.get('breeder') and not roles),
            'missing': missing,
        })
    rows.sort(key=lambda r: (r['name'].casefold(), r['id']))
    scoped = [r for r in rows if not filters.get('profile_berry') or filters['profile_berry'] in r['berry_ids']]
    query = str(filters.get('profile_q') or '').strip()
    if query:
        scoped = [r for r in scoped if query.casefold() in r['name'].casefold()]
    gap = str(filters.get('profile_gap') or 'all')
    if gap not in dict(GAPS):
        gap = 'all'
    visible = [r for r in scoped if gap == 'all' or gap in r['missing']]
    return {
        'rows': visible, 'scoped_total': len(scoped), 'catalog_total': len(rows),
        'missing_counts': {key: sum(key in r['missing'] for r in scoped) for key, _ in GAPS if key != 'all'},
        'filters': {'profile_q': query, 'profile_berry': str(filters.get('profile_berry') or ''), 'profile_gap': gap},
        'gap_options': GAPS, 'berry_options': list(BERRY_LABELS.items()),
    }
