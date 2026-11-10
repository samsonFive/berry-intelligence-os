import pytest
from fastapi import HTTPException, Request

from app import main
from app.berry_landscape_routes import global_berry_landscape, global_berry_overview
from app.services import company_directory, global_berry_landscape as landscape


@pytest.fixture
def world():
    def entity(key, kind, name, crops=(), **attrs):
        return {'id': key, 'entity_type': kind, 'name': name, 'status': 'active', 'berry_ids': crops,
                'attributes': attrs}

    entities = {
        'company-example': entity('company-example', 'company', 'Example Berries',
                                  ['berry-blueberry', 'berry-strawberry'], headquarters='Toronto', country='Canada'),
        'variety-signal': entity('variety-signal', 'variety', 'Signal', ['berry-blueberry']),
        'geography-mexico': entity('geography-mexico', 'geography', 'Mexico', region='Latin America'),
        'geography-canada': entity('geography-canada', 'geography', 'Canada', region='North America'),
    }
    first = {'id': 'ev-first', 'status': 'published', 'source_type': 'company_press_release',
             'title': 'Cultivar licensing announced', 'summary': 'Blueberry license in Mexico.',
             'source_url': 'https://example.com/first', 'verification_state': 'verified_primary',
             'published_date': '2026-07-05', 'event_date': '2026-07-01', 'event_type': 'licensing',
             'landscape_event_key': 'blueberry-signal-mexico', 'berry_ids': ['berry-blueberry'],
             'entity_ids': ['company-example', 'variety-signal', 'geography-mexico']}
    second = {**first, 'id': 'ev-reprint', 'source_url': 'https://example.org/reprint',
              'verification_state': 'single_source', 'published_date': '2026-07-08', 'event_date': None}
    held = {**first, 'id': 'ev-held', 'status': 'in_review', 'title': 'Held lead'}
    demo = {**first, 'id': 'ev-demo', 'demo': True, 'title': 'Demo event'}
    relationships = [
        {'id': 'rel-license', 'subject_id': 'company-example', 'object_id': 'variety-signal',
         'predicate': 'licenses', 'status': 'active', 'evidence_ids': ['ev-first'], 'effective_date': '2026-07-01'},
        {'id': 'rel-operates', 'subject_id': 'company-example', 'object_id': 'geography-mexico',
         'predicate': 'operates_in', 'status': 'active', 'evidence_ids': ['ev-first']},
    ]
    return dict(entities=entities, companies={}, relationships=relationships, evidence=[first, second, held, demo],
                coverage={'observations': []})


def test_event_key_groups_sources_and_retains_event_and_publication_dates(world):
    model = landscape.model(**world, filters=landscape.filters_for(
        {'region': 'latin-america', 'event_type': 'licensing', 'q': 'Signal', 'start': '2026-07-01', 'end': '2026-07-01'},
        'blueberry'))
    assert len(model['events']) == 1
    event = model['events'][0]
    assert event['date'] == '2026-07-01'
    assert event['date_label'] == 'Event date'
    assert {source['id']: source['published_date'] for source in event['sources']} == {
        'ev-first': '2026-07-05', 'ev-reprint': '2026-07-08'}
    assert {party['href'] for party in event['parties']} == {'/entities/company/company-example', '/entities/variety/variety-signal'}
    assert [relationship['id'] for relationship in model['relationships']] == ['rel-license']


def test_announcement_and_effective_dates_remain_distinct_for_the_same_event(world):
    source = world['evidence'][0]
    source.update(announcement_date='2026-07-01', effective_date='2026-07-18')
    model = landscape.model(**world, filters=landscape.filters_for({}, 'blueberry'))
    assert [(row['date_label'], row['date']) for row in model['events']] == [
        ('Effective', '2026-07-18'), ('Announced', '2026-07-01')]
    assert all({source['id'] for source in row['sources']} == {'ev-first', 'ev-reprint'} for row in model['events'])


def test_multicrop_company_keeps_role_and_geography_scoped(world):
    blue = landscape.model(**world, filters=landscape.filters_for({'role': 'rights'}, 'blueberry'))
    red = landscape.model(**world, filters=landscape.filters_for({}, 'strawberry'))
    assert [row['id'] for row in blue['companies']] == [row['id'] for row in red['companies']] == ['company-example']
    assert blue['companies'][0]['roles'] == ['rights']
    assert red['companies'][0]['roles'] == []
    assert not red['events'] and not red['relationships']
    worldwide = landscape.model(**world, filters=landscape.filters_for({}, 'blueberry'))
    assert {(row['kind'], row['place']) for row in worldwide['footprint']} == {
        ('headquarters', 'Toronto'), ('operations', 'Mexico')}


def test_generic_relationships_cannot_expand_company_crop_scope(world):
    entity = world['entities']['company-example']
    entity['berry_ids'] = ['berry-raspberry']
    entity['attributes']['blueberry_activity_identified'] = False
    # A collector topic and generic operating location carry no blueberry role.
    world['relationships'].pop(0)
    overview = landscape.model(**world, filters=landscape.filters_for({}))
    assert overview['companies'][0]['crops'] == ['raspberry']
    assert not overview['relationships']
    assert [row['kind'] for row in overview['footprint']] == ['headquarters']
    blue = landscape.model(**world, filters=landscape.filters_for({}, 'blueberry'))
    assert not blue['companies']


def test_overview_and_all_crop_routes_include_five_sections_and_legacy_handoff(monkeypatch, world):
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    monkeypatch.setattr(main, 'entity_index', lambda: world['entities'])
    monkeypatch.setattr(main, 'all_relationships', lambda: world['relationships'])
    monkeypatch.setattr(main, 'published_evidence', lambda: world['evidence'])
    monkeypatch.setattr(company_directory, 'catalog', lambda _: world['companies'])
    routes = {getattr(route, 'path', ''): getattr(route, 'endpoint', None) for route in main.app.routes}
    assert routes['/landscapes/global'] is global_berry_overview
    assert routes['/landscapes/global/{crop}'] is global_berry_landscape

    def request(crop='', query=b''):
        return Request({'type': 'http', 'app': main.app, 'router': main.app.router, 'method': 'GET',
                        'scheme': 'http', 'server': ('testserver', 80), 'headers': [], 'session': {},
                        'path': '/landscapes/global' + (f'/{crop}' if crop else ''), 'query_string': query})

    for crop in ('', *landscape.CROPS):
        response = global_berry_landscape(request(crop), crop) if crop else global_berry_overview(request())
        assert response.status_code == 200
        body = response.body.decode()
        for section in ('companies', 'footprint', 'relationships', 'events', 'coverage'):
            assert f'id="{section}"' in body
        assert 'berry-strategy-review' not in body
        if crop:
            assert f'href="/landscapes/berries/{crop}"' in body
    with pytest.raises(HTTPException) as unknown_crop:
        global_berry_landscape(request('missing'), 'missing')
    assert unknown_crop.value.status_code == 404
    with pytest.raises(HTTPException) as unknown_region:
        global_berry_overview(request(query=b'region=missing'))
    assert unknown_region.value.status_code == 422
