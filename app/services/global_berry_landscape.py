"""Read model over published Evidence, canonical profiles and stored relationships."""
from collections import defaultdict
from datetime import date

from app.services.berries.landscape import SEED_FIXTURE_ENTITY_IDS, SEED_FIXTURE_EVIDENCE_IDS
from app.services.geography_hierarchy import geography_descendants, record_geography_ids
from app.services.landscape_explorer import ROLE_LABELS
from app.services.map_regions import public_source_url


CROPS = {key: key.title() for key in ('blueberry', 'strawberry', 'raspberry', 'blackberry')}
REGIONS = {
    'north-america': 'North America', 'latin-america': 'Latin America', 'europe': 'Europe',
    'mea': 'Middle East and Africa', 'asia-pacific': 'Asia-Pacific',
}
ROLES = {
    'breeding': 'Breeding', 'rights': 'IP ownership and licensing', 'propagation': 'Propagation',
    'growing': 'Growing', 'packing': 'Packing', 'marketing': 'Marketing',
    'distribution': 'Distribution', 'retail': 'Retail',
}
EVENT_TYPES = {'ip': 'Plant IP', 'ownership': 'Ownership and investment', 'licensing': 'Licensing',
               'partnership': 'Partnerships', 'commercial': 'Commercial milestones', 'regulatory': 'Regulatory decisions'}
FOOTPRINT_TYPES = {'headquarters': 'Headquarters', 'production': 'Production', 'market': 'Sales markets',
                   'rights': 'Rights and licensing territories', 'operations': 'Other operations and trials'}
DIRECTORY_SORTS = {'name': 'Company name A–Z', 'name-desc': 'Company name Z–A', 'crops': 'Most tracked crops'}
ACTOR_TYPES = {'company', 'breeding_program', 'retailer'}
ROLE_PREDICATES = {'develops': 'breeding', 'licenses': 'rights', 'grows': 'growing',
                   'markets': 'marketing', 'distributes': 'distribution'}
DECLARED_ROLES = {
    'breeding': {'breeder', 'breeding', 'breeding_entity', 'private_breeding_program', 'public_breeding_program'},
    'rights': {'rights_holder', 'patent_assignee', 'genetics_licensor', 'genetics_sub_licensor',
               'genetics_licensee', 'licensee', 'licensing_body', 'genetics_owner'},
    'propagation': {'nursery', 'nursery_propagator', 'plant_producer'},
    'growing': {'grower', 'grower_marketer', 'grower_cooperative'}, 'packing': {'packer'},
    'marketing': {'marketer', 'marketing', 'grower_marketer'},
    'distribution': {'distributor', 'exporter', 'shipper'}, 'retail': {'grocery_retailer', 'retailer'},
}
EVENT_MARKERS = {
    'ip': {'ip', 'pbr', 'patent', 'patent_filing', 'plant_patent', 'plant_variety_protection', 'variety_registration'},
    'ownership': {'ownership', 'acquisition', 'merger', 'mergers_and_acquisitions', 'divestiture', 'investment'},
    'licensing': {'licensing', 'genetics_licensing', 'cultivar_license', 'propagation_agreement'},
    'partnership': {'partnership', 'joint_venture', 'breeding_partnership'},
    'commercial': {'commercial', 'commercial_launch', 'production_expansion', 'expansion', 'launch',
                   'product_launch', 'retail_exclusivity', 'market_access', 'market_entry', 'distribution_agreement'},
    'regulatory': {'regulatory', 'regulatory_decision', 'regulatory_status_review'},
}
REGION_ROOTS = {'north-america': 'geography-north-america', 'europe': 'geography-europe',
                'mea': 'geography-africa', 'asia-pacific': 'geography-apac'}
REGION_NAMES = {**{label.casefold(): key for key, label in REGIONS.items()},
                'africa': 'mea', 'middle east': 'mea', 'middle east & africa': 'mea', 'south america': 'latin-america'}


def filters_for(params, crop=''):
    filters = {key: str(params.get(key) or '').strip() for key in ('region', 'role', 'event_type', 'start', 'end', 'q')}
    filters.update(crop=crop, sort=str(params.get('sort') or 'name'))
    for key, choices in [('crop', CROPS), ('region', REGIONS), ('role', ROLES),
                         ('event_type', EVENT_TYPES), ('sort', DIRECTORY_SORTS)]:
        if filters[key] and filters[key] not in choices:
            raise ValueError(f'Choose a supported {key.replace("_", " ")}.')
    for key in ('start', 'end'):
        if filters[key] and _day(filters[key]) != filters[key]:
            raise ValueError('Use YYYY-MM-DD dates.')
    if filters['start'] and filters['end'] and filters['start'] > filters['end']:
        raise ValueError('The start date must precede or match the end date.')
    filters['q'] = filters['q'][:120]
    return filters


def _day(value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        return ''


def _in_window(value, filters):
    start, end = filters['start'], filters['end']
    return (not start or value and value >= start) and (not end or value and value <= end)


def _crops(row):
    return {key.removeprefix('berry-') for key in row.get('berry_ids') or []} & CROPS.keys()


def _display(row):
    kind, key = row['entity_type'], row['id']
    href = f'/geographies/{key}' if kind == 'geography' else f'/entities/{kind}/{key}'
    return {'id': key, 'name': row.get('name') or key, 'href': href, 'kind': kind}


def _source(row):
    return {'id': row['id'], 'title': row.get('title') or row['id'], 'source_type': row.get('source_type'),
            'source_name': row.get('source_name'), 'source_url': public_source_url(row.get('source_url')),
            'published_date': _day(row.get('published_date')), 'event_date': _day(row.get('event_date')),
            'summary': row.get('summary') or '', 'verification_state': row.get('verification_state') or '',
            'status': row.get('status'), 'evidence_links': [link for link in row.get('evidence_links') or []
                                                            if link.get('status') in {'accepted', 'contested'}],
            'href': f'/intelligence/{row["id"]}'}


def _public_record(row):
    return (row.get('status') == 'published' and row['id'] not in SEED_FIXTURE_EVIDENCE_IDS
            and not any(row.get(key) for key in ('is_demo', 'demo', 'illustrative', 'workspace_capture'))
            and row.get('data_class') not in {'internal', 'demo', 'illustrative', 'private'}
            and bool(public_source_url(row.get('source_url'))))


def _verified_support(row):
    return (row.get('verification_state') not in {'disputed', 'contradicted', 'unverified'}
            and not any(link.get('status') == 'contested' for link in row.get('evidence_links') or []))


def _geography_index(entities, relationships):
    regions = {key: region for region, root in REGION_ROOTS.items()
               for key in {root, *geography_descendants(root, relationships=relationships)}}
    names, codes = {}, {}
    for key, row in entities.items():
        if row.get('entity_type') != 'geography':
            continue
        attrs = row.get('attributes') or {}
        region = REGION_NAMES.get(str(attrs.get('region') or row.get('name') or '').casefold())
        if region:
            regions[key] = region
        for name in [row.get('name') or '', *(row.get('aliases') or [])]:
            if name:
                names[name.casefold()] = key
        if attrs.get('iso_3166_1_alpha_2'):
            codes[attrs['iso_3166_1_alpha_2']] = key
    if 'geography-europe' in entities:
        codes['EU'] = codes['EP'] = 'geography-europe'
    return regions, names, codes


def _event_type(row):
    if (row.get('patent_filing') or row.get('source_type') in {'patent_record', 'plant_breeders_rights_record'}):
        return 'ip'
    if row.get('commercial_observation'):
        return 'commercial'
    markers = {str(row.get('event_type') or '').lower().replace('-', '_')}
    # Historic collector tags may be search phrases. Use exact editorial tags only.
    markers.update(tag.replace('-', '_') for tag in row.get('tags') or [])
    return next((key for key, tags in EVENT_MARKERS.items() if markers & tags), '')


def _milestones(row, kind):
    patent = row.get('patent_filing') or {}
    if patent:
        keys = [('filing_date', 'Application filed'), ('publication_date', 'Publication'), ('grant_date', 'Grant')]
        dates = [(basis, label, _day(patent.get(basis))) for basis, label in keys]
        return [(basis, label, value) for basis, label, value in dates if value] or [('', 'Registry record', '')]
    stages = [(key, label, value) for key, label in [('announcement_date', 'Announced'), ('effective_date', 'Effective')]
              if (value := _day(row.get(key)))]
    event = _day(row.get('event_date'))
    if event and all(event != value for _, _, value in stages):
        stages.append(('event_date', 'Event date', event))
    if stages:
        return stages
    if kind == 'commercial' and (value := _day((row.get('commercial_observation') or {}).get('observed_at'))):
        return [('observed_at', 'Observed', value)]
    published = _day(row.get('published_date'))
    return [('published_date', 'Source published', published)] if published else [('', 'Date unrecorded', '')]


def _events(records, entities, regions, codes, filters, actor_roles, selected):
    grouped = {}
    event_candidates = {}
    prior_evidence = {row['landscape_event_key']: row for row in records.values() if row.get('landscape_event_key')}
    for row in records.values():
        kind = _event_type(row)
        crops = _crops(row) & selected
        if kind and crops and (not filters['event_type'] or filters['event_type'] == kind):
            event_candidates[row['id']] = (row, kind, crops)
    # Collapse explicit duplicate links only. Other relationships can be separate milestones.
    parent = {key: key for key in event_candidates}

    def root(key):
        while key != parent[key]:
            key = parent[key]
        return key

    for key, (row, kind, _) in event_candidates.items():
        for link in row.get('evidence_links') or []:
            target = link.get('target_evidence_id')
            if (target in parent and event_candidates[target][1] == kind and link.get('status') == 'accepted'
                    and link.get('predicate') == 'duplicates'):
                parent[root(key)] = root(target)
    # Older research packages marked reprints with a tag and linked the same
    # Fact and Relationship. Require both shared IDs and the same dated basis.
    legacy_links = defaultdict(list)
    for key, (row, kind, _) in event_candidates.items():
        stamp = _day(row.get('event_date')) or _day(row.get('published_date'))
        if kind == 'ip' or not stamp or row.get('landscape_event_key'):
            continue
        for fact in row.get('fact_ids') or []:
            for rel in row.get('relationship_ids') or []:
                legacy_links[kind, stamp, fact, rel].append(key)
    for keys in legacy_links.values():
        if len(keys) > 1 and any('republication' in (event_candidates[key][0].get('tags') or []) for key in keys):
            for key in keys[1:]:
                parent[root(key)] = root(keys[0])
    duplicate_roots = {root(key) for key in parent if parent[key] != key}
    ordered = sorted(event_candidates.values(), key=lambda item: 'republication' in (item[0].get('tags') or []))
    for row, kind, crops in ordered:
        parties = {key for key in [*(row.get('entity_ids') or []), *(row.get('company_ids') or [])]
                   if key in entities and entities[key].get('entity_type') in ACTOR_TYPES | {'variety'}}
        roles = {role for key in parties for crop in crops for role in actor_roles.get((key, crop), ())}
        if kind in {'ip', 'licensing'}:
            roles.add('rights')
        territory = str((row.get('patent_filing') or {}).get('jurisdiction') or '')
        geo_ids = record_geography_ids(row) & entities.keys()
        if territory in codes:
            geo_ids.add(codes[territory])
        geo_regions = {regions[key] for key in geo_ids if key in regions}
        source = {**_source(row), 'crops': sorted(crops), 'regions': sorted(geo_regions)}
        patent = row.get('patent_filing') or {}
        identifier = patent.get('publication_number') or patent.get('application_number') or ''
        deduped = root(row['id'])
        event_key = row.get('landscape_event_key')
        duplicate_key = (deduped if deduped in duplicate_roots else '') or row.get('syndication_group_id')
        identity = (event_key or (f'{territory}/{identifier}' if identifier else '') or duplicate_key
                    or row.get('canonical_url') or source['source_url'] or row['id'])
        for basis, label, stamp in _milestones(row, kind):
            if not patent and (event_key or duplicate_key):
                stage = basis if basis in {'announcement_date', 'effective_date'} else ''
                group = (kind, identity, stage, '')
            else:
                group = (kind, identity, basis, stamp)
            prior = prior_evidence.get(row.get('prior_event_key'))
            item = grouped.setdefault(group, {'id': row['id'], 'kind': kind, 'type_label': EVENT_TYPES[kind],
                                              'title': source['title'], 'summary': source['summary'], 'date': stamp,
                                              'event_key': event_key,
                                              'prior': _source(prior) if prior else None,
                                              'date_label': label, 'dates': set(), 'identifier': identifier, 'jurisdiction': territory,
                                              'cultivar_name': patent.get('cultivar_name'), 'application_number': patent.get('application_number'),
                                              'assignees': patent.get('assignees') or [], 'applicants': patent.get('applicants') or [],
                                              'crops': set(), 'regions': set(), 'places': set(), 'parties': set(),
                                              'roles': set(), 'sources': []})
            item['crops'].update(crops)
            item['regions'].update(geo_regions)
            item['places'].update(geo_ids)
            item['parties'].update(parties)
            item['roles'].update(roles)
            item['sources'].append(source)
            if stamp:
                item['dates'].add((basis, label, stamp))
    # A known syndicated item or corroborating source with a publication date
    # alone supports the same explicit milestone without creating a new one.
    for group, item in list(grouped.items()):
        if group[2:] != ('', '') or any(basis != 'published_date' for basis, _, _ in item['dates']):
            continue
        stages = [grouped[key] for basis in ('announcement_date', 'effective_date')
                  if (key := (*group[:2], basis, '')) in grouped]
        if stages:
            for stage in stages:
                stage['sources'].extend({**source, 'basis': 'Related publication · stage unrecorded'} for source in item['sources'])
            del grouped[group]
    result = []
    for item in grouped.values():
        dates = item.pop('dates')
        world_dates = {(label, stamp) for basis, label, stamp in dates if basis != 'published_date'}
        if len(world_dates) == 1:
            item['date_label'], item['date'] = next(iter(world_dates))
        elif len(world_dates) > 1:
            item['date_label'], item['date'] = 'Conflicting event dates', ''
        elif dates:
            item['date'] = min(stamp for _, _, stamp in dates)
        if (filters['region'] and filters['region'] not in item['regions']
                or filters['role'] and filters['role'] not in item['roles'] or not _in_window(item['date'], filters)):
            continue
        item['parties'] = [_display(entities[key]) for key in sorted(item['parties'])]
        item['places'] = sorted(entities[key]['name'] for key in item['places'])
        item['sources'] = list({source['id']: source for source in item['sources']}.values())
        item['crops'], item['regions'], item['roles'] = map(sorted, (item['crops'], item['regions'], item['roles']))
        query = filters['q'].casefold()
        haystack = ' '.join([item['title'], item['summary'], item['identifier'], item['cultivar_name'] or '',
                             item['application_number'] or '', *item['places'],
                             *(party['name'] for party in item['parties'])]).casefold()
        if query not in haystack:
            continue
        result.append(item)
    return sorted(result, key=lambda row: (row['date'], row['id']), reverse=True)


def _source_checked_milestones(rows, events, entities, records, filters):
    canonical_ids = {(event['kind'], source['id']) for event in events for source in event['sources']}
    event_keys = {event['event_key'] for event in events if event['event_key']}
    results = []
    for row in rows:
        kind = row['kind']
        existing = row.get('existing_evidence_id')
        if ((kind, existing) in canonical_ids or row['id'] in event_keys
                or filters['event_type'] and filters['event_type'] != kind or not _in_window(row['date'], filters)):
            continue
        parties = [_display(entities[key]) for key in row['entity_ids'] if key in entities]
        search_text = ' '.join([row['title'], row['summary'], row.get('identifier') or '',
                                *row['places'],
                                *(party['name'] for party in parties)]).casefold()
        if filters['q'].casefold() not in search_text:
            continue
        results.append({**row, 'parties': parties, 'type_label': EVENT_TYPES[kind],
                        'related_evidence': _source(records[existing]) if existing in records else None})
    return sorted(results, key=lambda row: (row['date'] or '', row['id']), reverse=True)


def model(*, entities, companies, relationships, evidence, coverage, filters):
    entities = {key: row for key, row in entities.items() if key not in SEED_FIXTURE_ENTITY_IDS}
    records = {row['id']: row for row in evidence if _public_record(row)}
    regions, names, codes = _geography_index(entities, relationships)
    selected = {filters['crop']} if filters['crop'] else set(CROPS)
    actor_crops = defaultdict(set)
    actor_roles = defaultdict(set)
    actor_regions = defaultdict(set)
    actor_sources = defaultdict(set)
    footprint, edges = [], []
    actors = {**companies, **{key: row for key, row in entities.items() if row.get('entity_type') in ACTOR_TYPES}}
    actors = {key: row for key, row in actors.items() if key not in SEED_FIXTURE_ENTITY_IDS
              and row.get('entity_type') in ACTOR_TYPES and not companies.get(key, {}).get('is_registry')}
    for key, row in actors.items():
        actor_crops[key].update(_crops(row) & selected)
        roles = set(row.get('roles') or [])
        for crop in actor_crops[key]:
            actor_roles[key, crop].update(role for role, names_ in DECLARED_ROLES.items() if names_ & roles)
        attrs = row.get('attributes') or {}
        if attrs.get('headquarters') and actor_crops[key]:
            geography = names.get(str(attrs.get('country') or '').casefold())
            region = regions.get(geography, '')
            actor_regions[key].update([region])
            sources = [_source(records[sid]) for sid in row.get('evidence_ids') or [] if sid in records
                       and (not _crops(records[sid]) or _crops(records[sid]) & selected)]
            footprint.append({'kind': 'headquarters', 'actor': _display(row), 'place': attrs['headquarters'],
                              'region': region, 'crops': sorted(actor_crops[key]), 'roles': [], 'sources': sources[:4],
                              'status': 'Profile headquarters', 'date': ''})
    for rel in relationships:
        left, right = (entities.get(rel.get(key), {}) for key in ('subject_id', 'object_id'))
        predicate = rel.get('predicate')
        if not left or not right or predicate not in ROLE_LABELS.keys() | {'carries'}:
            continue
        if rel.get('status') not in {'active', 'historical', 'disputed'}:
            continue
        source_rows = [records[key] for key in rel.get('evidence_ids') or [] if key in records]
        if not source_rows:
            continue
        source_crops = set().union(*(_crops(row) for row in source_rows))
        genetics = [row for row in (left, right) if row['entity_type'] in {'variety', 'breeding_program'} and _crops(row)]
        genetic_crops = set.intersection(*(_crops(row) for row in genetics)) if genetics else set(CROPS)
        direct_crops = _crops(rel) or (genetic_crops if genetics else set())
        # Legacy source tags can describe the topic of a search rather than the
        # crop served by a company. Generic links can narrow registered scope.
        # Only explicitly scoped or cultivar-specific role links can extend it.
        endpoint_crops = [_crops(row) for row in (left, right) if row['id'] in actors and _crops(row)]
        registered_crops = set.intersection(*endpoint_crops) if endpoint_crops else set()
        crops = (direct_crops or source_crops & registered_crops) & genetic_crops & selected
        crops = {crop for crop in crops if not any((row.get('attributes') or {}).get(f'{crop}_activity_identified') is False
                                                  for row in (left, right))}
        if not crops:
            continue
        geography = right['id'] if right['entity_type'] == 'geography' else ''
        geo_ids = {geography} if geography else set().union(*(record_geography_ids(row) for row in source_rows))
        geo_regions = {regions[key] for key in geo_ids if key in regions}
        role = ROLE_PREDICATES.get(predicate, '')
        if predicate == 'owns' and right['entity_type'] in {'variety', 'patent'}:
            role = 'rights'
        if predicate in {'sells', 'carries'} and (left['entity_type'] == 'retailer'
                or set(left.get('roles') or []) & DECLARED_ROLES['retail']):
            role = 'retail'
        status = rel['status'] if all(_verified_support(row) for row in source_rows) else 'needs review'
        stamp = _day(rel.get('effective_date'))
        sources = [_source(row) for row in source_rows]
        if status == 'active':
            for actor in {left['id'], right['id']} & actors.keys():
                if direct_crops and role and actor == left['id']:
                    actor_crops[actor].update(crops)
                if crops & actor_crops[actor]:
                    actor_sources[actor].update(source['id'] for source in sources)
            if left['id'] in actors and role:
                for crop in crops:
                    actor_roles[left['id'], crop].add(role)
            if geography:
                actor_regions[left['id']].update(geo_regions)
        if (filters['region'] and filters['region'] not in geo_regions or filters['role'] and role != filters['role']
                or not _in_window(stamp, filters)):
            continue
        label = 'Owns' if predicate == 'owns' and not role else ROLE_LABELS.get(predicate, 'Carries')
        edge = {'id': rel['id'], 'actor': _display(left), 'target': _display(right), 'role': role,
                'label': label, 'status': status, 'crops': sorted(crops),
                'date': stamp, 'notes': rel.get('notes') or '', 'sources': sources,
                'places': sorted(entities[key]['name'] for key in geo_ids & entities.keys())}
        edges.append(edge)
        if geography:
            kind = {'grows': 'production', 'markets': 'market', 'sells': 'market', 'distributes': 'market',
                    'licenses': 'rights'}.get(predicate, 'operations')
            footprint.append({'kind': kind, 'actor': edge['actor'], 'place': right['name'],
                              'region': regions.get(geography, ''), 'crops': edge['crops'],
                              'roles': [role] if role else [], 'sources': sources, 'status': status,
                              'date': stamp, 'notes': edge['notes']})
    observations = coverage.get('observations', [])
    for row in observations:
        key = row.get('entity_id')
        if key in actors:
            actor_crops[key].add(row['crop'])
            actor_roles[key, row['crop']].add(row['role'])
            actor_regions[key].add(row['region'])
        kind = row.get('geography_type')
        if kind in FOOTPRINT_TYPES:
            actor = _display(actors[key]) if key in actors else {'name': row.get('entity_name') or row['title']}
            footprint.append({'kind': kind, 'actor': actor, 'place': row['country'], 'region': row['region'],
                              'crops': [row['crop']], 'roles': [row['role']], 'status': 'Primary-source spot check',
                              'sources': [{'source_url': public_source_url(row['source_url']),
                                           'published_date': row.get('source_date')}], 'date': '',
                              'notes': row['summary'], 'metric': row.get('metric')})
    directory = []
    for key, row in actors.items():
        crops = actor_crops[key]
        roles = {role for crop in crops for role in actor_roles[key, crop]}
        if (not crops or filters['region'] and filters['region'] not in actor_regions[key]
                or filters['role'] and filters['role'] not in roles):
            continue
        source_ids = [key_ for key_ in row.get('evidence_ids') or [] if key_ in records
                      and (not _crops(records[key_]) or _crops(records[key_]) & crops)]
        source_ids = list(dict.fromkeys([*source_ids, *sorted(actor_sources[key])]))
        directory.append({**_display(row), 'href': row.get('profile_url') or _display(row)['href'],
                          'crops': sorted(crops), 'roles': sorted(roles), 'status': row.get('status') or 'unverified',
                          'headquarters': (row.get('attributes') or {}).get('headquarters'),
                          'sources': [_source(records[key_]) for key_ in source_ids[:3]]})
    directory.sort(key=lambda row: row['name'].casefold(), reverse=filters['sort'] == 'name-desc')
    if filters['sort'] == 'crops':
        directory.sort(key=lambda row: len(row['crops']), reverse=True)
    footprint = [row for row in footprint if (not filters['region'] or row['region'] == filters['region'])
                 and (not filters['role'] or filters['role'] in row['roles']
                      or any(filters['role'] in actor_roles[row['actor'].get('id'), crop] for crop in row['crops']))]
    events = _events(records, entities, regions, codes, filters, actor_roles, selected)
    milestones = _source_checked_milestones(coverage.get('milestones', []), events, entities, records, filters)
    return {'companies': directory, 'relationships': sorted(edges, key=lambda row: (row['date'], row['id']), reverse=True),
            'footprint': sorted(footprint, key=lambda row: (row['kind'], row['place'], row['actor']['name'])),
            'events': events, 'coverage': {**coverage, 'milestones': milestones},
            'map_geographies': sorted(key for key, region in regions.items() if region == filters['region'])}
